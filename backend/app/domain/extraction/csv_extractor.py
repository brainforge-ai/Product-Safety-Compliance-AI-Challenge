"""CSV row parser (yields structured dicts, not a text blob)."""

import csv
from pathlib import Path

from app.core.exceptions import ExtractionError


class CsvExtractor:
    def extract(self, path: Path) -> list[dict[str, str]]:
        """Read a CSV file and return one dict per row."""
        try:
            with path.open(newline="", encoding="utf-8-sig") as f:
                return list(csv.DictReader(f))
        except (OSError, csv.Error) as exc:
            raise ExtractionError(f"Could not read CSV file: {path}") from exc
