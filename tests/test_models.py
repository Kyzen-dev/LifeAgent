from claude_agent_sdk import ResultMessage

from lifeagent.agent import AgentReply, ChatAgent
from lifeagent.models import ModelRegistry
from lifeagent.voice import speech_config


def registry(**keys):
    return ModelRegistry.load(keys)


def test_availability_follows_keys():
    assert registry().available() == []
    r = registry(ANTHROPIC_API_KEY="sk-ant", OPENROUTER_API_KEY="or")
    aliases = {s.alias for s in r.available()}
    assert {"sonnet", "opus", "or-gpt", "or-gemini"} <= aliases
    assert "gpt" not in aliases  # the gateway needs LITELLM_MASTER_KEY
    assert "gpt" in {s.alias for s in registry(LITELLM_MASTER_KEY="k").available()}


def test_resolve_and_pick():
    r = registry(OPENROUTER_API_KEY="or")
    assert r.resolve("claude-sonnet-5-5").alias == "sonnet"
    assert r.resolve("OPUS").alias == "opus"
    adhoc = r.resolve("openrouter:qwen/qwen3-coder")
    assert adhoc.provider == "openrouter" and adhoc.model_id == "qwen/qwen3-coder" and not adhoc.thinking
    assert r.resolve("claude-future-9").provider == "anthropic"
    assert r.resolve("nonsense") is None
    # the configured default has no key, so the first available model is used
    assert r.pick(None, "sonnet").provider == "openrouter"


def test_cli_env_for_gateway_and_native():
    r = registry(ANTHROPIC_API_KEY="sk-ant", OPENROUTER_API_KEY="or-key", ZAI_API_KEY="z")
    env = r.cli_env(r.resolve("or-gpt"))
    assert env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "or-key" and env["ANTHROPIC_API_KEY"] == ""
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "openai/gpt-6.1-sol"
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "openai/gpt-6-luna"
    assert env["CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"] == "1"
    native = r.cli_env(r.resolve("sonnet"))
    assert "ANTHROPIC_BASE_URL" not in native and "ANTHROPIC_API_KEY" not in native
    assert r.cli_env(r.resolve("glm"))["API_TIMEOUT_MS"] == "3000000"


def test_gateway_url_override_and_cost():
    r = registry(LITELLM_MASTER_KEY="k", LITELLM_URL="http://127.0.0.1:4000/")
    spec = r.resolve("gpt")
    assert r.cli_env(spec)["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:4000"
    assert r.estimate_cost(spec, {"input_tokens": 1_000_000, "output_tokens": 100_000}) == 2 + 1
    assert r.estimate_cost(r.resolve("openrouter:x/y"), {"input_tokens": 5}) is None


def test_models_file_adds_and_overrides(tmp_path):
    path = tmp_path / "models.toml"
    path.write_text('''
[provider.local]
label = "Ollama via LiteLLM"
key_env = "LOCAL_KEY"
base_url = "http://ollama-gw:4000"

[[model]]
alias = "qwen"
provider = "local"
model_id = "qwen3:14b"
price_in = 0
price_out = 0

[[model]]
alias = "sonnet"
provider = "anthropic"
model_id = "claude-sonnet-5-5"
label = "My Sonnet"
thinking = true
effort = true

[[model]]
alias = "broken"
bogus = 1
''', encoding="utf-8")
    r = ModelRegistry.load({"LOCAL_KEY": "x", "ANTHROPIC_API_KEY": "a"}, path)
    qwen = r.resolve("qwen")
    assert r.is_available(qwen) and r.cli_env(qwen)["ANTHROPIC_BASE_URL"] == "http://ollama-gw:4000"
    assert r.resolve("sonnet").label == "My Sonnet"
    assert r.resolve("broken") is None


def _result(cost, tokens_in, tokens_out, **kw):
    return ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1,
                         session_id="s", total_cost_usd=cost,
                         usage={"input_tokens": tokens_in, "output_tokens": tokens_out}, **kw)


async def test_turn_accounting_uses_deltas(tool_ctx):
    tool_ctx.app.models = registry(ANTHROPIC_API_KEY="a", OPENROUTER_API_KEY="o")
    agent = ChatAgent(tool_ctx.app, 42)
    sonnet = tool_ctx.app.models.resolve("sonnet")
    assert agent._account(sonnet, _result(0.10, 1000, 100)) == (0.10, 1000, 100)
    cost, tin, tout = agent._account(sonnet, _result(0.25, 3000, 300))
    assert round(cost, 6) == 0.15 and (tin, tout) == (2000, 200)

    agent2 = ChatAgent(tool_ctx.app, 43)
    gpt = tool_ctx.app.models.resolve("or-gpt")
    cost, tin, tout = agent2._account(gpt, _result(9.99, 1_000_000, 0))
    assert cost == 2.0 and tin == 1_000_000  # the CLI's cost is ignored for non-Anthropic models


