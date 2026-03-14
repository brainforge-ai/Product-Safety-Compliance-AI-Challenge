"""3-tier ingredient matching engine + visual verification safety net.

Tier 1: Exact case-insensitive match (free, instant)
Tier 2: Normalized match -- strip whitespace, hyphens, special chars (free, instant)
Tier 3: LLM chemical reasoning via Claude (handles synonyms, formulas,
         IUPAC names, trade names, multilingual names, and OCR misreads)
Visual Verify: Send the raw image + forbidden list to Claude for a direct check
               (only used for image inputs when Tiers 1-3 find nothing)

Prompt caching: Tier 3 and Visual Verify use Anthropic's prompt caching.
The system prompt + forbidden list form a cached prefix.  Within a batch,
the first call writes the cache; subsequent calls read from it at 90%
lower input cost.  When the forbidden list changes (user adds/removes),
the cache auto-invalidates and is re-created.

The forbidden ingredients list is NEVER hardcoded.  It is loaded dynamically
from whichever CSV the caller provides, and can be swapped at runtime via
the API or the Streamlit UI.
"""

import re
import json
import base64
import logging
from typing import List, Tuple, Dict

import anthropic
from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Load forbidden ingredients  (dynamic -- never hardcoded)
# ---------------------------------------------------------------------------

def load_forbidden_ingredients(csv_path: str) -> List[str]:
    """Read forbidden ingredients from a CSV file at runtime."""
    ingredients: List[str] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0:
                continue  # skip header
            val = line.strip().strip('"').strip("'")
            if val:
                ingredients.append(val)
    return ingredients


# ---------------------------------------------------------------------------
# Tier 1 -- Exact (case-insensitive) match
# ---------------------------------------------------------------------------

def tier1_exact_match(ingredient: str, forbidden: List[str]) -> str | None:
    """Return the forbidden ingredient if there is a case-insensitive exact match."""
    lowered = ingredient.lower().strip()
    for f in forbidden:
        if lowered == f.lower().strip():
            return f
    return None


# ---------------------------------------------------------------------------
# Tier 2 -- Normalized match (strip whitespace, hyphens, special chars)
# ---------------------------------------------------------------------------

_NORM_RE = re.compile(r"[\s\-_.,;:()\[\]]+")


def _normalize(s: str) -> str:
    """Strip whitespace, hyphens, and special characters, then lowercase."""
    return _NORM_RE.sub("", s).lower()


def tier2_normalized_match(ingredient: str, forbidden: List[str]) -> str | None:
    """Return the forbidden ingredient if normalized forms match."""
    n = _normalize(ingredient)
    for f in forbidden:
        if n == _normalize(f):
            return f
    return None


# ---------------------------------------------------------------------------
# Tier 3 -- LLM chemical-reasoning match (Claude) with prompt caching
# ---------------------------------------------------------------------------

# System prompt: static instructions (cached together with the forbidden list)
_LLM_SYSTEM = """\
You are a chemical safety expert fluent in ALL languages.

Your task: for each extracted ingredient, determine if it is chemically \
identical to ANY forbidden ingredient.

These ingredients may come from OCR and could contain minor errors. However, \
you must apply STRICT chemical accuracy -- do NOT flag ingredients that are \
genuinely different chemicals.

STRICT RULES FOR CHEMICAL FORMULAS:
- Each molecular formula represents a SPECIFIC chemical. Different formulas \
  mean different chemicals, even if they look similar as text strings.
- C6H12O6 (glucose) is NOT C6H6 (benzene). Do NOT do substring matching \
  on formulas. The ENTIRE formula must match.
- C12H2O2 is NOT Cl2H2O2. "C12" means 12 carbon atoms; "Cl2" means 2 \
  chlorine atoms. These are different elements, different chemicals.
- H2O2 (hydrogen peroxide) is NOT H2O (water). Every atom and count matters.
- Only flag a formula if the COMPLETE formula matches a forbidden one, or \
  if you are certain it is the SAME compound written differently.

MATCHING CRITERIA:
- Chemical formula <-> common name (e.g., C6H6 = Benzene, CH2O = Formaldehyde)
- IUPAC names, systematic names, trade names
- Synonyms and abbreviations
- Names in ANY language or script (phonetic transliterations, CJK, etc.)
- CAS names, E-numbers, pharmaceutical names

IMPORTANT -- AVOID FALSE POSITIVES:
- When in doubt, mark as NOT forbidden. A false positive (wrongly rejecting \
  a safe product) is worse than a false negative.
- Do NOT match by substring, partial overlap, or superficial text similarity.
- Only flag TRUE chemical identity matches.

Return ONLY a JSON array (no markdown, no explanation outside the JSON):
[
  {
    "ingredient": "<extracted name>",
    "is_forbidden": true/false,
    "matched_forbidden": "<forbidden ingredient it matches>" or null,
    "explanation": "<brief reason>"
  }
]"""


def tier3_llm_match(
    ingredients: List[str],
    forbidden: List[str],
) -> List[Dict]:
    """Use Claude LLM to reason about chemical identity matches.

    Prompt caching: the system prompt + forbidden list are cached.
    Only the ingredients-to-check vary per call.
    """
    if not ingredients:
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # System = static instructions + forbidden list (cached together)
    system_text = f"{_LLM_SYSTEM}\n\nFORBIDDEN INGREDIENTS:\n{json.dumps(forbidden)}"

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        temperature=0,
        system=[{
            "type": "text",
            "text": system_text,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": (
                f"EXTRACTED INGREDIENTS TO CHECK (from OCR):\n"
                f"{json.dumps(ingredients)}\n\n"
                f"Return the JSON array now."
            ),
        }],
    )

    usage = response.usage
    logger.info(
        "Tier3 LLM tokens -- input: %d, output: %d, cache_read: %s, cache_create: %s",
        usage.input_tokens,
        usage.output_tokens,
        getattr(usage, "cache_read_input_tokens", 0),
        getattr(usage, "cache_creation_input_tokens", 0),
    )

    raw = response.content[0].text.strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        logger.error("Failed to parse LLM response: %s", raw[:500])
        return []


