const fs = require('node:fs/promises');
const path = require('node:path');

// fs-extra compatibility helpers using built-in node:fs
const fsHelpers = {
    async pathExists(p) {
        try { await fs.access(p); return true; } catch { return false; }
    },
    async ensureDir(p) {
        await fs.mkdir(p, { recursive: true });
    },
    async copy(src, dest) {
        await fs.copyFile(src, dest);
    },
    async readFile(p) {
        return fs.readFile(p, 'utf8');
    },
    async writeFile(p, content) {
        await fs.writeFile(p, content, 'utf8');
    }
};

function readScalarYamlValue(content, key) {
    const match = content.match(new RegExp(`^${key}:\\s*(.+)$`, 'm'));
    if (!match) return undefined;
    const rawValue = match[1].trim();
    if ((rawValue.startsWith('"') && rawValue.endsWith('"')) || (rawValue.startsWith("'") && rawValue.endsWith("'"))) {
        return rawValue.slice(1, -1);
    }
    return rawValue;
}

function parseCsvLine(line) {
    const values = [];
    let current = '';
    let inQuotes = false;

    for (let index = 0; index < line.length; index++) {
        const char = line[index];

        if (inQuotes) {
            if (char === '"') {
                if (line[index + 1] === '"') {
                    current += '"';
                    index++;
                } else {
                    inQuotes = false;
                }
            } else {
                current += char;
            }
            continue;
        }

        if (char === ',') {
            values.push(current);
            current = '';
            continue;
        }

        if (char === '"') {
            inQuotes = true;
            continue;
        }

        current += char;
    }

    values.push(current);
    return values;
}

function toYamlString(value) {
    return `"${String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
}

function getConfigValue(config, keys, fallback) {
    for (const key of keys) {
        if (Object.prototype.hasOwnProperty.call(config, key) && config[key] !== undefined && config[key] !== null && config[key] !== '') {
            return config[key];
        }
    }
    return fallback;
}

async function readInstalledCoreConfig(projectRoot) {
    const candidatePaths = [
        path.join(projectRoot, '_bmad', 'core', 'bmadconfig.yaml'),
        path.join(projectRoot, '_bmad', 'bmb', 'bmadconfig.yaml'),
        path.join(projectRoot, '_bmad', 'bmm', 'bmadconfig.yaml'),
        path.join(projectRoot, '_bmad', 'cis', 'bmadconfig.yaml'),
        path.join(projectRoot, '_bmad', 'gds', 'bmadconfig.yaml'),
        path.join(projectRoot, '_bmad', 'tea', 'bmadconfig.yaml'),
    ];

    for (const candidatePath of candidatePaths) {
        if (!(await fsHelpers.pathExists(candidatePath))) continue;
        const content = await fsHelpers.readFile(candidatePath);
        return {
            user_name: readScalarYamlValue(content, 'user_name'),
            communication_language: readScalarYamlValue(content, 'communication_language'),
            document_output_language: readScalarYamlValue(content, 'document_output_language'),
            output_folder: readScalarYamlValue(content, 'output_folder'),
        };
    }

    return {};
}

async function readInstalledSkillManifest(projectRoot) {
    const manifestPath = path.join(projectRoot, '_bmad', '_config', 'skill-manifest.csv');
    if (!(await fsHelpers.pathExists(manifestPath))) {
        return [];
    }

    const content = await fsHelpers.readFile(manifestPath);
    const lines = content.split(/\r?\n/).filter(line => line.trim().length > 0);
    if (lines.length <= 1) {
        return [];
    }

    const headers = parseCsvLine(lines[0]);
    const indexByHeader = Object.fromEntries(headers.map((header, index) => [header, index]));
    const skills = [];

    for (const line of lines.slice(1)) {
        const row = parseCsvLine(line);
        const name = row[indexByHeader.canonicalId];
        const description = row[indexByHeader.description];
        const skillPath = row[indexByHeader.path];
        const installToBmad = row[indexByHeader.install_to_bmad];

        if (!name || !skillPath || installToBmad !== 'true') {
            continue;
        }

        skills.push({
            name,
            description,
            targetPath: `lens.core/${skillPath}`,
        });
    }

    return skills;
}

/**
 * Copy all files from srcDir to destDir, optionally skipping existing files.
 * Only copies files (not subdirectories).
 */
async function copyDirContents(srcDir, destDir, { skipExisting = true, logger } = {}) {
    await fsHelpers.ensureDir(destDir);
    const entries = await fs.readdir(srcDir, { withFileTypes: true });
    let copied = 0;
    let skipped = 0;
    for (const entry of entries) {
        if (!entry.isFile()) continue;
        const destPath = path.join(destDir, entry.name);
        if (skipExisting && await fsHelpers.pathExists(destPath)) {
            skipped++;
            continue;
        }
        await fsHelpers.copy(path.join(srcDir, entry.name), destPath);
        copied++;
    }
    return { copied, skipped };
}

// ─────────────────────────────────────────────────────────────────────────────
// Stub generators — thin adapters that redirect to module content by path
// ─────────────────────────────────────────────────────────────────────────────

const LIGHT_PREFLIGHT_COMMAND = 'uv run ./lens.core/_bmad/lens-work/scripts/light-preflight.py';

function ghSkillStub(name, description, targetPath) {
    return `---
name: ${name}
description: ${toYamlString(description)}
---

# ${name} (Stub)

> **This is a stub.** Load and execute the full skill from the release module.

Read and follow all instructions in:

\`\`\`
${targetPath}
\`\`\`
`;
}

