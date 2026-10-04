import json

from lifeagent.tools import web

GEO = {"results": [{"name": "تهران", "country": "ایران", "latitude": 35.69, "longitude": 51.42}]}
FORECAST = {
    "current": {"temperature_2m": 21.3, "apparent_temperature": 20.1, "relative_humidity_2m": 30,
                "weather_code": 2, "wind_speed_10m": 9.4},
    "daily": {"time": ["2026-10-04", "2026-10-05"], "weather_code": [2, 61],
              "temperature_2m_max": [26.0, 22.5], "temperature_2m_min": [14.2, 13.0],
              "precipitation_probability_max": [5, 70], "uv_index_max": [5.1, 3.2]},
}


async def test_weather_and_prices(tool_ctx, monkeypatch):
    calls = []

    async def fake_get_json(url, params):
        calls.append((url, params))
        if "geocoding" in url:
            return GEO
        if "forecast" in url:
            return FORECAST
        if "coingecko" in url:
            return {"bitcoin": {"usd": 61000, "usd_24h_change": -1.2}}
        return {"base": "USD", "rates": {"EUR": 0.91}}

    monkeypatch.setattr(web, "_get_json", fake_get_json)
    t = {x.name: x.handler for x in web.build(tool_ctx)}

    data = json.loads((await t["weather_forecast"]({"days": 2}))["content"][0]["text"])
    assert data["now"]["condition"] == "نیمه‌ابری"
    assert data["daily"][1]["condition"] == "باران ملایم" and data["daily"][1]["rain_chance"] == 70
    assert calls[0][1]["name"] == "Tehran"  # default city from settings

    prices = json.loads((await t["market_prices"]({"crypto": "bitcoin", "fx_symbols": "eur"}))["content"][0]["text"])
    assert prices["crypto_usd"]["bitcoin"]["usd"] == 61000 and prices["fx"]["rates"]["EUR"] == 0.91
    assert calls[-1][1]["to"] == "EUR"


async def test_youtube_rejects_bad_id(tool_ctx):
    t = {x.name: x.handler for x in web.build(tool_ctx)}
    assert (await t["youtube_transcript"]({"url": "not a video"}))["is_error"]


def test_youtube_id_regex():
    for url in ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1", "https://youtu.be/dQw4w9WgXcQ",
                "https://youtube.com/shorts/dQw4w9WgXcQ"):
        assert web._YT_ID_RE.search(url).group(1) == "dQw4w9WgXcQ"
