"""Tests for finding deduplication logic."""

from src.schemas import Finding
from src.deduplication import deduplicate_findings


def test_deduplicate_same_line_findings():
    f_bandit = Finding(
        tool="bandit",
        rule_id="B105",
        category="security",
        severity="warning",
        confidence="medium",
        message="Possible hardcoded password: 'secret123'",
        file_path="app.py",
        line_number=3,
    )

    f_agent = Finding(
        tool="specialist-security",
        rule_id="HARDCODED_CREDENTIAL",
        category="security",
        severity="critical",
        confidence="high",
        message="Plaintext password in authentication check",
        file_path="app.py",
        line_number=3,
        suggested_fix="password == os.getenv('ADMIN_PASS')",
    )

    f_unrelated = Finding(
        tool="ruff",
        rule_id="F401",
        category="style",
        severity="info",
        message="Unused import",
        file_path="utils.py",
        line_number=1,
    )

    # 3 raw findings with 2 overlapping on app.py:3
    raw = [f_bandit, f_agent, f_unrelated]
    deduped = deduplicate_findings(raw)

    assert len(deduped) == 2

    app_finding = next(f for f in deduped if f.file_path == "app.py")
    assert "bandit" in app_finding.tool
    assert "specialist-security" in app_finding.tool
    assert app_finding.severity == "critical"  # Elevated to highest severity
    assert app_finding.confidence == "high"    # Elevated to highest confidence
    assert app_finding.suggested_fix == "password == os.getenv('ADMIN_PASS')"