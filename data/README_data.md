# Data Directory

This directory holds inputs for the Product Safety Compliance AI system.

## Structure

- **`samples/`** – Example product files (labels, PDFs, images, text) for development and demos. You can run evaluation against these via the API or the optional UI.
- **`evaluation/`** – Reserved for held-out test products (not shipped in the repo). The system is designed to generalize to new, unseen data.

The **forbidden ingredient list** is supplied only via the API or UI (upload CSV or paste comma-separated list). No default list is loaded from this directory. When pasting CSV, the first column is used as ingredients; headers and risk-level words (high, medium, low) are ignored.

## Product file formats

Supported for product labels / ingredient lists:

- **PDF** – text extraction via pdfplumber  
- **Images** – PNG, JPG, etc.; OCR via EasyOCR  
- **TXT, DOCX, CSV, XLSX** – text or table extraction  

Unstructured and OCR output are handled by the extraction and normalization steps before matching against the forbidden list.
