"""Offline lifecycle adapters for the actual checked-out device runner.

All original function bodies are compiled verbatim with allowlisted fake imports,
paths, MQTT, subprocesses, clocks and threads. The audit guard additionally blocks
real I/O, even when production exception handling catches the blocked operation.
Source and inventory reads happen before the guard; device code is never imported.

Threads execute deterministically here. These tests establish ordering and cleanup
ownership, not real-thread timing, signal delivery or hardware qualification.
"""

import ast
import builtins
import copy
import hashlib
import json
import math
import queue
import re
import signal
import statistics
import subprocess
import sys
from collections import deque
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

SOURCE = Path(__file__).with_name("device_runner.py")
TEXT = SOURCE.read_text()
INVENTORY = json.loads(SOURCE.with_name("inventory.example.json").read_text())
BLOCK_EXTERNAL = False
FORBIDDEN_EVENTS = []


def audit(event, args):
    if BLOCK_EXTERNAL and (
        event == "open"
        or event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn"))
        or event in {"os.system", "os.fork", "_thread.start_new_thread"}
    ):
        FORBIDDEN_EVENTS.append(event)
        raise AssertionError(f"External capability attempted: {event}")


sys.addaudithook(audit)


class Lab:
    def __init__(self, name, **options):
        self.name, self.options = name, options
        self.trace, self.events = [], []
        self.now, self.sample, self.stopped, self.locked = 0.0, 0, False, False
        self.hits, self.threads, self.restore_calls = {}, [], 0
        self.config = copy.deepcopy(INVENTORY)
        self.config.update(
            enabled=True,
            allow_meter_loss=True,
            cleanup_allow=["restore_meter_service"],
            reconnect_count=10,
            native_client_sha256=hashlib.sha256(b"synthetic native source").hexdigest(),
        )
        self.handlers = {}
        self.files = {
            "/data/inverter-control/version": self.config["controller_version"].encode(),
            "/data/inverter-control/inverter_control/dbus_native.py": b"synthetic native source",
            "/opt/victronenergy/version": self.config["venus_firmware"].encode(),
        }
        if options.get("identity_file"):
            self.files["/data/inverter-control/version"] = b"wrong version"

    def log(self, kind, *args):
        self.trace.append([kind, *copy.deepcopy(args)])

    def point(self, name):
        self.hits[name] = self.hits.get(name, 0) + 1
        self.log("point", name, self.hits[name])
        faults = self.options.get("faults", []) + (
            [self.options["fault"]] if self.options.get("fault") else []
        )
        for spec in faults:
            if spec[0] == name and self.hits[name] == spec[1]:
                error = spec[2]
                if error == "signal":
                    self.handlers[signal.SIGTERM](signal.SIGTERM, None)
                if error == "timeout":
                    raise subprocess.TimeoutExpired(["synthetic", name], 5)
                if error == "process":
                    raise subprocess.CalledProcessError(17, ["synthetic", name])
                raise {
                    "value": ValueError,
                    "runtime": RuntimeError,
                    "interrupt": InterruptedError,
                    "base": KeyboardInterrupt,
                    "os": OSError,
                }[error](name)

    def monotonic(self):
        self.log("clock", self.now)
        return self.now

    def sleep(self, seconds):
        self.log("sleep", seconds)
        self.now += seconds

    def printed(self, text, *, flush):
        assert flush and self.locked
        event = json.loads(text)
        self.log("print", event)
        self.point("print:" + event["kind"])
        self.events.append(event)

    def command(self, argv, **kwargs):
        allowed = argv in (
            ["svc", "-d", self.config["meter_service"]],
            ["svc", "-u", self.config["meter_service"]],
            ["svstat", self.config["meter_service"]],
        )
        assert allowed, argv
        self.log("command", argv, kwargs)
        name = "command:" + " ".join(argv[:2])
        if argv[:2] == ["svc", "-u"]:
            self.restore_calls += 1
            # Restoration acknowledgement occurs strictly after the received
            # zero sample, as a real command/handshake does (without sleeping).
            self.now += 0.001
        self.point(name)
        up = not self.options.get("restore_false") or self.restore_calls == 0
        return SimpleNamespace(stdout=": up (pid 123)" if up else ": down 1 seconds", returncode=0)

    def namespace(self):
        lab = self

        class DevicePath:
            def __init__(self, value):
                self.value = str(PurePosixPath(value))

            def __truediv__(self, other):
                return DevicePath(str(PurePosixPath(self.value) / other))

            def __str__(self):
                return self.value

            def read_bytes(self):
                lab.log("path.read", self.value)
                assert self.value in lab.files, self.value
                return lab.files[self.value]

            def read_text(self):
                return self.read_bytes().decode()

        class Lock:
            def __enter__(self):
                assert not lab.locked
                lab.locked = True
                lab.log("lock.enter")

            def __exit__(self, *_args):
                lab.locked = False
                lab.log("lock.exit")

        class Event:
            def set(self):
                lab.log("stop.set")
                lab.stopped = True

            def is_set(self):
                lab.log("stop.is_set", lab.stopped)
                return lab.stopped

        class NativeClient:
            def __init__(self):
                lab.log("native.init")
                self.calls = 0

            def get_value(self, service, path, *, timeout):
                self.calls += 1
                lab.log("native.get", service, path, timeout)
                lab.point("native.get")
                if lab.options.get("identity_mismatch") and self.calls == 1:
                    return "wrong identity"
                if lab.options.get("reconnect_false") and self.calls > 5:
                    return "unavailable"
                return next(
                    p["expected"]
                    for p in lab.config["identity"]
                    if p["service"] == service and p["path"] == path
                )

            def _get_bus(self):
                lab.log("native.bus")
                return "synthetic bus"

            def _mark_failure(self, bus):
                assert bus == "synthetic bus"
                lab.log("native.failure")

            def close(self):
                lab.log("native.close")
                lab.point("native.close")

        class Thread:
            def __init__(self, *, target, daemon):
                assert daemon is True
                self.target, self.joined = target, False
                self.role = "closer" if target.__name__ == "close" else "worker"
                lab.log("thread.create", self.role)
                lab.point("thread.create:" + self.role)
                lab.threads.append(self)

            def start(self):
                lab.log("thread.start", self.role)
                lab.point("thread.start:" + self.role)
                if lab.options.get("worker_deadline") and self.role == "worker":
                    return
                if lab.options.get("close_wedge") and self.role == "closer":
                    return
                try:
                    self.target()
                except BaseException as error:
                    # Real threads do not forward target exceptions to start().
                    lab.log("thread.target_error", self.role, type(error).__name__, str(error))

            def is_alive(self):
                alive = (
                    self.role == "worker"
                    and (
                        lab.options.get("worker_deadline")
                        or lab.options.get("join_wedge")
                        and self.joined
                    )
                ) or (self.role == "closer" and lab.options.get("close_wedge"))
                lab.log("thread.alive", self.role, bool(alive))
                return bool(alive)

            def join(self, *, timeout):
                lab.log("thread.join", self.role, timeout)
                lab.point("thread.join:" + self.role)
                self.joined = True

        class Broker:
            def __init__(self, version):
                assert version == 2
                lab.log("broker.init")
                lab.broker = self

            def connect(self, host, port, *, keepalive):
                assert (host, port, keepalive) == ("127.0.0.1", 1883, 30)
                lab.log("broker.connect", host, port, keepalive)
                lab.point("broker.connect")
                self.on_connect(self, None, None)

            def subscribe(self, topic, *, qos):
                assert (topic, qos) == ("inverter/state", 1)
                lab.log("broker.subscribe", topic, qos)

            def loop_start(self):
                lab.log("broker.loop_start")
                lab.point("broker.loop_start")

            def disconnect(self):
                lab.log("broker.disconnect")
                lab.point("broker.disconnect")

            def loop_stop(self):
                lab.log("broker.loop_stop")
                lab.point("broker.loop_stop")

        class Queue:
            def __init__(self, *, maxsize):
                assert maxsize == 10000
                self.items = deque()

            def put_nowait(self, item):
                lab.log("queue.put", item)
                if lab.options.get("queue_full"):
                    raise queue.Full
                self.items.append(item)

            def get(self, *, timeout):
                assert timeout == lab.config["limits"]["sample_gap_seconds"]
                lab.sample += 1
                lab.log("queue.get", lab.sample, timeout)
                lab.point("queue.get")
                assert lab.sample <= 500, "Unbounded synthetic receiver loop"
                if lab.options.get("queue_empty"):
                    raise queue.Empty
                lab.now = lab.sample * 10.0
                if lab.options.get("throttle") and lab.sample == 2:
                    lab.now = 10.5
                state = {
                    "uptime": lab.now + 100,
                    "dry_run": False,
                    "grid_control_valid": lab.now != 1810,
                    "grid_loss_zero_applied": lab.now == 1810,
                    "grid_loss_state": "zero" if lab.now == 1810 else "normal",
                    "perf": {
                        "cycle_ms": {"p95": 100, "p99": 150},
                        "setvalue_ms": {"p95": 30, "p99": 50},
                        "rss_mb": 45,
                    },
                }
                if lab.options.get("unhealthy_first"):
                    state["dry_run"] = True
                if lab.options.get("unhealthy_fault") and lab.now == 1800:
                    state["grid_control_valid"] = False
                if lab.options.get("deadline_restore"):
                    state.update(grid_control_valid=True, grid_loss_zero_applied=False)
                if lab.options.get("filtered_messages"):
                    for topic, retain in (("other", False), ("inverter/state", True)):
                        lab.broker.on_message(
                            None,
                            None,
                            SimpleNamespace(topic=topic, retain=retain, payload=b"invalid JSON"),
                        )
                payload = (
                    b"invalid JSON" if lab.options.get("bad_json") else json.dumps(state).encode()
                )
                lab.broker.on_message(
                    None,
                    None,
                    SimpleNamespace(topic="inverter/state", retain=False, payload=payload),
                )
                if not self.items:
                    raise queue.Empty
                received, data = self.items.popleft()
                if lab.options.get("queue_stale"):
                    lab.now += timeout + 1
                return received, data

        mqtt = SimpleNamespace(Client=Broker, CallbackAPIVersion=SimpleNamespace(VERSION2=2))
        paho = SimpleNamespace(mqtt=SimpleNamespace(client=mqtt))

        def import_only(name, _globals=None, _locals=None, fromlist=(), level=0):
            lab.log("import", name, list(fromlist or ()), level)
            assert level == 0
            if name == "paho.mqtt.client":
                return mqtt if fromlist else paho
            if name == "inverter_control.dbus_native":
                return SimpleNamespace(NativeDbusClient=NativeClient)
            raise AssertionError("Forbidden import: " + name)

        def set_signal(number, handler):
            lab.log("signal.install", number)
            lab.handlers[number] = handler

        safe_builtins = vars(builtins).copy()
        safe_builtins["__import__"] = import_only
        safe_builtins["print"] = lab.printed
        return {
            "__builtins__": safe_builtins,
            "__name__": "synthetic_device_runner",
            "Path": DevicePath,
            "hashlib": hashlib,
            "math": math,
            "re": re,
            "statistics": statistics,
            "json": json,
            "signal": SimpleNamespace(
                SIGTERM=signal.SIGTERM, SIGINT=signal.SIGINT, signal=set_signal
            ),
            "sys": SimpleNamespace(path=[]),
            "threading": SimpleNamespace(Lock=Lock, Event=Event, Thread=Thread),
            "queue": SimpleNamespace(Queue=Queue, Empty=queue.Empty, Full=queue.Full),
            "subprocess": SimpleNamespace(
                run=lab.command,
                SubprocessError=subprocess.SubprocessError,
                TimeoutExpired=subprocess.TimeoutExpired,
                CalledProcessError=subprocess.CalledProcessError,
            ),
            "time": SimpleNamespace(monotonic=lab.monotonic, sleep=lab.sleep),
        }

    def run(self, source=TEXT):
        global BLOCK_EXTERNAL
        # Compile every original function verbatim, without module imports/main.
        functions = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)]
        ns = self.namespace()
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), ns)
        FORBIDDEN_EVENTS.clear()
        BLOCK_EXTERNAL = True
        try:
            try:
                result = ns["run_device"](
                    self.config, preflight_only=self.options.get("preflight", False)
                )
                self.outcome = {"return": result}
            except BaseException as error:
                self.outcome = {"error": type(error).__name__, "message": str(error)}
        finally:
            BLOCK_EXTERNAL = False
        assert not FORBIDDEN_EVENTS, (self.name, "blocked external capabilities", FORBIDDEN_EVENTS)
        assert self.outcome.get("error") != "AssertionError", (
            self.name,
            "fake contract",
            self.outcome,
        )
        assert not any(event.get("error") == "AssertionError" for event in self.events), (
            self.name,
            "masked fake contract",
        )
        assert not any(
            row[0] == "thread.target_error" and row[2] == "AssertionError" for row in self.trace
        ), (self.name, "thread fake contract")
        return self

    def assert_safety(self):
        commands = [x[1] for x in self.trace if x[0] == "command"]
        down = [
            i
            for i, x in enumerate(self.trace)
            if x[:2] == ["command", ["svc", "-d", self.config["meter_service"]]]
        ]
        journal = [
            i for i, x in enumerate(self.trace) if x[0] == "print" and x[1]["kind"] == "meter_down"
        ]
        restore = [
            i
            for i, x in enumerate(self.trace)
            if x[:2] == ["command", ["svc", "-u", self.config["meter_service"]]]
        ]
        assert all(journal and journal[0] < i for i in down), (self.name, "stop before journal")
        assert not restore or journal, (self.name, "restoration without prior attempted journal")
        if self.options.get("must_restore"):
            assert restore and restore[0] > journal[0], (
                self.name,
                "missing restoration after attempted fault",
            )
        if "restore_count" in self.options:
            assert len(restore) == self.options["restore_count"], (
                self.name,
                "restore count",
                len(restore),
            )
        if self.options.get("no_fault"):
            assert not down and not restore, (self.name, commands)
        if self.options.get("return_code") is not None:
            assert self.outcome == {"return": self.options["return_code"]}, (
                self.name,
                self.outcome,
            )
        if self.options.get("cleanup_complete"):
            kinds = [x[0] for x in self.trace]
            assert (
                kinds.index("broker.disconnect")
                < kinds.index("broker.loop_stop")
                < kinds.index("native.close")
            )
        if self.options.get("error_kind"):
            assert any(
                e["kind"] == "error" and e.get("error") == self.options["error_kind"]
                for e in self.events
            ), (self.name, self.events[-5:])
        if "raised" in self.options:
            assert self.outcome.get("error") == self.options["raised"], (self.name, self.outcome)
        if self.options.get("cleanup_error"):
            assert any(e["kind"] == "cleanup_error" for e in self.events)
        if self.options.get("cleanup_stops_at"):
            kinds = [x[0] for x in self.trace]
            if self.options["cleanup_stops_at"] == "disconnect":
                assert "broker.loop_stop" not in kinds and "native.close" not in kinds
            if self.options["cleanup_stops_at"] == "loop_stop":
                assert "native.close" not in kinds
        return self


