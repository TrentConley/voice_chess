from __future__ import annotations

import io
import logging
from typing import Optional

import requests
from fastapi import HTTPException, UploadFile

from ..core.config import get_settings


logger = logging.getLogger(__name__)


class TranscriptionService:
    def __init__(self, api_key: Optional[str], model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.elevenlabs.io/v1/speech-to-text"

    async def transcribe(self, file: UploadFile) -> str:
        contents = await file.read()
        return await self.transcribe_bytes(contents, file.filename, file.content_type)
    
    async def transcribe_bytes(self, contents: bytes, filename: Optional[str] = None, content_type: Optional[str] = None) -> str:
        if not self.api_key:
            raise HTTPException(status_code=500, detail="ElevenLabs API key is not configured")

        if not contents:
            raise HTTPException(status_code=400, detail="Empty audio payload")

        data = io.BytesIO(contents)
        files = {
            "file": (filename or "audio.webm", data, content_type or "audio/webm"),
        }
        form_data = {
            "model_id": self.model,
            "language_code": "en",  # Force English for better accuracy
        }
        headers = {
            "xi-api-key": self.api_key,
        }
        logger.debug("Sending audio (%d bytes, content-type %s) to ElevenLabs transcription model %s", len(contents), content_type, self.model)

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
    model = settings.elevenlabs_model or "scribe_v1"
    return TranscriptionService(api_key=settings.elevenlabs_api_key, model=model)
