"""Domain-level exception types."""


class AppError(Exception):
    pass


class ExtractionError(AppError):
    pass


class UnsupportedFileTypeError(ExtractionError):
    pass


class ParsingError(AppError):
    pass


class MatchingError(AppError):
    """Reserved for deterministic tier failures; optional tiers fail open."""

    pass
