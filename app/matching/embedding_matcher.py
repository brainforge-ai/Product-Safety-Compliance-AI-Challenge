"""Embedding-based matching utilities."""

import os
import re
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer
import numpy as np
from ..reasoning.llm_reasoner import llm_reason
from ..extraction.normalizer import normalize, normalize_formula

# Lazy-loaded model to avoid import-time loading issues
model = None

# Only accept a match when similarity is above this threshold (avoids false positives).
SIMILARITY_THRESHOLD = 0.85

# CAS number pattern: do not treat as ingredient or show in output (e.g. 123-31-9).
CAS_PATTERN = re.compile(r"^\d{2,7}-\d{2}-\d$")

# Normalized (lowercase) tokens that are noise and must not be matched or reported.
NOISE_INGREDIENTS = frozenset({
    "aqua", "water", "parfum", "fragrance", "denat", "ci", "perfume", "aroma",
    "color", "colour", "parfum fragrance", "alcohol", "citric",
    "edta", "edetate", "ethylenediaminetetraacetic", "disodium edta", "tetrasodium edta",
})

# Minimum length for an ingredient token (filter OCR junk like "ci", "ed").
MIN_INGREDIENT_LENGTH = 3
FUZZY_MATCH_THRESHOLD = 90


def _tokenize_for_match(text: str) -> set[str]:
    """Tokenize normalized ingredient text for overlap validation."""
    normalized = normalize(text)
    if not normalized:
        return set()
    return {
        token
        for token in normalized.split()
        if len(token) >= 3 and not token.isdigit() and token not in NOISE_INGREDIENTS
    }


def _has_token_overlap(left: str, right: str) -> bool:
    """Require some lexical overlap before accepting embedding fallback matches."""
    left_tokens = _tokenize_for_match(left)
    right_tokens = _tokenize_for_match(right)
    if not left_tokens or not right_tokens:
        return False
    return bool(left_tokens & right_tokens)


def _exact_or_synonym_match(ingredient: str, forbidden: list[str], term_to_canonical: dict[str, str]):
    """Return canonical name when the ingredient exactly matches a forbidden term/synonym."""
    normalized_ingredient = normalize(ingredient)
    formula_ingredient = normalize_formula(ingredient)
    for candidate in {ingredient.strip().lower(), normalized_ingredient, formula_ingredient}:
        if candidate and candidate in term_to_canonical:
            return term_to_canonical[candidate]
    for forbidden_item in forbidden:
        if normalized_ingredient == normalize(forbidden_item):
            return term_to_canonical.get(forbidden_item, forbidden_item)
        if formula_ingredient and formula_ingredient == normalize_formula(forbidden_item):
            return term_to_canonical.get(forbidden_item, forbidden_item)
    return None


def _formula_equivalent(left: str, right: str) -> bool:
    """Return True when two terms are the same chemical formula after normalization."""
    left_formula = normalize_formula(left)
    right_formula = normalize_formula(right)
    if not left_formula or not right_formula:
        return False
    formula_pattern = re.compile(r"^(?=.*[a-z])(?=.*\d)[a-z0-9]+$")
    return bool(formula_pattern.match(left_formula) and left_formula == right_formula)


def _fuzzy_equivalent(left: str, right: str) -> bool:
    """Return True for close spelling variations after normalization."""
    left_norm = normalize(left)
    right_norm = normalize(right)
    if not left_norm or not right_norm:
        return False
    token_score = fuzz.token_sort_ratio(left_norm, right_norm)
    if _has_token_overlap(left_norm, right_norm):
        return token_score >= FUZZY_MATCH_THRESHOLD

    left_tokens = left_norm.split()
    right_tokens = right_norm.split()
    if len(left_tokens) == 1 and len(right_tokens) == 1:
        compact_left = left_tokens[0]
        compact_right = right_tokens[0]
        ratio_score = fuzz.ratio(compact_left, compact_right)
        return (
            ratio_score >= FUZZY_MATCH_THRESHOLD
            and compact_left[:4] == compact_right[:4]
            and compact_left[-4:] == compact_right[-4:]
        )

    return False


def get_model():
    """Lazy load the sentence transformer model."""
    global model
    if model is None:
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return model


# Cache for forbidden embeddings
_forbidden_cache = {}


def get_forbidden_embeddings(forbidden):
    """
    Get cached embeddings for forbidden list.
    """
    key = tuple(sorted(forbidden))
    if key not in _forbidden_cache:
        _forbidden_cache[key] = get_model().encode(forbidden)
    return _forbidden_cache[key]


