"""Data schemas for code review findings using Pydantic."""

import hashlib
from typing import Optional, Literal
from pydantic import BaseModel, Field


SeverityLevel = Literal["info", "warning", "error", "critical"]
ConfidenceLevel = Literal["low", "medium", "high"]
FindingCategory = Literal["security", "correctness", "performance", "style", "other"]


class Finding(BaseModel):
    """Normalized finding representation across deterministic tools and LLM agents."""

    tool: str = Field(description="Tool or agent that generated the finding (e.g. ruff, bandit, semgrep, llm-security)")
    rule_id: str = Field(description="Unique rule or test identifier (e.g. B105, SIM103)")
    category: FindingCategory = Field(default="other", description="Category of the finding")
    severity: SeverityLevel = Field(default="warning", description="Severity level")
    confidence: Optional[ConfidenceLevel] = Field(default=None, description="Confidence level of the finding")
    message: str = Field(description="Human-readable explanation of the issue")
    file_path: str = Field(description="Path to the file relative to repo root")
    line_number: int = Field(description="Line number in the modified file (1-indexed)")
    end_line_number: Optional[int] = Field(default=None, description="End line number for multi-line findings")
    column: Optional[int] = Field(default=None, description="Starting column offset")
    code_snippet: Optional[str] = Field(default=None, description="Relevant code snippet")
    url: Optional[str] = Field(default=None, description="Reference URL for documentation or CWE")
    suggested_fix: Optional[str] = Field(default=None, description="Suggested code fix if available")

    @property
    def fingerprint(self) -> str:
        """Deterministic fingerprint for deduplication across tools and re-pushes."""
        data = f"{self.file_path}:{self.line_number}:{self.rule_id}:{self.message.strip()}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]

    def to_markdown(self) -> str:
        """Format the finding as a GitHub-flavored Markdown review comment."""
        severity_badges = {
            "critical": "> [!CAUTION]\n> **CRITICAL SEVERITY**",
            "error": "> [!WARNING]\n> **ERROR**",
            "warning": "> [!WARNING]\n> **WARNING**",
            "info": "> [!NOTE]\n> **INFO**",
        }
        badge = severity_badges.get(self.severity, "> [!NOTE]")
        lines = [
            badge,
            f"> **[{self.tool.upper()}] {self.rule_id}**: {self.message}",
        ]
        if self.confidence:
            lines.append(f"> *Confidence:* `{self.confidence.upper()}`")
        if self.url:
            lines.append(f"> *Reference:* [{self.rule_id}]({self.url})")
        if self.suggested_fix:
            lines.append(f"\n```suggestion\n{self.suggested_fix}\n```")
        return "\n".join(lines)
