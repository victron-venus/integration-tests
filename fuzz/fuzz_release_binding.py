"""Fuzz only pure release binding validation; never call a device runner."""
import json
from pathlib import Path
import sys

import atheris

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with atheris.instrument_imports():
    from hardware.device_runner import validate_release_artifact


@atheris.instrument_func
def test_one_input(data):
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError, RecursionError):
        return
    try:
        result = validate_release_artifact(value)
    except ValueError:
        return
    assert result is value
    assert 3 <= len(result["files"]) <= 4096
    for name in result["files"]:
        assert not name.startswith("/") and "\\" not in name
        assert all(part not in ("", ".", "..") for part in name.split("/"))


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
