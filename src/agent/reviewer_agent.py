"""Autonomous Code Review Agent with tool calling and a strict loop cap."""

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

AGENT_SYSTEM_PROMPT = """You are an expert autonomous code review agent.
You are reviewing a Pull Request diff. You have code exploration tools:
- `read_file`: Inspect contents and surrounding context of any file.
- `search_code`: Search for functions, callers, and patterns across the repository.
- `find_references`: Locate definitions and usages of symbols.
- `get_diff`: View the full PR diff.

Workflow:
1. First, check the diff to identify changed functions, imports, or callers.
2. Use tools to inspect external files if the diff calls other functions, changes shared signatures, or modifies data structures.
3. Determine if the changes introduce bugs, broken contracts, or security vulnerabilities.
4. When finished investigating, you MUST call `report_findings` with your final list of issues.
   If the code is clean and correct, call `report_findings` with an empty list `findings: []`.
"""


load_dotenv()  # Automatically load .env if present

class ReviewerAgent:
    """Agent that navigates a repository using tools and reports structured findings."""

    def __init__(
        self,
        repo_dir: str,
        model: str = "claude-3-5-haiku-20241022",
        max_steps: int = 6,
        api_key: Optional[str] = None,
    ):
        self.repo_dir = repo_dir
        self.model = model
        self.max_steps = max_steps

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def review_pr(self, pr_diff: str, target_file: str) -> list[Finding]:
        """Execute the agent loop over a PR diff with tool calling."""
        tools = CodebaseTools(repo_dir=self.repo_dir, pr_diff=pr_diff)
        all_tools = AGENT_TOOLS_DEFINITIONS + [REVIEW_TOOL_DEFINITION]

        messages = [
            {
                "role": "user",
                "content": (
                    f"Please review this Pull Request targeting `{target_file}`.\n\n"
                    f"Diff:\n```diff\n{pr_diff}\n```\n\n"
                    "Use tools to investigate referenced files or definitions if needed, "
                    "then submit your findings with `report_findings`."
                ),
            }
        ]

        print(f"Starting Agent Loop (Model: {self.model}, Max Steps: {self.max_steps})...")

        for step in range(1, self.max_steps + 1):
            print(f"\n--- [Agent Step {step}/{self.max_steps}] ---")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=AGENT_SYSTEM_PROMPT,
                messages=messages,
                tools=all_tools,
            )

            # Record assistant response
            messages.append({"role": "assistant", "content": response.content})

            # Check if agent reported findings
            tool_calls = [b for b in response.content if b.type == "tool_use"]

            if not tool_calls:
                print("Agent responded without tool calls.")
                break

            tool_results = []
            reported_findings: Optional[list[Finding]] = None

            for tool_call in tool_calls:
                tool_name = tool_call.name
                tool_args = tool_call.input

                print(f"🔧 Agent invoked tool: `{tool_name}` with args: {tool_args}")

                if tool_name == "report_findings":
                    # Agent completed its review!
                    reported_findings = []
                    for item in tool_args.get("findings", []):
                        finding = Finding(
                            tool=f"agent-{self.model.split('-')[1]}",
                            rule_id=item["rule_id"],
                            category=item["category"],
                            severity=item["severity"],
                            confidence=item["confidence"],
                            message=item["message"],
                            file_path=item["file_path"],
                            line_number=item["line_number"],
                            suggested_fix=item.get("suggested_fix"),
                        )
                        reported_findings.append(finding)
                    return reported_findings

                # Execute investigation tool
                tool_output = tools.execute_tool(tool_name, tool_args)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": tool_output,
                })

            # Pass tool observations back to Claude for the next turn
            messages.append({"role": "user", "content": tool_results})

        # Fallback if loop cap is reached before agent reports findings
        print(f"\n⚠️ Reached loop cap ({self.max_steps} steps). Forcing final findings report...")
        final_response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=AGENT_SYSTEM_PROMPT,
            messages=messages,
            tools=[REVIEW_TOOL_DEFINITION],
            tool_choice={"type": "tool", "name": "report_findings"},
        )
        for block in final_response.content:
            if block.type == "tool_use" and block.name == "report_findings":
                return [
                    Finding(
                        tool=f"agent-{self.model.split('-')[1]}",
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