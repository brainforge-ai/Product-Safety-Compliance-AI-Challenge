"""Aggregates per-ingredient match results into a final Accept/Reject
decision, matching the challenge README's response contract
(ARCHITECTURE.md Section 10).
"""

from app.domain.matching.pipeline import MatchPipeline
from app.domain.models import EvaluationResult, ExtractedProduct, MatchResult


def _build_result(product_name: str, matches: list[MatchResult]) -> EvaluationResult:
    if not matches:
        return EvaluationResult(product_name=product_name, status="Accepted")

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


def merge_llm_matches(result: EvaluationResult, llm_matches: list[MatchResult]) -> EvaluationResult:
    """Fold tier 6's additional matches into an already-decided result,
    rebuilding the Accept/Reject status and `reason` list the same way
    `decide` does. A no-op if the LLM tier found nothing.
    """
    if not llm_matches:
        return result
    return _build_result(result.product_name, result.matches + llm_matches)
