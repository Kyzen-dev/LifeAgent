"""Convert the model's Markdown into Telegram-safe HTML and split long replies."""

from __future__ import annotations

import html
import re

CHUNK_LIMIT = 3500  # Telegram caps messages at 4096 chars; leave room for tags.

_FENCE_RE = re.compile(r"```([\w+-]*)\n(.*?)```", re.S)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_ITALIC_RE = re.compile(r"(?<![*\w])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![*\w])")
_STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*$", re.M)
_BULLET_RE = re.compile(r"^(\s*)[-*]\s+", re.M)
_QUOTE_RE = re.compile(r"^&gt;\s?(.*)$", re.M)
_HR_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$", re.M)


def md_to_html(text: str) -> str:
    stash: list[str] = []

    def keep(fragment: str) -> str:
        stash.append(fragment)
        return f"\x00{len(stash) - 1}\x00"

    def fence(match: re.Match[str]) -> str:
        lang, code = match.group(1), match.group(2).rstrip("\n")
        attr = f' class="language-{lang}"' if lang else ""
        return keep(f"<pre><code{attr}>{html.escape(code)}</code></pre>")

    text = _FENCE_RE.sub(fence, text)
    text = _INLINE_CODE_RE.sub(lambda m: keep(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = _LINK_RE.sub(
        lambda m: keep(f'<a href="{html.escape(m.group(2), quote=True)}">{html.escape(m.group(1))}</a>'),
        text,
    )

    text = html.escape(text, quote=False)
    text = _HR_RE.sub("──────────", text)
    text = _HEADING_RE.sub(r"<b>\1</b>", text)
    text = _BOLD_RE.sub(r"<b>\1</b>", text)
    text = _ITALIC_RE.sub(r"<i>\1</i>", text)
    text = _STRIKE_RE.sub(r"<s>\1</s>", text)
    text = _BULLET_RE.sub(r"\1• ", text)
    text = _QUOTE_RE.sub(r"▎\1", text)

    return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)


def split_markdown(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Split on line boundaries, closing and reopening code fences across chunks."""
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    fence_lang: str | None = None  # None = outside a fence

    def flush() -> None:
        nonlocal current, size
        if current:
            body = "\n".join(current)
            if fence_lang is not None:
                body += "\n```"
            chunks.append(body)
        current = [f"```{fence_lang}"] if fence_lang is not None else []
        size = sum(len(line) + 1 for line in current)

    for line in text.split("\n"):
        while len(line) > limit:  # a single monster line
            flush()
            current.append(line[:limit])
            size += limit
            line = line[limit:]
        if size + len(line) + 1 > limit and current:
            flush()
        current.append(line)
        size += len(line) + 1
        stripped = line.strip()
        if stripped.startswith("```"):
            fence_lang = None if fence_lang is not None else stripped[3:].strip()

    if current and any(line.strip() for line in current):
        chunks.append("\n".join(current))
    return chunks or [""]
