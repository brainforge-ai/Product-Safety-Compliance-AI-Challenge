"""Token usage and cost accounting for Pydantic AI adapters."""

import logging

from pydantic_ai.usage import RunUsage

from app.domain.models import LlmUsage

logger = logging.getLogger(__name__)


def usage_from_run(run_usage: RunUsage, model_ref: str) -> LlmUsage:
    """Convert Pydantic AI run usage into domain usage with optional cost."""
    input_cost: float | None = None
    output_cost: float | None = None
    total_cost: float | None = None

    try:
        import genai_prices

        price = genai_prices.calc_price(run_usage, model_ref, provider_id="google")
        input_cost = float(price.input_price)
        output_cost = float(price.output_price)
        total_cost = float(price.total_price)
    except Exception as exc:  # noqa: BLE001 - cost reporting is best-effort
        logger.warning("Could not price LLM usage for model %r: %s", model_ref, exc)

    return LlmUsage(
        input_tokens=run_usage.input_tokens,
        output_tokens=run_usage.output_tokens,
        total_tokens=run_usage.total_tokens,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        estimated_cost_usd=total_cost,
    )
