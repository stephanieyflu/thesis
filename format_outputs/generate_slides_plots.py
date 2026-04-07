"""
Thesis / CFR slide figures — suggested reading order for a coherent story:

1. **01_dashboard** — First-arrival ECDF, means, redundancy, 5-min coverage at baseline; **14** P(first arrival ≤ T) vs T = 5,…,10 min.
2. **02_tradeoff** — Redundancy vs speed (mean first-arrival) with EMS mean reference.
3. **08–09 / race** — Volunteer-before-EMS rate and Δ vs EMS-only (min(volunteer, EMS) decomposition).
4. **10–13** — ECDF of CFR-beats-EMS, heatmaps, density/acceptance/travel trends for that rate.
5. **03–07 / 04–06** — Factorial sensitivities (travel friction, density, acceptance).
6. **00_compare_ems** (if `--compare-thesis-subdir` is set) — Same baseline slice under two EMS calibrations.

Use `--thesis-subdir` to point at the folder that contains your slice CSVs (e.g.\
`thesis_archetype_grid`, or `results_final/thesis_archetype_grid_ems5_10` when using\
`--results-root results_final`). Match `--ems-preset` to the simulation batch (`5_10`,\
`10_15`, or `15_20`); the default thesis grid in `experiment_grid.py` uses the `5_10` means\
unless `THESIS_EMS_PRESET` overrides it.
"""

from pathlib import Path
import argparse
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from scipy import stats

from utils import apply_thesis_retroactive_time_adjustment


GROUP_COLS = [
    "policy",
    "environment",
    "ems_label",
    "acceptance_label",
    "density_label",
    "speed_label",
    "run_id",
    "seed",
]

# P(first_arrival <= T min); derived from per-event first_arrival_time during aggregation.
COVERAGE_THRESHOLDS_MIN = list(range(5, 11))  # 5 … 10

# Run-level means (after aggregating event-level simulation output).
METRIC_COLS = [
    "first_arrival_time",
    "num_redundant",
    *[f"coverage_{t}" for t in COVERAGE_THRESHOLDS_MIN],
    "num_alerted",
    "num_accepted",
    "cfr_beats_ems",
    "first_volunteer_arrival",
]

# Raw columns expected in thesis/chunk CSVs (event-level rows before groupby).
# coverage_* are recomputed from first_arrival_time in aggregation (CSV column optional).
CSV_EVENT_METRIC_COLS = [
    "first_arrival_time",
    "ambulance_time",
    "num_redundant",
    "num_alerted",
    "num_accepted",
    "cfr_beats_ems",
    "first_volunteer_arrival",
]

BASELINE_FILTERS_BY_MODE = {
    "main": {
        "ems_label": "fixed",
        "acceptance_label": "acc_v3",
        "density_label": "low",
        "speed_label": "baseline",
    },
    "travel": {
        "ems_label": "fixed",
        "acceptance_label": "acc_v3",
        "density_label": "low",
        "speed_label": "trav_v3",
    },
}

# Default reference lines on plots (urban / rural mean EMS times in minutes).
EMS_BENCHMARK = {
    "urban": {"mean": 10.0, "std": 3.0},
    "rural": {"mean": 15.0, "std": 5.0},
}

# Presets must match how you simulated THESIS_EMS_FIXED in experiment_grid.py (lognormal EMS).
EMS_PRESETS: dict[str, dict[str, dict[str, float]]] = {
    "5_10": {
        "urban": {"mean": 5.0, "std": 2.0},
        "rural": {"mean": 10.0, "std": 3.0},
    },
    "10_15": {
        "urban": {"mean": 10.0, "std": 3.0},
        "rural": {"mean": 15.0, "std": 5.0},
    },
    "15_20": {
        "urban": {"mean": 15.0, "std": 4.0},
        "rural": {"mean": 20.0, "std": 6.0},
    },
}

# Cross-EMS overlay legends (dual-full-bundles); primary baseline first, compare second.
EMS_PRESET_CROSS_LEGEND = {
    "5_10": "EMS ~5/10 min (urban/rural means)",
    "10_15": "EMS ~10/15 min (urban/rural means)",
    "15_20": "EMS ~15/20 min (urban/rural means)",
}

# -----------------------------------------------------------------------------
# Legacy CSV adjustment: subtract E[legacy view/decision delay] from volunteer
# arrival times (see ``apply_thesis_retroactive_time_adjustment`` in ``utils`` and
# ``THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY`` in ``config``).
# -----------------------------------------------------------------------------


def _thesis_time_adj_cache_suffix() -> str:
    from config import THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY

    return "_thesis_time_adj" if THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY else ""

# Exclude policies from all slide outputs (kept in raw simulation CSVs).
EXCLUDED_POLICIES = {"Random"}

# Stable policy color mapping across all figures.
POLICY_COLOR_ORDER = [
    "Mobile Lifesaver",
    "GoodSAM",
    "Hartslagnu",
    "Momentum",
    "HeartRunner",
    "PulsePoint_and_myResponder",
    "EMS only",
    "Random",
]


def resolve_ems_benchmark(
    preset: str,
    urban_mean: float | None = None,
    rural_mean: float | None = None,
) -> dict[str, dict[str, float]]:
    if preset not in EMS_PRESETS:
        raise ValueError(f"Unknown --ems-preset {preset!r}; choose from {list(EMS_PRESETS)}")
    bench: dict[str, dict[str, float]] = {k: dict(v) for k, v in EMS_PRESETS[preset].items()}
    if urban_mean is not None:
        bench["urban"]["mean"] = float(urban_mean)
    if rural_mean is not None:
        bench["rural"]["mean"] = float(rural_mean)
    return bench


def _ems_mean(bench: dict[str, dict[str, float]] | None, env: str) -> float:
    b = bench if bench is not None else EMS_BENCHMARK
    return float(b[env]["mean"])


def resolve_plot_output_dir(
    results: Path,
    mode: str,
    thesis_subdir: str,
    output_tag: str | None,
) -> Path:
    """Separate folders for default grid vs e.g. thesis_archetype_grid_ems15_20."""
    if output_tag:
        return results / f"slides_figures_{mode}_{output_tag}"
    name = Path(thesis_subdir).name
    if name == "thesis_archetype_grid":
        return results / f"slides_figures_{mode}"
    return results / f"slides_figures_{mode}_{name}"

DENSITY_ORDER = ["low", "mid_low", "medium", "mid_high", "high"]
ACCEPTANCE_ORDER = ["acc_v1", "acc_v2", "acc_v3", "acc_v4", "acc_v5", "acc_v6"]
TRAVEL_ORDER = ["trav_v1", "trav_v2", "trav_v3", "trav_v4", "trav_v5"]
ENV_ORDER = ["urban", "rural"]


def resolve_root() -> Path:
    root = Path.cwd()
    if not (root / "results").exists() and (root.parent / "results").exists():
        root = root.parent
    return root


def _ensure_race_columns(chunk: pd.DataFrame) -> pd.DataFrame:
    """Old CSVs may lack race-decomposition columns; fill so aggregation still runs."""
    chunk = chunk.copy()
    if "cfr_beats_ems" not in chunk.columns:
        chunk["cfr_beats_ems"] = np.float64(0.0)
    else:
        chunk["cfr_beats_ems"] = chunk["cfr_beats_ems"].astype(np.float64)
    if "first_volunteer_arrival" not in chunk.columns:
        chunk["first_volunteer_arrival"] = np.nan
    else:
        chunk["first_volunteer_arrival"] = pd.to_numeric(
            chunk["first_volunteer_arrival"], errors="coerce"
        )
    return chunk


def _ensure_coverage_thresholds(chunk: pd.DataFrame) -> pd.DataFrame:
    """P(first arrival <= T min) per event from first_arrival_time (matches simulation logic)."""
    chunk = chunk.copy()
    fa = pd.to_numeric(chunk["first_arrival_time"], errors="coerce")
    for t in COVERAGE_THRESHOLDS_MIN:
        chunk[f"coverage_{t}"] = (fa <= float(t)).astype(np.float64)
    return chunk


