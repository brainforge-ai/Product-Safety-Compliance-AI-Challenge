"""CSV-backed forbidden ingredient list repository.

Loads the default list from a CSV file and supports in-memory replacement
(e.g. from an uploaded CSV). Persistence of uploaded lists across restarts
is wired in Phase 6; this repository is the in-memory source of truth
either way.
"""

import csv
from pathlib import Path


class ForbiddenListRepository:
    def __init__(self, entries: list[str]) -> None:
        self._entries = list(entries)

    @classmethod
    def from_csv(cls, path: Path) -> "ForbiddenListRepository":
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            column = reader.fieldnames[0] if reader.fieldnames else None
            if column is None:
                return cls([])
            entries = [row[column].strip() for row in reader if row.get(column, "").strip()]

        return cls(entries)

    def get_all(self) -> list[str]:
        return list(self._entries)

    def replace(self, entries: list[str]) -> None:
        self._entries = list(entries)
