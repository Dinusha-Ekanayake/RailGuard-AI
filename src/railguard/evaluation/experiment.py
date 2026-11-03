"""Run experiment 002: E0 and E1 on each feature variant (pure, no files written).

Per model and variant: fit on the fit mask (no failure or pre-event rows, REQ-002-03), score
every split, pick the alert threshold on validation only (REQ-002-04), then evaluate validation
and test once with that frozen threshold.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from railguard.data.labels import FailureWindow
from railguard.data.metropt3 import TIMESTAMP_COL
from railguard.evaluation.alerts import alert_episodes
from railguard.evaluation.event_metrics import EventMetrics, evaluate_events, operating_hours
from railguard.evaluation.experiment_config import ExperimentConfig
from railguard.evaluation.splits import assign_split, fit_mask
from railguard.evaluation.thresholds import select_threshold
from railguard.features.windows import SEGMENT_COL, FeatureConfig, feature_columns, window_features
from railguard.logging_utils import log_rows
from railguard.models.baselines import IsolationForestScorer, RobustZScore, Scorer

EVAL_SPLITS: tuple[str, ...] = ("validation", "test")
JSON_DECIMALS = 6

_logger = logging.getLogger("railguard")


@dataclass(frozen=True)
class SplitEvaluation:
    """Event metrics for one split at the frozen threshold."""

    operating_hours: float
    alert_episodes: int
    metrics: EventMetrics


@dataclass(frozen=True)
class ModelRun:
    model: str
    variant: str
    threshold: float
    splits: dict[str, SplitEvaluation]


@dataclass(frozen=True)
class ExperimentResult:
    seed: int
    features: dict[str, list[str]]
    runs: list[ModelRun]
    # Validation and test scores per (model, variant): columns score, segment_id, split.
    # Kept for plots only; to_json() never serialises them.
    scores: dict[tuple[str, str], pd.DataFrame] = field(
        default_factory=dict, repr=False, compare=False
    )

    def to_json(self) -> str:
        """Deterministic JSON: sorted keys, floats rounded to 6 dp, no run time."""
        payload = _plain({"seed": self.seed, "features": self.features, "runs": self.runs})
        return json.dumps(payload, sort_keys=True, indent=2)


def _plain(value: Any) -> Any:
    """Convert result objects to JSON-ready values with rounded floats."""
    if isinstance(value, float):
        return round(value, JSON_DECIMALS)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {name: _plain(getattr(value, name)) for name in value.__dataclass_fields__}
    return value


def _variant_columns(all_columns: list[str], removed: tuple[str, ...]) -> list[str]:
    signals = {c.split("__")[0] for c in all_columns}
    unknown = [r for r in removed if r not in signals]
    if unknown:
        raise ValueError(f"removed signals match no feature column: {unknown}")
    return [c for c in all_columns if c.split("__")[0] not in removed]


def _scorers(config: ExperimentConfig) -> dict[str, Scorer]:
    return {
        "E0": RobustZScore(),
        "E1": IsolationForestScorer(config.isolation_forest, config.seed),
    }


def _relevant_windows(
    windows: list[FailureWindow], span: tuple[pd.Timestamp, pd.Timestamp], horizon: pd.Timedelta
) -> list[FailureWindow]:
    """Windows whose ``[start - horizon, end]`` range overlaps the split's ``[start, end)``."""
    return [w for w in windows if w.end >= span[0] and w.start - horizon < span[1]]


def run_experiment(
    df: pd.DataFrame,
    labels: pd.Series,
    windows: list[FailureWindow],
    config: ExperimentConfig,
) -> ExperimentResult:
    """Run E0 and E1 for every feature variant.

    ``labels`` holds one failure-window label per row of ``df`` (same index).
    """
    if not labels.index.equals(df.index):
        raise ValueError("labels must share the index of df")
    feats = window_features(df, FeatureConfig.from_experiment(config))
    row_labels = pd.Series(labels.to_numpy(), index=pd.DatetimeIndex(df[TIMESTAMP_COL]))
    row_labels = row_labels.reindex(feats.index)
    split = assign_split(pd.Series(feats.index, index=feats.index), config.split)
    mask = fit_mask(split, row_labels)
    if not mask.any():
        raise ValueError("no rows left to fit on after excluding failure and pre-event rows")
    all_columns = feature_columns(FeatureConfig.from_experiment(config))
    variants = {n: _variant_columns(all_columns, r) for n, r in config.variants.items()}
    pairs = [
        _run_one(model, scorer, name, columns, feats, split, mask, windows, config)
        for name, columns in variants.items()
        for model, scorer in _scorers(config).items()
    ]
    log_rows("run_experiment", len(df), len(feats))
    return ExperimentResult(
        seed=config.seed,
        features=variants,
        runs=[run for run, _ in pairs],
        scores={(run.model, run.variant): scored for run, scored in pairs},
    )


def _run_one(
    model: str,
    scorer: Scorer,
    variant: str,
    columns: list[str],
    feats: pd.DataFrame,
    split: pd.Series,
    mask: pd.Series,
    windows: list[FailureWindow],
    config: ExperimentConfig,
) -> tuple[ModelRun, pd.DataFrame]:
    scorer.fit(feats.loc[mask, columns])
    scores = pd.Series(scorer.score(feats[columns]), index=feats.index)
    segments = feats[SEGMENT_COL]

    def pick(name: str) -> tuple[pd.Series, pd.Series, list[FailureWindow], float]:
        rows = (split == name).to_numpy()
        if not rows.any():
            raise ValueError(f"the {name} split has no scored rows")
        span = getattr(config.split, name)
        hours = operating_hours(pd.Series(feats.index[rows]), segments[rows])
        return (
            scores[rows],
            segments[rows],
            _relevant_windows(windows, span, config.horizon),
            hours,
        )

    val_scores, val_seg, val_windows, val_hours = pick("validation")
    threshold = select_threshold(
        val_scores, "validation", val_windows, config.horizon, val_hours,
        config.budget_per_hour, config.merge_gap, val_seg,
    )  # fmt: skip
    _logger.info("run_experiment: %s/%s threshold %.6f", model, variant, threshold)
    evaluations: dict[str, SplitEvaluation] = {}
    for name in EVAL_SPLITS:
        s, seg, w, hours = pick(name)
        episodes = alert_episodes(s, threshold, config.merge_gap, seg)
        metrics = evaluate_events(episodes, w, config.horizon, hours)
        evaluations[name] = SplitEvaluation(hours, len(episodes), metrics)
    scored = pd.DataFrame(
        {"score": scores, "segment_id": segments, "split": split.astype(str)}
    ).loc[split.isin(EVAL_SPLITS).to_numpy()]
    return ModelRun(model, variant, threshold, evaluations), scored
