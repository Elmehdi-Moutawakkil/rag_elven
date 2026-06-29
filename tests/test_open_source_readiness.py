import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.open_source_audit import audit_tracked_files, summarize


class OpenSourceReadinessTests(unittest.TestCase):
    def test_audit_flags_tracked_env_as_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("OPENAI_API_KEY=sk-test", encoding="utf-8")
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")

            with patch("scripts.open_source_audit.git_ls_files", return_value=[".env", "README.md", ".env.example"]):
                report = summarize(audit_tracked_files(root))

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["counts"]["blocker"], 1)

    def test_audit_warns_when_license_is_undecided(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")

            with patch("scripts.open_source_audit.git_ls_files", return_value=["README.md", ".env.example"]):
                report = summarize(audit_tracked_files(root))

        self.assertEqual(report["status"], "review_required")
        self.assertEqual(report["counts"]["warning"], 1)

    def test_audit_warns_for_tracked_data_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")
            (root / "LICENSE").write_text("placeholder\n", encoding="utf-8")

            with patch("scripts.open_source_audit.git_ls_files", return_value=["README.md", ".env.example", "LICENSE", "data/source.pdf"]):
                report = summarize(audit_tracked_files(root))

        self.assertEqual(report["status"], "review_required")
        self.assertEqual(report["findings"][0]["code"], "tracked-data-review")


if __name__ == "__main__":
    unittest.main()
