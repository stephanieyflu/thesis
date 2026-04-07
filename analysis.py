import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D
import os

try:
    import seaborn as sns
except ModuleNotFoundError:
    sns = None

if sns is not None:
    sns.set(style="whitegrid")


def _mean_ci(series):
    """
    Compute mean and 95% confidence interval (normal approximation).
    """
    m = series.mean()
    n = len(series)
    if n <= 1:
        return m, m, m
    se = series.std(ddof=1) / np.sqrt(n)
    half = 1.96 * se
    return m, m - half, m + half


def summarize_results(df):
    """
    Summarize performance metrics.

    If a 'run_id' column is present, compute means and 95% CIs across runs.
    Otherwise, report simple event-level means.

    Event-level rows are passed through ``apply_thesis_retroactive_time_adjustment``
    when configured (see ``config.THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY``).
    """
    from utils import apply_thesis_retroactive_time_adjustment

    df = apply_thesis_retroactive_time_adjustment(df)

    if "run_id" in df.columns:
        agg_spec = {
            "first_arrival_mean": ("first_arrival_time", "mean"),
            "success_rate": ("success", "mean"),
            "alerts_mean": ("num_alerted", "mean"),
        }
        if "cfr_beats_ems" in df.columns:
            agg_spec["cfr_beats_ems_rate"] = ("cfr_beats_ems", "mean")
        per_run = df.groupby("run_id").agg(**agg_spec).reset_index()

        fa_mean, fa_lo, fa_hi = _mean_ci(per_run["first_arrival_mean"])
        sr_mean, sr_lo, sr_hi = _mean_ci(per_run["success_rate"])
        al_mean, al_lo, al_hi = _mean_ci(per_run["alerts_mean"])

        summary = {
            "avg_first_arrival": fa_mean,
            "avg_first_arrival_ci": (fa_lo, fa_hi),
            "success_rate": sr_mean,
            "success_rate_ci": (sr_lo, sr_hi),
            "avg_num_alerts": al_mean,
            "avg_num_alerts_ci": (al_lo, al_hi),
            "max_num_alerts": df["num_alerted"].max(),
        }
        if "cfr_beats_ems_rate" in per_run.columns:
            cb_mean, cb_lo, cb_hi = _mean_ci(per_run["cfr_beats_ems_rate"])
            summary["cfr_beats_ems_rate"] = cb_mean
            summary["cfr_beats_ems_rate_ci"] = (cb_lo, cb_hi)
    else:
        summary = {
            "avg_first_arrival": df["first_arrival_time"].mean(),
            "median_first_arrival": df["first_arrival_time"].median(),
            "std_first_arrival": df["first_arrival_time"].std(),
            "success_rate": df["success"].mean(),
            "avg_num_alerts": df["num_alerted"].mean(),
            "max_num_alerts": df["num_alerted"].max(),
        }

    return summary

def plot_first_arrival_distribution(df, ax=None, label=None):
    if sns is None:
        raise RuntimeError("plot_first_arrival_distribution requires seaborn. Install it with `pip install seaborn`.")
    if ax is None:
        plt.figure(figsize=(8,5))
        ax = plt.gca()
    sns.kdeplot(df['first_arrival_time'], fill=True, alpha=0.3, ax=ax, label=label)
    ax.set_xlabel("First Arrival Time (minutes)")
    ax.set_ylabel("Density")
    ax.set_title("First Arrival Time Distribution")

