"""Tests for Cost Router model tiering and smart escalation."""

from src.schemas import Finding
from src.router.router import CostRouter, CHEAP_TIER, STRONG_TIER


def test_routing_sensitive_files_escalates_to_strong_model():
    router = CostRouter()

    # Routine file should get cheap tier
    routine_model = router.route_specialist("correctness", "utils/string_helpers.py")
    assert routine_model == CHEAP_TIER

    # Auth file must get escalated to strong tier
    auth_model = router.route_specialist("security", "services/auth_handler.py")
    assert auth_model == STRONG_TIER

    token_model = router.route_specialist("correctness", "api/jwt_token.py")
    assert token_model == STRONG_TIER


def test_escalation_for_uncertain_high_severity_findings():
    router = CostRouter()

    # Confident finding on normal file -> no escalation needed
    confident_finding = Finding(
        tool="specialist-correctness",
        rule_id="NULL_DEREF",
        category="correctness",
        severity="error",
        confidence="high",
        message="Definite None dereference",
        file_path="math.py",
        line_number=10,
    )
    assert router.should_escalate_finding(confident_finding) is False

    # Uncertain critical finding on normal file -> must escalate to verify!
    uncertain_finding = Finding(
        tool="specialist-security",
        rule_id="POSSIBLE_RACE",
        category="security",
        severity="critical",
        confidence="low",
        message="Possible race condition under load",
        file_path="cache.py",
        line_number=25,
    )
    assert router.should_escalate_finding(uncertain_finding) is True