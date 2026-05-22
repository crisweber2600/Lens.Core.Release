# PrePlan Brainstorm Governance Contract

This contract captures the expected behavior for interactive `/lens-preplan` runs.

## Conversation Order

1. Resolve feature context and `docs.path` silently from governance metadata.
2. Announce the resolved staging path and governance-only planning boundary.
3. Ask the BMAD brainstorming setup questions first:
   - What are we brainstorming about?
   - What specific outcomes are you hoping for?
4. Summarize the topic and goals back to the user and confirm accuracy.
5. Begin the brainstorming workflow.
6. If the user asks to create, clone, or register a target repo, preplan must pause and route that work through `bmad-lens-target-repo`, then resume the interrupted checkpoint.
7. Only after the brainstorming context exists may preplan offer follow-on synthesis such as research or a product brief.

## Forbidden Interactive Prompts

- Do not ask the user where drafts should be stored when `feature.yaml.docs.path` is already known.
- Do not ask a standalone upfront question such as "which services should I load context for?"
- Do not jump directly to product-brief or PRD synthesis before the brainstorming topic and goals have been elicited.
- Do not infer or invent a TargetProjects clone path inside preplan.
- Do not mutate `repo-inventory.yaml` or `feature.yaml.target_repos` directly from preplan.

## Context Boundary

- Preplan grounds itself in governance artifacts only: constitutions, feature docs, service docs, feature summaries, and prior planning artifacts mirrored into governance.
- If additional services are mentioned during the session, preplan should load matching governance service context implicitly as the conversation unfolds.
- If a mentioned service has no governance docs, preplan should surface that gap explicitly instead of inspecting target-project source code.
- If the session needs a new target repo, preplan should hand off to the dedicated repo-provisioning skill instead of reasoning about repo placement itself.

## Artifact Boundary

- Preplan stages drafts under the resolved control-repo docs path.
- Governance publication remains a later handoff concern and is not part of the preplan conversation loop by default.