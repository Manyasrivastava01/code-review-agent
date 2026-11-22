"""Bandit security analyzer and normalizer."""

import json
import os
import shutil
import subprocess
import sys
from typing import Sequence
from src.analyzers.base import BaseAnalyzer
from src.schemas import Finding, SeverityLevel, ConfidenceLevel


class BanditAnalyzer(BaseAnalyzer):
    """Runs Bandit for Python security flaws and normalizes output into Findings."""

    name = "bandit"

    def is_available(self) -> bool:
        """Check if bandit CLI or python module is available."""
        return shutil.which("bandit") is not None or self._can_import()

    def _can_import(self) -> bool:
        try:
            import bandit  # noqa: F401
            return True
        except ImportError:
            return False

    def run(self, file_paths: Sequence[str]) -> list[Finding]:
        python_files = [f for f in file_paths if f.endswith(".py") and os.path.exists(f)]
        if not python_files:
            return []

        # Run bandit with JSON output format
        cmd = [sys.executable, "-m", "bandit", "-f", "json", "-q"] + python_files
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            output = result.stdout.strip()
            if not output:
                return []
            data = json.loads(output)
        except Exception as e:
            print(f"[Bandit] Warning: failed to run bandit: {e}", file=sys.stderr)
            return []

        return self.normalize(data)

    def normalize(self, data: dict) -> list[Finding]:
        """Convert raw Bandit JSON output to list of Finding objects."""
        findings: list[Finding] = []
        severity_map: dict[str, SeverityLevel] = {
            "HIGH": "critical",
            "MEDIUM": "warning",
            "LOW": "info",
            "UNDEFINED": "info",
        }
        confidence_map: dict[str, ConfidenceLevel] = {
            "HIGH": "high",
            "MEDIUM": "medium",
            "LOW": "low",
        }

        results = data.get("results", [])
        for item in results:
            raw_severity = item.get("issue_severity", "MEDIUM").upper()
            raw_confidence = item.get("issue_confidence", "MEDIUM").upper()

            file_path = os.path.normpath(item.get("filename", "")).replace("\\", "/")
            if file_path.startswith("./"):
                file_path = file_path[2:]

            cwe_info = item.get("issue_cwe", {})
            cwe_id = cwe_info.get("id")
            cwe_link = cwe_info.get("link")
            rule_id = item.get("test_id", "B000")
            if cwe_id:
                rule_id = f"{rule_id} (CWE-{cwe_id})"

            finding = Finding(
                tool="bandit",
                rule_id=rule_id,
                category="security",
                severity=severity_map.get(raw_severity, "warning"),
                confidence=confidence_map.get(raw_confidence, "medium"),
                message=item.get("issue_text", ""),
                file_path=file_path,
                line_number=item.get("line_number", 1),
                code_snippet=item.get("code", "").strip(),
                url=cwe_link or item.get("more_info"),
            )
            findings.append(finding)

        return findings
