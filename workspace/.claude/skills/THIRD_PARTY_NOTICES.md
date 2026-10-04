# Third-party skills

Skills in this folder that come from other projects, with their licenses. Each vendored or
adapted skill keeps its license file (`LICENSE` / `LICENSE.txt`) in its own directory.
Discovered via the SkillsMP index (skillsmp.com), which aggregates public GitHub repositories.

| Skill | Source | License | How it is used |
|---|---|---|---|
| `skill-creator` | [anthropics/skills](https://github.com/anthropics/skills) `skills/skill-creator` @ 8a1541c | Apache-2.0 | Vendored unchanged |
| `discernment-nudge` | [anthropics/skills](https://github.com/anthropics/skills) `skills/discernment-nudge` @ 8a1541c | Apache-2.0 | Vendored unchanged |
| `deepread` | [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) `research/deepread` @ 19392f7 | MIT | Vendored + LifeAgent note appended |
| `systematic-debugging` | [obra/superpowers](https://github.com/obra/superpowers) `skills/systematic-debugging` @ 8ca22db | MIT | Vendored (test fixtures omitted) + LifeAgent note appended |
| `capture` | alirezarezvani/claude-skills `productivity/capture` @ 19392f7 | MIT | Adapted (Persian, LifeAgent tools; scripts removed) |
| `deep-work` | alirezarezvani/claude-skills `productivity/deep-work` @ 19392f7 | MIT | Adapted (calendar/habit tools instead of scripts); references and assets kept |
| `deep-research` | alirezarezvani/claude-skills `research/deep-research` @ 19392f7 | MIT | Adapted (notes/research layout, researcher subagents) |
| `decision-helper` | alirezarezvani/claude-skills `productivity/roast` + `c-level-advisor/executive-mentor/hard-call` @ 19392f7 | MIT | Adapted and merged; roast references kept |

Not included on purpose:
- Anthropic `docx` / `pdf` / `pptx` / `xlsx`: proprietary license that forbids copying them outside
  Anthropic's services. LifeAgent ships its own `office-docs` skill instead.
- Skills without a license (e.g. most of ComposioHQ/awesome-claude-skills): used only as ideas.
