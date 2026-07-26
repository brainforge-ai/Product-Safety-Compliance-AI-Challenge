"""Token-usage/cost accounting shared by the Pydantic AI adapters in this
package.

Cost lookup uses `genai-prices` (already a transitive dependency of
`pydantic-ai`, and a maintained pricing database covering Gemini/OpenAI/
Anthropic/etc. model rates) rather than a hand-maintained price table, so it
tracks provider pricing changes automatically. If a model isn't in that
database, or the lookup fails for any reason, pricing fields are left None
rather than reporting a guessed number -- this must never break a real
answer just because cost reporting failed.
"""

import logging

from pydantic_ai.usage import RunUsage

from app.domain.models import LlmUsage

logger = logging.getLogger(__name__)


def usage_from_run(run_usage: RunUsage, model_ref: str) -> LlmUsage:
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
