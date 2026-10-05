<!--
راهنمای استفاده (برای صاحب پروژه):
این فایل را به agent پیاده‌سازی بده (مثلاً یک session جدید Claude Code روی همین ریپو) و بنویس:
«docs/IMPLEMENTATION_BRIEF.md را کامل بخوان و طبق بخش "Your mission" کار را شروع کن.»
agent اول گزارش تحلیل می‌دهد و برای تصمیم‌های مهم از تو سؤال می‌پرسد؛ قبل از تأیید تو چیزی را روی سرور اجرا یا merge نمی‌کند.
-->

# LifeAgent — Implementation & Operations Brief

**Audience:** an AI implementation/ops agent (e.g. Claude Code) taking over deployment, infrastructure and the next development steps.
**Repo:** https://github.com/Kyzen-dev/LifeAgent (public) · default branch `claude/brave-feynman-oienzb` (no `main` yet)
**Brief date:** 2026-10-05 (1405/07/13) · **Owner:** a Persian-speaking freelance AI engineer living in Iran; single user.

---

## 1. Your mission

1. **Analyze and review** how to run LifeAgent in production for this owner — hosting, deployment, hardening, operations, cost — and the open technical items listed here. Produce an evidence-based analysis with a clear recommendation, not a menu.
2. **Plan** the implementation of the agreed items as small, reviewable steps.
3. **Implement** only after the owner approves the plan, via branches + PRs that pass CI. Never act on the owner's server or merge without explicit approval.

### Deliverables
| # | Deliverable | Where |
|---|---|---|
| D1 | Infra & deployment analysis report (findings, options matrix, recommendation, risks, open questions) | `docs/analysis/2026-10-infra-review.md` |
| D2 | Step-by-step implementation plan with acceptance criteria per step | same report, section "Plan" |
| D3 | PRs for approved changes (each: tests, CI green, short PR description, rollback note) | GitHub |
| D4 | Updated owner-facing docs if behavior changes (`docs/DEPLOY.md` in Persian, and regenerate `docs/setup-guide.html` content accordingly) | repo |
| D5 | A short Persian summary for the owner after each milestone (what changed, what to do, what to verify) | chat |

### Definition of done for the analysis (D1)
- Every factual claim about a provider, price, quota, policy or library API is **verified against a current primary source** (link + access date), or explicitly marked *unverified*.
- Each recommendation states: why, cost/month, effort, risk, and how to roll back.
- Questions that only the owner can answer are listed at the end, each with your recommended default.

---

## 2. Ground rules

1. **Secrets and personal data never enter git.** The repo is public. `.env`, `workspace/memory/*`, `workspace/notes/*`, `workspace/inbox|outbox/*`, `data/` are git-ignored — keep it that way. Do not paste secrets into PRs, logs, issues or chat.
2. **Ask before** anything destructive or outward-facing: server commands, deleting data, force-push, merging, changing billing, sending messages to the owner's contacts.
3. **Sanctions/ToS:** the owner lives in Iran. Many providers (cloud, payment, freelance platforms) restrict Iran. Analyze availability honestly and note restrictions, but **do not** advise on evading sanctions, KYC, identity or location checks. Account access arrangements are the owner's business and out of scope.
4. **Verify, don't recall.** Prices, free-tier limits, API shapes and model IDs change. Check current docs (WebSearch/WebFetch, Context7 for libraries). The Claude Agent SDK / Claude API details must come from Anthropic's current docs.
5. **Keep the safety model intact:** read-only tools run freely; anything with external side effects requires the owner's tap on "✅ تأیید" in Telegram (`lifeagent/permissions.py`, `lifeagent/approvals.py`). Do not widen auto-approval without explicit approval.
6. **Owner UX is Persian.** User-facing bot text and owner docs in Persian; code, commits, PRs and technical reports in English.
7. Small PRs, one concern each, with tests. CI must be green before asking for merge.

---

## 3. System overview

**What it is:** a personal assistant the owner talks to via Telegram. Python app (`python-telegram-bot`) → one long-lived **Claude Agent SDK** client per chat (`ClaudeSDKClient`, bundled Claude CLI) → tools via MCP. Proactive routines via APScheduler. Data in SQLite + Markdown files.

