"""Failure-window labels. Rows outside the reported windows are unknown, never healthy."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from railguard.logging_utils import log_rows

FAILURE = "documented_failure_window"
PRE_EVENT = "pre_event_window"
UNKNOWN = "unlabelled_or_unknown"
LABELS: tuple[str, ...] = (FAILURE, PRE_EVENT, UNKNOWN)


@dataclass(frozen=True)
class FailureWindow:
    id: int
    start: pd.Timestamp
    end: pd.Timestamp
    failure: str
    severity: str
    maintenance: str | None
    note: str


def load_failure_windows(yaml_path: str | Path) -> list[FailureWindow]:
    """Load failure windows from YAML, requiring start < end."""
    with Path(yaml_path).open(encoding="utf-8") as handle:
        content = yaml.safe_load(handle)
    windows = [
        FailureWindow(
            id=int(item["id"]),
            start=pd.Timestamp(item["start"]),
            end=pd.Timestamp(item["end"]),
            failure=str(item["failure"]),
            severity=str(item["severity"]),
            maintenance=item.get("maintenance"),
            note=str(item.get("note") or ""),
        )
        for item in content["windows"]
    ]
    if len({w.id for w in windows}) != len(windows):
        raise ValueError("duplicate window ids")
    for window in windows:
        if window.start >= window.end:
            raise ValueError(f"window {window.id}: start must be before end")
    return windows


def assign_labels(
    ts: "pd.Series[pd.Timestamp]",
    windows: list[FailureWindow],
    pre_event_horizon: pd.Timedelta,
) -> pd.Series:
    """Give each timestamp exactly one label (failure > pre-event > unknown).

    Window bounds are inclusive. The pre-event window is ``[start - horizon, start)``.
    """
    if pre_event_horizon < pd.Timedelta(0):
        raise ValueError("pre_event_horizon must be non-negative")
    in_failure = pd.Series(False, index=ts.index)
    in_pre = pd.Series(False, index=ts.index)
    for window in windows:
        in_failure |= (ts >= window.start) & (ts <= window.end)
        in_pre |= (ts >= window.start - pre_event_horizon) & (ts < window.start)
    labels = pd.Series(UNKNOWN, index=ts.index, dtype=object)
    labels[in_pre] = PRE_EVENT
    labels[in_failure] = FAILURE
    log_rows("assign_labels", len(ts), len(labels))
    return labels.astype(pd.CategoricalDtype(categories=list(LABELS)))
