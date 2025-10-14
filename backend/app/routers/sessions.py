import json
import logging
import time
from datetime import datetime

import chess
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..models.schemas import MoveRecord, MoveResult, SessionCreateResponse, SessionStateResponse, TurnResponse
from ..services.game_state import store
from ..services.llm import MoveInterpreter, get_move_interpreter
from ..services.stockfish import get_stockfish_service
from ..services.transcription import TranscriptionService, get_transcription_service
from ..services.tts import get_tts_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_interpreter() -> MoveInterpreter:
    return get_move_interpreter()


def get_transcriber() -> TranscriptionService:
    return get_transcription_service()


@router.post("", response_model=SessionCreateResponse)
async def create_session(skill_level: int = 5) -> SessionCreateResponse:
    # Clamp skill level between 0 and 20
    skill_level = max(0, min(20, skill_level))
    session = await store.create_session(skill_level=skill_level)
    return SessionCreateResponse(session_id=session.session_id, fen=session.board.fen(), moves=session.moves)


@router.put("/{session_id}/skill-level")
async def update_skill_level(session_id: str, skill_level: int):
    try:
        # Clamp skill level between 0 and 20
        skill_level = max(0, min(20, skill_level))
        store.update_skill_level(session_id, skill_level)
        return {"skill_level": skill_level}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.get("/{session_id}", response_model=SessionStateResponse)
async def get_session(session_id: str) -> SessionStateResponse:
    try:
        return store.to_response(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.get("/{session_id}/tts/{move_san}")
async def get_move_speech(session_id: str, move_san: str):
    """Generate TTS audio for a chess move."""
    from fastapi.responses import Response
    
    try:
        # Verify session exists
        store.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    
    tts = get_tts_service()
    audio_bytes = tts.generate_speech(move_san)
    
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/{session_id}/turn", response_model=TurnResponse)
async def take_turn(
    session_id: str,
    audio: UploadFile = File(...),
    interpreter: MoveInterpreter = Depends(get_interpreter),
    transcriber: TranscriptionService = Depends(get_transcriber),
):
    request_start = time.time()
    logger.info("Starting turn processing for session %s", session_id)
    
    try:
        session = store.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc

    # Step 1: Transcription
    transcription_start = time.time()
    transcript = await transcriber.transcribe(audio)
    transcription_time = time.time() - transcription_start
    logger.info("Transcription completed in %.2fs: %s", transcription_time, transcript)

    # Step 2: LLM Interpretation
    interpretation_start = time.time()
    interpretation = await interpreter.interpret(transcript, session.board)
    interpretation_time = time.time() - interpretation_start
    logger.info("LLM interpretation completed in %.2fs: %s", interpretation_time, interpretation.uci)

    # Try to parse the move - handle both UCI and SAN notation
    player_move = None
    move_str = interpretation.uci.strip().lower()
    
    try:
        # First try as UCI (e.g., "g1f3")
        player_move = chess.Move.from_uci(move_str)
        logger.debug("Parsed as UCI move: %s", player_move)
    except ValueError:
        # Try stripping piece prefix (e.g., "ng1f3" -> "g1f3", "ke1g1" -> "e1g1")
        if len(move_str) >= 5 and move_str[0] in 'nbrqkp':
            try:
                stripped = move_str[1:]
                player_move = chess.Move.from_uci(stripped)
                logger.info("Stripped piece prefix '%s' -> UCI: %s", move_str, player_move.uci())
            except ValueError:
                pass
        
        if not player_move:
            # If UCI fails, try parsing as SAN notation (e.g., "Nf3", "nf3")
            try:
                player_move = session.board.parse_san(interpretation.uci)
                logger.info("Converted SAN '%s' to UCI: %s", interpretation.uci, player_move.uci())
            except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError):
                # Try case-insensitive SAN
                try:
                    # Capitalize piece letters for SAN parsing (e.g., "nf3" -> "Nf3")
                    san_normalized = interpretation.uci[0].upper() + interpretation.uci[1:] if interpretation.uci and interpretation.uci[0].isalpha() else interpretation.uci
                    player_move = session.board.parse_san(san_normalized)
                    logger.info("Converted normalized SAN '%s' to UCI: %s", san_normalized, player_move.uci())
                except Exception:
                    pass
        
        if not player_move:
            logger.error("Invalid move string from LLM: '%s'", interpretation.uci)
            logger.error("Transcript was: '%s'", transcript)
            raise HTTPException(
                status_code=400, 
                detail=f"Could not understand move: Heard \"{transcript}\" but couldn't interpret it as a valid chess move. Please try again."
            )

    if player_move not in session.board.legal_moves:
        legal_moves_uci = [m.uci() for m in session.board.legal_moves]
        logger.error("Illegal move attempted: %s", player_move.uci())
        logger.error("Legal moves were: %s", ", ".join(legal_moves_uci))
        logger.error("Board position (FEN): %s", session.board.fen())
        logger.error("Transcript was: '%s'", transcript)
        raise HTTPException(
            status_code=400, 
            detail=f"Illegal move: Heard \"{transcript}\" but {player_move.uci()} is not a legal move in this position."
        )

    player_san = session.board.san(player_move)
    session.board.push(player_move)

    ply_index = len(session.moves) + 1
    player_record = MoveRecord(
        ply=ply_index,
        actor="player",
        uci=interpretation.uci,
        san=player_san,
        transcript=transcript,
        timestamp=datetime.utcnow(),
    )
    store.add_move(session_id, player_record)

    # Check if user delivered checkmate or stalemate
    if session.board.is_checkmate():
        logger.info("Player delivered checkmate!")
        total_time = time.time() - request_start
        logger.info("Turn completed in %.2fs (checkmate)", total_time)
        return TurnResponse(
            transcript=transcript,
            user_move=MoveResult(uci=interpretation.uci, san=player_san),
            engine_move=MoveResult(uci="", san="Checkmate!"),
            fen=session.board.fen(),
            moves=session.moves,
        )
    
    if session.board.is_stalemate():
        logger.info("Game ended in stalemate")
        total_time = time.time() - request_start
        logger.info("Turn completed in %.2fs (stalemate)", total_time)
        return TurnResponse(
            transcript=transcript,
            user_move=MoveResult(uci=interpretation.uci, san=player_san),
            engine_move=MoveResult(uci="", san="Stalemate"),
            fen=session.board.fen(),
            moves=session.moves,
        )

    # Step 3: Engine Move
    engine_start = time.time()
    engine = get_stockfish_service()
    engine_move = await engine.choose_move(session.board, skill_level=session.skill_level)
    engine_time = time.time() - engine_start
    logger.info("Stockfish (level %d) move completed in %.2fs: %s", session.skill_level, engine_time, engine_move.uci())

    engine_san = session.board.san(engine_move)
    session.board.push(engine_move)
    
    # Check if engine delivered checkmate or stalemate
    if session.board.is_checkmate():
        logger.info("Engine delivered checkmate!")
        engine_san += "#"  # Add checkmate symbol
    elif session.board.is_stalemate():
        logger.info("Game ended in stalemate after engine move")
        engine_san += " (Stalemate)"

    engine_record = MoveRecord(
        ply=ply_index + 1,
        actor="engine",
        uci=engine_move.uci(),
        san=engine_san,
        transcript=None,
        timestamp=datetime.utcnow(),
    )
    store.add_move(session_id, engine_record)

    total_time = time.time() - request_start
    logger.info(
        "Turn completed in %.2fs (transcription: %.2fs, interpretation: %.2fs, engine: %.2fs)",
        total_time, transcription_time, interpretation_time, engine_time
    )

    return TurnResponse(
        transcript=transcript,
        user_move=MoveResult(uci=interpretation.uci, san=player_san),
        engine_move=MoveResult(uci=engine_move.uci(), san=engine_san),
        fen=session.board.fen(),
        moves=session.moves,
    )


