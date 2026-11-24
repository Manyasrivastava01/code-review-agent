"""Tests for YAML policy engine and merge status check evaluation."""

import tempfile
from pathlib import Path
from src.schemas import Finding
from src.policy import load_policy, evaluate_policy


def test_policy_blocks_on_critical_finding():
    critical_finding = Finding(
        tool="bandit",
        rule_id="B105",
        category="security",
        severity="critical",
        message="Hardcoded password",
        file_path="app.py",
        line_number=3,
    )

    policy = load_policy("review_policy.yaml")
    decision = evaluate_policy([critical_finding], policy)

    assert decision.passed is False
    assert decision.critical_count == 1
    assert any("CRITICAL" in r for r in decision.reasons)


def test_policy_passes_clean_findings():
    info_finding = Finding(
        tool="ruff",
        rule_id="I001",
        category="style",
        severity="info",
        message="Unsorted imports",
        file_path="app.py",
        line_number=1,
    )

    policy = load_policy("review_policy.yaml")
    decision = evaluate_policy([info_finding], policy)

    assert decision.passed is True
    assert len(decision.reasons) == 0
    assert "clear for merge" in decision.summary