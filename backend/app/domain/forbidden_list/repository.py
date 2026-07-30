"""In-memory forbidden ingredient list loaded from CSV."""

import csv
import hashlib
from collections.abc import Iterable
from io import StringIO
from pathlib import Path
from threading import RLock


class ForbiddenListRepository:
    def __init__(self, entries: list[str]) -> None:
        """Hold an in-memory copy of forbidden ingredient entries."""
        self._lock = RLock()
        self._entries = _unique_entries(entries)
        self._version = _version_hash(self._entries)

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
        with self._lock:
            return list(self._entries)

    def replace(self, entries: list[str]) -> None:
        """Replace the in-memory list with a new set of entries."""
        resolved = _unique_entries(entries)
        with self._lock:
            self._entries = resolved
            self._version = _version_hash(resolved)

    def version_hash(self) -> str:
        """Stable, order-independent hash of the current entry set."""
        with self._lock:
            return self._version

    def snapshot(self) -> tuple[list[str], str]:
        """Return entries and their matching version atomically."""
        with self._lock:
            return list(self._entries), self._version


def parse_csv_entries(lines: Iterable[str]) -> list[str]:
    """Parse the first CSV column into stripped forbidden ingredient strings."""
    reader = csv.DictReader(lines)
    column = reader.fieldnames[0] if reader.fieldnames else None
    if column is None:
        return []
    return [row[column].strip() for row in reader if row.get(column, "").strip()]


def _unique_entries(entries: Iterable[str]) -> list[str]:
    """Trim and de-duplicate entries case-insensitively, preserving order."""
    unique: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        value = entry.strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            unique.append(value)
    return unique


def _version_hash(entries: Iterable[str]) -> str:
    canonical = "\n".join(sorted(entry.casefold() for entry in entries))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
