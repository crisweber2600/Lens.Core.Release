# Capabilities

## Built-in

| Code | Name | Description | Source |
|------|------|-------------|--------|
| validate-workspace | Validate Workspace Structure | Checks workspace against Lens Core rules; produces pass/fail report with remediation guidance | `capabilities/validate-workspace.md` |
| generate-github-stubs | Generate .github Redirect Stubs | Creates `.github/workflows/` and `.github/prompts/` redirect stubs pointing to `lens.core/` canonical | `capabilities/generate-github-stubs.md` |
| generate-workflows | Generate Enforcement Workflows | Produces GitHub workflow files for runtime enforcement of Lens Core rules | `capabilities/generate-workflows.md` |
| define-rules | Define Core Rules | Documents the definitive ruleset as `Agents.md` and updates `rules-core.md` | `capabilities/define-rules.md` |
| register-extensions | Register Rule Extensions | Adds custom rules from other agents to the extensibility registry without modifying core | `capabilities/register-extensions.md` |
| audit-enforcement | Audit Enforcement | Generates a compliance report from the enforcement log; surfaces gaps and coverage | `capabilities/audit-enforcement.md` |

## Tools

Prefer crafting your own tools over depending on external ones. A script you wrote and saved is more reliable than an external API. Use the file system creatively.

### User-Provided Tools

_MCP servers, APIs, or services the owner has made available. Document them here._
