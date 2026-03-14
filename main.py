"""
Product Safety Compliance API
=============================
AI-powered system that evaluates product safety by checking ingredients
against a forbidden ingredients list.  Uses Claude Vision for OCR and
Claude LLM for chemical reasoning.

Run:
    uvicorn main:app --reload --port 8000
"""

import os
import shutil
import tempfile
import logging
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import DEFAULT_FORBIDDEN_CSV, BASE_DIR
from app.evaluator import evaluate_product, evaluate_batch
from app.models import EvaluationResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Product Safety Compliance API",
    description=(
        "AI-powered system to evaluate whether a product should be accepted "
        "or rejected based on forbidden chemical ingredients.  Supports PDF, "
        "images, text, CSV, Excel, JSON, and DOCX inputs."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Product Safety Compliance API",
        "docs": "/docs",
        "endpoints": ["/evaluate_product", "/evaluate_batch", "/evaluate_index"],
    }


@app.post("/evaluate_product", response_model=EvaluationResponse)
async def evaluate_single(
    file: UploadFile = File(...),
    forbidden_list: Optional[UploadFile] = File(default=None),
):
    """Evaluate a single product file.

    Upload any supported file (PDF, PNG, JPG, TXT, CSV, XLSX, JSON, DOCX)
    and optionally a custom forbidden ingredients CSV.

    Returns JSON with product_name, status (Accepted/Rejected), and reasons.
    """
    tmp_path = _save_upload(file)
    forbidden_path = _resolve_forbidden(forbidden_list)

    try:
        return evaluate_product(tmp_path, forbidden_path)
    finally:
        os.unlink(tmp_path)
        _cleanup_forbidden(forbidden_list, forbidden_path)


@app.post("/evaluate_batch", response_model=List[EvaluationResponse])
async def evaluate_many(
    files: List[UploadFile] = File(...),
    forbidden_list: Optional[UploadFile] = File(default=None),
):
    """Evaluate multiple product files in one request."""
    tmp_paths = [_save_upload(f) for f in files]
    forbidden_path = _resolve_forbidden(forbidden_list)

    try:
        return evaluate_batch(tmp_paths, forbidden_path)
    finally:
        for p in tmp_paths:
            os.unlink(p)
        _cleanup_forbidden(forbidden_list, forbidden_path)


@app.post("/evaluate_index", response_model=List[EvaluationResponse])
async def evaluate_from_index(
    forbidden_list: Optional[UploadFile] = File(default=None),
):
    """Evaluate all products listed in product_index.csv."""
    import pandas as pd
    from app.config import PRODUCT_INDEX_CSV

    if not os.path.exists(PRODUCT_INDEX_CSV):
        raise HTTPException(status_code=404, detail="product_index.csv not found")

    forbidden_path = _resolve_forbidden(forbidden_list)

    try:
        df = pd.read_csv(PRODUCT_INDEX_CSV)
        file_paths = [
            os.path.join(BASE_DIR, row["filename"])
            for _, row in df.iterrows()
        ]
        return evaluate_batch(file_paths, forbidden_path)
    finally:
        _cleanup_forbidden(forbidden_list, forbidden_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_upload(upload: UploadFile) -> str:
    """Write an uploaded file to a temporary path and return the path."""
    suffix = f"_{upload.filename}" if upload.filename else ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    shutil.copyfileobj(upload.file, tmp)
    tmp.close()
    return tmp.name


def _resolve_forbidden(upload: Optional[UploadFile]) -> str:
    """Use uploaded forbidden CSV if provided, otherwise fall back to default."""
    if upload is None:
        return DEFAULT_FORBIDDEN_CSV
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    shutil.copyfileobj(upload.file, tmp)
    tmp.close()
    return tmp.name


def _cleanup_forbidden(upload: Optional[UploadFile], path: str) -> None:
    """Remove the temporary forbidden CSV if one was uploaded."""
    if upload is not None and path != DEFAULT_FORBIDDEN_CSV:
        os.unlink(path)
