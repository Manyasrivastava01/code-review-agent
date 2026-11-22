"""Semgrep pattern-based security & correctness analyzer normalizer."""

import json
import os
import shutil
import subprocess
import sys
from typing import Sequence
from src.analyzers.base import BaseAnalyzer
from src.schemas import Finding, SeverityLevel, ConfidenceLevel


class SemgrepAnalyzer(BaseAnalyzer):
    """Runs Semgrep scan and normalizes output into Findings."""

    name = "semgrep"

    def is_available(self) -> bool:
        """Check if semgrep binary is installed in PATH."""
        return shutil.which("semgrep") is not None

    def run(self, file_paths: Sequence[str]) -> list[Finding]:
        target_files = [f for f in file_paths if os.path.exists(f)]
        if not target_files or not self.is_available():
            return []

        # Run semgrep with auto config or standard p/default rules
        cmd = ["semgrep", "scan", "--config=auto", "--json", "--quiet"] + list(target_files)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            output = result.stdout.strip()
            if not output:
                return []
            data = json.loads(output)
        except Exception as e:
            print(f"[Semgrep] Warning: failed to run semgrep: {e}", file=sys.stderr)
            return []

        return self.normalize(data)

    def normalize(self, data: dict) -> list[Finding]:
        """Convert raw Semgrep JSON output to list of Finding objects."""
        findings: list[Finding] = []
        severity_map: dict[str, SeverityLevel] = {
            "ERROR": "error",
            "WARNING": "warning",
            "INFO": "info",
            "EXPERIMENT": "info",
        }
        confidence_map: dict[str, ConfidenceLevel] = {
            "HIGH": "high",
            "MEDIUM": "medium",
            "LOW": "low",
        }

        results = data.get("results", [])
        for item in results:
            extra = item.get("extra", {})
            metadata = extra.get("metadata", {})
            raw_severity = extra.get("severity", "WARNING").upper()
            raw_confidence = metadata.get("confidence", "MEDIUM").upper()

            category = "security" if "security" in metadata.get("category", "").lower() else "correctness"

            start = item.get("start", {})
            end = item.get("end", {})
            file_path = os.path.normpath(item.get("path", "")).replace("\\", "/")

            finding = Finding(
                tool="semgrep",
                rule_id=item.get("check_id", "semgrep-rule"),
                category=category,
                severity=severity_map.get(raw_severity, "warning"),
                confidence=confidence_map.get(raw_confidence, "medium"),
                message=extra.get("message", "").strip(),
                file_path=file_path,
                line_number=start.get("line", 1),
                end_line_number=end.get("line"),
                column=start.get("col"),
                code_snippet=extra.get("lines", "").strip(),
                url=metadata.get("source"),
                suggested_fix=extra.get("fix"),
            )
            findings.append(finding)

        return findings
