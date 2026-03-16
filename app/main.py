"""Product Safety AI application entry point (FastAPI)."""

import asyncio
import os
import shutil
import uuid
import json
import time
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, UploadFile, Form, File, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from .pipeline import run_pipeline
from .logger import logger


MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024)))


def _init_app_state(fastapi_app: FastAPI):
    """Initialize shared app state for health/readiness reporting."""
    fastapi_app.state.started_at = time.time()
    fastapi_app.state.startup_complete = False
    fastapi_app.state.models_ready = False
    fastapi_app.state.ocr_ready = False
    fastapi_app.state.readiness_error = None


def _ensure_app_state(fastapi_app: FastAPI):
    """Ensure app state exists even when lifespan hooks are not triggered."""
    required_attrs = ("started_at", "startup_complete", "models_ready", "ocr_ready", "readiness_error")
    if any(not hasattr(fastapi_app.state, attr) for attr in required_attrs):
        _init_app_state(fastapi_app)


def _warmup_dependencies(fastapi_app: FastAPI):
    """Warm application dependencies used on first request.

    Environment flags:
    - PRELOAD_MODELS=1: preload embedding model
    - PRELOAD_OCR=1: preload EasyOCR reader
    """
    preload_models = os.getenv("PRELOAD_MODELS", "1") == "1"
    preload_ocr = os.getenv("PRELOAD_OCR", "0") == "1"

    try:
        if preload_models:
            from .matching.embedding_matcher import get_model
            get_model()
            fastapi_app.state.models_ready = True
            logger.info("Embedding model warmup complete")
        else:
            fastapi_app.state.models_ready = True

        if preload_ocr:
            from .ingestion.image_ocr import get_ocr_reader
            get_ocr_reader()
            fastapi_app.state.ocr_ready = True
            logger.info("OCR model warmup complete")
        else:
            fastapi_app.state.ocr_ready = True

        fastapi_app.state.readiness_error = None
        fastapi_app.state.startup_complete = True
        logger.info("Application warmup complete")
        return True
    except Exception as exc:
        fastapi_app.state.readiness_error = str(exc)
        fastapi_app.state.startup_complete = False
        logger.exception("Application warmup failed")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload embedding model (and optional OCR) at startup so first request is fast."""
    _init_app_state(app)
    _warmup_dependencies(app)
    yield
    # Shutdown: nothing to clean up


app = FastAPI(lifespan=lifespan)

# Expose Prometheus metrics at /metrics so Prometheus (and Grafana) can scrape them.
Instrumentator().instrument(app).expose(app)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    """Add request tracing headers and reject oversized requests early."""
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
    request.state.request_id = request_id

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_UPLOAD_SIZE_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request too large. Max size is {MAX_UPLOAD_SIZE_BYTES} bytes.",
                        "request_id": request_id,
                    },
                )
        except ValueError:
            pass

    started = time.time()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(round(time.time() - started, 4))
    logger.info("%s %s -> %s [%s]", request.method, request.url.path, response.status_code, request_id)
    return response


def _parse_forbidden_list(forbidden_list: str):
    """Parse forbidden_list form input into a list of ingredient names.

    Supports:
    - JSON array string: ["methylparaben", "hydroquinone"]
    - Plain string: "methylparaben"
    - Comma/newline separated string: "methylparaben, hydroquinone"

    Raises:
        ValueError: If the payload is JSON but not a string/list of strings.
    """
    if forbidden_list is None:
        return None

    raw = forbidden_list.strip()
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, list):
        cleaned = [str(item).strip() for item in parsed if str(item).strip()]
        return cleaned or None

    if isinstance(parsed, str):
        raw = parsed.strip()
    elif parsed is not None:
        raise ValueError("forbidden_list must be a JSON array, JSON string, or plain text list")

    if not raw:
        return None

    if "," in raw or "\n" in raw:
        items = [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]
        return items or None

    return [raw]


def _require_forbidden_list(forbidden_list: str):
    """Parse and require a non-empty forbidden list from the request."""
    parsed = _parse_forbidden_list(forbidden_list)
    if not parsed:
        raise ValueError("forbidden_list is required and must be provided in the request")
    return parsed


@app.get("/health/live")
async def health_live():
    """Liveness probe: process is up and serving HTTP."""
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    """Readiness probe: only ready after configured warmup succeeds."""
    _ensure_app_state(app)
    ready = bool(app.state.startup_complete and app.state.models_ready and app.state.ocr_ready)
    payload = {
        "status": "ready" if ready else "not_ready",
        "startup_complete": bool(app.state.startup_complete),
        "models_ready": bool(app.state.models_ready),
        "ocr_ready": bool(app.state.ocr_ready),
        "uptime_seconds": round(time.time() - app.state.started_at, 2),
    }
    if app.state.readiness_error:
        payload["error"] = app.state.readiness_error
    status_code = 200 if ready else 503
    return JSONResponse(status_code=status_code, content=payload)


@app.post("/health/warmup")
async def health_warmup():
    """Manual warmup endpoint for startup jobs or operational workflows."""
    _ensure_app_state(app)
    success = await asyncio.to_thread(_warmup_dependencies, app)
    payload = {
        "status": "warmed" if success else "warmup_failed",
        "startup_complete": bool(app.state.startup_complete),
        "models_ready": bool(app.state.models_ready),
        "ocr_ready": bool(app.state.ocr_ready),
    }
    if app.state.readiness_error:
        payload["error"] = app.state.readiness_error
    return JSONResponse(status_code=200 if success else 503, content=payload)


def _resolve_data_path(relative_path: str):
    """Resolve path relative to data/; raise ValueError if outside."""
    from pathlib import Path
    base = (Path(__file__).resolve().parent.parent / "data").resolve()
    resolved = (base / relative_path.replace("\\", "/")).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError("Path must be under data/")
    return resolved


@app.post("/evaluate_product_path")
async def evaluate_product_path(
    request: Request,
    path: str = Form(..., description="Path relative to data/ (e.g. samples/label.png)"),
    forbidden_list: str = Form(None, description="Optional JSON array of forbidden ingredient names"),
):
    """Evaluate a product file already on the server (e.g. under data/samples/). Path is relative to data/."""
    try:
        full_path = _resolve_data_path(path)
        if not full_path.is_file():
            return JSONResponse(
                status_code=404,
                content={"detail": "File not found", "path": path, "request_id": request.state.request_id},
            )
        custom_forbidden = _require_forbidden_list(forbidden_list)
        logger.info("Evaluating server-side file path=%s request_id=%s", path, request.state.request_id)
        result = await asyncio.to_thread(run_pipeline, str(full_path), custom_forbidden)
        result["file_name"] = path
        result["request_id"] = request.state.request_id
        return result
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"detail": str(e), "request_id": request.state.request_id},
        )
    except Exception as e:
        logger.exception("evaluate_product_path failed path=%s request_id=%s", path, request.state.request_id)
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(e),
                "product_name": "Error",
                "status": "Error",
                "reason": [f"Processing failed: {str(e)}"],
                "file_name": path,
                "request_id": request.state.request_id,
            },
        )


@app.post("/evaluate_product")
async def evaluate_product(
    request: Request,
    file: UploadFile = File(..., description="Product label: PDF, image, TXT, DOCX, CSV, or XLSX"),
    forbidden_list: str = Form(None, description="Optional JSON array of forbidden ingredient names"),
):
    """Evaluate a single product file. Returns product_name, status (Accepted/Rejected), and reason list."""
    safe_name = os.path.basename(file.filename or "upload")
    path = f"temp_{uuid.uuid4().hex}_{safe_name}"
    try:
        logger.info("Evaluating uploaded file=%s request_id=%s", safe_name, request.state.request_id)
        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        custom_forbidden = _require_forbidden_list(forbidden_list)

        # Run CPU/IO-heavy pipeline in thread pool so the event loop is not blocked
        result = await asyncio.to_thread(run_pipeline, path, custom_forbidden)
        result["file_name"] = file.filename
        result["request_id"] = request.state.request_id
        return result
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"detail": str(e), "file_name": file.filename, "request_id": request.state.request_id},
        )
    except Exception as e:
        logger.exception("evaluate_product failed file=%s request_id=%s", safe_name, request.state.request_id)
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(e),
                "product_name": "Error",
                "status": "Error",
                "reason": [f"Processing failed: {str(e)}"],
                "file_name": file.filename,
                "request_id": request.state.request_id,
            },
        )
    finally:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


@app.post("/evaluate_products")
async def evaluate_products(
    request: Request,
    files: List[UploadFile] = File(
        ...,
        description="Upload multiple product files"
    ),
    forbidden_list: str = Form(None)
):
    """Batch evaluate multiple product files. Send multiple files under the same form key 'files'."""
    try:
        custom_forbidden = _require_forbidden_list(forbidden_list)
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"detail": str(e), "request_id": request.state.request_id},
        )

    results = []
    for file in files:
        safe_name = os.path.basename(file.filename or "upload")
        path = f"temp_{uuid.uuid4().hex}_{safe_name}"
        try:
            logger.info("Evaluating batch file=%s request_id=%s", safe_name, request.state.request_id)
            with open(path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            result = await asyncio.to_thread(run_pipeline, path, custom_forbidden)
            result["file_name"] = file.filename
            result["request_id"] = request.state.request_id
            results.append(result)
        except Exception as e:
            logger.exception("evaluate_products failed file=%s request_id=%s", safe_name, request.state.request_id)
            results.append({
                "product_name": "Error",
                "status": "Error",
                "reason": [f"Processing failed: {str(e)}"],
                "confidence": 0.0,
                "file_name": file.filename,
                "request_id": request.state.request_id,
            })
        finally:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    return {"results": results, "request_id": request.state.request_id}