@router.post("/{session_id}/turn-stream")
async def take_turn_stream(
    session_id: str,
    audio: UploadFile = File(...),
    interpreter: MoveInterpreter = Depends(get_interpreter),
    transcriber: TranscriptionService = Depends(get_transcriber),
):
    # Read audio file contents once before streaming starts
    audio_contents = await audio.read()
    audio_filename = audio.filename
    audio_content_type = audio.content_type
    
    async def event_generator():
        request_start = time.time()
        logger.info("Starting streaming turn for session %s", session_id)
        
        try:
            session = store.get_session(session_id)
        except KeyError:
            yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
            return

        try:
            # Step 1: Transcription
            yield f"data: {json.dumps({'status': 'transcribing'})}\n\n"
            transcription_start = time.time()
            transcript = await transcriber.transcribe_bytes(audio_contents, audio_filename, audio_content_type)
            transcription_time = time.time() - transcription_start
            logger.info("Transcription completed in %.2fs: %s", transcription_time, transcript)
            yield f"data: {json.dumps({'status': 'transcribed', 'transcript': transcript})}\n\n"

            # Step 2: LLM Interpretation
            yield f"data: {json.dumps({'status': 'interpreting'})}\n\n"
            interpretation_start = time.time()
            interpretation = await interpreter.interpret(transcript, session.board)
            interpretation_time = time.time() - interpretation_start
            logger.info("LLM interpretation completed in %.2fs: %s", interpretation_time, interpretation.uci)
            
            # Try to parse the move - handle both UCI and SAN notation
            player_move = None
            move_str = interpretation.uci.strip().lower()
            
            try:
                # First try as UCI (e.g., "g1f3")
                player_move = chess.Move.from_uci(move_str)
                logger.debug("Parsed as UCI move: %s", player_move)
            except ValueError:
                # Try stripping piece prefix (e.g., "ng1f3" -> "g1f3", "ke1g1" -> "e1g1")
                if len(move_str) >= 5 and move_str[0] in 'nbrqkp':
                    try:
                        stripped = move_str[1:]
                        player_move = chess.Move.from_uci(stripped)
                        logger.info("Stripped piece prefix '%s' -> UCI: %s", move_str, player_move.uci())
                    except ValueError:
                        pass
                
                if not player_move:
                    # If UCI fails, try parsing as SAN notation (e.g., "Nf3", "nf3")
                    try:
                        player_move = session.board.parse_san(interpretation.uci)
                        logger.info("Converted SAN '%s' to UCI: %s", interpretation.uci, player_move.uci())
                    except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError):
                        # Try case-insensitive SAN
                        try:
                            # Capitalize piece letters for SAN parsing (e.g., "nf3" -> "Nf3")
                            san_normalized = interpretation.uci[0].upper() + interpretation.uci[1:] if interpretation.uci and interpretation.uci[0].isalpha() else interpretation.uci
                            player_move = session.board.parse_san(san_normalized)
                            logger.info("Converted normalized SAN '%s' to UCI: %s", san_normalized, player_move.uci())
                        except Exception:
                            pass
                
                if not player_move:
                    logger.error("Invalid move string from LLM: '%s'", interpretation.uci)
                    logger.error("Transcript was: '%s'", transcript)
                    error_msg = f"Could not understand move: Heard \"{transcript}\" but couldn't interpret it as a valid chess move. Please try again."
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                    return

            if player_move not in session.board.legal_moves:
                legal_moves_uci = [m.uci() for m in session.board.legal_moves]
                logger.error("Illegal move attempted: %s", player_move.uci())
                logger.error("Legal moves were: %s", ", ".join(legal_moves_uci))
                logger.error("Board position (FEN): %s", session.board.fen())
                logger.error("Transcript was: '%s'", transcript)
                error_msg = f"Illegal move: Heard \"{transcript}\" but {player_move.uci()} is not a legal move in this position."
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                return

            player_san = session.board.san(player_move)
            session.board.push(player_move)

            ply_index = len(session.moves) + 1
            player_record = MoveRecord(
                ply=ply_index,
                actor="player",
                uci=interpretation.uci,
                san=player_san,
                transcript=transcript,
                timestamp=datetime.utcnow(),
            )
            store.add_move(session_id, player_record)

            yield f"data: {json.dumps({'status': 'player_moved', 'move': {'uci': interpretation.uci, 'san': player_san}})}\n\n"

            # Check if user delivered checkmate or stalemate
            if session.board.is_checkmate():
                logger.info("Player delivered checkmate!")
                total_time = time.time() - request_start
                logger.info("Streaming turn completed in %.2fs (checkmate)", total_time)
                result = {
                    'status': 'complete',
                    'transcript': transcript,
                    'user_move': {'uci': interpretation.uci, 'san': player_san + '#'},
                    'engine_move': {'uci': '', 'san': 'Checkmate!'},
                    'fen': session.board.fen(),
                }
                yield f"data: {json.dumps(result)}\n\n"
                return
            
            if session.board.is_stalemate():
                logger.info("Game ended in stalemate")
                total_time = time.time() - request_start
                logger.info("Streaming turn completed in %.2fs (stalemate)", total_time)
                result = {
                    'status': 'complete',
                    'transcript': transcript,
                    'user_move': {'uci': interpretation.uci, 'san': player_san},
                    'engine_move': {'uci': '', 'san': 'Stalemate'},
                    'fen': session.board.fen(),
                }
                yield f"data: {json.dumps(result)}\n\n"
                return

            # Step 3: Engine Move
            yield f"data: {json.dumps({'status': 'engine_thinking'})}\n\n"
            engine_start = time.time()
            engine = get_stockfish_service()
            engine_move = await engine.choose_move(session.board, skill_level=session.skill_level)
            engine_time = time.time() - engine_start
            logger.info("Stockfish (level %d) move completed in %.2fs: %s", session.skill_level, engine_time, engine_move.uci())
            engine_san = session.board.san(engine_move)
            session.board.push(engine_move)
            
            # Check if engine delivered checkmate or stalemate
            if session.board.is_checkmate():
                logger.info("Engine delivered checkmate!")
                engine_san += "#"  # Add checkmate symbol
            elif session.board.is_stalemate():
                logger.info("Game ended in stalemate after engine move")
                engine_san += " (Stalemate)"

            engine_record = MoveRecord(
                ply=ply_index + 1,
                actor="engine",
                uci=engine_move.uci(),
                san=engine_san,
                transcript=None,
                timestamp=datetime.utcnow(),
            )
            store.add_move(session_id, engine_record)

            # Final result
            total_time = time.time() - request_start
            logger.info(
                "Streaming turn completed in %.2fs (transcription: %.2fs, interpretation: %.2fs, engine: %.2fs)",
                total_time, transcription_time, interpretation_time, engine_time
            )
            
            result = {
                'status': 'complete',
                'transcript': transcript,
                'user_move': {'uci': interpretation.uci, 'san': player_san},
                'engine_move': {'uci': engine_move.uci(), 'san': engine_san},
                'fen': session.board.fen(),
            }
            yield f"data: {json.dumps(result)}\n\n"

        except Exception as e:
            logger.exception("Error in streaming turn")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
