from pathlib import Path

import pytest

from app.core.exceptions import UnsupportedFileTypeError
from app.domain.extraction.detector import FileType, detect_file_type


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("label.pdf", FileType.PDF),
        ("label.PNG", FileType.IMAGE),
        ("label.jpg", FileType.IMAGE),
        ("label.txt", FileType.TEXT),
        ("label.csv", FileType.CSV),
    ],
)
def test_detects_by_extension(tmp_path: Path, filename: str, expected: FileType) -> None:
    path = tmp_path / filename
    path.write_bytes(b"irrelevant")
    assert detect_file_type(path) == expected


def test_falls_back_to_content_sniffing_for_unknown_extension(tmp_path: Path) -> None:
    path = tmp_path / "label.bin"
    path.write_bytes(b"%PDF-1.7\n...")
    assert detect_file_type(path) == FileType.PDF


def test_unsupported_file_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "label.exe"
    path.write_bytes(b"MZ\x90\x00garbage")
    with pytest.raises(UnsupportedFileTypeError):
        detect_file_type(path)


def test_unreadable_path_raises(tmp_path: Path) -> None:
    path = tmp_path / "missing.bin"
    with pytest.raises(UnsupportedFileTypeError):
        detect_file_type(path)
