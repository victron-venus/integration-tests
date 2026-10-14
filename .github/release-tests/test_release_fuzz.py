"""Offline regression tests for bounded Go diagnostic retention."""

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

    def test_each_regression_tree_has_file_limit_and_target_report_records_truncation(self):
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
        self.assertEqual(len(report["go_regressions"]), 2)
        for retained in report["go_regressions"]:
            self.assertEqual({key: retained[key] for key in ("files", "bytes", "truncated")},
                             {"files": 2, "bytes": 8, "truncated": True})
            copied = self.output / target["name"] / retained["directory"] / "FuzzInput"
            self.assertEqual(sorted(path.name for path in copied.iterdir()), ["a", "b"])
            self.assertEqual((copied / "a").read_bytes(), b"seed")
        self.assertEqual(report["generated_corpus"], {"files": 1, "bytes": 5, "truncated": False})
        self.assertEqual((self.output / target["name"] / "go-generated-corpus/generated").read_bytes(), b"cache")

    def test_regression_byte_limit_including_oversized_first_file(self):
        self.seed("testdata/fuzz/FuzzInput/a", b"1234")
        self.seed("testdata/fuzz/FuzzInput/b", b"56")
        for budget, count, size in ((5, 1, 4), (3, 0, 0)):
            with self.subTest(budget=budget), patch.object(fuzz, "CORPUS_BYTES", budget):
                output = self.output / str(budget)
                report = fuzz.retain_go_diagnostics(self.root, self.cwd, output, None)
                retained = report["go_regressions"][0]
                self.assertEqual(retained, {"directory": "go-regressions-0", "files": count,
                                            "bytes": size, "truncated": True})
                copied = list((output / retained["directory"]).rglob("*"))
                self.assertEqual(sum(path.is_file() for path in copied), count)
                self.assertEqual(sum(path.stat().st_size for path in copied if path.is_file()), size)

    def test_exact_limits_preserve_nested_files_and_skip_symlinks(self):
        seed = self.seed("testdata/fuzz/FuzzInput/seed")
        (seed.parent / "link").symlink_to(seed)
        (seed.parent / "directory-link").symlink_to(self.root, target_is_directory=True)
        with patch.object(fuzz, "CORPUS_FILES", 1), patch.object(fuzz, "CORPUS_BYTES", 4):
            report = fuzz.retain_go_diagnostics(self.root, self.cwd, self.output, None)
        self.assertEqual(report["go_regressions"], [{"directory": "go-regressions-0",
                                                    "files": 1, "bytes": 4, "truncated": False}])
        copied = self.output / "go-regressions-0" / "FuzzInput"
        self.assertEqual([path.name for path in copied.iterdir()], ["seed"])
        self.assertEqual((copied / "seed").read_bytes(), b"seed")
