"""Versioned wire fixtures must remain valid; implicit or foreign writes do not."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).parent / "dashboard/v1"


def test_shared_schema_fixtures():
    fixtures = json.loads((ROOT / "fixtures.json").read_text())
    command = Draft202012Validator(json.loads((ROOT / "control.schema.json").read_text()))
    telemetry = Draft202012Validator(json.loads((ROOT / "telemetry.schema.json").read_text()))
    command.check_schema(command.schema)
    telemetry.check_schema(telemetry.schema)
    for case in fixtures["commands"]:
        command.validate(case)
    for case in fixtures["boolean_cases"]:
        telemetry.validate({"booleans": {"no_feed": case["expected"]}})
    for payload in (
        {"entity": "no_feed"},
        {"entity": "no_feed", "state": "toggle"},
        {"entity": "switch.no_feed", "state": "off"},
    ):
        with pytest.raises(ValidationError):
            command.validate({"topic": "inverter/cmd/toggle", "payload": payload})
    with pytest.raises(ValidationError):
        telemetry.validate({"booleans": {"no_feed": "unknown"}})