```
Telegram ──long polling──► lifeagent (python -m lifeagent)
   ▲                         ├─ telegram_bot.py   handlers, progress UI, routine delivery (SKIP = stay silent)
   │ approve/deny buttons    ├─ agent.py          ChatAgent: ClaudeSDKClient per chat, resume via data/home/.claude
   └─────────────────────────┤  permissions.py    allow / ask / deny policy  ─► approvals.py (inline buttons)
                             ├─ scheduler.py      routines, reminders, prayer times (APScheduler, in-memory, rebuilt from DB)
                             ├─ tools/*           in-process MCP server "life" (SQLite): finance, habits, health, journal,
                             │                    tasks, goals, reminders, freelance/time tracking, weather, prices, YouTube, prayer
                             ├─ mcp_servers.py    external MCP: google (stdio, uvx workspace-mcp), github (remote http),
                             │                    context7 (remote http), browser (optional, npx @playwright/mcp)
                             ├─ db.py             SQLite (WAL) + migrations via PRAGMA user_version
                             └─ workspace/        agent cwd: CLAUDE.md, .claude/skills (31), .claude/agents (5), memory/, notes/
```

### Key files
| Path | Purpose |
|---|---|
| `lifeagent/__main__.py` | entry point (`python -m lifeagent`) |
| `lifeagent/agent.py` | Agent SDK options (model, effort, system prompt, skills, MCP servers, `can_use_tool`) |
| `lifeagent/config.py` | all settings from env (`Settings.from_env`) |
| `lifeagent/doctor.py` | health check; `--live` runs one tiny real agent turn |
| `deploy/configure.py` | stdlib-only interactive wizard; validates Telegram token, detects user id, validates Anthropic key; writes `.env` (0600); `--check` mode |
| `deploy/setup-server.sh` | idempotent VPS setup: swap, Docker, wizard, uid mapping, build, up, doctor |
| `deploy/backup.sh` | consistent SQLite online backup + memory/notes/sessions/.env tarball, 14-day retention |
| `deploy/container_smoke.py` | runs inside the built image in CI |
| `.github/workflows/ci.yml` | lint + pytest; Docker build for **amd64 and arm64** + smoke test as an arbitrary non-root uid |
| `Dockerfile` / `docker-compose.yml` | `python:3.12-slim-trixie`; fonts-vazirmatn, pango (WeasyPrint), uv; runs as host uid (`LIFEAGENT_UID/GID`), `init: true`, log rotation |
| `docs/DEPLOY.md`, `docs/setup-guide.html` | owner's Persian setup guide (Markdown and offline HTML) |
| `docs/ROADMAP.md` | development roadmap (phases 0–5 + security track) |
| `workspace/.claude/skills/*` | 31 skills (behavior); `THIRD_PARTY_NOTICES.md` lists licenses |

### Runtime facts
- **Versions:** Python 3.12, `claude-agent-sdk>=0.2.163` (bundles the Claude CLI; wheels exist for linux x86_64 and aarch64), `python-telegram-bot` 22.x, APScheduler 3.11.
- **Default model:** `claude-sonnet-5-5`, effort `medium`, adaptive thinking (owner chose "economical"). Override with `LIFEAGENT_MODEL` / `LIFEAGENT_EFFORT`.
- **Volumes:** `./data → /data` (SQLite `lifeagent.sqlite3`, `HOME=/data/home` incl. `~/.claude` session transcripts used for resume, uv cache, Google tokens); `./workspace → /app/workspace`.
- **Inbound network:** none required (Telegram long polling). Port `127.0.0.1:8000` is published only for the one-time Google OAuth callback via SSH tunnel.
- **Outbound domains:** `api.telegram.org`, `api.anthropic.com` (Claude CLI also contacts Anthropic endpoints), `api.openai.com` (voice, optional), `api.githubcopilot.com` + `api.github.com` (optional), `mcp.context7.com`, `api.aladhan.com`, `api.open-meteo.com`, `geocoding-api.open-meteo.com`, `api.coingecko.com`, `api.frankfurter.app`, `www.youtube.com`, Google OAuth/APIs (optional), `pypi.org`/`files.pythonhosted.org` (uvx), `registry.npmjs.org` (browser MCP, optional).
- **Approximate footprint (to be measured — see T-A4):** Python app ~150 MB + Claude CLI process per active chat ~300–500 MB + optional Google MCP ~150 MB. A 1 GB VM needs swap; 2 GB+ recommended.
- **Owner preferences baked into defaults:** routines 08:00 / 14:00 / 23:00 Asia/Tehran, AI digest Thu 10:00, weekly review Fri 18:00, prayer reminders optional (`PRAYER_REMINDERS`).

---

## 4. Verification status (be precise about what is proven)

