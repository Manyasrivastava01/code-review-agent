"""Critic Agent: Filters false positives and weak findings using confidence scoring."""

import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import anthropic

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas import Finding

load_dotenv()

CRITIC_SYSTEM_PROMPT = """You are a Principal Code Review Critic and False-Positive Filter.
Your job is to critically evaluate candidate findings produced by junior reviewers and eliminate:
1. Hallucinations (claiming a bug exists when the code handles it properly).
2. Pedantic nitpicks that do not impact security, correctness, or performance.
3. Speculative warnings with low probability of real-world failure.

For each finding:
- Determine if it is a genuine, actionable defect (`is_valid: true`).
- Assign a confidence score from 0.0 (pure hallucination) to 1.0 (verified critical bug).
- Provide a concise reasoning explaining why it is accepted or rejected.
"""

CRITIC_TOOL_DEFINITION = {
    "name": "submit_verdicts",
    "description": "Submit verification verdicts for all evaluated candidate findings.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "finding_id": {"type": "string", "description": "The fingerprint or rule_id of the finding"},
                        "is_valid": {"type": "boolean", "description": "True if genuine issue, False if hallucination or noise"},
                        "confidence_score": {"type": "number", "description": "Confidence from 0.0 to 1.0"},
                        "reasoning": {"type": "string", "description": "Reasoning for the verdict"},
                    },
                    "required": ["finding_id", "is_valid", "confidence_score", "reasoning"],
                },
            }
        },
        "required": ["verdicts"],
    },
}


class CriticAgent:
    """Evaluates findings to weed out false positives and low-confidence warnings."""

    def __init__(
        self,
        model: str = "claude-3-5-haiku-20241022",
        confidence_threshold: float = 0.75,
        api_key: Optional[str] = None,
    ):
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def filter_findings(
        self,
        findings: list[Finding],
        pr_diff: str,
    ) -> tuple[list[Finding], list[Finding]]:
        """Filter findings through the Critic.
        
        Returns:
            (accepted_findings, rejected_findings)
        """
        if not findings:
            return [], []

        # Prepare candidate payload for Critic
        candidates_summary = []
        for f in findings:
            candidates_summary.append({
                "id": f.fingerprint,
                "tool": f.tool,
                "rule": f.rule_id,
                "file": f.file_path,
                "line": f.line_number,
                "severity": f.severity,
                "message": f.message,
                "suggested_fix": f.suggested_fix,
            })

        user_content = (
            f"PR Diff:\n```diff\n{pr_diff}\n```\n\n"
            f"Candidate Findings to Evaluate:\n{candidates_summary}\n\n"
            "Evaluate each finding critically and submit verdicts via `submit_verdicts`."
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=CRITIC_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            tools=[CRITIC_TOOL_DEFINITION],
            tool_choice={"type": "tool", "name": "submit_verdicts"},
        )

        verdicts = {}
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_verdicts":
                for v in block.input.get("verdicts", []):
                    verdicts[v["finding_id"]] = v

        accepted: list[Finding] = []
        rejected: list[Finding] = []

        for f in findings:
            # Check by fingerprint or rule_id
            verdict = verdicts.get(f.fingerprint) or verdicts.get(f.rule_id)
            if not verdict:
                # Default fallback: keep finding if critic didn't evaluate
                accepted.append(f)
                continue

            score = verdict.get("confidence_score", 0.0)
            is_valid = verdict.get("is_valid", False)

            if is_valid and score >= self.confidence_threshold:
                accepted.append(f)
            else:
                rejected.append(f)

        return accepted, rejected