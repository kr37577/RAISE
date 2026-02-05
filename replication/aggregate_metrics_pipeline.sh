#!/usr/bin/env bash
set -euo pipefail

vuljit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

MAPPING_FILE="${VULJIT_PROJECT_MAPPING:-${vuljit_dir}/datasets/derived_artifacts/oss_fuzz_metadata/c_cpp_vulnerability_summary.csv}"
METRICS_DIR="${VULJIT_METRICS_DIR:-${vuljit_dir}/datasets/derived_artifacts/commit_metrics}"
COVERAGE_DIR="${VULJIT_COVERAGE_AGG_DIR:-${vuljit_dir}/datasets/derived_artifacts/coverage_metrics}"
PATCH_COV_DIR="${VULJIT_PATCH_COV_DIR:-${vuljit_dir}/datasets/derived_artifacts/patch_coverage_metrics}"
OUT_DIR="${VULJIT_BASE_DATA_DIR:-${vuljit_dir}/datasets/derived_artifacts/aggregate}"
COVERAGE_LAG_DAYS="${COVERAGE_LAG_DAYS:-0}"

PYTHON_SCRIPT="${vuljit_dir}/scripts/modeling/aggregate_metrics_pipeline.py"

if [[ ! -f "${PYTHON_SCRIPT}" ]]; then
  echo "[error] Python script not found: ${PYTHON_SCRIPT}" >&2
  exit 1
fi

if [[ ! -f "${MAPPING_FILE}" ]]; then
  echo "[error] Mapping file not found: ${MAPPING_FILE}" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

echo "[info] Using mapping file: ${MAPPING_FILE}"
echo "[info] Output dir: ${OUT_DIR}"

# CSV 先頭行はヘッダーを想定
tail -n +2 "${MAPPING_FILE}" | while IFS=, read -r project language main_repo homepage primary_contact vuln_count extra; do
  # 簡易トリム（先頭/末尾のダブルクォートや改行を削除）
  project="${project%$'\r'}"
  project="${project%\"}"
  project="${project#\"}"

  directory_name="${project}"

  if [[ -z "${project}" ]]; then
    continue
  fi

  echo "------------------------------------------------------------------"
  echo "[info] Processing project=${project}"

  "${PYTHON_BIN}" "${PYTHON_SCRIPT}" "${project}" "${directory_name}" \
    --metrics "${METRICS_DIR}" \
    --coverage "${COVERAGE_DIR}" \
    --patch-coverage "${PATCH_COV_DIR}" \
    --coverage-lag-days "${COVERAGE_LAG_DAYS}" \
    --out "${OUT_DIR}"
done

echo "[info] All projects processed."
