"""Pipeline orchestration for product safety checks."""

import re

from .ingestion.file_loader import load_file
from .extraction.ingredient_parser import extract_ingredients, extract_product_name
from .extraction.normalizer import normalize
from .matching.embedding_matcher import embedding_match, should_skip_ingredient
from .decision.decision_engine import make_decision
from .config import expand_forbidden_synonyms
from .reasoning.llm_reasoner import llm_reason
from .logger import logger

# Drop these if they appear in the API-provided forbidden list (CSV headers / risk levels).
FORBIDDEN_LIST_SKIP = frozenset({"ingredient", "ingredients", "cas_number", "risk_level", "high", "medium", "low"})
CAS_ONLY = re.compile(r"^\d{2,7}-\d{2}-\d$")


def _clean_forbidden_list(names):
    """Remove CSV headers, risk levels, and CAS-only entries from the forbidden list."""
    if not names:
        return []
    out = []
    for n in names:
        s = (n or "").strip()
        if not s:
            continue
        if s.lower() in FORBIDDEN_LIST_SKIP:
            continue
        if CAS_ONLY.match(s):
            continue
        out.append(s)
    return out  # For fallback extraction


def _expand_candidate_ingredients(ingredients, normalized_ingredients, forbidden_list):
    """Expand OCR ingredient blocks into candidate phrases for matching.

    EasyOCR often returns one long whitespace-separated ingredient line for images.
    This helper preserves exact extracted items and also creates contiguous phrase windows
    so multi-word forbidden ingredients like "sodium lauryl sulfate" can still match.
    """
    expanded_original = []
    expanded_normalized = []

    max_forbidden_tokens = 1
    if forbidden_list:
        max_forbidden_tokens = max(
            1,
            max(len((item or "").split()) for item in forbidden_list if (item or "").strip()),
        )

    seen = set()
    for original, normalized in zip(ingredients, normalized_ingredients):
        if not original or not normalized:
            continue

        base_key = normalized.strip().lower()
        if base_key and base_key not in seen:
            expanded_original.append(original)
            expanded_normalized.append(normalized)
            seen.add(base_key)

        tokens = [token for token in normalized.split() if token]
        if len(tokens) <= 1:
            continue

        for window in range(1, min(max_forbidden_tokens, len(tokens)) + 1):
            for start in range(0, len(tokens) - window + 1):
                phrase = " ".join(tokens[start:start + window]).strip()
                if not phrase:
                    continue
                phrase_key = phrase.lower()
                if phrase_key in seen:
                    continue
                expanded_original.append(phrase)
                expanded_normalized.append(phrase)
                seen.add(phrase_key)

    return expanded_original, expanded_normalized


def run_pipeline(file_path: str, custom_forbidden: list = None) -> dict:
    """
    End-to-end pipeline for a single product file.

    Args:
        file_path: Path to the product file.
        custom_forbidden: Optional list of custom forbidden ingredients.

    Returns a dict so it can be returned directly from FastAPI as JSON.
    """
    try:
        logger.info("Pipeline started for file_path=%s", file_path)
        raw_text = load_file(file_path)
        product_name = extract_product_name(raw_text)
        ingredients = extract_ingredients(raw_text)
        logger.info("Raw OCR ingredient text for file_path=%s: %s", file_path, raw_text[:1000])
        logger.info("Extracted ingredient tokens for file_path=%s: %s", file_path, ingredients)
        
        # Fallback to LLM if regex extraction fails
        if not ingredients:
            try:
                llm_response = llm_reason(raw_text)
                # Parse LLM response to extract ingredients (simple split or regex)
                ingredients = [ing.strip() for ing in llm_response.split(',') if ing.strip()]
            except Exception as e:
                logger.warning("LLM fallback failed for file_path=%s: %s", file_path, e)
                ingredients = []  # If LLM fails, proceed with empty
        
        normalized_ingredients = [normalize(i) for i in ingredients if i]
        logger.info("Normalized ingredient text for file_path=%s: %s", file_path, normalized_ingredients)
        
        # Forbidden list must be provided dynamically by the API/UI request.
        if not custom_forbidden:
            raise ValueError("forbidden_list is required and must be provided in the request")

        cleaned = _clean_forbidden_list(custom_forbidden)
        forbidden_list, term_to_canonical = expand_forbidden_synonyms(cleaned)
        logger.info("Forbidden list received from request for file_path=%s: %s", file_path, cleaned)
        forbidden_set = {t.strip().lower() for t in forbidden_list}
        logger.info("Expanded forbidden list for file_path=%s: %s", file_path, forbidden_list[:100])

        ingredients, normalized_ingredients = _expand_candidate_ingredients(
            ingredients, normalized_ingredients, forbidden_list
        )
        logger.info("Expanded candidate ingredient phrases for file_path=%s: %s", file_path, normalized_ingredients)
        
        # Filter OCR tokens (short, CAS, noise), but keep tokens that are in the user's forbidden list (e.g. water).
        filtered_ingredients = []
        filtered_normalized = []
        for ing, norm in zip(ingredients, normalized_ingredients):
            if not ing or not norm:
                continue
            norm_lower = norm.strip().lower()
            keep = (not should_skip_ingredient(norm)) or (norm_lower in forbidden_set)
            if keep:
                filtered_ingredients.append(ing)
                filtered_normalized.append(norm)
        
        # Each ingredient matches only the single best forbidden; return canonical name only.
        raw_matches = embedding_match(
            filtered_normalized, forbidden_list, term_to_canonical, forbidden_set=forbidden_set
        )
        # Dedupe by canonical (one line per forbidden ingredient), keep best score.
        canonical_best = {}
        for i, canonical, score in raw_matches:
            c = (canonical or "").strip().lower()
            if c and (c not in canonical_best or score > canonical_best[c][1]):
                canonical_best[c] = (canonical, score)
        forbidden_matches = list(canonical_best.values())
        logger.info("Detected forbidden chemicals for file_path=%s: %s", file_path, forbidden_matches)
        status, reason, confidence = make_decision(forbidden_matches)

        logger.info(
            "Pipeline completed for file_path=%s status=%s matches=%s",
            file_path,
            status,
            len(forbidden_matches),
        )

        return {
            "product_name": str(product_name),
            "status": str(status),
            "reason": [str(r) for r in reason],
            "confidence": float(confidence),
        }
    except Exception as e:
        logger.exception("Pipeline failed for file_path=%s", file_path)
        return {
            "product_name": "Error",
            "status": "Error",
            "reason": [f"Processing failed: {str(e)}"],
            "confidence": 0.0,
        }
