# Lens Workbench

LENS lifecycle workbench for feature context switching, initialization, planning, governance, and Auspex topology/reporting workflows.

Auspex is the preferred Lens workflow for organic, multi-feature knowledge work: Two-Tree topology, derived maps, living ledgers, Salmon impact, audits, and stakeholder reporting. The legacy domain, service, and feature commands remain available for direct scaffold and lifecycle operations.

## Commands

| Command | Code | Description |
|---------|------|-------------|
| /switch | SW | Switch the active Lens feature context |
| /lens-auspex-start | AX0 | Create an Auspex unit of work with durable memory, then hand off to Lens lifecycle |
| /lens-auspex-map-audit | AXA | Audit topology, stable IDs, parent refs, ledgers, and projection readiness |
| /lens-auspex-topology-design | AXT | Design or update Two-Tree program, domain, and service topology |
| /lens-auspex-reporting-snapshot | AXR | Create read-only stakeholder status snapshots |
| /new-feature | NF | Create a new feature with the feature initializer skill |
| /new-domain | ND | Create a new domain scaffold and register it with Lens |
| /new-service | NS | Create a new service scaffold within a domain |
| /help | HP | Show contextual command guidance |
| /next | NX | Route to the single best next lifecycle action |

## Discovery

- `module-help.csv` — full command catalog with args, phases, and outputs
- `module.yaml` — module registration and prompt list
- `agents/lens.agent.md` — entry agent with compact menu
- `docs/auspex-lens-integration-flow.md` — how to wire Auspex into the Lens workflow and run the new flow

## Configuration

- `bmadconfig.yaml` — committed Lens module defaults for governance path, topology, target project path, git remote, and lifecycle contract
- `docs/configuration.md` — user config contract for supported `config.user.yaml` overrides
