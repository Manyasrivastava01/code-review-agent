"""Ruff linter and code quality analyzer normalizer."""

import json
import os
import shutil
import subprocess
import sys
from typing import Sequence
from src.analyzers.base import BaseAnalyzer
from src.schemas import Finding, SeverityLevel


class RuffAnalyzer(BaseAnalyzer):
    """Runs Ruff check and normalizes output into Findings."""

    name = "ruff"

    def is_available(self) -> bool:
        return shutil.which("ruff") is not None or self._can_import()

    def _can_import(self) -> bool:
        try:
            import ruff  # noqa: F401
            return True
        except ImportError:
            return False

    def run(self, file_paths: Sequence[str]) -> list[Finding]:
        python_files = [f for f in file_paths if f.endswith(".py") and os.path.exists(f)]
        if not python_files:
            return []

        cmd = [sys.executable, "-m", "ruff", "check", "--output-format=json"] + python_files
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            output = result.stdout.strip()
            if not output:
                return []
            data = json.loads(output)
        except Exception as e:
            print(f"[Ruff] Warning: failed to run ruff: {e}", file=sys.stderr)
            return []

        return self.normalize(data)

    def normalize(self, data: list[dict]) -> list[Finding]:
        """Convert raw Ruff JSON output to list of Finding objects."""
        findings: list[Finding] = []
        severity_map: dict[str, SeverityLevel] = {
            "error": "error",
            "warning": "warning",
            "info": "info",
        }

        for item in data:
            location = item.get("location", {})
            end_location = item.get("end_location", {})
            raw_severity = item.get("severity", "warning").lower()

            raw_filename = item.get("filename", "")
            # Make path relative to current working directory
            try:
                rel_path = os.path.relpath(raw_filename, os.getcwd())
            except ValueError:
                rel_path = raw_filename
            file_path = os.path.normpath(rel_path).replace("\\", "/")

            code = item.get("code", "RUFF")
            category = "correctness"
            if code.startswith("S"):
                category = "security"
            elif code.startswith("PERF"):
                category = "performance"
            elif code.startswith(("E", "W", "I", "D")):
                category = "style"

            suggested_fix = None
            fix = item.get("fix")
            if fix and isinstance(fix, dict):
                edits = fix.get("edits", [])
                if edits and isinstance(edits, list):
                    suggested_fix = edits[0].get("content")

            finding = Finding(
                tool="ruff",
                rule_id=code,
                category=category,
                severity=severity_map.get(raw_severity, "warning"),
                confidence="high",
                message=item.get("message", ""),
                file_path=file_path,
                line_number=location.get("row", 1),
                end_line_number=end_location.get("row"),
                column=location.get("column"),
                url=item.get("url"),
                suggested_fix=suggested_fix,
            )
            findings.append(finding)

        return findings
