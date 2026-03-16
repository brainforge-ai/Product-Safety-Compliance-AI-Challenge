"""PDF parsing utilities."""

import pdfplumber


def extract_pdf(file_path):
    """
    Extract all text from a PDF file, one page at a time, and return it as a single string.
    """
    # Start with an empty string; we'll append each page's text to it.
    text = ""

    # pdfplumber.open() opens the PDF. Using 'with' ensures the file is closed when we're done.
    with pdfplumber.open(file_path) as pdf:

        # Loop over every page in the PDF (pdf.pages is a list of page objects).
        for page in pdf.pages:

            # extract_text() gets the text from that page. It can return None if the page has no text (e.g. image-only).
            # "or ''" turns None into an empty string so we never concatenate None and cause an error.
            text += page.extract_text() or ""

    # Return the full document text (all pages concatenated).
    return text
