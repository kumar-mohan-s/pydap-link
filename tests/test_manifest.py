from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from regmap_manifest import ManifestValidationError, load_manifest, parse_scratch_range
from regmap_profiles import get_profile


HEADER = "S.No,Register Name,Access,Address,Value,Width,Expected,Mask,Verification,Safety,Requires Halt,Restore\n"


class ManifestTests(unittest.TestCase):
    def test_samv71_template_matches_profile(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checks = load_manifest(root / "register_map_template.csv")

        self.assertEqual(len(checks), 5)
        get_profile("samv71q21").validate(checks)

    def test_invalid_access_is_rejected_before_execution(self) -> None:
        contents = HEADER + "1,Bad,RWW,0x400E0940,,32,,,record,read_only,true,\n"

        with self._manifest(contents) as path:
            with self.assertRaises(ManifestValidationError) as context:
                load_manifest(path)

        self.assertIn("Access must be R, W, or RW", str(context.exception))

    def test_write_requires_scratch_safety_class(self) -> None:
        contents = HEADER + "1,Scratch,RW,0x2045F000,0xDEADBEEF,32,,,exact,read_only,true,true\n"

        with self._manifest(contents) as path:
            with self.assertRaises(ManifestValidationError) as context:
                load_manifest(path)

        self.assertIn("restricted to Safety=scratch", str(context.exception))

    def test_scratch_range_requires_valid_address_and_size(self) -> None:
        scratch = parse_scratch_range("0x2045F000:0x100")
        self.assertTrue(scratch.contains(0x2045F0FC, 32))
        self.assertFalse(scratch.contains(0x2045F100, 32))

    def test_unquoted_comma_in_csv_is_rejected(self) -> None:
        contents = HEADER + "1,CPUID,R,0xE000ED00,,32,0x411FC271,,exact,read_only,true,,first,second\n"

        with self._manifest(contents) as path:
            with self.assertRaises(ManifestValidationError) as context:
                load_manifest(path)

        self.assertIn("Quote fields that contain commas", str(context.exception))

    def _manifest(self, contents: str):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "manifest.csv"
        path.write_text(contents, encoding="utf-8")
        return _PathContext(path)


class _PathContext:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
