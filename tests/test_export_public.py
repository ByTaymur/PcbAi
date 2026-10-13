import tempfile
import unittest
from pathlib import Path

from scripts.export_public import leaks, private_patterns


class ExportPublicTests(unittest.TestCase):
    def test_home_path_forms_and_email_are_found_but_handle_is_allowed(self):
        pattern = private_patterns(home=Path("C:/Users/Ayse"), emails=["ayse@mail.test"])
        for text in ('"C:\\\\Users\\\\Ayse\\\\Documents"', "C:/Users/ayse/x", "/c/Users/Ayse/x", "/home/ayse/x",
                     "contact: AYSE@mail.test"):
            self.assertTrue(pattern.search(text.encode()), text)
        for text in ('"publisher": "ayse"', "ayse.pcbai-vscode@0.1.4", "%LOCALAPPDATA%\\PcbAi",
                     "C:/Users/Ayseler/x", "C:\\PcbAi\\.venv"):
            self.assertFalse(pattern.search(text.encode()), text)

    def test_leaks_reports_file_and_line_outside_git_folder(self):
        with tempfile.TemporaryDirectory(prefix="pcbai-export-") as temporary:
            root = Path(temporary)
            (root / "docs").mkdir()
            (root / "docs/a.md").write_text("clean\nC:\\Users\\Ayse\\x\n", encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git/config").write_text("/home/ayse\n", encoding="utf-8")
            self.assertEqual(leaks(root, private_patterns(home=Path("/home/ayse"))), ["docs/a.md:2"])


if __name__ == "__main__":
    unittest.main()
