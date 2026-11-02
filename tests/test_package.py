import railguard


def test_package_exposes_version() -> None:
    assert railguard.__version__ == "0.1.0"
