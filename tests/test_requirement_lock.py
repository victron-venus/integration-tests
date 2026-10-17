"""Regression coverage for dependency updates that leave the runner lock stale."""

import unittest

from scripts.validate_requirement_lock import validate_lock, validate_uv_lock

HASH = "--hash=sha256:" + "a" * 64


class RequirementLockTests(unittest.TestCase):
    def test_matching_hashed_pin_and_platform_transitive_dependency(self):
        validate_lock(
            "websockets==17.2\n",
            f"websockets==17.2 \\\n    {HASH}\ncolorama==0.4.6 ; sys_platform == 'win32' {HASH}\n",
        )

    def test_update_without_regenerated_lock_fails(self):
        with self.assertRaisesRegex(ValueError, "stale or missing"):
            validate_lock("websockets==17.2\n", f"websockets==17.1 {HASH}\n")

    def test_missing_conditional_unhashed_or_duplicate_direct_pin_fails(self):
        for lock in (
            f"pytest==9.1.1 {HASH}",
            f"websockets==17.2 ; sys_platform == 'win32' {HASH}",
            "websockets==17.2",
            f"websockets==17.2 {HASH}\nwebsockets==17.2 {HASH}",
        ):
            with self.subTest(lock=lock), self.assertRaises(ValueError):
                validate_lock("websockets==17.2", lock)

    def test_unsupported_or_empty_input_fails(self):
        for inputs in ("", "websockets>=17.2", "-r other.in", "websockets==17.2\nwebsockets==17.2"):
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                validate_lock(inputs, f"websockets==17.2 {HASH}")


class UvLockTests(unittest.TestCase):
    project = '[project]\nname = "suite"\ndependencies = ["websockets>=17.2"]\n'

    @staticmethod
    def entry(version, marker=""):
        return (
            '[[package]]\nname = "websockets"\n'
            f'version = "{version}"\n'
            'source = { registry = "https://pypi.org/simple" }\n'
            + (f'resolution-markers = ["{marker}"]\n' if marker else "")
        )

    def test_matching_registry_version_and_runner_only_tool(self):
        validate_uv_lock(
            "websockets==17.2\npytest-html==4.2.0", self.project, self.entry("17.2")
        )

    def test_stale_missing_or_non_registry_dependency_fails(self):
        for lock in (
            self.entry("17.1"),
            'package = []',
            self.entry("17.2").replace('registry = "https://pypi.org/simple"', 'editable = "."'),
        ):
            with self.subTest(lock=lock), self.assertRaisesRegex(ValueError, "uv lock"):
                validate_uv_lock("websockets==17.2", self.project, lock)

    def test_matching_platform_variants_are_allowed(self):
        lock = self.entry("17.2", "sys_platform == 'win32'") + self.entry(
            "17.2", "sys_platform != 'win32'"
        )
        validate_uv_lock("websockets==17.2", self.project, lock)

    def test_conflicting_platform_variant_cannot_match_unconditional_pin(self):
        lock = self.entry("17.2", "sys_platform == 'win32'") + self.entry(
            "17.1", "sys_platform != 'win32'"
        )
        with self.assertRaisesRegex(ValueError, "conflicting"):
            validate_uv_lock("websockets==17.2", self.project, lock)

    def test_project_dependency_must_have_a_runner_pin(self):
        with self.assertRaisesRegex(ValueError, "lacks.*runner pin"):
            validate_uv_lock("pytest==9.1.1", self.project, self.entry("17.2"))


if __name__ == "__main__":
    unittest.main()
