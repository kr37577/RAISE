#!/usr/bin/env bash
# Run the full RQ3 additional-build simulation pipeline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DATASETS_ROOT="${REPO_ROOT}/datasets"
PYTHON_BIN="${PYTHON_BIN:-python3}"

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

export PYTHONLOGLEVEL="${PYTHONLOGLEVEL:-INFO}" 
export RQ3_LOG_LEVEL="${RQ3_LOG_LEVEL:-DEBUG}"

run_step "Generating build timelines" \
  "${PYTHON_BIN}" "${SCRIPT_DIR}/timeline_cli_wrapper.py" "${TIMELINE_ARGS[@]}"

run_step "Running additional-build simulation" \
  "${PYTHON_BIN}" "${SCRIPT_DIR}/simulate_additional_builds.py" "${SIM_ARGS[@]}"

echo "RQ3 simulation completed. Outputs are available under: ${DATASETS_ROOT}/derived_artifacts/rq3/simulation_outputs"
