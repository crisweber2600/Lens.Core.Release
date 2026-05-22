# Document Project

Capture the final state of the implemented feature before archiving by delegating to the wrapped Lens document-project workflow.

## Outcome

Project documentation is generated through `bmad-lens-document-project`, which runs the full `bmad-document-project` workflow with feature-aware output paths. Successful completion of that wrapped run satisfies the documentation gate for the complete workflow.

## When to Use

After the retrospective and before finalize. This is the **non-negotiable** step — the wrapped documentation workflow must complete before the feature is archived.

## Delegation Contract

The complete workflow does not manage a manual README/deployment checklist itself. It delegates documentation capture to `bmad-lens-document-project`, which:

- resolves feature-scoped docs paths from `feature.yaml` when available
- falls back to the standard Lens feature docs paths when feature metadata does not define overrides
- invokes the full `bmad-document-project` workflow in that scoped context
- writes the generated documentation artifacts to the control repo docs path and mirrors governance-facing outputs into the feature directory docs path

The wrapped workflow owns the exact artifact set. Typical outputs come from the `bmad-document-project` flow itself and may include generated overview/index artifacts rather than a fixed manual document pair.

## Process

1. Resolve the current feature context (`featureId`, `domain`, `service`, `governance_repo`)
2. Delegate to the existing Lens wrapper:

```text
Load `../../bmad-lens-document-project/SKILL.md` with the current feature context.
```

3. Let the wrapped workflow decide whether it needs an initial scan, a resume, or a rescan based on its own state and existing artifacts
4. Do not proceed to finalize until the wrapped workflow completes successfully or the user explicitly exits back out of the complete workflow

## Confirmation

After documentation is captured, confirm:

```
✓ bmad-lens-document-project completed for {featureId}
✓ Control repo feature docs captured under the resolved docs path
✓ Governance repo feature docs captured under the resolved governance docs path
```

If the wrapped workflow is cancelled or fails, stop the complete workflow and resolve the documentation issue before archive.
