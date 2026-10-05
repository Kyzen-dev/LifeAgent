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
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / ".env.example"

REQUIRED = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USER_IDS")
TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")

sys.path.insert(0, str(ROOT))
from lifeagent.models import ModelRegistry  # noqa: E402  (standard library only)

# At least one of these must be set: the model providers (see lifeagent/models.py).
PROVIDER_KEYS = ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY",
                 "ZAI_API_KEY", "LITELLM_MASTER_KEY")

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


def check_bearer(url: str, key: str) -> tuple[bool | None, str]:
    """True = accepted, False = rejected (401/403), None = could not tell."""
    status, _ = http_json(url, headers={"Authorization": f"Bearer {key}"})
    if status == 200:
        return True, "key accepted"
    if status in (401, 403):
        return False, f"key rejected (HTTP {status})"
    return None, f"could not verify (HTTP {status}); doctor --live will test it"


def check_openai(key: str) -> tuple[bool | None, str]:
    return check_bearer("https://api.openai.com/v1/models", key)


def check_gemini(key: str) -> tuple[bool | None, str]:
    status, _ = http_json(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
    if status == 200:
        return True, "key accepted"
    return (False if status in (400, 401, 403) else None), f"HTTP {status}"


KEY_CHECKS = {
    "ANTHROPIC_API_KEY": check_anthropic,
    "OPENROUTER_API_KEY": lambda k: check_bearer("https://openrouter.ai/api/v1/key", k),
    "DEEPSEEK_API_KEY": lambda k: check_bearer("https://api.deepseek.com/models", k),
    "MOONSHOT_API_KEY": lambda k: check_bearer("https://api.moonshot.ai/v1/models", k),
    "OPENAI_API_KEY": check_openai,
    "GEMINI_API_KEY": check_gemini,
    "GROQ_API_KEY": lambda k: check_bearer("https://api.groq.com/openai/v1/models", k),
}


def verify_key(name: str, key: str) -> bool:
    """Check a key if we know how; prints the outcome. False only when it was rejected."""
    check = KEY_CHECKS.get(name)
    if check is None:
        warn(f"{name}: not verified here; `python -m lifeagent.doctor --live` tests it")
        return True
    try:
        good, info = check(key)
    except urllib.error.URLError as exc:
        warn(f"{name}: provider not reachable ({exc.reason}); keeping it unchecked")
        return True
    (ok if good else fail if good is False else warn)(f"{name}: {info}")
    return good is not False


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


PROVIDER_MENU = [
    ("ANTHROPIC_API_KEY", "Anthropic — Claude (recommended; console.anthropic.com → API Keys, add credit)", "sk-ant-"),
    ("OPENROUTER_API_KEY", "OpenRouter — one key for Claude, GPT, Gemini, Grok... (openrouter.ai/keys)", "sk-or-"),
    ("DEEPSEEK_API_KEY", "DeepSeek — very cheap, cannot read images (platform.deepseek.com)", "sk-"),
    ("GATEWAY", "OpenAI / Gemini with your own keys (adds a LiteLLM gateway container)", ""),
    ("MOONSHOT_API_KEY", "Moonshot Kimi (platform.moonshot.ai)", ""),
    ("ZAI_API_KEY", "Z.ai GLM (z.ai)", ""),
]


def ask_key(name: str, current: str, prefix: str = "") -> str:
    while True:
        key = ask(f"   {name}", current, secret=True)
        if not key:
            return ""
        if prefix and not key.startswith(prefix):
            fail(f"{name} usually starts with {prefix}")
            if not yes("   Use it anyway?", False):
                continue
        if verify_key(name, key) or not yes("   Enter it again?", True):
            return key


def step_providers(values: dict[str, str]) -> dict[str, str]:
    print(f"\n{BOLD}3) AI model providers{RESET}  (at least one; you can switch models later with /model)")
    updates: dict[str, str] = {}
    while True:
        for i, (key, label, _) in enumerate(PROVIDER_MENU, 1):
            have = values.get(key) or updates.get(key) or (key == "GATEWAY" and (values.get("LITELLM_MASTER_KEY") or updates.get("LITELLM_MASTER_KEY")))
            print(f"   {i}. {label}{'  [set]' if have else ''}")
        choice = input(f"{BOLD}Add which provider? number, or Enter when done{RESET}: ").strip()
        if not choice:
            if any((values.get(k) or updates.get(k)) for k in PROVIDER_KEYS):
                return updates
            fail("Add at least one provider.")
            continue
        if not choice.isdigit() or not 1 <= int(choice) <= len(PROVIDER_MENU):
            continue
        key, label, prefix = PROVIDER_MENU[int(choice) - 1]
        if key == "GATEWAY":
            updates.update(step_gateway(values))
            continue
        entered = ask_key(key, values.get(key, ""), prefix)
        if entered:
            updates[key] = entered


def step_gateway(values: dict[str, str]) -> dict[str, str]:
    print("   OpenAI and Gemini go through a small LiteLLM container (needs ~0.5-1 GB extra RAM).")
    updates: dict[str, str] = {}
    openai = ask_key("OPENAI_API_KEY", values.get("OPENAI_API_KEY", ""), "sk-")
    gemini = ask_key("GEMINI_API_KEY", values.get("GEMINI_API_KEY", ""))
    if openai:
        updates["OPENAI_API_KEY"] = openai
    if gemini:
        updates["GEMINI_API_KEY"] = gemini
    if openai or gemini:
        updates["LITELLM_MASTER_KEY"] = values.get("LITELLM_MASTER_KEY") or "sk-" + secrets.token_urlsafe(24)
        updates["COMPOSE_PROFILES"] = "gateway"  # docker compose starts the gateway too
        ok("gateway enabled (models: gpt, gpt-luna, gemini, gemini-flash)")
    return updates


def step_models(values: dict[str, str]) -> dict[str, str]:
    """Pick the default and fallback models among those the entered keys unlock."""
    registry = ModelRegistry.load(values)
    available = registry.available()
    print(f"\n{BOLD}4) Default model{RESET}")
    for spec in available:
        print(f"   {spec.alias:16} {spec.label} — {spec.note}")
    preferred = [a for a in ("sonnet", "or-sonnet", "deepseek-pro", "gpt", "glm") if registry.resolve(a) in available]
    default = registry.pick(values.get("LIFEAGENT_MODEL"), *preferred)
    while True:
        alias = ask("Default model (alias)", default.alias)
        spec = registry.resolve(alias)
        if spec and registry.is_available(spec):
            break
        fail("Pick one of the aliases listed above.")
    updates = {"LIFEAGENT_MODEL": spec.alias}
    others = [s for s in available if s.provider != spec.provider]
    if others:
        suggestion = values.get("LIFEAGENT_FALLBACK_MODEL") or others[0].alias
        fallback = ask("Fallback model when the default provider fails (Enter = suggested, '-' = none)", suggestion)
        if fallback and fallback != "-" and registry.resolve(fallback):
            updates["LIFEAGENT_FALLBACK_MODEL"] = fallback
        elif fallback == "-":
            updates["LIFEAGENT_FALLBACK_MODEL"] = ""
    return updates


def step_optional(values: dict[str, str]) -> dict[str, str]:
    updates: dict[str, str] = {}
    print(f"\n{BOLD}5) Optional extras{RESET}  (press Enter to skip any of them)")

    print("   Voice messages: a free Groq key (console.groq.com) is enough; OpenAI also works.")
    key = ask("GROQ_API_KEY for voice messages", values.get("GROQ_API_KEY", ""), secret=True)
    if key:
        verify_key("GROQ_API_KEY", key)
        updates["GROQ_API_KEY"] = key
    elif not values.get("OPENAI_API_KEY"):
        key = ask("OPENAI_API_KEY for voice messages", "", secret=True)
        if key:
            verify_key("OPENAI_API_KEY", key)
            updates["OPENAI_API_KEY"] = key

    key = ask("TAVILY_API_KEY for web search with non-Claude models (free at tavily.com)",
              values.get("TAVILY_API_KEY", ""), secret=True)
    if key:
        updates["TAVILY_API_KEY"] = key
    key = ask("BRSAPI_KEY for Iranian dollar/gold prices (free at brsapi.ir)", values.get("BRSAPI_KEY", ""), secret=True)
    if key:
        updates["BRSAPI_KEY"] = key

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


def is_complete(values: dict[str, str]) -> bool:
    return all(values.get(k) for k in REQUIRED) and any(values.get(k) for k in PROVIDER_KEYS)


def check_existing(values: dict[str, str]) -> int:
    missing = [k for k in REQUIRED if not values.get(k)]
    if not any(values.get(k) for k in PROVIDER_KEYS):
        missing.append("a model provider key (" + " / ".join(PROVIDER_KEYS[:3]) + " / ...)")
    if missing:
        fail(f"missing in .env: {', '.join(missing)}")
        return 1
    status = 0
    try:
        good, info = telegram_get_me(values["TELEGRAM_BOT_TOKEN"])
        (ok if good else fail)(f"Telegram: {'@' + info if good else info}")
        status |= not good
        for key in PROVIDER_KEYS + ("OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY"):
            if values.get(key):
                status |= not verify_key(key, values[key])
    except urllib.error.URLError as exc:
        warn(f"network check skipped: {exc.reason}")
    registry = ModelRegistry.load(values)
    if registry.available():
        default = registry.pick(values.get("LIFEAGENT_MODEL"))
        ok(f"default model: {default.alias} ({default.label})")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or verify the LifeAgent .env file")
    parser.add_argument("--check", action="store_true", help="only verify the existing .env")
    parser.add_argument("--complete", action="store_true",
                        help="exit 0 if .env has every required value (no network)")
    args = parser.parse_args()

    source = ENV_PATH if ENV_PATH.exists() else EXAMPLE_PATH
    text = source.read_text(encoding="utf-8")
    values = parse_env(text)

    if args.complete:
        return 0 if ENV_PATH.exists() and is_complete(values) else 1
    if args.check:
        return check_existing(values)

    print(f"{BOLD}LifeAgent setup{RESET} — writes {ENV_PATH}")
    print("Press Enter to keep a value shown in [brackets].")
    try:
        token, username = step_telegram(values)
        updates = {"TELEGRAM_BOT_TOKEN": token}
        updates["TELEGRAM_ALLOWED_USER_IDS"] = step_user_id(values, token, username)
        updates.update(step_providers(values))
        updates.update(step_models({**values, **updates}))
        updates.update(step_optional({**values, **updates}))
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled; nothing was written.")
        return 1

    ENV_PATH.write_text(set_env_values(text, updates), encoding="utf-8")
    os.chmod(ENV_PATH, 0o600)
    print()
    ok(f"saved {ENV_PATH}")
    print("Next: put your profile.md in workspace/memory/ (optional), then start the bot.")
    if updates.get("COMPOSE_PROFILES") == "gateway":
        print("The LiteLLM gateway starts together with the bot (COMPOSE_PROFILES=gateway).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
