"""Rule-based Cost Router with model tiers and smart escalation."""

import re
from typing import Optional
from src.schemas import Finding

CHEAP_TIER = "claude-3-5-haiku-20241022"
STRONG_TIER = "claude-3-5-sonnet-20241022"

# File patterns that represent sensitive code requiring the strong model tier
SECURITY_SENSITIVE_PATTERNS = [
    r"auth",
    r"login",
    r"crypto",
    r"password",
    r"secret",
    r"token",
    r"permission",
    r"credential",
    r"session",
    r"\.env",
]


class CostRouter:
    """Decides which model tier handles each agent task and manages escalations."""

    def __init__(
        self,
        cheap_model: str = CHEAP_TIER,
        strong_model: str = STRONG_TIER,
    ):
        self.cheap_model = cheap_model
        self.strong_model = strong_model

    def is_security_sensitive(self, file_path: str) -> bool:
        """Check if file touches sensitive authentication, secrets, or encryption logic."""
        file_lower = file_path.lower()
        return any(re.search(pat, file_lower) for pat in SECURITY_SENSITIVE_PATTERNS)

    def route_specialist(self, specialist_type: str, target_file: str) -> str:
        """Choose the most cost-effective model tier for a specialist.
        
        - If the target file is security-sensitive -> escalate to Strong Tier.
        - Otherwise -> run on Cheap Tier.
        """
        if self.is_security_sensitive(target_file):
            return self.strong_model
        return self.cheap_model

    def route_critic(self) -> str:
        """The Critic acts as the ultimate filter, so it defaults to the Strong Tier."""
        return self.strong_model

    def should_escalate_finding(self, finding: Finding) -> bool:
        """Determine if a finding from a cheap model requires strong-model escalation.
        
        Escalate if:
        1. It touches a security-sensitive file.
        2. Or it is a high-severity finding ('critical' or 'error') with 'low' or 'medium' confidence.
        """
        if self.is_security_sensitive(finding.file_path):
            return True

        is_high_severity = finding.severity in ("critical", "error")
        is_uncertain = finding.confidence in ("low", "medium")

        return is_high_severity and is_uncertain