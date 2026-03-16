import json
import csv
from io import StringIO

import streamlit as st
import requests


st.set_page_config(page_title="Product Safety AI", layout="centered")

st.title("Product Safety AI Dashboard")
st.write(
    "Upload a product label (PDF/image/text) and an optional forbidden ingredient list. "
    "The backend will analyze it and return a safety evaluation."
)
st.caption("First request may take 1–2 minutes (embedding model loads on first use). Later requests are faster. If you see a timeout, ensure Ollama is not enabled or increase timeout below.")

# Optional custom forbidden ingredient list (CSV or comma-separated text)
forbidden_list_file = st.file_uploader(
    "Optional: Upload a custom forbidden ingredient CSV", type=["csv"]
)

forbidden_text = st.text_area(
    "Or paste a comma-separated forbidden ingredient list (optional)", ""
)

# Non-ingredient tokens to drop when parsing CSV (headers, risk levels)
SKIP_TOKENS = frozenset({"ingredient", "ingredients", "cas_number", "risk_level", "high", "medium", "low"})


def parse_forbidden_list(text):
    """Parse pasted text: CSV (one ingredient per row, first column) or comma-separated list."""
    if not text or not text.strip():
        return []
    text = text.strip()
    # If it looks like CSV (has newlines and commas), parse as CSV and take first column
    if "\n" in text:
        rows = list(csv.reader(StringIO(text)))
        out = []
        for row in rows:
            if not row or not row[0].strip():
                continue
            token = row[0].strip().lower()
            if token in SKIP_TOKENS:
                continue
            out.append(row[0].strip())
        return out
    return [item.strip() for item in text.split(",") if item.strip() and item.strip().lower() not in SKIP_TOKENS]


custom_forbidden = None
if forbidden_list_file is not None:
    try:
        data = forbidden_list_file.read().decode("utf-8")
        custom_forbidden = parse_forbidden_list(data)
    except Exception:
        st.warning("Could not parse the uploaded CSV file. Expecting one ingredient per row (or header 'ingredient').")

if forbidden_text:
    custom_forbidden = parse_forbidden_list(forbidden_text)

file = st.file_uploader("Upload product label", type=["pdf", "png", "jpg", "jpeg", "txt", "docx", "csv", "xlsx"])

if file is not None:
    with st.spinner("Evaluating product safety..."):
        try:
            files = {"file": (file.name, file, file.type or "application/octet-stream")}
            data = {}
            if custom_forbidden:
                data["forbidden_list"] = json.dumps(custom_forbidden)

            response = requests.post(
                "http://localhost:8000/evaluate_product",
                files=files,
                data=data,
                timeout=300,
            )

            if response.ok:
                st.subheader("Evaluation Result")
                st.json(response.json())
            else:
                st.error(f"Request failed with status {response.status_code}")
                try:
                    st.json(response.json())
                except Exception:
                    st.write(response.text)
        except requests.exceptions.RequestException as e:
            st.error(f"Error connecting to backend: {e}")

