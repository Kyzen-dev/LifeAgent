"""Speech-to-text for Telegram voice messages (OpenAI transcription API)."""

from __future__ import annotations

import httpx

TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"


async def transcribe(audio: bytes, filename: str, api_key: str, model: str, language: str = "fa") -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": model, "language": language},
            files={"file": (filename, audio)},
        )
        response.raise_for_status()
        return response.json().get("text", "").strip()
