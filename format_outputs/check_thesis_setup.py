"""Verify thesis pipeline scripts exist (parallel runner, slice runner, merge, plots)."""

from __future__ import annotations

import sys
from pathlib import Path


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    fo = root / "format_outputs"
    required = [
        fo / "run_thesis_slice.py",
        fo / "merge_thesis_slices.py",
        fo / "run_all_thesis_parallel.sh",
        fo / "run_all_thesis_parallel.ps1",
        fo / "generate_slides_plots.py",
    ]
    for fp in required:
        if not fp.exists():
            fail(f"Missing required file: {fp}")

    print("[OK] All thesis pipeline scripts present.")
    print("     Run: bash format_outputs/run_all_thesis_parallel.sh   (or .\\format_outputs\\run_all_thesis_parallel.ps1)")
    print("     Then: python format_outputs/generate_slides_plots.py")


if __name__ == "__main__":
    main()
