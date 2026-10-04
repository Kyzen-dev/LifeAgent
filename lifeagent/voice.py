"""Speech-to-text for Telegram voice messages (OpenAI transcription API)."""

from __future__ import annotations

import httpx

TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"


async def transcribe(audio: bytes, filename: str, api_key: str, model: str, language: str | None = None) -> str:
    """Speech to text; language=None lets the model detect it (Persian and English voice notes)."""
    data = {"model": model}
    if language:
        data["language"] = language
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files={"file": (filename, audio)},
        )
        response.raise_for_status()
        return response.json().get("text", "").strip()
