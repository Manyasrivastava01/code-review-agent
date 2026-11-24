"""Specialist agents (Security, Correctness, Performance) running concurrently via asyncio."""

import asyncio
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
from src.agent.tools import CodebaseTools, AGENT_TOOLS_DEFINITIONS
from src.llm_reviewer import REVIEW_TOOL_DEFINITION

load_dotenv()

# Specialized System Prompts
SPECIALIST_PROMPTS = {
    "security": """You are an elite Security Specialist code reviewer.
Your SOLE focus is identifying security vulnerabilities, including:
- OWASP Top 10 (SQL/Command/NoSQL injection, XSS, SSRF, IDOR).
- Cryptographic weaknesses and hardcoded secrets.
- Insecure deserialization, path traversal, and unsafe reflection.
- Authentication/authorization bypasses and privilege escalation.

Ignore formatting, stylistic preferences, and non-security bugs.
Use codebase tools to trace untrusted user input to sensitive sinks.
Submit findings via `report_findings` with category 'security'.""",

    "correctness": """You are a senior Software Reliability Engineer and Correctness Specialist.
Your SOLE focus is catching logic bugs and contract violations, including:
- Broken assumptions and mismatches with existing functions or types in other files.
- Off-by-one errors, infinite loops, and unhandled exceptions/edge cases.
- Race conditions, shared mutable state issues, and deadlock possibilities.
- Null/None dereferences and improper error handling.

Ignore minor style or styling preferences.
Use codebase tools to verify function signatures and callers across files.
Submit findings via `report_findings` with category 'correctness'.""",

    "performance": """You are a Principal Performance Engineer.
Your SOLE focus is identifying algorithmic and resource inefficiencies, including:
- N+1 query patterns and redundant database or network roundtrips.
- Algorithmic bottlenecks (e.g. O(n^2) operations inside loops instead of sets/dicts).
- Unbounded memory consumption or memory leaks (unclosed streams, unreleased resources).
- Blocking I/O inside asynchronous or high-throughput code paths.

Ignore cosmetic style and pure security flaws unless they impact resource exhaustion.
Submit findings via `report_findings` with category 'performance'.""",
}


class SpecialistAgent:
    """Async specialist agent focused on a single review domain."""

    def __init__(
        self,
        specialist_type: str,  # 'security', 'correctness', or 'performance'
        repo_dir: str,
        model: str = "claude-3-5-haiku-20241022",
        max_steps: int = 4,
        api_key: Optional[str] = None,
    ):
        if specialist_type not in SPECIALIST_PROMPTS:
            raise ValueError(f"Unknown specialist type: '{specialist_type}'")

        self.specialist_type = specialist_type
        self.repo_dir = repo_dir
        self.model = model
        self.max_steps = max_steps
        self.system_prompt = SPECIALIST_PROMPTS[specialist_type]

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)

    async def review_pr_async(self, pr_diff: str, target_file: str) -> list[Finding]:
        """Execute the async specialist review loop with tool calling."""
        tools = CodebaseTools(repo_dir=self.repo_dir, pr_diff=pr_diff)
        all_tools = AGENT_TOOLS_DEFINITIONS + [REVIEW_TOOL_DEFINITION]

        messages = [
            {
                "role": "user",
                "content": (
                    f"Specialist Review Domain: [{self.specialist_type.upper()}]\n"
                    f"Target file: `{target_file}`\n\n"
                    f"Diff:\n```diff\n{pr_diff}\n```\n\n"
                    "Inspect necessary files using tools and submit findings via `report_findings`."
                ),
            }
        ]

        for step in range(1, self.max_steps + 1):
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self.system_prompt,
                messages=messages,
                tools=all_tools,
            )

            messages.append({"role": "assistant", "content": response.content})
            tool_calls = [b for b in response.content if b.type == "tool_use"]

            if not tool_calls:
                break

            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.name
                tool_args = tool_call.input

                if tool_name == "report_findings":
                    findings = []
                    for item in tool_args.get("findings", []):
                        findings.append(
                            Finding(
                                tool=f"specialist-{self.specialist_type}",
                                rule_id=item["rule_id"],
                                category=item["category"],
                                severity=item["severity"],
                                confidence=item["confidence"],
                                message=item["message"],
                                file_path=item["file_path"],
                                line_number=item["line_number"],
                                suggested_fix=item.get("suggested_fix"),
                            )
                        )
                    return findings

                output = tools.execute_tool(tool_name, tool_args)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": output,
                })

            messages.append({"role": "user", "content": tool_results})

        # Fallback if max steps reached
        final_response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=self.system_prompt,
            messages=messages,
            tools=[REVIEW_TOOL_DEFINITION],
            tool_choice={"type": "tool", "name": "report_findings"},
        )
        for block in final_response.content:
            if block.type == "tool_use" and block.name == "report_findings":
                return [
                    Finding(
                        tool=f"specialist-{self.specialist_type}",
                        rule_id=i["rule_id"],
                        category=i["category"],
                        severity=i["severity"],
                        confidence=i["confidence"],
                        message=i["message"],
                        file_path=i["file_path"],
                        line_number=i["line_number"],
                        suggested_fix=i.get("suggested_fix"),
                    )
                    for i in block.input.get("findings", [])
                ]

        return []


async def run_specialists_parallel(
    repo_dir: str,
    pr_diff: str,
    target_file: str,
    model: str = "claude-3-5-haiku-20241022",
    api_key: Optional[str] = None,
) -> list[Finding]:
    """Run Security, Correctness, and Performance specialists concurrently."""
    security_agent = SpecialistAgent("security", repo_dir, model=model, api_key=api_key)
    correctness_agent = SpecialistAgent("correctness", repo_dir, model=model, api_key=api_key)
    performance_agent = SpecialistAgent("performance", repo_dir, model=model, api_key=api_key)

    print(f"🚀 Launching 3 Specialist Agents concurrently with asyncio.gather...")

    results = await asyncio.gather(
        security_agent.review_pr_async(pr_diff, target_file),
        correctness_agent.review_pr_async(pr_diff, target_file),
        performance_agent.review_pr_async(pr_diff, target_file),
    )

    all_findings = []
    for specialist_findings in results:
        all_findings.extend(specialist_findings)

    print(f"✅ All 3 specialists finished. Total raw findings: {len(all_findings)}")
    return all_findings