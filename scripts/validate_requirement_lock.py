#!/usr/bin/env python3
"""Check the runner's exact input pins against its generated hashed lock."""

import re
from pathlib import Path

PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)")


def direct_pins(text):
    """Accept only the unconditional exact pins supported by this runner."""
    pins = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN.fullmatch(line)
        if match is None:
            raise ValueError(f"Runner input requires an unconditional exact pin: {line}")
        name, version = match.groups()
        name = re.sub(r"[-_.]+", "-", name).lower()
        if name in pins:
            raise ValueError(f"Duplicate runner input: {name}")
        pins[name] = version
    if not pins:
        raise ValueError("Runner input is empty")
    return pins


def validate_lock(inputs, lock):
    """Reject stale, missing, conditional or unhashed direct dependencies."""
    records = {}
    for logical in lock.replace("\\\n", " ").splitlines():
        line = logical.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN.match(line)
        if match is None:
            raise ValueError("Unsupported runner lock record")
        name, version = match.groups()
        name = re.sub(r"[-_.]+", "-", name).lower()
        tail = line[match.end():].strip()
        records.setdefault(name, []).append((version, tail))
    for name, version in direct_pins(inputs).items():
        entries = records.get(name, [])
        if len(entries) != 1 or entries[0][0] != version:
            raise ValueError(f"Runner lock is stale or missing: {name}=={version}; regenerate it")
        hashes = entries[0][1].split()
        if not hashes or not all(re.fullmatch(r"--hash=sha256:[0-9a-f]{64}", h) for h in hashes):
            raise ValueError(f"Runner lock must unconditionally hash {name}")


def main():
    root = Path(__file__).resolve().parents[1]
    validate_lock(
        (root / "requirements-test-runner.in").read_text(),
        (root / "requirements-test-runner.txt").read_text(),
    )
    print("Runner input pins match the hashed lock")


if __name__ == "__main__":
    main()
