"""Chemical detection utilities."""

import re

# Simple pattern for chemical-like tokens (e.g., H2, Na, Cl, Fe3).
CHEM_PATTERN = r"[A-Z][a-z]?\d*"


def detect_formula(ingredient):
    """
    Return True if the given ingredient string contains a chemical-like token
    that matches CHEM_PATTERN, else False.
    """
    if re.search(CHEM_PATTERN, ingredient):
        return True

    return False
