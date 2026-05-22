# Lens Workbench

LENS lifecycle workbench for feature context switching, initialization, planning, governance, topology, ledgers, Salmon impact, audits, and stakeholder reporting workflows.

Use the plain NextLens command surface for durable work intake and cumulative project knowledge. Domain, service, and feature commands remain available for direct scaffold and lifecycle operations.

## Commands

| Command | Code | Description |
|---------|------|-------------|
| /switch | SW | Switch the active Lens feature context |
| /lens-work-intake | WI | Create a durable feature archive, then hand off to Lens lifecycle |
| /lens-map-audit | MA | Audit topology, stable IDs, parent refs, ledgers, and projection readiness |
| /lens-topology-design | TD | Design or update Two-Tree program, domain, and service topology |
| /lens-reporting-snapshot | RS | Create read-only stakeholder status snapshots |
| /new-feature | NF | Create a new feature with the feature initializer skill |
| /new-domain | ND | Create a new domain scaffold and register it with Lens |
| /new-service | NS | Create a new service scaffold within a domain |
| /help | HP | Show contextual command guidance |
| /next | NX | Route to the single best next lifecycle action |

## Discovery

- `module-help.csv` — full command catalog with args, phases, and outputs
- `module.yaml` — module registration and prompt list
- `agents/lens.agent.md` — entry agent with compact menu
- `skills/lens-*/` — imported NextLens skill source mirror for local lifecycle and reporting workflows

## Configuration

- `bmadconfig.yaml` — committed Lens module defaults for governance path, topology, target project path, git remote, and lifecycle contract
- `docs/configuration.md` — user config contract for supported `config.user.yaml` overrides
