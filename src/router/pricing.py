"""Token pricing calculation and cost tracking for model tiers."""

from pydantic import BaseModel

# Official Pricing per 1,000,000 tokens (USD)
MODEL_PRICING = {
    # Cheap Tier
    "claude-3-5-haiku-20241022": {
        "input_per_million": 0.80,
        "output_per_million": 4.00,
    },
    # Strong Tier
    "claude-3-5-sonnet-20241022": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
    # Fallback / Default
    "default": {
        "input_per_million": 1.00,
        "output_per_million": 5.00,
    },
}


class CallMetrics(BaseModel):
    caller: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate exact USD cost for a model call."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    input_cost = (input_tokens / 1_000_000.0) * pricing["input_per_million"]
    output_cost = (output_tokens / 1_000_000.0) * pricing["output_per_million"]
    return round(input_cost + output_cost, 6)