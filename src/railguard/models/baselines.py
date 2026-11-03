"""Anomaly-score baselines: robust z-score (E0) and Isolation Forest (E1).

Both follow the ``Scorer`` protocol: ``fit`` on normal data, ``score`` returns one value per
row where higher means more anomalous. NaN is rejected rather than imputed.
"""

import logging
from typing import Protocol, Self

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from railguard.evaluation.experiment_config import IsolationForestParams

MAD_TO_STD = 1.4826  # makes MAD comparable to a standard deviation for normal data

_logger = logging.getLogger("railguard")


class Scorer(Protocol):
    def fit(self, features: pd.DataFrame) -> Self: ...

    def score(self, features: pd.DataFrame) -> np.ndarray: ...


def _check_no_nan(features: pd.DataFrame) -> None:
    if features.isna().any().any():
        raise ValueError("features must not contain NaN")


def _select(features: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    missing = [c for c in columns if c not in features.columns]
    if missing:
        raise ValueError(f"missing features: {missing}")
    selected = features[columns]
    _check_no_nan(selected)
    return selected


class RobustZScore:
    """Score = max over features of ``|x - median| / (1.4826 * MAD)`` from the fit data.

    A feature with zero MAD falls back to its standard deviation; if that is also zero it is
    dropped (and logged) so it can never influence a score.
    """

    def __init__(self) -> None:
        self._center: pd.Series | None = None
        self._scale: pd.Series | None = None
        self.dropped_features: tuple[str, ...] = ()

    def fit(self, features: pd.DataFrame) -> Self:
        _check_no_nan(features)
        center = features.median()
        mad_scale = features.sub(center).abs().median() * MAD_TO_STD
        scale = mad_scale.where(mad_scale > 0, features.std())
        usable = scale > 0
        self.dropped_features = tuple(str(c) for c in scale.index[~usable])
        if self.dropped_features:
            _logger.info("RobustZScore: dropped constant features %s", list(self.dropped_features))
        if not usable.any():
            raise ValueError("no usable features: every feature is constant in the fit data")
        self._center, self._scale = center[usable], scale[usable]
        return self

    def score(self, features: pd.DataFrame) -> np.ndarray:
        if self._center is None or self._scale is None:
            raise RuntimeError("call fit before score")
        selected = _select(features, [str(c) for c in self._center.index])
        z = selected.sub(self._center).abs().div(self._scale)
        return z.max(axis=1).to_numpy(dtype="float64")


class IsolationForestScorer:
    """``StandardScaler`` then ``IsolationForest``; score is ``-score_samples`` (higher = odder)."""

    def __init__(self, params: IsolationForestParams, seed: int) -> None:
        self._params = params
        self._seed = seed
        self._columns: list[str] | None = None
        self._scaler = StandardScaler()
        self._forest: IsolationForest | None = None

    def fit(self, features: pd.DataFrame) -> Self:
        _check_no_nan(features)
        self._columns = [str(c) for c in features.columns]
        scaled = self._scaler.fit_transform(features.to_numpy(dtype="float64"))
        self._forest = IsolationForest(
            n_estimators=self._params.n_estimators,
            max_samples=self._params.max_samples,
            contamination=self._params.contamination,
            random_state=self._seed,
        ).fit(scaled)
        return self

    def score(self, features: pd.DataFrame) -> np.ndarray:
        if self._forest is None or self._columns is None:
            raise RuntimeError("call fit before score")
        selected = _select(features, self._columns)
        scaled = self._scaler.transform(selected.to_numpy(dtype="float64"))
        return np.asarray(-self._forest.score_samples(scaled), dtype="float64")