def _aggregate_chunk_to_runs(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk = _ensure_race_columns(chunk)
    chunk = apply_thesis_retroactive_time_adjustment(chunk)
    chunk = _ensure_coverage_thresholds(chunk)

    def _fv_sum(s: pd.Series) -> float:
        return float(np.nansum(s.to_numpy(dtype=float)))

    def _fv_n(s: pd.Series) -> int:
        return int(np.isfinite(s.to_numpy(dtype=float)).sum())

    cov_aggs = {f"coverage_{t}_sum": (f"coverage_{t}", "sum") for t in COVERAGE_THRESHOLDS_MIN}
    base_aggs = {
        "first_arrival_time_sum": ("first_arrival_time", "sum"),
        "num_redundant_sum": ("num_redundant", "sum"),
        "num_alerted_sum": ("num_alerted", "sum"),
        "num_accepted_sum": ("num_accepted", "sum"),
        "cfr_beats_ems_sum": ("cfr_beats_ems", "sum"),
        "first_volunteer_sum": ("first_volunteer_arrival", _fv_sum),
        "first_volunteer_n": ("first_volunteer_arrival", _fv_n),
        "event_count": ("first_arrival_time", "size"),
    }
    base_aggs.update(cov_aggs)
    return chunk.groupby(GROUP_COLS, as_index=False).agg(**base_aggs)


def _rollup_agg(acc: pd.DataFrame | None, part: pd.DataFrame) -> pd.DataFrame:
    if acc is None:
        return part
    merged = pd.concat([acc, part], ignore_index=True)
    cov_sums = [f"coverage_{t}_sum" for t in COVERAGE_THRESHOLDS_MIN]
    return (
        merged.groupby(GROUP_COLS, as_index=False)[
            [
                "first_arrival_time_sum",
                "num_redundant_sum",
                *cov_sums,
                "num_alerted_sum",
                "num_accepted_sum",
                "cfr_beats_ems_sum",
                "first_volunteer_sum",
                "first_volunteer_n",
                "event_count",
            ]
        ]
        .sum()
    )


def _stream_source_files_into_agg(
    files: list[Path],
    usecols: list[str],
    chunksize: int,
    agg: pd.DataFrame | None,
) -> pd.DataFrame | None:
    for fp in files:
        print(f"  reading {fp.name}")
        for chunk in pd.read_csv(fp, usecols=lambda c: c in usecols, chunksize=chunksize):
            part = _aggregate_chunk_to_runs(chunk)
            agg = _rollup_agg(agg, part)
    return agg


def _is_run_level_schema(columns: list[str]) -> bool:
    return all(c in columns for c in (GROUP_COLS + METRIC_COLS))


def _load_run_level_files(files: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    keep_cols = GROUP_COLS + METRIC_COLS
    for fp in files:
        print(f"  reading run-level {fp.name}")
        frames.append(pd.read_csv(fp, usecols=lambda c: c in keep_cols))
    if not frames:
        return pd.DataFrame(columns=keep_cols)
    return pd.concat(frames, ignore_index=True)


def build_run_level_from_sources(
    results_dir: Path,
    mode: str = "main",
    chunksize: int = 200_000,
    use_cache: bool = True,
    thesis_subdir: str = "thesis_archetype_grid",
) -> pd.DataFrame:
    sub_name = Path(thesis_subdir).name
    suf = _thesis_time_adj_cache_suffix()
    if sub_name == "thesis_archetype_grid":
        run_cache = results_dir / f"run_level_for_slides_{mode}{suf}.csv"
    else:
        run_cache = results_dir / f"run_level_for_slides_{mode}_{sub_name}{suf}.csv"
    if use_cache and run_cache.exists():
        run_df = pd.read_csv(run_cache)
        print(f"Loaded cached run-level dataset: {run_cache.name} | rows={len(run_df):,}")
        return run_df

    thesis_dir = (results_dir / thesis_subdir).resolve()

    combined_thesis = thesis_dir / f"combined_thesis_{mode}_grid.csv"
    mono_files = [
        thesis_dir / f"thesis_{mode}_urban.csv",
        thesis_dir / f"thesis_{mode}_rural.csv",
    ]
    density_files = sorted(thesis_dir.glob(f"thesis_{mode}_urban_*.csv")) + sorted(
        thesis_dir.glob(f"thesis_{mode}_rural_*.csv")
    )

    # Fast path: if source CSVs are already run-level (one row per scenario/policy/run),
    # load directly instead of re-aggregating event-level rows.
    source_files = [combined_thesis] if combined_thesis.exists() else density_files
    if not source_files and all(p.exists() for p in mono_files):
        source_files = mono_files
    if source_files:
        sample_cols = pd.read_csv(source_files[0], nrows=0).columns.tolist()
        if _is_run_level_schema(sample_cols):
            from config import THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY

            if THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY:
                raise ValueError(
                    "Legacy decision-delay time adjustment needs event-level CSV columns "
                    "(first_volunteer_arrival, ambulance_time). Use event-level exports, or set "
                    "THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY = False in config.py, or pass "
                    "--skip-legacy-delay-adjustment."
                )
            run_df = _load_run_level_files(source_files)
            run_df.to_csv(run_cache, index=False)
            print(f"Saved run-level cache: {run_cache} | rows={len(run_df):,}")
            return run_df

    usecols = GROUP_COLS + CSV_EVENT_METRIC_COLS
    agg = None

    if combined_thesis.exists():
        print(f"Streaming combined thesis file: {combined_thesis.name}")
        for chunk in pd.read_csv(combined_thesis, usecols=lambda c: c in usecols, chunksize=chunksize):
            part = _aggregate_chunk_to_runs(chunk)
            agg = _rollup_agg(agg, part)

    elif density_files:
        print(f"Streaming {len(density_files)} density slice files for mode={mode}...")
        agg = _stream_source_files_into_agg(density_files, usecols, chunksize, agg)

    elif all(p.exists() for p in mono_files):
        print(f"Streaming mono thesis files for mode={mode}...")
        agg = _stream_source_files_into_agg(mono_files, usecols, chunksize, agg)

    else:
        chunk_files = sorted(results_dir.glob("combined_grid_chunk*_*.csv"))
        if chunk_files and mode == "main":
            print(f"Streaming {len(chunk_files)} chunk files into run-level aggregation...")
            for fp in chunk_files:
                print(f"  reading {fp.name}")
                for chunk in pd.read_csv(fp, usecols=lambda c: c in usecols, chunksize=chunksize):
                    part = _aggregate_chunk_to_runs(chunk)
                    agg = _rollup_agg(agg, part)
        else:
            merged = results_dir / "combined_notebook_plus_grid_all.csv"
            if mode == "main" and merged.exists():
                print(f"Streaming merged file {merged.name} into run-level aggregation...")
                for chunk in pd.read_csv(merged, usecols=lambda c: c in usecols, chunksize=chunksize):
                    part = _aggregate_chunk_to_runs(chunk)
                    agg = _rollup_agg(agg, part)
            else:
                raise FileNotFoundError(
                    f"No usable CSV sources found for mode={mode}. "
                    f"Looked for combined file, density slices, and mono files in {thesis_dir}."
                )

    if agg is None or agg.empty:
        raise RuntimeError(f"No data aggregated from sources for mode={mode}.")

    run_df = agg.copy()
    run_df["first_arrival_time"] = run_df["first_arrival_time_sum"] / run_df["event_count"]
    run_df["num_redundant"] = run_df["num_redundant_sum"] / run_df["event_count"]
    for t in COVERAGE_THRESHOLDS_MIN:
        run_df[f"coverage_{t}"] = run_df[f"coverage_{t}_sum"] / run_df["event_count"]
    run_df["num_alerted"] = run_df["num_alerted_sum"] / run_df["event_count"]
    run_df["num_accepted"] = run_df["num_accepted_sum"] / run_df["event_count"]
    run_df["cfr_beats_ems"] = run_df["cfr_beats_ems_sum"] / run_df["event_count"]
    run_df["first_volunteer_arrival"] = np.where(
        run_df["first_volunteer_n"] > 0,
        run_df["first_volunteer_sum"] / run_df["first_volunteer_n"],
        np.nan,
    )
    run_df = run_df[GROUP_COLS + METRIC_COLS]

    run_df.to_csv(run_cache, index=False)
    print(f"Saved run-level cache: {run_cache} | rows={len(run_df):,}")
    return run_df


def validate_run_df(run_df: pd.DataFrame) -> None:
    required_cols = GROUP_COLS + METRIC_COLS
    missing = [c for c in required_cols if c not in run_df.columns]
    if missing:
        raise ValueError(
            f"Missing expected columns: {missing}. "
            "If you upgraded this script, delete run_level cache files or re-run with --no-run-cache."
        )
    print("Scenario-run rows:", f"{len(run_df):,}")


def _exclude_policies(run_df: pd.DataFrame) -> pd.DataFrame:
    """Drop policies not intended for reporting (e.g., Random baseline)."""
    if "policy" not in run_df.columns:
        return run_df
    if not EXCLUDED_POLICIES:
        return run_df
    keep = ~run_df["policy"].isin(EXCLUDED_POLICIES)
    dropped = int((~keep).sum())
    if dropped:
        print(f"Excluding {dropped:,} rows for policies: {sorted(EXCLUDED_POLICIES)}")
    return run_df.loc[keep].copy()


def extract_baseline(run_df: pd.DataFrame, mode: str) -> pd.DataFrame:
    filters = BASELINE_FILTERS_BY_MODE[mode]
    baseline_df = run_df.copy()
    for col, value in filters.items():
        baseline_df = baseline_df[baseline_df[col] == value]

    if baseline_df.empty:
        print("Available labels for debugging:")
        for c in ["ems_label", "acceptance_label", "density_label", "speed_label"]:
            vals = sorted(run_df[c].dropna().astype(str).unique().tolist())
            print(f"  {c}: {vals}")
        raise RuntimeError(
            f"Baseline scenario produced no rows for mode={mode}. Filters used: {filters}"
        )

    print(f"Baseline rows ({mode}): {len(baseline_df):,}")
    for env in ENV_ORDER:
        n = (baseline_df["environment"] == env).sum()
        if n:
            print(f"  {env}: {n:,} rows")
    return baseline_df


def _policy_order(df: pd.DataFrame) -> list[str]:
    return df.groupby("policy")["first_arrival_time"].mean().sort_values().index.tolist()


def _policy_palette(policy_order: list[str]) -> dict[str, tuple]:
    base_colors = sns.color_palette("colorblind", n_colors=len(POLICY_COLOR_ORDER))
    palette = {p: c for p, c in zip(POLICY_COLOR_ORDER, base_colors)}
    missing = [p for p in policy_order if p not in palette]
    if missing:
        extra = sns.color_palette("husl", n_colors=len(missing))
        palette.update({p: c for p, c in zip(missing, extra)})
    return {p: palette[p] for p in policy_order}


def _tight_limits(values: pd.Series, pad_frac: float = 0.08, min_pad: float = 0.02):
    vmin = float(values.min())
    vmax = float(values.max())
    span = max(vmax - vmin, min_pad)
    pad = max(span * pad_frac, min_pad)
    return vmin - pad, vmax + pad


def _partial_quantile_xlim(
    ax,
    values: pd.Series,
    q_lo: float = 0.005,
    q_hi: float = 0.995,
    pad_frac: float = 0.06,
    min_pad: float = 0.05,
    lower_zero: bool = True,
):
    """Mild default zoom for long-tailed continuous x-axes."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    if v.empty:
        return
    lo = float(v.quantile(q_lo))
    hi = float(v.quantile(q_hi))
    span = max(hi - lo, min_pad)
    pad = max(span * pad_frac, min_pad)
    x0 = lo - pad
    x1 = hi + pad
    if lower_zero:
        x0 = max(0.0, x0)
    if x1 > x0:
        ax.set_xlim(x0, x1)


def _apply_zoom_limits(ax, values: pd.Series, include: list[float] | None = None,
                       pad_frac: float = 0.12, min_pad: float = 0.04, lower_zero: bool = False):
    extra = pd.Series(include if include is not None else [], dtype=float)
    vals = pd.concat([values.astype(float), extra], ignore_index=True)
    lo, hi = _tight_limits(vals, pad_frac=pad_frac, min_pad=min_pad)
    if lower_zero:
        lo = max(0, lo)
    ax.set_ylim(lo, hi)


def _place_legend_outside(ax, title: str | None = None):
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return
    ax.legend(
        handles,
        labels,
        title=title,
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
        frameon=True,
        fontsize=9,
        title_fontsize=10,
    )


def _pretty_density(label: str) -> str:
    return label.replace("_", " ").title()


def _pretty_acceptance(label: str) -> str:
    return label.upper().replace("_", " ")


def _pretty_travel(label: str) -> str:
    return label.upper().replace("_", " ")


def save_coverage_threshold_curves(
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    zoom: bool = False,
) -> None:
    """
    Mean P(first arrival <= T minutes) for T = 5,…,10 at the baseline slice (one line per policy).
    """
    cov_cols = [f"coverage_{t}" for t in COVERAGE_THRESHOLDS_MIN]
    melted = baseline_df.melt(
        id_vars=["environment", "policy"],
        value_vars=cov_cols,
        var_name="_c",
        value_name="coverage",
    )
    melted["threshold_min"] = melted["_c"].str.replace("coverage_", "", regex=False).astype(int)
    melted = melted.drop(columns=["_c"])

    fig, axes = plt.subplots(1, 2, figsize=(17, 6.5), sharey=True)
    for i, env in enumerate(ENV_ORDER):
        sub = melted[melted["environment"] == env]
        if sub.empty:
            axes[i].set_visible(False)
            continue
        env_base = baseline_df[baseline_df["environment"] == env]
        po = _policy_order(env_base)
        pal = _policy_palette(po)
        sns.lineplot(
            data=sub,
            x="threshold_min",
            y="coverage",
            hue="policy",
            hue_order=po,
            palette=[pal[p] for p in po],
            marker="o",
            linewidth=2.2,
            ax=axes[i],
        )
        axes[i].set_xticks(COVERAGE_THRESHOLDS_MIN)
        axes[i].set_xlabel("Time threshold T (minutes)")
        axes[i].set_ylabel("P(first arrival ≤ T)")
        axes[i].set_ylim(0, 1.05)
        axes[i].set_title(f"{env.capitalize()}: coverage vs time threshold (baseline)")
        _place_legend_outside(axes[i], title="Policy")
        if zoom:
            _apply_zoom_limits(
                axes[i],
                sub.groupby(["policy", "threshold_min"])["coverage"].mean(),
                pad_frac=0.12,
                min_pad=0.02,
                lower_zero=True,
            )

    plt.suptitle(
        f"{mode.capitalize()} | Early-arrival coverage: P(first arrival ≤ T) for T = 5,…,10 min",
        y=1.02,
        fontsize=14,
    )
    plt.tight_layout(rect=[0, 0, 0.82, 1])
    suffix = "_zoom" if zoom else ""
    plt.savefig(out / f"14_coverage_vs_threshold_{mode}_baseline{suffix}.png", bbox_inches="tight")
    plt.close()

    wide = (
        baseline_df.groupby(["environment", "policy"], as_index=False)[cov_cols]
        .mean()
        .rename(
            columns={
                f"coverage_{t}": f"P(first_arrival_le_{t}min)"
                for t in COVERAGE_THRESHOLDS_MIN
            }
        )
    )
    wide.to_csv(out / f"baseline_coverage_by_threshold_{mode}.csv", index=False)


def save_baseline_summary_tables(
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
) -> None:
    baseline_df.to_csv(out / f"baseline_rows_{mode}.csv", index=False)

    cov_aggs = {
        f"mean_coverage_le_{t}_min": (f"coverage_{t}", "mean")
        for t in COVERAGE_THRESHOLDS_MIN
    }
    summary = baseline_df.groupby(["environment", "policy"], as_index=False).agg(
        mean_first_arrival_minutes=("first_arrival_time", "mean"),
        sd_first_arrival_minutes=("first_arrival_time", "std"),
        mean_redundant_arrivals=("num_redundant", "mean"),
        sd_redundant_arrivals=("num_redundant", "std"),
        mean_alerted_responders=("num_alerted", "mean"),
        mean_accepted_responders=("num_accepted", "mean"),
        mean_cfr_beats_ems_rate=("cfr_beats_ems", "mean"),
        mean_first_volunteer_arrival=("first_volunteer_arrival", "mean"),
        **cov_aggs,
    )
    summary.to_csv(out / f"baseline_policy_environment_summary_{mode}.csv", index=False)


def save_story_slide_figures(
    run_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    ems_benchmark: dict[str, dict[str, float]] | None = None,
) -> None:
    """
    Curated figures for the 5-slide results narrative.
    - main mode: S1, S2, S3
    - travel mode: S4
    """
    if mode == "main":
        # S1: First-arrival ECDF + who arrives first.
        fig, axes = plt.subplots(
            2, 2, figsize=(20, 11), gridspec_kw={"height_ratios": [1.0, 0.62]}
        )
        legend_items = {}
        for i, env in enumerate(ENV_ORDER):
            sub = baseline_df[baseline_df["environment"] == env].copy()
            if sub.empty:
                axes[0, i].set_visible(False)
                axes[1, i].set_visible(False)
                continue
            po = _policy_order(sub)
            pal = _policy_palette(po)

            sns.ecdfplot(
                data=sub, x="first_arrival_time", hue="policy", hue_order=po,
                palette=[pal[p] for p in po], linewidth=2.1, ax=axes[0, i]
            )
            axes[0, i].axvline(_ems_mean(ems_benchmark, env), color="dimgray", linestyle=":", linewidth=2.0)
            _partial_quantile_xlim(axes[0, i], sub["first_arrival_time"])
            axes[0, i].set_title(f"{env.capitalize()}: first-arrival CDF")
            axes[0, i].set_xlabel("First-arrival time (minutes)")
            axes[0, i].set_ylabel("Cumulative share of incidents")
            for p in po:
                legend_items[p] = pal[p]
            leg = axes[0, i].get_legend()
            if leg is not None:
                leg.remove()

            race = sub.groupby("policy", as_index=False).agg(cfr=("cfr_beats_ems", "mean"))
            race = race.set_index("policy").reindex(po).reset_index()
            race["ems_first"] = 1.0 - race["cfr"]
            axes[1, i].barh(
                race["policy"], race["cfr"], height=0.58, color="#4C72B0", label="Volunteer first"
            )
            axes[1, i].barh(
                race["policy"],
                race["ems_first"],
                left=race["cfr"],
                height=0.58,
                color="#C0C0C0",
                label="EMS first",
            )
            axes[1, i].set_xlim(0, 1.0)
            axes[1, i].set_xlabel("Share of incidents")
            axes[1, i].set_title(f"{env.capitalize()}: who arrives first")
            axes[1, i].invert_yaxis()
        if legend_items:
            ordered_policies = [p for p in POLICY_COLOR_ORDER if p in legend_items]
            ordered_policies += [p for p in legend_items.keys() if p not in ordered_policies]
            policy_handles = [
                Line2D([0], [0], color=legend_items[p], lw=2.5, label=p) for p in ordered_policies
            ]
            fig.legend(
                policy_handles,
                [h.get_label() for h in policy_handles],
                title="Policy",
                loc="upper left",
                bbox_to_anchor=(0.86, 0.98),
                ncol=1,
                frameon=True,
            )
        race_handles = [
            Patch(facecolor="#4C72B0", edgecolor="none", label="Volunteer first"),
            Patch(facecolor="#C0C0C0", edgecolor="none", label="EMS first"),
        ]
        fig.legend(
            race_handles,
            [h.get_label() for h in race_handles],
            title="First-arriver split",
            loc="upper left",
            bbox_to_anchor=(0.86, 0.45),
            ncol=1,
            frameon=True,
        )
        plt.suptitle("S1 | Core performance: speed and first-arriver decomposition (baseline)", y=1.01)
        plt.tight_layout(rect=[0, 0.02, 0.84, 0.98])
        for _ax in fig.axes:
            _ax.set_title("")
        plt.savefig(out / "S1_core_speed_and_first_arriver_main.png", bbox_inches="tight")
        plt.savefig(out / "S1_core_speed_and_first_arriver_main.pdf", bbox_inches="tight")
        plt.close()

        # S2: Redundancy-only burden plot (baseline).
        fig, axes = plt.subplots(1, 2, figsize=(18, 6), sharey=False)
        for i, env in enumerate(ENV_ORDER):
            sub = baseline_df[baseline_df["environment"] == env].copy()
            if sub.empty:
                axes[i].set_visible(False)
                continue
            order = sub.groupby("policy")["num_redundant"].mean().sort_values().index.tolist()
            pal = _policy_palette(order)
            sns.barplot(
                data=sub,
                x="policy",
                y="num_redundant",
                order=order,
                palette=[pal[p] for p in order],
                errorbar=("ci", 95),
                ax=axes[i],
            )
            axes[i].set_title(f"{env.capitalize()}: mean redundant arrivals")
            axes[i].set_xlabel("Policy")
            axes[i].set_ylabel("Redundant arrivals per incident")
            axes[i].tick_params(axis="x", rotation=35)
            _apply_zoom_limits(
                axes[i],
                sub.groupby("policy")["num_redundant"].mean(),
                pad_frac=0.14,
                min_pad=0.02,
                lower_zero=True,
            )
        plt.suptitle("S2 | Operational burden: redundant arrivals by policy (baseline)", y=1.02)
        plt.tight_layout()
        for _ax in fig.axes:
            _ax.set_title("")
        plt.savefig(out / "S2_redundancy_burden_main.png", bbox_inches="tight")
        plt.savefig(out / "S2_redundancy_burden_main.pdf", bbox_inches="tight")
        plt.close()

        # S3: Acceptance x density heatmaps for two selected policies.
        selected = ["GoodSAM", "Mobile Lifesaver"]
        fig, axes = plt.subplots(2, 2, figsize=(18, 11), sharex=False, sharey=False)
        cax = fig.add_axes([0.92, 0.18, 0.015, 0.64])
        for r, env in enumerate(ENV_ORDER):
            for c, pol in enumerate(selected):
                ax = axes[r, c]
                sub = run_df[
                    (run_df["environment"] == env)
                    & (run_df["policy"] == pol)
                    & (run_df["ems_label"] == "fixed")
                    & (run_df["speed_label"] == "baseline")
                ].copy()
                piv = sub.pivot_table(
                    index="density_label", columns="acceptance_label", values="cfr_beats_ems", aggfunc="mean"
                ).reindex(index=[x for x in DENSITY_ORDER if x in sub["density_label"].unique()],
                          columns=[x for x in ACCEPTANCE_ORDER if x in sub["acceptance_label"].unique()])
                if piv.empty:
                    ax.set_visible(False)
                    continue
                sns.heatmap(
                    piv, annot=True, fmt=".2f", cmap="YlGnBu", vmin=0, vmax=1,
                    linewidths=0.4, linecolor="white", cbar=(r == 0 and c == 1),
                    cbar_ax=cax if (r == 0 and c == 1) else None,
                    cbar_kws={"label": "Mean P(volunteer before EMS)"},
                    ax=ax,
                )
                ax.set_title(f"{env.capitalize()} | {pol}")
                ax.set_xlabel("Acceptance tier")
                ax.set_ylabel("Density level")
                ax.set_xticklabels([_pretty_acceptance(t.get_text()) for t in ax.get_xticklabels()], rotation=25)
                ax.set_yticklabels([_pretty_density(t.get_text()) for t in ax.get_yticklabels()], rotation=0)
        plt.suptitle("S3 | Main-grid sensitivity: acceptance and density effects", y=1.01)
        plt.tight_layout(rect=[0, 0, 0.90, 0.98])
        for _ax in fig.axes:
            _ax.set_title("")
        plt.savefig(out / "S3_acceptance_density_heatmaps_main.png", bbox_inches="tight")
        plt.savefig(out / "S3_acceptance_density_heatmaps_main.pdf", bbox_inches="tight")
        plt.close()

    if mode == "travel":
        # S4: Travel-speed x density sensitivity (heatmaps) for two selected policies.
        selected = ["GoodSAM", "Mobile Lifesaver"]
        fig, axes = plt.subplots(2, 2, figsize=(18, 11), sharex=False, sharey=False)
        cax = fig.add_axes([0.92, 0.18, 0.015, 0.64])
        for r, env in enumerate(ENV_ORDER):
            for c, pol in enumerate(selected):
                ax = axes[r, c]
                sub = run_df[
                    (run_df["environment"] == env)
                    & (run_df["policy"] == pol)
                    & (run_df["ems_label"] == "fixed")
                    & (run_df["acceptance_label"] == "acc_v3")
                ].copy()
                piv = sub.pivot_table(
                    index="density_label", columns="speed_label", values="cfr_beats_ems", aggfunc="mean"
                ).reindex(index=[x for x in DENSITY_ORDER if x in sub["density_label"].unique()],
                          columns=[x for x in TRAVEL_ORDER if x in sub["speed_label"].unique()])
                if piv.empty:
                    ax.set_visible(False)
                    continue
                sns.heatmap(
                    piv, annot=True, fmt=".2f", cmap="YlGnBu", vmin=0, vmax=1,
                    linewidths=0.4, linecolor="white", cbar=(r == 0 and c == 1),
                    cbar_ax=cax if (r == 0 and c == 1) else None,
                    cbar_kws={"label": "Mean P(volunteer before EMS)"},
                    ax=ax,
                )
                ax.set_title(f"{env.capitalize()} | {pol}")
                ax.set_xlabel("Travel-friction tier")
                ax.set_ylabel("Density level")
                ax.set_xticklabels([_pretty_travel(t.get_text()) for t in ax.get_xticklabels()], rotation=25)
                ax.set_yticklabels([_pretty_density(t.get_text()) for t in ax.get_yticklabels()], rotation=0)
        plt.suptitle("S4 | Travel and density sensitivity (acceptance fixed at ACC V3)", y=1.01)
        plt.tight_layout(rect=[0, 0, 0.90, 0.98])
        for _ax in fig.axes:
            _ax.set_title("")
        plt.savefig(out / "S4_travel_density_heatmaps_travel.png", bbox_inches="tight")
        plt.savefig(out / "S4_travel_density_heatmaps_travel.pdf", bbox_inches="tight")
        plt.close()


def save_environment_dashboard(
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    zoom: bool = False,
    show_ems_reference: bool = True,
    ems_benchmark: dict[str, dict[str, float]] | None = None,
) -> None:
    for env in ENV_ORDER:
        env_df = baseline_df[baseline_df["environment"] == env].copy()
        if env_df.empty:
            continue

        policy_order = _policy_order(env_df)
        policy_to_color = _policy_palette(policy_order)
        ems_mean = _ems_mean(ems_benchmark, env)

        fig, axes = plt.subplots(2, 2, figsize=(20, 12))

        ax = axes[0, 0]
        sns.ecdfplot(
            data=env_df,
            x="first_arrival_time",
            hue="policy",
            hue_order=policy_order,
            palette=policy_to_color,
            linewidth=2.0,
            ax=ax,
        )
        if show_ems_reference:
            ax.axvline(ems_mean, color="dimgray", linestyle=":", linewidth=2.0, label=f"EMS mean ({ems_mean:.1f} min)")
        ax.set_title("Distribution of first-arrival times")
        ax.set_xlabel("First-arrival time (minutes)")
        ax.set_ylabel("Cumulative proportion of events")
        if zoom:
            q1, q99 = env_df["first_arrival_time"].quantile([0.01, 0.99])
            pad = max(0.05 * float(q99 - q1), 0.05)
            ax.set_xlim(max(0, float(q1) - pad), float(q99) + pad)
        else:
            _partial_quantile_xlim(ax, env_df["first_arrival_time"])
        _place_legend_outside(ax, title="Policy")

        ax = axes[0, 1]
        sns.barplot(
            data=env_df,
            x="policy",
            y="first_arrival_time",
            order=policy_order,
            palette=policy_to_color,
            errorbar=("ci", 95),
            ax=ax,
        )
        if show_ems_reference:
            ax.axhline(ems_mean, color="dimgray", linestyle=":", linewidth=2.0)
        ax.set_title("Mean first-arrival time")
        ax.set_xlabel("Alerting policy")
        ax.set_ylabel("Mean first-arrival time (minutes)")
        ax.tick_params(axis="x", rotation=35)
        if zoom:
            _apply_zoom_limits(
                ax,
                env_df.groupby("policy")["first_arrival_time"].mean(),
                include=[ems_mean],
                pad_frac=0.18,
                min_pad=0.04,
            )

        ax = axes[1, 0]
        order_red = env_df.groupby("policy")["num_redundant"].mean().sort_values().index.tolist()
        sns.barplot(
            data=env_df,
            x="policy",
            y="num_redundant",
            order=order_red,
            palette=policy_to_color,
            errorbar=("ci", 95),
            ax=ax,
        )
        ax.set_title("Mean redundant arrivals")
        ax.set_xlabel("Alerting policy")
        ax.set_ylabel("Mean redundant arrivals per event")
        ax.tick_params(axis="x", rotation=35)
        if zoom:
            _apply_zoom_limits(
                ax,
                env_df.groupby("policy")["num_redundant"].mean(),
                pad_frac=0.15,
                min_pad=0.02,
                lower_zero=True,
            )

        ax = axes[1, 1]
        sns.barplot(
            data=env_df,
            x="policy",
            y="coverage_5",
            order=policy_order,
            palette=policy_to_color,
            errorbar=("ci", 95),
            ax=ax,
        )
        ax.set_title("Coverage within 5 minutes")
        ax.set_xlabel("Alerting policy")
        ax.set_ylabel("Proportion of events reached within 5 minutes")
        ax.tick_params(axis="x", rotation=35)
        if zoom:
            _apply_zoom_limits(
                ax,
                env_df.groupby("policy")["coverage_5"].mean(),
                pad_frac=0.18,
                min_pad=0.02,
                lower_zero=True,
            )

        plt.suptitle(
            f"{mode.capitalize()} | {env.capitalize()} | Baseline dashboard "
            f"(dashed vertical: EMS mean ≈ {_ems_mean(ems_benchmark, env):.1f} min for this env)",
            y=1.02,
            fontsize=14,
        )
        plt.tight_layout(rect=[0, 0, 0.86, 1])

        fname = (
            f"01_dashboard_{mode}_{env}_baseline_zoom.png"
            if zoom else
            f"01_dashboard_{mode}_{env}_baseline.png"
        )
        plt.savefig(out / fname, bbox_inches="tight")
        plt.close()


def save_tradeoff_and_burden_figure(
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    zoom: bool = False,
    ems_benchmark: dict[str, dict[str, float]] | None = None,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(19, 7), sharex=False, sharey=False)

    for i, env in enumerate(ENV_ORDER):
        env_df = baseline_df[baseline_df["environment"] == env].copy()
        if env_df.empty:
            axes[i].set_visible(False)
            continue

        policy_order = _policy_order(env_df)
        policy_to_color = _policy_palette(policy_order)
        trade = env_df.groupby("policy", as_index=False).agg(
            first_arrival_time=("first_arrival_time", "mean"),
            num_redundant=("num_redundant", "mean"),
            coverage_5=("coverage_5", "mean"),
            num_alerted=("num_alerted", "mean"),
        )

        sns.scatterplot(
            data=trade,
            x="num_redundant",
            y="first_arrival_time",
            hue="policy",
            hue_order=policy_order,
            palette=policy_to_color,
            size="coverage_5",
            sizes=(180, 950),
            alpha=0.9,
            edgecolor="black",
            linewidth=0.3,
            ax=axes[i],
        )
        axes[i].axhline(_ems_mean(ems_benchmark, env), color="dimgray", linestyle=":", linewidth=2.0)
        axes[i].set_title(f"{env.capitalize()}: speed–redundancy trade-off")
        axes[i].set_xlabel("Mean redundant arrivals per event")
        axes[i].set_ylabel("Mean first-arrival time (minutes)")
        _place_legend_outside(axes[i], title="Policy")

        if zoom:
            yvals = pd.concat(
                [trade["first_arrival_time"], pd.Series([_ems_mean(ems_benchmark, env)])],
                ignore_index=True,
            )
            xlo, xhi = _tight_limits(trade["num_redundant"], pad_frac=0.12, min_pad=0.02)
            ylo, yhi = _tight_limits(yvals, pad_frac=0.12, min_pad=0.04)
            axes[i].set_xlim(max(0, xlo), xhi)
            axes[i].set_ylim(ylo, yhi)

    plt.suptitle(f"{mode.capitalize()} | Baseline policy trade-off by environment", y=1.02, fontsize=16)
    plt.tight_layout(rect=[0, 0, 0.82, 1])
    fname = (
        f"02_tradeoff_compare_{mode}_baseline_zoom.png"
        if zoom else
        f"02_tradeoff_compare_{mode}_baseline.png"
    )
    plt.savefig(out / fname, bbox_inches="tight")
    plt.close()


def save_race_outcome_figure(
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    zoom: bool = False,
) -> None:
    """
    P(CFR arrives before EMS) and mean first-volunteer arrival (when any accept),
    decomposing the min(volunteer, EMS) outcome metric.
    """
    fig, axes = plt.subplots(2, 2, figsize=(20, 12))

    for i, env in enumerate(ENV_ORDER):
        env_df = baseline_df[baseline_df["environment"] == env].copy()
        if env_df.empty:
            axes[0, i].set_visible(False)
            axes[1, i].set_visible(False)
            continue

        policy_order = _policy_order(env_df)
        policy_to_color = _policy_palette(policy_order)

        ax = axes[0, i]
        sns.barplot(
            data=env_df,
            x="policy",
            y="cfr_beats_ems",
            order=policy_order,
            palette=[policy_to_color[p] for p in policy_order],
            errorbar=("ci", 95),
            ax=ax,
        )
        ax.set_title(f"{env.capitalize()}: P(CFR before EMS)")
        ax.set_xlabel("Alerting policy")
        ax.set_ylabel("Share of events where volunteer min < EMS time")
        ax.tick_params(axis="x", rotation=35)
        ax.set_ylim(0, 1.05)
        if zoom:
            _apply_zoom_limits(
                ax,
                env_df.groupby("policy")["cfr_beats_ems"].mean(),
                pad_frac=0.2,
                min_pad=0.02,
                lower_zero=True,
            )

        ax = axes[1, i]
        sub_fv = env_df[env_df["policy"] != "EMS only"].copy()
        po2 = [p for p in policy_order if p != "EMS only"]
        sns.barplot(
            data=sub_fv,
            x="policy",
            y="first_volunteer_arrival",
            order=po2,
            palette=[policy_to_color[p] for p in po2],
            errorbar=("ci", 95),
            ax=ax,
        )
        ax.set_title(f"{env.capitalize()}: mean first volunteer arrival (if any accept)")
        ax.set_xlabel("Alerting policy")
        ax.set_ylabel("Minutes (run-mean of event means; NaNs ignored)")
        ax.tick_params(axis="x", rotation=35)
        if zoom:
            _apply_zoom_limits(
                ax,
                sub_fv.groupby("policy")["first_volunteer_arrival"].mean(),
                pad_frac=0.18,
                min_pad=0.04,
            )

    plt.suptitle(
        f"{mode.capitalize()} | Race decomposition (baseline scenario)",
        y=1.02,
        fontsize=16,
    )
    plt.tight_layout(rect=[0, 0, 0.88, 1])
    fname = f"08_race_outcomes_{mode}_baseline_zoom.png" if zoom else f"08_race_outcomes_{mode}_baseline.png"
    plt.savefig(out / fname, bbox_inches="tight")
    plt.close()


def save_delta_vs_ems_only_figure(
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    zoom: bool = False,
) -> None:
    """Mean first-arrival minus EMS-only policy (same env), highlighting incremental alerting value."""
    rows: list[dict] = []
    for env in ENV_ORDER:
        env_df = baseline_df[baseline_df["environment"] == env]
        if env_df.empty:
            continue
        ems_only = env_df[env_df["policy"] == "EMS only"]
        if ems_only.empty:
            continue
        ref = ems_only["first_arrival_time"].mean()
        for pol in env_df["policy"].unique():
            m = env_df[env_df["policy"] == pol]["first_arrival_time"].mean()
            rows.append(
                {
                    "environment": env,
                    "policy": pol,
                    "delta_first_arrival_vs_ems_only": float(m - ref),
                }
            )

    delta_df = pd.DataFrame(rows)
    if delta_df.empty:
        return

    fig, axes = plt.subplots(1, 2, figsize=(18, 7), sharey=False)

    for i, env in enumerate(ENV_ORDER):
        sub = delta_df[delta_df["environment"] == env].copy()
        if sub.empty:
            axes[i].set_visible(False)
            continue
        pol_order = sub.groupby("policy")["delta_first_arrival_vs_ems_only"].mean().sort_values().index.tolist()
        palette = _policy_palette(pol_order)

        ax = axes[i]
        sns.barplot(
            data=sub,
            x="policy",
            y="delta_first_arrival_vs_ems_only",
            order=pol_order,
            palette=[palette[p] for p in pol_order],
            ax=ax,
        )
        ax.axhline(0, color="black", linewidth=1.2)
        ax.set_title(f"{env.capitalize()}: Δ mean first-arrival vs EMS-only")
        ax.set_xlabel("Alerting policy")
        ax.set_ylabel("Minutes (negative = faster than EMS-only baseline)")
        ax.tick_params(axis="x", rotation=35)
        if zoom:
            _apply_zoom_limits(
                ax,
                sub["delta_first_arrival_vs_ems_only"],
                include=[0.0],
                pad_frac=0.2,
                min_pad=0.02,
            )

    plt.suptitle(
        f"{mode.capitalize()} | Incremental first-arrival vs alerting no volunteers",
        y=1.02,
        fontsize=16,
    )
    plt.tight_layout(rect=[0, 0, 0.88, 1])
    for _ax in fig.axes:
        _ax.set_title("")
    fname = f"09_delta_vs_ems_only_{mode}_baseline_zoom.png" if zoom else f"09_delta_vs_ems_only_{mode}_baseline.png"
    plt.savefig(out / fname, bbox_inches="tight")
    plt.savefig(out / fname.replace(".png", ".pdf"), bbox_inches="tight")
    plt.close()


def save_cfr_beats_ecdf_baseline(
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    zoom: bool = False,
) -> None:
    """ECDF of run-level P(volunteer before EMS) across Monte Carlo replications."""
    fig, axes = plt.subplots(1, 2, figsize=(18, 7), sharey=False)

    for i, env in enumerate(ENV_ORDER):
        env_df = baseline_df[baseline_df["environment"] == env].copy()
        ax = axes[i]
        if env_df.empty:
            ax.set_visible(False)
            continue

        policy_order = _policy_order(env_df)
        policy_to_color = _policy_palette(policy_order)
        sns.ecdfplot(
            data=env_df,
            x="cfr_beats_ems",
            hue="policy",
            hue_order=policy_order,
            palette=[policy_to_color[p] for p in policy_order],
            linewidth=2.0,
            ax=ax,
        )
        ax.axvline(0.5, color="gray", linestyle="--", linewidth=1.0, alpha=0.7)
        ax.set_title(f"{env.capitalize()}: volunteer-before-EMS rate (run-level means)")
        ax.set_xlabel("P(CFR before EMS) per replication")
        ax.set_ylabel("Cumulative proportion of runs")
        ax.set_xlim(0, 1.05)
        _place_legend_outside(ax, title="Policy")
        if zoom:
            q1, q99 = env_df["cfr_beats_ems"].quantile([0.01, 0.99])
            pad = max(0.02, 0.05 * float(q99 - q1))
            ax.set_xlim(max(0, q1 - pad), min(1.0, q99 + pad))

    plt.suptitle(
        f"{mode.capitalize()} | ECDF of volunteer-before-EMS rate (baseline scenario)",
        y=1.02,
        fontsize=16,
    )
    plt.tight_layout(rect=[0, 0, 0.82, 1])
    fname = f"10_cfr_beats_ecdf_baseline_{mode}_zoom.png" if zoom else f"10_cfr_beats_ecdf_baseline_{mode}.png"
    plt.savefig(out / fname, bbox_inches="tight")
    plt.close()


def save_cfr_beats_heatmaps(
    run_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    zoom: bool = False,
) -> None:
    """Heatmaps of mean P(volunteer before EMS): main = density × acceptance; travel = speed × policy."""
    top_policies = (
        baseline_df.groupby("policy")["first_arrival_time"].mean().sort_values().head(3).index.tolist()
    )
    print("Top policies for CFR-beats heatmaps (by baseline first-arrival):", top_policies)
    suffix = "_zoom" if zoom else ""

    if mode == "main":
        for env in ENV_ORDER:
            for pol in top_policies:
                sub = run_df[
                    (run_df["environment"] == env)
                    & (run_df["policy"] == pol)
                    & (run_df["ems_label"] == "fixed")
                    & (run_df["speed_label"] == "baseline")
                ].copy()
                if sub.empty:
                    continue

                piv = sub.pivot_table(
                    index="density_label",
                    columns="acceptance_label",
                    values="cfr_beats_ems",
                    aggfunc="mean",
                )
                piv = piv.reindex(
                    index=[x for x in DENSITY_ORDER if x in piv.index],
                    columns=[x for x in ACCEPTANCE_ORDER if x in piv.columns],
                )
                if piv.empty:
                    continue

                plt.figure(figsize=(9, 5))
                sns.heatmap(
                    piv,
                    annot=True,
                    fmt=".2f",
                    cmap="YlGnBu",
                    vmin=0,
                    vmax=1,
                    linewidths=0.4,
                    linecolor="white",
                    cbar_kws={"shrink": 0.85, "label": "Mean P(vol before EMS)"},
                )
                plt.title(f"{env.capitalize()} | {pol}\nMean volunteer-before-EMS rate")
                plt.xlabel("Acceptance setting")
                plt.ylabel("Density setting")
                plt.gca().set_xticklabels(
                    [_pretty_acceptance(t.get_text()) for t in plt.gca().get_xticklabels()],
                    rotation=25,
                )
                plt.gca().set_yticklabels(
                    [_pretty_density(t.get_text()) for t in plt.gca().get_yticklabels()],
                    rotation=0,
                )
                plt.tight_layout()
                plt.savefig(
                    out / f"11_cfr_beats_heatmap_main_{env}_{pol.replace(' ', '_')}{suffix}.png",
                    bbox_inches="tight",
                )
                plt.close()

    else:
        for env in ENV_ORDER:
            sub = run_df[
                (run_df["environment"] == env)
                & (run_df["ems_label"] == "fixed")
                & (run_df["acceptance_label"] == "acc_v3")
                & (run_df["density_label"] == "low")
                & (run_df["speed_label"].isin(TRAVEL_ORDER))
            ].copy()
            if sub.empty:
                continue

            piv = sub.pivot_table(
                index="speed_label",
                columns="policy",
                values="cfr_beats_ems",
                aggfunc="mean",
            )
            piv = piv.reindex(index=[x for x in TRAVEL_ORDER if x in piv.index])
            if piv.empty:
                continue

            plt.figure(figsize=(12, 5))
            sns.heatmap(
                piv,
                annot=True,
                fmt=".2f",
                cmap="YlGnBu",
                vmin=0,
                vmax=1,
                linewidths=0.4,
                linecolor="white",
                cbar_kws={"shrink": 0.85, "label": "Mean P(vol before EMS)"},
            )
            plt.title(f"{env.capitalize()} | Mean volunteer-before-EMS rate (travel friction × policy)")
            plt.xlabel("Policy")
            plt.ylabel("Travel-friction setting")
            plt.gca().set_yticklabels(
                [_pretty_travel(t.get_text()) for t in plt.gca().get_yticklabels()],
                rotation=0,
            )
            plt.tight_layout()
            plt.savefig(out / f"11_cfr_beats_heatmap_travel_{env}{suffix}.png", bbox_inches="tight")
            plt.close()


def save_cfr_beats_main_trend_lines(
    run_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    out: Path,
    zoom: bool = False,
) -> None:
    """Sensitivity of volunteer-before-EMS rate to density and acceptance (main grid)."""
    top_policies = (
        baseline_df.groupby("policy")["first_arrival_time"].mean().sort_values().head(3).index.tolist()
    )

    for env in ENV_ORDER:
        sub = run_df[
            (run_df["environment"] == env)
            & (run_df["ems_label"] == "fixed")
            & (run_df["speed_label"] == "baseline")
            & (run_df["policy"].isin(top_policies))
        ].copy()
        if sub.empty:
            continue

        fig, axes = plt.subplots(1, 2, figsize=(17, 6), sharex=False)

        density_sub = sub[sub["acceptance_label"] == "acc_v3"].copy()
        sns.lineplot(
            data=density_sub,
            x="density_label",
            y="cfr_beats_ems",
            hue="policy",
            hue_order=top_policies,
            marker="o",
            errorbar=("ci", 95),
            ax=axes[0],
        )
        axes[0].set_title(f"{env.capitalize()}: volunteer-before-EMS vs density (acceptance ACC V3)")
        axes[0].set_xlabel("Density setting")
        axes[0].set_ylabel("Mean P(CFR before EMS)")
        axes[0].set_xticks(range(len(DENSITY_ORDER)))
        axes[0].set_xticklabels([_pretty_density(x) for x in DENSITY_ORDER], rotation=25)
        axes[0].set_xlim(-0.1, len(DENSITY_ORDER) - 0.9)
        axes[0].set_ylim(0, 1.05)
        _place_legend_outside(axes[0], title="Policy")

        acc_sub = sub[sub["density_label"] == "low"].copy()
        sns.lineplot(
            data=acc_sub,
            x="acceptance_label",
            y="cfr_beats_ems",
            hue="policy",
            hue_order=top_policies,
            marker="o",
            errorbar=("ci", 95),
            legend=False,
            ax=axes[1],
        )
        axes[1].set_title(f"{env.capitalize()}: volunteer-before-EMS vs acceptance (density low)")
        axes[1].set_xlabel("Acceptance setting")
        axes[1].set_ylabel("Mean P(CFR before EMS)")
        axes[1].set_xticks(range(len(ACCEPTANCE_ORDER)))
        axes[1].set_xticklabels([_pretty_acceptance(x) for x in ACCEPTANCE_ORDER], rotation=25)
        axes[1].set_xlim(-0.1, len(ACCEPTANCE_ORDER) - 0.9)
        axes[1].set_ylim(0, 1.05)

        if zoom:
            _apply_zoom_limits(
                axes[0],
                density_sub.groupby(["policy", "density_label"])["cfr_beats_ems"].mean(),
                pad_frac=0.15,
                min_pad=0.02,
                lower_zero=True,
            )
            _apply_zoom_limits(
                axes[1],
                acc_sub.groupby(["policy", "acceptance_label"])["cfr_beats_ems"].mean(),
                pad_frac=0.15,
                min_pad=0.02,
                lower_zero=True,
            )

        plt.suptitle(f"Main grid | volunteer-before-EMS rate | {env.capitalize()}", y=1.02)
        plt.tight_layout(rect=[0, 0, 0.85, 1])
        suffix = "_zoom" if zoom else ""
        plt.savefig(out / f"12_cfr_beats_main_trends_{env}{suffix}.png", bbox_inches="tight")
        plt.close()


def save_cfr_beats_travel_trend_lines(
    run_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    out: Path,
    zoom: bool = False,
) -> None:
    """Volunteer-before-EMS rate vs travel friction (travel grid)."""
    top_policies = (
        baseline_df.groupby("policy")["first_arrival_time"].mean().sort_values().head(3).index.tolist()
    )

    for env in ENV_ORDER:
        sub = run_df[
            (run_df["environment"] == env)
            & (run_df["ems_label"] == "fixed")
            & (run_df["acceptance_label"] == "acc_v3")
            & (run_df["density_label"] == "low")
            & (run_df["speed_label"].isin(TRAVEL_ORDER))
            & (run_df["policy"].isin(top_policies))
        ].copy()
        if sub.empty:
            continue

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.lineplot(
            data=sub,
            x="speed_label",
            y="cfr_beats_ems",
            hue="policy",
            hue_order=top_policies,
            marker="o",
            errorbar=("ci", 95),
            ax=ax,
        )
        ax.set_title(
            f"{env.capitalize()}: volunteer-before-EMS vs travel friction "
            f"(density low, acceptance ACC V3)"
        )
        ax.set_xlabel("Travel-friction setting")
        ax.set_ylabel("Mean P(CFR before EMS)")
        ax.set_xticks(range(len(TRAVEL_ORDER)))
        ax.set_xticklabels([_pretty_travel(x) for x in TRAVEL_ORDER], rotation=25)
        ax.set_xlim(-0.1, len(TRAVEL_ORDER) - 0.9)
        ax.set_ylim(0, 1.05)
        _place_legend_outside(ax, title="Policy")
        if zoom:
            _apply_zoom_limits(
                ax,
                sub.groupby(["policy", "speed_label"])["cfr_beats_ems"].mean(),
                pad_frac=0.15,
                min_pad=0.02,
                lower_zero=True,
            )

        plt.suptitle("Travel grid | volunteer-before-EMS rate", y=1.02)
        plt.tight_layout(rect=[0, 0, 0.82, 1])
        suffix = "_zoom" if zoom else ""
        plt.savefig(out / f"12_cfr_beats_travel_trends_{env}{suffix}.png", bbox_inches="tight")
        plt.close()


def save_travel_cfr_beats_barplot(
    run_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    out: Path,
    zoom: bool = False,
) -> None:
    """Grouped bars: P(volunteer before EMS) vs travel friction, by policy (top policies at baseline)."""
    top_policies = (
        baseline_df.groupby("policy")["first_arrival_time"].mean().sort_values().head(5).index.tolist()
    )
    fig, axes = plt.subplots(1, 2, figsize=(20, 7), sharey=True)

    for col, env in enumerate(ENV_ORDER):
        sub = run_df[
            (run_df["environment"] == env)
            & (run_df["ems_label"] == "fixed")
            & (run_df["acceptance_label"] == "acc_v3")
            & (run_df["density_label"] == "low")
            & (run_df["speed_label"].isin(TRAVEL_ORDER))
            & (run_df["policy"].isin(top_policies))
        ].copy()
        ax = axes[col]
        if sub.empty:
            ax.set_visible(False)
            continue

        policy_to_color = _policy_palette(top_policies)
        sns.barplot(
            data=sub,
            x="speed_label",
            y="cfr_beats_ems",
            hue="policy",
            order=TRAVEL_ORDER,
            hue_order=top_policies,
            palette=[policy_to_color[p] for p in top_policies],
            errorbar=("ci", 95),
            ax=ax,
        )
        ax.set_title(f"{env.capitalize()}: P(CFR before EMS) vs travel friction")
        ax.set_xlabel("Travel-friction setting")
        ax.set_ylabel("Mean P(volunteer before EMS)")
        ax.set_xticklabels([_pretty_travel(x.get_text()) for x in ax.get_xticklabels()], rotation=25)
        ax.set_ylim(0, 1.05)
        _place_legend_outside(ax, title="Policy")
        if zoom:
            _apply_zoom_limits(
                ax,
                sub.groupby(["speed_label", "policy"])["cfr_beats_ems"].mean(),
                pad_frac=0.18,
                min_pad=0.02,
                lower_zero=True,
            )

    plt.suptitle(
        "Travel sensitivity: volunteer-before-EMS rate — top 5 policies by baseline first-arrival",
        y=1.02,
        fontsize=16,
    )
    plt.tight_layout(rect=[0, 0, 0.78, 1])
    fname = "13_travel_cfr_beats_bars_zoom.png" if zoom else "13_travel_cfr_beats_bars.png"
    plt.savefig(out / fname, bbox_inches="tight")
    plt.close()


def save_cfr_beats_violin_baseline(
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    zoom: bool = False,
) -> None:
    """Violin: distribution of run-level volunteer-before-EMS rate by policy."""
    for env in ENV_ORDER:
        env_df = baseline_df[baseline_df["environment"] == env].copy()
        if env_df.empty:
            continue

        plt.figure(figsize=(12, 6))
        sns.violinplot(data=env_df, x="policy", y="cfr_beats_ems", inner="quart", cut=0)
        plt.title(f"{mode.capitalize()} | {env.capitalize()} | Volunteer-before-EMS rate (baseline)")
        plt.xlabel("Alerting policy")
        plt.ylabel("P(CFR before EMS) per replication")
        plt.xticks(rotation=35, ha="right")
        plt.ylim(0, 1.05)
        if zoom:
            _apply_zoom_limits(
                plt.gca(),
                env_df.groupby("policy")["cfr_beats_ems"].mean(),
                pad_frac=0.15,
                min_pad=0.02,
                lower_zero=True,
            )
        plt.tight_layout()
        suffix = "_zoom" if zoom else ""
        plt.savefig(out / f"A2_violin_cfr_beats_baseline_{mode}_{env}{suffix}.png", bbox_inches="tight")
        plt.close()


def save_cfr_beats_scenario_tables(run_df: pd.DataFrame, out: Path, mode: str) -> None:
    """Export best/worst scenarios by mean volunteer-before-EMS rate."""
    scenario_cols = ["policy", "environment", "ems_label", "acceptance_label", "density_label", "speed_label"]
    scenario_avg = run_df.groupby(scenario_cols, as_index=False).agg(
        mean_cfr_beats_ems=("cfr_beats_ems", "mean"),
        mean_first_arrival=("first_arrival_time", "mean"),
    )
    scenario_avg.nlargest(15, "mean_cfr_beats_ems").to_csv(
        out / f"A4_top15_scenarios_cfr_beats_ems_{mode}.csv",
        index=False,
    )
    scenario_avg.nsmallest(15, "mean_cfr_beats_ems").to_csv(
        out / f"A4_bottom15_scenarios_cfr_beats_ems_{mode}.csv",
        index=False,
    )


def save_cross_ems_comparison_figure(
    baseline_a: pd.DataFrame,
    baseline_b: pd.DataFrame,
    label_a: str,
    label_b: str,
    out: Path,
    mode: str,
    zoom: bool = False,
) -> None:
    """
    Overlay two baseline slices that differ only by EMS calibration (separate result folders).
    Top row: first-arrival ECDF; bottom row: P(CFR before EMS) ECDF.
    """
    df = pd.concat(
        [
            baseline_a.assign(EMS_calibration=label_a),
            baseline_b.assign(EMS_calibration=label_b),
        ],
        ignore_index=True,
    )

    fig, axes = plt.subplots(2, 2, figsize=(20, 14))

    for row, (metric, xlab) in enumerate(
        [
            ("first_arrival_time", "First-arrival time (minutes)"),
            ("cfr_beats_ems", "P(CFR before EMS) per replication"),
        ]
    ):
        for col, env in enumerate(ENV_ORDER):
            ax = axes[row, col]
            sub = df[df["environment"] == env]
            if sub.empty:
                ax.set_visible(False)
                continue

            policy_order = _policy_order(sub)
            sns.ecdfplot(
                data=sub,
                x=metric,
                hue="policy",
                hue_order=policy_order,
                style="EMS_calibration",
                linewidth=2.0,
                ax=ax,
            )
            if metric == "cfr_beats_ems":
                ax.set_xlim(0, 1.05)
            else:
                if zoom:
                    q1, q99 = sub[metric].quantile([0.01, 0.99])
                    pad = max(0.05 * float(q99 - q1), 0.05)
                    ax.set_xlim(max(0, float(q1) - pad), float(q99) + pad)
                else:
                    _partial_quantile_xlim(ax, sub[metric])
            ax.set_title(f"{env.capitalize()} | {metric.replace('_', ' ')}")
            ax.set_xlabel(xlab)
            ax.set_ylabel("Cumulative proportion of runs")
            _place_legend_outside(ax, title="Policy / EMS")

    plt.suptitle(
        f"{mode.capitalize()} | Cross-EMS comparison at baseline slice\n"
        f"{label_a} vs {label_b}",
        y=1.01,
        fontsize=14,
    )
    plt.tight_layout(rect=[0, 0, 0.82, 0.97])
    suffix = "_zoom" if zoom else ""
    plt.savefig(out / f"00_compare_ems_cases_{mode}_baseline{suffix}.png", bbox_inches="tight")
    plt.close()


def save_travel_sensitivity_figure(
    run_df: pd.DataFrame,
    out: Path,
    zoom: bool = False,
    ems_benchmark: dict[str, dict[str, float]] | None = None,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 12), sharex=True)

    for col, env in enumerate(ENV_ORDER):
        sub = run_df[
            (run_df["environment"] == env)
            & (run_df["ems_label"] == "fixed")
            & (run_df["acceptance_label"] == "acc_v3")
            & (run_df["density_label"] == "low")
            & (run_df["speed_label"].isin(TRAVEL_ORDER))
        ].copy()

        if sub.empty:
            axes[0, col].set_visible(False)
            axes[1, col].set_visible(False)
            continue

        ax = axes[0, col]
        sns.barplot(
            data=sub,
            x="speed_label",
            y="first_arrival_time",
            order=TRAVEL_ORDER,
            errorbar=("ci", 95),
            ax=ax,
        )
        ax.axhline(_ems_mean(ems_benchmark, env), color="dimgray", linestyle=":", linewidth=2.0)
        ax.set_title(f"{env.capitalize()}: first-arrival time vs travel friction")
        ax.set_xlabel("")
        ax.set_ylabel("Mean first-arrival time (minutes)")
        ax.set_xticklabels([_pretty_travel(x.get_text()) for x in ax.get_xticklabels()], rotation=25)
        if zoom:
            _apply_zoom_limits(
                ax,
                sub.groupby("speed_label")["first_arrival_time"].mean(),
                include=[_ems_mean(ems_benchmark, env)],
                pad_frac=0.18,
                min_pad=0.04,
            )

        ax = axes[1, col]
        sns.barplot(
            data=sub,
            x="speed_label",
            y="coverage_5",
            order=TRAVEL_ORDER,
            errorbar=("ci", 95),
            ax=ax,
        )
        ax.set_title(f"{env.capitalize()}: early coverage vs travel friction")
        ax.set_xlabel("Travel-friction setting")
        ax.set_ylabel("Proportion of events reached within 5 minutes")
        ax.set_xticklabels([_pretty_travel(x.get_text()) for x in ax.get_xticklabels()], rotation=25)
        if zoom:
            _apply_zoom_limits(
                ax,
                sub.groupby("speed_label")["coverage_5"].mean(),
                pad_frac=0.18,
                min_pad=0.02,
                lower_zero=True,
            )

    plt.suptitle("Travel sensitivity at baseline acceptance, density, and EMS setting", y=1.02, fontsize=16)
    plt.tight_layout()
    fname = "03_travel_sensitivity_dashboard_zoom.png" if zoom else "03_travel_sensitivity_dashboard.png"
    plt.savefig(out / fname, bbox_inches="tight")
    plt.close()


def save_sensitivity_heatmaps(
    run_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    zoom: bool = False,
) -> None:
    top_policies = (
        baseline_df.groupby("policy")["first_arrival_time"].mean().sort_values().head(3).index.tolist()
    )
    print("Top baseline policies by first-arrival-time:", top_policies)

    for env in ENV_ORDER:
        for pol in top_policies:
            sub = run_df[
                (run_df["environment"] == env)
                & (run_df["policy"] == pol)
                & (run_df["ems_label"] == "fixed")
            ].copy()

            if mode == "main":
                sub = sub[sub["speed_label"] == "baseline"]
                piv_arr = sub.pivot_table(
                    index="density_label",
                    columns="acceptance_label",
                    values="first_arrival_time",
                    aggfunc="mean",
                )
                piv_red = sub.pivot_table(
                    index="density_label",
                    columns="acceptance_label",
                    values="num_redundant",
                    aggfunc="mean",
                )

                piv_arr = piv_arr.reindex(
                    index=[x for x in DENSITY_ORDER if x in piv_arr.index],
                    columns=[x for x in ACCEPTANCE_ORDER if x in piv_arr.columns],
                )
                piv_red = piv_red.reindex(
                    index=[x for x in DENSITY_ORDER if x in piv_red.index],
                    columns=[x for x in ACCEPTANCE_ORDER if x in piv_red.columns],
                )

                fig, axes = plt.subplots(1, 2, figsize=(15, 5))
                sns.heatmap(
                    piv_arr, annot=True, fmt=".2f", cmap="viridis_r",
                    linewidths=0.4, linecolor="white", cbar_kws={"shrink": 0.85}, ax=axes[0]
                )
                axes[0].set_title(f"{env.capitalize()} | {pol}\nMean first-arrival time")
                axes[0].set_xlabel("Acceptance setting")
                axes[0].set_ylabel("Density setting")
                axes[0].set_xticklabels([_pretty_acceptance(t.get_text()) for t in axes[0].get_xticklabels()], rotation=25)
                axes[0].set_yticklabels([_pretty_density(t.get_text()) for t in axes[0].get_yticklabels()], rotation=0)

                sns.heatmap(
                    piv_red, annot=True, fmt=".2f", cmap="magma",
                    linewidths=0.4, linecolor="white", cbar_kws={"shrink": 0.85}, ax=axes[1]
                )
                axes[1].set_title(f"{env.capitalize()} | {pol}\nMean redundant arrivals")
                axes[1].set_xlabel("Acceptance setting")
                axes[1].set_ylabel("Density setting")
                axes[1].set_xticklabels([_pretty_acceptance(t.get_text()) for t in axes[1].get_xticklabels()], rotation=25)
                axes[1].set_yticklabels([_pretty_density(t.get_text()) for t in axes[1].get_yticklabels()], rotation=0)

                plt.tight_layout()
                suffix = "_zoom" if zoom else ""
                plt.savefig(
                    out / f"04_heatmaps_main_{env}_{pol.replace(' ', '_')}{suffix}.png",
                    bbox_inches="tight",
                )
                plt.close()

            else:
                sub = sub[
                    (sub["acceptance_label"] == "acc_v3")
                    & (sub["density_label"] == "low")
                    & (sub["speed_label"].isin(TRAVEL_ORDER))
                ]

                piv_arr = sub.pivot_table(
                    index="speed_label",
                    columns="policy",
                    values="first_arrival_time",
                    aggfunc="mean",
                )

                if piv_arr.empty:
                    continue

                piv_arr = piv_arr.reindex(index=[x for x in TRAVEL_ORDER if x in piv_arr.index])

                plt.figure(figsize=(10, 5))
                sns.heatmap(
                    piv_arr,
                    annot=True,
                    fmt=".2f",
                    cmap="viridis_r",
                    linewidths=0.4,
                    linecolor="white",
                    cbar_kws={"shrink": 0.85},
                )
                plt.title(f"{env.capitalize()} | Mean first-arrival time across travel friction")
                plt.xlabel("Policy")
                plt.ylabel("Travel-friction setting")
                plt.gca().set_yticklabels([_pretty_travel(t.get_text()) for t in plt.gca().get_yticklabels()], rotation=0)
                plt.tight_layout()
                suffix = "_zoom" if zoom else ""
                plt.savefig(
                    out / f"04_heatmap_travel_first_arrival_{env}{suffix}.png",
                    bbox_inches="tight",
                )
                plt.close()


def save_main_sensitivity_trend_lines(
    run_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    out: Path,
    zoom: bool = False,
    ems_benchmark: dict[str, dict[str, float]] | None = None,
) -> None:
    top_policies = (
        baseline_df.groupby("policy")["first_arrival_time"].mean().sort_values().head(3).index.tolist()
    )

    for env in ENV_ORDER:
        sub = run_df[
            (run_df["environment"] == env)
            & (run_df["ems_label"] == "fixed")
            & (run_df["speed_label"] == "baseline")
            & (run_df["policy"].isin(top_policies))
        ].copy()

        if sub.empty:
            continue

        # 1) Density trends at fixed acceptance = acc_v3
        density_sub = sub[sub["acceptance_label"] == "acc_v3"].copy()

        fig, axes = plt.subplots(1, 2, figsize=(17, 6), sharex=True)

        sns.lineplot(
            data=density_sub,
            x="density_label",
            y="first_arrival_time",
            hue="policy",
            hue_order=top_policies,
            marker="o",
            errorbar=("ci", 95),
            ax=axes[0],
        )
        axes[0].set_title(f"{env.capitalize()}: effect of density on first-arrival time")
        axes[0].set_xlabel("Density setting")
        axes[0].set_ylabel("Mean first-arrival time (minutes)")
        axes[0].set_xticks(range(len(DENSITY_ORDER)))
        axes[0].set_xticklabels([_pretty_density(x) for x in DENSITY_ORDER], rotation=25)
        axes[0].set_xlim(-0.1, len(DENSITY_ORDER) - 0.9)
        axes[0].axhline(_ems_mean(ems_benchmark, env), color="dimgray", linestyle=":", linewidth=2.0)
        _place_legend_outside(axes[0], title="Policy")

        sns.lineplot(
            data=density_sub,
            x="density_label",
            y="coverage_5",
            hue="policy",
            hue_order=top_policies,
            marker="o",
            errorbar=("ci", 95),
            legend=False,
            ax=axes[1],
        )
        axes[1].set_title(f"{env.capitalize()}: effect of density on 5-minute coverage")
        axes[1].set_xlabel("Density setting")
        axes[1].set_ylabel("Proportion of events reached within 5 minutes")
        axes[1].set_xticks(range(len(DENSITY_ORDER)))
        axes[1].set_xticklabels([_pretty_density(x) for x in DENSITY_ORDER], rotation=25)
        axes[1].set_xlim(-0.1, len(DENSITY_ORDER) - 0.9)

        if zoom:
            _apply_zoom_limits(
                axes[0],
                density_sub.groupby(["policy", "density_label"])["first_arrival_time"].mean(),
                include=[_ems_mean(ems_benchmark, env)],
                pad_frac=0.18,
                min_pad=0.04,
            )
            _apply_zoom_limits(
                axes[1],
                density_sub.groupby(["policy", "density_label"])["coverage_5"].mean(),
                pad_frac=0.18,
                min_pad=0.02,
                lower_zero=True,
            )

        plt.suptitle(f"Main sensitivity trends by density | {env.capitalize()} | Acceptance fixed at ACC V3", y=1.02)
        plt.tight_layout(rect=[0, 0, 0.85, 1])
        suffix = "_zoom" if zoom else ""
        plt.savefig(out / f"05_density_trends_{env}{suffix}.png", bbox_inches="tight")
        plt.close()

        # 2) Acceptance trends at fixed density = low
        acc_sub = sub[sub["density_label"] == "low"].copy()

        fig, axes = plt.subplots(1, 2, figsize=(17, 6), sharex=True)

        sns.lineplot(
            data=acc_sub,
            x="acceptance_label",
            y="first_arrival_time",
            hue="policy",
            hue_order=top_policies,
            marker="o",
            errorbar=("ci", 95),
            ax=axes[0],
        )
        axes[0].set_title(f"{env.capitalize()}: effect of acceptance on first-arrival time")
        axes[0].set_xlabel("Acceptance setting")
        axes[0].set_ylabel("Mean first-arrival time (minutes)")
        axes[0].set_xticks(range(len(ACCEPTANCE_ORDER)))
        axes[0].set_xticklabels([_pretty_acceptance(x) for x in ACCEPTANCE_ORDER], rotation=25)
        axes[0].set_xlim(-0.1, len(ACCEPTANCE_ORDER) - 0.9)
        axes[0].axhline(_ems_mean(ems_benchmark, env), color="dimgray", linestyle=":", linewidth=2.0)
        _place_legend_outside(axes[0], title="Policy")

        sns.lineplot(
            data=acc_sub,
            x="acceptance_label",
            y="coverage_5",
            hue="policy",
            hue_order=top_policies,
            marker="o",
            errorbar=("ci", 95),
            legend=False,
            ax=axes[1],
        )
        axes[1].set_title(f"{env.capitalize()}: effect of acceptance on 5-minute coverage")
        axes[1].set_xlabel("Acceptance setting")
        axes[1].set_ylabel("Proportion of events reached within 5 minutes")
        axes[1].set_xticks(range(len(ACCEPTANCE_ORDER)))
        axes[1].set_xticklabels([_pretty_acceptance(x) for x in ACCEPTANCE_ORDER], rotation=25)
        axes[1].set_xlim(-0.1, len(ACCEPTANCE_ORDER) - 0.9)

        if zoom:
            _apply_zoom_limits(
                axes[0],
                acc_sub.groupby(["policy", "acceptance_label"])["first_arrival_time"].mean(),
                include=[_ems_mean(ems_benchmark, env)],
                pad_frac=0.18,
                min_pad=0.04,
            )
            _apply_zoom_limits(
                axes[1],
                acc_sub.groupby(["policy", "acceptance_label"])["coverage_5"].mean(),
                pad_frac=0.18,
                min_pad=0.02,
                lower_zero=True,
            )

        plt.suptitle(f"Main sensitivity trends by acceptance | {env.capitalize()} | Density fixed at Low", y=1.02)
        plt.tight_layout(rect=[0, 0, 0.85, 1])
        plt.savefig(out / f"06_acceptance_trends_{env}{suffix}.png", bbox_inches="tight")
        plt.close()


def save_travel_sensitivity_trend_lines(
    run_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    out: Path,
    zoom: bool = False,
    ems_benchmark: dict[str, dict[str, float]] | None = None,
) -> None:
    top_policies = (
        baseline_df.groupby("policy")["first_arrival_time"].mean().sort_values().head(3).index.tolist()
    )

    for env in ENV_ORDER:
        sub = run_df[
            (run_df["environment"] == env)
            & (run_df["ems_label"] == "fixed")
            & (run_df["acceptance_label"] == "acc_v3")
            & (run_df["density_label"] == "low")
            & (run_df["speed_label"].isin(TRAVEL_ORDER))
            & (run_df["policy"].isin(top_policies))
        ].copy()

        if sub.empty:
            continue

        fig, axes = plt.subplots(1, 2, figsize=(17, 6), sharex=True)

        sns.lineplot(
            data=sub,
            x="speed_label",
            y="first_arrival_time",
            hue="policy",
            hue_order=top_policies,
            marker="o",
            errorbar=("ci", 95),
            ax=axes[0],
        )
        axes[0].set_title(f"{env.capitalize()}: effect of travel friction on first-arrival time")
        axes[0].set_xlabel("Travel-friction setting")
        axes[0].set_ylabel("Mean first-arrival time (minutes)")
        axes[0].set_xticks(range(len(TRAVEL_ORDER)))
        axes[0].set_xticklabels([_pretty_travel(x) for x in TRAVEL_ORDER], rotation=25)
        axes[0].set_xlim(-0.1, len(TRAVEL_ORDER) - 0.9)
        axes[0].axhline(_ems_mean(ems_benchmark, env), color="dimgray", linestyle=":", linewidth=2.0)
        _place_legend_outside(axes[0], title="Policy")

        sns.lineplot(
            data=sub,
            x="speed_label",
            y="coverage_5",
            hue="policy",
            hue_order=top_policies,
            marker="o",
            errorbar=("ci", 95),
            legend=False,
            ax=axes[1],
        )
        axes[1].set_title(f"{env.capitalize()}: effect of travel friction on 5-minute coverage")
        axes[1].set_xlabel("Travel-friction setting")
        axes[1].set_ylabel("Proportion of events reached within 5 minutes")
        axes[1].set_xticks(range(len(TRAVEL_ORDER)))
        axes[1].set_xticklabels([_pretty_travel(x) for x in TRAVEL_ORDER], rotation=25)
        axes[1].set_xlim(-0.1, len(TRAVEL_ORDER) - 0.9)

        if zoom:
            _apply_zoom_limits(
                axes[0],
                sub.groupby(["policy", "speed_label"])["first_arrival_time"].mean(),
                include=[_ems_mean(ems_benchmark, env)],
                pad_frac=0.18,
                min_pad=0.04,
            )
            _apply_zoom_limits(
                axes[1],
                sub.groupby(["policy", "speed_label"])["coverage_5"].mean(),
                pad_frac=0.18,
                min_pad=0.02,
                lower_zero=True,
            )

        plt.suptitle(f"Travel sensitivity trends | {env.capitalize()} | Density fixed at Low, Acceptance fixed at ACC V3", y=1.02)
        plt.tight_layout(rect=[0, 0, 0.85, 1])
        suffix = "_zoom" if zoom else ""
        plt.savefig(out / f"07_travel_trends_{env}{suffix}.png", bbox_inches="tight")
        plt.close()


def save_appendix_tables(
    run_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    out: Path,
    mode: str,
    zoom: bool = False,
) -> None:
    cov_aggs_app = {
        f"mean_coverage_le_{t}_min": (f"coverage_{t}", "mean")
        for t in COVERAGE_THRESHOLDS_MIN
    }
    summary = run_df.groupby(["environment", "policy"], as_index=False).agg(
        mean_first_arrival_minutes=("first_arrival_time", "mean"),
        sd_first_arrival_minutes=("first_arrival_time", "std"),
        mean_redundant_arrivals=("num_redundant", "mean"),
        sd_redundant_arrivals=("num_redundant", "std"),
        mean_alerted_responders=("num_alerted", "mean"),
        mean_accepted_responders=("num_accepted", "mean"),
        mean_cfr_beats_ems=("cfr_beats_ems", "mean"),
        mean_first_volunteer_arrival=("first_volunteer_arrival", "mean"),
        **cov_aggs_app,
    )
    summary.to_csv(out / f"table_policy_summary_fullgrid_by_environment_{mode}.csv", index=False)

    scenario_cols = ["policy", "environment", "ems_label", "acceptance_label", "density_label", "speed_label"]
    scenario_avg = run_df.groupby(scenario_cols, as_index=False).agg(
        mean_first_arrival_minutes=("first_arrival_time", "mean"),
        mean_redundant_arrivals=("num_redundant", "mean"),
        mean_cfr_beats_ems=("cfr_beats_ems", "mean"),
        mean_first_volunteer_arrival=("first_volunteer_arrival", "mean"),
        **cov_aggs_app,
    )
    scenario_avg.nsmallest(10, "mean_first_arrival_minutes").to_csv(
        out / f"A3_best10_scenarios_first_arrival_{mode}.csv", index=False
    )
    scenario_avg.nlargest(10, "mean_first_arrival_minutes").to_csv(
        out / f"A3_worst10_scenarios_first_arrival_{mode}.csv", index=False
    )

    for env in ENV_ORDER:
        env_df = baseline_df[baseline_df["environment"] == env]
        if env_df.empty:
            continue

        fig, axes = plt.subplots(1, 2, figsize=(18, 6))
        sns.violinplot(data=env_df, x="policy", y="first_arrival_time", inner="quart", ax=axes[0])
        axes[0].set_title(f"{mode.capitalize()} | {env.capitalize()} | Baseline first-arrival distribution")
        axes[0].set_xlabel("Alerting policy")
        axes[0].set_ylabel("First-arrival time (minutes)")
        axes[0].tick_params(axis="x", rotation=35)
        if zoom:
            _apply_zoom_limits(
                axes[0],
                env_df.groupby("policy")["first_arrival_time"].mean(),
                pad_frac=0.18,
                min_pad=0.04,
            )

        sns.violinplot(data=env_df, x="policy", y="num_redundant", inner="quart", ax=axes[1])
        axes[1].set_title(f"{mode.capitalize()} | {env.capitalize()} | Baseline redundant-arrival distribution")
        axes[1].set_xlabel("Alerting policy")
        axes[1].set_ylabel("Redundant arrivals per event")
        axes[1].tick_params(axis="x", rotation=35)
        if zoom:
            _apply_zoom_limits(
                axes[1],
                env_df.groupby("policy")["num_redundant"].mean(),
                pad_frac=0.15,
                min_pad=0.02,
                lower_zero=True,
            )

        plt.tight_layout()
        suffix = "_zoom" if zoom else ""
        plt.savefig(out / f"A1_violin_distributions_baseline_{mode}_{env}{suffix}.png", bbox_inches="tight")
        plt.close()


def _render_slides_bundle(
    run_df: pd.DataFrame,
    out: Path,
    mode: str,
    ems_benchmark: dict[str, dict[str, float]],
    zoom: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate run-level data and write all figures for one EMS / results batch."""
    out.mkdir(parents=True, exist_ok=True)
    print("OUT:", out)
    print("BASELINE FILTERS:", BASELINE_FILTERS_BY_MODE[mode])
    print("EMS reference (plot lines):", ems_benchmark)
    from config import THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY

    if THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY:
        print(
            "Legacy delay adjustment: subtracting E[legacy view/decision delay] from volunteer arrival "
            "times when aggregating event-level CSVs; alert/accept counts unchanged."
        )
    validate_run_df(run_df)
    run_df = _exclude_policies(run_df)
    baseline_df = extract_baseline(run_df, mode)

    save_baseline_summary_tables(baseline_df, out, mode)
    save_coverage_threshold_curves(baseline_df, out, mode, zoom=False)

    save_environment_dashboard(
        baseline_df, out, mode, zoom=False, show_ems_reference=True, ems_benchmark=ems_benchmark
    )
    save_tradeoff_and_burden_figure(baseline_df, out, mode, zoom=False, ems_benchmark=ems_benchmark)
    save_race_outcome_figure(baseline_df, out, mode, zoom=False)
    save_delta_vs_ems_only_figure(baseline_df, out, mode, zoom=False)
    save_cfr_beats_ecdf_baseline(baseline_df, out, mode, zoom=False)
    save_cfr_beats_heatmaps(run_df, baseline_df, out, mode, zoom=False)
    save_cfr_beats_scenario_tables(run_df, out, mode)
    save_cfr_beats_violin_baseline(baseline_df, out, mode, zoom=False)

    if mode == "travel":
        save_travel_sensitivity_figure(run_df, out, zoom=False, ems_benchmark=ems_benchmark)
        save_travel_sensitivity_trend_lines(
            run_df, baseline_df, out, zoom=False, ems_benchmark=ems_benchmark
        )
        save_travel_cfr_beats_barplot(run_df, baseline_df, out, zoom=False)
        save_cfr_beats_travel_trend_lines(run_df, baseline_df, out, zoom=False)
    else:
        save_main_sensitivity_trend_lines(
            run_df, baseline_df, out, zoom=False, ems_benchmark=ems_benchmark
        )
        save_cfr_beats_main_trend_lines(run_df, baseline_df, out, zoom=False)

    save_sensitivity_heatmaps(run_df, baseline_df, out, mode, zoom=False)
    save_appendix_tables(run_df, baseline_df, out, mode, zoom=False)
    save_story_slide_figures(run_df, baseline_df, out, mode, ems_benchmark=ems_benchmark)

    if zoom:
        save_coverage_threshold_curves(baseline_df, out, mode, zoom=True)
        save_environment_dashboard(
            baseline_df, out, mode, zoom=True, show_ems_reference=True, ems_benchmark=ems_benchmark
        )
        save_tradeoff_and_burden_figure(baseline_df, out, mode, zoom=True, ems_benchmark=ems_benchmark)
        save_race_outcome_figure(baseline_df, out, mode, zoom=True)
        save_delta_vs_ems_only_figure(baseline_df, out, mode, zoom=True)
        save_cfr_beats_ecdf_baseline(baseline_df, out, mode, zoom=True)
        save_cfr_beats_heatmaps(run_df, baseline_df, out, mode, zoom=True)
        save_cfr_beats_violin_baseline(baseline_df, out, mode, zoom=True)

        if mode == "travel":
            save_travel_sensitivity_figure(run_df, out, zoom=True, ems_benchmark=ems_benchmark)
            save_travel_sensitivity_trend_lines(
                run_df, baseline_df, out, zoom=True, ems_benchmark=ems_benchmark
            )
            save_travel_cfr_beats_barplot(run_df, baseline_df, out, zoom=True)
            save_cfr_beats_travel_trend_lines(run_df, baseline_df, out, zoom=True)
        else:
            save_main_sensitivity_trend_lines(
                run_df, baseline_df, out, zoom=True, ems_benchmark=ems_benchmark
            )
            save_cfr_beats_main_trend_lines(run_df, baseline_df, out, zoom=True)

        save_sensitivity_heatmaps(run_df, baseline_df, out, mode, zoom=True)
        save_appendix_tables(run_df, baseline_df, out, mode, zoom=True)

    return run_df, baseline_df


def _run_one_mode_bundle(
    mode: str,
    out: Path,
    results: Path,
    thesis_subdir: str,
    ems_benchmark: dict[str, dict[str, float]],
    chunksize: int,
    use_cache: bool,
    zoom: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load or build run-level data for one results folder, then render all figures."""
    print("Thesis CSV folder:", results / thesis_subdir)
    run_df = build_run_level_from_sources(
        results,
        mode=mode,
        chunksize=chunksize,
        use_cache=use_cache,
        thesis_subdir=thesis_subdir,
    )
    return _render_slides_bundle(run_df, out, mode, ems_benchmark, zoom)


def _infer_compare_ems_preset(primary_preset: str, explicit: str | None) -> str:
    if explicit is not None:
        return explicit
    if primary_preset == "5_10":
        return "10_15"
    if primary_preset == "10_15":
        return "15_20"
    return "10_15"  # primary 15_20 (or unknown) → compare to 10_15


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate thesis plots from CFR simulation outputs.",
        epilog=(
            "Examples:\n"
            "  Default grid (~10/15 min EMS):  python format_outputs/generate_slides_plots.py\n"
            "  Slower EMS batch folder:         python format_outputs/generate_slides_plots.py "
            "--thesis-subdir thesis_archetype_grid_ems15_20 --ems-preset 15_20\n"
            "  Compare two EMS batches:         python format_outputs/generate_slides_plots.py "
            "--compare-thesis-subdir thesis_archetype_grid_ems15_20 --ems-preset 10_15\n"
            "  Full trees + compare in one run: python format_outputs/generate_slides_plots.py "
            "--thesis-subdir thesis_archetype_grid_ems15_20 --ems-preset 15_20 "
            "--compare-thesis-subdir thesis_archetype_grid --dual-full-bundles --no-run-cache"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=200_000,
        help="CSV streaming chunk size for low-memory aggregation.",
    )
    parser.add_argument(
        "--zoom",
        action="store_true",
        help="Generate zoomed-axis versions of all figure outputs.",
    )
    parser.add_argument(
        "--no-run-cache",
        action="store_true",
        help="Rebuild run-level cache(s) from CSV sources instead of reusing cache.",
    )
    parser.add_argument(
        "--skip-legacy-delay-adjustment",
        action="store_true",
        help=(
            "Do not subtract E[legacy view/decision delay] when aggregating event-level CSVs "
            "(use after re-running the updated simulator that omits that delay)."
        ),
    )
    parser.add_argument(
        "--results-root",
        type=str,
        default="results_final",
        help=(
            "Directory under the project root that holds thesis CSV subfolders "
            "(default: results_final). Use results for outputs under results/ only."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["main", "travel", "both"],
        default="both",
        help="Which thesis result set(s) to process.",
    )
    parser.add_argument(
        "--thesis-subdir",
        type=str,
        default="thesis_archetype_grid",
        help=(
            "Folder under --results-root containing combined_thesis_*_grid.csv "
            "(default: thesis_archetype_grid; use thesis_archetype_grid_ems15_20 for the slower-EMS run)."
        ),
    )
    parser.add_argument(
        "--ems-preset",
        type=str,
        choices=list(EMS_PRESETS.keys()),
        default="10_15",
        help="Which urban/rural EMS means to use for reference lines (must match the simulation).",
    )
    parser.add_argument(
        "--ems-urban-mean",
        type=float,
        default=None,
        help="Override urban EMS mean (minutes) for reference lines.",
    )
    parser.add_argument(
        "--ems-rural-mean",
        type=float,
        default=None,
        help="Override rural EMS mean (minutes) for reference lines.",
    )
    parser.add_argument(
        "--output-tag",
        type=str,
        default=None,
        help="Force output folder name slides_figures_{mode}_{tag}; default is derived from --thesis-subdir.",
    )
    parser.add_argument(
        "--compare-thesis-subdir",
        type=str,
        default=None,
        help=(
            "Optional second results subfolder (under results/) with the other EMS calibration. "
            "Loads only for 00_compare_ems_cases_* overlay figures (does not re-render the full bundle there)."
        ),
    )
    parser.add_argument(
        "--compare-label-a",
        type=str,
        default="EMS ~10/15 min (urban/rural means)",
        help="Legend label for primary --thesis-subdir batch.",
    )
    parser.add_argument(
        "--compare-label-b",
        type=str,
        default="EMS ~15/20 min (urban/rural means)",
        help="Legend label for --compare-thesis-subdir batch.",
    )
    parser.add_argument(
        "--compare-ems-preset",
        type=str,
        choices=list(EMS_PRESETS.keys()),
        default=None,
        help=(
            "When using --dual-full-bundles: EMS reference lines for the compare-thesis-subdir "
            "figure bundle (default: the other preset vs --ems-preset)."
        ),
    )
    parser.add_argument(
        "--dual-full-bundles",
        action="store_true",
        help=(
            "With --compare-thesis-subdir: render the complete figure/table set for BOTH result "
            "folders (each gets its own slides_* output dir and EMS reference lines), write "
            "run-level caches once per folder, and save cross-EMS comparison figures into each "
            "output dir. Avoids a second full --no-run-cache pass."
        ),
    )
    args = parser.parse_args()
    if args.dual_full_bundles and not args.compare_thesis_subdir:
        parser.error("--dual-full-bundles requires --compare-thesis-subdir")

    if args.skip_legacy_delay_adjustment:
        import config as _cfg

        _cfg.THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY = False

    sns.set_theme(style="whitegrid", context="paper")
    sns.set_palette(sns.color_palette("colorblind", desat=0.75))
    plt.rcParams.update(
        {
            "text.usetex": False,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial"],
            "mathtext.fontset": "cm",
            "figure.dpi": 170,
            "savefig.dpi": 300,
            "axes.grid": True,
            "grid.alpha": 0.20,
            "grid.linewidth": 0.6,
            "grid.linestyle": "-",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.6,
            "axes.labelsize": 11,
            "axes.titlesize": 10,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.frameon": True,
            "legend.framealpha": 0.92,
            "legend.fancybox": False,
            "legend.fontsize": 8.5,
            "legend.title_fontsize": 9,
        }
    )

    root = resolve_root()
    results = (root / args.results_root).resolve()
    modes = ["main", "travel"] if args.mode == "both" else [args.mode]

    ems_benchmark = resolve_ems_benchmark(
        args.ems_preset,
        urban_mean=args.ems_urban_mean,
        rural_mean=args.ems_rural_mean,
    )

    print("ROOT:", root)
    print("RESULTS:", results)

    use_cache = not args.no_run_cache

    for mode in modes:
        print(f"\n=== Processing mode: {mode} ===")

        if args.dual_full_bundles:
            compare_preset = _infer_compare_ems_preset(args.ems_preset, args.compare_ems_preset)
            ems_compare_benchmark = resolve_ems_benchmark(
                compare_preset,
                urban_mean=args.ems_urban_mean,
                rural_mean=args.ems_rural_mean,
            )
            cross_label_a = EMS_PRESET_CROSS_LEGEND.get(args.ems_preset, args.compare_label_a)
            cross_label_b = EMS_PRESET_CROSS_LEGEND.get(compare_preset, args.compare_label_b)
            out_primary = resolve_plot_output_dir(results, mode, args.thesis_subdir, args.output_tag)
            out_compare = resolve_plot_output_dir(
                results, mode, args.compare_thesis_subdir, args.output_tag
            )

            print(f"  Primary batch: {args.thesis_subdir} ({args.ems_preset} reference lines) -> {out_primary}")
            run_primary = build_run_level_from_sources(
                results,
                mode=mode,
                chunksize=args.chunksize,
                use_cache=use_cache,
                thesis_subdir=args.thesis_subdir,
            )
            _, baseline_primary = _render_slides_bundle(
                run_primary, out_primary, mode, ems_benchmark, args.zoom
            )

            print(
                f"  Compare batch: {args.compare_thesis_subdir} ({compare_preset} reference lines) -> {out_compare}"
            )
            run_compare = build_run_level_from_sources(
                results,
                mode=mode,
                chunksize=args.chunksize,
                use_cache=use_cache,
                thesis_subdir=args.compare_thesis_subdir,
            )
            _, baseline_compare = _render_slides_bundle(
                run_compare, out_compare, mode, ems_compare_benchmark, args.zoom
            )

            for out_dir in (out_primary, out_compare):
                save_cross_ems_comparison_figure(
                    baseline_primary,
                    baseline_compare,
                    cross_label_a,
                    cross_label_b,
                    out_dir,
                    mode,
                    zoom=False,
                )
                if args.zoom:
                    save_cross_ems_comparison_figure(
                        baseline_primary,
                        baseline_compare,
                        cross_label_a,
                        cross_label_b,
                        out_dir,
                        mode,
                        zoom=True,
                    )
            continue

        out = resolve_plot_output_dir(results, mode, args.thesis_subdir, args.output_tag)

        run_df, baseline_df = _run_one_mode_bundle(
            mode=mode,
            out=out,
            results=results,
            thesis_subdir=args.thesis_subdir,
            ems_benchmark=ems_benchmark,
            chunksize=args.chunksize,
            use_cache=use_cache,
            zoom=args.zoom,
        )

        if args.compare_thesis_subdir:
            print(f"  Loading comparison baseline from {args.compare_thesis_subdir} ...")
            run_df_b = build_run_level_from_sources(
                results,
                mode=mode,
                chunksize=args.chunksize,
                use_cache=use_cache,
                thesis_subdir=args.compare_thesis_subdir,
            )
            validate_run_df(run_df_b)
            run_df_b = _exclude_policies(run_df_b)
            baseline_b = extract_baseline(run_df_b, mode)
            save_cross_ems_comparison_figure(
                baseline_df,
                baseline_b,
                args.compare_label_a,
                args.compare_label_b,
                out,
                mode,
                zoom=False,
            )
            if args.zoom:
                save_cross_ems_comparison_figure(
                    baseline_df,
                    baseline_b,
                    args.compare_label_a,
                    args.compare_label_b,
                    out,
                    mode,
                    zoom=True,
                )

    print("\nDone.")


if __name__ == "__main__":
    main()