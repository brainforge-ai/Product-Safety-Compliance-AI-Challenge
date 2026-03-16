# Product Safety Compliance AI

AI-powered system that evaluates whether a product should be **Accepted** or **Rejected** based on the presence of forbidden chemical ingredients. It ingests product data from PDFs, images, CSVs, and text, extracts ingredients, and compares them against a configurable forbidden-ingredient list.

## Features

- **Multi-format ingestion**: PDFs (product labels), images (OCR), TXT, DOCX, CSV, XLSX
- **Robust extraction**: Handles unstructured and OCR text; optional LLM fallback when regex extraction finds no ingredients
- **Naming variations**: Embedding-based matching + PubChem synonym expansion (e.g. "Glucose" vs "D-Glucopyranose")
- **Custom forbidden list**: Upload a CSV or paste a comma-separated list; no hardcoded lists
- **REST API**: `POST /evaluate_product` (single file) and `POST /evaluate_products` (batch)
- **Optional UI**: Streamlit dashboard for upload and evaluation
- **Monitoring**: Prometheus metrics at `/metrics` for Grafana or other scrapers

## Architecture overview

```text
Input files
  ├─ TXT / DOCX / CSV / XLSX
  ├─ PDF
  └─ Images
        |
        v
File ingestion layer
  ├─ text readers
  ├─ PDF parser
  ├─ OCR for images
  └─ structured table loaders
        |
        v
Raw extracted text
        |
        v
Ingredient parsing
  ├─ product name extraction
  ├─ ingredient list extraction
  └─ normalization / cleanup
        |
        v
Forbidden list preparation
  ├─ API-provided custom forbidden list
  ├─ cleanup of headers / invalid values
  └─ optional PubChem synonym expansion
        |
        v
Matching engine
  ├─ exact/normalized preservation of clear matches
  ├─ embedding similarity matching
  └─ optional LLM validation for borderline matches
        |
        v
Decision engine
  ├─ Accepted
  ├─ Rejected
  └─ confidence score + reasons
        |
        v
Outputs
  ├─ FastAPI JSON response
  ├─ health/readiness endpoints
  └─ metrics + request tracing
```

## Request flow diagram

```text
Client request
    |
    v
FastAPI endpoint
    |
    +--> request size guard
    +--> request ID + timing middleware
    |
    v
Temporary file / server-side path resolution
    |
    v
Pipeline runner
    |
    +--> file loader
    +--> ingredient parser
    +--> normalization
    +--> forbidden list expansion
    +--> matching
    +--> decision engine
    |
    v
JSON result
    |
    +--> status
    +--> reasons
    +--> confidence
    +--> request_id
```

## Quick start

### 1. Setup

```bash
cd "Product Safety AI"
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### 2. Run the API

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs: http://127.0.0.1:8000/docs  
- Liveness: http://127.0.0.1:8000/health/live  
- Readiness: http://127.0.0.1:8000/health/ready  
- Metrics: http://127.0.0.1:8000/metrics  
- Grafana: http://localhost:3000/

### 3. (Optional) Run the UI

```bash
streamlit run streamlit_app.py
```

Upload a product label (image/PDF/text) and optionally a forbidden-ingredients CSV. The first request may take 1–2 minutes while the embedding model loads; later requests are faster.

### 4. Evaluate a product via API

**Upload a file:**

```bash
curl -X POST "http://127.0.0.1:8000/evaluate_product" \
  -F "file=@path/to/label.png" \
  -F "forbidden_list=[\"hydroquinone\",\"methylparaben\"]"
```

**Evaluate a file already under `data/` (e.g. from `samples/`):**

```bash
curl -X POST "http://127.0.0.1:8000/evaluate_product_path" \
  -F "path=samples/label.png"
