#!/usr/bin/env python3
"""Default-off Cerbo qualification. No SSH, imports or device access in dry-run."""

import argparse
import hashlib
import json
import math
import queue
import re
import signal
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path


def finite(value):
    """Booleans, nulls and NaN are not measured numbers."""
    return type(value) in (int, float) and math.isfinite(value)


def validate_inventory(config, execute=False):
    """Validate the complete, explicit lab contract before any connection."""
    required = {
        "schema_version",
        "device_id",
        "enabled",
        "ssh_target",
        "python",
        "controller_root",
        "controller_version",
        "native_client_sha256",
        "venus_firmware",
        "identity",
        "meter_service",
        "allow_meter_loss",
        "cleanup_allow",
        "duration_seconds",
        "reconnect_count",
        "limits",
    }
    if set(config) != required or config["schema_version"] != 1:
        raise ValueError("Inventory must have exactly the schema v1 fields")
    patterns = {
        "device_id": r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}",
        "ssh_target": r"[a-zA-Z0-9_.-]+@[a-zA-Z0-9][a-zA-Z0-9.-]*",
        "python": r"/[a-zA-Z0-9_./-]+",
        "controller_root": r"/[a-zA-Z0-9_./-]+",
        "native_client_sha256": r"[0-9a-f]{64}",
        "meter_service": r"/service/[a-zA-Z0-9_-]+",
    }
    for key, pattern in patterns.items():
        if not isinstance(config[key], str) or not re.fullmatch(pattern, config[key]):
            raise ValueError(f"Invalid inventory field: {key}")
    if config["meter_service"] in {
        "/service/inverter-control",
        "/service/dbus",
        "/service/flashmq",
    }:
        raise ValueError("Only the dedicated lab meter service may be faulted")
    if type(config["enabled"]) is not bool or type(config["allow_meter_loss"]) is not bool:
        raise ValueError("Authorization flags must be booleans")
    if (
        config["controller_root"] != "/data/inverter-control"
        or config["python"] != "/usr/bin/python3"
    ):
        raise ValueError(
            "Only the reviewed /data/inverter-control installation and /usr/bin/python3 are supported"
        )
    for key in ("controller_version", "venus_firmware"):
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f"Missing exact identity: {key}")
    roles = {"target_product", "target_firmware", "bms_product", "bms_firmware", "meter_product"}
    probes = config["identity"]
    if not isinstance(probes, list) or len(probes) != 5 or {p["role"] for p in probes} != roles:
        raise ValueError("Inventory requires exact target, BMS and meter identities")
    for probe in probes:
        if set(probe) != {"role", "service", "path", "expected"}:
            raise ValueError("Invalid identity probe")
        if not re.fullmatch(r"com\.victronenergy\.[a-zA-Z0-9_.-]+", probe["service"]):
            raise ValueError("Invalid identity service")
        if not re.fullmatch(r"/[a-zA-Z0-9_/]+", probe["path"]) or not isinstance(
            probe["expected"], str
        ):
            raise ValueError("Invalid identity path/value")
    if config["cleanup_allow"] not in ([], ["restore_meter_service"]):
        raise ValueError("Cleanup can only restore this run's stopped meter service")
    if (
        type(config["duration_seconds"]) is not int
        or not 3600 <= config["duration_seconds"] <= 21600
    ):
        raise ValueError("Soak must run between one and six hours")
    if type(config["reconnect_count"]) is not int or not 10 <= config["reconnect_count"] <= 100:
        raise ValueError("Reconnect storm requires 10..100 cycles")
    keys = {
        "cycle_p95_ms",
        "cycle_p99_ms",
        "write_p95_ms",
        "write_p99_ms",
        "rss_drift_mb",
        "sample_gap_seconds",
        "probe_deadline_seconds",
        "accepted_zero_seconds",
    }
    if set(config["limits"]) != keys or not all(
        finite(v) and v > 0 for v in config["limits"].values()
    ):
        raise ValueError("Every gate needs a finite positive threshold")
    if execute and (
        config["enabled"] is not True
        or config["allow_meter_loss"] is not True
        or config["cleanup_allow"] != ["restore_meter_service"]
    ):
        raise ValueError(
            "Execution requires device opt-in, meter-loss approval and exact restoration permission"
        )
    return config


