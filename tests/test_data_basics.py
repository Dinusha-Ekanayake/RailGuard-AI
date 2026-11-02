import dataclasses
import hashlib
import logging
from pathlib import Path

import pandas as pd
import pytest

from railguard.data.errors import ChecksumMismatchError, SchemaValidationError
from railguard.data.metadata import DatasetMetadata, sha256_file
from railguard.data.metropt3 import load_metropt3, validate_metropt3
from railguard.logging_utils import log_rows


def test_fixture_loads_with_pandas(fixture_csv: Path) -> None:
    assert len(pd.read_csv(fixture_csv)) == 50


def test_sha256_matches_hashlib(tmp_path: Path) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc" * 1000)
    assert sha256_file(p) == hashlib.sha256(b"abc" * 1000).hexdigest()


def test_metadata_is_frozen() -> None:
    m = DatasetMetadata("n", "p", "s", 1, ("a",), "t")
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.rows = 2  # type: ignore[misc]


def test_log_rows_captures_counts(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="railguard"):
        log_rows("step", 10, 8)
    assert "step" in caplog.text
    assert "before=10" in caplog.text
    assert "after=8" in caplog.text


def test_load_drops_index_and_parses(fixture_csv: Path) -> None:
    df, meta = load_metropt3(fixture_csv)
    assert not any(str(c).startswith("Unnamed") for c in df.columns)
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert meta.rows == 50
    assert df["COMP"].dtype == "int8"
    assert df["TP2"].dtype == "float32"
    validate_metropt3(df)


def test_load_checksum_ok_and_mismatch(fixture_csv: Path) -> None:
    _, meta = load_metropt3(fixture_csv)
    load_metropt3(fixture_csv, meta.sha256)
    with pytest.raises(ChecksumMismatchError):
        load_metropt3(fixture_csv, "0" * 64)


def _df(fixture_csv: Path) -> pd.DataFrame:
    return load_metropt3(fixture_csv)[0]


def test_validate_missing_column(fixture_csv: Path) -> None:
    with pytest.raises(SchemaValidationError) as e:
        validate_metropt3(_df(fixture_csv).drop(columns=["TP2"]))
    assert e.value.column == "TP2"


def test_validate_unparseable_timestamp(fixture_csv: Path) -> None:
    df = _df(fixture_csv)
    df.loc[3, "timestamp"] = pd.NaT
    with pytest.raises(SchemaValidationError) as e:
        validate_metropt3(df)
    assert e.value.column == "timestamp"


def test_validate_unsorted(fixture_csv: Path) -> None:
    df = _df(fixture_csv).iloc[::-1].reset_index(drop=True)
    with pytest.raises(SchemaValidationError, match="timestamp"):
        validate_metropt3(df)


def test_validate_duplicate(fixture_csv: Path) -> None:
    df = _df(fixture_csv)
    df.loc[1, "timestamp"] = df.loc[0, "timestamp"]
    with pytest.raises(SchemaValidationError, match="duplicate"):
        validate_metropt3(df)


def test_validate_non_numeric(fixture_csv: Path) -> None:
    df = _df(fixture_csv)
    df["TP3"] = df["TP3"].astype(str)
    with pytest.raises(SchemaValidationError) as e:
        validate_metropt3(df)
    assert e.value.column == "TP3"


def test_validate_digital_value_two(fixture_csv: Path) -> None:
    df = _df(fixture_csv)
    df["MPG"] = df["MPG"].astype("int64")
    df.loc[0, "MPG"] = 2
    with pytest.raises(SchemaValidationError) as e:
        validate_metropt3(df)
    assert e.value.column == "MPG"


def test_validate_null_analogue(fixture_csv: Path) -> None:
    df = _df(fixture_csv)
    df.loc[2, "H1"] = float("nan")
    with pytest.raises(SchemaValidationError) as e:
        validate_metropt3(df)
    assert e.value.column == "H1"


def test_load_missing_timestamp_column(tmp_path: Path) -> None:
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n")
    with pytest.raises(SchemaValidationError, match="timestamp"):
        load_metropt3(p)
