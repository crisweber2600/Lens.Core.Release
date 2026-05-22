"""Tests for install.py."""
import importlib.util
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "install.py"


def _run(*args, **kwargs):
    return subprocess.run(
        ["uv", "run", "--script", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        **kwargs,
    )


def _load_script_module():
    spec = importlib.util.spec_from_file_location("install_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestHelpFlag:
    def test_help_exits_zero(self):
        result = _run("--help")
        assert result.returncode == 0, f"--help should exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_help_shows_ide_flag(self):
        result = _run("--help")
        combined = result.stdout + result.stderr
        assert "--ide" in combined

    def test_help_shows_dry_run(self):
        result = _run("--help")
        combined = result.stdout + result.stderr
        assert "dry-run" in combined or "dry_run" in combined

    def test_help_mentions_opencode(self):
        result = _run("--help")
        combined = result.stdout + result.stderr
        assert "opencode" in combined


class TestArgumentParsing:
    def test_invalid_ide_exits_nonzero(self):
        result = _run("--ide", "not-a-real-ide")
        assert result.returncode != 0

    def test_dry_run_flag_accepted(self):
        result = _run("--dry-run")
        assert result.returncode == 0


class TestOutputDirs:
    def test_install_output_dirs_creates_personal_folder(self, tmp_path):
        module = _load_script_module()
        module._project_root = tmp_path
        module._dry_run = False

        module.install_output_dirs()

        assert (tmp_path / ".lens").is_dir()
        assert (tmp_path / ".lens/personal").is_dir()
        assert not (tmp_path / "docs/lens-work/personal").exists()


class TestGeneratedAdapters:
    def test_github_copilot_generation_includes_discover_and_quickplan_prompts(self, tmp_path):
        module = _load_script_module()
        module._project_root = tmp_path
        module._dry_run = False
        module._update = False

        module.install_github_copilot()

        discover_prompt = tmp_path / ".github/prompts/lens-discover.prompt.md"
        quickplan_prompt = tmp_path / ".github/prompts/lens-quickplan.prompt.md"
        status_prompt = tmp_path / ".github/prompts/lens-status.prompt.md"

        assert discover_prompt.is_file()
        assert quickplan_prompt.is_file()
        assert not status_prompt.exists()
        discover_prompt_text = discover_prompt.read_text(encoding="utf-8")
        quickplan_prompt_text = quickplan_prompt.read_text(encoding="utf-8")

        assert "light-preflight.py" in discover_prompt_text
        assert "You MUST execute these steps in order:" in discover_prompt_text
        assert "FIRST, run `uv run ./lens.core/_bmad/lens-work/scripts/light-preflight.py`" in discover_prompt_text
        assert "ONLY AFTER a successful prompt-start sync" in discover_prompt_text
        assert "lens.core/_bmad/lens-work/prompts/lens-discover.prompt.md" in discover_prompt_text
        assert "lens.core/_bmad/lens-work/prompts/lens-quickplan.prompt.md" in quickplan_prompt_text

    def test_cursor_generation_includes_discover_command(self, tmp_path):
        module = _load_script_module()
        module._project_root = tmp_path
        module._dry_run = False
        module._update = False

        module.install_cursor()

        discover_command = tmp_path / ".cursor/commands/bmad-lens-discover.md"
        status_command = tmp_path / ".cursor/commands/bmad-lens-status.md"

        assert discover_command.is_file()
        assert not status_command.exists()
        assert "light-preflight.py" in discover_command.read_text(encoding="utf-8")
        assert "skills/bmad-lens-discover/SKILL.md" in discover_command.read_text(encoding="utf-8")

    def test_javascript_installer_mentions_light_preflight(self):
        installer = (SCRIPT.parent.parent / "_module-installer" / "installer.js").read_text(encoding="utf-8")

        assert "light-preflight.py" in installer
        assert "LIGHT_PREFLIGHT_COMMAND" in installer
        assert "You MUST execute these steps in order:" in installer
        assert "ONLY AFTER a successful prompt-start sync" in installer
        assert "FIRST, run \\`${LIGHT_PREFLIGHT_COMMAND}\\`" in installer

    def test_all_source_managed_prompt_stubs_include_shared_preflight_template(self):
        prompts_dir = SCRIPT.parents[3] / ".github/prompts"
        prompt_files = sorted(prompts_dir.glob("*.prompt.md"))

        assert prompt_files, "expected source-managed GitHub prompt stubs"

        for prompt_file in prompt_files:
            prompt_text = prompt_file.read_text(encoding="utf-8")

            assert "light-preflight.py" in prompt_text, prompt_file.name
            assert "You MUST execute these steps in order:" in prompt_text, prompt_file.name
            assert "FIRST, run `uv run ./lens.core/_bmad/lens-work/scripts/light-preflight.py`" in prompt_text, prompt_file.name
            assert "ONLY AFTER a successful prompt-start sync" in prompt_text, prompt_file.name
            assert "vscode_askQuestions" in prompt_text, prompt_file.name
            assert f"lens.core/_bmad/lens-work/prompts/{prompt_file.name}" in prompt_text, prompt_file.name

    def test_source_managed_lens_switch_prompt_includes_light_preflight(self):
        source_prompt = SCRIPT.parents[3] / ".github/prompts/lens-switch.prompt.md"
        prompt_text = source_prompt.read_text(encoding="utf-8")

        assert "light-preflight.py" in prompt_text
        assert "You MUST execute these steps in order:" in prompt_text
        assert "FIRST, run `uv run ./lens.core/_bmad/lens-work/scripts/light-preflight.py`" in prompt_text
        assert "ONLY AFTER a successful prompt-start sync" in prompt_text
        assert "vscode_askQuestions" in prompt_text
        assert "lens.core/_bmad/lens-work/prompts/lens-switch.prompt.md" in prompt_text

    def test_release_lens_switch_prompt_controls_menu_execution(self):
        release_prompt = SCRIPT.parent.parent / "prompts/lens-switch.prompt.md"
        prompt_text = release_prompt.read_text(encoding="utf-8")

        assert "Use this prompt as the entry controller for `/lens-switch`." in prompt_text
        assert "If not, run that command now from the workspace root." in prompt_text
        assert "Do not resolve config paths or execute `switch-ops.py` until the shared prompt-start sync has succeeded." in prompt_text
        assert "Missing config is normal. Do not search the workspace" in prompt_text
        assert "If `vscode_askQuestions` is not available, render the numbered menu and STOP." in prompt_text
        assert "Do not infer a target from the current branch" in prompt_text
        assert "uv run --script {project-root}/{release_repo_root}/_bmad/lens-work/skills/bmad-lens-switch/scripts/switch-ops.py" in prompt_text

    def test_promote_workflow_validates_source_managed_prompt_stubs(self):
        workflow = (SCRIPT.parents[3] / ".github/workflows/promote-to-release.yml").read_text(encoding="utf-8")

        assert "Published prompt file differs from source" in workflow
        assert "Source prompt missing shared preflight template" in workflow
        assert "must require running preflight before loading the release prompt" in workflow
        assert "must block release-prompt loading until preflight succeeds" in workflow
        assert "Source prompt missing question-tool guidance" in workflow
        assert "Source prompt delegates to the wrong release prompt" in workflow


# TODO: Test ensure_dir creates directories
# TODO: Test write_file respects --update flag
