"""Verify thesis pipeline scripts exist (parallel runner, slice runner, merge, plots)."""

from __future__ import annotations

import sys
from pathlib import Path


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    tools = root / "thesis_tools"
    required = [
        tools / "run_thesis_slice.py",
        tools / "run_all_thesis_parallel_all_ems_results_final.sh",
        tools / "watch_thesis_progress.py",
        tools / "generate_slides_plots.py",
    ]
    for fp in required:
        if not fp.exists():
            fail(f"Missing required file: {fp}")

    print("[OK] All thesis pipeline scripts present.")
    print("     Run: bash thesis_tools/run_all_thesis_parallel_all_ems_results_final.sh")
    print("     Then: python thesis_tools/generate_slides_plots.py")


if __name__ == "__main__":
    main()
