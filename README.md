# A Simulation Approach to Comparing & Optimizing Alert Rules in Community First Responder Systems for OHCA (ESC499 Undergraduate Thesis)

Discrete-event simulation framework for comparing community first responder (CFR) alerting policies under stylized urban/rural emergency-response environments.

## Overview

This repository contains:

- a CFR simulation engine and policy implementations (canonical package: `src/cfr_sim/`)
- factorial experiment configuration for thesis runs (`src/cfr_sim/experiment_grid.py`)
- batch runners and plotting pipelines (`thesis_tools/`)
- thesis manuscript source (`report/`)

The experiments are designed for **comparative policy evaluation** (not city-specific calibration): policy ranking, trade-offs, and sensitivity to density, engagement, travel friction, and EMS response assumptions.

## Quick Start

```bash
python -m venv .venv-thesis
source .venv-thesis/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
```

Run the thesis main grid:

```bash
python thesis_tools/run_thesis_slice.py --environment urban --mode main
```

Generate figures from existing results:

```bash
python thesis_tools/generate_slides_plots.py \
  --results-root results_final \
  --thesis-subdir thesis_archetype_grid_ems5_10 \
  --ems-preset 5_10 \
  --mode both
```

## Reproducibility: Key Commands

- **Parallel thesis slices / batches:** `thesis_tools/run_all_thesis_parallel_all_ems_results_final.sh`
- **Per-slice runner:** `thesis_tools/run_thesis_slice.py`
- **Progress monitor:** `thesis_tools/watch_thesis_progress.py`
- **Build thesis PDF (from `report/`):** `latexmk -pdf main.tex`

See `thesis_tools/README.md` for the canonical command set.

## Repository Layout

```text
thesis/
├── src/cfr_sim/                # Canonical Python package (core simulation modules)
├── thesis_tools/               # Preferred CLI script location
├── deprecated/                 # Archived legacy code and old script paths
├── results/                    # Local/intermediate outputs
├── results_final/              # Final run artifacts (CSVs + figures)
└── report/                     # LaTeX thesis source
```

## Data and Outputs

Primary outputs are event-level and run-level CSV files, plus publication figures in `results_final/slides_figures_*`.

Large result files and build artifacts are intentionally ignored by git.

## Package Structure

Core modules now live under `src/cfr_sim/`, and new imports should use `src.cfr_sim.*`.
`thesis_tools/` is now the preferred CLI folder name for thesis scripts.
Legacy full implementations and old script paths are archived under `deprecated/`.
For final write-up and reproducibility commands, use `thesis_tools/` and `src.cfr_sim.*`.