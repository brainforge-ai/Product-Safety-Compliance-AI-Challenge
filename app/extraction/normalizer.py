import re
from functools import lru_cache

import pubchempy as pcp

from ..logger import logger


SUBSCRIPT_TRANSLATION = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋", "0123456789+-")
CAS_PATTERN = re.compile(r"^\d{1,7}-\d{2}-\d$")
ELEMENT_SYMBOLS = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar",
    "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr",
    "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe",
    "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu",
    "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac",
    "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh",
    "Hs", "Mt", "Ds", "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
}


def cleanup_ocr_artifacts(text: str, lowercase: bool = False, preserve_newlines: bool = False) -> str:
    """Normalize OCR artifacts such as subscript digits and uneven spacing."""
    value = (text or "").translate(SUBSCRIPT_TRANSLATION).strip()
    value = value.replace("−", "-").replace("–", "-").replace("—", "-")
    if preserve_newlines:
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"[^\S\n]+", " ", value)
        value = re.sub(r"\n+", "\n", value)
    else:
        value = re.sub(r"\s+", " ", value)
    return value.lower() if lowercase else value


def normalize_formula(text: str) -> str:
    """Normalize chemical formulas while preserving letters/numbers order."""
    value = cleanup_ocr_artifacts(text, lowercase=False)
    if not value:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", value).lower()


def looks_like_formula(text: str) -> bool:
    """Heuristically detect formula-like terms before PubChem resolution."""
    candidate = re.sub(r"[^A-Za-z0-9]", "", cleanup_ocr_artifacts(text, lowercase=False))
    if not candidate:
        return False
    if not any(ch.isdigit() for ch in candidate):
        return False

    index = 0
    token_count = 0
    while index < len(candidate):
        two_char = candidate[index:index + 2]
        one_char = candidate[index:index + 1]

        symbol = None
        if len(two_char) == 2 and two_char[0].isalpha() and two_char[1].isalpha() and two_char.capitalize() in ELEMENT_SYMBOLS:
            symbol = two_char.capitalize()
            index += 2
        elif one_char.isalpha() and one_char.upper() in ELEMENT_SYMBOLS:
            symbol = one_char.upper()
            index += 1
        else:
            return False

        token_count += 1
        while index < len(candidate) and candidate[index].isdigit():
            index += 1

    return token_count >= 1


def _compound_display_name(compound, fallback: str) -> str:
    """Choose a canonical display name from a PubChem compound object."""
    iupac = (getattr(compound, "iupac_name", None) or "").strip()
    synonyms = getattr(compound, "synonyms", None) or []
    preferred_synonym = ""
    for synonym in synonyms:
        candidate = cleanup_ocr_artifacts(str(synonym), lowercase=False)
        if not candidate:
            continue
        if CAS_PATTERN.match(candidate):
            continue
        if looks_like_formula(candidate):
            continue
        preferred_synonym = candidate
        break

    first_synonym = cleanup_ocr_artifacts(str(synonyms[0]), lowercase=False) if synonyms else ""
    name = preferred_synonym or iupac or first_synonym or fallback
    return cleanup_ocr_artifacts(name, lowercase=True)


@lru_cache(maxsize=512)
def _get_pubchem_compounds(identifier: str, namespace: str):
    """Cached PubChem lookup with safe fallback to an empty tuple."""
    try:
        compounds = pcp.get_compounds(identifier, namespace) or []
        return tuple(compounds)
    except Exception:
        logger.warning("PubChem lookup failed for identifier=%s namespace=%s", identifier, namespace, exc_info=True)
        return tuple()


@lru_cache(maxsize=512)
def resolve_formula_to_name(text: str) -> str:
    """Resolve a chemical formula to a canonical chemical name using PubChem."""
    formula = normalize_formula(text)
    if not looks_like_formula(text):
        return ""
    for query in (formula, formula.upper()):
        compounds = _get_pubchem_compounds(query, "formula")
        if compounds:
            return _compound_display_name(compounds[0], formula)
    return ""


def resolve_chemical_name(text: str) -> str:
    """Resolve formula-like inputs to canonical chemical names when possible."""
    cleaned = cleanup_ocr_artifacts(text, lowercase=False)
    if not cleaned:
        return ""
    if looks_like_formula(cleaned):
        resolved = resolve_formula_to_name(cleaned)
        if resolved:
            return resolved
    return cleaned


@lru_cache(maxsize=512)
def get_pubchem_synonyms(term: str) -> tuple[str, ...]:
    """Resolve PubChem synonyms for a term with caching and safe fallback."""
    cleaned = cleanup_ocr_artifacts(term, lowercase=False)
    if not cleaned:
        return tuple()

    if CAS_PATTERN.match(cleaned):
        namespace = "cas"
        query = cleaned
    elif looks_like_formula(cleaned):
        namespace = "formula"
        query = normalize_formula(cleaned)
    else:
        namespace = "name"
        query = cleaned

    compounds = _get_pubchem_compounds(query, namespace)
    if not compounds and namespace == "formula":
        compounds = _get_pubchem_compounds(query.upper(), namespace)
    if not compounds:
        return tuple()

    synonyms = []
    canonical = _compound_display_name(compounds[0], cleaned)
    if canonical:
        synonyms.append(canonical)
    for synonym in getattr(compounds[0], "synonyms", None) or []:
        cleaned_synonym = cleanup_ocr_artifacts(str(synonym), lowercase=True)
        if cleaned_synonym:
            synonyms.append(cleaned_synonym)
    return tuple(dict.fromkeys(synonyms))


def normalize(text):
    """
    Normalize ingredient text so matching is more robust.
    Handles common variations, units, and formatting.
    """

    raw_text = cleanup_ocr_artifacts(text, lowercase=False)
    resolved_text = resolve_chemical_name(raw_text)

    # 1. lowercase
    text = cleanup_ocr_artifacts(resolved_text, lowercase=True)

    # 2. convert british spelling
    text = text.replace("sulphate", "sulfate").replace("colour", "color")

    # 3. remove common units and percentages
    text = re.sub(r'\b\d+(\.\d+)?\s*(%|mg|g|ml|l|kg|oz|lb|cup|tbsp|tsp)\b', '', text)

    # 4. remove parentheses but keep inner content so formulas/names survive
    text = text.replace("(", " ").replace(")", " ")

    # 5. remove punctuation but keep numbers and letters
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # 6. collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    # 7. trim
    text = text.strip()

    formula_norm = normalize_formula(raw_text)
    if looks_like_formula(raw_text) and formula_norm and formula_norm == text.replace(" ", ""):
        return formula_norm

    return text