# Understanding Your LENS Workspace

When you start using LENS, you will see the same few names over and over: the control repo, `TargetProjects/`, the governance repo, `lens.core/`, and LENS itself. This guide explains what each one is, what it is for, and how they work together during normal day-to-day use.

---

## Short Version

- **Control repo** = your LENS home base. Open this repo in your editor and run LENS commands here.
- **`TargetProjects/`** = the folder that contains the real repos you work on.
- **Governance repo** = the shared rules and feature-tracking repo, usually at `TargetProjects/lens/lens-governance/`.
- **`lens.core/`** = the read-only LENS payload inside your control repo.
- **LENS** = the workbench and assistant that coordinates planning, governance, and implementation across those locations.

If you remember only one thing, remember this: **use the control repo to run LENS, use target repos to change product code, and treat `lens.core/` as read-only.**

---

## Workspace Layout

Your workspace typically looks like this:

```text
control-repo/
├── lens.core/                     # read-only LENS payload
├── docs/                          # planning artifacts written by LENS
├── .lens/                         # local profile and workspace state
└── TargetProjects/
    ├── lens/
    │   └── lens-governance/       # shared governance repo
    └── {domain}/
        └── {service}/
            └── {repo}/            # actual code repo
```

The important point is that these folders do different jobs. LENS works best when you keep those jobs separate.

---

## What Each Part Is For

| Part | What it is | What you do there |
|------|------------|-------------------|
| **Control repo** | Your operational LENS workspace | Open it in VS Code, run LENS commands, review planning artifacts, manage the lifecycle |
| **`TargetProjects/`** | A container for cloned working repos | Open target repos, inspect code, and implement changes |
| **Governance repo** | Shared team authority for rules and feature metadata | Read constitutions, repo inventory, and feature state; let LENS use it for coordination |
| **`lens.core/`** | Installed LENS release payload | Use its prompts, skills, scripts, and docs indirectly through LENS; do not edit it directly |
| **Target repo** | A real product or implementation repo under `TargetProjects/` | Change application code, tests, configs, and other shipped software |
| **LENS** | The workbench that ties all of this together | Routes commands, reads governance, stages planning outputs, and guides work from planning to implementation |

---

## How They Work Together

### 1. You start in the control repo

The control repo is the workspace you open first. It gives LENS a stable home for:

- your local setup
- planning artifacts under `docs/`
- user state under `.lens/`
- the installed `lens.core/` payload
- the `TargetProjects/` folder where actual repos live

This is the place where you run commands like `/onboard`, `/dashboard`, `/next`, `/preplan`, and `/finalizeplan`.

### 2. `lens.core/` supplies the LENS behavior

Inside the control repo, `lens.core/` contains the LENS release payload: prompts, skills, workflows, scripts, and reference docs.

Most users should think of `lens.core/` the same way they think about an installed toolchain: it is part of the workspace, but it is not where normal project work happens.

### 3. Governance tells LENS what rules and shared state apply

The governance repo is the shared authority that tells LENS things like:

- which repos belong in `TargetProjects/`
- which constitutions and policies apply
- which features already exist
- what state those features are in

LENS uses governance to stay aligned with the rest of the team instead of treating your local workspace as an isolated sandbox.

### 4. `TargetProjects/` holds the repos you actually work on

`TargetProjects/` is not one repo. It is a folder full of repos.

That usually includes:

- the governance repo
- one or more target repos where implementation happens
- sometimes supporting repos that LENS needs to operate on

When it is time to inspect or change product code, this is where you go.

### 5. LENS coordinates the flow across all of them

In a normal workflow, LENS does all of the following:

- runs from the control repo
- reads its behavior from `lens.core/`
- uses governance to understand rules, repo inventory, and feature state
- stages planning artifacts in the control repo
- hands implementation work off to the correct target repo in `TargetProjects/`

That separation is the core design: **planning happens in the LENS workspace, implementation happens in target repos, and governance keeps the shared rules and state consistent.**

---

## What Lives Where

Use this as your quick placement guide:

- **Planning documents**: control repo `docs/`
- **Local profile and personal workspace state**: control repo `.lens/`
- **LENS prompts, skills, scripts, and reference docs**: control repo `lens.core/`
- **Constitutions, repo inventory, and shared feature metadata**: governance repo
- **Application code, tests, implementation configs, and shipped software**: target repos under `TargetProjects/`

If you are not sure where something belongs, ask a simple question: **is this LENS workspace state, shared governance state, or product code?** The answer tells you where it should live.

---

## A Typical User Flow

Here is the mental model for a normal day:

1. Open the control repo.
2. Run LENS commands there to check status and decide the next step.
3. Let LENS create or update planning artifacts in the control repo.
4. Move into the correct target repo under `TargetProjects/` when implementation is needed.
5. Let governance continue to provide shared rules and feature tracking in the background.

You do not need to manually stitch those systems together every time. LENS is designed to do that orchestration for you.

---

## Common Mistakes to Avoid

- Do not treat the control repo like your main application repo.
- Do not write product code into the control repo just because that is where you opened LENS.
- Do not edit `lens.core/` directly during normal use.
- Do not assume every repo under `TargetProjects/` is an application repo; one of them is usually the governance repo.
- Do not treat governance as personal scratch space; it is shared team state.

For most end users, anything involving the editable LENS source project or release promotion pipeline is background detail. The main things you need are the control repo, `TargetProjects/`, governance, and the LENS command surface.

---

## Related Guides

- [Getting Started](./GETTING-STARTED.md)
- [Onboarding Checklist](./onboarding-checklist.md)
- [Project Overview](./project-overview.md)
- [Lifecycle Reference](./lifecycle-reference.md)