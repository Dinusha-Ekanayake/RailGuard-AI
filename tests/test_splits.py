"""Tests for ``evaluation.splits`` (T-002-05; REQ-002-03)."""

import logging

import pandas as pd
import pytest

from railguard.data.labels import FAILURE, LABELS, PRE_EVENT, UNKNOWN
from railguard.evaluation.experiment_config import SplitConfig
from railguard.evaluation.splits import OUTSIDE, assign_split, fit_mask

T = pd.Timestamp
CONFIG = SplitConfig(
    fit=(T("2020-02-01"), T("2020-04-10")),
    validation=(T("2020-04-10"), T("2020-06-01")),
    test=(T("2020-06-01"), T("2020-09-01")),
)


def _split(*stamps: str) -> list[str]:
    return (
        assign_split(pd.Series(pd.to_datetime(list(stamps), format="ISO8601")), CONFIG)
        .astype(str)
        .tolist()
    )


def test_ranges_are_half_open() -> None:
    got = _split(
        "2020-02-01", "2020-04-09 23:59:59", "2020-04-10", "2020-05-31 23:59:59",
        "2020-06-01", "2020-08-31 23:59:59",
    )  # fmt: skip

    assert got == ["fit", "fit", "validation", "validation", "test", "test"]


def test_rows_outside_every_range_are_marked_outside() -> None:
    assert _split("2020-01-31 23:59:59", "2020-09-01", "2021-01-01") == [OUTSIDE] * 3


def test_keeps_index_and_categorical_dtype() -> None:
    ts = pd.Series(pd.to_datetime(["2020-03-01", "2020-05-01"]), index=[7, 9])
    out = assign_split(ts, CONFIG)

    assert out.index.tolist() == [7, 9]
    assert isinstance(out.dtype, pd.CategoricalDtype)
    assert list(out.cat.categories) == ["fit", "validation", "test", OUTSIDE]


def test_empty_input() -> None:
    assert assign_split(pd.Series([], dtype="datetime64[ns]"), CONFIG).empty


def test_boundaries_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="railguard"):
        assign_split(pd.Series(pd.to_datetime(["2020-03-01"])), CONFIG)

    assert "2020-04-10" in caplog.text
    assert "validation" in caplog.text


def test_fit_mask_excludes_failure_and_pre_event_rows() -> None:
    ts = pd.Series(pd.to_datetime(["2020-03-01"] * 4 + ["2020-05-01", "2020-07-01"]))
    labels = pd.Series([UNKNOWN, FAILURE, PRE_EVENT, UNKNOWN, UNKNOWN, UNKNOWN]).astype(
        pd.CategoricalDtype(categories=list(LABELS))
    )
    mask = fit_mask(assign_split(ts, CONFIG), labels)

    assert mask.tolist() == [True, False, False, True, False, False]
    assert mask.dtype == bool


def test_fit_mask_rejects_misaligned_inputs() -> None:
    split = assign_split(pd.Series(pd.to_datetime(["2020-03-01", "2020-03-02"])), CONFIG)
    labels = pd.Series([UNKNOWN], dtype=pd.CategoricalDtype(categories=list(LABELS)))

    with pytest.raises(ValueError, match="same index"):
        fit_mask(split, labels)
