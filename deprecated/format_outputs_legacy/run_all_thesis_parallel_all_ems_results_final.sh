#!/usr/bin/env bash
# Deprecated compatibility entrypoint. Use thesis_tools/ path directly.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "${ROOT_DIR}/thesis_tools/run_all_thesis_parallel_all_ems_results_final.sh" "$@"
