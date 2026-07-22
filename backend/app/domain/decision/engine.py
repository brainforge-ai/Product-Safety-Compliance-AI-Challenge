"""Aggregates per-ingredient match results into a final Accept/Reject
decision, matching the challenge README's response contract
(ARCHITECTURE.md Section 10).
"""

from app.domain.matching.pipeline import MatchPipeline
from app.domain.models import EvaluationResult, ExtractedProduct


def decide(
    product: ExtractedProduct, forbidden_list: list[str], pipeline: MatchPipeline
) -> EvaluationResult:
    matches = [
        result
        for ingredient in product.ingredients
        if (result := pipeline.match_ingredient(ingredient, forbidden_list)) is not None
    ]

    if not matches:
        return EvaluationResult(product_name=product.product_name, status="Accepted")

    seen_reasons: set[str] = set()
    reasons = []
    for match in matches:
        reason = f"Contains {match.forbidden_ingredient}"
        if reason not in seen_reasons:
            seen_reasons.add(reason)
            reasons.append(reason)

    return EvaluationResult(
        product_name=product.product_name,
        status="Rejected",
        reason=reasons,
        matches=matches,
    )
