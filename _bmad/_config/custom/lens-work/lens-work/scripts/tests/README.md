# Script Tests

Unit tests for lens-work Python scripts. Each test file corresponds to a script in the parent directory.

## Running Tests

```bash
# Run all tests (from repo root or lens-work/)
pytest scripts/tests/ -v

# Run a single test file
pytest scripts/tests/test-create-pr.py -v
```

> **Requirements:** `pip install pytest` or `uv add pytest`

## Test Files

| Test | Script Under Test |
|------|-------------------|
| `test-create-pr.py` | `uv run create-pr.py` |
| `test-batch-mode-contracts.py` | Static contract checks for `/batch` publication and two-pass batch behavior |
| `test-install.py` | `uv run install.py` |
| `test-light-preflight.py` | `uv run light-preflight.py` |
| `test-phase-conductor-contracts.py` | Static contract checks for interactive planning handoffs |
| `test-preflight.py` | `uv run preflight.py` |
| `test-setup-control-repo.py` | `uv run setup-control-repo.py` |
| `test-store-github-pat.py` | `uv run store-github-pat.py` |
