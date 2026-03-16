"""Image OCR utilities."""

import easyocr
from PIL import Image, ImageFilter
import numpy as np
import cv2


def _group_ocr_results_into_lines(results, y_tolerance=18):
    """Group EasyOCR detections into text lines using bounding-box Y positions.

    This preserves newline-separated ingredient lists from images instead of flattening
    everything into one long space-separated string.
    """
    if not results:
        return []

    positioned = []
    for box, text_part, _ in results:
        if not text_part or not str(text_part).strip():
            continue
        xs = [point[0] for point in box]
        ys = [point[1] for point in box]
        positioned.append(
            {
                "text": str(text_part).strip(),
                "x": min(xs),
                "y": sum(ys) / len(ys),
            }
        )

    if not positioned:
        return []

    positioned.sort(key=lambda item: (item["y"], item["x"]))
    lines = []
    current_line = [positioned[0]]
    current_y = positioned[0]["y"]

    for item in positioned[1:]:
        if abs(item["y"] - current_y) <= y_tolerance:
            current_line.append(item)
            current_y = (current_y + item["y"]) / 2
        else:
            lines.append(current_line)
            current_line = [item]
            current_y = item["y"]
    lines.append(current_line)

    normalized_lines = []
    for line in lines:
        line.sort(key=lambda item: item["x"])
        normalized_lines.append(" ".join(item["text"] for item in line).strip())
    return [line for line in normalized_lines if line]

# Lazy-loaded EasyOCR reader to avoid import-time failures
_reader = None


def get_ocr_reader():
    """Return a cached EasyOCR reader instance."""
    global _reader
    if _reader is None:
        # Use a minimal language set to avoid EasyOCR language incompatibility issues.
        # EasyOCR raises an error if Arabic is combined with many other languages.
        # We prioritize English for product labels.
        lang_list = ["en"]
        _reader = easyocr.Reader(lang_list)
    return _reader


def preprocess_image(img):
    """
    Preprocess image for better OCR: grayscale, adaptive threshold, noise removal.
    """
    # Convert to grayscale
    img = img.convert("L")

    # Convert to OpenCV format
    img_cv = np.array(img)

    # Apply Gaussian blur to reduce noise
    img_cv = cv2.GaussianBlur(img_cv, (5, 5), 0)

    # Adaptive thresholding
    img_cv = cv2.adaptiveThreshold(
        img_cv, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # Convert back to PIL
    img = Image.fromarray(img_cv)

    return img


def extract_image(file_path):
    """
    Run OCR on an image file using EasyOCR and return the extracted text as a string.
    Supports multiple languages.
    """
    # Open the image from disk. PIL (Pillow) supports common formats (PNG, JPEG, BMP, etc.).
    img = Image.open(file_path)

    # Preprocess for better OCR
    img = preprocess_image(img)

    # Convert PIL image to numpy array for EasyOCR
    img_array = np.array(img)

    # Run EasyOCR on the image and get results
    reader = get_ocr_reader()
    results = reader.readtext(img_array)

    # Preserve line structure so newline-separated ingredients in images remain parseable.
    lines = _group_ocr_results_into_lines(results)
    text = "\n".join(lines).strip()
    print(f"OCR extracted from {file_path}: '{text}'")  # Debug: log extracted text
    return text
