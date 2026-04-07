#!/usr/bin/env bash
# Full thesis batch: all EMS presets (10/15, 15/20, 5/10) → results_final/
#
# For each EMS preset runs BOTH:
#   - main grid (density × acceptance)
#   - travel grid (density × travel friction)
#
# Slices are written under:
#   results_final/thesis_archetype_grid_ems<EMS_PRESET>/
#
# Requires THESIS_EMS_PRESET in format_outputs/experiment_grid.py (imported by run_thesis_slice).
#
# Optional: after simulations, generate slide figures per preset (RUN_PLOTS=1).
#
# Watch live progress (separate terminal; default logs dir is results_final/logs):
#   python format_outputs/watch_thesis_progress.py
#
# Usage (from repo root, Git Bash / WSL / Linux / macOS):
#   bash format_outputs/run_all_thesis_parallel_all_ems_results_final.sh
#
#   NUM_RUNS=500 RUN_TRAVEL=1 RUN_PLOTS=1 bash format_outputs/run_all_thesis_parallel_all_ems_results_final.sh
#
# Environment:
#   NUM_RUNS       — Monte Carlo replications per scenario cell (default: 1000)
#   SKIP_EXISTING  — 1 = skip slice CSV if already present (default: 1)
#   RUN_TRAVEL     — 1 = run travel grid too (default: 1)
#   RUN_PLOTS      — 0 = after all EMS runs, run generate_slides_plots.py per preset (default: 0)
#   RETRIES, BATCH_BY_DENSITY, MAX_JOBS — same as run_all_thesis_parallel_all_ems.sh

set -euo pipefail

NUM_RUNS="${NUM_RUNS:-1000}"
PYTHON_BIN="${PYTHON_BIN:-python}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"
RUN_TRAVEL="${RUN_TRAVEL:-1}"
RUN_PLOTS="${RUN_PLOTS:-0}"
RETRIES="${RETRIES:-3}"
BATCH_BY_DENSITY="${BATCH_BY_DENSITY:-1}"
MAX_JOBS="${MAX_JOBS:-2}"

# All EMS presets
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
  local logf
  local out_csv
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
    # Skip from the bash layer too (same rule as run_thesis_slice.py: file exists and non-trivial size).
    if [ -s "${out_csv}" ] && [ "$(wc -c < "${out_csv}")" -gt 100 ]; then
      echo "Skipping existing: ${out_csv}"
      return 0
    fi
    skip_args=(--skip-existing)
  fi

  echo "Starting thesis_${mode}_${env}${density:+_${density}} -> ${logf}"
  (
    cd "${ROOT_DIR}"
    "${PYTHON_BIN}" format_outputs/run_thesis_slice.py \
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
    local dens
    local env
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

  local failed=0
  local pid
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
      echo "Give up on ${mode} after ${RETRIES} attempt(s). Fix errors and re-run."
      return 1
    fi

    echo "Retrying failed ${mode} slices only (skip-existing on)..."
    sleep 2
  done
}

echo "ROOT: ${ROOT_DIR}"
echo "RESULTS_ROOT: ${ROOT_DIR}/${RESULTS_ROOT_NAME}"
echo "NUM_RUNS=${NUM_RUNS} SKIP_EXISTING=${SKIP_EXISTING} RUN_TRAVEL=${RUN_TRAVEL} RUN_PLOTS=${RUN_PLOTS} RETRIES=${RETRIES} BATCH_BY_DENSITY=${BATCH_BY_DENSITY} MAX_JOBS=${MAX_JOBS}"

for ems_preset in "${EMS_PRESETS[@]}"; do
  export THESIS_EMS_PRESET="${ems_preset}"

  RESULTS_SUBDIR="${RESULTS_ROOT_NAME}/thesis_archetype_grid_ems${ems_preset}"
  RESULTS_FOLDER="${ROOT_DIR}/${RESULTS_SUBDIR}"
  mkdir -p "${RESULTS_FOLDER}"

  LOG_SUFFIX="ems${ems_preset//_/}"

  echo
  echo "########################################"
  echo "Starting EMS preset ${THESIS_EMS_PRESET} -> ${RESULTS_SUBDIR}"
  echo "########################################"

  if [ "${RUN_TRAVEL}" = "1" ]; then
    echo "=== Running main and travel concurrently [EMS=${THESIS_EMS_PRESET}] ==="
    run_mode_with_retries "main" &
    pid_main=$!

    run_mode_with_retries "travel" &
    pid_travel=$!

    fail=0
    if ! wait "${pid_main}"; then
      echo "Main grid failed (EMS=${THESIS_EMS_PRESET})."
      fail=1
    fi
    if ! wait "${pid_travel}"; then
      echo "Travel grid failed (EMS=${THESIS_EMS_PRESET})."
      fail=1
    fi

    if [ "${fail}" -ne 0 ]; then
      exit 1
    fi
  else
    run_mode_with_retries "main"
  fi

  echo "Finished EMS preset ${THESIS_EMS_PRESET}."
done

echo
echo "Done. Slice CSVs are under:"
for ems_preset in "${EMS_PRESETS[@]}"; do
  echo "  ${RESULTS_ROOT_NAME}/thesis_archetype_grid_ems${ems_preset}"
done

if [ "${RUN_PLOTS}" = "1" ]; then
  echo
  echo "########################################"
  echo "Generating slide figures (generate_slides_plots.py) into ${RESULTS_ROOT_NAME}/slides_figures_*"
  echo "########################################"
  for ems_preset in "${EMS_PRESETS[@]}"; do
    echo "--- plots: --results-root ${RESULTS_ROOT_NAME} --thesis-subdir thesis_archetype_grid_ems${ems_preset} --ems-preset ${ems_preset} ---"
    (
      cd "${ROOT_DIR}"
      "${PYTHON_BIN}" format_outputs/generate_slides_plots.py \
        --results-root "${RESULTS_ROOT_NAME}" \
        --thesis-subdir "thesis_archetype_grid_ems${ems_preset}" \
        --ems-preset "${ems_preset}" \
        --mode both
    )
  done
  echo "Plotting finished."
fi

echo
echo "All done."
