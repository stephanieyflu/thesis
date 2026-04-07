"""Watch progress of thesis slice jobs (main/travel × urban/rural × density).

Auto-discovers ``thesis_*.log`` under ``<results-root>/logs/`` (default: ``results_final/logs``).
Use ``--results-root results`` to watch the older ``results/logs`` layout.
Log names may include an EMS batch suffix, e.g. ``thesis_main_urban_low_ems1015.log``.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

# Matches lines like: [12/100] (remaining: 88)
PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]\s+\(remaining:\s*(\d+)\)")

# Full logs can be gigabytes; never load whole file (read_text caused MemoryError).
DEFAULT_TAIL_BYTES = 1024 * 1024  # 1 MiB tail: enough for progress + Saved / Traceback


def read_log_tail(log_path: Path, max_bytes: int = DEFAULT_TAIL_BYTES) -> str:
    """Last max_bytes of file only (binary seek), UTF-8 decoded."""
    try:
        with log_path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return ""
            if size <= max_bytes:
                f.seek(0)
                return f.read().decode("utf-8", errors="ignore")
            f.seek(max(0, size - max_bytes))
            return f.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""


def parse_last_progress(log_path: Path, tail_bytes: int = DEFAULT_TAIL_BYTES):
    if not log_path.exists():
        return None
    text = read_log_tail(log_path, tail_bytes)
    if not text.strip():
        return None

    lines = [ln for ln in text.splitlines() if ln.strip()]

    for ln in reversed(lines):
        m = PROGRESS_RE.search(ln)
        if m:
            cur, total, rem = map(int, m.groups())
            return {
                "current": cur,
                "total": total,
                "remaining": rem,
                "line": ln,
            }

    if "Saved " in text and "rows to" in text:
        return {"done": True}

    return {"line": lines[-1] if lines else ""}


def classify_job(log_path: Path, tail_bytes: int = DEFAULT_TAIL_BYTES):
    if not log_path.exists():
        return "pending"
    text = read_log_tail(log_path, tail_bytes)
    if not text:
        return "running"

    if "Traceback" in text or "FAIL" in text:
        return "failed"
    if "Saved " in text and "rows to" in text:
        return "done"
    return "running"


def clear_screen():
    print("\033[2J\033[H", end="")


def discover_logs(logs_dir: Path, include_travel: bool) -> list[Path]:
    logs = sorted(logs_dir.glob("thesis_*.log"))
    if not include_travel:
        logs = [p for p in logs if "travel" not in p.name]
    return sorted(logs, key=job_sort_key)


def _split_thesis_log_stem(stem: str) -> tuple[str, str, str, str]:
    """
    Parse stems like:
      thesis_main_urban
      thesis_main_urban_low
      thesis_main_urban_low_ems1015
    Returns (mode, env, density_label, ems_tag) where ems_tag is '' or e.g. 'ems1015'.
    """
    parts = stem.split("_")
    if len(parts) < 3 or parts[0] != "thesis":
        return "", "", "", ""
    mode = parts[1]
    env = parts[2]
    rest = parts[3:]
    ems_tag = ""
    if rest and rest[-1].startswith("ems"):
        ems_tag = rest[-1]
        rest = rest[:-1]
    density = "_".join(rest) if rest else ""
    return mode, env, density, ems_tag


def job_sort_key(path: Path):
    name = path.stem
    mode, env, density, ems_tag = _split_thesis_log_stem(name)

    mode_order = {"main": 0, "travel": 1}
    env_order = {"urban": 0, "rural": 1}
    density_order = {
        "": 0,
        "low": 1,
        "mid_low": 2,
        "medium": 3,
        "mid_high": 4,
        "high": 5,
    }
    # Order matches typical parallel-all-EMS runs: 10/15 -> 15/20 -> 5/10
    ems_tag_order = {"": 0, "ems1015": 1, "ems1520": 2, "ems510": 3}

    return (
        ems_tag_order.get(ems_tag, 50),
        mode_order.get(mode, 99),
        env_order.get(env, 99),
        density_order.get(density, 99),
        name,
    )


def pretty_job_name(stem: str) -> str:
    mode, env, density, ems_tag = _split_thesis_log_stem(stem)
    if not mode:
        return stem
    bits = [f"{mode:6s}", "|", f"{env:5s}"]
    if density:
        bits.extend(["|", density])
    if ems_tag:
        bits.extend(["|", ems_tag])
    return " ".join(bits)


def format_short_status(prog: dict | None) -> tuple[str, int, int]:
    if not prog:
        return "-", 0, 0

    if "current" in prog and "total" in prog:
        return f"{prog['current']}/{prog['total']}", prog["current"], prog["total"]

    if prog.get("done"):
        return "done", 0, 0

    if prog.get("line"):
        line = str(prog["line"]).strip()
        if len(line) > 90:
            line = line[:87] + "..."
        return line, 0, 0

    return "-", 0, 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python format_outputs/watch_thesis_progress.py\n"
            "  python format_outputs/watch_thesis_progress.py --results-root results --once\n"
        ),
    )
    parser.add_argument("--refresh", type=float, default=2.0, help="Seconds between refreshes.")
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit.")
    parser.add_argument(
        "--main-only",
        action="store_true",
        help="Only watch thesis_main_*.log files.",
    )
    parser.add_argument(
        "--results-root",
        type=str,
        default="results_final",
        help=(
            "Project subdirectory that contains logs/ (default: results_final). "
            "Use results for the legacy results/ batch layout."
        ),
    )
    parser.add_argument(
        "--tail-mb",
        type=float,
        default=1.0,
        help="Max megabytes to read from the end of each log (default 1). Avoids memory errors on huge logs.",
    )
    args = parser.parse_args()

    tail_bytes = max(64 * 1024, int(args.tail_mb * 1024 * 1024))

    root = Path(__file__).resolve().parents[1]
    logs_dir = (root / args.results_root / "logs").resolve()

    last_total_done = None
    last_ts = None
    ema_rate = None

    while True:
        include_travel = not args.main_only
        job_logs = discover_logs(logs_dir, include_travel=include_travel)

        rows = []
        counts = {"pending": 0, "running": 0, "done": 0, "failed": 0}
        overall_progress_current = 0
        overall_progress_total = 0

        for log_path in job_logs:
            status = classify_job(log_path, tail_bytes=tail_bytes)
            counts[status] += 1
            prog = parse_last_progress(log_path, tail_bytes=tail_bytes)

            short, cur, tot = format_short_status(prog)
            overall_progress_current += cur
            overall_progress_total += tot
            rows.append((pretty_job_name(log_path.stem), status, short))

        now_ts = time.time()
        eta_text = "n/a"

        if overall_progress_total > 0:
            total_done = overall_progress_current
            total_left = max(0, overall_progress_total - total_done)

            if last_total_done is not None and last_ts is not None:
                dt = max(1e-6, now_ts - last_ts)
                ddone = max(0, total_done - last_total_done)
                inst_rate = ddone / dt
                if ema_rate is None:
                    ema_rate = inst_rate
                else:
                    alpha = 0.35
                    ema_rate = alpha * inst_rate + (1 - alpha) * ema_rate

            if ema_rate is not None and ema_rate > 1e-9:
                eta_sec = total_left / ema_rate
                h = int(eta_sec // 3600)
                m = int((eta_sec % 3600) // 60)
                s = int(eta_sec % 60)
                eta_text = f"{h:02d}:{m:02d}:{s:02d}"

        last_total_done = overall_progress_current
        last_ts = now_ts

        clear_screen()
        print("Thesis slice progress")
        print(f"logs: {logs_dir}")
        print(f"results-root: {args.results_root}")
        print(f"watching: {'main only' if args.main_only else 'main + travel'}")
        print()

        if not job_logs:
            print("(no thesis_*.log files yet)")
        else:
            print(
                f"pending={counts['pending']}  running={counts['running']}  "
                f"done={counts['done']}  failed={counts['failed']}"
            )

            if overall_progress_total > 0:
                pct = 100.0 * overall_progress_current / max(1, overall_progress_total)
                print(
                    f"aggregate inner-loop progress: "
                    f"{overall_progress_current}/{overall_progress_total} ({pct:.1f}%)"
                )
                if ema_rate is not None:
                    print(f"rate: {ema_rate:.2f} it/s  |  ETA: {eta_text}")
                else:
                    print("rate: warming up...  |  ETA: n/a")
            else:
                print("aggregate inner-loop progress: waiting for first progress lines...")

        print("-" * 110)
        print(f"{'job':28s}  {'status':8s}  details")
        print("-" * 110)
        for job, status, short in rows:
            print(f"{job:28s}  {status:8s}  {short}")
        print("-" * 110)
        print("Press Ctrl+C to stop watching.")

        if args.once:
            break
        time.sleep(max(0.5, args.refresh))


if __name__ == "__main__":
    main()