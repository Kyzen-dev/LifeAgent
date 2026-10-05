"""Model catalog: which LLM answers, and how the Claude CLI reaches it.

The agent runtime is always the Claude Agent SDK (skills, MCP, subagents, approvals);
only the model behind it changes. Anthropic models are called directly. Other models
are reached through an Anthropic-compatible endpoint, which the CLI is pointed at with
ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN in the CLI's environment:

* OpenRouter and DeepSeek speak the Anthropic Messages API themselves;
* OpenAI, Gemini, local Ollama models (and anything else LiteLLM supports) go through
  the optional LiteLLM gateway container (docker compose --profile gateway), which
  translates the Messages API — see deploy/litellm/config.yaml.

A provider is available when its key is set in .env. Extra models (or overrides of
the built-in ones) can be listed in data/models.toml:

    [[model]]
    alias = "qwen"
    provider = "openrouter"
    model_id = "qwen/qwen3-coder"
    label = "Qwen3 Coder"
    price_in = 0.2      # USD per 1M input tokens (for /cost on non-Anthropic models)
    price_out = 0.8
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping

try:  # Python 3.11+; deploy/configure.py may run on an older system python
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    key_env: str  # the .env variable holding this provider's key
    base_url: str | None = None  # None = api.anthropic.com
    base_url_env: str | None = None  # lets .env override base_url
    native: bool = False  # Anthropic itself: thinking/effort, server web search, exact cost
    extra_env: tuple[tuple[str, str], ...] = ()  # provider-recommended CLI settings


PROVIDERS: dict[str, Provider] = {
    p.name: p
    for p in [
        Provider("anthropic", "Anthropic", "ANTHROPIC_API_KEY", native=True),
        Provider("openrouter", "OpenRouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api"),
        Provider("deepseek", "DeepSeek", "DEEPSEEK_API_KEY", "https://api.deepseek.com/anthropic"),
        Provider("moonshot", "Moonshot (Kimi)", "MOONSHOT_API_KEY", "https://api.moonshot.ai/anthropic"),
        Provider("zai", "Z.ai (GLM)", "ZAI_API_KEY", "https://api.z.ai/api/anthropic",
                 extra_env=(("API_TIMEOUT_MS", "3000000"),)),
        Provider("gateway", "LiteLLM gateway", "LITELLM_MASTER_KEY", "http://litellm:4000", "LITELLM_URL"),
        Provider("custom", "Custom endpoint", "CUSTOM_LLM_API_KEY", None, "CUSTOM_LLM_BASE_URL"),
    ]
}


@dataclass(frozen=True)
class ModelSpec:
    alias: str  # short name for /model and LIFEAGENT_MODEL
    provider: str
    model_id: str  # the id the provider expects
    label: str
    note: str = ""  # one Persian line shown in /model
    price_in: float | None = None  # USD per 1M tokens; Anthropic cost comes from the CLI
    price_out: float | None = None
    small_model: str | None = None  # same-provider model for background work (WebFetch, titles)
    max_output: int | None = None  # caps CLAUDE_CODE_MAX_OUTPUT_TOKENS for smaller models
    context: int | None = None  # context window, so the CLI compacts in time
    thinking: bool = False  # send adaptive thinking (Anthropic models that support it)
    effort: bool = False  # send the effort level
    vision: bool = True
    # Anthropic request features the CLI may use with a non-Anthropic model (its
    # *_SUPPORTED_CAPABILITIES): effort, thinking, adaptive_thinking, interleaved_thinking,
    # mid_conversation_system, temperature. Empty = plain Messages API only.
    capabilities: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model_id}"


def _m(alias: str, provider: str, model_id: str, label: str, note: str = "", **kw: Any) -> ModelSpec:
    return ModelSpec(alias=alias, provider=provider, model_id=model_id, label=label, note=note, **kw)


# Built-in catalog. Prices are USD per 1M tokens (input, output) as published in
# October 2026; check them now and then — /cost on non-Anthropic models relies on them.
# Anthropic does not support Claude Code on non-Claude models, so those are marked
# experimental: tool use works through the endpoints below, but quality varies.
X = " (آزمایشی)"
BUILTIN: list[ModelSpec] = [
    # Anthropic, direct: thinking and effort supported; the CLI reports exact cost.
    _m("sonnet", "anthropic", "claude-sonnet-5-5", "Claude Sonnet 5.5", "متعادل و اقتصادی — پیش‌فرض",
       price_in=2, price_out=10, thinking=True, effort=True),
    _m("opus", "anthropic", "claude-opus-5-5", "Claude Opus 5.5", "قوی‌تر برای کارهای سخت و طولانی",
       price_in=4, price_out=20, thinking=True, effort=True),
    _m("fable", "anthropic", "claude-fable-5-1", "Claude Fable 5.1", "قوی‌ترین مدل Anthropic؛ گران",
       price_in=10, price_out=50, thinking=True, effort=True),
    _m("haiku", "anthropic", "claude-haiku-4-5", "Claude Haiku 4.5", "سریع و ارزان برای کارهای ساده",
       price_in=1, price_out=5),
    # OpenRouter: one key, many vendors. Claude through OpenRouter is the combination
    # OpenRouter itself guarantees; the others are best effort.
    _m("or-sonnet", "openrouter", "anthropic/claude-sonnet-5.5", "Claude Sonnet 5.5 · OpenRouter",
       "همان Claude با پرداخت از OpenRouter", price_in=2, price_out=10),
    _m("or-gpt", "openrouter", "openai/gpt-6.1-sol", "GPT-6.1 Sol · OpenRouter" + X, "مدل اصلی OpenAI",
       price_in=2, price_out=10, small_model="openai/gpt-6-luna"),
    _m("or-gemini", "openrouter", "google/gemini-3.1-pro-preview", "Gemini 3.1 Pro · OpenRouter" + X,
       "مدل قوی Google", price_in=2, price_out=12, small_model="google/gemini-3.8-flash"),
    _m("or-gemini-flash", "openrouter", "google/gemini-3.8-flash", "Gemini 3.8 Flash · OpenRouter" + X,
       "سریع و ارزان Google", price_in=0.75, price_out=3.75),
    _m("or-grok", "openrouter", "x-ai/grok-4.7", "Grok 4.7 · OpenRouter" + X, "مدل xAI",
       price_in=2, price_out=6, small_model="x-ai/grok-4.3"),
    # Providers with their own Anthropic-compatible endpoint (no gateway needed).
    _m("deepseek", "deepseek", "deepseek-v4-flash", "DeepSeek V4 Flash" + X, "بسیار ارزان؛ عکس نمی‌بیند",
       price_in=0.3, price_out=1.2, vision=False),
    _m("deepseek-pro", "deepseek", "deepseek-v4-pro", "DeepSeek V4 Pro" + X, "ارزان و قوی؛ عکس نمی‌بیند",
       price_in=1.32, price_out=3.96, small_model="deepseek-v4-flash", vision=False),
    _m("kimi", "moonshot", "kimi-k3", "Kimi K3" + X, "مدل Moonshot",
       price_in=3, price_out=15, small_model="kimi-k2.7-code"),
    _m("glm", "zai", "glm-5.3", "GLM 5.3" + X, "مدل Z.ai؛ ارزان",
       price_in=1.4, price_out=4.4, small_model="glm-5.3-flash"),
    # OpenAI and Gemini with your own keys, through the LiteLLM gateway
    # (ids = model_name entries in deploy/litellm/config.yaml).
    _m("gpt", "gateway", "gpt-6.1-sol", "GPT-6.1 Sol" + X, "OpenAI با کلید خودت (gateway)",
       price_in=2, price_out=10, small_model="gpt-6-luna"),
    _m("gpt-luna", "gateway", "gpt-6-luna", "GPT-6 Luna" + X, "OpenAI بسیار ارزان (gateway)",
       price_in=0.1, price_out=0.5),
    _m("gemini", "gateway", "gemini-3.1-pro-preview", "Gemini 3.1 Pro" + X, "Google با کلید خودت (gateway)",
       price_in=2, price_out=12, small_model="gemini-3.8-flash"),
    _m("gemini-flash", "gateway", "gemini-3.8-flash", "Gemini 3.8 Flash" + X, "Google سریع و ارزان (gateway)",
       price_in=0.75, price_out=3.75),
]

_SPEC_FIELDS = {f.name for f in fields(ModelSpec)}


@dataclass
class ModelRegistry:
    env: Mapping[str, str]
    specs: list[ModelSpec] = field(default_factory=lambda: list(BUILTIN))
    providers: dict[str, Provider] = field(default_factory=lambda: dict(PROVIDERS))

    @classmethod
    def load(cls, env: Mapping[str, str], extra_file: Path | None = None) -> "ModelRegistry":
        registry = cls(env=dict(env))
        if extra_file and extra_file.is_file():
            registry.merge_file(extra_file)
        return registry

    def merge_file(self, path: Path) -> None:
        """Add or override models (and custom providers) from a TOML file."""
        if tomllib is None:
            log.error("ignoring %s: reading TOML needs Python 3.11+", path)
            return
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            log.error("ignoring %s: %s", path, exc)
            return
        for name, conf in (data.get("provider") or {}).items():
            base = self.providers.get(name)
            values = {"name": name, "label": conf.get("label", name), "key_env": conf.get("key_env", ""),
                      "base_url": conf.get("base_url"), "base_url_env": conf.get("base_url_env")}
            if base:
                values = {**base.__dict__, **{k: v for k, v in values.items() if v}}
            self.providers[name] = Provider(**values)
        for entry in data.get("model") or []:
            unknown = set(entry) - _SPEC_FIELDS
            if unknown or not {"alias", "provider", "model_id"} <= set(entry):
                log.error("ignoring model entry %s in %s (unknown or missing fields)", entry, path)
                continue
            entry.setdefault("label", entry["model_id"])
            if "capabilities" in entry:
                entry["capabilities"] = tuple(entry["capabilities"])
            spec = ModelSpec(**entry)
            self.specs = [s for s in self.specs if s.alias != spec.alias] + [spec]

    # --- lookup ---------------------------------------------------------

    def provider(self, spec: ModelSpec) -> Provider:
        return self.providers[spec.provider]

    def key_for(self, provider: Provider) -> str | None:
        return (self.env.get(provider.key_env) or "").strip() or None

    def base_url(self, provider: Provider) -> str | None:
        if provider.base_url_env and (self.env.get(provider.base_url_env) or "").strip():
            return self.env[provider.base_url_env].strip().rstrip("/")
        return provider.base_url

    def is_available(self, spec: ModelSpec) -> bool:
        provider = self.providers.get(spec.provider)
        if provider is None or not self.key_for(provider):
            return False
        return provider.native or bool(self.base_url(provider))

    def available(self) -> list[ModelSpec]:
        return [s for s in self.specs if self.is_available(s)]

    def resolve(self, name: str | None) -> ModelSpec | None:
        """Find a model by alias, model id, or "provider:model_id" (ad-hoc models)."""
        if not name:
            return None
        name = name.strip()
        for spec in self.specs:
            if name.lower() in (spec.alias.lower(), spec.model_id.lower(), spec.key.lower()):
                return spec
        provider, sep, model_id = name.partition(":")
        if sep and provider in self.providers and model_id:
            native = self.providers[provider].native
            return ModelSpec(alias=name, provider=provider, model_id=model_id, label=model_id,
                             thinking=native, effort=native)
        if name.startswith("claude-"):  # an Anthropic model that is not in the catalog yet
            return ModelSpec(alias=name, provider="anthropic", model_id=name, label=name,
                             thinking=True, effort=True)
        return None

    def pick(self, *names: str | None) -> ModelSpec:
        """The first of names that resolves and is available; else the first available model."""
        for name in names:
            spec = self.resolve(name)
            if spec and self.is_available(spec):
                return spec
        available = self.available()
        if not available:
            raise SystemExit(
                "No model provider is configured: set ANTHROPIC_API_KEY (or OPENROUTER_API_KEY, "
                "DEEPSEEK_API_KEY, LITELLM_MASTER_KEY, ...) in .env"
            )
        return available[0]

    # --- what the CLI needs -----------------------------------------------

    def cli_env(self, spec: ModelSpec) -> dict[str, str]:
        """Environment for the Claude CLI process that serves this model."""
        env = {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
        provider = self.provider(spec)
        if spec.max_output:
            env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(spec.max_output)
        if spec.context:
            env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = str(spec.context)
        if provider.native:
            return env
        small = spec.small_model or spec.model_id
        env.update(
            {
                "ANTHROPIC_BASE_URL": self.base_url(provider) or "",
                "ANTHROPIC_AUTH_TOKEN": self.key_for(provider) or "",
                "ANTHROPIC_API_KEY": "",  # must be empty, or the CLI sends it instead
                # Subagents and background work ask for opus/sonnet/haiku by tier name:
                # point every tier at models this provider actually serves.
                "ANTHROPIC_DEFAULT_FABLE_MODEL": spec.model_id,
                "ANTHROPIC_DEFAULT_OPUS_MODEL": spec.model_id,
                "ANTHROPIC_DEFAULT_SONNET_MODEL": spec.model_id,
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": small,
                "ANTHROPIC_SMALL_FAST_MODEL": small,
                "CLAUDE_CODE_SUBAGENT_MODEL": spec.model_id,
                # Anthropic-only beta headers make most gateways reject the request.
                "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
                # Never let an Anthropic login on the host reach a third-party endpoint.
                "CLAUDE_CODE_OAUTH_TOKEN": "",
            }
        )
        # Unknown model ids are otherwise treated as current Claude models (effort,
        # thinking, mid-conversation system messages). Declare what this model supports.
        # (The bundled CLI 2.1.x still sends output_config.effort and some anthropic-beta
        # headers to custom endpoints; LiteLLM drops them with drop_params, and the
        # Anthropic-compatible providers above accept them.)
        caps = ",".join(spec.capabilities)
        for tier in ("FABLE", "OPUS", "SONNET", "HAIKU"):
            env[f"ANTHROPIC_DEFAULT_{tier}_MODEL_SUPPORTED_CAPABILITIES"] = caps
        env.update(dict(provider.extra_env))
        return env

    def estimate_cost(self, spec: ModelSpec, usage: Mapping[str, Any] | None) -> float | None:
        """USD from token usage and the catalog price; None when the price is unknown."""
        if not usage or spec.price_in is None or spec.price_out is None:
            return None
        tokens_in = sum(int(usage.get(k) or 0) for k in
                        ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        tokens_out = int(usage.get("output_tokens") or 0)
        return (tokens_in * spec.price_in + tokens_out * spec.price_out) / 1_000_000

    def describe(self, spec: ModelSpec) -> str:
        provider = self.provider(spec)
        if provider.native or provider.label.split()[0] in spec.label:
            return spec.label
        return f"{spec.label} · {provider.label}"
