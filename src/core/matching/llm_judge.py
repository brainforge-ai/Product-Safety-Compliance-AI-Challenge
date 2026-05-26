"""
LLM Judge (Layer C) - Final arbiter for ambiguous ingredient matches.

Uses GPT-4o to determine if unresolved ingredients match any forbidden entries.
This is called only when Layers A and B fail to make a determination.
"""
from __future__ import annotations
import logging

from src.core.models import MatchHit, MatchLayer
from src.core.matching.normalize import normalize_name
from src.core.openai_client import get_openai_client, parse_json_response

logger = logging.getLogger(__name__)

LLM_JUDGE_SYSTEM_PROMPT = """You are a chemical safety expert determining if product ingredients match forbidden substances.

CRITICAL RULES:
1. Chemical formulas are EXACT - C6H12O6 (glucose) is NOT C6H6 (benzene). Do NOT do substring matching.
2. You must understand chemical synonyms:
   - "Hydrogen Peroxide" = H2O2
   - "Benzene" = C6H6
   - "Caffeine" = C8H10N4O2
   - "1,4-Dioxane" = C4H8O2
3. Handle trade names, IUPAC names, E-numbers, CAS names
4. Be conservative: only match if you are CERTAIN they refer to the same substance
5. Consider common misspellings and abbreviations

You will receive:
- A list of forbidden ingredients
- A list of product ingredients to check

For each product ingredient, determine if it matches ANY forbidden ingredient.

6. Use only strings from the provided lists — never invent, paraphrase, or add ingredients or forbidden entries.

7. If you cannot establish the same substance with high confidence, return no match for that ingredient. Prefer {"matches": []} over a speculative match.
"""



async def judge_ingredients(
    ingredients: list[str],
    forbidden_list: list[str],
) -> list[MatchHit]:
    """
    Use GPT-4o to judge if ingredients match any forbidden entries.
    """
    if not ingredients:
        return []

    # Build normalized lookup maps for validation
    # This allows us to match "Glucose" with " glucose" or "GLUCOSE"
    normalized_to_ingredient = {normalize_name(ing): ing for ing in ingredients}
    normalized_to_forbidden = {normalize_name(f): f for f in forbidden_list}

    client = get_openai_client()

    forbidden_str = "\n".join(f"- {f}" for f in forbidden_list)
    ingredients_str = "\n".join(f"- {i}" for i in ingredients)

    user_prompt = f"""FORBIDDEN INGREDIENTS:
{forbidden_str}

PRODUCT INGREDIENTS TO CHECK:
{ingredients_str}

For each product ingredient, determine if it matches any forbidden ingredient.

Return ONLY valid JSON in this exact format:
{{
  "matches": [
    {{
      "ingredient": "exact ingredient name from product",
      "forbidden_match": "exact forbidden ingredient it matches",
      "confidence": 0.95,
      "reasoning": "brief explanation"
    }}
  ]
}}

If no matches found, return: {{"matches": []}}"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": LLM_JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            max_tokens=1000,
        )

        content = response.choices[0].message.content
        data = parse_json_response(content)

        if not isinstance(data, dict):
            logger.warning("LLM Judge returned non-dict response")
            return []

        matches = data.get("matches", [])

        if not isinstance(matches, list):
            logger.warning("LLM Judge 'matches' is not a list")
            return []

        hits = []
        for match in matches:
            if not isinstance(match, dict):
                continue

            # Validate required fields exist and are strings
            ingredient = match.get("ingredient")
            forbidden_match = match.get("forbidden_match")
            confidence = match.get("confidence", 0.0)

            if not ingredient or not isinstance(ingredient, str):
                continue
            if not forbidden_match or not isinstance(forbidden_match, str):
                continue
            if not isinstance(confidence, (int, float)):
                confidence = 0.0

            # Normalize for lookup - handles whitespace/casing differences
            norm_ingredient = normalize_name(ingredient)
            norm_forbidden = normalize_name(forbidden_match)

            # Verify the forbidden_match is actually in our forbidden list (normalized)
            if norm_forbidden not in normalized_to_forbidden:
                logger.warning(f"LLM returned invalid forbidden_match: '{forbidden_match}'")
                continue

            # Verify the ingredient was in our input list (normalized)
            if norm_ingredient not in normalized_to_ingredient:
                logger.warning(f"LLM returned ingredient not in input: '{ingredient}'")
                continue

            # Use the original strings from our input for consistency
            original_ingredient = normalized_to_ingredient[norm_ingredient]
            original_forbidden = normalized_to_forbidden[norm_forbidden]

            if confidence >= 0.85:
                hits.append(MatchHit(
                    ingredient=original_ingredient,
                    forbidden_match=original_forbidden,
                    layer=MatchLayer.C_LLM,
                    confidence=float(confidence),
                    reasoning=match.get("reasoning") if isinstance(match.get("reasoning"), str) else None,
                ))

        return hits

    except Exception as e:
        logger.error(f"LLM Judge failed: {e}")
        return []