function ghAgentStub() {
    return `\`\`\`chatagent
---
description: '@lens — LENS Workbench thin shell for help, next action, and status routing'
tools: ['read', 'edit', 'search', 'execute']
---

You must fully embody this agent's persona and follow all activation instructions exactly as specified.

<agent-activation CRITICAL="TRUE">
1. LOAD the module config from lens.core/_bmad/lens-work/module.yaml
2. LOAD the FULL agent definition from lens.core/_bmad/lens-work/agents/lens.agent.md
3. READ its entire contents - this contains the complete thin-shell agent persona and menu
4. LOAD the lifecycle contract from lens.core/_bmad/lens-work/lifecycle.yaml
5. LOAD the module help index from lens.core/_bmad/lens-work/module-help.csv
6. FOLLOW every activation step in the agent definition precisely
7. DISPLAY the shell greeting and compact menu from the agent definition
8. WAIT for user input before proceeding
</agent-activation>

\`\`\`
`;
}

function ghStubPrompt(name, description, targetPrompt, extra, { noModel = true } = {}) {
    const extraBlock = extra ? `\n${extra}` : '';
    const modelLine = noModel ? '' : 'model: Claude Sonnet 4.6 (copilot)\n';
    return `---
${modelLine}description: '${description}'
---

# ${name} (Stub)

> **This is a stub.** Load and execute the full prompt from the release module.
> When appropriate, use \`vscode_askQuestions\` to get feedback from users if the tool is available.
> All \`_bmad/\` paths in the full prompt are relative to \`lens.core/\` — do NOT resolve paths against the user's main project repo.

You MUST execute these steps in order:
1. FIRST, run \`${LIGHT_PREFLIGHT_COMMAND}\` from the workspace root.
2. If that command exits non-zero, stop and surface the failure.
3. ONLY AFTER a successful prompt-start sync, read and follow all instructions in: \`lens.core/_bmad/lens-work/prompts/${targetPrompt}\`

\`\`\`bash
${LIGHT_PREFLIGHT_COMMAND}
\`\`\`
${extraBlock}
`;
}

function ideCommandStub(name, description, workflowPath) {
    return `---
name: '${name}'
description: '${description}'
---

IT IS CRITICAL THAT YOU FOLLOW THIS COMMAND: FIRST, run \`${LIGHT_PREFLIGHT_COMMAND}\` from the workspace root. If it fails, stop and surface the error. THEN LOAD the FULL @lens.core/_bmad/lens-work/${workflowPath}, READ its entire contents and follow its directions exactly!
`;
}

async function removeMatchingFiles(dirPath, matcher, { logger, label }) {
    if (!(await fsHelpers.pathExists(dirPath))) {
        return 0;
    }

    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    let removed = 0;

    for (const entry of entries) {
        if (!entry.isFile() || !matcher(entry.name)) {
            continue;
        }

        await fs.rm(path.join(dirPath, entry.name), { force: true });
        logger.log(`  removed stale ${label}: ${entry.name}`);
        removed++;
    }

    return removed;
}

