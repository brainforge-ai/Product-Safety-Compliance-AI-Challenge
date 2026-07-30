"""Domain-level exception types."""


class AppError(Exception):
    """Base class for application errors mapped to HTTP responses."""


class ExtractionError(AppError):
    """Raised when file content cannot be extracted."""


class UnsupportedFileTypeError(ExtractionError):
    """Raised when a file type is not supported for evaluation."""


class ParsingError(AppError):
    """Raised when structured product data cannot be parsed."""


class UploadTooLargeError(AppError):
    """Raised when an uploaded payload exceeds a configured resource bound."""


class MatchingError(AppError):
    """Reserved for deterministic tier failures; optional tiers fail open."""
