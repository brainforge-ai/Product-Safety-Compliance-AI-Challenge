"""CSV-backed forbidden ingredient list repository.

Loads the default list from a CSV file and supports in-memory replacement
(e.g. from an uploaded CSV). Persistence of uploaded lists across restarts
is wired in Phase 6; this repository is the in-memory source of truth
either way.
"""

import csv
from collections.abc import Iterable
from io import StringIO
from pathlib import Path


class ForbiddenListRepository:
    def __init__(self, entries: list[str]) -> None:
        self._entries = list(entries)

    @classmethod
    def from_csv(cls, path: Path) -> "ForbiddenListRepository":
        with path.open(newline="", encoding="utf-8") as f:
            return cls(parse_csv_entries(f))

    @classmethod
    def from_csv_text(cls, text: str) -> "ForbiddenListRepository":
        return cls(parse_csv_entries(StringIO(text)))

    def get_all(self) -> list[str]:
        return list(self._entries)

    def replace(self, entries: list[str]) -> None:
        self._entries = list(entries)


def parse_csv_entries(lines: Iterable[str]) -> list[str]:
    """Read the first column of a forbidden-list CSV, from any file-like/line iterable."""
    reader = csv.DictReader(lines)
    column = reader.fieldnames[0] if reader.fieldnames else None
    if column is None:
        return []
    return [row[column].strip() for row in reader if row.get(column, "").strip()]
