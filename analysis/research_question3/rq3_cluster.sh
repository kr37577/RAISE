#!/usr/bin/env bash
# Run the full RQ3 additional-build simulation pipeline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
PYENV_ENV_NAME="py3"
if [[ -x "${PYENV_ROOT}/versions/${PYENV_ENV_NAME}/bin/python" ]]; then
  PYTHON_EXEC="${PYENV_ROOT}/versions/${PYENV_ENV_NAME}/bin/python"
else
  PYTHON_EXEC="$(command -v python3)"
fi
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DATASETS_ROOT="${REPO_ROOT}/datasets"

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH}"
else
  export PYTHONPATH="${REPO_ROOT}"
fi

run_step() {
  local description="$1"
  shift
  echo "==> ${description}"
  "$@"
  echo ""
}

TIMELINE_ARGS=()
if [[ -n "${RQ3_TIMELINE_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  TIMELINE_ARGS=(${RQ3_TIMELINE_ARGS})
fi

SIM_ARGS=()
if [[ -n "${RQ3_SIMULATION_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  SIM_ARGS=(${RQ3_SIMULATION_ARGS})
fi

cd "${SCRIPT_DIR}"

run_step "Generating build timelines" \
  "${PYTHON_EXEC}" "${SCRIPT_DIR}/timeline_cli_wrapper.py" "${TIMELINE_ARGS[@]}"

run_step "Running additional-build simulation" \
  "${PYTHON_EXEC}" "${SCRIPT_DIR}/simulate_additional_builds.py" "${SIM_ARGS[@]}"

echo "RQ3 simulation completed. Outputs are available under: ${DATASETS_ROOT}/derived_artifacts/rq3/simulation_outputs"
