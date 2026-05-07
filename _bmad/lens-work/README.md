# Lens Workbench

LENS lifecycle workbench — feature context switching, initialization, planning, and governance.

## Commands

| Command | Code | Description |
|---------|------|-------------|
| /switch | SW | Switch the active Lens feature context |
| /new-feature | NF | Create a new feature with the feature initializer skill |
| /new-domain | ND | Create a new domain scaffold and register it with Lens |
| /new-service | NS | Create a new service scaffold within a domain |
| /help | HP | Show contextual command guidance |
| /next | NX | Route to the single best next lifecycle action |

## Discovery

- `module-help.csv` — full command catalog with args, phases, and outputs
- `module.yaml` — module registration and prompt list
- `agents/lens.agent.md` — entry agent with compact menu

## Configuration

- `bmadconfig.yaml` — committed Lens module defaults for governance path, topology, target project path, git remote, and lifecycle contract
- `docs/configuration.md` — user config contract for supported `config.user.yaml` overrides
