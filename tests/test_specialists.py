"""Tests for concurrent specialist agents execution."""

import pytest
from unittest.mock import MagicMock, patch
from src.agent.specialists import run_specialists_parallel, SpecialistAgent


@pytest.mark.anyio
async def test_specialists_parallel_execution():
    """Verify that all 3 specialists run concurrently and output domain-tagged findings."""
    async def mock_review(self, pr_diff: str, target_file: str):
        return [MagicMock(tool=f"specialist-{self.specialist_type}", category=self.specialist_type)]

    with patch.object(SpecialistAgent, "review_pr_async", mock_review):
        findings = await run_specialists_parallel(
            repo_dir=".",
            pr_diff="@@ -0,0 +1 @@\n+sample",
            target_file="app.py",
            api_key="mock-key",
        )

        assert len(findings) == 3
        tools = {f.tool for f in findings}
        assert tools == {"specialist-security", "specialist-correctness", "specialist-performance"}
