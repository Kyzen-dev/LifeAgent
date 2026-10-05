"""End-to-end: the bundled Claude CLI sends requests where lifeagent.models points it.

A local fake Anthropic Messages server records what arrives. No real API is called.
"""

import asyncio
import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from lifeagent.models import ModelRegistry, ModelSpec


def _cli_available() -> bool:
    try:
        from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    import claude_agent_sdk
    from pathlib import Path

    bundled = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
    return bundled.exists() or shutil.which("claude") is not None


pytestmark = pytest.mark.skipif(not _cli_available(), reason="Claude CLI not available")


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


class FakeMessagesAPI(BaseHTTPRequestHandler):
    requests: list = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"data": []}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}")
        FakeMessagesAPI.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                                         "body": body})
        if "count_tokens" in self.path:
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"input_tokens": 10}')
            return
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        message = {"id": "msg_1", "type": "message", "role": "assistant", "model": body.get("model"), "content": [],
                   "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1000, "output_tokens": 1}}
        for event, data in [
            ("message_start", {"type": "message_start", "message": message}),
            ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "OK"}}),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                               "usage": {"output_tokens": 50}}),
            ("message_stop", {"type": "message_stop"}),
        ]:
            self.wfile.write(_sse(event, data))


@pytest.fixture
def fake_api():
    FakeMessagesAPI.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeMessagesAPI)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


async def test_cli_uses_the_provider_endpoint_and_key(fake_api, tmp_path, monkeypatch):
    # Start from a server-like environment: no Claude Code session or host-managed provider.
    import os

    for name in list(os.environ):
        if name.startswith(("CLAUDE", "CCR_", "ANTHROPIC_")):
            monkeypatch.delenv(name)
    # An Anthropic login present on the host must never reach a third-party endpoint.
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-must-not-leak")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api-must-not-leak")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    registry = ModelRegistry.load({"CUSTOM_LLM_BASE_URL": fake_api, "CUSTOM_LLM_API_KEY": "sk-provider-123"})
    spec = ModelSpec(alias="t", provider="custom", model_id="gpt-6-luna", label="t", max_output=8000)
    options = ClaudeAgentOptions(
        model=spec.model_id, env=registry.cli_env(spec), thinking={"type": "disabled"}, max_turns=1,
        allowed_tools=[], setting_sources=[], cwd=str(tmp_path), disallowed_tools=["WebSearch"],
        system_prompt="test",
    )
    result = None

    async def run():
        nonlocal result
        async for message in query(prompt="Reply with exactly: OK", options=options):
            if isinstance(message, ResultMessage):
                result = message

    await asyncio.wait_for(run(), timeout=120)
    assert result is not None and result.result == "OK"
    calls = [r for r in FakeMessagesAPI.requests if r["path"].startswith("/v1/messages") and "count_tokens" not in r["path"]]
    assert calls, FakeMessagesAPI.requests
    for call in calls:
        assert call["headers"].get("authorization") == "Bearer sk-provider-123"
        assert "x-api-key" not in call["headers"]
        assert "must-not-leak" not in json.dumps(call["headers"])
    main = calls[-1]["body"]
    assert main["model"] == "gpt-6-luna" and main["max_tokens"] == 8000
    assert "thinking" not in main or main["thinking"] in (None, {"type": "disabled"})
    assert "WebSearch" not in [t.get("name") for t in main.get("tools", [])]
