"""Speech-to-text for Telegram voice messages (any OpenAI-compatible transcription API).

Groq hosts Whisper with a free tier; OpenAI is the paid alternative. Both accept the
same multipart request, so only the URL, key and model differ.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from .config import Settings

ENDPOINTS = {
    "groq": ("https://api.groq.com/openai/v1/audio/transcriptions", "whisper-large-v3-turbo"),
    "openai": ("https://api.openai.com/v1/audio/transcriptions", "whisper-1"),
}


@dataclass(frozen=True)
class SpeechConfig:
    provider: str
    url: str
    api_key: str
    model: str


def speech_config(settings: Settings) -> SpeechConfig | None:
    """The transcription service to use, or None when no key is configured.

    TRANSCRIBE_PROVIDER=auto prefers Groq (free) and falls back to OpenAI.
    """
    keys = {"groq": settings.groq_api_key, "openai": settings.openai_api_key}
    wanted = settings.transcribe_provider
    order = [wanted] if wanted in ENDPOINTS else ["groq", "openai"]
    for provider in order:
        if keys.get(provider):
            url, default_model = ENDPOINTS[provider]
            model = settings.transcribe_model or default_model
            if provider == "groq" and model == "whisper-1":  # OpenAI-only name left in an older .env
                model = default_model
            return SpeechConfig(provider, url, keys[provider], model)
    return None


async def transcribe(audio: bytes, filename: str, config: SpeechConfig, language: str | None = None) -> str:
    """Speech to text; language=None lets the model detect it (Persian and English voice notes)."""
    data = {"model": config.model}
    if language:
        data["language"] = language
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            config.url,
            headers={"Authorization": f"Bearer {config.api_key}"},
            data=data,
            files={"file": (filename, audio)},
        )
        response.raise_for_status()
        return response.json().get("text", "").strip()
