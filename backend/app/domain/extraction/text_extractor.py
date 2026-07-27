"""Direct read of plain-text product files."""

from pathlib import Path

from app.core.exceptions import ExtractionError
from app.domain.extraction.base import Extractor


class TextExtractor(Extractor):
    def extract(self, path: Path) -> str:
        """Read a plain-text product file as UTF-8, falling back to Latin-1."""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")
        except OSError as exc:
            raise ExtractionError(f"Could not read text file: {path}") from exc
