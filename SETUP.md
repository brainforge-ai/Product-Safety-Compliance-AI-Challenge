# Setup & Run Guide

This is a two-part app: a FastAPI backend (`backend/`) and a React/Vite frontend (`frontend/`). The backend is fully functional and testable on its own with zero configuration - the frontend and the optional AI tiers are additive.

## Prerequisites

- Python 3.11+
- Node 20+
- Tesseract OCR system binary (required for image extraction - see step 2a)

## 1. Clone

```bash
git clone <repo-url>
cd Product-Safety-Compliance-AI-Challenge
```

## 2. Backend setup

### 2a. Install Tesseract (system binary, not installable via pip)

```bash
# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y tesseract-ocr
```

Verify it's on `PATH` before continuing:

```bash
tesseract --version
```

### 2b. Python virtual environment and dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements-dev.txt   # runtime deps + pytest/httpx/ruff (installs requirements.txt too)
```

Only need to run the app, not the tests? `pip install -r requirements.txt` alone is enough.

Optional - only needed to exercise the local embedding tier or the Gemini LLM tier (both off by default):

```bash
pip install -r requirements-ai.txt
```

### 2c. Environment variables

```bash
cp .env.example .env
```

The app runs correctly with the defaults in `.env.example` - every AI feature is opt-in. Flags, from `backend/.env.example`:

| Variable | Default | Needed for |
|---|---|---|
| `ENABLE_LLM_MATCHING` | `false` | Tier 6 (Gemini reasoning) + LLM extraction fallback |
| `LLM_PROVIDER` | `pydantic_ai` | - |
| `LLM_MODEL` | `google:gemini-3.1-flash-lite` | - |
| `GOOGLE_API_KEY` | *(empty)* | Required if `ENABLE_LLM_MATCHING=true` |
| `LLM_TIMEOUT_SECONDS` | `20.0` | - |
| `ENABLE_EMBEDDING_MATCHING` | `false` | Tier 5 (local semantic match) |
| `ENABLE_PERSISTENCE` | `false` | `GET /api/products` evaluation history |
| `DATABASE_URL` | `sqlite:///./data/app.db` | - |
| `MAX_UPLOAD_BYTES` | `10485760` | Per-file upload limit (10 MiB) |
| `MAX_UPLOAD_FILES` | `20` | Maximum files in one evaluation request |
| `DEFAULT_FORBIDDEN_LIST_PATH` | repo-root `forbidden_ingredients.csv` | Only set if relocating the dataset |
| `SAMPLE_DATA_DIR` | repo root | Only set if relocating the dataset |

### 2d. Run the backend

```bash
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

## 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Opens on http://localhost:5173 and proxies `/api` requests to `http://localhost:8000` (see `vite.config.ts`) - no CORS setup needed, just have the backend running too.

## 4. Example API calls

Run these from the repo root with the backend running on `:8000`.

```bash
# Health check
curl -s http://localhost:8000/api/health

# Single text-file product
curl -s -X POST http://localhost:8000/api/evaluate \
  -F "files=@texts/P-2025-0004_Ultra_Conditioner.txt" | python3 -m json.tool

# Single PDF product
curl -s -X POST http://localhost:8000/api/evaluate \
  -F "files=@pdfs/P-2025-0003_Daily_Moisturizer.pdf" | python3 -m json.tool

# Single image product (exercises OCR)
curl -s -X POST http://localhost:8000/api/evaluate \
  -F "files=@images/P-2025-0006_Pure_Lotion.png" | python3 -m json.tool

# Multiple files in one request -> batch response shape
curl -s -X POST http://localhost:8000/api/evaluate \
  -F "files=@pdfs/P-2025-0001_Pro_Moisturizer.pdf" \
  -F "files=@texts/P-2025-0005_Pro_Mask.txt" | python3 -m json.tool

# Evaluate a file already on disk, by path (relative to SAMPLE_DATA_DIR)
curl -s -X POST http://localhost:8000/api/evaluate/by-path \
  -H "Content-Type: application/json" \
  -d '{"path": "texts/P-2025-0024_Pro_Conditioner.txt"}' | python3 -m json.tool

# Evaluate all 30 sample products from product_index.csv in one call
curl -s -X POST http://localhost:8000/api/evaluate/batch-samples | python3 -m json.tool

# Current forbidden ingredient list
curl -s http://localhost:8000/api/forbidden-ingredients | python3 -m json.tool

# Replace the forbidden ingredient list (CSV upload)
curl -s -X POST http://localhost:8000/api/forbidden-ingredients \
  -F "file=@forbidden_ingredients.csv" | python3 -m json.tool
```

## 5. Running tests

```bash
# Backend
cd backend
source .venv/bin/activate
python -m pytest -q
ruff check .

# Frontend
cd frontend
npm run build     # tsc -b && vite build
npm run lint       # oxlint
```

## More detail

`docs/ARCHITECTURE.md` covers the full system design (pipeline stages, matching tiers, tradeoffs). `docs/IMPLEMENTATION_PLAN.md` and `docs/HURDLES.md` cover how it was built, phase by phase, including every bug and tradeoff found along the way.
