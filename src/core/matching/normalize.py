"""
Chemical-aware normalization for ingredient matching.

Handles:
- Hill notation for molecular formulas (C first, H second, rest alphabetical)
- Name normalization (lowercase, whitespace cleanup)
- Special cases like "1,4-Dioxane" where commas are part of the name
- Classification of strings as formulas vs names
"""
from __future__ import annotations
import re
from collections import Counter

from src.core.models import IngredientKind

# Full periodic table element symbols
ELEMENTS = frozenset([
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
    "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
    "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
    "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
    "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds",
    "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og"
])

# Regex to tokenize molecular formulas: matches element symbol + optional count
_FORMULA_TOKEN_RE = re.compile(r"([A-Z][a-z]?)(\d*)")

# Common abbreviations that look like formulas but aren't
_NON_FORMULA_ABBREVS = frozenset([
    "BHA", "BHT", "EDTA", "PEG", "SLS", "SLES", "TEA", "DEA", "MEA",
    "AHA", "PVP", "PABA", "DMSO", "ATP", "DNA", "RNA"
])


def is_formula(s: str) -> bool:
    """
    Determine if a string is a molecular formula.

    Valid formulas:
    - C6H6 (benzene)
    - H2O2 (hydrogen peroxide)
    - C8H10N4O2 (caffeine)

    Not formulas:
    - BHA (abbreviation, 'A' is not an element)
    - Benzene (common name)
    - Sodium Lauryl Sulfate (multi-word name)
    """
    s = s.strip()

    # Quick rejections
    if not s:
        return False
    if " " in s:  # Multi-word = definitely a name
        return False
    if s.upper() in _NON_FORMULA_ABBREVS:
        return False
    if not s[0].isupper():  # Formulas start with capital
        return False

    # Must contain at least one digit for count (except single-element)
    # But H2O has digits, C6H6 has digits, etc.

    # Parse tokens and validate each is a real element
    tokens = _FORMULA_TOKEN_RE.findall(s)
    if not tokens:
        return False

    # Reconstruct to check we matched the whole string
    reconstructed = "".join(f"{el}{cnt}" for el, cnt in tokens)
    if reconstructed != s:
        return False

    # Every element symbol must be valid
    elements_found = [el for el, _ in tokens if el]
    if not elements_found:
        return False

    for el in elements_found:
        if el not in ELEMENTS:
            return False

    return True


def parse_formula(formula: str) -> Counter:
    """
    Parse a molecular formula into element counts.

    Example: "C6H6" -> Counter({'C': 6, 'H': 6})
    """
    counts = Counter()
    for el, cnt in _FORMULA_TOKEN_RE.findall(formula):
        if el:
            counts[el] += int(cnt) if cnt else 1
    return counts


def to_hill(formula: str) -> str:
    """
    Convert a molecular formula to Hill notation.

    Hill notation rules:
    1. Carbon (C) first, if present
    2. Hydrogen (H) second, if C present
    3. All other elements alphabetically
    4. Counts of 1 are omitted

    Examples:
    - C6H6 -> C6H6 (already Hill)
    - H2O2 -> H2O2 (no C, so H first alphabetically)
    - C8H10N4O2 -> C8H10N4O2
    """
    if not is_formula(formula):
        return formula  # Return as-is if not a formula

    counts = parse_formula(formula)
    parts = []

    # Hill ordering
    if "C" in counts:
        # Carbon first
        c_count = counts.pop("C")
        parts.append(f"C{c_count}" if c_count > 1 else "C")

        # Hydrogen second (if present)
        if "H" in counts:
            h_count = counts.pop("H")
            parts.append(f"H{h_count}" if h_count > 1 else "H")

    # Rest alphabetically
    for el in sorted(counts.keys()):
        cnt = counts[el]
        parts.append(f"{el}{cnt}" if cnt > 1 else el)

    return "".join(parts)


def normalize_name(name: str) -> str:
    """
    Normalize a chemical name for comparison.

    - Lowercase
    - Strip leading/trailing whitespace
    - Collapse multiple spaces to single space
    - Preserve important characters like commas in "1,4-Dioxane"
    """
    name = name.strip().lower()
    name = re.sub(r"\s+", " ", name)
    return name


def normalize_for_matching(s: str) -> str:
    """
    Aggressive normalization for fuzzy matching.

    - Remove spaces, hyphens, underscores
    - Lowercase
    - BUT preserve digits and commas (for things like 1,4-Dioxane)
    """
    s = s.strip().lower()
    # Remove common separators but keep commas and digits
    s = re.sub(r"[\s\-_]+", "", s)
    return s


def classify(s: str) -> IngredientKind:
    """Classify a string as either a formula or a name."""
    return IngredientKind.FORMULA if is_formula(s) else IngredientKind.NAME