def _is_noise(normalized_ingredient: str) -> bool:
    """True if this normalized ingredient is noise (aqua, parfum, denat, etc.) and should not be reported."""
    if not normalized_ingredient or not normalized_ingredient.strip():
        return True
    return normalized_ingredient.strip().lower() in NOISE_INGREDIENTS


def should_skip_ingredient(normalized_ingredient: str) -> bool:
    """
    True if this token should be skipped: too short, CAS number, or noise.
    Used to filter OCR junk before matching.
    """
    s = (normalized_ingredient or "").strip().lower()
    if not s or len(s) < MIN_INGREDIENT_LENGTH:
        return True
    if CAS_PATTERN.match(s):
        return True
    return s in NOISE_INGREDIENTS


def llm_validate_match(ingredient, forbidden_item):
    """
    Use LLM to validate if the ingredient contains or is related to the forbidden item.
    When LLM is disabled or fails, returns False so we rely on embedding similarity only.
    """
    if os.getenv("ENABLE_LLM_REASONING", "0") != "1":
        return False
    prompt = f"Does the ingredient '{ingredient}' contain or is it the same as '{forbidden_item}'? Answer with 'yes' or 'no'."
    try:
        response = llm_reason(prompt).strip().lower()
        return "yes" in response
    except Exception:
        return False


def embedding_match(ingredients, forbidden, term_to_canonical=None, forbidden_set=None):
    """
    For each extracted ingredient, find ONLY the best forbidden match (one-to-one).
    Accept only if similarity > SIMILARITY_THRESHOLD. Skip noise (aqua, parfum, etc.) unless
    the ingredient is in forbidden_set (e.g. user added "water" to forbidden list).
    Returns list of (ingredient_index, canonical_forbidden_name, score); each ingredient at most once.
    """
    if not ingredients or not forbidden:
        return []
    if term_to_canonical is None:
        term_to_canonical = {t: t for t in forbidden}
    forbidden_set = forbidden_set or frozenset()

    normalized_forbidden_map = {}
    formula_forbidden_map = {}
    for forbidden_item in forbidden:
        canonical = term_to_canonical.get(forbidden_item, forbidden_item)
        raw_key = (forbidden_item or "").strip().lower()
        norm_key = normalize(forbidden_item)
        formula_key = normalize_formula(forbidden_item)
        for key in {raw_key, norm_key}:
            if key:
                normalized_forbidden_map[key] = canonical
        if formula_key:
            formula_forbidden_map[formula_key] = canonical

    embeddings1 = get_model().encode(ingredients)
    embeddings2 = get_forbidden_embeddings(forbidden)

    matches = []
    for i, e1 in enumerate(embeddings1):
        raw_lower = (ingredients[i] or "").strip().lower()
        norm_lower = normalize(ingredients[i])
        formula_lower = normalize_formula(ingredients[i])
        if should_skip_ingredient(ingredients[i]) and norm_lower not in forbidden_set and formula_lower not in forbidden_set:
            continue

        exact_canonical = None
        for key, lookup in (
            (raw_lower, normalized_forbidden_map),
            (norm_lower, normalized_forbidden_map),
            (formula_lower, formula_forbidden_map),
        ):
            if key and key in lookup:
                exact_canonical = lookup[key]
                break
        if exact_canonical:
            matches.append((i, exact_canonical, 1.0))
            continue

        canonical = _exact_or_synonym_match(ingredients[i], forbidden, term_to_canonical)
        if canonical:
            matches.append((i, canonical, 1.0))
            continue

        direct_match = None
        for forbidden_item in forbidden:
            if _formula_equivalent(ingredients[i], forbidden_item) or _fuzzy_equivalent(ingredients[i], forbidden_item):
                canonical = term_to_canonical.get(forbidden_item, forbidden_item)
                direct_match = (i, canonical, 0.95)
                break
        if direct_match is not None:
            matches.append(direct_match)
            continue

        best_j = None
        best_sim = -1.0
        for j, e2 in enumerate(embeddings2):
            sim = np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2))
            if sim > best_sim:
                best_sim = sim
                best_j = j
        if best_j is not None and float(best_sim) > SIMILARITY_THRESHOLD:
            if not _has_token_overlap(ingredients[i], forbidden[best_j]):
                continue
            canonical = term_to_canonical.get(forbidden[best_j], forbidden[best_j])
            score = round(float(best_sim), 2)
            if score > 0.8 and llm_validate_match(ingredients[i], forbidden[best_j]):
                score = min(score + 0.1, 1.0)
            matches.append((i, canonical, score))

    return matches
