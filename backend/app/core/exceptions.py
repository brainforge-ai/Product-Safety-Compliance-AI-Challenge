"""Domain-level exception types.

These are framework-free; the API layer (added in Phase 7) is responsible
for catching them and mapping them to appropriate HTTP responses.
"""


class AppError(Exception):
    """Base class for all application-raised errors."""


class ExtractionError(AppError):
    """Raised when raw text/rows cannot be extracted from a product file."""


class UnsupportedFileTypeError(ExtractionError):
    """Raised when a file's type cannot be detected or is not supported."""


class ParsingError(AppError):
    """Raised when structured fields cannot be parsed from extracted text."""


class MatchingError(AppError):
    """Raised when the ingredient matching pipeline fails unrecoverably.

    Individual optional tiers (embedding, LLM) should fail open rather than
    raise this; it is reserved for failures in the deterministic tiers that
    indicate a genuine bug rather than an unresolved ingredient.
    """
