"""Row parser for CSV product files.

Not a member of the `Extractor` protocol: CSV yields row-shaped structured
data (a list of dicts), not a raw text blob, and is handled as a distinct
parsing path from Phase 3 onward.
"""

import csv
from pathlib import Path

from app.core.exceptions import ExtractionError


class CsvExtractor:
    def extract(self, path: Path) -> list[dict[str, str]]:
        try:
            with path.open(newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except OSError as exc:
            raise ExtractionError(f"Could not read CSV file: {path}") from exc
