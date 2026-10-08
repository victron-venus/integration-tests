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
