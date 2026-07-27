"""In-memory forbidden ingredient list loaded from CSV."""

import csv
import hashlib
from collections.abc import Iterable
from io import StringIO
from pathlib import Path


class ForbiddenListRepository:
    def __init__(self, entries: list[str]) -> None:
        """Hold an in-memory copy of forbidden ingredient entries."""
        self._entries = list(entries)

    @classmethod
    def from_csv(cls, path: Path) -> "ForbiddenListRepository":
        """Load forbidden entries from a CSV file on disk."""
        with path.open(newline="", encoding="utf-8") as f:
            return cls(parse_csv_entries(f))

    @classmethod
    def from_csv_text(cls, text: str) -> "ForbiddenListRepository":
        """Load forbidden entries from CSV text in memory."""
        return cls(parse_csv_entries(StringIO(text)))

    def get_all(self) -> list[str]:
        """Return a copy of all forbidden ingredient entries."""
        return list(self._entries)

    def replace(self, entries: list[str]) -> None:
        """Replace the in-memory list with a new set of entries."""
        self._entries = list(entries)

    def version_hash(self) -> str:
        """Stable, order-independent hash of the current entry set."""
        canonical = "\n".join(sorted(e.strip().lower() for e in self._entries))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_csv_entries(lines: Iterable[str]) -> list[str]:
    """Parse the first CSV column into stripped forbidden ingredient strings."""
    reader = csv.DictReader(lines)
    column = reader.fieldnames[0] if reader.fieldnames else None
    if column is None:
        return []
    return [row[column].strip() for row in reader if row.get(column, "").strip()]
