"""Core evaluation logic: extract -> parse -> match -> decide."""

import os
import re
import logging
from typing import List, Optional

from app.file_router import detect_file_type
from app.extractors.text_extractor import extract_from_text, extract_from_json, extract_from_docx
from app.extractors.pdf_extractor import extract_from_pdf
from app.extractors.image_extractor import extract_from_image
from app.extractors.csv_extractor import extract_from_csv, extract_from_excel
from app.ingredient_parser import parse_ingredients
from app.matching_engine import load_forbidden_ingredients, match_ingredients, visual_verify_image
from app.models import EvaluationResponse, ForbiddenMatch

logger = logging.getLogger(__name__)

_READABILITY_RE = re.compile(r"READABILITY:\s*(HIGH|MEDIUM|LOW)", re.IGNORECASE)

_EXTRACTORS = {
    "text": extract_from_text,
    "json": extract_from_json,
    "csv": extract_from_csv,
    "excel": extract_from_excel,
    "docx": extract_from_docx,
}

_JUNK_WORDS = {"unknown", "not found", "illegible", "n/a", "none", ""}
_NARRATIVE_PREFIXES = (
    "note:", "the handwritten", "the visible", "this image",
    "this appears", "looking at", "i can see", "the text",
    "the english", "the writing", "it appears", "this is",
)


def evaluate_product(
    file_path: str,
    forbidden_csv_path: str,
    extra_forbidden: Optional[List[str]] = None,
    source_filename: Optional[str] = None,
) -> EvaluationResponse:
    """Evaluate a single product file against the forbidden ingredients list.

    Args:
        file_path: Path to the product file (any supported format).
        forbidden_csv_path: Path to the base forbidden_ingredients.csv.
        extra_forbidden: Additional forbidden ingredients to merge in
                         (e.g. user-added via the UI).  These are combined
                         with the CSV list at runtime and do not modify the
                         original CSV file.
        source_filename: Original filename for display purposes. If not
                         provided, derived from file_path.
    """
    forbidden_list = load_forbidden_ingredients(forbidden_csv_path)
    if extra_forbidden:
        # Merge without duplicates (case-insensitive)
        existing_lower = {f.lower() for f in forbidden_list}
        for item in extra_forbidden:
            if item.lower() not in existing_lower:
                forbidden_list.append(item)
                existing_lower.add(item.lower())

    file_type = detect_file_type(file_path)

    # 1. Extraction
    raw_text = _extract(file_path, file_type)
    logger.info("Extracted %d chars from %s", len(raw_text), file_path)

    # 1b. Parse OCR readability indicator (images only)
    readability = "HIGH"
    if file_type == "image":
        m = _READABILITY_RE.search(raw_text)
        if m:
            readability = m.group(1).upper()
        logger.info("Image readability: %s", readability)

    # 2. Parsing
    product_id, product_name, ingredients = parse_ingredients(raw_text)
    if product_id and product_id.lower().strip() in _JUNK_WORDS:
        product_id = ""
    if not product_name or product_name.lower().strip() in _JUNK_WORDS:
        product_name = _name_from_filename(file_path)
    logger.info("Parsed %d ingredients for '%s'", len(ingredients), product_name)

    # 3. Matching (Tier 1: exact, Tier 2: normalized, Tier 3: LLM reasoning)
    matches, _safe = match_ingredients(ingredients, forbidden_list)

    # 4. Filter out junk / narrative text from ingredient list
    real_ingredients = [
        ing for ing in ingredients
        if ing.lower().strip() not in _JUNK_WORDS
        and not any(ing.lower().startswith(p) for p in _NARRATIVE_PREFIXES)
        and len(ing.strip()) > 2
    ]
    ingredients = real_ingredients
    low_confidence = file_type == "image" and len(real_ingredients) == 0

    # 5. Visual verification -- ALWAYS run for images as an independent check.
    #    OCR can hallucinate wrong ingredient names on blurry/low-contrast images,
    #    so we cannot rely solely on the OCR->parse->match pipeline.
    if file_type == "image":
        logger.info("Running visual verification on %s", file_path)
        visual_matches = visual_verify_image(file_path, forbidden_list)
        if visual_matches:
            already = {(m["ingredient"], m["matched_forbidden"]) for m in matches}
            for vm in visual_matches:
                if (vm["ingredient"], vm["matched_forbidden"]) not in already:
                    matches.append(vm)
            low_confidence = False
            logger.info("Visual verification caught %d forbidden matches", len(visual_matches))

    # 6. Decision
    if matches:
        status = "Rejected"
        reasons = [
            f"Contains {m.get('matched_forbidden', m['ingredient'])}"
            for m in matches
        ]
    elif low_confidence or (file_type == "image" and readability == "LOW" and not matches):
        status = "Needs Review"
        reasons = [
            "Image readability is low -- text is blurry, faded, or hard to read. "
            "OCR results may be unreliable. Please verify this product manually."
        ]
    else:
        status = "Accepted"
        reasons = []

    return EvaluationResponse(
        product_id=product_id or None,
        product_name=product_name,
        source_file=source_filename or os.path.basename(file_path),
        status=status,
        reason=reasons,
        raw_extracted_text=raw_text,
        ingredients_found=ingredients,
        forbidden_matches=[ForbiddenMatch(**m) for m in matches],
    )


def evaluate_batch(
    file_paths: List[str],
    forbidden_csv_path: str,
    extra_forbidden: Optional[List[str]] = None,
) -> List[EvaluationResponse]:
    """Evaluate a list of product files."""
    results = []
    for fp in file_paths:
        try:
            results.append(evaluate_product(fp, forbidden_csv_path, extra_forbidden))
        except Exception as exc:
            logger.exception("Error evaluating %s", fp)
            results.append(
                EvaluationResponse(
                    product_name=_name_from_filename(fp),
                    source_file=os.path.basename(fp),
                    status="Error",
                    reason=[str(exc)],
                )
            )
    return results


def extract_text_from_file(file_path: str) -> str:
    """Extract raw text from any supported file.  Used by the UI to parse
    uploaded files for additional forbidden ingredient names."""
    file_type = detect_file_type(file_path)
    return _extract(file_path, file_type)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract(file_path: str, file_type: str) -> str:
    """Dispatch to the correct extractor based on detected file type."""
    if file_type in _EXTRACTORS:
        return _EXTRACTORS[file_type](file_path)
    if file_type == "pdf":
        return extract_from_pdf(file_path)
    if file_type == "image":
        return extract_from_image(file_path)
    raise ValueError(f"No extractor for file type '{file_type}'")


def _name_from_filename(file_path: str) -> str:
    """Derive a human-readable product name from the filename."""
    base = os.path.splitext(os.path.basename(file_path))[0]
    name = base.split("_", 1)[-1] if "_" in base else base
    return name.replace("_", " ")
