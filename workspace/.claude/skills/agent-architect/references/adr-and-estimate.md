# ADR template and estimation method

## ADR — `notes/work/adr/YYYY-MM-DD-<slug>.md`

Before writing, Grep `notes/work/adr/` for a related decision. Link it, or mark the old one
`Superseded by <file>`. No client names or confidential data — use a neutral project label.

```markdown
# ADR: <decision in a few words>
> خلاصه: <one line, for Grep — what was decided and why>

- Status: Proposed | Accepted | Superseded by <file> | Deprecated
- Date: YYYY-MM-DD (<Jalali date>)
- Context label: <anonymized project or "internal">

## Context
Problem, constraints (volume, latency, budget, data sensitivity, team skills), forces at play.

## Options considered
1. <Option> — pros / cons / cost / risk
2. <Option> — ...
(Always include the simplest viable option, even if rejected.)

## Decision
What was chosen and the deciding criteria.

## Consequences
Positive, negative, follow-up work, what becomes harder later.

## Verification
Docs and sources checked, with dates and library versions
(e.g. "langgraph docs via context7, YYYY-MM-DD, project pins vX.Y").

## Revisit when
Concrete triggers: volume above X, cost above Y, eval score below Z, a relevant release.
```

## Estimation method (mode D)

1. **Scope and assumptions.** Restate the problem in the client's words; list assumptions, out-of-scope
   items and what the client must provide (data access, sample data, API keys, a decision maker).
2. **Milestones with acceptance criteria.** Typical shape for agent projects (adapt, don't force):
   - M0 Discovery and data audit — access, samples, success metric, eval set v0.
   - M1 Proof of concept on the happy path + baseline eval score.
   - M2 Core graph, tools and integrations.
   - M3 Hardening — eval to the agreed threshold, guardrails, human approval steps, error handling.
   - M4 Observability, deployment, docs and handoff.
   - Optional: post-launch tuning or a monthly retainer.
3. **Three-point estimate per task:** optimistic O, most likely M, pessimistic P hours;
   expected E = (O + 4M + P) / 6. Report a rounded range, not false precision.
4. **Explicit line items** often forgotten: client communication and meetings, code review,
   deployment and environment setup, documentation, eval dataset labeling.
5. **LLM uncertainty buffer** as its own line (the `client-acquisition` skill uses 20–30%): higher
   when data quality is unknown, the success metric is vague, the eval threshold is strict, or
   integrations are new. State which drivers apply.
6. **Calibrate with history.** `project_list` with status=done gives estimate_hours vs logged hours.
   If past projects ran over by a consistent ratio, apply it and say so. No history → say the
   estimate is uncalibrated.
7. **Calendar time.** Convert hours to weeks using the user's real weekly capacity (profile + active
   projects from `project_list`), not hours ÷ 8.
8. **Running costs for the client,** separate from the build price: tokens per request × volume ×
   current price (search with date), hosting, vector DB, observability plan. Give ranges with
   assumptions; recommend the client owns the provider accounts and keys.
9. **Pricing and proposal text** belong to `client-acquisition` / `upwork-growth`; hand over the
   milestone list, ranges, assumptions and risks.

### Telegram summary shape (no tables)
- **⏱️ تخمین:** M0 … ساعت · M1 … · M2 … · M3 … · M4 … → جمع X–Y ساعت (~N هفته با ظرفیت فعلی)
- **بافر:** …٪ — به دلیل …
- **کالیبراسیون:** پروژه‌های قبلی به‌طور میانگین …٪ بیشتر/کمتر از تخمین شدند (یا: سابقه نیست)
- **هزینه جاری مشتری:** ماهانه حدود … (فرض‌ها: … درخواست در روز، قیمت‌ها طبق منبع … به تاریخ …)
- **ریسک‌های اصلی:** ۲-۳ مورد
