"""Tests for the Critic Agent and confidence threshold filtering."""

from unittest.mock import MagicMock, patch
from src.schemas import Finding
from src.agent.critic import CriticAgent


def test_critic_filters_low_confidence_and_hallucinations():
    genuine_finding = Finding(
        tool="specialist-security",
        rule_id="SEC_SQLI",
        category="security",
        severity="critical",
        confidence="high",
        message="Direct string concatenation in SQL query",
        file_path="db.py",
        line_number=10,
    )

    hallucinated_finding = Finding(
        tool="specialist-correctness",
        rule_id="NITPICK_UNUSED",
        category="correctness",
        severity="info",
        confidence="low",
        message="Variable might be unused if universe ends",
        file_path="db.py",
        line_number=2,
    )

    critic = CriticAgent(confidence_threshold=0.75, api_key="mock-key")

    mock_tool = MagicMock()
    mock_tool.type = "tool_use"
    mock_tool.name = "submit_verdicts"
    mock_tool.input = {
        "verdicts": [
            {
                "finding_id": genuine_finding.fingerprint,
                "is_valid": True,
                "confidence_score": 0.95,
                "reasoning": "Real SQL injection on line 10",
            },
            {
                "finding_id": hallucinated_finding.fingerprint,
                "is_valid": False,
                "confidence_score": 0.30,
                "reasoning": "Hallucination; line 2 is properly handled",
            },
        ]
    }

    mock_response = MagicMock()
    mock_response.content = [mock_tool]

    with patch.object(critic.client.messages, "create", return_value=mock_response):
        accepted, rejected = critic.filter_findings(
            findings=[genuine_finding, hallucinated_finding],
            pr_diff="@@ -0,0 +10 @@\n+query = 'SELECT * FROM users WHERE id = ' + uid",
        )

        assert len(accepted) == 1
        assert len(rejected) == 1
        assert accepted[0].rule_id == "SEC_SQLI"
        assert rejected[0].rule_id == "NITPICK_UNUSED"