"""CLI: run experiment 002 (E0 robust z-score, E1 Isolation Forest) and write its outputs.

Writes ``metrics.json`` (deterministic), ``run_info.json`` (provenance and run time),
``results.md`` (event counts per model, variant and split) and, when matplotlib is
installed, ``plots/``.
"""

import argparse
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from railguard.data.errors import ChecksumMismatchError
from railguard.data.labels import FailureWindow, assign_labels, load_failure_windows
from railguard.data.metropt3 import load_metropt3, validate_metropt3
from railguard.evaluation.alerts import alert_episodes
from railguard.evaluation.experiment import ExperimentResult, ModelRun, run_experiment
from railguard.evaluation.experiment_config import ExperimentConfig, load_experiment_config
from railguard.preprocessing.segments import assign_segments

SECONDS_PER_HOUR = 3600.0
TABLE_HEADER = (
    "| Model | Variant | Split | Events with an alert | Lead time per event (h) "
    "| Alerts outside windows per operating hour | Threshold |\n"
    "|---|---|---|---|---|---|---|\n"
)


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def _git_dirty() -> bool | None:
    """True when tracked or untracked code differs from HEAD; None when git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", "src", "scripts", "configs", "tests"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return bool(out.stdout.strip())


def _lead_text(run: ModelRun, split: str) -> str:
    parts = []
    for event in run.splits[split].metrics.events:
        lead = (
            "none" if event.lead_time_s is None else f"{event.lead_time_s / SECONDS_PER_HOUR:.2f}"
        )
        parts.append(f"#{event.event_id}: {lead}")
    return ", ".join(parts) or "no events in split"


def results_table(result: ExperimentResult, plots: list[str] | None = None) -> str:
    """Markdown table with event counts (never percentages of events), then the plot list."""
    rows = []
    for run in result.runs:
        for split, evaluation in run.splits.items():
            metrics = evaluation.metrics
            rows.append(
                f"| {run.model} | {run.variant} | {split} "
                f"| {metrics.detected} of {len(metrics.events)} | {_lead_text(run, split)} "
                f"| {metrics.outside_per_hour:.4f} | {run.threshold:.6f} |"
            )
    note = (
        "An event counts as having an alert when an alert episode overlaps "
        "[start - horizon, end]. Lead time is measured from the first alert in that range to "
        "the window start (negative after it began). Alerts outside documented windows are an "
        "upper bound on false alerts: windows are approximate and other anomalies may exist.\n"
    )
    if plots:
        listing = "\n".join(f"- plots/{name}" for name in plots)
        plot_text = f"\n## Plots\n\n{listing}\n"
    else:
        plot_text = "\n## Plots\n\nNo plots were written (matplotlib is not installed).\n"
    table = "\n".join(rows)
    return f"# EXP-002 results\n\n{TABLE_HEADER}{table}\n\n{note}{plot_text}"


def _split_for(window: FailureWindow, config: ExperimentConfig) -> str | None:
    """Split containing the window start, else the first one the window's range overlaps."""
    names = ("validation", "test")
    for name in names:
        start, end = getattr(config.split, name)
        if start <= window.start < end:
            return name
    for name in names:
        start, end = getattr(config.split, name)
        if window.end >= start and window.start - config.horizon < end:
            return name
    return None


def _event_view(
    scored: pd.DataFrame, split: str, window: FailureWindow, horizon: pd.Timedelta
) -> pd.DataFrame:
    """Score rows of ``split`` within ``[start - 2*horizon, end + horizon]``."""
    rows = scored[scored["split"] == split]
    lo, hi = window.start - 2 * horizon, window.end + horizon
    return rows[(rows.index >= lo) & (rows.index <= hi)]


