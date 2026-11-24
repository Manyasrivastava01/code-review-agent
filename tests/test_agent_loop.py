"""Tests for the agent loop structure and loop cap."""

from unittest.mock import MagicMock, patch
from src.agent.reviewer_agent import ReviewerAgent


def test_agent_loop_cap():
    """Verify that the agent never exceeds max_steps if it keeps calling read_file."""
    agent = ReviewerAgent(repo_dir=".", max_steps=3, api_key="mock-test-key")

    # Mock Claude returning a read_file tool call repeatedly
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.name = "read_file"
    mock_tool_block.id = "call_123"
    mock_tool_block.input = {"file_path": "README.md"}

    mock_response = MagicMock()
    mock_response.content = [mock_tool_block]

    # Mock the fallback report_findings block
    mock_report_block = MagicMock()
    mock_report_block.type = "tool_use"
    mock_report_block.name = "report_findings"
    mock_report_block.input = {"findings": []}

    mock_fallback_response = MagicMock()
    mock_fallback_response.content = [mock_report_block]

    with patch.object(agent.client.messages, "create", side_effect=[mock_response, mock_response, mock_response, mock_fallback_response]) as mock_create:
        findings = agent.review_pr(pr_diff="@@ -0,0 +1 @@\n+test", target_file="test.py")
        assert findings == []
        # Total calls = 3 loop steps + 1 fallback call = 4
        assert mock_create.call_count == 4