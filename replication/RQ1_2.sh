#!/usr/bin/env bash
# Run RQ1/2 analyses locally (no Slurm) by calling the two Python scripts in sequence.
set -euo pipefail

vuljit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

analysis_dir="${vuljit_dir}/analysis/research_question1_2"
SCRIPT_COMPARISON="${analysis_dir}/analyze_comparison.py"
SCRIPT_TRENDS="${analysis_dir}/analyze_trends_comparison.py"

if [[ ! -f "${SCRIPT_COMPARISON}" || ! -f "${SCRIPT_TRENDS}" ]]; then
  echo "[error] analysis scripts not found under ${analysis_dir}" >&2
  exit 1
fi

echo "[info] Running analyze_comparison.py"
"${PYTHON_BIN}" "${SCRIPT_COMPARISON}"

echo "---------------------------------"
echo "[info] Running analyze_trends_comparison.py"
"${PYTHON_BIN}" "${SCRIPT_TRENDS}"

echo "---------------------------------"
echo "[info] RQ1/2 analyses completed."
