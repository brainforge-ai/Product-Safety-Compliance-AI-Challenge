"""File loading utilities: route files to the right extractor and return text."""

import os

from .pdf_parser import extract_pdf
from .image_ocr import extract_image
from .text_reader import extract_txt
from .doc_parser import extract_docx
from .csv_parser import extract_csv
from .xlsx_parser import extract_xlsx

# Supported extensions: PDF, images (many formats), plain text, DOCX, CSV, XLSX.
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
TEXT_EXTENSIONS = {".txt"}
DOCX_EXTENSIONS = {".docx"}
CSV_EXTENSIONS = {".csv"}
XLSX_EXTENSIONS = {".xlsx"}


def load_file(file_path):
    """
    Detect file type from the path, call the right extractor, and return the extracted text.
    Supports: .pdf, all image formats in IMAGE_EXTENSIONS, .txt, .docx, .csv, .xlsx.
    """
    # Get the file extension in lowercase (e.g. ".pdf", ".png", ".jpg") for consistent matching.
    ext = os.path.splitext(file_path)[1].lower()

    if ext in PDF_EXTENSIONS:
        return extract_pdf(file_path)

    if ext in IMAGE_EXTENSIONS:
        return extract_image(file_path)

    if ext in TEXT_EXTENSIONS:
        return extract_txt(file_path)

    if ext in DOCX_EXTENSIONS:
        return extract_docx(file_path)

    if ext in CSV_EXTENSIONS:
        return extract_csv(file_path)

    if ext in XLSX_EXTENSIONS:
        return extract_xlsx(file_path)

    raise Exception(f"Unsupported format: {ext}")
