"""Shared extractor protocol for the single-blob file types (pdf, image, text).

CSV is deliberately not a member of this protocol: it produces row-shaped
structured data rather than a raw text blob, and is handled as a distinct
parsing path (see docs/IMPLEMENTATION_PLAN.md Phase 2/3).
"""

from pathlib import Path
from typing import Protocol


class Extractor(Protocol):
    """Extracts a raw text blob from a file. Pure function of file bytes."""

    def extract(self, path: Path) -> str: ...