# ---------------------------------------------------------------------------
# Orchestrator -- run all 3 tiers
# ---------------------------------------------------------------------------

def match_ingredients(
    ingredients: List[str],
    forbidden: List[str],
) -> Tuple[List[Dict], List[str]]:
    """Run the 3-tier matching pipeline.

    Returns (forbidden_matches, safe_ingredients).
    """
    matches: List[Dict] = []
    remaining: List[str] = []
    safe: List[str] = []

    for ingredient in ingredients:
        hit = tier1_exact_match(ingredient, forbidden)
        if hit:
            matches.append({
                "ingredient": ingredient,
                "matched_forbidden": hit,
                "match_tier": "exact",
                "explanation": f"Exact match with '{hit}'",
            })
            continue

        hit = tier2_normalized_match(ingredient, forbidden)
        if hit:
            matches.append({
                "ingredient": ingredient,
                "matched_forbidden": hit,
                "match_tier": "normalized",
                "explanation": f"Normalized match with '{hit}'",
            })
            continue

        remaining.append(ingredient)

    if remaining:
        llm_results = tier3_llm_match(remaining, forbidden)
        for r in llm_results:
            if r.get("is_forbidden"):
                matches.append({
                    "ingredient": r["ingredient"],
                    "matched_forbidden": r.get("matched_forbidden", "Unknown"),
                    "match_tier": "llm",
                    "explanation": r.get("explanation", ""),
                })
            else:
                safe.append(r["ingredient"])

    return matches, safe


# ---------------------------------------------------------------------------
# Visual Verification -- send raw image + forbidden list to Claude (cached)
# ---------------------------------------------------------------------------

_VISUAL_VERIFY_SYSTEM = """\
You are a chemical safety inspector.

Your task: look at the provided image and determine if it contains ANY text \
(in ANY language, script, or handwriting style) that refers to ANY of the \
forbidden ingredients listed below.

Consider:
- Text in ANY language or script worldwide
- Handwritten, printed, or typed text
- Chemical formulas
- Phonetic transliterations in non-Latin scripts
- Synonyms, abbreviations, trade names, IUPAC names
- Partial or messy handwriting -- give your BEST interpretation

STRICT RULES -- AVOID FALSE POSITIVES:
- DO NOT do substring matching on molecular formulas. Each formula is a \
  unique chemical. C6H12O6 (glucose) is NOT C6H6 (benzene), even though \
  "C6H6" appears as a character substring of "C6H12O6". They are entirely \
  different molecules.
- C12... (12 carbon atoms) is NOT Cl2... (2 chlorine atoms). "C" followed \
  by a number is carbon count; "Cl" is the chlorine element. Different.
- H2O2 is NOT H2O. Every atom and subscript matters.
- Only flag a chemical if the COMPLETE chemical identity matches a \
  forbidden ingredient. Partial formula overlap does NOT count.
- When in doubt, do NOT flag it. A false positive (wrongly rejecting a \
  safe product) is worse than a false negative.

Return ONLY a JSON object (no markdown, no explanation outside JSON):
{
  "found_forbidden": true/false,
  "matches": [
    {
      "text_in_image": "<what you see in the image>",
      "matched_forbidden": "<forbidden ingredient it matches>",
      "explanation": "<why this matches>"
    }
  ]
}

If no forbidden ingredients are found, return:
{"found_forbidden": false, "matches": []}"""


_IMAGE_MEDIA_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "webp": "image/webp", "gif": "image/gif", "bmp": "image/png",
    "tiff": "image/png", "tif": "image/png",
}


def visual_verify_image(
    image_path: str,
    forbidden: List[str],
) -> List[Dict]:
    """Send the raw image to Claude with the forbidden list for direct visual check.

    Prompt caching: the system prompt + forbidden list are cached.
    Only the image varies per call.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = image_path.rsplit(".", 1)[-1].lower()
    media_type = _IMAGE_MEDIA_TYPES.get(ext, "image/png")

    system_text = (
        f"{_VISUAL_VERIFY_SYSTEM}\n\n"
        f"FORBIDDEN INGREDIENTS LIST:\n{json.dumps(forbidden)}"
    )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            temperature=0,
            system=[{
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Does this image contain any forbidden ingredients? Return the JSON.",
                    },
                ],
            }],
        )

        usage = response.usage
        logger.info(
            "Visual verify tokens -- input: %d, output: %d, cache_read: %s, cache_create: %s",
            usage.input_tokens,
            usage.output_tokens,
            getattr(usage, "cache_read_input_tokens", 0),
            getattr(usage, "cache_creation_input_tokens", 0),
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)

        if result.get("found_forbidden"):
            matches = []
            for m in result.get("matches", []):
                matches.append({
                    "ingredient": m.get("text_in_image", "Visual detection"),
                    "matched_forbidden": m.get("matched_forbidden", "Unknown"),
                    "match_tier": "visual_verify",
                    "explanation": m.get("explanation", ""),
                })
            return matches
    except Exception as exc:
        logger.error("Visual verification failed: %s", exc)

    return []
