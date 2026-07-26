"""Aggregates per-ingredient match results into a final Accept/Reject
decision, matching the challenge README's response contract
(ARCHITECTURE.md Section 10).
"""

from app.domain.matching.pipeline import MatchPipeline
from app.domain.models import EvaluationResult, ExtractedProduct, LlmUsage, MatchResult


def _combine_usage(a: LlmUsage | None, b: LlmUsage | None) -> LlmUsage | None:
    """Sum token usage/cost across two LLM calls for the same product (e.g.
    the extraction fallback and tier 6 matching, if both ran). Missing cost
    on one side is treated as 0 rather than making the total None, so a
    partial pricing lookup failure doesn't hide the other call's real cost.
    """
    if a is None:
        return b
    if b is None:
        return a

    def _sum(x: float | None, y: float | None) -> float | None:
        if x is None and y is None:
            return None
        return (x or 0.0) + (y or 0.0)

    return LlmUsage(
        input_tokens=a.input_tokens + b.input_tokens,
        output_tokens=a.output_tokens + b.output_tokens,
        total_tokens=a.total_tokens + b.total_tokens,
        input_cost_usd=_sum(a.input_cost_usd, b.input_cost_usd),
        output_cost_usd=_sum(a.output_cost_usd, b.output_cost_usd),
        estimated_cost_usd=_sum(a.estimated_cost_usd, b.estimated_cost_usd),
    )


def _build_result(
    product_name: str, matches: list[MatchResult], llm_usage: LlmUsage | None = None
) -> EvaluationResult:
    if not matches:
        return EvaluationResult(product_name=product_name, status="Accepted", llm_usage=llm_usage)

    seen_reasons: set[str] = set()
    reasons = []
    for match in matches:
        reason = f"Contains {match.forbidden_ingredient}"
        if reason not in seen_reasons:
            seen_reasons.add(reason)
            reasons.append(reason)

    return EvaluationResult(
        product_name=product_name,
        status="Rejected",
        reason=reasons,
        matches=matches,
        llm_usage=llm_usage,
    )


def decide(
    product: ExtractedProduct, forbidden_list: list[str], pipeline: MatchPipeline
) -> EvaluationResult:
    matches = [
        result
        for ingredient in product.ingredients
        if (result := pipeline.match_ingredient(ingredient, forbidden_list)) is not None
    ]
    return _build_result(product.product_name, matches)


def unresolved_ingredients(product: ExtractedProduct, result: EvaluationResult) -> list[str]:
    """Ingredients from `product` that `result` has no match for -- the
    candidates for tier 6's LLM pass. Relies on every matcher setting
    `matched_text` to the ingredient string verbatim (true of all of tiers
    1-5 today); if a future matcher normalizes `matched_text` instead, this
    comparison needs to change with it.
    """
    matched_texts = {match.matched_text for match in result.matches}
    return [ingredient for ingredient in product.ingredients if ingredient not in matched_texts]


def merge_llm_matches(
    result: EvaluationResult,
    llm_matches: list[MatchResult],
    usage: LlmUsage | None = None,
) -> EvaluationResult:
    """Fold an LLM call's additional matches (if any) and usage/cost (if any)
    into an already-decided result, rebuilding the Accept/Reject status and
    `reason` list the same way `decide` does. Called for both the extraction
    fallback (llm_matches always `[]`, since it only recovers ingredients,
    not matches) and tier 6 matching -- `usage` accumulates across both if a
    product goes through them in sequence. A true no-op only when there is
    neither a new match nor new usage to record.
    """
    combined_usage = _combine_usage(result.llm_usage, usage)
    if not llm_matches:
        if combined_usage is result.llm_usage:
            return result
        return result.model_copy(update={"llm_usage": combined_usage})
    return _build_result(result.product_name, result.matches + llm_matches, combined_usage)
