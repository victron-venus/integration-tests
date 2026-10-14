"""Offline regression tests for bounded Go diagnostic retention."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import release_fuzz as fuzz


class GoDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cwd = self.root / "source"
        self.cwd.mkdir()
        self.output = self.root / "output"
        self.output.mkdir()
        self.cache = self.root / "cache"
        self.enterContext(patch.object(fuzz.subprocess, "check_output", return_value=str(self.cache)))

    def seed(self, relative, data=b"seed"):
        path = self.cwd / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_regression_trees_share_one_file_limit_and_report_truncation(self):
        for package in ("one", "two"):
            for name in ("a", "b", "c"):
                self.seed(f"{package}/testdata/fuzz/FuzzInput/{name}")
        generated = self.cache / "fuzz" / "generated"
        generated.parent.mkdir(parents=True)
        generated.write_bytes(b"cache")

        def execute(command, cwd, log, timeout, isolated):
            log.write_text("fuzz: elapsed: 1s, execs: 10\n")
            return 0, 1.0

        target = {"name": "go-input", "engine": "go", "seconds": 1,
                  "command": ["go", "test", "-fuzz=FuzzInput"], "cwd": "source"}
        with patch.object(fuzz, "CORPUS_FILES", 2), patch.object(fuzz, "execute", side_effect=execute):
            report = fuzz.run_target(self.root, self.output, target)
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["go_regressions"], {"files": 2, "bytes": 8, "truncated": True})
        retained = self.output / target["name"] / "go-regressions"
        copied = retained / "one/testdata/fuzz/FuzzInput"
        self.assertEqual(sorted(path.name for path in copied.iterdir()), ["a", "b"])
        self.assertEqual((copied / "a").read_bytes(), b"seed")
        self.assertFalse((retained / "two").exists())
        metadata = self.output / target["name"] / "go-regressions.json"
        self.assertEqual(json.loads(metadata.read_text()), report["go_regressions"])
        self.assertEqual(report["generated_corpus"], {"files": 1, "bytes": 5, "truncated": False})
        self.assertEqual((self.output / target["name"] / "go-generated-corpus/generated").read_bytes(), b"cache")

    def test_regression_byte_limit_including_oversized_first_file(self):
        self.seed("testdata/fuzz/FuzzInput/a", b"1234")
        self.seed("testdata/fuzz/FuzzInput/b", b"56")
        for budget, count, size in ((5, 1, 4), (3, 0, 0)):
            with self.subTest(budget=budget), patch.object(fuzz, "CORPUS_BYTES", budget):
                output = self.output / str(budget)
                output.mkdir()
                report = fuzz.retain_go_diagnostics(self.root, self.cwd, output, None)
                retained = report["go_regressions"]
                self.assertEqual(retained, {"files": count,
                                            "bytes": size, "truncated": True})
                copied = list((output / "go-regressions").rglob("*"))
                self.assertEqual(sum(path.is_file() for path in copied), count)
                self.assertEqual(sum(path.stat().st_size for path in copied if path.is_file()), size)

    def test_exact_limits_preserve_nested_files_and_skip_symlinks(self):
        seed = self.seed("testdata/fuzz/FuzzInput/seed")
        (seed.parent / "link").symlink_to(seed)
        (seed.parent / "directory-link").symlink_to(self.root, target_is_directory=True)
        with patch.object(fuzz, "CORPUS_FILES", 1), patch.object(fuzz, "CORPUS_BYTES", 4):
            report = fuzz.retain_go_diagnostics(self.root, self.cwd, self.output, None)
        self.assertEqual(report["go_regressions"], {"files": 1, "bytes": 4, "truncated": False})
        copied = self.output / "go-regressions" / "testdata/fuzz/FuzzInput"
        self.assertEqual([path.name for path in copied.iterdir()], ["seed"])
        self.assertEqual((copied / "seed").read_bytes(), b"seed")
