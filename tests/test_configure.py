import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "configure", Path(__file__).resolve().parent.parent / "deploy" / "configure.py"
)
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


def test_env_round_trip_keeps_comments_and_order():
    text = "# comment\nTELEGRAM_BOT_TOKEN=\nLIFEAGENT_MODEL=claude-sonnet-5-5\n\n# tail\n"
    out = configure.set_env_values(text, {"TELEGRAM_BOT_TOKEN": "1:abc", "NEW_KEY": "x"})
    assert out.splitlines()[:3] == ["# comment", "TELEGRAM_BOT_TOKEN=1:abc", "LIFEAGENT_MODEL=claude-sonnet-5-5"]
    assert out.rstrip().endswith("NEW_KEY=x") and "# tail" in out
    assert configure.parse_env(out)["TELEGRAM_BOT_TOKEN"] == "1:abc"


def test_example_env_has_required_keys():
    example = configure.parse_env(configure.EXAMPLE_PATH.read_text(encoding="utf-8"))
    for key in configure.REQUIRED:
        assert key in example


def test_recent_senders_newest_first_and_acknowledged(monkeypatch):
    calls = []

    def fake_http(url, headers=None, timeout=20):
        calls.append(url)
        if "offset=" in url:
            return 200, {"ok": True, "result": []}
        return 200, {"ok": True, "result": [
            {"update_id": 10, "message": {"from": {"id": 111, "first_name": "Ali", "is_bot": False}}},
            {"update_id": 11, "message": {"from": {"id": 222, "first_name": "Me", "username": "me", "is_bot": False}}},
            {"update_id": 12, "message": {"from": {"id": 999, "first_name": "Bot", "is_bot": True}}},
        ]}

    monkeypatch.setattr(configure, "http_json", fake_http)
    senders, error = configure.telegram_recent_senders("1:abc")
    assert error is None
    assert senders == [(222, "Me (@me)"), (111, "Ali")]
    assert calls[-1].endswith("offset=13&timeout=0")


def test_recent_senders_conflict(monkeypatch):
    monkeypatch.setattr(configure, "http_json", lambda *a, **k: (409, {"ok": False}))
    senders, error = configure.telegram_recent_senders("1:abc")
    assert senders == [] and "already running" in error


def test_check_existing(monkeypatch, capsys):
    assert configure.check_existing({"TELEGRAM_BOT_TOKEN": "x"}) == 1

    def fake_http(url, headers=None, timeout=20):
        if "telegram" in url:
            return 200, {"ok": True, "result": {"username": "my_bot"}}
        return 401, {"error": {"message": "invalid x-api-key"}}

    monkeypatch.setattr(configure, "http_json", fake_http)
    values = {"TELEGRAM_BOT_TOKEN": "1:a", "TELEGRAM_ALLOWED_USER_IDS": "1", "ANTHROPIC_API_KEY": "sk-ant-x"}
    assert configure.check_existing(values) == 1
    out = capsys.readouterr().out
    assert "@my_bot" in out and "invalid x-api-key" in out


def test_token_format():
    assert configure.TOKEN_RE.match("123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw1")
    assert not configure.TOKEN_RE.match("123:short")


def test_complete_needs_a_provider_key():
    base = {"TELEGRAM_BOT_TOKEN": "1:a", "TELEGRAM_ALLOWED_USER_IDS": "1"}
    assert not configure.is_complete(base)
    assert configure.is_complete({**base, "OPENROUTER_API_KEY": "sk-or-x"})
    assert configure.is_complete({**base, "LITELLM_MASTER_KEY": "sk-x"})


def test_verify_key_tolerates_unknown_status(monkeypatch, capsys):
    monkeypatch.setattr(configure, "http_json", lambda *a, **k: (404, {}))
    assert configure.verify_key("OPENROUTER_API_KEY", "sk-or-x") is True
    monkeypatch.setattr(configure, "http_json", lambda *a, **k: (401, {}))
    assert configure.verify_key("DEEPSEEK_API_KEY", "sk-x") is False
    assert configure.verify_key("ZAI_API_KEY", "x") is True
    assert "not verified" in capsys.readouterr().out


def test_model_step_suggests_cross_provider_fallback(monkeypatch):
    answers = iter(["", ""])  # accept the suggested default and fallback
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    out = configure.step_models({"ANTHROPIC_API_KEY": "a", "DEEPSEEK_API_KEY": "d"})
    assert out["LIFEAGENT_MODEL"] == "sonnet" and out["LIFEAGENT_FALLBACK_MODEL"] == "deepseek"
