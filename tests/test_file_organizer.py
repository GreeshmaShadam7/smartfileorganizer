
import tempfile
import unittest
from pathlib import Path

from file_scanner import get_category, is_screenshot
from duplicate_detector import find_duplicates


class TestSmartFileOrganizer(unittest.TestCase):

    def test_pdf_category(self):
        self.assertEqual(
            get_category(Path("resume.pdf")),
            "Documents",
        )

    def test_zip_category(self):
        self.assertEqual(
            get_category(Path("backup.zip")),
            "Archives",
        )

    def test_screenshot_detection(self):
        self.assertTrue(
            is_screenshot(Path("Screenshot_2026.png"))
        )

    def test_duplicate_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / "one.txt"
            second = Path(folder) / "two.txt"

            first.write_text("same content", encoding="utf-8")
            second.write_text("same content", encoding="utf-8")

            records = [
                {"path": str(first)},
                {"path": str(second)},
            ]

            duplicates = find_duplicates(records)

            self.assertEqual(len(duplicates), 1)
            self.assertEqual(duplicates[0]["count"], 2)


if __name__ == "__main__":
    unittest.main()