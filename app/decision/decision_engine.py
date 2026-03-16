"""Decision engine for product safety outcomes."""

import re

# CAS numbers (e.g. 123-31-9) must not appear in reason text.
_CAS_PATTERN = re.compile(r"^\d{2,7}-\d{2}-\d$")


def _format_canonical(name: str) -> str:
    """Title-case for display (e.g. 'hydroquinone' -> 'Hydroquinone')."""
    return name.strip().title() if name else name


def make_decision(forbidden_matches):
    """
    Determine if a product is Accepted or Rejected based on forbidden matches.
    Returns only canonical forbidden ingredient names (no OCR text, no synonyms, no CAS).

    Args:
        forbidden_matches: List of (canonical_forbidden_name, confidence_score).

    Returns:
        status: "Accepted" or "Rejected"
        reason: Sorted, deduplicated list, e.g. ["Contains Hydroquinone", "Contains Methylparaben"]
        confidence: Average confidence score of matches, or 1.0 if accepted
    """
    if not forbidden_matches:
        return "Accepted", [], 1.0

    reasons = []
    for canonical, score in forbidden_matches:
        if not canonical or _CAS_PATTERN.match((canonical or "").strip()):
            continue
        reasons.append(f"Contains {_format_canonical(canonical)}")

    reasons = sorted(set(reasons))
    avg_confidence = sum(float(s) for _, s in forbidden_matches) / len(forbidden_matches)
    return "Rejected", reasons, float(round(avg_confidence, 2))