def plot_success_rate_over_threshold(df, thresholds=None, ax=None, label=None):
    if sns is None:
        raise RuntimeError("plot_success_rate_over_threshold requires seaborn. Install it with `pip install seaborn`.")
    if thresholds is None:
        thresholds = range(1, 16)
    rates = [(df['first_arrival_time'] <= t).mean() for t in thresholds]
    if ax is None:
        plt.figure(figsize=(8,5))
        ax = plt.gca()
    sns.lineplot(x=thresholds, y=rates, marker="o", ax=ax, label=label)
    ax.set_xlabel("Time Threshold (minutes)")
    ax.set_ylabel("Success Rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("Success Rate vs Time Threshold")

def plot_alerts_distribution(df, ax=None, label=None):
    if sns is None:
        raise RuntimeError("plot_alerts_distribution requires seaborn. Install it with `pip install seaborn`.")
    if ax is None:
        plt.figure(figsize=(8,5))
        ax = plt.gca()
    sns.histplot(df['num_alerted'], bins=20, kde=False, ax=ax, label=label)
    ax.set_xlabel("Number of Responders Alerted")
    ax.set_ylabel("Frequency")
    ax.set_title("Number of Responders Alerted per Event")

def dashboard_of_dashboards(dfs_dict, title=None):
    fig, axes = plt.subplots(3, 1, figsize=(14, 16), constrained_layout=False)
    plt.subplots_adjust(hspace=0.45, right=0.8)

    for key, df in dfs_dict.items():
        plot_first_arrival_distribution(df, ax=axes[0], label=key)
    axes[0].legend(loc='center left', bbox_to_anchor=(1, 0.5))

    for key, df in dfs_dict.items():
        plot_success_rate_over_threshold(df, ax=axes[1], label=key)
    axes[1].legend(loc='center left', bbox_to_anchor=(1, 0.5))

    for key, df in dfs_dict.items():
        plot_alerts_distribution(df, ax=axes[2], label=key)
    axes[2].legend(loc='center left', bbox_to_anchor=(1, 0.5))

    if title:
        fig.suptitle(title, fontsize=18, y=0.95)

    plt.show()


def animate_event_trace(
    trace,
    interval_ms=100,
    num_frames=60,
    time_margin_min=2.0,
    show=True,
    save_path=None,
    dpi=150,
    fps=10,
    pos_scale=1.5,
    motion_ease=0.6,
    scale_km=1.0,
):
    """
    Animate a single event trace returned by `simulation.run_single_event_trace`.

    The animation is a 2D schematic: responders start at radius=distance and move
    in straight lines to the event point (origin) after their response delay.
    """
    responder_traces = trace["responders"]

    # Precompute initial geometry for every responder.
    dist = np.array([r["distance"] for r in responder_traces], dtype=float)
    angles = np.array([r["angle"] for r in responder_traces], dtype=float)
    # Animation convention: radial coordinate uses sampled distance_to_event; bearing is synthetic.
    # `pos_scale` exaggerates spatial spread so motion is easier to see.
    x0 = pos_scale * dist * np.cos(angles)
    y0 = pos_scale * dist * np.sin(angles)

    alerted = np.array([r["alerted"] for r in responder_traces], dtype=bool)
    accepted = np.array([r["accepted"] for r in responder_traces], dtype=bool)
    start_move_time = np.array(
        [(-1.0 if r["start_move_time"] is None else float(r["start_move_time"])) for r in responder_traces],
        dtype=float,
    )
    arrival_time = np.array(
        [(-1.0 if r["arrival_time"] is None else float(r["arrival_time"])) for r in responder_traces],
        dtype=float,
    )

    # Tighten the viewport: use a high percentile to avoid outlier-driven zoom.
    if dist.size:
        dist_lim = float(np.quantile(dist, 0.92))
    else:
        dist_lim = 1.0
    axis_lim = max(1.0, dist_lim * pos_scale * 1.15)

    # Ambulance: start at some fixed distance above the origin and move to origin.
    t_ambulance = float(trace["t_ambulance"])
    amb_start_x = float(trace.get("ambulance_start_x", 0.0))
    amb_start_y = float(trace.get("ambulance_start_y", dist_lim * pos_scale * 1.2))

    # Frame times (relative to event start).
    accepted_arrivals = arrival_time[arrival_time >= 0]
    t_end = max(t_ambulance, float(np.max(accepted_arrivals)) if accepted_arrivals.size else 0.0) + float(
        time_margin_min
    )
    times = np.linspace(0.0, t_end, num_frames)

    # Trace summary fields used for both styling and overlays.
    t_first = float(trace["t_first"])
    success = bool(trace["success"])
    first_source = str(trace.get("first_source", "unknown"))
    redundant_total = int(trace.get("redundant_arrivals", 0))

    # Accepted responders arriving after the first arrival are "redundant".
    redundant_flags = accepted & (arrival_time > t_first)
    first_arrival_flags = accepted & (~redundant_flags)

    # Colors + marker sizes by responder category.
    colors = np.empty(len(responder_traces), dtype=object)
    colors[(~alerted)] = "#888888"
    colors[(alerted) & (~accepted)] = "#DD8452"  # orange-ish
    colors[first_arrival_flags] = "#55A868"  # green-ish: first accepting arrivals
    colors[redundant_flags] = "#8172B2"  # purple-ish: redundant accepting arrivals

    sizes = np.full(len(responder_traces), 22.0, dtype=float)  # not alerted
    sizes[(alerted) & (~accepted)] = 45.0
    sizes[first_arrival_flags] = 85.0
    sizes[redundant_flags] = 70.0

    # Subtle, presentation-friendly background styling + typography.
    from matplotlib import font_manager

    available_fonts = {f.name for f in font_manager.fontManager.ttflist}
    has_roboto = any(name == "Roboto" or name.startswith("Roboto") for name in available_fonts)

    font_family = (
        ["Roboto", "DejaVu Sans", "Arial", "sans-serif"]
        if has_roboto
        else ["DejaVu Sans", "Arial", "sans-serif"]
    )
    plt.rcParams.update(
        {
            # Research-poster / conference aesthetic.
            # NOTE: Matplotlib uses system fonts; this will fall back gracefully
            # if Roboto isn't installed.
            "font.family": font_family,
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.titleweight": "normal",
            # Use a sans-serif math font so the overlay text matches Roboto-style
            # labeling more closely.
            "mathtext.fontset": "dejavusans",
        }
    )

    fig, ax = plt.subplots(figsize=(9.0, 7.0))
    fig.patch.set_facecolor("#f7f8fb")
    ax.set_facecolor("#ffffff")
    ax.set_axisbelow(True)  # ensure grid stays behind dots/radius overlays
    ax.set_aspect("equal", "box")
    ax.set_xlim(-axis_lim, axis_lim)
    ax.set_ylim(-axis_lim, axis_lim)
    # Reduce chart vibes: keep only a subtle title and remove axis labels.
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_title(
        f'{trace["policy"]} · {trace["environment"].title()} simulation',
        fontsize=12,
        fontweight="normal",
        color="#2b2d42",
        pad=10,
    )
    # Keep a light grid for spatial reference.
    ax.grid(True, color="#dfe4ee", linewidth=0.8, alpha=0.38)
    # Explicit zorder for the grid (Matplotlib sometimes varies per backend).
    for gl in ax.get_xgridlines() + ax.get_ygridlines():
        gl.set_zorder(0)

    # Static event point at origin.
    ax.scatter([0.0], [0.0], s=140, c="#4C72B0", marker="*", label="Event", zorder=5)

    # Scatter of responders (positions updated over time).
    # White stroke improves contrast in GIFs.
    sc = ax.scatter(
        x0,
        y0,
        s=sizes,
        c=colors,
        edgecolor="white",
        linewidths=0.6,
        alpha=0.96,
        zorder=4,
    )

    # Ambulance point.
    amb_sc = ax.scatter(
        [amb_start_x],
        [amb_start_y],
        s=90,
        c="#C44E52",
        marker="s",
        label="Ambulance",
        zorder=5,
    )

    time_text = ax.text(
        0.02,
        0.98,
        "",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        color="#f4f8ff",
        bbox=dict(
            boxstyle="round,pad=0.45",
            facecolor="#1f2a44",
            alpha=0.70,
            edgecolor="#5f78a8",
        ),
        zorder=6,
    )

    # Legend for responder colors/categories.
    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#888888",
            markersize=8,
            label="Not alerted",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#DD8452",
            markersize=8,
            label="Alerted, not accepted",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#55A868",
            markersize=8,
            label="Accepted (first arrivals)",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#8172B2",
            markersize=8,
            label="Accepted (redundant arrivals)",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="w",
            markerfacecolor="#C44E52",
            markersize=9,
            label="Ambulance",
        ),
        Line2D(
            [0],
            [0],
            marker="*",
            color="#4C72B0",
            markerfacecolor="#4C72B0",
            markersize=12,
            label="Event",
        ),
    ]
    leg = ax.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(1.02, 0.98),  # outside plot, top-aligned
        borderaxespad=0.0,
        frameon=True,
    )
    if leg is not None:
        leg.get_frame().set_facecolor("#ffffff")
        leg.get_frame().set_alpha(0.9)
        leg.get_frame().set_edgecolor("#d9dbe5")
        for txt in leg.get_texts():
            txt.set_fontsize(8)

    # Scale bar (keeps one reference without chart-like axes labels).
    bar_len = float(pos_scale) * float(scale_km)
    # Place scale bar at the bottom-right to avoid typical legend overlap.
    x_end = 0.9 * axis_lim
    x_start = x_end - bar_len
    if x_start < -axis_lim:
        x_start = -0.9 * axis_lim
        x_end = x_start + bar_len
    y_start = -0.88 * axis_lim
    y_end = y_start
    ax.plot([x_start, x_end], [y_start, y_end], color="#2b2d42", linewidth=3, zorder=3)
    ax.text(
        (x_start + x_end) / 2.0,
        y_start + 0.04 * axis_lim,
        f"{scale_km:g} km",
        ha="center",
        va="bottom",
        fontsize=9,
        color="#2b2d42",
        zorder=3,
    )

    # Hide tick labels to emphasize "simulation view" rather than "graph".
    ax.tick_params(labelbottom=False, labelleft=False)
    ax.set_xticks([])
    ax.set_yticks([])

    # Event-specific furthest-alerted radius overlay.
    if np.any(alerted):
        furthest_alerted_r = float(np.max(dist[alerted])) * pos_scale
        circ = plt.Circle(
            (0.0, 0.0),
            furthest_alerted_r,
            facecolor="#4C72B0",
            edgecolor="#4C72B0",
            alpha=0.10,
            fill=True,
            linewidth=2.8,
            linestyle="--",
            zorder=2,
        )
        ax.add_patch(circ)

    def _pos_at_time(t):
        x = x0.copy()
        y = y0.copy()

        # Only accepted responders move.
        moving = accepted

        # Before they start moving: keep at initial position.
        started = moving & (t >= start_move_time) & (arrival_time > start_move_time)
        finished = moving & (arrival_time >= 0) & (t >= arrival_time)

        # Moving in-progress.
        in_progress = started & (~finished)
        if np.any(in_progress):
            denom = arrival_time[in_progress] - start_move_time[in_progress]
            denom = np.where(denom <= 1e-9, 1e-9, denom)  # avoid div-by-zero
            progress = (t - start_move_time[in_progress]) / denom
            progress = np.clip(progress, 0.0, 1.0)
            # Ease curve makes motion more obvious early in the animation.
            progress = progress ** motion_ease
            x[in_progress] = (1.0 - progress) * x0[in_progress]
            y[in_progress] = (1.0 - progress) * y0[in_progress]

        # After arrival: place at origin.
        if np.any(finished):
            x[finished] = 0.0
            y[finished] = 0.0

        return x, y

    def update(frame_idx):
        t = float(times[frame_idx])
        x, y = _pos_at_time(t)
        sc.set_offsets(np.c_[x, y])

        # Ambulance movement (linear schematic).
        if t_ambulance <= 1e-9 or t >= t_ambulance:
            amb_x = 0.0
            amb_y = 0.0
        else:
            amb_progress = t / t_ambulance
            amb_progress = np.clip(amb_progress, 0.0, 1.0)
            amb_x = (1.0 - amb_progress) * amb_start_x
            amb_y = (1.0 - amb_progress) * amb_start_y
        amb_sc.set_offsets(np.array([[amb_x, amb_y]]))

        arrived_accepted = int(np.sum((arrival_time >= 0) & (t >= arrival_time)))
        redundant_so_far = int(np.sum((arrival_time > t_first) & (t >= arrival_time)))
        success_text = "yes" if success else "no"
        first_label = {"ambulance": "ambulance", "responder": "responder", "tie": "tie"}.get(first_source, first_source)

        overlay = (
            rf"$\mathbf{{t:}}\ {t:.2f}\ \mathrm{{min}}$" + "\n"
            + rf"$\mathbf{{t_{{first}}:}}\ {t_first:.2f}\ \mathrm{{min}}$"
            + "\n"
            + rf"$\mathbf{{first:}}\ \mathrm{{{first_label}}}$"
            + "\n"
            + rf"$\mathbf{{success:}}\ \mathrm{{{success_text}}}$"
            + "\n"
            + rf"$\mathbf{{arrived:}}\ {arrived_accepted}$"
            + "\n"
            + rf"$\mathbf{{redundant:}}\ {redundant_so_far}/{redundant_total}$"
        )
        time_text.set_text(overlay)
        return (sc, amb_sc, time_text)

    ani = FuncAnimation(fig, update, frames=len(times), interval=interval_ms, blit=False, repeat=False)
    # Reserve space on the right for an external legend.
    fig.subplots_adjust(right=0.70)

    if save_path:
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        ext = os.path.splitext(save_path)[1].lower()
        writer = None
        if ext == ".gif":
            try:
                from matplotlib.animation import PillowWriter

                writer = PillowWriter(fps=fps)
            except Exception as e:
                raise RuntimeError(
                    "Saving GIF requires Pillow. Install it with `pip install pillow`."
                ) from e
        else:
            # Keep this conservative: mp4/webm typically require ffmpeg.
            raise ValueError(f"Unsupported save extension: {ext}. Use .gif for now.")

        ani.save(save_path, writer=writer, dpi=dpi)

    if show:
        plt.show()

    return ani
