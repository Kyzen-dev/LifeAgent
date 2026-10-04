"""Live data from free public APIs: weather, market prices, YouTube transcripts."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
from claude_agent_sdk import tool

from ..context import ToolContext
from .common import INT, STR, err, ok, safe, schema

TIMEOUT = httpx.Timeout(20.0)

# WMO weather interpretation codes → Persian
WEATHER_CODES = {
    0: "صاف", 1: "تقریباً صاف", 2: "نیمه‌ابری", 3: "ابری", 45: "مه", 48: "مه یخ‌زده",
    51: "نم‌نم باران", 53: "نم‌نم باران", 55: "نم‌نم باران شدید", 61: "باران ملایم", 63: "باران",
    65: "باران شدید", 66: "باران یخ‌زن", 67: "باران یخ‌زن شدید", 71: "برف ملایم", 73: "برف",
    75: "برف شدید", 77: "دانه برف", 80: "رگبار ملایم", 81: "رگبار", 82: "رگبار شدید",
    85: "بارش برف", 86: "بارش برف شدید", 95: "رعدوبرق", 96: "رعدوبرق با تگرگ", 99: "رعدوبرق با تگرگ شدید",
}

_YT_ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})")


async def _get_json(url: str, params: dict[str, Any]) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def build(ctx: ToolContext) -> list:
    @tool(
        "weather_forecast",
        "وضعیت فعلی و پیش‌بینی آب‌وهوا (Open-Meteo). بدون city = شهر پیش‌فرض کاربر.",
        schema({"city": {"type": "string", "description": "نام شهر به فارسی یا انگلیسی"},
                "days": {**INT, "minimum": 1, "maximum": 7}}),
    )
    @safe
    async def weather_forecast(args: dict[str, Any]) -> dict[str, Any]:
        city = args.get("city") or ctx.settings.city
        places = await _get_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": city, "count": 1, "language": "fa"},
        )
        if not places.get("results"):
            return err(f"شهر «{city}» پیدا نشد")
        place = places["results"][0]
        data = await _get_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max",
                "timezone": str(ctx.settings.tz),
                "forecast_days": int(args.get("days") or 3),
            },
        )
        current = data["current"]
        daily = data["daily"]
        return ok(
            {
                "place": f"{place.get('name')}, {place.get('country', '')}",
                "now": {
                    "temp_c": current["temperature_2m"],
                    "feels_like_c": current["apparent_temperature"],
                    "humidity": current["relative_humidity_2m"],
                    "wind_kmh": current["wind_speed_10m"],
                    "condition": WEATHER_CODES.get(current["weather_code"], str(current["weather_code"])),
                },
                "daily": [
                    {
                        "date": day,
                        "condition": WEATHER_CODES.get(code, str(code)),
                        "min_c": tmin,
                        "max_c": tmax,
                        "rain_chance": rain,
                        "uv_max": uv,
                    }
                    for day, code, tmin, tmax, rain, uv in zip(
                        daily["time"], daily["weather_code"], daily["temperature_2m_min"],
                        daily["temperature_2m_max"], daily["precipitation_probability_max"],
                        daily["uv_index_max"],
                        strict=True,
                    )
                ],
            }
        )

    @tool(
        "market_prices",
        "قیمت لحظه‌ای رمزارزها (CoinGecko) به دلار و نرخ رسمی ارزهای جهانی (ECB). "
        "نرخ دلار/طلا/سکه بازار آزاد ایران را ندارد؛ برای آن از WebSearch استفاده کن.",
        schema(
            {
                "crypto": {"type": "string", "description": "شناسه‌های CoinGecko با کاما، مثل bitcoin,ethereum,tether,the-open-network"},
                "fx_base": {"type": "string", "description": "ارز مبنا برای نرخ‌های جهانی، مثل USD"},
                "fx_symbols": {"type": "string", "description": "ارزهای مقصد با کاما، مثل EUR,GBP,TRY,AED"},
            }
        ),
    )
    @safe
    async def market_prices(args: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        crypto = (args.get("crypto") or "").replace(" ", "")
        if not crypto and not args.get("fx_symbols"):
            crypto = "bitcoin,ethereum,tether"
        if crypto:
            result["crypto_usd"] = await _get_json(
                "https://api.coingecko.com/api/v3/simple/price",
                {"ids": crypto, "vs_currencies": "usd", "include_24hr_change": "true",
                 "include_last_updated_at": "true"},
            )
        if args.get("fx_symbols"):
            result["fx"] = await _get_json(
                "https://api.frankfurter.app/latest",
                {"from": (args.get("fx_base") or "USD").upper(), "to": args["fx_symbols"].replace(" ", "").upper()},
            )
        return ok(result)

    @tool(
        "youtube_transcript",
        "متن (زیرنویس) یک ویدیوی YouTube برای خلاصه‌کردن یا یادگیری. ممکن است برای برخی ویدیوها "
        "یا از IP سرور در دسترس نباشد.",
        schema({"url": {"type": "string", "description": "لینک یا شناسه ویدیو"},
                "languages": {**STR, "description": "ترتیب زبان‌های ترجیحی با کاما؛ پیش‌فرض fa,en"}},
               ["url"]),
    )
    @safe
    async def youtube_transcript(args: dict[str, Any]) -> dict[str, Any]:
        from youtube_transcript_api import YouTubeTranscriptApi

        raw = args["url"].strip()
        match = _YT_ID_RE.search(raw)
        video_id = match.group(1) if match else raw
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError("شناسه ویدیو نامعتبر است")
        languages = [x.strip() for x in (args.get("languages") or "fa,en").split(",") if x.strip()]

        def fetch() -> tuple[str, str]:
            api = YouTubeTranscriptApi()
            try:
                fetched = api.fetch(video_id, languages=languages)
            except Exception:  # noqa: BLE001 - fall back to any available language
                transcript = next(iter(api.list(video_id)))
                fetched = transcript.fetch()
            text = " ".join(s.text.replace("\n", " ") for s in fetched.snippets)
            return fetched.language_code, text

        try:
            language, text = await asyncio.to_thread(fetch)
        except Exception as exc:  # noqa: BLE001
            return err(f"دریافت زیرنویس ممکن نشد ({type(exc).__name__}). از کاربر بخواه متن یا فایل را بفرستد.")
        limit = 120_000
        return ok({"video_id": video_id, "language": language, "truncated": len(text) > limit,
                   "chars": len(text), "text": text[:limit]})

    return [weather_forecast, market_prices, youtube_transcript]