| Area | Status | Evidence |
|---|---|---|
| Unit tests (37) + lint | ✅ verified | CI `test` job |
| Docker image builds on amd64 and arm64 (incl. apt: Vazirmatn, pango) | ✅ verified | CI `docker` matrix |
| Inside image as non-root arbitrary uid: libraries, fonts, Persian PDF embeds Vazirmatn, SQLite tools, Claude CLI starts and loads 31 skills + 5 subagents | ✅ verified | `deploy/container_smoke.py` in CI |
| Setup wizard (`configure.py`) logic, `.env` writing, Anthropic key rejection path | ✅ verified (Telegram calls mocked) | tests + manual dry run |
| Backup + restore of a live WAL database | ✅ verified locally | manual test |
| Offline HTML guide renders on desktop/mobile, light/dark, no overflow | ✅ verified | Chromium screenshots |
| **Real Telegram conversation end to end** | ❌ not verified | no Telegram access during development |
| **Real Claude turn with the owner's key** (`doctor --live`) | ❌ not verified | no key available |
| **`setup-server.sh` on a real VM** (Oracle ARM / GCP) | ❌ not verified | logic reviewed, `bash -n` only |
| **Google OAuth flow inside Docker** (callback binding) | ⚠️ uncertain | see T-D |
| Prayer times / weather / prices live APIs | ⚠️ parsing verified with fixtures; live calls not verified | — |
| Oracle Always Free idle-reclamation behavior for this workload | ⚠️ policy-based assumption | see T-A |

---

## 5. Analysis tasks

Work through these in order. For each: findings (verified vs assumed) → options → recommendation → plan → acceptance criteria.

### T-A. Hosting decision
Compare at least: **Oracle Cloud Always Free (Ampere A1)**, **Google Cloud e2-micro free tier**, **a low-cost paid VPS** (e.g. ARM/x86 instances from Hetzner, or similar providers in EU), **PaaS** (Fly.io / Railway / Render / Koyeb — check if long-running workers with persistent volumes are free or cheap), and **GitHub Codespaces** (testing only).
Criteria: monthly cost; persistence (volume for SQLite + `~/.claude`); always-on (no sleeping); RAM/CPU vs footprint; idle-reclamation or suspension policies; egress to all domains in §3; latency to Telegram/Anthropic; ARM vs x86 (both supported); backup options; operational burden; **signup/payment feasibility given the owner's situation (state restrictions factually; no evasion advice)**.
- T-A4: **measure** real memory/CPU of the container during idle, a normal turn, a routine, and with Google MCP enabled (`docker stats`), and size the VM from data.
Output: decision matrix + recommendation + fallback option.

### T-B. Delivery pipeline
Today the server builds the image itself (`docker compose up --build`). Evaluate **building in CI and pushing to GHCR** (multi-arch), with the server only pulling a tagged image:
- Pros to quantify: no compiler/RAM spikes on small VMs, reproducible artifact, faster deploys, instant rollback by tag.
- Design: `release` workflow on tag/merge to `main` → `ghcr.io/kyzen-dev/lifeagent:<sha>` + `:stable`; compose uses `image:` with optional local `build:`; `setup-server.sh` gains `pull` mode.
- Also: create a protected `main` branch with required CI (ROADMAP 0.1) and a release/rollback procedure.

### T-C. Reproducibility & supply chain
- `requirements*.txt` use `>=` ranges → introduce a lock (e.g. `uv lock`/`uv pip compile` with hashes) for the image; keep CI testing the lock.
- External MCP servers are fetched unpinned at runtime (`uvx workspace-mcp`, `npx @playwright/mcp@latest`) → pin versions, ideally pre-install in the image so runtime does not depend on PyPI/npm.
- Pin the base image by digest; add Dependabot (pip, GitHub Actions, Docker).
- GitHub Actions warn that Node 20 actions are deprecated → bump action majors.

