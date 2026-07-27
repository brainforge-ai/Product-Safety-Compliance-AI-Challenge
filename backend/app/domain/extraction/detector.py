"""File-type detection by extension with content-sniffing fallback."""

from enum import StrEnum
from pathlib import Path

from app.core.exceptions import UnsupportedFileTypeError

_EXTENSION_MAP = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".txt": "text",
    ".csv": "csv",
}


class FileType(StrEnum):
    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"
    CSV = "csv"


# Magic-byte prefixes for content-sniffing fallback, checked in order.
_SIGNATURES: list[tuple[bytes, FileType]] = [
    (b"%PDF-", FileType.PDF),
    (b"\x89PNG\r\n\x1a\n", FileType.IMAGE),
    (b"\xff\xd8\xff", FileType.IMAGE),
]


def detect_file_type(path: Path) -> FileType:
    """Detect a file's type from its extension, falling back to content sniffing.

    Raises UnsupportedFileTypeError if neither approach recognizes the file.
    """
    suffix = path.suffix.lower()
    if suffix in _EXTENSION_MAP:
        return FileType(_EXTENSION_MAP[suffix])

    try:
        header = path.read_bytes()[:8]
    except OSError as exc:
        raise UnsupportedFileTypeError(f"Could not read file to detect type: {path}") from exc

    for signature, file_type in _SIGNATURES:
        if header.startswith(signature):
            return file_type

    raise UnsupportedFileTypeError(f"Unsupported or unrecognized file type: {path}")
