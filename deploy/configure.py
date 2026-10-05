#!/usr/bin/env python3
"""Interactive setup wizard: writes .env and verifies every key as it is entered.

Standard library only, so it runs on a fresh server before anything is installed:

    python3 deploy/configure.py           # interactive
    python3 deploy/configure.py --check   # only verify the existing .env

Prompts are in English on purpose: most server terminals render Persian text badly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / ".env.example"

REQUIRED = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USER_IDS", "ANTHROPIC_API_KEY")
TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")

GREEN, YELLOW, RED, BOLD, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}  OK{RESET}  {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}  !!{RESET}  {msg}")


def fail(msg: str) -> None:
    print(f"{RED}  XX{RESET}  {msg}")


# --- HTTP ---------------------------------------------------------------------------


def http_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> tuple[int, dict]:
    """GET url and parse JSON. Network failures raise urllib.error.URLError."""
    request = urllib.request.Request(url, headers={"User-Agent": "lifeagent-configure", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(body)
        except ValueError:
            return exc.code, {"raw": body[:300]}


def telegram_get_me(token: str) -> tuple[bool, str]:
    status, data = http_json(f"https://api.telegram.org/bot{token}/getMe")
    if status == 200 and data.get("ok"):
        return True, data["result"]["username"]
    return False, data.get("description") or f"HTTP {status}"


def telegram_recent_senders(token: str) -> tuple[list[tuple[int, str]], str | None]:
    """Users who recently messaged the bot, newest first; clears those updates afterwards."""
    status, data = http_json(f"https://api.telegram.org/bot{token}/getUpdates?timeout=0")
    if status == 409:
        return [], "the bot is already running somewhere else (stop it, then try again)"
    if status != 200 or not data.get("ok"):
        return [], data.get("description") or f"HTTP {status}"
    senders: dict[int, str] = {}
    last_update = None
    for update in data.get("result", []):
        last_update = update["update_id"]
        message = update.get("message") or update.get("edited_message") or {}
        user = message.get("from")
        if user and not user.get("is_bot"):
            name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
            if user.get("username"):
                name += f" (@{user['username']})"
            senders.pop(user["id"], None)
            senders[user["id"]] = name or str(user["id"])
    if last_update is not None:  # acknowledge so the bot does not replay them later
        http_json(f"https://api.telegram.org/bot{token}/getUpdates?offset={last_update + 1}&timeout=0")
    return list(reversed(senders.items())), None


def check_anthropic(key: str) -> tuple[bool, str]:
    status, data = http_json(
        "https://api.anthropic.com/v1/models?limit=1",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    if status == 200:
        return True, "key accepted"
    message = (data.get("error") or {}).get("message") or data.get("raw") or ""
    return False, f"HTTP {status} {message}".strip()


def check_openai(key: str) -> tuple[bool, str]:
    status, data = http_json("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
    return status == 200, "key accepted" if status == 200 else f"HTTP {status}"


def check_github(token: str) -> tuple[bool, str]:
    status, data = http_json("https://api.github.com/user", headers={"Authorization": f"Bearer {token}"})
    return status == 200, f"logged in as {data.get('login')}" if status == 200 else f"HTTP {status}"


# --- .env file ------------------------------------------------------------------------


def parse_env(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def set_env_values(text: str, updates: dict[str, str]) -> str:
    """Replace KEY=... lines in place (keeping comments and order); append unknown keys."""
    lines = text.splitlines()
    seen = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            lines[i] = f"{key}={updates[key]}"
            seen.add(key)
    lines += [f"{key}={value}" for key, value in updates.items() if key not in seen]
    return "\n".join(lines) + "\n"


def mask(value: str) -> str:
    return value[:6] + "…" + value[-4:] if len(value) > 12 else "(set)"


# --- interactive steps ------------------------------------------------------------------


def ask(prompt: str, current: str = "", secret: bool = False) -> str:
    shown = f" [{mask(current) if secret else current}]" if current else ""
    answer = input(f"{BOLD}{prompt}{RESET}{shown}: ").strip()
    return answer or current


def yes(prompt: str, default: bool) -> bool:
    answer = input(f"{BOLD}{prompt}{RESET} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not answer else answer.startswith("y")


def step_telegram(values: dict[str, str]) -> tuple[str, str]:
    print(f"\n{BOLD}1) Telegram bot token{RESET}  (from @BotFather → /newbot)")
    while True:
        token = ask("Bot token", values.get("TELEGRAM_BOT_TOKEN", ""), secret=True)
        if not TOKEN_RE.match(token):
            fail("That does not look like a bot token (format 123456789:ABC...). Copy it again from BotFather.")
            continue
        try:
            good, info = telegram_get_me(token)
        except urllib.error.URLError as exc:
            warn(f"Could not reach Telegram ({exc.reason}); keeping the token unchecked.")
            return token, ""
        if good:
            ok(f"bot @{info}")
            return token, info
        fail(f"Telegram rejected the token: {info}")


def step_user_id(values: dict[str, str], token: str, username: str) -> str:
    print(f"\n{BOLD}2) Your Telegram user id{RESET}  (only these users can talk to the bot)")
    current = values.get("TELEGRAM_ALLOWED_USER_IDS", "")
    if username and yes(f"Detect it automatically? Send any message to @{username} in Telegram first", True):
        input("   Press Enter after you have sent the message... ")
        try:
            senders, error = telegram_recent_senders(token)
        except urllib.error.URLError as exc:
            senders, error = [], str(exc.reason)
        if error:
            warn(error)
        for user_id, name in senders:
            if yes(f"   Use {name} — id {user_id}?", True):
                ok(f"user id {user_id}")
                return str(user_id)
        if not senders and not error:
            warn("No message found. Make sure you messaged the right bot.")
    while True:
        user_ids = ask("User id(s), comma separated (get it from @userinfobot)", current)
        if re.fullmatch(r"\d+(,\d+)*", user_ids.replace(" ", "")):
            return user_ids.replace(" ", "")
        fail("Only digits and commas, e.g. 123456789")


def step_anthropic(values: dict[str, str]) -> str:
    print(f"\n{BOLD}3) Anthropic API key{RESET}  (console.anthropic.com → API Keys; add credit under Billing)")
    while True:
        key = ask("API key", values.get("ANTHROPIC_API_KEY", ""), secret=True)
        if not key.startswith("sk-ant-"):
            fail("Anthropic keys start with sk-ant-")
            continue
        try:
            good, info = check_anthropic(key)
        except urllib.error.URLError as exc:
            warn(f"Could not reach api.anthropic.com ({exc.reason}); keeping the key unchecked.")
            return key
        if good:
            ok(info)
            return key
        fail(info)
        if not yes("Enter it again?", True):
            return key


def step_optional(values: dict[str, str]) -> dict[str, str]:
    updates: dict[str, str] = {}
    print(f"\n{BOLD}4) Optional extras{RESET}  (press Enter to skip any of them)")

    key = ask("OpenAI API key for voice messages", values.get("OPENAI_API_KEY", ""), secret=True)
    if key:
        try:
            good, info = check_openai(key)
            (ok if good else warn)(f"OpenAI: {info}")
        except urllib.error.URLError as exc:
            warn(f"OpenAI not reachable: {exc.reason}")
        updates["OPENAI_API_KEY"] = key

    token = ask("GitHub fine-grained token", values.get("GITHUB_PERSONAL_ACCESS_TOKEN", ""), secret=True)
    if token:
        try:
            good, info = check_github(token)
            (ok if good else warn)(f"GitHub: {info}")
        except urllib.error.URLError as exc:
            warn(f"GitHub not reachable: {exc.reason}")
        updates["GITHUB_PERSONAL_ACCESS_TOKEN"] = token

    prayer_default = values.get("PRAYER_REMINDERS", "false").lower() == "true"
    updates["PRAYER_REMINDERS"] = "true" if yes("Prayer-time reminders (azan)?", prayer_default) else "false"
    city = ask("City (English name, for weather and prayer times)", values.get("LIFEAGENT_CITY", "Tehran"))
    updates["LIFEAGENT_CITY"] = city
    updates["PRAYER_CITY"] = city
    return updates


# --- check-only mode ----------------------------------------------------------------------


def check_existing(values: dict[str, str]) -> int:
    missing = [k for k in REQUIRED if not values.get(k)]
    if missing:
        fail(f"missing in .env: {', '.join(missing)}")
        return 1
    status = 0
    try:
        good, info = telegram_get_me(values["TELEGRAM_BOT_TOKEN"])
        (ok if good else fail)(f"Telegram: {'@' + info if good else info}")
        status |= not good
        good, info = check_anthropic(values["ANTHROPIC_API_KEY"])
        (ok if good else fail)(f"Anthropic: {info}")
        status |= not good
    except urllib.error.URLError as exc:
        warn(f"network check skipped: {exc.reason}")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or verify the LifeAgent .env file")
    parser.add_argument("--check", action="store_true", help="only verify the existing .env")
    args = parser.parse_args()

    source = ENV_PATH if ENV_PATH.exists() else EXAMPLE_PATH
    text = source.read_text(encoding="utf-8")
    values = parse_env(text)

    if args.check:
        return check_existing(values)

    print(f"{BOLD}LifeAgent setup{RESET} — writes {ENV_PATH}")
    print("Press Enter to keep a value shown in [brackets].")
    try:
        token, username = step_telegram(values)
        updates = {"TELEGRAM_BOT_TOKEN": token}
        updates["TELEGRAM_ALLOWED_USER_IDS"] = step_user_id(values, token, username)
        updates["ANTHROPIC_API_KEY"] = step_anthropic(values)
        updates.update(step_optional(values))
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled; nothing was written.")
        return 1

    ENV_PATH.write_text(set_env_values(text, updates), encoding="utf-8")
    os.chmod(ENV_PATH, 0o600)
    print()
    ok(f"saved {ENV_PATH}")
    print("Next: put your profile.md in workspace/memory/ (optional), then start the bot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
