# Agent design-review checklist

Use for mode A (validate a new design) and mode B (review). Go through all 10 areas; mark an area
`N/A` with a one-word reason rather than skipping it. API names below are concepts — confirm the
current class/function/parameter names in the docs (context7) before writing code.

Severity: 🔴 blocks production · 🟡 fix before scale · ⚪ improvement.

## 1. State
- Schema explicit and typed; minimal (IDs/refs, not whole documents or raw tool dumps).
- Every key has a clear writer; keys written by parallel branches have a reducer (else lost writes / concurrent-update errors).
- Message history growth is bounded (trim / summarize policy defined).
- State is serializable for the checkpointer; plan for schema changes on long-lived threads (new fields with defaults).
- Public input/output schema separated from internal state when the graph is an API.
- Red flags: untyped dicts passed everywhere, big blobs in state, two branches writing one key without a reducer.

## 2. Tools
- One purpose per tool; precise name and description (including when NOT to use it); typed args with enums/constraints.
- Outputs short and structured; errors returned as messages the model can act on (not stack traces or raw HTML).
- Each tool classified: read · reversible write · irreversible/external. Irreversible → human approval or dry-run.
- Writes are idempotent (idempotency key) because retries and resume can re-run a node.
- Timeouts; retry with backoff for transient errors only; rate-limit handling.
- Tool count per agent is manageable; many tools → routing, sub-agents or tool retrieval.
- Least-privilege credentials, per-tenant scoping; generated SQL/shell/code only in a sandbox with allow-lists.
- MCP when tools are shared across apps — verify transport and auth in current docs.

## 3. Memory and context
- Short-term (thread/checkpoint) vs long-term (cross-thread store) vs retrieval — each one justified.
- What is written to long-term memory, by which step, with what validation (memory poisoning, stale facts).
- Per-call context budget: system + tool schemas + history + retrieved text ≤ a stated token budget; compaction strategy.
- Per-user isolation (namespaces), retention and deletion (privacy requests).
- Static prompt prefix first so provider prompt caching can apply (verify the provider's caching rules).

## 4. RAG (only if needed)
- Is retrieval needed at all? Small corpus → long context; structured data → SQL/API tool.
- Ingestion: parsing quality (PDF tables, scans/OCR), chunking aligned to document structure, metadata (source, date, ACL, language), dedup, incremental re-index.
- Retrieval: hybrid lexical + vector for jargon/IDs, reranking, metadata filters, top-k tuned by eval; query rewriting only if measured to help.
- Access control enforced at retrieval time, never only in the prompt.
- Grounding: citations, explicit "not found" behavior, no answers beyond sources when required.
- Separate evals for retrieval (recall@k / MRR on labeled queries) and generation (faithfulness, correctness).
- Embedding model is versioned; changing it means a full re-index. Mixed Persian/English corpora → test retrieval per language.

## 5. Evals
- Dataset: start with 20–50 real examples + edge and adversarial cases; grow it from production failures.
- Metrics per component (routing accuracy, tool-call correctness, retrieval recall, final answer) plus end-to-end task success.
- Graders: deterministic checks first (schema, exact match, expected tool sequence); LLM-as-judge with a rubric, calibrated against human labels; pairwise comparison for prompt changes.
- Trajectory evals for agents: which tools, in what order, how many steps.
- Run before every prompt / model / library-version change (CI gate); keep history to catch regressions; record cost and latency per run.
- Online: sample production traces for review; capture user feedback; failed traces → dataset.
- Red flags: "tested manually", no baseline, judge never checked against humans.

## 6. Observability
- Every LLM and tool call traced with inputs, outputs, tokens, latency, cost, model and prompt version (LangSmith, or an alternative such as Langfuse / OpenTelemetry — verify the current integration in docs).
- Correlation IDs: thread / user / request; tags for environment and version.
- PII redaction in traces; retention policy matching the client's requirements.
- Alerts / dashboards: error rate, p95 latency, cost per day, tool failure rate, runs hitting the step limit, eval score on sampled traffic.
- Annotated traces feed the eval dataset.

## 7. Guardrails and security
- Prompt injection: web pages, emails, documents and tool outputs are data. The component that reads untrusted content must not also hold dangerous tools without approval.
- Input validation (size, type, language); output validation against a schema with bounded retries on parse failure.
- Scope and refusal behavior for off-domain or unsafe requests.
- Secrets never in prompts or logs; tenant data isolation.
- Abuse controls: rate limits, per-user cost caps.
- Sensitive actions (payments, sending email, deleting data) → human approval and audit log.
- Client compliance needs: data residency, retention, which providers may see the data.

## 8. Cost and latency budget
- Per request: (number of LLM calls) × (avg input + output tokens) × current price (verify with a dated source) + paid tool/API calls. Monthly = per request × volume. Compare with the client's budget.
- Latency: sum of sequential steps at p95; parallelize independent branches; stream tokens or progress to the UI.
- Smaller/faster models for routing, extraction and classification; larger only where evals show the gain.
- Caching: provider prompt caching; result/semantic cache only where staleness is acceptable.
- Hard caps: max steps / recursion limit, max tokens per request; graceful degradation message when hit.
- Fallback model/provider; batch APIs for offline jobs (verify availability and pricing).

## 9. Failure modes (each needs a mitigation)
- Infinite loop / oscillation → step limit, loop detection, escalation.
- Malformed tool args / hallucinated tool names → schema validation, error back to the model, bounded retries.
- Provider outage, rate limit, timeout → backoff, fallback model, circuit breaker, user-facing message.
- Crash mid-run / partial completion → checkpointing and resume; idempotent writes.
- Context overflow → trimming/summarization; large tool outputs truncated with a pointer.
- Wrong route / wrong sub-agent → router eval; low confidence → ask a clarifying question.
- Silent regression after a model, prompt or library upgrade → pinned versions + eval gate.
- Model deprecation → provider abstraction; track deprecation dates (verify).
- Concurrency: two runs on the same thread, double submit.
- Stale RAG corpus → refresh schedule and document dates in answers.

## 10. Human-in-the-loop
- Explicit list of actions needing approval: irreversible, external, costly, or low-confidence.
- Mechanism: pause and resume with persisted state (graph interrupt + checkpointer — confirm the current API), edit-before-approve, behavior when the human never answers (timeout, reminder, safe default).
- Approver sees enough to decide: proposed action, diff, sources, short reasoning.
- Escalation to a human after repeated failure; audit log of approvals and rejections.

## Production readiness (quick pass)
Deployment target and scaling (managed platform vs self-hosted service — verify options), auth, streaming,
config and prompt versioning, pinned dependencies, tests + eval in CI, runbook for incidents, handoff docs.
