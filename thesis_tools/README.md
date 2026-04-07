# Thesis Tools

Canonical scripts for final thesis reproducibility.

## Most-used commands

- Run all cached/final batches (main + travel):
  - `bash thesis_tools/run_all_thesis_parallel_all_ems_results_final.sh`
- Regenerate publication figures from cached results:
  - `python thesis_tools/generate_slides_plots.py --results-root results_final --thesis-subdir thesis_archetype_grid_ems5_10 --ems-preset 5_10 --mode both`
- Monitor progress:
  - `python thesis_tools/watch_thesis_progress.py`
