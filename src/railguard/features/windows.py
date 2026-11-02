"""Trailing-window features on a 60 s scoring grid (spec 002, REQ-002-01 and REQ-002-02).

Every feature at time ``t`` uses only rows with timestamp ``<= t`` from the same segment
(``closed="right"`` rolling windows, one segment at a time), so nothing leaks from the
future and no window reaches across a gap.
"""

import logging
from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd

from railguard.data.metropt3 import ANALOG_COLUMNS, DIGITAL_COLUMNS, TIMESTAMP_COL
from railguard.evaluation.experiment_config import ExperimentConfig
from railguard.logging_utils import log_rows

SEGMENT_COL = "segment_id"
ANALOG_STATS: tuple[str, ...] = ("mean", "std", "min", "max")
DIGITAL_STATS: tuple[str, ...] = ("duty", "transitions")

_COVERAGE_EPS = 1e-9  # float tolerance when comparing row counts with min_coverage

_logger = logging.getLogger("railguard")


@dataclass(frozen=True)
class FeatureConfig:
    """Window sizes, nominal sampling interval, scoring stride and minimum window coverage.

    ``sample_interval`` is fixed by config (never inferred from data) so that coverage, and
    therefore which rows are dropped, cannot depend on rows after the scoring time.
    """

    window_sizes: tuple[pd.Timedelta, ...]
    sample_interval: pd.Timedelta
    stride: pd.Timedelta
    min_coverage: float

    def __post_init__(self) -> None:
        if not self.window_sizes or any(w <= pd.Timedelta(0) for w in self.window_sizes):
            raise ValueError("window_sizes must be non-empty and positive")
        if self.sample_interval <= pd.Timedelta(0):
            raise ValueError("sample_interval must be positive")
        if self.stride <= pd.Timedelta(0):
            raise ValueError("stride must be positive")
        if not 0.0 < self.min_coverage <= 1.0:
            raise ValueError("min_coverage must be in (0, 1]")

    @classmethod
    def from_experiment(cls, config: ExperimentConfig) -> "FeatureConfig":
        """Copy the feature settings out of an experiment config."""
        return cls(config.window_sizes, config.sample_interval, config.stride, config.min_coverage)


def window_label(window: pd.Timedelta) -> str:
    """Whole seconds, so ``60s`` and ``300s`` never collide with ``1min`` style names."""
    return f"{int(window.total_seconds())}s"


def feature_columns(config: FeatureConfig) -> list[str]:
    """Output column names in a fixed order: window by window, analogue then digital."""
    names: list[str] = []
    for window in config.window_sizes:
        label = window_label(window)
        names += [f"{c}__{s}__{label}" for c in ANALOG_COLUMNS for s in ANALOG_STATS]
        names += [f"{c}__{s}__{label}" for c in DIGITAL_COLUMNS for s in DIGITAL_STATS]
    return names


def window_features(df: pd.DataFrame, config: FeatureConfig) -> pd.DataFrame:
    """Return one feature row per scoring timestamp, indexed by that timestamp.

    Scoring rows are the last row of each ``config.stride`` bucket within a segment. Rows whose
    coverage (rows held / rows expected at ``config.sample_interval``) is below
    ``config.min_coverage`` for any window size are dropped and the count is logged.
    Standard deviation uses ``ddof=1``. A transition is a change from the previous row, which
    for the first row of a window may lie just outside it. Whether a row is scored depends on
    the next row's timestamp (offline use only); a segment's partial first or last bucket is
    scored too, and the coverage rule then drops it if it is thin.
    """
    _validate(df)
    columns = [SEGMENT_COL, *feature_columns(config)]
    if df.empty:
        log_rows("window_features", 0, 0)
        return pd.DataFrame(columns=columns).rename_axis(TIMESTAMP_COL)

    parts = [
        _segment_features(segment.set_index(TIMESTAMP_COL), seg_id, config)
        for seg_id, segment in _segments(df)
    ]
    scored = pd.concat(parts)
    enough = scored.pop("_enough")
    kept = scored.loc[enough, columns]
    _logger.info(
        "window_features: dropped %d of %d scoring rows below min coverage %.2f",
        len(scored) - len(kept),
        len(scored),
        config.min_coverage,
    )
    log_rows("window_features", len(df), len(kept))
    return kept


def _validate(df: pd.DataFrame) -> None:
    required = {TIMESTAMP_COL, SEGMENT_COL, *ANALOG_COLUMNS, *DIGITAL_COLUMNS}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"missing columns: {missing}")
    signals = list(ANALOG_COLUMNS + DIGITAL_COLUMNS)
    if df[SEGMENT_COL].isna().any() or not pd.api.types.is_integer_dtype(df[SEGMENT_COL]):
        raise ValueError("segment_id must be a non-null integer column")
    if df[signals].isna().any().any():
        raise ValueError("signal columns must not contain NaN")
    ts = df[TIMESTAMP_COL]
    if not ts.is_monotonic_increasing:
        raise ValueError("timestamps must be sorted ascending")
    if not ts.is_unique:
        raise ValueError("timestamps must be unique")


def _segments(df: pd.DataFrame) -> list[tuple[int, pd.DataFrame]]:
    return [(cast(int, seg_id), seg) for seg_id, seg in df.groupby(SEGMENT_COL, sort=True)]


def _scoring_positions(index: pd.Index, stride: pd.Timedelta) -> np.ndarray:
    """Positions of the last row in each stride bucket."""
    buckets = pd.DatetimeIndex(index).floor(stride)
    return np.flatnonzero(np.append(buckets[:-1] != buckets[1:], True))


def _segment_features(segment: pd.DataFrame, seg_id: int, config: FeatureConfig) -> pd.DataFrame:
    positions = _scoring_positions(segment.index, config.stride)
    analog = segment[list(ANALOG_COLUMNS)].astype("float64")
    digital = segment[list(DIGITAL_COLUMNS)].astype("float64")
    flips = digital.diff().abs().fillna(0.0)
    ones = pd.Series(1.0, index=segment.index)

    blocks: list[pd.DataFrame] = []
    enough = np.ones(len(positions), dtype=bool)
    for window in config.window_sizes:
        label = window_label(window)

        def pick(frame: pd.DataFrame, stat: str, suffix: str = label) -> None:
            blocks.append(frame.iloc[positions].add_suffix(f"__{stat}__{suffix}"))

        rolling = analog.rolling(window, closed="right")
        pick(rolling.mean(), "mean")
        pick(rolling.std(), "std")
        pick(rolling.min(), "min")
        pick(rolling.max(), "max")
        pick(digital.rolling(window, closed="right").mean(), "duty")
        pick(flips.rolling(window, closed="right").sum(), "transitions")
        held = ones.rolling(window, closed="right").sum().iloc[positions].to_numpy()
        expected_rows = window / config.sample_interval
        enough &= held >= config.min_coverage * expected_rows - _COVERAGE_EPS

    result = pd.concat(blocks, axis=1)[feature_columns(config)]
    result.insert(0, SEGMENT_COL, seg_id)
    result["_enough"] = enough
    return result.rename_axis(TIMESTAMP_COL)
