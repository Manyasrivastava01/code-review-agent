"""Tests for pricing calculator and cost logging."""

import tempfile
from pathlib import Path
from src.router.pricing import calculate_cost, CallMetrics
from src.storage import AuditStorage


def test_pricing_calculation():
    # 10,000 input tokens, 1,000 output tokens on Haiku
    cost_haiku = calculate_cost("claude-3-5-haiku-20241022", 10_000, 1_000)
    # 10k * $0.80/M = $0.008, 1k * $4.00/M = $0.004 -> Total $0.012
    assert cost_haiku == 0.012

    # Same tokens on Sonnet
    cost_sonnet = calculate_cost("claude-3-5-sonnet-20241022", 10_000, 1_000)
    # 10k * $3.00/M = $0.030, 1k * $15.00/M = $0.015 -> Total $0.045
    assert cost_sonnet == 0.045
    assert cost_sonnet > (3 * cost_haiku)  # Sonnet is >3x more expensive!


def test_cost_logging_in_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = AuditStorage(db_path=str(Path(tmpdir) / "test_costs.db"))

        metrics = CallMetrics(
            caller="specialist-security",
            model="claude-3-5-haiku-20241022",
            input_tokens=5000,
            output_tokens=500,
            latency_ms=850.5,
            cost_usd=0.006,
        )

        storage.record_llm_cost(pr_number=1, metrics=metrics)
        summary = storage.get_pr_cost_summary(pr_number=1)

        assert summary["total_calls"] == 1
        assert summary["total_input_tokens"] == 5000
        assert summary["total_output_tokens"] == 500
        assert round(summary["total_cost_usd"], 3) == 0.006
        assert summary["avg_latency_ms"] == 850.5