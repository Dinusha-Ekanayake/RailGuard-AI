"""Deterministic data-quality report for a timestamped DataFrame."""

import json
import math
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

DEFAULT_GAP_THRESHOLD_S = 60.0
_QUANTILES = (0.01, 0.5, 0.99)
_ONE_HOUR_S = 3600


def _nan_to_none(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _nan_to_none(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_nan_to_none(v) for v in value]
    return value


@dataclass(frozen=True)
class QualityReport:
    rows: int
    columns: list[str]
    dtypes: dict[str, str]
    timestamp_parse_rate: float
    duplicate_timestamps: int
    nulls: dict[str, int]
    value_ranges: dict[str, dict[str, float]]
    interval_seconds: dict[str, float]
    gap_threshold_s: float
    gap_count: int
    gap_count_over_1h: int
    gaps: list[dict[str, Any]]
    digital_cardinality: dict[str, list[float]]

    def to_json(self) -> str:
        return json.dumps(_nan_to_none(asdict(self)), indent=2, sort_keys=True, allow_nan=False)


def quality_report(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    digital_columns: tuple[str, ...] = (),
    gap_threshold_s: float = DEFAULT_GAP_THRESHOLD_S,
) -> QualityReport:
    ts = df[timestamp_col]
    deltas = ts.diff().dt.total_seconds().dropna()
    gap_deltas = deltas[deltas > gap_threshold_s]
    previous = ts.shift(1)
    gaps = [
        {
            "start": str(previous.loc[i]),
            "end": str(ts.loc[i]),
            "seconds": float(seconds),
        }
        for i, seconds in gap_deltas.items()
    ]
    numeric = df.drop(columns=[timestamp_col]).select_dtypes("number")
    return QualityReport(
        rows=len(df),
        columns=list(df.columns),
        dtypes={str(c): str(t) for c, t in df.dtypes.items()},
        timestamp_parse_rate=float(ts.notna().mean()) if len(df) else 1.0,
        duplicate_timestamps=int(ts.duplicated().sum()),
        nulls={str(c): int(n) for c, n in df.isna().sum().items()},
        value_ranges={
            c: {"min": float(numeric[c].min()), "max": float(numeric[c].max())}
            for c in numeric.columns
        },
        interval_seconds={f"p{int(q * 100)}": float(deltas.quantile(q)) for q in _QUANTILES},
        gap_threshold_s=gap_threshold_s,
        gap_count=len(gap_deltas),
        gap_count_over_1h=int((deltas > _ONE_HOUR_S).sum()),
        gaps=gaps,
        digital_cardinality={
            c: sorted(float(v) for v in df[c].unique()) for c in digital_columns if c in df
        },
    )
