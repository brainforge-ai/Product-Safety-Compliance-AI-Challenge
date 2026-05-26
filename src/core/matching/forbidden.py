"""
ForbiddenIndex: Pre-resolved index of forbidden ingredients.

At startup, resolves all forbidden ingredients to:
- Normalized forms (Hill notation for formulas, lowercase for names)
- PubChem CIDs
- All known synonyms/aliases

This enables Layer A to catch matches like "Hydrogen Peroxide" -> "H2O2"
without any API calls during request processing.
"""
from __future__ import annotations
import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.core.matching.normalize import (
    classify,
    normalize_name,
    normalize_for_matching,
    to_hill,
)
from src.core.matching.pubchem import PubChemClient
from src.core.models import IngredientKind, MatchLayer

logger = logging.getLogger(__name__)


@dataclass
class ForbiddenEntry:
    """A single forbidden ingredient with all its resolved data."""
    raw: str  # Original entry from CSV
    normalized: str  # Normalized form
    kind: IngredientKind
    cids: list[int] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)


@dataclass
class LayerAMatch:
    """Result of a Layer A match."""
    forbidden_raw: str  # The matched forbidden entry
    layer: MatchLayer  # A_EXACT or A_ALIAS


class ForbiddenIndex:
    """
    Index of forbidden ingredients with pre-resolved CIDs and synonyms.

    Supports three types of lookups:
    1. match_layer_a: Combined exact + alias matching (single method)
    2. cid_overlap: Match via PubChem CID intersection
    """

    def __init__(self):
        self.entries: dict[str, ForbiddenEntry] = {}  # keyed by raw entry
        self.cid_to_entries: dict[int, list[str]] = {}  # CID -> raw entries
        self.all_cids: set[int] = set()

        # Unified lookup index - maps normalized forms to (raw_entry, is_exact)
        # is_exact=True means it's a direct match, False means it's an alias
        self._normalized_index: dict[str, tuple[str, bool]] = {}

    @classmethod
    def from_csv(cls, path: str | Path) -> "ForbiddenIndex":
        """Load forbidden ingredients from CSV file."""
        index = cls()
        path = Path(path)

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw = row.get("ingredient", "").strip()
                if not raw:
                    continue

                kind = classify(raw)
                if kind == IngredientKind.FORMULA:
                    normalized = to_hill(raw)
                else:
                    normalized = normalize_name(raw)

                entry = ForbiddenEntry(
                    raw=raw,
                    normalized=normalized,
                    kind=kind,
                )
                index.entries[raw] = entry

                # Build unified index - exact matches
                index._normalized_index[normalized] = (raw, True)
                index._normalized_index[normalize_for_matching(raw)] = (raw, True)

        logger.info(f"Loaded {len(index.entries)} forbidden ingredients from {path}")
        return index

    async def resolve_all(self, pubchem: PubChemClient) -> None:
        """
        Pre-resolve all forbidden ingredients to CIDs and synonyms.

        This is called once at startup. After this, Layer A can match
        against all known aliases without any API calls.
        """
        logger.info("Resolving forbidden ingredients via PubChem...")

        for raw, entry in self.entries.items():
            is_form = entry.kind == IngredientKind.FORMULA

            try:
                cids, synonyms = await pubchem.get_cid_with_synonyms(
                    raw, is_formula=is_form
                )

                entry.cids = cids
                entry.synonyms = synonyms

                # Build CID index
                for cid in cids:
                    self.all_cids.add(cid)
                    if cid not in self.cid_to_entries:
                        self.cid_to_entries[cid] = []
                    self.cid_to_entries[cid].append(raw)

                # Build synonym index (alias matches)
                for syn in synonyms:
                    norm_syn = normalize_name(syn)
                    # Only add if not already present (preserve exact match priority)
                    if norm_syn not in self._normalized_index:
                        self._normalized_index[norm_syn] = (raw, False)

                    agg_norm = normalize_for_matching(syn)
                    if agg_norm not in self._normalized_index:
                        self._normalized_index[agg_norm] = (raw, False)

                logger.debug(
                    f"Resolved '{raw}': {len(cids)} CIDs, {len(synonyms)} synonyms"
                )

            except Exception as e:
                logger.warning(f"Failed to resolve '{raw}': {e}")

        logger.info(
            f"Resolution complete: {len(self.all_cids)} unique CIDs, "
            f"{len(self._normalized_index)} normalized forms indexed"
        )

    def match_layer_a(self, ingredient: str) -> Optional[LayerAMatch]:
        """
        Layer A: Combined exact + alias matching in a single lookup.

        Checks all normalized forms against the unified index.
        Returns the match with whether it was exact or alias.
        """
        # Try exact normalized form first
        kind = classify(ingredient)
        if kind == IngredientKind.FORMULA:
            normalized = to_hill(ingredient)
        else:
            normalized = normalize_name(ingredient)

        if normalized in self._normalized_index:
            raw, is_exact = self._normalized_index[normalized]
            return LayerAMatch(
                forbidden_raw=raw,
                layer=MatchLayer.A_EXACT if is_exact else MatchLayer.A_ALIAS
            )

        # Try aggressive normalization
        agg_norm = normalize_for_matching(ingredient)
        if agg_norm in self._normalized_index:
            raw, is_exact = self._normalized_index[agg_norm]
            return LayerAMatch(
                forbidden_raw=raw,
                layer=MatchLayer.A_EXACT if is_exact else MatchLayer.A_ALIAS
            )

        return None

    def cid_overlap(self, ingredient_cids: list[int]) -> Optional[str]:
        """
        Layer B: Check if any ingredient CIDs overlap with forbidden CIDs.

        Returns the first matched forbidden entry raw string, or None.
        """
        for cid in ingredient_cids:
            if cid in self.cid_to_entries:
                return self.cid_to_entries[cid][0]
        return None

    def get_all_raw_entries(self) -> list[str]:
        """Get all raw forbidden ingredient strings for LLM prompt."""
        return list(self.entries.keys())

    def __len__(self) -> int:
        return len(self.entries)