def _plot_event(
    plt: Any, run: ModelRun, scored: pd.DataFrame, window: FailureWindow,
    split: str, config: ExperimentConfig, path: Path,
) -> None:  # fmt: skip
    """Score line, frozen threshold, documented window, pre-event start and alert episodes."""
    rows = scored[scored["split"] == split]
    episodes = alert_episodes(rows["score"], run.threshold, config.merge_gap, rows["segment_id"])
    lo, hi = window.start - 2 * config.horizon, window.end + config.horizon
    view = _event_view(scored, split, window, config.horizon)
    fig, ax = plt.subplots(figsize=(9, 4))
    for _, segment in view.groupby("segment_id"):  # one line per segment: gaps stay gaps
        ax.plot(segment.index, segment["score"], color="tab:blue", linewidth=1)
    ax.axhline(run.threshold, color="tab:red", linestyle="--", label="threshold")
    ax.axvspan(window.start, window.end, color="tab:orange", alpha=0.25, label="documented window")
    ax.axvline(window.start - config.horizon, color="black", linestyle=":", label="pre-event start")
    for i, episode in enumerate(e for e in episodes if e.end >= lo and e.start <= hi):
        end = max(episode.end, episode.start + config.stride)  # single-row episodes stay visible
        ax.axvspan(episode.start, end, color="tab:red", alpha=0.3,
                   label="alert episode" if i == 0 else None)  # fmt: skip
    ax.set_title(f"{run.model} / {run.variant} / event {window.id} ({split})")
    ax.set_ylabel("anomaly score")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.autofmt_xdate()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def write_plots(
    result: ExperimentResult,
    out_dir: Path,
    windows: list[FailureWindow],
    config: ExperimentConfig,
) -> list[str]:
    """Write PNG plots and return their names; return [] (and say so) without matplotlib."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is not installed: skipping plots")
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for run in result.runs:
        scored = result.scores[(run.model, run.variant)]
        for window in windows:
            split = _split_for(window, config)
            if split is None:
                continue
            name = f"{run.model}_{run.variant}_event{window.id}.png"
            _plot_event(plt, run, scored, window, split, config, out_dir / name)
            names.append(name)
    names += _bar_charts(plt, result, out_dir)
    return names


def _bar_charts(plt: Any, result: ExperimentResult, out_dir: Path) -> list[str]:
    labels = [f"{r.model}/{r.variant}" for r in result.runs]
    names = []
    for name, getter, title in (
        (
            "alerts_outside_per_hour",
            lambda m: m.outside_per_hour,
            "Alerts outside documented windows per operating hour (upper bound)",
        ),
        ("events_with_alert", lambda m: float(m.detected), "Events with an alert"),
    ):
        fig, ax = plt.subplots(figsize=(8, 4))
        width = 0.4
        for i, split in enumerate(("validation", "test")):
            values = [getter(r.splits[split].metrics) for r in result.runs]
            ax.bar([x + i * width for x in range(len(labels))], values, width, label=split)
        ax.set_xticks([x + width / 2 for x in range(len(labels))], labels, rotation=20)
        ax.set_title(title)
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / f"{name}.png")
        plt.close(fig)
        names.append(f"{name}.png")
    return names


def _run_info(
    result: ExperimentResult, config_path: Path, sha256: str, seconds: float
) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle)
    return {
        "dataset_sha256": sha256,
        "config": raw_config,
        "seed": result.seed,
        "features": result.features,
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "run_seconds": round(seconds, 3),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sha256", required=True, help="expected dataset SHA-256 (mandatory)")
    parser.add_argument("--max-gap-s", type=float, default=60.0)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.perf_counter()
    config = load_experiment_config(args.config)
    windows: list[FailureWindow] = load_failure_windows(args.windows)
    try:
        df, metadata = load_metropt3(args.csv, args.sha256)
    except ChecksumMismatchError as error:
        raise SystemExit(f"dataset checksum mismatch, nothing written: {error}") from error
    validate_metropt3(df)
    df["segment_id"] = assign_segments(df["timestamp"], args.max_gap_s)
    labels = assign_labels(df["timestamp"], windows, pd.Timedelta(config.horizon))
    result = run_experiment(df, labels, windows, config)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metrics.json").write_text(result.to_json(), encoding="utf-8")
    info = _run_info(result, args.config, metadata.sha256, time.perf_counter() - started)
    (args.out / "run_info.json").write_text(json.dumps(info, sort_keys=True, indent=2), "utf-8")
    plots = write_plots(result, args.out / "plots", windows, config)
    (args.out / "results.md").write_text(results_table(result, plots), encoding="utf-8")


if __name__ == "__main__":
    main()
