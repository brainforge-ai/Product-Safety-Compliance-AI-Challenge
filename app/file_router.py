"""Route input files to the correct extractor based on file extension."""

import os


SUPPORTED_EXTENSIONS = {
    ".txt": "text",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".bmp": "image",
    ".tiff": "image",
    ".tif": "image",
    ".csv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".json": "json",
    ".docx": "docx",
}


def detect_file_type(file_path: str) -> str:
    """Detect file type from extension and route to appropriate extractor."""
    ext = os.path.splitext(file_path)[1].lower()
    file_type = SUPPORTED_EXTENSIONS.get(ext)
    if not file_type:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS.keys()))}"
        )
    return file_type


def get_supported_extensions() -> list:
    """Return a sorted list of all supported file extensions."""
    return sorted(SUPPORTED_EXTENSIONS.keys())
