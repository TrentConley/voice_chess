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

from ..core.llm import get_groq_client
from ..core.config import get_settings


logger = logging.getLogger(__name__)


MOVE_FUNCTION = {
    "type": "function",
    "function": {
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
    },
}


@dataclass
class MoveInterpretation:
    uci: str
    san_hint: Optional[str] = None


class MoveInterpreter:
    def __init__(self) -> None:
        self.client = get_groq_client()
        settings = get_settings()
        self.model = settings.groq_llm_model or "llama-3.1-70b-versatile"

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

        # Convert to standard chat completion format
        messages = []
        for msg in input_messages:
            role = msg["role"]
            content_parts = msg["content"]
            # Combine all text parts into a single string
            text = "\n".join([part["text"] for part in content_parts if part.get("type") == "input_text"])
            messages.append({"role": role, "content": text})
        
        logger.info("Calling Groq with model: %s", self.model)
        
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=[MOVE_FUNCTION],
            temperature=0.0,  # Deterministic for consistent move parsing
        )

    def _parse_response(self, response) -> Optional[MoveInterpretation]:
        # Parse standard OpenAI chat completion response
        logger.debug("Parsing chat completion response: %s", response)
        
        if not response.choices:
            logger.warning("No choices in response")
            return None
        
        message = response.choices[0].message
        
        # Check for tool calls (function calls)
        if message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.function.name == "submit_move":
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                        logger.debug("Function call arguments: %s", arguments)
                        
                        uci = arguments.get("uci", "").strip()
                        san = arguments.get("san")
                        logger.info("Extracted from function call: uci='%s', san='%s'", uci, san)
                        
                        if uci:
                            return MoveInterpretation(uci=uci, san_hint=san)
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse tool call arguments as JSON: %s", e)
        
        # Fallback to content if no tool call
        content = message.content
        if content:
            logger.debug("No tool call found, trying fallback content: %s", content)
            match = re.search(r"([a-h][1-8][a-h][1-8][nbrq]?)", content)
            if match:
                logger.info("Extracted from fallback text: uci='%s'", match.group(1))
                return MoveInterpretation(uci=match.group(1))

        logger.warning("Could not extract move from response")
        return None


def get_move_interpreter() -> MoveInterpreter:
    return MoveInterpreter()
