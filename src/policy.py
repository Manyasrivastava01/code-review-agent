"""Policy Engine for enforcing merge gates based on YAML configuration."""

import os
from pathlib import Path
from typing import Sequence
import yaml
from pydantic import BaseModel, Field
from src.schemas import Finding


class BlockRules(BaseModel):
    blocked_severities: list[str] = Field(default_factory=lambda: ["critical", "error"])
    blocked_categories: list[str] = Field(default_factory=lambda: ["security"])
    max_warnings: int = 3


class PolicyConfig(BaseModel):
    version: str = "1.0"
    policy_name: str = "Default Guardrails"
    block_rules: BlockRules = Field(default_factory=BlockRules)
    status_check_context: str = "code-review/autonomous-agent"


class PolicyDecision(BaseModel):
    passed: bool
    reasons: list[str]
    critical_count: int
    error_count: int
    warning_count: int
    summary: str


def load_policy(policy_path: str = "review_policy.yaml") -> PolicyConfig:
    """Load policy configuration from YAML, or return safe defaults."""
    path = Path(policy_path)
    if not path.is_file():
        return PolicyConfig()

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return PolicyConfig(**data)


def evaluate_policy(findings: Sequence[Finding], policy: PolicyConfig) -> PolicyDecision:
    """Evaluate findings against policy rules to determine pass/fail merge status."""
    reasons: list[str] = []

    criticals = [f for f in findings if f.severity == "critical"]
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    # Check blocked severities
    for f in findings:
        if f.severity in policy.block_rules.blocked_severities:
            msg = f"Blocked by [{f.severity.upper()}] finding ({f.rule_id}) in {f.file_path}:{f.line_number}"
            if msg not in reasons:
                reasons.append(msg)

    # Check blocked categories
    for f in findings:
        if f.category in policy.block_rules.blocked_categories and f.severity != "info":
            msg = f"Blocked by [{f.category.upper()}] category rule ({f.rule_id}) in {f.file_path}:{f.line_number}"
            if msg not in reasons:
                reasons.append(msg)

    # Check max warnings
    if len(warnings) > policy.block_rules.max_warnings:
        reasons.append(
            f"Exceeded max allowable warnings ({len(warnings)} > {policy.block_rules.max_warnings})"
        )

    passed = len(reasons) == 0

    if passed:
        summary = "All policy gates passed. Code is clear for merge!"
    else:
        summary = f"Merge blocked: {len(reasons)} policy violation(s) detected."

    return PolicyDecision(
        passed=passed,
        reasons=reasons,
        critical_count=len(criticals),
        error_count=len(errors),
        warning_count=len(warnings),
        summary=summary,
    )