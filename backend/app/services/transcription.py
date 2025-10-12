from __future__ import annotations

import io
import logging
from typing import Optional

import requests
from fastapi import HTTPException, UploadFile

from ..core.config import get_settings


logger = logging.getLogger(__name__)


class TranscriptionService:
    # Chess-specific vocabulary to guide transcription
    CHESS_PROMPT = (
        "Chess move notation: pawn, knight, bishop, rook, queen, king, "
        "castle, castles, check, checkmate, capture, captures, takes, "
        "files a through h, ranks 1 through 8, "
        "e4, d4, Nf3, Nc3, Bc4, O-O, queenside, kingside"
    )
    
    def __init__(self, api_key: Optional[str], model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.openai.com/v1/audio/transcriptions"

    async def transcribe(self, file: UploadFile) -> str:
        contents = await file.read()
        return await self.transcribe_bytes(contents, file.filename, file.content_type)
    
    async def transcribe_bytes(self, contents: bytes, filename: Optional[str] = None, content_type: Optional[str] = None) -> str:
        if not self.api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key is not configured")

        if not contents:
            raise HTTPException(status_code=400, detail="Empty audio payload")

        data = io.BytesIO(contents)
        files = {
            "file": (filename or "audio.webm", data, content_type or "audio/webm"),
        }
        form_data = {
            "model": self.model,
            "response_format": "json",
            "language": "en",  # Force English for better accuracy
            "prompt": self.CHESS_PROMPT,  # Chess-specific vocabulary guidance
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        logger.debug("Sending audio (%d bytes, content-type %s) to transcription model %s with chess prompt", len(contents), content_type, self.model)

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                data=form_data,
                files=files,
                timeout=12,  # 12 second timeout for snappy responses
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            logger.error("Transcription request timed out after 12s")
            raise HTTPException(status_code=504, detail="Transcription timed out. Please try again.") from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response else "unknown"
            body = exc.response.text if exc.response else ""
            logger.error("Transcription API returned %s: %s", status, body)
            raise HTTPException(status_code=502, detail="Transcription service returned an error") from exc
        except requests.RequestException as exc:
            logger.exception("Transcription request failed")
            raise HTTPException(status_code=502, detail="Network error during transcription. Please try again.") from exc

        payload = response.json()
        transcript = payload.get("text") or payload.get("transcript")
        if not transcript:
            raise HTTPException(status_code=502, detail="Transcription service returned no text")
        logger.info("Transcribed: '%s' (%d chars)", transcript, len(transcript))
        return transcript.strip()


def get_transcription_service() -> TranscriptionService:
    settings = get_settings()
    model = settings.openai_transcription_model or "gpt-4o-transcribe"
    return TranscriptionService(api_key=settings.openai_api_key, model=model)
