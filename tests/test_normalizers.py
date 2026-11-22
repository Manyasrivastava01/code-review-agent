"""Tests for normalizers."""

from src.analyzers.bandit_analyzer import BanditAnalyzer
from src.analyzers.ruff_analyzer import RuffAnalyzer


def test_bandit_normalizer():
    analyzer = BanditAnalyzer()
    sample_bandit_json = {
        "results": [
            {
                "code": "if username == 'admin' and password == 'secret':",
                "filename": "./app.py",
                "issue_confidence": "HIGH",
                "issue_cwe": {"id": 259, "link": "https://cwe.mitre.org/data/definitions/259.html"},
                "issue_severity": "HIGH",
                "issue_text": "Possible hardcoded password: 'secret'",
                "line_number": 3,
                "test_id": "B105",
                "test_name": "hardcoded_password_string",
            }
        ]
    }
    findings = analyzer.normalize(sample_bandit_json)
    assert len(findings) == 1
    f = findings[0]
    assert f.tool == "bandit"
    assert f.rule_id == "B105 (CWE-259)"
    assert f.severity == "critical"
    assert f.confidence == "high"
    assert f.file_path == "app.py"
    assert f.line_number == 3


def test_ruff_normalizer():
    analyzer = RuffAnalyzer()
    sample_ruff_json = [
        {
            "code": "F401",
            "message": "`os` imported but unused",
            "filename": "src/module.py",
            "location": {"row": 2, "column": 8},
            "severity": "error",
            "url": "https://docs.astral.sh/ruff/rules/unused-import",
            "fix": {
                "edits": [{"content": ""}]
            }
        }
    ]
    findings = analyzer.normalize(sample_ruff_json)
    assert len(findings) == 1
    f = findings[0]
    assert f.tool == "ruff"
    assert f.rule_id == "F401"
    assert f.severity == "error"
    assert f.line_number == 2
    assert f.suggested_fix == ""
