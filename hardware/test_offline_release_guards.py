"""Dependency-free release parser checks; no runner execution or device access."""
import hashlib
import io
import tarfile
import unittest

from hardware.device_runner import validate_release_artifact
from hardware.release_artifact import _archive_payload


def binding():
    return {
        "repository": "victron-venus/inverter-control",
        "release_tag": "v1.0.0-rc.1", "build_tag": "v1.0.0-rc.1",
        "source_sha": "a" * 40, "manifest_sha256": "b" * 64,
        "asset_name": "synthetic.tar.gz", "asset_sha256": "c" * 64,
        "files": {name: "d" * 64 for name in ("version", "main.py", "setup")},
    }


class OfflineReleaseGuards(unittest.TestCase):
    def test_repository_must_be_a_string(self):
        for value in ({}, [], None, 42, True):
            candidate = binding()
            candidate["repository"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_release_artifact(candidate)

    def test_valid_binding_keeps_exact_identity(self):
        candidate = binding()
        self.assertIs(validate_release_artifact(candidate), candidate)

    def test_archive_hashes_payload_and_rejects_escaping_names(self):
        for name in ("inverter-control/version", "inverter-control/../escape"):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode="w:gz") as archive:
                info = tarfile.TarInfo(name)
                info.size = 3
                archive.addfile(info, io.BytesIO(b"1.0"))
            if ".." in name:
                with self.assertRaises(ValueError):
                    _archive_payload(stream.getvalue(), "inverter-control")
            else:
                self.assertEqual(_archive_payload(stream.getvalue(), "inverter-control"),
                                 {"version": hashlib.sha256(b"1.0").hexdigest()})
