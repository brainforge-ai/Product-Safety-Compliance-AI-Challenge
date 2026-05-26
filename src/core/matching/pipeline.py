"""
3-Layer Matching Pipeline

Layer A: Exact + Alias Matching (free, in-memory)
  - Normalized exact match
  - Pre-resolved synonym/alias matching

Layer B: PubChem CID Intersection (cached API calls, parallelized)
  - Resolve ingredient to CIDs
  - Check for overlap with forbidden CID set

Layer C: LLM Judge (GPT-4o, batch call)
  - Final arbiter for unresolved ingredients
  - Only called for ingredients that fail A and B
"""
from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional

from src.core.models import (
    EvaluationResult,
    IngredientKind,
    MatchHit,
    MatchLayer,
    MatchTrace,
    ProductExtraction,
    ProductStatus,
)
from src.core.matching.forbidden import ForbiddenIndex
from src.core.matching.normalize import classify, to_hill
from src.core.matching.pubchem import PubChemClient
from src.core.matching.llm_judge import judge_ingredients

logger = logging.getLogger(__name__)


class MatchPipeline:
    """
    3-layer matching pipeline for ingredient safety evaluation.

    Layers are processed in order, with short-circuiting:
    - If Layer A finds a match, skip B and C for that ingredient
    - If Layer B finds a match, skip C for that ingredient
    - Layer C processes all remaining unresolved ingredients in a single batch
    """

    def __init__(
        self,
        forbidden_index: ForbiddenIndex,
        pubchem_client: PubChemClient,
    ):
        self.forbidden = forbidden_index
        self.pubchem = pubchem_client

    async def _resolve_cids(
        self, ingredient: str
    ) -> tuple[str, list[int], Optional[Exception]]:
        """Resolve an ingredient to CIDs. Returns (ingredient, cids, error)."""
        try:
            kind = classify(ingredient)
            if kind == IngredientKind.FORMULA:
                normalized = to_hill(ingredient)
                cids = await self.pubchem.get_cids_by_formula(normalized)
            else:
                cids = await self.pubchem.get_cids_by_name(ingredient)
            return ingredient, cids, None
        except Exception as e:
            return ingredient, [], e

    async def evaluate(
        self,
        extraction: ProductExtraction,
        filename: str,
    ) -> EvaluationResult:
        """
        Evaluate a product's ingredients against the forbidden list.

        Args:
            extraction: Extracted product data
            filename: Original filename for logging

        Returns:
            Complete evaluation result with match details
        """
        start_time = time.time()
        trace = MatchTrace()
        hits: list[MatchHit] = []
        layer_b_candidates: list[str] = []

        logger.info(
            f"Evaluating {extraction.product_name}: "
            f"{len(extraction.ingredients)} ingredients"
        )

        # === LAYER A: Combined Exact + Alias Matching ===
        for ingredient in extraction.ingredients:
            trace.layer_a_checks += 1

            layer_a_match = self.forbidden.match_layer_a(ingredient)
            if layer_a_match:
                trace.layer_a_hits += 1
                hits.append(MatchHit(
                    ingredient=ingredient,
                    forbidden_match=layer_a_match.forbidden_raw,
                    layer=layer_a_match.layer,
                    confidence=1.0 if layer_a_match.layer.value == "A_exact" else 0.98,
                ))
                logger.debug(
                    f"Layer A: '{ingredient}' -> '{layer_a_match.forbidden_raw}' "
                    f"({layer_a_match.layer.value})"
                )
            else:
                # No Layer A match - candidate for Layer B
                layer_b_candidates.append(ingredient)

        # === LAYER B: PubChem CID Intersection (parallelized) ===
        unresolved: list[str] = []

        if layer_b_candidates:
            trace.layer_b_checks = len(layer_b_candidates)

            # Parallelize CID lookups using asyncio.gather
            cid_tasks = [self._resolve_cids(ing) for ing in layer_b_candidates]
            cid_results = await asyncio.gather(*cid_tasks)
            trace.pubchem_calls = len(layer_b_candidates)

            for ingredient, cids, error in cid_results:
                if error:
                    logger.warning(f"Layer B failed for '{ingredient}': {error}")
                    trace.layer_b_errors += 1
                    unresolved.append(ingredient)
                    continue

                if cids:
                    cid_match = self.forbidden.cid_overlap(cids)
                    if cid_match:
                        trace.layer_b_hits += 1
                        hits.append(MatchHit(
                            ingredient=ingredient,
                            forbidden_match=cid_match,
                            layer=MatchLayer.B_PUBCHEM,
                            confidence=0.95,
                            cid=cids[0],
                        ))
                        logger.debug(
                            f"Layer B CID: '{ingredient}' (CID {cids[0]}) -> '{cid_match}'"
                        )
                        continue

                # No CID match - add to unresolved for Layer C
                unresolved.append(ingredient)

        # === LAYER C: LLM Judge (batch call for all unresolved) ===
        if unresolved:
            trace.layer_c_checks = len(unresolved)
            trace.llm_calls += 1

            logger.info(f"Layer C: Judging {len(unresolved)} unresolved ingredients")

            llm_hits = await judge_ingredients(
                ingredients=unresolved,
                forbidden_list=self.forbidden.get_all_raw_entries(),
            )

            trace.layer_c_hits = len(llm_hits)
            hits.extend(llm_hits)

            for hit in llm_hits:
                logger.debug(
                    f"Layer C LLM: '{hit.ingredient}' -> '{hit.forbidden_match}' "
                    f"(confidence: {hit.confidence})"
                )

        # Build final result
        duration_ms = (time.time() - start_time) * 1000

        result = EvaluationResult(
            product_id=extraction.product_id,
            product_name=extraction.product_name,
            filename=filename,
            status=ProductStatus.REJECTED if hits else ProductStatus.ACCEPTED,
            reason=[f"Contains {hit.ingredient} (matches {hit.forbidden_match})" for hit in hits],
            hits=hits,
            ingredients_detected=extraction.ingredients,
            trace=trace,
            extraction_method=extraction.extraction_method,
            duration_ms=duration_ms,
        )

        logger.info(
            f"Result: {result.status.value} | "
            f"{len(hits)} hits | "
            f"{duration_ms:.1f}ms | "
            f"Layers: A={trace.layer_a_hits}, B={trace.layer_b_hits}, C={trace.layer_c_hits}"
        )

        return result
