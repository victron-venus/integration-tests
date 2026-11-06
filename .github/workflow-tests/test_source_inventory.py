"""Keep required source-distribution files present even on documentation PRs."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SourceInventoryTests(unittest.TestCase):
    def test_release_inventory_contains_tracked_regular_sources(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from package_source import sources

            # This existing validator only reads the inventory, Git index and files.
            # It does not build, install, allocate release versions or contact devices.
            self.assertTrue(sources(ROOT))
        finally:
            sys.path.pop(0)
