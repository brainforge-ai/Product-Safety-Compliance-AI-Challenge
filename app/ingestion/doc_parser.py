"""DOCX file parsing utilities."""

from docx import Document


def extract_docx(file_path):
    """
    Extract text from a .docx file.
    """
    doc = Document(file_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text