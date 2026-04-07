#!/usr/bin/env bash
# Canonical thesis batch runner: all EMS presets -> results_final/
#
# For each EMS preset runs BOTH:
#   - main grid (density × acceptance)
#   - travel grid (density × travel friction)
#
# Watch progress:
#   python thesis_tools/watch_thesis_progress.py
#
# Usage:
#   bash thesis_tools/run_all_thesis_parallel_all_ems_results_final.sh
#   NUM_RUNS=500 RUN_TRAVEL=1 RUN_PLOTS=1 bash thesis_tools/run_all_thesis_parallel_all_ems_results_final.sh

set -euo pipefail

NUM_RUNS="${NUM_RUNS:-1000}"
PYTHON_BIN="${PYTHON_BIN:-python}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"
RUN_TRAVEL="${RUN_TRAVEL:-1}"
RUN_PLOTS="${RUN_PLOTS:-0}"
RETRIES="${RETRIES:-3}"
BATCH_BY_DENSITY="${BATCH_BY_DENSITY:-1}"
MAX_JOBS="${MAX_JOBS:-2}"

EMS_PRESETS=("5_10")
RESULTS_ROOT_NAME="${RESULTS_ROOT_NAME:-results_final}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/${RESULTS_ROOT_NAME}/logs"
mkdir -p "${LOG_DIR}"

wait_for_slot() {
  while [ "$(jobs -rp | wc -l)" -ge "${MAX_JOBS}" ]; do
    sleep 1
  done
}

run_slice() {
  local mode="$1"
  local env="$2"
  local density="${3:-}"
  local logf out_csv
  local extra_args=()

  if [ -n "${density}" ]; then
    logf="${LOG_DIR}/thesis_${mode}_${env}_${density}_${LOG_SUFFIX}.log"
    out_csv="${RESULTS_FOLDER}/thesis_${mode}_${env}_${density}.csv"
    extra_args=(--density "${density}")
  else
    logf="${LOG_DIR}/thesis_${mode}_${env}_${LOG_SUFFIX}.log"
    out_csv="${RESULTS_FOLDER}/thesis_${mode}_${env}.csv"
  fi

  local skip_args=()
  if [ "${SKIP_EXISTING}" = "1" ]; then
    if [ -s "${out_csv}" ] && [ "$(wc -c < "${out_csv}")" -gt 100 ]; then
      echo "Skipping existing: ${out_csv}"
      return 0
    fi
    skip_args=(--skip-existing)
  fi

  echo "Starting thesis_${mode}_${env}${density:+_${density}} -> ${logf}"
  (
    cd "${ROOT_DIR}"
    "${PYTHON_BIN}" thesis_tools/run_thesis_slice.py \
      --environment "${env}" \
      --mode "${mode}" \
      --num-runs "${NUM_RUNS}" \
      --results-folder "${RESULTS_FOLDER}" \
      "${extra_args[@]}" \
      "${skip_args[@]}"
  ) >"${logf}" 2>&1
}

run_mode_parallel() {
  local mode="$1"
  local pids=()
  local envs=("urban" "rural")

  if [ "${BATCH_BY_DENSITY}" = "1" ]; then
    local dens env
    for dens in low mid_low medium mid_high high; do
      for env in "${envs[@]}"; do
        wait_for_slot
        run_slice "${mode}" "${env}" "${dens}" &
        pids+=("$!")
      done
    done
  else
    local env
    for env in "${envs[@]}"; do
      wait_for_slot
      run_slice "${mode}" "${env}" &
      pids+=("$!")
    done
  fi

  local failed=0 pid
  for pid in "${pids[@]}"; do
    if ! wait "${pid}"; then
      failed=$((failed + 1))
    fi
  done
  return "${failed}"
}

run_mode_with_retries() {
  local mode="$1"
  local attempt=0
  while true; do
    attempt=$((attempt + 1))
    echo "=== ${mode^} grid (mode=${mode}), attempt ${attempt} [EMS=${THESIS_EMS_PRESET}] ==="
    if run_mode_parallel "${mode}"; then
      echo "${mode^} grid slices OK."
      return 0
    fi
    echo "Some ${mode} jobs failed (see ${LOG_DIR}/thesis_${mode}_*_${LOG_SUFFIX}.log)."
    if [ "${attempt}" -ge "${RETRIES}" ]; then
      echo "Give up on ${mode} after ${RETRIES} attempt(s)."
      return 1
    fi
    sleep 2
  done
}

for ems_preset in "${EMS_PRESETS[@]}"; do
  export THESIS_EMS_PRESET="${ems_preset}"
  RESULTS_SUBDIR="${RESULTS_ROOT_NAME}/thesis_archetype_grid_ems${ems_preset}"
  RESULTS_FOLDER="${ROOT_DIR}/${RESULTS_SUBDIR}"
  mkdir -p "${RESULTS_FOLDER}"
  LOG_SUFFIX="ems${ems_preset//_/}"

  if [ "${RUN_TRAVEL}" = "1" ]; then
    run_mode_with_retries "main" &
    pid_main=$!
    run_mode_with_retries "travel" &
    pid_travel=$!
    wait "${pid_main}" && wait "${pid_travel}"
  else
    run_mode_with_retries "main"
  fi
done

if [ "${RUN_PLOTS}" = "1" ]; then
  for ems_preset in "${EMS_PRESETS[@]}"; do
    (
      cd "${ROOT_DIR}"
      "${PYTHON_BIN}" thesis_tools/generate_slides_plots.py \
        --results-root "${RESULTS_ROOT_NAME}" \
        --thesis-subdir "thesis_archetype_grid_ems${ems_preset}" \
        --ems-preset "${ems_preset}" \
        --mode both
    )
  done
fi
