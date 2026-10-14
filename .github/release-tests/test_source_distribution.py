"""Verify the real distribution inventory, isolated installation and receipts."""

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import package_source
import stage_release_assets
import version_plan
import version_receipt


class SourceDistributionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="integration-tests-package-contract-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in package_source.inventory(ROOT) + [".release-policy.json"]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        shutil.copytree(ROOT / "scripts", self.root / "scripts", dirs_exist_ok=True)
        self.command("git", "init", "-q")
        self.command("git", "add", ".")
        self.command(
            "git",
            "-c",
            "user.name=Source fixture",
            "-c",
            "user.email=source@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "Synthetic source snapshot",
        )
        self.policy = json.loads((self.root / ".release-policy.json").read_text())

    def command(self, *args):
        return subprocess.check_output(
            args, cwd=self.root, text=True, stderr=subprocess.STDOUT
        )

    def freeze(self, channel):
        plan = version_plan.create_plan(
            "0.1.1",
            channel,
            7,
            self.command("git", "rev-parse", "HEAD").strip(),
            self.policy,
            build_number=7,
        )
        (self.root / ".release-plan.json").write_text(json.dumps(plan))
        self.command(
            sys.executable,
            "scripts/version_plan.py",
            "sync",
            "--plan",
            ".release-plan.json",
        )
        return plan

    def test_beta_and_rc_archive_versions_receipts_and_component_independence(self):
        independent = ['hardware/release_artifact.py', 'requirements-test-runner.txt']
        before = {name: (self.root / name).read_bytes() for name in independent}
        metadata = {item["path"]: (self.root / item["path"]).read_bytes()
                    for item in self.policy["versioning"]["files"]}
        for channel, expected in (("beta", "0.1.1-beta.7"), ("rc", "0.1.1")):
            with self.subTest(channel=channel):
                for name, content in metadata.items():
                    (self.root / name).write_bytes(content)
                plan = self.freeze(channel)
                output = self.root / channel
                archive = package_source.build(self.root, "0.1.1", channel, output)
                with tarfile.open(archive) as package:
                    self.assertEqual(
                        package.extractfile("integration-tests/SOURCE_VERSION")
                        .read()
                        .decode()
                        .strip(),
                        expected,
                    )
                staged = stage_release_assets.stage(
                    self.root, channel, [channel + "/*"]
                )
                inventory = [
                    {
                        "name": p.name,
                        "size": p.stat().st_size,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    }
                    for p in sorted(staged.iterdir())
                ]
                version_receipt.verify_receipts(staged, plan, inventory, self.policy)
                version_receipt.verify_declared_artifacts(staged, self.policy, plan)
                self.assertEqual(
                    before,
                    {name: (self.root / name).read_bytes() for name in independent},
                )

    def test_actual_extracted_offline_recovery_guards_pass(self):
        self.freeze("rc")
        archive = package_source.build(self.root, "0.1.1", "rc", self.root / "output")
        package_source.verify(archive, self.root)

    def test_shared_local_package_command_uses_source_adapter(self):
        self.freeze("rc")
        self.command(
            sys.executable, "scripts/release.py", "package",
            "--version", "0.1.1", "--channel", "rc",
        )
        archives = list((self.root / "release-dist").glob("*.tar.gz"))
        self.assertEqual(len(archives), 1)
        package_source.verify(archives[0], self.root)

    def test_archive_is_reproducible_and_excludes_local_state(self):
        self.freeze("beta")
        (self.root / "private").mkdir()
        (self.root / "private/example.local.json").write_text(
            '{"synthetic":"do not package"}'
        )
        first = package_source.build(self.root, "0.1.1", "beta", self.root / "first")
        second = package_source.build(self.root, "0.1.1", "beta", self.root / "second")
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with tarfile.open(first) as package:
            self.assertFalse(any("/private/" in name for name in package.getnames()))
            self.assertTrue(
                all(
                    item.mtime == 0 and item.uid == 0 and item.gid == 0
                    for item in package
                )
            )

    def test_missing_and_linked_required_inputs_fail(self):
        path = self.root / "SOURCE_VERSION"
        path.unlink()
        with self.assertRaisesRegex(ValueError, "Missing, untracked or linked"):
            package_source.sources(self.root)
        path.symlink_to(self.root / "README.md")
        with self.assertRaisesRegex(ValueError, "Missing, untracked or linked"):
            package_source.sources(self.root)

    def test_inventory_rejects_traversal_and_duplicates(self):
        for names in (
            ["../outside", "SOURCE_VERSION", "release-files.json"],
            ["SOURCE_VERSION", "SOURCE_VERSION", "release-files.json"],
        ):
            with self.subTest(names=names):
                (self.root / "release-files.json").write_text(
                    json.dumps({"files": names})
                )
                with self.assertRaises(ValueError):
                    package_source.inventory(self.root)

    def test_changed_archive_fails_before_extraction(self):
        self.freeze("rc")
        archive = package_source.build(self.root, "0.1.1", "rc", self.root / "output")
        with tarfile.open(archive, "w:gz") as package:
            entry = tarfile.TarInfo("integration-tests/SOURCE_VERSION")
            entry.size = 6
            package.addfile(entry, io.BytesIO(b"9.9.9\n"))
        destination = self.root / "unpacked"
        with self.assertRaisesRegex(ValueError, "membership differs"):
            package_source.unpack(archive, self.root, destination)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
