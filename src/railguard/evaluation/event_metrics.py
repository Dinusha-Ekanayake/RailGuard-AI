"""Event-level metrics: detection, lead time and alerts outside documented windows (spec 002)."""

from dataclasses import dataclass

import pandas as pd

from railguard.data.labels import FailureWindow
from railguard.evaluation.alerts import AlertEpisode
from railguard.logging_utils import log_rows

SECONDS_PER_HOUR = 3600.0


@dataclass(frozen=True)
class EventResult:
    """Outcome for one documented event. ``lead_time_s`` is negative after the window began."""

    event_id: int
    detected: bool
    lead_time_s: float | None
    first_alert: pd.Timestamp | None


@dataclass(frozen=True)
class EventMetrics:
    events: list[EventResult]
    detected: int
    outside_alerts: int
    outside_per_hour: float


def operating_hours(ts: pd.Series, segment_ids: pd.Series) -> float:
    """Sum of per-segment durations in hours, so gaps between segments are excluded."""
    if len(ts) != len(segment_ids):
        raise ValueError("ts and segment_ids must have the same length")
    if segment_ids.isna().any():
        raise ValueError("segment_ids contain NaN")
    times = pd.Series(pd.to_datetime(ts).to_numpy())
    grouped = times.groupby(segment_ids.to_numpy())
    seconds = (grouped.max() - grouped.min()).dt.total_seconds()
    return float(seconds.sum() / SECONDS_PER_HOUR)


def evaluate_events(
    episodes: list[AlertEpisode],
    windows: list[FailureWindow],
    horizon: pd.Timedelta,
    op_hours: float,
) -> EventMetrics:
    """Score episodes against documented windows.

    An event is detected when an episode overlaps ``[start - horizon, end]`` (inclusive).
    The first alert is the earliest alert time inside the range, i.e.
    ``max(earliest overlapping episode start, start - horizon)``, so lead time
    (``start - first alert``) never exceeds the horizon and is negative after the window
    began. Episodes overlapping no such range count as alerts outside windows, per operating hour.
    """
    if op_hours <= 0:
        raise ValueError("operating hours must be positive")
    results: list[EventResult] = []
    inside: set[int] = set()
    for window in windows:
        lo = window.start - horizon
        hits = [i for i, e in enumerate(episodes) if e.end >= lo and e.start <= window.end]
        inside.update(hits)
        if not hits:
            results.append(EventResult(window.id, False, None, None))
            continue
        first = min(max(episodes[i].start, lo) for i in hits)
        lead = (window.start - first).total_seconds()
        results.append(EventResult(window.id, True, lead, first))
    outside = len(episodes) - len(inside)
    log_rows("evaluate_events", len(episodes), outside)
    return EventMetrics(
        events=results,
        detected=sum(r.detected for r in results),
        outside_alerts=outside,
        outside_per_hour=outside / op_hours,
    )
