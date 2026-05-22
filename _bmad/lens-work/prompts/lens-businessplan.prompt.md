---
description: 'BusinessPlan phase — PRD creation and UX design for a feature'
---

## Follow-up Questions

Use `vscode_askQuestions` for all follow-up questions instead of freeform chat prompts.

# /businessplan

Load `{project-root}/lens.core/_bmad/lens-work/skills/lens-businessplan/SKILL.md` and execute it.

Runtime config to resolve before invocation:
- governance_repo
- control_repo
- feature_id

The BusinessPlan phase publishes reviewed PrePlan artifacts to governance, then delegates PRD and UX authoring through `lens-bmad-skill`. The skill handles interactive vs batch mode, review-ready fast paths, and auto-delegation from `/next`. This release prompt does not add confirmation logic; all workflow orchestration is delegated to the skill.

Do not implement BusinessPlan logic in this prompt. Read the skill and follow its instructions.
