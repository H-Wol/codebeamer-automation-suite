from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.release_metadata import parse_release_tag
from scripts.release_metadata import read_release_version
from scripts.release_metadata import validate_release_tag
from scripts.release_metadata import write_github_output


class ReleaseMetadataTest(unittest.TestCase):
    def test_stable_tag(self) -> None:
        parsed = parse_release_tag("v1.2.3")

        self.assertEqual(parsed.version, "1.2.3")
        self.assertIsNone(parsed.rc_number)
        self.assertFalse(parsed.is_prerelease)

    def test_release_candidate_tag(self) -> None:
        parsed = parse_release_tag("v1.2.3-rc.4")

        self.assertEqual(parsed.version, "1.2.3")
        self.assertEqual(parsed.rc_number, 4)
        self.assertTrue(parsed.is_prerelease)

    def test_invalid_tags_are_rejected(self) -> None:
        invalid_tags = (
            "1.2.3",
            "v1.2",
            "v1.2.3-beta.1",
            "v01.2.3",
            "v1.02.3",
            "v1.2.03",
            "v1.2.3-rc.01",
            "v1.2.3-rc.",
            "v1.2.3-extra",
        )

        for tag in invalid_tags:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                parse_release_tag(tag)

    def test_version_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            version_file = Path(temporary_directory) / "VERSION"
            version_file.write_text("1.2.4\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "does not match VERSION"):
                validate_release_tag("v1.2.3", version_file)

    def test_version_file_accepts_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            version_file = Path(temporary_directory) / "VERSION"
            version_file.write_text("1.2.3\n", encoding="utf-8")

            self.assertEqual(read_release_version(version_file), "1.2.3")
            self.assertEqual(
                validate_release_tag("v1.2.3-rc.0", version_file).version,
                "1.2.3",
            )

    def test_invalid_version_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            version_file = Path(temporary_directory) / "VERSION"
            version_file.write_text("1.2.3-rc.1\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "X.Y.Z"):
                read_release_version(version_file)

    def test_github_output_contains_release_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "github-output.txt"

            write_github_output(output_path, parse_release_tag("v1.2.3-rc.2"))

            self.assertEqual(
                output_path.read_text(encoding="utf-8").splitlines(),
                [
                    "artifact_version=v1.2.3-rc.2",
                    "prerelease=true",
                    "release_tag=v1.2.3-rc.2",
                    "version=1.2.3",
                ],
            )


if __name__ == "__main__":
    unittest.main()
