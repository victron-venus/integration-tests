#!/usr/bin/env python3
"""Run the existing pinned dashboard integration suite in isolated containers."""

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
variants = {
    "python": ("victron-venus/inverter-dashboard", "ccde631cade6d381b87614cb21c464c7ad024cd4"),
    "go": ("victron-venus/inverter-dashboard-go", "e79fd89fe63683bb1aedb55b047ba96802771adf"),
}
selected = sys.argv[1:] or list(variants)
if any(name not in variants for name in selected):
    raise SystemExit("Choose python or go")
subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL)
for name in selected:
    with tempfile.TemporaryDirectory(prefix=f"integration-{name}-") as temporary:
        stage = Path(temporary)
        for item in root.iterdir():
            if (
                item.name in {".git", ".venv", "sources", "reports", "__pycache__"}
                or item.is_symlink()
            ):
                continue
            if item.is_dir():
                shutil.copytree(item, stage / item.name)
            else:
                shutil.copyfile(item, stage / item.name)
        source = stage / "sources" / "dashboard"
        source.mkdir(parents=True)
        repository, revision = variants[name]
        subprocess.run(["git", "init", "--quiet", str(source)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "fetch",
                "--depth=1",
                f"https://github.com/{repository}.git",
                revision,
            ],
            check=True,
        )
        subprocess.run(["git", "-C", str(source), "checkout", "--detach", "FETCH_HEAD"], check=True)
        project = f"release-ci-{name}-{os.getpid()}"
        image = f"{project}:test"
        dockerfile = (
            stage / "dashboard-python.test.dockerfile"
            if name == "python"
            else source / "Dockerfile"
        )
        subprocess.run(
            ["docker", "build", "--file", str(dockerfile), "--tag", image, str(source)], check=True
        )
        compose_path = stage / "docker-compose.yml"
        compose = yaml.safe_load(compose_path.read_text())
        for service in compose["services"].values():
            # No shared container names or host ports: tests communicate inside
            # their own Compose network and cannot replace local services.
            service.pop("container_name", None)
            service.pop("ports", None)
        compose_path.write_text(yaml.safe_dump(compose))
        override_path = stage / "docker-compose.ci.yml"
        override = yaml.safe_load(override_path.read_text())
        override["services"]["dashboard"]["image"] = image
        override_path.write_text(yaml.safe_dump(override))
        reports = stage / "reports"
        reports.mkdir(exist_ok=True)
        reports.chmod(0o777)
        command = [
            "docker",
            "compose",
            "--project-name",
            project,
            "-f",
            str(compose_path),
            "-f",
            str(override_path),
        ]
        result = 1
        try:
            subprocess.run(
                [
                    *command,
                    "up",
                    "-d",
                    "--build",
                    "mqtt-broker",
                    "mock-dbus",
                    "mock-battery",
                    "mock-pv",
                    "dashboard",
                ],
                check=True,
                cwd=stage,
            )
            subprocess.run([*command, "build", "test-runner"], check=True, cwd=stage)
            subprocess.run(
                [*command, "run", "--rm", "test-runner", "python", "tests/wait_ready.py"],
                check=True,
                cwd=stage,
            )
            result = subprocess.run(
                [
                    *command,
                    "run",
                    "--rm",
                    "test-runner",
                    "python",
                    "-m",
                    "pytest",
                    "tests/integration/",
                    "-v",
                    "--tb=short",
                    "--html=/reports/report.html",
                    "--self-contained-html",
                    "--junitxml=/reports/junit.xml",
                ],
                cwd=stage,
            ).returncode
        finally:
            logs = subprocess.run(
                [*command, "logs", "--no-color"], cwd=stage, capture_output=True
            ).stdout
            (reports / "containers.log").write_bytes(logs)
            destination = (
                root
                / "reports"
                / f"{name}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
            )
            shutil.copytree(reports, destination)
            subprocess.run([*command, "down", "--volumes"], cwd=stage, check=True)
        if result:
            raise SystemExit(result)
print("Pinned dashboard integration suites passed; physical hardware is outside this suite.")
