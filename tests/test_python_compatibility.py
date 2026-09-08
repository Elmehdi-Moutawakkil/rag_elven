"""Python 3.11 compatibility checks."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON311 = (
    sys.executable if sys.version_info[:2] == (3, 11)
    else os.environ.get("PYTHON311") or shutil.which("python3.11")
)


@unittest.skipUnless(PYTHON311, "Python 3.11 is not installed")
class Python311CompatibilityTests(unittest.TestCase):
    def test_selected_interpreter_is_python311(self):
        result = subprocess.run(
            [str(PYTHON311), "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "3.11")

    def test_project_python_files_compile_under_python311(self):
        paths = [PROJECT_ROOT / "app.py"]
        for directory in ("src", "scripts", "inspector", "mcp", "tests"):
            paths.extend((PROJECT_ROOT / directory).rglob("*.py"))

        result = subprocess.run(
            [str(PYTHON311), "-m", "py_compile", *(str(path) for path in sorted(paths))],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_citations_imports_under_python311(self):
        result = subprocess.run(
            [str(PYTHON311), "-c", "import src.citations; print(src.citations.__name__)"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "src.citations")


if __name__ == "__main__":
    unittest.main()
