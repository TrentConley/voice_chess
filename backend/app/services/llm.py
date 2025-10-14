from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import chess
from fastapi import HTTPException
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from ..core.llm import get_openai_client


logger = logging.getLogger(__name__)


MOVE_FUNCTION = {
    "type": "function",
    "name": "submit_move",
    "description": "Normalize a spoken chess move into UCI format.",
    "parameters": {
        "type": "object",
        "properties": {
            "uci": {"type": "string", "description": "Move in UCI notation"},
            "san": {"type": "string", "description": "Move in SAN notation"},
        },
        "required": ["uci"],
        "additionalProperties": False,
    },
}


@dataclass
class MoveInterpretation:
    uci: str
    san_hint: Optional[str] = None


class MoveInterpreter:
    def __init__(self) -> None:
        self.client = get_openai_client()

    async def interpret(self, transcript: str, board: chess.Board) -> MoveInterpretation:
        logger.info("Interpreting transcript: '%s'", transcript)
        logger.debug("Current FEN: %s", board.fen())
        legal_moves_formatted = [f"{move.uci()} ({board.san(move)})" for move in board.legal_moves]
        logger.debug("Legal moves (%d): %s", len(legal_moves_formatted), ", ".join(legal_moves_formatted[:10]) + ("..." if len(legal_moves_formatted) > 10 else ""))
        
        try:
            response = await asyncio.to_thread(self._invoke, transcript, board)
            logger.debug("LLM raw response: %s", response)
        except RetryError as exc:
            logger.exception("LLM interpretation failed after retries")
            raise HTTPException(status_code=502, detail="LLM interpretation failed") from exc

        move = self._parse_response(response)
        if not move:
            logger.warning("LLM returned no interpretable move for transcript: %s", transcript)
            logger.warning("Raw response was: %s", response)
            raise HTTPException(status_code=400, detail="Unable to interpret move from transcript")
        
        # Validate UCI and try fallback to SAN parsing if invalid
        uci_lower = move.uci.lower()
        try:
            # Try to parse as UCI first
            chess.Move.from_uci(uci_lower)
            logger.info("LLM interpreted move: uci=%s, san_hint=%s", uci_lower, move.san_hint)
            return MoveInterpretation(uci=uci_lower, san_hint=move.san_hint)
        except (ValueError, chess.InvalidMoveError):
            # UCI is invalid, try to parse as SAN notation
            logger.warning("Invalid UCI from LLM: '%s', attempting SAN fallback", uci_lower)
            
            # Try multiple case variations of the move string
            san_variations = [move.uci]  # Original
            
            # If starts with a piece letter (r/n/b/q/k in any case), try both cases
            if move.uci and move.uci[0].lower() in 'rnbqk':
                first_char = move.uci[0]
                rest = move.uci[1:]
                # Try both uppercase and lowercase
                san_variations.append(first_char.upper() + rest)
                san_variations.append(first_char.lower() + rest)
                # Remove duplicates while preserving order
                san_variations = list(dict.fromkeys(san_variations))
            
            logger.debug("Trying SAN variations for '%s': %s", move.uci, san_variations)
            
            for san_attempt in san_variations:
                try:
                    # Try parsing as SAN (e.g., 'bxc3', 'Re1', 'Nf3')
                    parsed_move = board.parse_san(san_attempt)
                    corrected_uci = parsed_move.uci()
                    logger.info("Successfully parsed as SAN. Corrected: %s -> %s", san_attempt, corrected_uci)
                    return MoveInterpretation(uci=corrected_uci, san_hint=board.san(parsed_move))
                except (ValueError, chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError):
                    continue  # Try next variation
            
            # All variations failed
            logger.error("Failed to parse '%s' as either UCI or SAN (tried: %s)", move.uci, san_variations)
            raise HTTPException(
                status_code=400, 
                detail=f"LLM returned invalid move format: '{move.uci}'"
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _invoke(self, transcript: str, board: chess.Board):
        prompt = (
            "You convert spoken chess commands into machine-readable moves. "
            "You will receive a list of legal moves in the format: 'UCI (SAN)' where:\n"
            "- UCI is the format you MUST return (e.g., 'e2e4', 'g1f3', 'a1e1')\n"
            "- SAN is shown in parentheses to help you identify the move (e.g., 'e4', 'Nf3', 'Re1')\n"
            "\n"
            "IMPORTANT: You must return the UCI part ONLY, not the SAN part.\n"
            "For example, if you see 'a1e1 (Re1)' and the user says 'rook e1', return 'a1e1' NOT 're1'.\n"
            "\n"
            "SAN notation guide (for matching spoken commands):\n"
            "- K = King, Q = Queen, R = Rook, B = Bishop, N = Knight, no prefix = Pawn\n"
            "- 'x' indicates a capture (e.g., 'Bxg8' = bishop captures on g8)\n"
            "\n"
            "Common speech patterns (match against SAN, return UCI):\n"
            "- 'bishop e4' → find move with '(Be4)' or '(Bce4)' or '(Bfe4)', return its UCI\n"
            "- 'rook e1' → find move with '(Re1)' or '(Rae1)' or '(Rfe1)', return its UCI\n"
            "- 'knight f3' → find move with '(Nf3)' or '(Ngf3)' or '(Nef3)', return its UCI\n"
            "- 'e4' → find move with '(e4)' or '(e3e4)', return its UCI\n"
            "- 'bishop takes' → find any move with '(Bx...)', return its UCI\n"
            "- 'rook takes d5' → find move with '(Rxd5)', return its UCI\n"
            "\n"
            "CRITICAL: Only return a move if the spoken command clearly matches a legal move. "
            "If the spoken command refers to a move that doesn't exist in the legal moves list "
            "(e.g., 'f3 takes g6' when no piece on f3 can capture g6), call the function with an empty string. "
            "Do NOT guess or return a different move than what was spoken."
        )
        legal_moves_formatted = []
        for move in board.legal_moves:
            uci = move.uci()
            san = board.san(move)
            legal_moves_formatted.append(f"{uci} ({san})")
        
        input_messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": f"Current FEN: {board.fen()}"},
                    {"type": "input_text", "text": f"Legal moves: {', '.join(legal_moves_formatted)}"},
                    {"type": "input_text", "text": f"Transcript: {transcript}"},
                ],
            },
        ]
        
        logger.info("LLM input messages: %s", json.dumps(input_messages, indent=2))

        return self.client.responses.create(
            model="gpt-4o-mini",  # Much faster than gpt-5, still excellent quality
            input=input_messages,
            tools=[MOVE_FUNCTION],
        )

    def _parse_response(self, response) -> Optional[MoveInterpretation]:
        items = getattr(response, "output", None) or []
        logger.debug("Parsing response with %d output items", len(items))
        
        for item in items:
            item_type = getattr(item, "type", None)
            item_name = getattr(item, "name", None)
            logger.debug("Output item: type=%s, name=%s", item_type, item_name)
            
            if item_type == "function_call" and item_name == "submit_move":
                arguments = getattr(item, "arguments", {})
                logger.debug("Function call arguments (raw): %s (type: %s)", arguments, type(arguments).__name__)
                
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                        logger.debug("Parsed JSON arguments: %s", arguments)
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse arguments as JSON: %s", e)
                        arguments = {"uci": arguments}
                
                uci = (arguments or {}).get("uci", "").strip()
                san = (arguments or {}).get("san")
                logger.info("Extracted from function call: uci='%s', san='%s'", uci, san)
                
                if uci:
                    return MoveInterpretation(uci=uci, san_hint=san)

        fallback = getattr(response, "output_text", None)
        if fallback:
            logger.debug("No function call found, trying fallback text: %s", fallback)
            match = re.search(r"([a-h][1-8][a-h][1-8][nbrq]?)", fallback)
            if match:
                logger.info("Extracted from fallback text: uci='%s'", match.group(1))
                return MoveInterpretation(uci=match.group(1))

        logger.warning("Could not extract move from response")
        return None


def get_move_interpreter() -> MoveInterpreter:
    return MoveInterpreter()
