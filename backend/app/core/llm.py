from typing import Optional

from openai import OpenAI

from .config import get_settings


_openai_client: Optional[OpenAI] = None
_groq_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Get OpenAI client (kept for backward compatibility, but we use Groq now)"""
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def get_groq_client() -> OpenAI:
    """Get Groq client (OpenAI-compatible)"""
    global _groq_client
    if _groq_client is None:
        settings = get_settings()
        _groq_client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )
    return _groq_client
