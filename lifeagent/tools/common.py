"""Helpers shared by the in-process MCP tools."""

from __future__ import annotations

import functools
import json
import logging
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def ok(data: Any) -> dict[str, Any]:
    if isinstance(data, str):
        text = data
    else:
        text = json.dumps(data, ensure_ascii=False, default=str, indent=1)
    return {"content": [{"type": "text", "text": text}]}


def err(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"خطا: {message}"}], "is_error": True}


def safe(fn: Handler) -> Handler:
    """Turn validation errors into tool errors the model can read and fix."""

    @functools.wraps(fn)
    async def wrapper(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return await fn(args)
        except (ValueError, KeyError, TypeError) as exc:
            return err(str(exc))
        except Exception as exc:  # noqa: BLE001 - surface anything to the model
            log.exception("tool %s failed", fn.__name__)
            return err(f"{type(exc).__name__}: {exc}")

    return wrapper


def schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


STR = {"type": "string"}
INT = {"type": "integer"}
NUM = {"type": "number"}
DATE = {
    "type": "string",
    "description": "تاریخ شمسی یا میلادی، مثل 1405/07/12 یا 2026-10-04",
}