### T-D. Google Workspace OAuth in Docker
`workspace-mcp` runs as a stdio child of the Claude CLI inside the container; its OAuth callback (`WORKSPACE_MCP_PORT`; 8000 is assumed in our compose file — verify the server's actual default) must be reachable from the owner's browser via `ssh -L 8000:localhost:8000`. Unknown: whether the callback server binds `0.0.0.0` inside the container (required for the published port) and where tokens are stored (must be under `/data`).
Read the current `workspace-mcp` docs/source, test locally, and propose the most robust flow (e.g. env vars for bind host/base URI, a one-shot auth command, or credential dir on `/data`). Update `docs/DEPLOY.md` §6 accordingly.

### T-E. Server hardening & operations
Propose and script (extend `setup-server.sh` or add `deploy/harden.sh`, opt-in):
- SSH key-only, disable password auth; `ufw` default deny inbound except SSH; `fail2ban`; `unattended-upgrades`.
- Docker: `mem_limit`/`cpus` sizing from T-A4; a `healthcheck` (the bot has no HTTP port — propose a heartbeat file or a tiny local endpoint); keep `init: true` and log rotation (already added).
- **Monitoring:** heartbeat to healthchecks.io (or similar free service) + Telegram error alerts (ROADMAP 0.2/0.3).
- **Backups:** off-server, encrypted (`age`) — e.g. weekly encrypted tarball sent to the owner's Telegram or object storage; a documented **restore drill** with acceptance test.
- Time: server cron runs in server TZ (UTC); app uses `Asia/Tehran` internally — document clearly.

### T-F. Application robustness review
Review and propose fixes (with tests) for:
- One long-lived `ClaudeSDKClient` per chat with no idle disconnect → memory over days; consider idle timeout + resume, and automatic session rotation with a summary (ROADMAP 1.6).
- Cost accounting (`usage` table) is approximate (cumulative `total_cost_usd` per client lifetime); consider per-turn usage logging incl. cache read/write tokens (ROADMAP 1.7).
- Concurrency: per-chat lock; routines and user messages queue; approval waits block the chat — confirm acceptable UX.
- Scheduler: reminders are rebuilt from SQLite at startup; prayer jobs scheduled daily with retry; verify DST/timezone assumptions (Iran abolished daylight saving time — confirm the container's tzdata reflects it).
- Failure modes: Telegram 409 conflict, Anthropic 429/529/overload, credit exhaustion, network partitions → user-visible Persian messages and backoff.
- Security: prompt-injection via email/web/file content (data ≠ instructions), path checks in `permissions.classify`, `send_file` path confinement, `.env` exposure inside container env.

### T-G. Model & cost strategy
Using Anthropic's current docs: validate model IDs and pricing; recommend per-route settings (chat vs routines vs research subagents), prompt caching effectiveness, and a monthly budget forecast for the owner's usage pattern (5 routines/day + ~30 messages/day as a starting assumption). Keep the owner's "economical" preference as the default.

### T-H. Live acceptance test plan
Turn §5 of `docs/DEPLOY.md` (the checklist) into an acceptance script the owner can run on the first deploy, plus `python -m lifeagent.doctor --live` criteria. Define pass/fail per item and how to collect logs (`docker compose logs --tail 200`).

---

## 6. Constraints for any proposal

- Single user; free or very low cost preferred; minimal ops burden (owner is a Python developer but not a sysadmin).
- No inbound ports required by default; Telegram long polling stays unless webhook brings a measured benefit.
- Must run on both arm64 and amd64.
- Keep data local to the owner's server; no third-party storage of personal data without encryption and approval.
- Persian UX; approval gate for side effects; no secrets in git.

---

## 7. How to work in this repo

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt -r requirements-docs.txt ruff
ruff check --select E,F,W,B --ignore E501 lifeagent tests deploy
python -m pytest -q
python -m lifeagent.doctor            # needs .env (use deploy/configure.py)
docker build -t lifeagent:dev .       # full image; CI also runs deploy/container_smoke.py inside it
```
Conventions:
- **DB schema changes:** append to `MIGRATIONS` in `lifeagent/db.py` (never edit an applied migration); update `SCHEMA` for fresh installs; add a test like `tests/test_db.py`.
- **New tool:** add to a module in `lifeagent/tools/`, wrap with `@safe`, return `ok()/err()`, register in `tools/__init__.py`, classify side effects in `permissions.py`, test with the handler directly (see `tests/test_freelance.py`).
- **New behavior:** prefer a skill in `workspace/.claude/skills/<name>/SKILL.md` (frontmatter `name`, `description`); keep personal facts out of skills (they read `memory/profile.md`).
- **Routines:** prompts in `lifeagent/prompts.py`; a routine may answer exactly `SKIP` to send nothing.
- Commits: imperative subject, body explains why; PRs small with test evidence.

---

## 8. Open questions to ask the owner (with suggested defaults)

1. Hosting budget: strictly free, or up to ~5 USD/month for reliability? *(default: free first — Oracle; paid fallback ready)*
2. Is the owner able to complete signup/payment for the chosen provider? *(ask; do not advise on workarounds)*
3. Enable Google Workspace now or later? *(default: later, after the core is stable)*
4. Off-server backup destination: Telegram (encrypted file to the owner) or object storage? *(default: Telegram)*
5. Allow CI-built images on GHCR (public package, contains no secrets)? *(default: yes)*
6. Monthly Anthropic budget cap? *(default: 30 USD, set in the Anthropic console)*

---

## 9. Suggested first message back to the owner

Reply in Persian with: (1) your understanding of the goal in 3 lines, (2) the questions from §8 you need answered now, (3) the order you will work in (T-A → T-B/T-C → T-D → T-E → T-F → T-G → T-H), and (4) when the D1 report will be ready.
