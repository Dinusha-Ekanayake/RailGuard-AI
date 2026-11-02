"""Gap segmentation: contiguous operating segments, never bridged by interpolation."""

import pandas as pd

from railguard.logging_utils import log_rows

DEFAULT_MAX_GAP_S = 60.0


def assign_segments(ts: pd.Series, max_gap_s: float = DEFAULT_MAX_GAP_S) -> pd.Series:
    """Return 0-based segment IDs; a gap strictly greater than ``max_gap_s`` starts a new one."""
    if max_gap_s < 0:
        raise ValueError("max_gap_s must be non-negative")
    if ts.empty:
        log_rows("assign_segments", 0, 0)
        return pd.Series([], index=ts.index, dtype="int64")
    if ts.isna().any() or not ts.is_monotonic_increasing:
        raise ValueError("timestamps must be non-null and sorted ascending")
    gaps = ts.diff().dt.total_seconds()
    new_segment = gaps > max_gap_s
    segment_ids: pd.Series = new_segment.cumsum().astype("int64")
    log_rows("assign_segments", len(ts), len(ts))
    return segment_ids