async def test_options_differ_for_native_and_other_models(tool_ctx):
    tool_ctx.app.models = registry(ANTHROPIC_API_KEY="a", OPENROUTER_API_KEY="o")
    agent = ChatAgent(tool_ctx.app, 42)
    native = agent._options(tool_ctx.app.models.resolve("sonnet"), None)
    assert native.thinking == {"type": "adaptive"} and native.effort == tool_ctx.settings.effort
    assert "exa" not in native.mcp_servers and "WebSearch" not in (native.disallowed_tools or [])

    other = agent._options(tool_ctx.app.models.resolve("or-gemini"), "sess")
    assert other.thinking == {"type": "disabled"} and other.effort is None
    assert other.disallowed_tools == ["WebSearch"] and "exa" in other.mcp_servers
    assert "mcp__exa" in other.allowed_tools and other.resume == "sess"
    assert other.env["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"
    assert "WebSearch در این مدل نیست" in other.system_prompt

    haiku = agent._options(tool_ctx.app.models.resolve("haiku"), None)
    assert haiku.thinking is None and haiku.effort is None


async def test_failover_only_when_nothing_ran(tool_ctx):
    tool_ctx.app.models = registry(ANTHROPIC_API_KEY="a", DEEPSEEK_API_KEY="d")
    object.__setattr__(tool_ctx.app.settings, "fallback_model", "deepseek")
    agent = ChatAgent(tool_ctx.app, 42)
    calls, notices = [], []

    async def attempt(spec, prompt, on_tool):
        calls.append(spec.alias)
        agent._turn_tools = []
        if spec.alias == "sonnet":
            return AgentReply(text="x", is_error=True, api_error="billing_error"), None
        return AgentReply(text="جواب از DeepSeek"), None

    async def notice(text):
        notices.append(text)

    agent._attempt = attempt
    reply = await agent.ask("سلام", on_notice=notice)
    assert calls == ["sonnet", "deepseek"] and reply.text == "جواب از DeepSeek"
    assert notices and "اعتبار" in notices[0]
    # during the failover window the fallback answers directly
    calls.clear()
    await agent.ask("دوباره")
    assert calls == ["deepseek"]

    # a turn that already ran tools is never retried on another model
    agent._failover_until = 0
    calls.clear()

    async def attempt_with_tools(spec, prompt, on_tool):
        calls.append(spec.alias)
        agent._turn_tools = ["mcp__life__finance_add_transaction"]
        return AgentReply(text="x", is_error=True, api_error="server_error"), None

    agent._attempt = attempt_with_tools
    reply = await agent.ask("ثبت کن")
    assert calls == ["sonnet"] and reply.api_error == "server_error"


async def test_set_model_reports_whether_context_is_kept(tool_ctx):
    tool_ctx.app.models = registry(ANTHROPIC_API_KEY="a", OPENROUTER_API_KEY="o")
    agent = ChatAgent(tool_ctx.app, 42)
    spec, kept = await agent.set_model("opus")
    assert spec.alias == "opus" and kept
    spec, kept = await agent.set_model("or-gpt")
    assert spec.alias == "or-gpt" and not kept
    assert await tool_ctx.db.get_chat_model(42) == "or-gpt"


def test_speech_provider_choice(tool_ctx):
    s = tool_ctx.settings
    object.__setattr__(s, "groq_api_key", None)
    object.__setattr__(s, "openai_api_key", None)
    assert speech_config(s) is None
    object.__setattr__(s, "openai_api_key", "sk-openai")
    assert speech_config(s).provider == "openai" and speech_config(s).model == "whisper-1"
    object.__setattr__(s, "groq_api_key", "gsk")
    object.__setattr__(s, "transcribe_model", "whisper-1")  # left over in an older .env
    cfg = speech_config(s)
    assert cfg.provider == "groq" and cfg.model == "whisper-large-v3-turbo"
    object.__setattr__(s, "transcribe_provider", "openai")
    assert speech_config(s).provider == "openai"


def test_gateway_models_match_litellm_config():
    import re
    from pathlib import Path

    from lifeagent.models import BUILTIN

    config = (Path(__file__).resolve().parent.parent / "deploy" / "litellm" / "config.yaml").read_text()
    served = set(re.findall(r"^\s*- model_name:\s*(\S+)", config, re.M))
    gateway = {s.model_id for s in BUILTIN if s.provider == "gateway"}
    gateway |= {s.small_model for s in BUILTIN if s.provider == "gateway" and s.small_model}
    assert gateway <= served, gateway - served
