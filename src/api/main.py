"""
FastAPI application for Product Safety Compliance evaluation.

Endpoints:
- POST /evaluate_product: Evaluate a single product file (upload)
- POST /evaluate/path: Evaluate a product by file path
- POST /evaluate/batch: Evaluate multiple products from index CSV
- GET /health: Health check
"""
from __future__ import annotations
import csv
import logging
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.core.bootstrap import create_pipeline, evaluate_file
from src.core.matching import MatchPipeline
from src.core.models import BatchEvaluationResult, EvaluationResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Global pipeline instance (initialized on startup)
pipeline: Optional[MatchPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize pipeline on startup."""
    global pipeline
    logger.info("Initializing pipeline...")
    pipeline = await create_pipeline()
    logger.info("Pipeline ready")
    yield


# Create FastAPI app
app = FastAPI(
    title="Product Safety Compliance API",
    description="AI-powered system for evaluating product ingredients against forbidden substances",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EvaluateRequest(BaseModel):
    """Request body for file path evaluation."""
    file_path: str
    forbidden_path: Optional[str] = None


class BatchEvaluateRequest(BaseModel):
    """Request body for batch evaluation."""
    product_index_path: str
    data_dir: str
    forbidden_path: Optional[str] = None


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "pipeline_ready": pipeline is not None,
    }


@app.post("/evaluate_product", response_model=EvaluationResult)
async def evaluate_product(
    file: UploadFile = File(...),
    forbidden_file: Optional[UploadFile] = File(None),
):
    """
    Evaluate a single product file.

    Accepts PDF, PNG, JPG, or TXT files.
    Optionally accepts a custom forbidden ingredients CSV.
    Returns evaluation result with Accept/Reject status and reasons.
    """
    # Determine which pipeline to use
    eval_pipeline = pipeline

    # If custom forbidden file provided, create a temporary pipeline
    if forbidden_file:
        suffix = Path(forbidden_file.filename).suffix
        if suffix.lower() != ".csv":
            raise HTTPException(status_code=400, detail="Forbidden file must be CSV")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_forbidden:
            forbidden_content = await forbidden_file.read()
            tmp_forbidden.write(forbidden_content)
            tmp_forbidden_path = Path(tmp_forbidden.name)

        try:
            eval_pipeline = await create_pipeline(forbidden_path=tmp_forbidden_path)
        except Exception as e:
            tmp_forbidden_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"Invalid forbidden CSV: {e}")

    if not eval_pipeline:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Save uploaded product file to temp location
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = await evaluate_file(eval_pipeline, tmp_path)
        # Override filename with original
        result.filename = file.filename
        return result

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        tmp_path.unlink(missing_ok=True)
        if forbidden_file and 'tmp_forbidden_path' in locals():
            tmp_forbidden_path.unlink(missing_ok=True)


@app.post("/evaluate/path", response_model=EvaluationResult)
async def evaluate_product_by_path(request: EvaluateRequest):
    """
    Evaluate a product by file path.

    Optionally specify a custom forbidden ingredients CSV path.
    For use when files are already on disk (e.g., during batch evaluation).
    """
    # Determine which pipeline to use
    eval_pipeline = pipeline

    if request.forbidden_path:
        forbidden_path = Path(request.forbidden_path)
        if not forbidden_path.exists():
            raise HTTPException(status_code=404, detail=f"Forbidden file not found: {forbidden_path}")
        try:
            eval_pipeline = await create_pipeline(forbidden_path=forbidden_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid forbidden CSV: {e}")

    if not eval_pipeline:
        raise HTTPException(status_code=503, detail="Service not initialized")

    file_path = Path(request.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    try:
        return await evaluate_file(eval_pipeline, file_path)

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate/batch", response_model=BatchEvaluationResult)
async def evaluate_batch(request: BatchEvaluateRequest):
    """
    Evaluate all products from a product index CSV.

    The product_index_path should point to a CSV with columns: product_id, filename
    The data_dir should contain the product files referenced in the index.
    Optionally specify a custom forbidden ingredients CSV path.

    Returns summary with counts for requested, evaluated, and skipped files.
    """
    # Determine which pipeline to use
    eval_pipeline = pipeline

    if request.forbidden_path:
        forbidden_path = Path(request.forbidden_path)
        if not forbidden_path.exists():
            raise HTTPException(status_code=404, detail=f"Forbidden file not found: {forbidden_path}")
        try:
            eval_pipeline = await create_pipeline(forbidden_path=forbidden_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid forbidden CSV: {e}")

    if not eval_pipeline:
        raise HTTPException(status_code=503, detail="Service not initialized")

    index_path = Path(request.product_index_path)
    data_dir = Path(request.data_dir)

    if not index_path.exists():
        raise HTTPException(status_code=404, detail=f"Index not found: {index_path}")

    start_time = time.time()
    results = []
    skipped = 0
    errors = 0

    # Read product index
    with open(index_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        products = list(reader)

    requested = len(products)
    logger.info(f"Evaluating {requested} products from {index_path}")

    for product in products:
        filename = product.get("filename", "")

        file_path = data_dir / filename
        if not file_path.exists():
            logger.warning(f"File not found, skipping: {file_path}")
            skipped += 1
            continue

        try:
            result = await evaluate_file(eval_pipeline, file_path)
            results.append(result)

        except Exception as e:
            logger.error(f"Failed to evaluate {filename}: {e}")
            errors += 1

    total_duration_ms = (time.time() - start_time) * 1000

    return BatchEvaluationResult(
        requested=requested,
        evaluated=len(results),
        skipped=skipped,
        errors=errors,
        accepted=sum(1 for r in results if r.status.value == "Accepted"),
        rejected=sum(1 for r in results if r.status.value == "Rejected"),
        results=results,
        total_duration_ms=total_duration_ms,
    )
