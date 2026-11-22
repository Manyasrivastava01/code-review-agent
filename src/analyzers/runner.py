"""Orchestrator to run all available deterministic analyzers."""

from typing import Sequence
from src.schemas import Finding
from src.analyzers.bandit_analyzer import BanditAnalyzer
from src.analyzers.ruff_analyzer import RuffAnalyzer
from src.analyzers.semgrep_analyzer import SemgrepAnalyzer


def run_all_analyzers(file_paths: Sequence[str]) -> list[Finding]:
    """Run Ruff, Bandit, and Semgrep (if available) and collect normalized findings."""
    analyzers = [
        BanditAnalyzer(),
        RuffAnalyzer(),
        SemgrepAnalyzer(),
    ]

    all_findings: list[Finding] = []
    for analyzer in analyzers:
        if analyzer.is_available():
            print(f"Running deterministic analyzer: {analyzer.name}...")
            findings = analyzer.run(file_paths)
            print(f"  -> {analyzer.name} produced {len(findings)} finding(s)")
            all_findings.extend(findings)
        else:
            print(f"Analyzer '{analyzer.name}' is not available in current environment; skipping.")

    return all_findings