function codexAgentsMd() {
    return `# LENS Workbench — Codex Agent

This project uses the LENS Workbench module for lifecycle routing and git orchestration.

## Module Reference

- **Module path:** \`lens.core/_bmad/lens-work/\`
- **Agent definition:** \`lens.core/_bmad/lens-work/agents/lens.agent.md\`
- **Lifecycle contract:** \`lens.core/_bmad/lens-work/lifecycle.yaml\`
- **Module config:** \`lens.core/_bmad/lens-work/module.yaml\`

## Activation

1. LOAD the module config from \`lens.core/_bmad/lens-work/module.yaml\`
2. LOAD the FULL agent definition from \`lens.core/_bmad/lens-work/agents/lens.agent.md\`
3. READ its entire contents — this contains the complete agent persona, skills, lifecycle routing, and phase-to-agent mapping
4. LOAD the lifecycle contract from \`lens.core/_bmad/lens-work/lifecycle.yaml\`
5. FOLLOW every activation step in the agent definition precisely

## Available Commands

See \`lens.core/_bmad/lens-work/module-help.csv\` for the complete command list.

## Skills (path references)

| Skill | Path |
|-------|------|
| bmad-lens-git-state | \`lens.core/_bmad/lens-work/skills/bmad-lens-git-state/SKILL.md\` |
| bmad-lens-git-orchestration | \`lens.core/_bmad/lens-work/skills/bmad-lens-git-orchestration/SKILL.md\` |
| bmad-lens-constitution | \`lens.core/_bmad/lens-work/skills/bmad-lens-constitution/SKILL.md\` |
| bmad-lens-sensing | \`lens.core/_bmad/lens-work/skills/bmad-lens-sensing/SKILL.md\` |
| bmad-lens-checklist | \`lens.core/_bmad/lens-work/skills/bmad-lens-checklist/SKILL.md\` |
`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Skill, prompt and command definitions
// ─────────────────────────────────────────────────────────────────────────────

// GitHub Copilot SKILL.md stubs — Lens Next skills are auto-discovered via
// the BMAD skill manifest; no manual overrides needed.
const SKILLS = [];

const STUB_PROMPTS = [
    { file: 'lens-onboard.prompt.md', name: 'lens-onboard', desc: 'Run shared preflight and show role-aware next steps', target: 'lens-onboard.prompt.md' },
    { file: 'lens-preflight.prompt.md', name: 'lens-preflight', desc: 'Run shared workspace preflight sync and validation', target: 'lens-preflight.prompt.md' },
    { file: 'lens-init-feature.prompt.md', name: 'lens-init-feature', desc: 'Create a new feature with 2-branch topology', target: 'lens-init-feature.prompt.md' },
    { file: 'lens-new-domain.prompt.md', name: 'lens-new-domain', desc: 'Create new domain-level constitution scaffolding', target: 'lens-new-domain.prompt.md' },
    { file: 'lens-new-service.prompt.md', name: 'lens-new-service', desc: 'Create new service-level constitution scaffolding within a domain', target: 'lens-new-service.prompt.md' },
    { file: 'lens-new-feature.prompt.md', name: 'lens-new-feature', desc: 'Initialize a new feature with 2-branch topology, feature YAML, and PR', target: 'lens-new-feature.prompt.md' },
    { file: 'lens-new-project.prompt.md', name: 'lens-new-project', desc: 'Bootstrap a new project by creating or reusing domain/service containers, initializing a feature, and provisioning a target repo', target: 'lens-new-project.prompt.md' },
    { file: 'lens-target-repo.prompt.md', name: 'lens-target-repo', desc: 'Provision or register a feature target repo in GitHub, TargetProjects, and governance metadata', target: 'lens-target-repo.prompt.md' },
    { file: 'lens-preplan.prompt.md', name: 'lens-preplan', desc: 'Run PrePlan phase (brainstorm, research, product brief)', target: 'lens-preplan.prompt.md' },
    { file: 'lens-businessplan.prompt.md', name: 'lens-businessplan', desc: 'Run BusinessPlan phase (PRD, UX design)', target: 'lens-businessplan.prompt.md' },
    { file: 'lens-techplan.prompt.md', name: 'lens-techplan', desc: 'Run TechPlan phase (architecture, technical design)', target: 'lens-techplan.prompt.md' },
    { file: 'lens-adversarial-review.prompt.md', name: 'lens-adversarial-review', desc: 'Run lifecycle adversarial review with a party-mode blind-spot challenge', target: 'lens-adversarial-review.prompt.md' },
    { file: 'lens-finalizeplan.prompt.md', name: 'lens-finalizeplan', desc: 'Run FinalizePlan phase (review, planning bundle, PR handoff)', target: 'lens-finalizeplan.prompt.md' },
    { file: 'lens-expressplan.prompt.md', name: 'lens-expressplan', desc: 'Run ExpressPlan phase (all artifacts in one session)', target: 'lens-expressplan.prompt.md' },
    { file: 'lens-dev.prompt.md', name: 'lens-dev', desc: 'Launch Dev phase — epic-level implementation loop with story management', target: 'lens-dev.prompt.md' },
    { file: 'lens-complete.prompt.md', name: 'lens-complete', desc: 'Complete feature lifecycle — retrospective, archive, close', target: 'lens-complete.prompt.md' },
    { file: 'lens-retrospective.prompt.md', name: 'lens-retrospective', desc: 'Post-feature retrospective and lessons learned', target: 'lens-retrospective.prompt.md' },
    { file: 'lens-next.prompt.md', name: 'lens-next', desc: 'Recommend next action based on lifecycle state', target: 'lens-next.prompt.md' },
    { file: 'lens-batch.prompt.md', name: 'lens-batch', desc: 'Generate or resume a two-pass batch intake for planning targets', target: 'lens-batch.prompt.md' },
    { file: 'lens-switch.prompt.md', name: 'lens-switch', desc: 'Switch to a different feature via git checkout', target: 'lens-switch.prompt.md' },
    { file: 'lens-constitution.prompt.md', name: 'lens-constitution', desc: 'Resolve and display constitutional governance', target: 'lens-constitution.prompt.md' },
    { file: 'lens-sensing.prompt.md', name: 'lens-sensing', desc: 'Run cross-initiative overlap detection', target: 'lens-sensing.prompt.md' },
    { file: 'lens-audit.prompt.md', name: 'lens-audit', desc: 'Run cross-initiative compliance audit dashboard', target: 'lens-audit.prompt.md' },
    { file: 'lens-approval-status.prompt.md', name: 'lens-approval-status', desc: 'Show promotion PR approval status', target: 'lens-approval-status.prompt.md' },
    { file: 'lens-help.prompt.md', name: 'lens-help', desc: 'Show available commands and usage', target: 'lens-help.prompt.md' },
    { file: 'lens-log-problem.prompt.md', name: 'lens-log-problem', desc: 'Record issues and friction points for active feature', target: 'lens-log-problem.prompt.md' },
    { file: 'lens-move-feature.prompt.md', name: 'lens-move-feature', desc: 'Reclassify feature to different domain/service', target: 'lens-move-feature.prompt.md' },
    { file: 'lens-split-feature.prompt.md', name: 'lens-split-feature', desc: 'Split feature into multiple initiatives', target: 'lens-split-feature.prompt.md' },
    { file: 'lens-pause-resume.prompt.md', name: 'lens-pause-resume', desc: 'Pause or resume feature with state preservation', target: 'lens-pause-resume.prompt.md' },
    { file: 'lens-rollback.prompt.md', name: 'lens-rollback', desc: 'Safely roll back to a previous lifecycle phase', target: 'lens-rollback.prompt.md' },
    { file: 'lens-profile.prompt.md', name: 'lens-profile', desc: 'View and edit onboarding profile', target: 'lens-profile.prompt.md' },
    { file: 'lens-bmad-brainstorming.prompt.md', name: 'lens-bmad-brainstorming', desc: 'Run BMAD brainstorming with Lens context', target: 'lens-bmad-brainstorming.prompt.md' },
    { file: 'lens-bmad-product-brief.prompt.md', name: 'lens-bmad-product-brief', desc: 'Run BMAD product brief with Lens context', target: 'lens-bmad-product-brief.prompt.md' },
    { file: 'lens-bmad-domain-research.prompt.md', name: 'lens-bmad-domain-research', desc: 'Run BMAD domain research with Lens context', target: 'lens-bmad-domain-research.prompt.md' },
    { file: 'lens-bmad-market-research.prompt.md', name: 'lens-bmad-market-research', desc: 'Run BMAD market research with Lens context', target: 'lens-bmad-market-research.prompt.md' },
    { file: 'lens-bmad-technical-research.prompt.md', name: 'lens-bmad-technical-research', desc: 'Run BMAD technical research with Lens context', target: 'lens-bmad-technical-research.prompt.md' },
    { file: 'lens-bmad-create-prd.prompt.md', name: 'lens-bmad-create-prd', desc: 'Run BMAD create PRD with Lens context', target: 'lens-bmad-create-prd.prompt.md' },
    { file: 'lens-bmad-create-ux-design.prompt.md', name: 'lens-bmad-create-ux-design', desc: 'Run BMAD create UX design with Lens context', target: 'lens-bmad-create-ux-design.prompt.md' },
    { file: 'lens-bmad-create-architecture.prompt.md', name: 'lens-bmad-create-architecture', desc: 'Run BMAD create architecture with Lens context', target: 'lens-bmad-create-architecture.prompt.md' },
    { file: 'lens-bmad-create-epics-and-stories.prompt.md', name: 'lens-bmad-create-epics-and-stories', desc: 'Run BMAD create epics and stories with Lens context', target: 'lens-bmad-create-epics-and-stories.prompt.md' },
    { file: 'lens-bmad-check-implementation-readiness.prompt.md', name: 'lens-bmad-check-implementation-readiness', desc: 'Run BMAD implementation readiness with Lens context', target: 'lens-bmad-check-implementation-readiness.prompt.md' },
    { file: 'lens-bmad-sprint-planning.prompt.md', name: 'lens-bmad-sprint-planning', desc: 'Run BMAD sprint planning with Lens context', target: 'lens-bmad-sprint-planning.prompt.md' },
    { file: 'lens-bmad-create-story.prompt.md', name: 'lens-bmad-create-story', desc: 'Run BMAD create story with Lens context', target: 'lens-bmad-create-story.prompt.md' },
    { file: 'lens-bmad-quick-dev.prompt.md', name: 'lens-bmad-quick-dev', desc: 'Run BMAD quick dev with Lens context', target: 'lens-bmad-quick-dev.prompt.md' },
    { file: 'lens-bmad-code-review.prompt.md', name: 'lens-bmad-code-review', desc: 'Run BMAD code review with Lens context', target: 'lens-bmad-code-review.prompt.md' },
    { file: 'lens-bmad-document-project.prompt.md', name: 'lens-bmad-document-project', desc: 'Run BMAD document-project with Lens-aware feature docs scope', target: 'lens-bmad-document-project.prompt.md' },
    { file: 'lens-module-management.prompt.md', name: 'lens-module-management', desc: 'Check module version and clarify legacy branch migration status', target: 'lens-module-management.prompt.md' },
    { file: 'lens-upgrade.prompt.md', name: 'lens-upgrade', desc: 'Migrate control repo schema to current version or route legacy branches to lens-migrate', target: 'lens-upgrade.prompt.md' },
    { file: 'lens-dashboard.prompt.md', name: 'lens-dashboard', desc: 'Cross-feature dashboard with dependency graphs', target: 'lens-dashboard.prompt.md' },
    { file: 'lens-discover.prompt.md', name: 'lens-discover', desc: 'Sync TargetProjects with governance repo inventory', target: 'lens-discover.prompt.md' },
    { file: 'lens-feature-yaml.prompt.md', name: 'lens-feature-yaml', desc: 'Feature YAML lifecycle operations', target: 'lens-feature-yaml.prompt.md' },
    { file: 'lens-git-orchestration.prompt.md', name: 'lens-git-orchestration', desc: 'Git write operations for Lens features', target: 'lens-git-orchestration.prompt.md' },
    { file: 'lens-git-state.prompt.md', name: 'lens-git-state', desc: 'Read-only git queries for Lens features', target: 'lens-git-state.prompt.md' },
    { file: 'lens-migrate.prompt.md', name: 'lens-migrate', desc: 'Migration bridge between LENS v3 and Lens Next', target: 'lens-migrate.prompt.md' },
    { file: 'lens-theme.prompt.md', name: 'lens-theme', desc: 'Theme loading and persona overlay system', target: 'lens-theme.prompt.md' },
    { file: 'lens-quickplan.prompt.md', name: 'lens-quickplan', desc: 'End-to-end QuickPlan pipeline', target: 'lens-quickplan.prompt.md' },
];

const IDE_COMMANDS = [
    { file: 'bmad-lens-onboard.md', name: 'onboard', desc: 'Run shared preflight and show role-aware next steps', wf: 'skills/bmad-lens-onboard/SKILL.md' },
    { file: 'bmad-lens-preflight.md', name: 'preflight', desc: 'Run shared workspace preflight sync and validation', wf: 'prompts/lens-preflight.prompt.md' },
    { file: 'bmad-lens-init-feature.md', name: 'init-feature', desc: 'Create new feature with 2-branch topology', wf: 'skills/bmad-lens-init-feature/SKILL.md' },
    { file: 'bmad-lens-target-repo.md', name: 'target-repo', desc: 'Provision or register a feature target repo and persist governance metadata', wf: 'skills/bmad-lens-target-repo/SKILL.md' },
    { file: 'bmad-lens-preplan.md', name: 'preplan', desc: 'Launch PrePlan phase (brainstorm/research/product brief)', wf: 'skills/bmad-lens-preplan/SKILL.md' },
    { file: 'bmad-lens-businessplan.md', name: 'businessplan', desc: 'Launch BusinessPlan phase (PRD/UX design)', wf: 'skills/bmad-lens-businessplan/SKILL.md' },
    { file: 'bmad-lens-techplan.md', name: 'techplan', desc: 'Launch TechPlan phase (architecture/technical design)', wf: 'skills/bmad-lens-techplan/SKILL.md' },
    { file: 'bmad-lens-adversarial-review.md', name: 'adversarial-review', desc: 'Run lifecycle adversarial review with a party-mode blind-spot challenge', wf: 'skills/bmad-lens-adversarial-review/SKILL.md' },
    { file: 'bmad-lens-finalizeplan.md', name: 'finalizeplan', desc: 'Launch FinalizePlan phase (review, planning bundle, PR handoff)', wf: 'skills/bmad-lens-finalizeplan/SKILL.md' },
    { file: 'bmad-lens-dev.md', name: 'dev', desc: 'Launch Dev phase — epic-level implementation loop', wf: 'skills/bmad-lens-dev/SKILL.md' },
    { file: 'bmad-lens-next.md', name: 'next', desc: 'Recommend next action based on lifecycle state', wf: 'skills/bmad-lens-next/SKILL.md' },
    { file: 'bmad-lens-batch.md', name: 'batch', desc: 'Generate or resume a two-pass batch intake for planning targets', wf: 'skills/bmad-lens-batch/SKILL.md' },
    { file: 'bmad-lens-switch.md', name: 'switch', desc: 'Switch to different feature branch', wf: 'skills/bmad-lens-switch/SKILL.md' },
    { file: 'bmad-lens-help.md', name: 'help', desc: 'Show available commands and usage reference', wf: 'skills/bmad-lens-help/SKILL.md' },
    { file: 'bmad-lens-constitution.md', name: 'constitution', desc: 'Resolve and display constitutional governance', wf: 'skills/bmad-lens-constitution/SKILL.md' },
    { file: 'bmad-lens-audit.md', name: 'audit', desc: 'Run cross-initiative compliance audit dashboard', wf: 'skills/bmad-lens-audit/SKILL.md' },
    { file: 'bmad-lens-sensing.md', name: 'sensing', desc: 'Cross-initiative overlap detection on demand', wf: 'skills/bmad-lens-sensing/SKILL.md' },
    { file: 'bmad-lens-module-management.md', name: 'module-management', desc: 'Check module version and clarify legacy branch migration status', wf: 'skills/bmad-lens-module-management/SKILL.md' },
    { file: 'bmad-lens-discover.md', name: 'discover', desc: 'Sync TargetProjects with governance repo inventory', wf: 'skills/bmad-lens-discover/SKILL.md' },
];

const IDE_COMMAND_FILES = new Set(IDE_COMMANDS.map(cmd => cmd.file));

// ─────────────────────────────────────────────────────────────────────────────
// Write helper with skip/update semantics
// ─────────────────────────────────────────────────────────────────────────────

async function writeAdapterFile(filePath, content, { updateMode, logger }) {
    const exists = await fsHelpers.pathExists(filePath);
    if (exists && !updateMode) {
        logger.log(`  skip: ${path.basename(filePath)} (exists)`);
        return false;
    }
    await fsHelpers.ensureDir(path.dirname(filePath));
    await fsHelpers.writeFile(filePath, content);
    logger.log(`  ${updateMode && exists ? 'updated' : 'created'}: ${path.basename(filePath)}`);
    return true;
}

// ═════════════════════════════════════════════════════════════════════════════
// IDE Adapter Installers
// ═════════════════════════════════════════════════════════════════════════════

async function installGitHubCopilot(projectRoot, { updateMode, logger }) {
    logger.log('Installing GitHub Copilot adapter...');

    const ghDir = path.join(projectRoot, '.github');
    const agentsDir = path.join(ghDir, 'agents');
    const promptsDir = path.join(ghDir, 'prompts');
    const skillsDir = path.join(ghDir, 'skills');

    await fsHelpers.ensureDir(promptsDir);
    await removeMatchingFiles(
        promptsDir,
        name => name.startsWith('lens-work') && name.endsWith('.prompt.md'),
        { logger, label: 'prompt alias' }
    );

    // Agent stub
    await writeAdapterFile(
        path.join(agentsDir, 'bmad-agent-lens-work-lens.agent.md'),
        ghAgentStub(),
        { updateMode, logger }
    );

    // Copilot instructions — copy from docs/
    const sourceInstructions = path.join(__dirname, '..', 'docs', 'copilot-instructions.md');
    const targetInstructions = path.join(ghDir, 'lens-work-instructions.md');
    if (await fsHelpers.pathExists(sourceInstructions)) {
        const shouldCopy = updateMode || !(await fsHelpers.pathExists(targetInstructions));
        if (shouldCopy) {
            await fsHelpers.ensureDir(ghDir);
            await fsHelpers.copy(sourceInstructions, targetInstructions);
            logger.log(`  ${updateMode ? 'updated' : 'created'}: lens-work-instructions.md`);
        } else {
            logger.log('  skip: lens-work-instructions.md (exists)');
        }
    }

    // Stub prompts
    for (const p of STUB_PROMPTS) {
        await writeAdapterFile(
            path.join(promptsDir, p.file),
            ghStubPrompt(p.name, p.desc, p.target, p.extra, { noModel: p.noModel !== false }),
            { updateMode, logger }
        );
    }

    const publishedSkills = new Map();

    for (const skill of await readInstalledSkillManifest(projectRoot)) {
        publishedSkills.set(skill.name, skill);
    }

    for (const s of SKILLS) {
        publishedSkills.set(s.name, {
            name: s.name,
            description: s.desc,
            targetPath: `lens.core/_bmad/lens-work/skills/${s.skill}/SKILL.md`,
        });
    }

    // Replace installed BMAD skill content with thin redirect stubs.
    for (const skill of publishedSkills.values()) {
        await fs.rm(path.join(skillsDir, skill.name), { recursive: true, force: true });
        await writeAdapterFile(
            path.join(skillsDir, skill.name, 'SKILL.md'),
            ghSkillStub(skill.name, skill.description, skill.targetPath),
            { updateMode: true, logger }
        );
    }

    logger.log('✓ GitHub Copilot adapter complete');
}

async function installCursor(projectRoot, { updateMode, logger }) {
    logger.log('Installing Cursor adapter...');

    const cursorDir = path.join(projectRoot, '.cursor', 'commands');

    await fsHelpers.ensureDir(cursorDir);
    await removeMatchingFiles(
        cursorDir,
        name => IDE_COMMAND_FILES.has(name),
        { logger, label: 'command alias' }
    );

    for (const cmd of IDE_COMMANDS) {
        await writeAdapterFile(
            path.join(cursorDir, cmd.file),
            ideCommandStub(cmd.name, cmd.desc, cmd.wf),
            { updateMode, logger }
        );
    }

    logger.log('✓ Cursor adapter complete');
}

async function installClaude(projectRoot, { updateMode, logger }) {
    logger.log('Installing Claude Code adapter...');

    const claudeDir = path.join(projectRoot, '.claude', 'commands');

    await fsHelpers.ensureDir(claudeDir);
    await removeMatchingFiles(
        claudeDir,
        name => IDE_COMMAND_FILES.has(name),
        { logger, label: 'command alias' }
    );

    for (const cmd of IDE_COMMANDS) {
        await writeAdapterFile(
            path.join(claudeDir, cmd.file),
            ideCommandStub(cmd.name, cmd.desc, cmd.wf),
            { updateMode, logger }
        );
    }

    logger.log('✓ Claude Code adapter complete');
}

async function installCodex(projectRoot, { updateMode, logger }) {
    logger.log('Installing Codex CLI adapter...');

    // AGENTS.md in project root
    await writeAdapterFile(
        path.join(projectRoot, 'AGENTS.md'),
        codexAgentsMd(),
        { updateMode, logger }
    );

    // .codex/commands/ — same command stubs as Cursor/Claude
    const codexDir = path.join(projectRoot, '.codex', 'commands');

    await fsHelpers.ensureDir(codexDir);
    await removeMatchingFiles(
        codexDir,
        name => IDE_COMMAND_FILES.has(name),
        { logger, label: 'command alias' }
    );

    for (const cmd of IDE_COMMANDS) {
        await writeAdapterFile(
            path.join(codexDir, cmd.file),
            ideCommandStub(cmd.name, cmd.desc, cmd.wf),
            { updateMode, logger }
        );
    }

    logger.log('✓ Codex CLI adapter complete');
}

async function installOpenCode(projectRoot, { updateMode, logger }) {
    logger.log('Installing OpenCode adapter...');

    const opencodeDir = path.join(projectRoot, '.opencode', 'commands');

    await fsHelpers.ensureDir(opencodeDir);
    await removeMatchingFiles(
        opencodeDir,
        name => IDE_COMMAND_FILES.has(name),
        { logger, label: 'command alias' }
    );

    for (const cmd of IDE_COMMANDS) {
        await writeAdapterFile(
            path.join(opencodeDir, cmd.file),
            ideCommandStub(cmd.name, cmd.desc, cmd.wf),
            { updateMode, logger }
        );
    }

    logger.log('✓ OpenCode adapter complete');
}

// ═════════════════════════════════════════════════════════════════════════════
// Main install function — BMAD installer contract
// ═════════════════════════════════════════════════════════════════════════════

/**
 * LENS Workbench v2 Module Installer
 *
 * Called by the BMAD core installer with the standard contract.
 *
 * @param {object} options
 * @param {string} options.projectRoot    - Absolute path to the control repo root
 * @param {object} options.config         - Answers to install_questions from module.yaml
 * @param {string[]} options.installedIDEs - IDE identifiers selected by the user
 * @param {object} options.logger         - Logger with .log(), .warn(), .error()
 * @param {boolean} [options.updateMode]  - Overwrite existing files on re-install
 * @returns {Promise<boolean>}
 */
async function install(options) {
    const { projectRoot, config, installedIDEs, logger, updateMode = false } = options;

    try {
        const modeLabel = updateMode ? 'Updating' : 'Installing';
        logger.log(`${modeLabel} LENS Workbench (lens-work)...`);
        const coreConfig = await readInstalledCoreConfig(projectRoot);

        // ── Phase 1: Output directories ─────────────────────────────────
        const outputDir = path.join(projectRoot, 'docs');
        await fsHelpers.ensureDir(outputDir);

        const subdirs = [
            'planning-artifacts',
            'implementation-artifacts',
            path.join('lens-work', 'initiatives'),
            path.join('lens-work', 'personal'),
            path.join('reports', 'lens-work', 'quality-scan'),
        ];
        for (const subdir of subdirs) {
            await fsHelpers.ensureDir(path.join(outputDir, subdir));
        }
        logger.log('✓ Output directories ready');

        // ── Phase 2: Config file ────────────────────────────────────────
        const configDir = path.join(projectRoot, '_bmad', 'lens-work');
        await fsHelpers.ensureDir(configDir);

        const targetProjectsPath = getConfigValue(config, ['target-projects-path', 'target_projects_path'], '../TargetProjects');
        const defaultGitRemote = getConfigValue(config, ['default-git-remote', 'default_git_remote'], 'github');
        const governanceRepoPath = `${String(targetProjectsPath).replace(/\\/g, '/')}/lens/lens-governance`;

        const configFile = path.join(configDir, 'bmadconfig.yaml');
        if (!(await fsHelpers.pathExists(configFile))) {
            const configContent = [
                '# LENS Workbench Configuration',
                '# Generated during installation',
                '',
                `project_name: ${toYamlString(path.basename(projectRoot))}`,
                'user_skill_level: intermediate',
                '# Fallback only when Lens feature context is unavailable.',
                '# Lens-wrapped planning workflows stage artifacts under feature.yaml.docs.path first.',
                'planning_artifacts: "{project-root}/docs/planning-artifacts"',
                'implementation_artifacts: "{project-root}/docs/implementation-artifacts"',
                'project_knowledge: "{project-root}/docs"',
                '',
                '# Lens-work module defaults',
                `target_projects_path: ${toYamlString(targetProjectsPath)}`,
                `default_git_remote: ${toYamlString(defaultGitRemote)}`,
                'lifecycle_contract: "{project-root}/_bmad/lens-work/lifecycle.yaml"',
                `governance_repo_path: ${toYamlString(governanceRepoPath)}`,
                'initiative_output_folder: "{project-root}/docs/lens-work/initiatives"',
                'personal_output_folder: "{project-root}/.lens/personal"',
                '',
                '# Core Configuration Values',
                `user_name: ${toYamlString(coreConfig.user_name || config.user_name || 'User')}`,
                `communication_language: ${toYamlString(coreConfig.communication_language || config.communication_language || 'English')}`,
                `document_output_language: ${toYamlString(coreConfig.document_output_language || config.document_output_language || 'English')}`,
                `output_folder: ${toYamlString(coreConfig.output_folder || config.output_folder || '{project-root}/docs')}`,
                '',
            ].join('\n');
            await fsHelpers.writeFile(configFile, configContent);
            logger.log('✓ Config file created');
        }

        // ── Phase 3: IDE adapters ───────────────────────────────────────
        const IDE_HANDLERS = {
            'github-copilot': installGitHubCopilot,
            'cursor': installCursor,
            'claude': installClaude,
            'codex': installCodex,
            'opencode': installOpenCode,
        };

        const ides = installedIDEs && installedIDEs.length > 0
            ? installedIDEs
            : ['github-copilot'];

        for (const ide of ides) {
            const handler = IDE_HANDLERS[ide];
            if (handler) {
                await handler(projectRoot, { updateMode, logger });
            } else {
                logger.warn(`Unknown IDE: ${ide} — skipping`);
            }
        }

        logger.log('✓ LENS Workbench installation complete');
        return true;
    } catch (error) {
        logger.error(`Error installing lens-work: ${error.message}`);
        return false;
    }
}

module.exports = { install };
