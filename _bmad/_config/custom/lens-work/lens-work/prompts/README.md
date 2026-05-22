# Prompts — Naming Convention

All prompt files follow the pattern `lens-{command}.prompt.md`.

| Pattern | Example | Menu Trigger |
|---------|---------|--------------|
| `lens-{command}.prompt.md` | `lens-dev.prompt.md` | `[DV]` or `/dev` |

The `{command}` segment maps directly to the slash-command name and the agent menu shortcut. The `.prompt.md` suffix is required for Copilot to register the file as a prompt.

## Prompt→Skill Mapping

Each prompt routes to a skill by referencing `{project-root}/lens.core/_bmad/lens-work/skills/bmad-lens-{skill-name}/SKILL.md`. The prompt is a thin stub; the skill handles execution.

## Frontmatter

All prompts include:
- `model` — default LLM model
- `communication_language` — user's preferred language
- `document_output_language` — language for generated documents
- `description` — brief summary for Copilot discovery
