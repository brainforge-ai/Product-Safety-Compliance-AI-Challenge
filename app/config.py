"""Application configuration."""

import os
import re
import pubchempy as pcp

from .logger import logger
from .extraction.normalizer import get_pubchem_synonyms, normalize, normalize_formula, resolve_chemical_name

# Max synonyms per ingredient when expanding (e.g. "Glucose" -> "D-Glucopyranose")
MAX_SYNONYMS_PER_INGREDIENT = 15
ENABLE_PUBCHEM_SYNONYMS = os.getenv("ENABLE_PUBCHEM_SYNONYMS", "1") == "1"

# CAS number pattern (e.g. 123-31-9); used to resolve to ingredient name for display.
CAS_PATTERN = re.compile(r"^\d{1,7}-\d{2}-\d$")


def _canonical_display_name(term: str) -> str:
    """Return a display name for the forbidden ingredient; resolve CAS to name when possible."""
    term = (term or "").strip().lower()
    if not term:
        return term
    resolved_term = resolve_chemical_name(term)
    if resolved_term and resolved_term.lower() != term.lower():
        return normalize(resolved_term)
    if not ENABLE_PUBCHEM_SYNONYMS:
        return term
    if CAS_PATTERN.match(term):
        try:
            compounds = pcp.get_compounds(term, "cas")
            if compounds and (getattr(compounds[0], "synonyms", None) or getattr(compounds[0], "iupac_name", None)):
                c = compounds[0]
                if getattr(c, "iupac_name", None):
                    return (c.iupac_name or term).strip().lower()
                syns = getattr(c, "synonyms", None)
                if syns:
                    return syns[0].strip().lower()
        except Exception:
            logger.warning("PubChem CAS resolution failed for term=%s", term, exc_info=True)
    return term


def expand_forbidden_synonyms(ingredient_names: list) -> tuple:
    """
    Expand a list of ingredient names with PubChem synonyms for better matching.
    Returns (expanded_list, term_to_canonical) so we can report the detected ingredient
    and map it to the canonical forbidden name (always a name, not a CAS number).
    """
    if not ingredient_names:
        return [], {}
    raw_list = [n.strip().lower() for n in ingredient_names if n and str(n).strip()]
    # Use display name (resolve CAS to name) so reasons show "Hydroquinone" not "123-31-9".
    canonical_list = [_canonical_display_name(n) or n for n in raw_list]
    expanded = set(canonical_list) | set(raw_list)
    term_to_canonical = {}
    for raw, canonical in zip(raw_list, canonical_list):
        term_to_canonical[raw] = canonical
        term_to_canonical[canonical] = canonical
        normalized_raw = normalize(raw)
        normalized_canonical = normalize(canonical)
        if normalized_raw:
            expanded.add(normalized_raw)
            term_to_canonical[normalized_raw] = canonical
        if normalized_canonical:
            expanded.add(normalized_canonical)
            term_to_canonical[normalized_canonical] = canonical
    if not ENABLE_PUBCHEM_SYNONYMS:
        return list(expanded), term_to_canonical
    for name in canonical_list:
        try:
            synonyms = get_pubchem_synonyms(name)[:MAX_SYNONYMS_PER_INGREDIENT]
            for synonym in synonyms:
                for term in {synonym, normalize(synonym), normalize_formula(synonym)}:
                    if term:
                        expanded.add(term)
                        term_to_canonical[term] = name
        except Exception:
            logger.warning("PubChem synonym expansion failed for name=%s", name, exc_info=True)
    return list(expanded), term_to_canonical

# Forbidden list is supplied only via the API/UI request. No default list is loaded from the repo.
FORBIDDEN_INGREDIENTS = []
FORBIDDEN_TERM_TO_CANONICAL = {}
