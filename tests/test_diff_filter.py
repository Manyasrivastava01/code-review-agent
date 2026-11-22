"""Tests for unified diff line extraction and filtering."""

from src.diff_filter import parse_diff_added_lines, filter_findings_by_diff
from src.schemas import Finding


def test_parse_diff_added_lines():
    sample_patch = (
        "@@ -0,0 +1,5 @@\n"
        "+def authenticate(username, password):\n"
        "+    # TODO: Replace hardcoded credential check\n"
        "+    if username == \"admin\" and password == \"secret123\":\n"
        "+        return True\n"
        "+    return False\n"
    )
    added = parse_diff_added_lines(sample_patch)
    assert added == {1, 2, 3, 4, 5}


def test_filter_findings_by_diff():
    findings = [
        Finding(
            tool="bandit",
            rule_id="B105",
            message="issue on line 3",
            file_path="app.py",
            line_number=3,
        ),
        Finding(
            tool="ruff",
            rule_id="F401",
            message="issue on line 50 (untouched legacy line)",
            file_path="app.py",
            line_number=50,
        ),
    ]
    changed_lines = {"app.py": {1, 2, 3, 4, 5}}
    filtered = filter_findings_by_diff(findings, changed_lines)
    assert len(filtered) == 1
    assert filtered[0].line_number == 3
