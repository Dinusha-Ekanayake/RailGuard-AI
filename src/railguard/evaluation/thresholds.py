"""Alert-threshold selection on validation scores only (REQ-002-04)."""

import logging

import numpy as np
import pandas as pd

from railguard.data.labels import FailureWindow
from railguard.evaluation.alerts import alert_episodes
from railguard.evaluation.event_metrics import evaluate_events

logger = logging.getLogger(__name__)

# Fixed quantile grid of validation scores.
CANDIDATE_QUANTILES: tuple[float, ...] = (
    0.90, 0.95, 0.99, 0.995, 0.999, 0.9995, 0.9999, 0.99995, 0.99999,
)  # fmt: skip


def select_threshold(
    scores: pd.Series,
    split_name: str,
    windows: list[FailureWindow],
    horizon: pd.Timedelta,
    op_hours: float,
    budget_per_hour: float,
    merge_gap: pd.Timedelta,
    segment_ids: pd.Series,
) -> float:
    """Lowest candidate whose alerts outside windows fit the budget, else the highest.

    Refuses any split other than ``"validation"`` (REQ-002-04).
    """
    if split_name != "validation":
        raise ValueError(
            f"thresholds are tuned on the validation split only, got {split_name!r} (REQ-002-04)"
        )
    if scores.empty:
        raise ValueError("scores are empty")
    if not np.isfinite(scores.to_numpy()).all():
        raise ValueError("scores must all be finite")
    candidates = [float(np.quantile(scores.to_numpy(), q)) for q in CANDIDATE_QUANTILES]
    for threshold in sorted(candidates):
        episodes = alert_episodes(scores, threshold, merge_gap, segment_ids)
        metrics = evaluate_events(episodes, windows, horizon, op_hours)
        if metrics.outside_per_hour <= budget_per_hour:
            return threshold
    logger.warning("no candidate within budget %.4f per hour; using the highest", budget_per_hour)
    return max(candidates)
