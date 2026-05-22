#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CONTROL_ROOT_DEFAULT="$(cd "${SRC_ROOT}/../../../.." && pwd)"
CONTROL_ROOT="${CONTROL_ROOT:-${CONTROL_ROOT_DEFAULT}}"
LENS_CORE_ROOT="${LENS_CORE_ROOT:-${CONTROL_ROOT}/lens.core}"

FILES=(
  "_bmad/lens-work/agents/lens.agent.yaml"
  "_bmad/lens-work/assets/templates/feature-yaml-template.yaml"
  "_bmad/lens-work/module.yaml"
  "_bmad/lens-work/skills/bmad-lens-init-feature/SKILL.md"
  "_bmad/lens-work/skills/bmad-lens-init-feature/scripts/init-feature-ops.py"
  "_bmad/lens-work/skills/bmad-lens-init-feature/scripts/tests/test-init-feature-ops.py"
  "_bmad/lens-work/skills/bmad-lens-document-project/SKILL.md"
)

if [[ ! -d "${LENS_CORE_ROOT}" ]]; then
  echo "ERROR: lens.core directory not found at: ${LENS_CORE_ROOT}" >&2
  echo "Set LENS_CORE_ROOT or CONTROL_ROOT and retry." >&2
  exit 2
fi

missing=0
diffs=0

for rel in "${FILES[@]}"; do
  src_file="${SRC_ROOT}/${rel}"
  release_file="${LENS_CORE_ROOT}/${rel}"

  if [[ ! -f "${src_file}" ]]; then
    echo "MISSING_IN_SRC ${rel}"
    missing=$((missing + 1))
    continue
  fi

  if [[ ! -f "${release_file}" ]]; then
    echo "MISSING_IN_LENS_CORE ${rel}"
    missing=$((missing + 1))
    continue
  fi

  if cmp -s "${src_file}" "${release_file}"; then
    echo "MATCH ${rel}"
  else
    echo "DIFF ${rel}"
    diffs=$((diffs + 1))
  fi
done

echo "SUMMARY missing=${missing} diffs=${diffs}"

if [[ ${missing} -eq 0 && ${diffs} -eq 0 ]]; then
  exit 0
fi

exit 1