```

Response format:

```json
{
  "product_name": "Example Product",
  "status": "Rejected",
  "reason": ["Contains hydroquinone", "Contains methylparaben"],
  "confidence": 0.92,
  "file_name": "label.png"
}
```

## Configuration

| Environment variable | Description |
|----------------------|-------------|
| `ENABLE_LLM_REASONING` | Set to `1` to enable LLM fallback for ingredient extraction and optional match validation (requires Ollama). Default: `0`. |
| `OLLAMA_HOST` | Ollama API base URL. Default: `http://localhost:11434`. |
| `OLLAMA_TIMEOUT` | Timeout in seconds for Ollama requests. Default: `25`. |
| `LLM_MODEL` | Ollama model name. Default: `llama3`. |
| `PRELOAD_MODELS` | Set to `1` to preload the embedding model at startup (recommended). Default: `1`. |
| `PRELOAD_OCR` | Set to `1` to preload the OCR reader at startup and include it in readiness checks. Default: `0`. |
| `MAX_UPLOAD_SIZE_BYTES` | Reject requests larger than this size with HTTP 413. Default: `10485760` (10 MB). |
| `ENABLE_PUBCHEM_SYNONYMS` | Set to `1` to enable live PubChem synonym/CAS expansion. Default: `0` for safer production behavior. |


The API is now improved for production-oriented deployments with:

- liveness and readiness endpoints for Kubernetes probes
- startup dependency warmup for model/OCR loading
- Prometheus metrics at `/metrics`
- request tracing via `X-Request-ID` and `X-Process-Time`
- upload-size guardrails through `MAX_UPLOAD_SIZE_BYTES`
- structured logging around startup and request execution

Remaining production work is mainly deployment/configuration focused:

- run behind a production ASGI process model in deployment (for example Gunicorn + Uvicorn workers on Linux)
- add Kubernetes manifests/Helm values if you plan to deploy to K8s
- configure CPU/memory requests and limits for model and OCR workloads
- persist or pre-bake model caches into the container image to reduce cold starts
- expand automated tests beyond the current API coverage to include broader integration/deployment scenarios
- add centralized logging/error monitoring such as Sentry, Datadog, or ELK
- review whether live PubChem lookups are acceptable for your latency/SLA needs; keep them disabled by default for production stability

- The forbidden list is supplied only via the API or UI (upload CSV or paste comma-separated list). No default list is loaded from the repo.
- Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (runs on CPU if no GPU).
- LLM is optional; the system works without Ollama using regex + "Contains:" fallback + embeddings.

## Matching tiers

The current project uses a layered matching strategy designed to balance recall, precision, and runtime cost.

### Tier 1: Ingredient extraction and normalization

- product text is extracted from the uploaded file
- ingredients are parsed from the extracted text
- tokens are normalized before matching
- obvious noise, very short fragments, and CAS-only values can be filtered out

This stage reduces OCR junk and formatting differences before semantic comparison begins.

### Tier 2: Embedding-based similarity matching

- normalized product ingredients are compared against the prepared forbidden list
- sentence-transformer embeddings are used to find the best semantic match
- only strong matches above the configured similarity threshold are accepted
- synonym-expanded forbidden terms can still map back to one canonical forbidden ingredient in the output

This is the main matching tier in the current implementation.

### Tier 3: Optional LLM-assisted validation / fallback

- if no ingredients are extracted, the system can optionally call the LLM to help recover ingredient names from raw text
- for strong embedding candidates, the LLM can optionally validate whether an ingredient really corresponds to a forbidden chemical
- LLM use is disabled by default and must be enabled explicitly with `ENABLE_LLM_REASONING=1`

This keeps the default system cheaper and more stable, while still allowing model-assisted reasoning when needed.

## Current decision model

```text
Extract text
   -> Parse ingredients
      -> Normalize ingredients
         -> Prepare forbidden list
            -> Match ingredients to forbidden terms
               -> If matches found: Rejected
               -> Else: Accepted
```

At the moment, the project returns `Accepted` or `Rejected`. A future enhancement would be adding a `Needs Review` state for low-confidence OCR or ambiguous extraction cases.

## Testing

Run the API tests with:

```bash
pytest -q
```

## Docker

Build and run the production container:

```bash
docker build -t product-safety-ai .
docker run -p 8000:8000 product-safety-ai
```

## Kubernetes probe examples

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 15

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  failureThreshold: 6
```

## Requirements

See `requirements.txt`. Key dependencies: FastAPI, sentence-transformers, EasyOCR, pdfplumber, pandas, pubchempy, prometheus-fastapi-instrumentator.
