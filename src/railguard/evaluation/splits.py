"""Chronological split assignment and the fit mask (spec 002, REQ-002-03)."""

import logging

import numpy as np
import pandas as pd

from railguard.data.labels import FAILURE, PRE_EVENT
from railguard.evaluation.experiment_config import SPLIT_NAMES, SplitConfig

OUTSIDE = "outside"
SPLIT_CATEGORIES: tuple[str, ...] = (*SPLIT_NAMES, OUTSIDE)
FIT = "fit"
EXCLUDED_FROM_FIT: tuple[str, ...] = (FAILURE, PRE_EVENT)

_logger = logging.getLogger("railguard")


def assign_split(ts: pd.Series, config: SplitConfig) -> pd.Series:
    """Label each timestamp ``fit``, ``validation``, ``test`` or ``outside``.

    Ranges are half-open ``[start, end)``. Rows in none of them are ``outside``.
    The boundaries used are logged.
    """
    for name in SPLIT_NAMES:
        start, end = getattr(config, name)
        _logger.info("assign_split: %s = [%s, %s)", name, start, end)
    values = np.full(len(ts), OUTSIDE, dtype=object)
    for name in SPLIT_NAMES:
        start, end = getattr(config, name)
        values[((ts >= start) & (ts < end)).to_numpy()] = name
    dtype = pd.CategoricalDtype(categories=list(SPLIT_CATEGORIES))
    return pd.Series(values, index=ts.index).astype(dtype)


def fit_mask(split: pd.Series, labels: pd.Series) -> pd.Series:
    """True for rows that may be used to fit: in the fit split and not failure or pre-event."""
    if not split.index.equals(labels.index):
        raise ValueError("split and labels must have the same index")
    mask = (split == FIT) & ~labels.isin(EXCLUDED_FROM_FIT)
    _logger.info("fit_mask: %d of %d rows usable for fitting", int(mask.sum()), len(mask))
    return mask.astype(bool)
