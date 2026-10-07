"""Regression coverage for dependency updates that leave the runner lock stale."""

import unittest

from scripts.validate_requirement_lock import validate_lock

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


if __name__ == "__main__":
    unittest.main()
