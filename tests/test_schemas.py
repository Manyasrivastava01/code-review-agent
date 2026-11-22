"""Tests for Finding schema and serialization."""

from src.schemas import Finding


def test_finding_creation_and_fingerprint():
    f1 = Finding(
        tool="bandit",
        rule_id="B105",
        category="security",
        severity="critical",
        confidence="high",
        message="Hardcoded password found",
        file_path="app.py",
        line_number=3,
    )
    f2 = Finding(
        tool="bandit",
        rule_id="B105",
        category="security",
        severity="critical",
        confidence="high",
        message="Hardcoded password found",
        file_path="app.py",
        line_number=3,
    )
    assert f1.fingerprint == f2.fingerprint
    assert len(f1.fingerprint) == 16


def test_finding_to_markdown():
    finding = Finding(
        tool="bandit",
        rule_id="B105",
        category="security",
        severity="critical",
        confidence="high",
        message="Possible hardcoded password",
        file_path="app.py",
        line_number=3,
        url="https://cwe.mitre.org/data/definitions/259.html",
    )
    md = finding.to_markdown()
    assert "CRITICAL SEVERITY" in md
    assert "[BANDIT] B105" in md
    assert "https://cwe.mitre.org/data/definitions/259.html" in md