CASES = [
    ("healthy", dict(return_code=0, must_restore=True, restore_count=1, cleanup_complete=True)),
    ("preflight", dict(preflight=True, return_code=0, no_fault=True, cleanup_complete=True)),
    ("identity_file", dict(identity_file=True, no_fault=True)),
    ("identity_probe", dict(identity_mismatch=True, no_fault=True, cleanup_complete=True)),
    ("queue_empty", dict(queue_empty=True, no_fault=True, error_kind="TimeoutError")),
    ("queue_stale", dict(queue_stale=True, no_fault=True, error_kind="TimeoutError")),
    ("unhealthy_first", dict(unhealthy_first=True, no_fault=True, error_kind="ValueError")),
    ("unhealthy_before_fault", dict(unhealthy_fault=True, no_fault=True, error_kind="ValueError")),
    ("throttled_sample", dict(throttle=True, must_restore=True)),
    ("filtered_messages", dict(filtered_messages=True, return_code=0, must_restore=True)),
    ("invalid_json", dict(bad_json=True, no_fault=True, error_kind="TimeoutError")),
    ("full_queue", dict(queue_full=True, no_fault=True, error_kind="TimeoutError")),
    ("journal_failure", dict(fault=("print:meter_down", 1, "value"), must_restore=True)),
    ("journal_interrupt", dict(fault=("print:meter_down", 1, "signal"), must_restore=True)),
    ("stop_command_failure", dict(fault=("command:svc -d", 1, "runtime"), must_restore=True)),
    ("stop_command_interrupt", dict(fault=("command:svc -d", 1, "interrupt"), must_restore=True)),
    ("restore_false", dict(restore_false=True, must_restore=True, restore_count=2, return_code=1)),
    (
        "restore_raises",
        dict(fault=("command:svc -u", 1, "runtime"), must_restore=True, restore_count=2),
    ),
    (
        "restore_emit_failure",
        dict(fault=("print:meter_restored", 1, "value"), must_restore=True, restore_count=2),
    ),
    (
        "deadline_restore",
        dict(deadline_restore=True, must_restore=True, restore_count=1, return_code=1),
    ),
    ("worker_deadline", dict(worker_deadline=True, no_fault=True, error_kind="TimeoutError")),
    ("join_wedge", dict(join_wedge=True, must_restore=True, error_kind="TimeoutError")),
    ("close_wedge", dict(close_wedge=True, must_restore=True, error_kind="TimeoutError")),
    ("reconnect_failed", dict(reconnect_false=True, no_fault=True, error_kind="RuntimeError")),
    (
        "receive_failure_after_fault",
        dict(fault=("queue.get", 181, "value"), must_restore=True, restore_count=1),
    ),
    (
        "receive_signal_before_fault",
        dict(fault=("queue.get", 100, "signal"), no_fault=True, error_kind="InterruptedError"),
    ),
    (
        "journal_base_exception",
        dict(
            fault=("print:meter_down", 1, "base"),
            must_restore=True,
            restore_count=1,
            raised="KeyboardInterrupt",
        ),
    ),
    (
        "restore_signal",
        dict(
            fault=("command:svc -u", 1, "signal"),
            must_restore=True,
            restore_count=2,
            error_kind="InterruptedError",
        ),
    ),
    (
        "cleanup_restore_raises",
        dict(
            faults=[("command:svc -d", 1, "value"), ("command:svc -u", 1, "runtime")],
            must_restore=True,
            restore_count=1,
            cleanup_error=True,
            cleanup_complete=True,
        ),
    ),
    (
        "error_emit_raises",
        dict(
            faults=[("command:svc -d", 1, "value"), ("print:error", 1, "runtime")],
            must_restore=True,
            restore_count=1,
            cleanup_complete=True,
            raised="RuntimeError",
        ),
    ),
    (
        "cleanup_error_emit_raises",
        dict(
            faults=[
                ("command:svc -d", 1, "value"),
                ("command:svc -u", 1, "runtime"),
                ("print:cleanup_error", 1, "interrupt"),
            ],
            must_restore=True,
            restore_count=1,
            raised="InterruptedError",
        ),
    ),
    (
        "stop_command_timeout",
        dict(
            fault=("command:svc -d", 1, "timeout"),
            must_restore=True,
            restore_count=1,
            error_kind="TimeoutExpired",
        ),
    ),
    (
        "stop_command_exit",
        dict(
            fault=("command:svc -d", 1, "process"),
            must_restore=True,
            restore_count=1,
            error_kind="CalledProcessError",
        ),
    ),
    (
        "stop_command_os_error",
        dict(
            fault=("command:svc -d", 1, "os"),
            must_restore=True,
            restore_count=1,
            error_kind="OSError",
        ),
    ),
    (
        "initial_status_timeout",
        dict(
            fault=("command:svstat /service/lab-meter", 1, "timeout"),
            no_fault=True,
            error_kind="TimeoutExpired",
        ),
    ),
    (
        "restore_command_timeout",
        dict(
            fault=("command:svc -u", 1, "timeout"),
            must_restore=True,
            restore_count=2,
            error_kind="TimeoutExpired",
        ),
    ),
    (
        "restore_command_exit",
        dict(
            fault=("command:svc -u", 1, "process"),
            must_restore=True,
            restore_count=2,
            error_kind="CalledProcessError",
        ),
    ),
    (
        "restore_status_timeout",
        dict(
            fault=("command:svstat /service/lab-meter", 2, "timeout"),
            must_restore=True,
            restore_count=2,
            error_kind="TimeoutExpired",
        ),
    ),
    (
        "restore_status_os_error",
        dict(
            fault=("command:svstat /service/lab-meter", 2, "os"),
            must_restore=True,
            restore_count=2,
            error_kind="OSError",
        ),
    ),
]
for point in ("thread.create:worker", "thread.start:worker", "broker.connect", "broker.loop_start"):
    CASES.append((point, dict(fault=(point, 1, "runtime"), no_fault=True, cleanup_complete=True)))
for point in ("broker.disconnect", "broker.loop_stop", "thread.start:closer", "thread.join:closer"):
    CASES.append((point, dict(fault=(point, 1, "runtime"), must_restore=True)))
for name, options in CASES:
    if name == "broker.disconnect":
        options.update(raised="RuntimeError", cleanup_stops_at="disconnect")
    if name == "broker.loop_stop":
        options.update(raised="RuntimeError", cleanup_stops_at="loop_stop")
