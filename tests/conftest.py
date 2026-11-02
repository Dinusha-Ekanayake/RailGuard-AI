from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "metropt3_small.csv"
REAL_CSV = ROOT / "datasets" / "raw" / "metropt+3+dataset" / "MetroPT3(AirCompressor).csv"
REAL_SHA = "db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24"


@pytest.fixture
def fixture_csv() -> Path:
    return FIXTURE


@pytest.fixture
def windows_yaml() -> Path:
    return ROOT / "configs" / "metropt3_failure_windows.yaml"
