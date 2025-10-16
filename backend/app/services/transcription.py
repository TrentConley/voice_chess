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
        self.endpoint = "https://api.groq.com/openai/v1/audio/transcriptions"

    async def transcribe(self, file: UploadFile) -> str:
        contents = await file.read()
        return await self.transcribe_bytes(contents, file.filename, file.content_type)
    
    async def transcribe_bytes(self, contents: bytes, filename: Optional[str] = None, content_type: Optional[str] = None) -> str:
        if not self.api_key:
            raise HTTPException(status_code=500, detail="Groq API key is not configured")

        if not contents:
            raise HTTPException(status_code=400, detail="Empty audio payload")

        # Groq API expects the file as multipart/form-data
        # Use generic audio filename since format detection is automatic
        data = io.BytesIO(contents)
        
        # Determine file extension from content type or filename
        file_ext = "webm"
        if content_type:
            if "mp3" in content_type:
                file_ext = "mp3"
            elif "mp4" in content_type or "m4a" in content_type:
                file_ext = "m4a"
            elif "wav" in content_type:
                file_ext = "wav"
            elif "ogg" in content_type:
                file_ext = "ogg"
        
        files = {
            "file": (f"audio.{file_ext}", data, content_type or "audio/webm"),
        }
        form_data = {
            "model": self.model,
            "response_format": "json",
            "language": "en",
            "prompt": self.CHESS_PROMPT,
            "temperature": 0.0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        logger.debug("Sending audio (%d bytes, type=%s, ext=%s) to Groq model %s", len(contents), content_type, file_ext, self.model)

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
            detail_msg = f"Transcription failed: {body[:200]}" if body else "Transcription service error"
            raise HTTPException(status_code=502, detail=detail_msg) from exc
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
    model = settings.groq_transcription_model or "whisper-large-v3"
    return TranscriptionService(api_key=settings.groq_api_key, model=model)
