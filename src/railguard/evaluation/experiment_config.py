"""Typed, validated configuration for experiment 002 (MetroPT-3 baselines)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

SPLIT_NAMES: tuple[str, ...] = ("fit", "validation", "test")
_HOURS_PER_BUDGET_PERIOD = 24.0

Range = tuple[pd.Timestamp, pd.Timestamp]


@dataclass(frozen=True)
class SplitConfig:
    """Chronological split as half-open ``[start, end)`` ranges."""

    fit: Range
    validation: Range
    test: Range

    def __post_init__(self) -> None:
        ranges = [(name, getattr(self, name)) for name in SPLIT_NAMES]
        for name, (start, end) in ranges:
            if start >= end:
                raise ValueError(f"split {name}: start must be before end")
        for (prev_name, prev), (name, cur) in zip(ranges, ranges[1:], strict=False):
            if cur[0] < prev[0]:
                raise ValueError(f"splits must be in order: {prev_name} then {name}")
            if cur[0] < prev[1]:
                raise ValueError(f"splits {prev_name} and {name} overlap")


@dataclass(frozen=True)
class IsolationForestParams:
    n_estimators: int
    max_samples: int
    contamination: str | float


@dataclass(frozen=True)
class ExperimentConfig:
    window_sizes: tuple[pd.Timedelta, ...]
    sample_interval: pd.Timedelta
    stride: pd.Timedelta
    min_coverage: float
    variants: dict[str, tuple[str, ...]]
    max_gap_s: float
    split: SplitConfig
    horizon: pd.Timedelta
    merge_gap: pd.Timedelta
    budget_per_hour: float
    seed: int
    isolation_forest: IsolationForestParams

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ExperimentConfig":
        features, evaluation = raw["features"], raw["evaluation"]
        min_coverage = float(features["min_coverage"])
        if not 0.0 < min_coverage <= 1.0:
            raise ValueError("min_coverage must be in (0, 1]")
        sample_interval = pd.Timedelta(features["sample_interval"])
        if sample_interval <= pd.Timedelta(0):
            raise ValueError("sample_interval must be positive")
        horizon = pd.Timedelta(evaluation["horizon"])
        if horizon <= pd.Timedelta(0):
            raise ValueError("horizon must be positive")
        merge_gap = pd.Timedelta(evaluation["merge_gap"])
        if merge_gap < pd.Timedelta(0):
            raise ValueError("merge_gap must not be negative")
        budget = float(evaluation["budget_per_24h"])
        if budget < 0:
            raise ValueError("budget_per_24h must not be negative")
        max_gap_s = float(raw["segmentation"]["max_gap_s"])
        if max_gap_s < 0:
            raise ValueError("max_gap_s must not be negative")
        split = SplitConfig(**{name: _range(raw["split"][name]) for name in SPLIT_NAMES})
        forest = raw["isolation_forest"]
        return cls(
            window_sizes=tuple(pd.Timedelta(w) for w in features["window_sizes"]),
            sample_interval=sample_interval,
            stride=pd.Timedelta(features["stride"]),
            min_coverage=min_coverage,
            variants={k: tuple(v) for k, v in features["variants"].items()},
            max_gap_s=max_gap_s,
            split=split,
            horizon=horizon,
            merge_gap=merge_gap,
            budget_per_hour=budget / _HOURS_PER_BUDGET_PERIOD,
            seed=int(raw["seed"]),
            isolation_forest=IsolationForestParams(
                n_estimators=int(forest["n_estimators"]),
                max_samples=int(forest["max_samples"]),
                contamination=forest["contamination"],
            ),
        )


def _range(pair: list[str]) -> Range:
    if len(pair) != 2:
        raise ValueError("a split range needs exactly [start, end]")
    return pd.Timestamp(pair[0]), pd.Timestamp(pair[1])


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    with Path(path).open(encoding="utf-8") as handle:
        return ExperimentConfig.from_dict(yaml.safe_load(handle))
