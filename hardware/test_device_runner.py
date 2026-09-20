"""Negative qualification tests: synthetic evidence can test the gate, not qualify a device."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hardware.device_runner import evaluate, main, restore_meter, validate_inventory


@pytest.fixture
def inventory():
    """An intentionally disabled example; never connect to a device in tests."""
    return json.loads(Path(__file__).with_name("inventory.example.json").read_text())


@pytest.fixture
def evidence(inventory):
    """Known-good gate input, visibly synthetic and never published as hardware proof."""
    events = [{"kind": "preflight", "ok": True, "t": 0}]
    for number in range(361):
        elapsed = number * 10
        outage = 1800 <= elapsed < 1820
        state = {
            "uptime": elapsed + 100,
            "dry_run": False,
            "grid_control_valid": not outage,
            "grid_loss_zero_applied": outage,
            "grid_loss_state": "zero" if outage else "normal",
            "perf": {
                "cycle_ms": {"p95": 100, "p99": 150},
                "setvalue_ms": {"p95": 30, "p99": 50},
                "rss_mb": 45,
            },
        }
        events.append({"kind": "sample", "t": elapsed, "state": state})
    events += [
        {"kind": "reconnect", "ok": True, "seconds": 2, "t": i + 1}
        for i in range(inventory["reconnect_count"])
    ]
    events += [{"kind": "meter_down", "t": 1799}, {"kind": "meter_restored", "ok": True, "t": 1811}]
    return events


def test_dry_run_never_opens_transport(inventory, tmp_path, monkeypatch):
    """Planning writes local evidence only and cannot accidentally establish SSH."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hardware").mkdir()
    source = tmp_path / "hardware/inventory.json"
    source.write_text(json.dumps(inventory))
    with patch(
        "hardware.device_runner.subprocess.run", side_effect=AssertionError("network access")
    ):
        assert main(["--inventory", str(source), "--output", str(tmp_path / "reports/report")]) == 0
    assert json.loads((tmp_path / "reports/report/plan.json").read_text())["qualification"] is False


@pytest.mark.parametrize(
    "field,value", [("enabled", False), ("allow_meter_loss", False), ("cleanup_allow", [])]
)
def test_each_authorization_is_required(inventory, field, value):
    """No default, truthy string or missing restoration permission enables faults."""
    inventory.update(enabled=True, allow_meter_loss=True, cleanup_allow=["restore_meter_service"])
    inventory[field] = value
    with pytest.raises(ValueError):
        validate_inventory(inventory, execute=True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ssh_target", "root@host;reboot"),
        ("meter_service", "/service/dbus"),
        ("duration_seconds", 60),
        ("native_client_sha256", "main"),
    ],
)
def test_invalid_scope_is_denied(inventory, field, value):
    """Fault scope is constrained before connection."""
    inventory[field] = value
    with pytest.raises(ValueError):
        validate_inventory(inventory)


def test_cleanup_has_no_ambient_authority(inventory):
    """An unrelated failed run cannot start services."""
    with patch(
        "hardware.device_runner.subprocess.run", side_effect=AssertionError("device mutation")
    ):
        assert restore_meter(inventory, True) is False
        inventory["cleanup_allow"] = ["restore_meter_service"]
        assert restore_meter(inventory, False) is False


def test_complete_gate_input(inventory, evidence):
    """All independently required measurements are present."""
    assert evaluate(inventory, evidence)["passed"] is True


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "dry_run",
        "wedge",
        "restart",
        "rss",
        "p99",
        "nan",
        "reconnect",
        "no_ack",
        "late_zero",
        "cleanup",
        "retained_zero",
        "no_recovery",
    ],
)
def test_fail_closed_evidence(inventory, evidence, change):
    """A green local/mock run cannot excuse a missing device safety observation."""
    samples = [e for e in evidence if e["kind"] == "sample"]
    if change == "missing":
        evidence[:] = evidence[:40]
    elif change == "dry_run":
        samples[30]["state"]["dry_run"] = True
    elif change == "wedge":
        samples[30]["t"] += 20
    elif change == "restart":
        samples[30]["state"]["uptime"] = 1
    elif change == "rss":
        for sample in samples[300:]:
            sample["state"]["perf"]["rss_mb"] = 100
    elif change == "p99":
        samples[30]["state"]["perf"]["setvalue_ms"]["p99"] = 900
    elif change == "nan":
        samples[30]["state"]["perf"]["cycle_ms"]["p95"] = float("nan")
    elif change == "reconnect":
        next(e for e in evidence if e["kind"] == "reconnect")["ok"] = False
    elif change == "no_ack":
        for sample in samples:
            sample["state"]["grid_loss_zero_applied"] = False
    elif change == "late_zero":
        next(e for e in evidence if e["kind"] == "meter_down")["t"] = 1700
    elif change == "cleanup":
        next(e for e in evidence if e["kind"] == "meter_restored")["ok"] = False
    elif change == "retained_zero":
        samples[179]["state"]["grid_loss_zero_applied"] = True
    elif change == "no_recovery":
        for sample in samples[182:]:
            sample["state"]["grid_control_valid"] = False
    assert evaluate(inventory, evidence)["passed"] is False


def test_unacknowledged_execute_never_connects(inventory, tmp_path, monkeypatch):
    """Device identity acknowledgement cannot be replaced by a generic yes."""
    config = copy.deepcopy(inventory)
    config.update(enabled=True, allow_meter_loss=True, cleanup_allow=["restore_meter_service"])
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hardware").mkdir()
    source = tmp_path / "hardware/inventory.json"
    source.write_text(json.dumps(config))
    with patch(
        "hardware.device_runner.subprocess.run", side_effect=AssertionError("network access")
    ):
        with pytest.raises(ValueError, match="ack-device"):
            main(["--inventory", str(source), "--execute", "--ack-device", "yes"])
