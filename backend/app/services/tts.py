from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import HTTPException

from ..core.llm import get_openai_client


logger = logging.getLogger(__name__)


def format_move_for_speech(san: str) -> str:
    """
    Convert chess notation to natural speech.
    Examples:
        Nf3 -> Knight f three
        Bxc5 -> Bishop takes c five
        O-O -> Castle kingside
        e4 -> e four
        Qh5+ -> Queen h five check
        Nf3# -> Knight f three checkmate
    """
    if san in ["O-O", "0-0"]:
        return "Castle kingside"
    if san in ["O-O-O", "0-0-0"]:
        return "Castle queenside"
    
    text = san
    
    # Handle checkmate and check symbols
    if text.endswith("#"):
        text = text[:-1] + " checkmate"
    elif text.endswith("+"):
        text = text[:-1] + " check"
    
    # Replace piece notation
    piece_map = {
        "K": "King ",
        "Q": "Queen ",
        "R": "Rook ",
        "B": "Bishop ",
        "N": "Knight ",
    }
    for piece, name in piece_map.items():
        if text.startswith(piece):
            text = name + text[1:]
            break
    
    # Replace 'x' with 'takes'
    text = text.replace("x", " takes ")
    
    # Add spaces between letters and numbers for better pronunciation
    # e.g., "f3" -> "f 3", "c5" -> "c 5"
    text = re.sub(r"([a-h])(\d)", r"\1 \2", text)
    
    # Clean up extra spaces
    text = " ".join(text.split())
    
    return text


class TTSService:
    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key
        self.client = get_openai_client() if api_key else None
    
    def generate_speech(self, text: str) -> bytes:
        """Generate speech audio from text using OpenAI TTS."""
        if not self.client:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        # Format chess moves for better pronunciation
        formatted_text = format_move_for_speech(text)
        logger.debug("TTS input: '%s' -> '%s'", text, formatted_text)
        
        try:
            response = self.client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice="coral",
                input=formatted_text,
                response_format="mp3",
            )
            
            # Return the audio bytes
            return response.content
        except Exception as exc:
            logger.exception("TTS generation failed")
            raise HTTPException(status_code=502, detail="TTS generation failed") from exc


_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    global _service
    if _service is None:
        from ..core.config import get_settings
        settings = get_settings()
        _service = TTSService(api_key=settings.openai_api_key)
    return _service