def evaluate(config, events):
    """Reject incomplete/stale evidence; percentiles are maxima of rolling windows."""
    errors = []
    samples = [e for e in events if e["kind"] == "sample"]
    limits = config["limits"]
    result = {
        "schema_version": 1,
        "device_id": config["device_id"],
        "passed": False,
        "metric_scope": "maximum observed rolling-window percentile",
        "errors": errors,
    }
    if len(samples) < 100:
        errors.append("insufficient fresh samples")
        return result
    times = [s["t"] for s in samples]
    duration = times[-1] - times[0]
    gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
    result.update(duration_seconds=duration, samples=len(samples), max_sample_gap=max(gaps))
    if (
        duration < config["duration_seconds"]
        or min(gaps) <= 0
        or max(gaps) > limits["sample_gap_seconds"]
    ):
        errors.append("soak duration/monotonic freshness gate failed (possible event-loop wedge)")
    states = [s["state"] for s in samples]
    uptimes = [s.get("uptime") for s in states]
    if (
        not all(finite(u) for u in uptimes)
        or any(b < a for a, b in zip(uptimes, uptimes[1:], strict=False))
        or uptimes[-1] - uptimes[0] < duration - limits["sample_gap_seconds"]
    ):
        errors.append("controller restart or frozen uptime")
    if any(s.get("dry_run") is not False for s in states):
        errors.append("controller dry-run/missing execution identity")
    metrics = [s.get("perf", {}) for s in states]
    for section, pct, limit in (
        ("cycle_ms", "p95", "cycle_p95_ms"),
        ("cycle_ms", "p99", "cycle_p99_ms"),
        ("setvalue_ms", "p95", "write_p95_ms"),
        ("setvalue_ms", "p99", "write_p99_ms"),
    ):
        values = [m.get(section, {}).get(pct) for m in metrics]
        if not all(finite(v) and v >= 0 for v in values):
            errors.append(f"missing/nonfinite {section}.{pct}")
        else:
            result[limit] = max(values)
            if max(values) > limits[limit]:
                errors.append(f"{limit} exceeded")
    rss = [m.get("rss_mb") for m in metrics]
    if not all(finite(v) and v > 0 for v in rss):
        errors.append("RSS evidence missing")
    else:
        width = max(1, len(rss) // 10)
        drift = statistics.median(rss[-width:]) - statistics.median(rss[:width])
        result["rss_drift_mb"] = drift
        if drift > limits["rss_drift_mb"]:
            errors.append("RSS drift exceeded")
    probes = [e for e in events if e["kind"] == "reconnect"]
    if len(probes) != config["reconnect_count"] or any(
        e.get("ok") is not True
        or not finite(e.get("seconds"))
        or not 0 <= e["seconds"] <= limits["probe_deadline_seconds"]
        for e in probes
    ):
        errors.append("native client reconnect/wedge gate failed")
    faults = [e for e in events if e["kind"] == "meter_down"]
    cleanups = [e for e in events if e["kind"] == "meter_restored"]
    if len(faults) != 1 or len(cleanups) != 1 or cleanups[0].get("ok") is not True:
        errors.append("real meter-loss or verified cleanup evidence missing")
    else:
        fault = faults[0]["t"]
        before = [s for s in samples if s["t"] < fault]
        accepted = [
            s
            for s in samples
            if fault <= s["t"] < cleanups[0]["t"]
            and s["state"].get("grid_control_valid") is False
            and s["state"].get("grid_loss_zero_applied") is True
            and s["state"].get("grid_loss_state") == "zero"
        ]
        if (
            not before
            or before[-1]["state"].get("grid_control_valid") is not True
            or before[-1]["state"].get("grid_loss_zero_applied") is not False
        ):
            errors.append("meter was not healthy with cleared zero acknowledgement before fault")
        if not accepted:
            errors.append("no accepted zero during real meter loss")
        else:
            result["accepted_zero_seconds"] = accepted[0]["t"] - fault
            if result["accepted_zero_seconds"] > limits["accepted_zero_seconds"]:
                errors.append("accepted-zero deadline exceeded")
        if not any(
            s["t"] > cleanups[0]["t"] and s["state"].get("grid_control_valid") is True
            for s in samples
        ):
            errors.append("meter did not recover after cleanup")
    if not any(e["kind"] == "preflight" and e.get("ok") is True for e in events):
        errors.append("identity preflight evidence missing")
    if any(e["kind"] == "error" for e in events):
        errors.append("runner error")
    result["passed"] = not errors
    return result


def checked_service(path):
    """Reject option injection and paths outside the dedicated service namespace."""
    if not isinstance(path, str) or re.fullmatch(r"/service/[a-zA-Z0-9_-]+", path) is None:
        raise ValueError("Invalid meter service")
    if path in {"/service/inverter-control", "/service/dbus", "/service/flashmq"}:
        raise ValueError("Shared infrastructure cannot be faulted")
    return path


def service_running(path):
    """Require an existing supervised service; never infer ownership from a PID alone."""
    path = checked_service(path)
    result = subprocess.run(["svstat", path], check=True, capture_output=True, text=True, timeout=5)
    return re.search(r": up \(pid \d+\)", result.stdout) is not None


def restore_meter(config, attempted):
    """No broad cleanup: only undo this process's authorized, journaled stop."""
    if not attempted or config["cleanup_allow"] != ["restore_meter_service"]:
        return False
    subprocess.run(["svc", "-u", checked_service(config["meter_service"])], check=True, timeout=5)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if service_running(config["meter_service"]):
            return True
        time.sleep(0.2)
    return False


def run_device(config, preflight_only=False):
    """Executed on the explicitly selected lab device, never on a PR runner."""
    validate_inventory(config, execute=True)
    events = []
    lock = threading.Lock()

    def emit(kind, **data):
        event = {"kind": kind, "t": time.monotonic(), **data}
        with lock:
            events.append(event)
            print(json.dumps(event, allow_nan=False), flush=True)
        return event

    def terminate(_signum, _frame):
        raise InterruptedError("qualification interrupted")

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    root = Path("/data/inverter-control")
    if (root / "version").read_text().strip() != config["controller_version"]:
        raise ValueError("Controller version mismatch")
    if (
        hashlib.sha256((root / "inverter_control/dbus_native.py").read_bytes()).hexdigest()
        != config["native_client_sha256"]
    ):
        raise ValueError("Native client source hash mismatch")
    if Path("/opt/victronenergy/version").read_text().strip() != config["venus_firmware"]:
        raise ValueError("Venus firmware mismatch")
    sys.path.insert(0, str(root))
    import paho.mqtt.client as mqtt  # noqa: PLC0415
    from inverter_control.dbus_native import NativeDbusClient  # noqa: PLC0415

    client = NativeDbusClient()
    broker = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    incoming = queue.Queue(maxsize=10000)
    stop = threading.Event()
    attempted = False

    def on_message(_client, _userdata, message):
        if message.topic == "inverter/state" and not message.retain:
            try:
                incoming.put_nowait((time.monotonic(), json.loads(message.payload)))
            except (ValueError, queue.Full):
                stop.set()  # Lost evidence is a gate failure, not a silently skipped sample.

    def reconnect_probe():
        # Only this read-only probe connection is disconnected. No global bus or
        # production controller service is restarted by this test.
        probe = config["identity"][0]
        for _ in range(config["reconnect_count"]):
            started = time.monotonic()
            client._mark_failure(client._get_bus())  # exact production reconnect path
            deadline = started + config["limits"]["probe_deadline_seconds"]
            ok = False
            while not stop.is_set() and time.monotonic() < deadline:
                if (
                    client.get_value(probe["service"], probe["path"], timeout=0.5)
                    == probe["expected"]
                ):
                    ok = True
                    break
                time.sleep(0.1)
            emit("reconnect", ok=ok, seconds=time.monotonic() - started)
            if not ok:
                stop.set()
                break

    try:
        observed = []
        for probe in config["identity"]:
            value = client.get_value(probe["service"], probe["path"], timeout=1)
            if value != probe["expected"]:
                raise ValueError(f"Identity mismatch: {probe['role']}")
            observed.append({**probe, "observed": value})
        if not service_running(config["meter_service"]):
            raise ValueError("Lab meter service must already be running")
        emit(
            "preflight",
            ok=True,
            identity=observed,
            controller_version=config["controller_version"],
            native_client_sha256=config["native_client_sha256"],
            venus_firmware=config["venus_firmware"],
        )
        if preflight_only:
            emit("preflight_only", qualification=False)
            return 0
        broker.on_message = on_message
        broker.on_connect = lambda connection, *_args: connection.subscribe("inverter/state", qos=1)
        broker.connect("127.0.0.1", 1883, keepalive=30)
        broker.loop_start()
        started = time.monotonic()
        first = None
        last_sample = float("-inf")
        fault_time = None
        restored = False
        worker = None
        duration = min(21600, max(3600, int(config["duration_seconds"])))
        while first is None or time.monotonic() - first <= duration + 1:
            if stop.is_set():
                raise RuntimeError("Reconnect or evidence collector failed")
            try:
                received, state = incoming.get(timeout=config["limits"]["sample_gap_seconds"])
            except queue.Empty as error:
                raise TimeoutError(
                    "Controller state absent: event-loop wedge or MQTT loss"
                ) from error
            if time.monotonic() - received > config["limits"]["sample_gap_seconds"]:
                raise TimeoutError("State queue is stale")
            if received - last_sample < 1:
                continue
            last_sample = received
            # Bound the observer's own CPU/RSS: retain only gate evidence, at 1 Hz.
            state = {
                key: state.get(key)
                for key in (
                    "uptime",
                    "dry_run",
                    "grid_control_valid",
                    "grid_loss_zero_applied",
                    "grid_loss_state",
                    "perf",
                )
            }
            if first is None:
                if state.get("dry_run") is not False or state.get("grid_control_valid") is not True:
                    raise ValueError(
                        "Controller must be live with a valid meter before qualification"
                    )
                first = received
                worker = threading.Thread(target=reconnect_probe, daemon=True)
                worker.start()
            emit("sample", t=received, state=state)
            if fault_time is None and received - started >= config["duration_seconds"] / 2:
                if (
                    state.get("grid_control_valid") is not True
                    or state.get("grid_loss_zero_applied") is not False
                ):
                    raise ValueError("Meter is not healthy immediately before fault")
                # Journal before the command: even an uncertain subprocess result requires restoration.
                attempted = True
                fault_time = emit("meter_down", service=config["meter_service"])["t"]
                subprocess.run(
                    ["svc", "-d", checked_service(config["meter_service"])], check=True, timeout=5
                )
            if fault_time is not None and not restored:
                accepted = (
                    state.get("grid_control_valid") is False
                    and state.get("grid_loss_zero_applied") is True
                    and state.get("grid_loss_state") == "zero"
                )
                if (
                    accepted
                    or time.monotonic() - fault_time > config["limits"]["accepted_zero_seconds"] + 2
                ):
                    restored = restore_meter(config, attempted)
                    emit("meter_restored", ok=restored)
                    if not restored:
                        raise RuntimeError("Meter restoration failed; operator recovery required")
                    attempted = False
        if worker is not None:
            worker.join(timeout=1)
            if worker.is_alive():
                raise TimeoutError("Native probe event-loop wedged")
    except Exception as error:  # Evidence and cleanup must survive any scenario failure.
        emit("error", error=type(error).__name__, message=str(error))
    finally:
        stop.set()
        if attempted:
            try:
                emit("meter_restored", ok=restore_meter(config, attempted))
            except Exception as error:
                emit("cleanup_error", error=type(error).__name__)
        broker.disconnect()
        broker.loop_stop()
        client.close()
    result = evaluate(config, events)
    emit("result", **result)
    return 0 if result["passed"] else 1


def main(argv=None):
    """Plan offline, or execute this reviewed source through host-key-checked SSH."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/hardware"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--ack-device")
    parser.add_argument("--agent", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.agent:
        return run_device(json.load(sys.stdin), args.preflight)
    inventory = args.inventory.resolve(strict=True)
    allowed_inventory = (Path.cwd() / "hardware").resolve()
    if not inventory.is_relative_to(allowed_inventory) and not inventory.is_relative_to(
        Path("/etc/victron-lab")
    ):
        raise ValueError("Inventory must be in hardware/ or /etc/victron-lab/")
    config = validate_inventory(json.loads(inventory.read_text()), execute=args.execute)
    if args.execute and args.ack_device != config["device_id"]:
        raise ValueError("--ack-device must exactly match the inventory device")
    reports_root = (Path.cwd() / "reports").resolve()
    output = args.output.resolve()
    if output == reports_root or not output.is_relative_to(reports_root):
        raise ValueError("Evidence output must be a new directory under reports/")
    output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).read_text()
    mode = "dry-run"
    if args.execute:
        mode = "preflight" if args.preflight else "execute"
    plan = {
        "mode": mode,
        "qualification": False,
        "inventory": config,
        "runner_sha256": hashlib.sha256(source.encode()).hexdigest(),
    }
    (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    if not args.execute:
        print(
            "Dry-run only: inventory validated; no SSH or hardware access. No qualification result."
        )
        return 0
    target = config["ssh_target"]
    if re.fullmatch(r"[a-zA-Z0-9_.-]+@[a-zA-Z0-9][a-zA-Z0-9.-]*", target) is None:
        raise ValueError("Invalid SSH destination")
    # The remote shell receives only a constant command. Source and JSON data
    # travel on stdin; repr produces a Python string literal, not executable input.
    program = source.rsplit('if __name__ == "__main__":', 1)[0]
    program += (
        f"\nraise SystemExit(run_device(json.loads({json.dumps(config)!r}), {args.preflight!r}))\n"
    )
    ssh = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=10",
        "-o",
        "ServerAliveCountMax=3",
        target,
        "/usr/bin/python3 -u -",
    ]
    code = 1
    try:
        process = subprocess.run(
            ssh,
            input=program,
            text=True,
            capture_output=True,
            timeout=config["duration_seconds"] + 300,
            check=False,
        )
        stdout, stderr, code = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode()
        stderr = "Remote deadline exceeded; independently verify meter service restoration.\n"
    (output / "events.jsonl").write_text(stdout)
    (output / "stderr.log").write_text(stderr)
    try:
        events = [json.loads(line) for line in stdout.splitlines()]
        if args.preflight:
            result = {
                "passed": False,
                "qualification": False,
                "mode": "preflight",
                "exit_code": code,
            }
        else:
            result = evaluate(config, events)
            if code:
                result["passed"] = False
                result["errors"].append("SSH/device process failed")
            if not result["passed"]:
                code = 1
    except (ValueError, KeyError, TypeError) as error:
        result = {"passed": False, "error": type(error).__name__}
        code = 1
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()
    }
    (output / "sha256.json").write_text(json.dumps(hashes, indent=2) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
