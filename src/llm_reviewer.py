"""Direct LLM code review on PR diffs with structured output using Claude."""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import anthropic

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas import Finding

# Tool definition forcing structured Pydantic-compatible JSON output
REVIEW_TOOL_DEFINITION = {
    "name": "report_findings",
    "description": "Report all detected code quality, correctness, performance, or security issues.",
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rule_id": {
                            "type": "string",
                            "description": "Short rule or issue code, e.g. HARDCODED_SECRET, RESOURCE_LEAK",
                        },
                        "category": {
                            "type": "string",
                            "enum": ["security", "correctness", "performance", "style", "other"],
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["info", "warning", "error", "critical"],
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "message": {
                            "type": "string",
                            "description": "Clear explanation of why this is a bug or problem",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "File path relative to repo root",
                        },
                        "line_number": {
                            "type": "integer",
                            "description": "The exact modified line number where the issue occurs",
                        },
                        "suggested_fix": {
                            "type": "string",
                            "description": "Concrete code replacement fixing the issue",
                        },
                    },
                    "required": ["rule_id", "category", "severity", "confidence", "message", "file_path", "line_number"],
                },
            }
        },
        "required": ["findings"],
    },
}

REVIEW_SYSTEM_PROMPT = """You are an expert senior code reviewer.
Review the provided git diff carefully. Focus strictly on:
1. Logic errors, off-by-one mistakes, and broken assumptions.
2. Security vulnerabilities (OWASP top 10, CWEs).
3. Resource leaks, race conditions, and performance bottlenecks.

Do NOT comment on minor formatting or style unless it causes bugs.
Only flag issues that exist on lines added or modified (lines starting with +).
You MUST call the `report_findings` tool to submit your findings. If no issues exist, return an empty findings list."""


def review_diff_with_llm(
    diff_text: str,
    file_path: str,
    model: str = "claude-3-5-haiku-20241022",
) -> list[Finding]:
    """Call Claude with the PR diff and return structured Finding objects."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")

    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"File: {file_path}\n\nGit Diff:\n```diff\n{diff_text}\n```"

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=REVIEW_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        tools=[REVIEW_TOOL_DEFINITION],
        tool_choice={"type": "tool", "name": "report_findings"},
    )

    findings: list[Finding] = []
    for content_block in response.content:
        if content_block.type == "tool_use" and content_block.name == "report_findings":
            raw_findings = content_block.input.get("findings", [])
            for item in raw_findings:
                finding = Finding(
                    tool="llm-haiku",
                    rule_id=item["rule_id"],
                    category=item["category"],
                    severity=item["severity"],
                    confidence=item["confidence"],
                    message=item["message"],
                    file_path=item["file_path"],
                    line_number=item["line_number"],
                    suggested_fix=item.get("suggested_fix"),
                )
                findings.append(finding)

    return findings


if __name__ == "__main__":
    load_dotenv()

    sample_diff = """@@ -0,0 +1,5 @@
+def authenticate(username, password):
+    # TODO: Replace hardcoded credential check
+    if username == "admin" and password == "secret123":
+        return True
+    return False"""

    print("Running Claude on sample diff...")
    try:
        results = review_diff_with_llm(sample_diff, "app.py")
        print(f"\nClaude found {len(results)} issue(s):")
        for f in results:
            print(f"- [{f.severity.upper()}] Line {f.line_number} ({f.rule_id}): {f.message}")
            if f.suggested_fix:
                print(f"  Suggested fix:\n    {f.suggested_fix}")
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)