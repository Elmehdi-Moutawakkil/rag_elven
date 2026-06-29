"""Read-only open-source readiness audit.

This script checks for publication blockers without changing files. It is not a
legal review. It flags missing decisions, tracked data risks, and obvious
secret patterns so the final publication pass has a concrete checklist.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FindingLevel = Literal["blocker", "warning", "info"]

SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\b(?:GROQ|ANTHROPIC|OPENAI)_API_KEY\s*=\s*[A-Za-z0-9_-]{12,}\b"),
]

TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".env", ".example"}
PUBLICATION_RISK_PREFIXES = ("data/", "vector_db/")


@dataclass(frozen=True)
class Finding:
    level: FindingLevel
    code: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def git_ls_files(root: Path = PROJECT_ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {".env.example", ".gitignore", "Makefile"}


def audit_tracked_files(root: Path = PROJECT_ROOT) -> list[Finding]:
    findings: list[Finding] = []
    tracked = git_ls_files(root)

    if ".env" in tracked:
        findings.append(Finding("blocker", "tracked-env", "Real .env file must not be tracked.", ".env"))

    if not (root / ".env.example").exists():
        findings.append(Finding("blocker", "missing-env-example", ".env.example is required."))

    if not (root / "README.md").exists():
        findings.append(Finding("blocker", "missing-readme", "README.md is required."))

    if not any((root / name).exists() for name in ("LICENSE", "LICENSE.md", "COPYING")):
        findings.append(
            Finding(
                "warning",
                "license-undecided",
                "No LICENSE file found. Choose a license before public release.",
            )
        )

    for rel_path in tracked:
        if rel_path.startswith(PUBLICATION_RISK_PREFIXES):
            findings.append(
                Finding(
                    "warning",
                    "tracked-data-review",
                    "Tracked corpus/index asset needs license and redistribution review before public release.",
                    rel_path,
                )
            )
            continue

        path = root / rel_path
        if path.exists() and _is_text_file(path):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    findings.append(
                        Finding(
                            "blocker",
                            "possible-secret",
                            "Possible secret-like token in tracked text file.",
                            rel_path,
                        )
                    )
                    break

    return findings


def summarize(findings: list[Finding]) -> dict[str, object]:
    counts = {
        "blocker": sum(1 for finding in findings if finding.level == "blocker"),
        "warning": sum(1 for finding in findings if finding.level == "warning"),
        "info": sum(1 for finding in findings if finding.level == "info"),
    }
    status = "blocked" if counts["blocker"] else "review_required" if counts["warning"] else "ready"
    return {
        "schema_version": 1,
        "status": status,
        "counts": counts,
        "findings": [finding.to_dict() for finding in findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit open-source readiness without modifying files.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as non-zero exit.")
    args = parser.parse_args()

    report = summarize(audit_tracked_files())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Open-source readiness: {report['status']}")
        for finding in report["findings"]:
            path = f" [{finding['path']}]" if finding.get("path") else ""
            print(f"- {finding['level']}: {finding['code']}{path} - {finding['message']}")

    counts = report["counts"]
    if counts["blocker"]:
        return 1
    if args.strict and counts["warning"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
