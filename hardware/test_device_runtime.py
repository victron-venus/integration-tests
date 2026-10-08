"""Offline execution/failure coverage; no physical device or network is used."""

import pytest

from hardware._device_runtime import CASES, TEXT, Lab

EXPECTED_OUTCOMES = {
    "healthy": {"return": 0},
    "preflight": {"return": 0},
    "identity_file": {"error": "ValueError", "message": "Controller version mismatch"},
    "identity_probe": {"return": 1},
    "queue_empty": {"return": 1},
    "queue_stale": {"return": 1},
    "unhealthy_first": {"return": 1},
    "unhealthy_before_fault": {"return": 1},
    "throttled_sample": {"return": 1},
    "filtered_messages": {"return": 0},
    "invalid_json": {"return": 1},
    "full_queue": {"return": 1},
    "journal_failure": {"return": 1},
    "journal_interrupt": {"return": 1},
    "stop_command_failure": {"return": 1},
    "stop_command_interrupt": {"return": 1},
    "restore_false": {"return": 1},
    "restore_raises": {"return": 1},
    "restore_emit_failure": {"return": 1},
    "deadline_restore": {"return": 1},
    "worker_deadline": {"return": 1},
    "join_wedge": {"return": 1},
    "close_wedge": {"return": 1},
    "reconnect_failed": {"return": 1},
    "receive_failure_after_fault": {"return": 1},
    "receive_signal_before_fault": {"return": 1},
    "journal_base_exception": {"error": "KeyboardInterrupt", "message": "print:meter_down"},
    "restore_signal": {"return": 1},
    "cleanup_restore_raises": {"return": 1},
    "error_emit_raises": {"error": "RuntimeError", "message": "print:error"},
    "cleanup_error_emit_raises": {"error": "InterruptedError", "message": "print:cleanup_error"},
    "stop_command_timeout": {"return": 1},
    "stop_command_exit": {"return": 1},
    "stop_command_os_error": {"return": 1},
    "initial_status_timeout": {"return": 1},
    "restore_command_timeout": {"return": 1},
    "restore_command_exit": {"return": 1},
    "restore_status_timeout": {"return": 1},
    "restore_status_os_error": {"return": 1},
    "thread.create:worker": {"return": 1},
    "thread.start:worker": {"return": 1},
    "broker.connect": {"return": 1},
    "broker.loop_start": {"return": 1},
    "broker.disconnect": {"error": "RuntimeError", "message": "broker.disconnect"},
    "broker.loop_stop": {"error": "RuntimeError", "message": "broker.loop_stop"},
    "thread.start:closer": {"error": "RuntimeError", "message": "thread.start:closer"},
    "thread.join:closer": {"error": "RuntimeError", "message": "thread.join:closer"},
}


@pytest.mark.parametrize("name,options", CASES, ids=[case[0] for case in CASES])
def test_offline_device_lifecycle(name, options):
    lab = Lab(name, **options).run().assert_safety()
    assert lab.outcome == EXPECTED_OUTCOMES[name]


def test_journal_failure_requires_prior_fault_ownership():
    original = (
        "                attempted = True\n"
        '                fault_time = emit("meter_down", service=config["meter_service"])["t"]'
    )
    reordered = (
        '                fault_time = emit("meter_down", service=config["meter_service"])["t"]\n'
        "                attempted = True"
    )
    assert TEXT.count(original) == 1
    unsafe = TEXT.replace(original, reordered)
    lab = Lab("journal_after_mutant", fault=("print:meter_down", 1, "value"), must_restore=True)
    lab.run(unsafe)
    with pytest.raises(AssertionError, match="missing restoration"):
        lab.assert_safety()


def test_caught_external_io_still_fails_the_offline_guard():
    original = "    try:\n        observed = []"
    external = '    try:\n        open("/never-access-this-synthetic-path")\n        observed = []'
    assert TEXT.count(original) == 1
    unsafe = TEXT.replace(original, external)
    lab = Lab("blocked_external_io")
    with pytest.raises(AssertionError, match="blocked external capabilities"):
        lab.run(unsafe)


@pytest.mark.parametrize(
    "faults,expected",
    [
        (
            [("broker.disconnect", 1, "runtime"), ("broker.loop_stop", 1, "os")],
            [("OSError", "broker.loop_stop"), ("RuntimeError", "broker.disconnect")],
        ),
        (
            [("broker.disconnect", 1, "runtime"), ("thread.start:closer", 1, "os")],
            [("OSError", "thread.start:closer"), ("RuntimeError", "broker.disconnect")],
        ),
        (
            [
                ("command:svc -d", 1, "value"),
                ("command:svc -u", 1, "runtime"),
                ("print:cleanup_error", 1, "interrupt"),
                ("broker.disconnect", 1, "value"),
                ("broker.loop_stop", 1, "os"),
            ],
            [
                ("OSError", "broker.loop_stop"),
                ("ValueError", "broker.disconnect"),
                ("InterruptedError", "print:cleanup_error"),
                ("RuntimeError", "command:svc -u"),
            ],
        ),
    ],
)
def test_cleanup_attempts_later_resources_and_retains_exception_context(faults, expected):
    lab = Lab("multiple_cleanup_failures", faults=faults, must_restore=True).run().assert_safety()
    kinds = [row[0] for row in lab.trace]
    assert kinds.index("broker.disconnect") < kinds.index("broker.loop_stop")
    assert kinds.index("broker.loop_stop") < kinds.index(
        "thread.create", kinds.index("broker.loop_stop")
    )
    chain = []
    error = lab.exception
    while error is not None:
        chain.append((type(error).__name__, str(error)))
        error = error.__context__
    assert chain == expected


def test_interrupted_restoration_still_closes_resources():
    lab = (
        Lab(
            "restoration_base_exception",
            faults=[("command:svc -d", 1, "value"), ("command:svc -u", 1, "base")],
            must_restore=True,
            restore_count=1,
            cleanup_complete=True,
            raised="KeyboardInterrupt",
        )
        .run()
        .assert_safety()
    )
    assert str(lab.exception) == "command:svc -u"


def test_existing_failure_propagates_after_successful_cleanup():
    lab = (
        Lab(
            "report_failure_preserved",
            faults=[("command:svc -d", 1, "value"), ("print:error", 1, "runtime")],
            must_restore=True,
            cleanup_complete=True,
        )
        .run()
        .assert_safety()
    )
    assert (type(lab.exception).__name__, str(lab.exception)) == ("RuntimeError", "print:error")
    assert (type(lab.exception.__context__).__name__, str(lab.exception.__context__)) == (
        "ValueError",
        "command:svc -d",
    )


def test_restore_before_its_journal_fails_even_without_required_restore():
    original = (
        '                fault_time = emit("meter_down", service=config["meter_service"])["t"]'
    )
    assert TEXT.count(original) == 1
    unsafe = TEXT.replace(original, "                restore_meter(config, attempted)\n" + original)
    lab = Lab("restore_before_journal")
    lab.run(unsafe)
    with pytest.raises(AssertionError, match="restoration without prior attempted journal"):
        lab.assert_safety()
