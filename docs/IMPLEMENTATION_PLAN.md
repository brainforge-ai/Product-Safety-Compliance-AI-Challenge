# Phased Implementation Plan

This plan breaks the build described in `docs/ARCHITECTURE.md` into small, independently verifiable phases. Every phase ends with the same three steps: run the test suite, run a manual verification pass, then commit. No phase should be considered done until its tests pass and its commit is made; the next phase should not start on top of an unverified one.

**Convention used below:**
- **Sub-tasks**: concrete implementation steps for the phase.
- **Technical notes**: implementation details, gotchas, and references back to `docs/ARCHITECTURE.md`.
- **Verification**: what to run/check before committing.
- **Commit**: the commit message to use once verification passes.

---

## Phase 0: Repository & Environment Scaffolding

**Goal:** A running, empty-but-real FastAPI app with the full folder layout in place, so every later phase has a home to slot code into.

**Sub-tasks:**
- Create the `backend/` and `frontend/` directory skeletons matching Section 9 of `ARCHITECTURE.md` (empty `__init__.py` files for now).
- Create a Python virtual environment (`python3.11 -m venv .venv`) and a `requirements.txt` with the core runtime deps: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`.
- Add a `.gitignore` covering `.venv/`, `__pycache__/`, `*.db`, `.env`, `node_modules/`, `dist/`, `.pytest_cache/`.
- Add Ruff configuration (`pyproject.toml` `[tool.ruff]` section or `ruff.toml`).
- Add `.env.example` listing every config flag from `ARCHITECTURE.md` Sections 7 and 8 (`ENABLE_LLM_MATCHING`, `LLM_PROVIDER`, `LLM_MODEL`, `GOOGLE_API_KEY`, `ENABLE_PERSISTENCE`, `DATABASE_URL`, `ENABLE_EMBEDDING_MATCHING`), all with safe defaults or placeholders.
- Build a minimal FastAPI app (`app/main.py`) with an app factory and a single `GET /api/v1/health` route.
- Add `pytest` and `httpx` as dev dependencies, with a first smoke test hitting `/api/v1/health`.

**Technical notes:**
- Keep `app/main.py` as just wiring (app factory, router mounting, lifespan hook placeholder); no business logic lives here per the ports-and-adapters principle in Section 3.
- The `.env.example` should be safe to commit; the real `.env` (with a live `GOOGLE_API_KEY`) must be gitignored.

**Verification:**
- `pip install -r requirements.txt` succeeds inside the venv.
- `uvicorn app.main:app --reload` boots without error.
- `curl localhost:8000/api/v1/health` returns `200`.
- `pytest` passes (the health smoke test).
- `ruff check .` passes with no errors.

**Commit:** `chore: scaffold backend project structure and FastAPI health check`

---

## Phase 1: Domain Models, Settings, and Cross-Cutting Concerns

**Goal:** The framework-free vocabulary (Pydantic models, settings, logging, exceptions) that every later phase will build on.

**Sub-tasks:**
- Define core domain models (`domain/models.py`): `ExtractedProduct`, `Ingredient`, `MatchResult` (with `method` and `confidence`), `EvaluationResult` matching the API contract in Section 10 of `ARCHITECTURE.md`.
- Define a `MatchMethod` enum: `exact`, `formula`, `fuzzy`, `acronym`, `embedding`, `llm`.
- Add `core/config.py` with a `pydantic-settings` `Settings` class reading every flag listed in Phase 0's `.env.example`.
- Add `core/logging.py` with a basic structured logging setup (standard library `logging`, configured via `dictConfig`).
- Add `core/exceptions.py`: `ExtractionError`, `ParsingError`, `UnsupportedFileTypeError`, `MatchingError`, mapped later to HTTP error responses at the API layer.

**Technical notes:**
- `Settings` should have sane defaults for everything except secrets (`GOOGLE_API_KEY` defaults to `None`, `ENABLE_LLM_MATCHING` defaults to `False` so the app works with zero configuration).
- Domain models must not import anything from `fastapi`, `sqlmodel`, or the LLM client, per the ports-and-adapters principle.

**Verification:**
- `pytest` passes for new unit tests covering: settings defaults, settings overrides via environment variables, and model validation (e.g. `EvaluationResult.status` only accepts `Accepted`/`Rejected`).
- `ruff check .` passes.

**Commit:** `feat: add domain models, settings, logging, and exception types`

---

## Phase 2: File Extraction Layer

**Goal:** Given any of the four supported file types, produce a raw text blob (or structured rows, for CSV).

**Sub-tasks:**
- Copy the provided sample dataset (`images/`, `pdfs/`, `texts/`, `product_index.csv`, `forbidden_ingredients.csv`) into `backend/tests/fixtures/` so tests are self-contained and reproducible.
- Implement `domain/extraction/base.py`: an `Extractor` protocol (`extract(path) -> str`).
- Implement `domain/extraction/detector.py`: file-type detection by extension with a content-sniffing fallback.
- Implement `pdf_extractor.py` (PyMuPDF/`fitz` text extraction, with page rasterization + OCR fallback if extracted text is empty, per the `OCRFALL` node in Section 5).
- Implement `image_extractor.py` (`pytesseract` + Pillow).
- Implement `text_extractor.py` (direct file read).
- Implement `csv_extractor.py` (row parsing into a list of dicts).

**Technical notes:**
- Tesseract must be installed as a system binary before these tests will pass (`brew install tesseract` on macOS, `apt-get install tesseract-ocr` on Linux). Note this explicitly in the setup guide during Phase 10, and treat a missing binary as a clear, actionable startup/test error rather than a silent failure.
- Extraction results should be cacheable by content hash (per Section 12), but the cache itself can be introduced in Phase 8 alongside the LLM cache; for now, extractors just need to be pure functions of file bytes.

**Verification:**
- `pytest` passes for extractor unit tests run against all 30 sample files (10 pdf, 10 image, 10 text; CSV tested with a small synthetic fixture since the sample set has no per-product CSV file).
- Spot-check OCR output quality manually on 2-3 images to confirm ingredient text is legible.
- `ruff check .` passes.

**Commit:** `feat: implement multi-format file extraction layer (pdf, image, text, csv)`

---

## Phase 3: Structured Parsing Layer

**Goal:** Turn a raw text blob into a populated `ExtractedProduct` (name, SKU, description, ingredient list).

**Sub-tasks:**
- Implement `domain/parsing/product_parser.py`: regex/heuristic extraction of `Product ID`, `Product Name`, `SKU`, `Description`, and the `Ingredients / Chemical Formulas:` section; tokenize the ingredient list (strip bullets, dashes, numbering, whitespace).
- Handle the CSV extractor's row-shaped output as a distinct parsing path (map row columns to the same `ExtractedProduct` shape).
- Add a `needs_llm_fallback` flag on the parse result for when no ingredients section is found; wire the actual LLM-based extraction fallback in Phase 8 (leave a clear `TODO` and an interface stub for now, not a real implementation).
- Build `tests/fixtures/expected_ingredients.json`: manually verified expected ingredient lists for all 30 sample products, used as the ground truth for parser tests.

**Technical notes:**
- Keep the parser tolerant of minor formatting differences (extra whitespace, different bullet characters) since the hidden evaluation set is not guaranteed to match the sample formatting exactly.

**Verification:**
- `pytest` passes: parsed `product_name`, `sku`, and ingredient lists match `expected_ingredients.json` for all 30 samples.
- `ruff check .` passes.

**Commit:** `feat: add structured product and ingredient field parser`

---

## Phase 4: Normalization & Molecular Formula Parser

**Goal:** Canonicalize ingredient strings so downstream matching tiers compare apples to apples.

**Sub-tasks:**
- Implement `domain/normalization/text_normalizer.py`: lowercase, strip punctuation/whitespace, Unicode normalize.
- Implement `domain/normalization/formula_parser.py`: tokenize formulas like `C6H6` or `H2O2` into a sorted `{element: count}` dict; provide an `is_formula(text) -> bool` heuristic and a formula-equality comparison function that is order-independent (`H2O2` equals `O2H2`).

**Technical notes:**
- The formula parser only needs to handle simple flat formulas (no nested parentheses/hydrates) since that is what appears in the dataset; document this as a known limitation rather than over-engineering it.

**Verification:**
- `pytest` passes: normalization idempotency tests, formula equivalence tests (including reordered element sequences), and rejection of non-formula strings (e.g. `"Sodium Hydroxide"` is not treated as a formula).
- `ruff check .` passes.

**Commit:** `feat: add text normalizer and molecular formula canonicalization`

---

## Phase 5: Rule-Based Matching Pipeline (Tiers 1-4) & Decision Engine

**Goal:** The deterministic backbone of the system: exact, formula, fuzzy, and acronym matching, composed into a pipeline, feeding an accept/reject decision.

**Sub-tasks:**
- Implement `domain/matching/base.py`: a `Matcher` protocol (`match(ingredient, forbidden_entry) -> MatchResult | None`).
- Implement `exact_matcher.py`, `formula_matcher.py` (using Phase 4's formula parser), `fuzzy_matcher.py` (`rapidfuzz` token/partial ratio with a configurable threshold), and `acronym_matcher.py` (initials-based heuristic, not a hardcoded lookup table).
- Implement `domain/matching/pipeline.py`: a `MatchPipeline` that runs matchers in order and short-circuits on the first confident match; built to accept an extensible list of matchers so tiers 5-6 can be registered later without changing this code.
- Implement `domain/decision/engine.py`: aggregates per-ingredient `MatchResult`s into an `EvaluationResult` (`Accepted`/`Rejected` plus `reason` strings in the `"Contains X"` format from the README).
- Implement `domain/forbidden_list/repository.py`: a CSV-backed repository that loads the default forbidden list and supports in-memory replacement (persistence of uploaded lists is wired in Phase 6).

**Technical notes:**
- The acronym matcher must compute initials generically from any multi-word forbidden ingredient name; it must not contain any dataset-specific lookup table (per the generalization principle in Section 3).
- Include the README's `Glucose` vs `D-Glucopyranose` example as an explicit synthetic test case for the fuzzy tier, since it doesn't occur in the sample dataset itself.

**Verification:**
- `pytest` passes: isolated tests per matcher tier (including the `BHA` vs `Butylated Hydroxyanisole` acronym case and the `Glucose`/`D-Glucopyranose` fuzzy case), a full-pipeline test on a synthetic ingredient/forbidden list, and decision-engine tests for both `Accepted` and `Rejected` outcomes.
- Manual end-to-end run: pipe all 30 real sample products (post-Phase-3 parsing) through the tiers 1-4 pipeline against the real `forbidden_ingredients.csv` and spot-check that products containing `Coumarin`, `Propylparaben`, `BHT`, etc. are correctly flagged.
- `ruff check .` passes.

**Commit:** `feat: implement tiered rule-based ingredient matcher and decision engine`

---

## Phase 6: Persistence Layer (Toggleable SQLite)

**Goal:** Evaluation history and forbidden-list versioning, fully removable via one flag.

**Sub-tasks:**
- Implement `infra/db/models.py`: SQLModel tables `EvaluationRecord` and `ForbiddenListVersion`.
- Implement `infra/db/session.py`: engine/session factory reading `DATABASE_URL`.
- Implement an `EvaluationRepository` protocol with two implementations: `SqliteEvaluationRepository` and `NoopEvaluationRepository`.
- Wire selection between the two implementations at startup based on `ENABLE_PERSISTENCE`, via dependency injection (not an `if` scattered through service code).
- Use `SQLModel.metadata.create_all()` at startup for schema bootstrap; a full Alembic migration setup is out of scope given the project's size.

**Technical notes:**
- The forbidden-list repository from Phase 5 stays in-memory when persistence is off; when persistence is on, uploaded forbidden lists are additionally versioned and stored via `ForbiddenListVersion`.

**Verification:**
- `pytest` passes: a repository round-trip test with `ENABLE_PERSISTENCE=true` against a temporary/in-memory SQLite database, and a test confirming `NoopEvaluationRepository` performs no writes and requires no database.
- Manual check: toggling `ENABLE_PERSISTENCE` between `true`/`false` and restarting the app produces no code changes, only different DI wiring.
- `ruff check .` passes.

**Commit:** `feat: add toggleable SQLite persistence for evaluation history and forbidden list versions`

---

## Phase 7: API Layer

**Goal:** Wire everything built so far behind the REST endpoints defined in Section 10 of `ARCHITECTURE.md`.

**Sub-tasks:**
- Define request/response schemas in `api/v1/schemas/` mirroring the exact JSON contract from the challenge README plus the additive `matches` field.
- Implement routers: `routes_health.py`, `routes_evaluate.py` (`/evaluate`, `/evaluate/batch`, `/evaluate/by-path`, `/evaluate/batch-samples`), `routes_forbidden_list.py` (`GET`/`POST /forbidden-ingredients`).
- Implement `services/evaluation_service.py`: orchestrates extraction, parsing, normalization, matching, decisioning, and (optionally) persistence for a single product; a batch variant runs multiple products concurrently with a bounded `asyncio.Semaphore`.
- Implement `services/forbidden_list_service.py`: handles CSV upload/validation and delegates to the forbidden-list repository.
- Wire dependency injection for repositories and services, and flesh out the FastAPI lifespan hook in `main.py` (create DB tables if persistence is enabled, load the default forbidden list).

**Technical notes:**
- Blocking extraction/OCR work must run via FastAPI's threadpool (`run_in_threadpool`), not directly on the event loop, per Section 12.
- The `/evaluate/batch-samples` endpoint reads `product_index.csv` and evaluates every mapped file in one call; per-file errors must be isolated so one bad file doesn't fail the whole batch.

**Verification:**
- `pytest` passes: `TestClient`-based integration tests hitting `/evaluate` for each of the 30 sample files, a `/evaluate/batch-samples` test, `GET`/`POST /forbidden-ingredients` tests, and a contract test asserting the response shape exactly matches the README's example JSON.
- Manual check: run the app, open `/docs`, and manually exercise a couple of endpoints with `curl`.
- `ruff check .` passes.

**Commit:** `feat: add FastAPI REST layer wiring extraction, matching, and decision pipeline end-to-end`

---

## Phase 8: Optional AI Tiers (Local Embeddings + Gemini via Pydantic AI)

**Goal:** Add tiers 5 and 6 from Section 6 of `ARCHITECTURE.md`, fully feature-flagged and never required for the system to function.

**Sub-tasks:**
- Implement `matching/embedding_matcher.py`: a `sentence-transformers` (MiniLM) cosine-similarity tier, model loaded once as a lazy singleton at startup, gated by `ENABLE_EMBEDDING_MATCHING`.
- Implement `infra/llm/base.py`: an `LLMClient` protocol.
- Implement `infra/llm/pydantic_ai_client.py`: the concrete adapter using a Pydantic AI `Agent(model="google:gemini-3.1-flash-lite", output_type=LLMMatchResponse)`, per the design in Section 7.
- Implement `matching/llm_matcher.py`: tier 6, batching all of a product's unresolved ingredients into one call, applying the cache-then-call-then-cache pattern, and failing open (treat as no-match, log a warning) on error or timeout.
- Implement `infra/cache/llm_response_cache.py`: keyed by `(normalized_ingredient, forbidden_list_version)`.
- Register tiers 5 and 6 into the `MatchPipeline` from Phase 5, behind their respective flags.

**Technical notes:**
- Per Section 13, the LLM matcher must be tested with a mocked `LLMClient`; the automated test suite must never depend on network access or spend real Gemini credits.
- A manual, opt-in smoke test against the real Gemini API (with a real `GOOGLE_API_KEY` set locally) is worth doing once by hand to confirm the end-to-end integration works, but this is not part of the committed test suite.

**Verification:**
- `pytest` passes fully offline (LLM client mocked, embedding model either mocked or run locally with no network calls).
- Manual smoke test: with a real `GOOGLE_API_KEY`, run one product with a deliberately obscure ingredient synonym through the full pipeline and confirm tier 6 produces a sensible match.
- `ruff check .` passes.

**Commit:** `feat: add optional embedding and Gemini (Pydantic AI) matching tiers with caching`

---

## Phase 9: Frontend Application

**Goal:** A lean React UI covering evaluate, results, and forbidden-list management.

**Sub-tasks:**
- Scaffold a Vite + React + TypeScript app in `frontend/`.
- Set up Tailwind CSS.
- Build a typed API client (`frontend/src/api/`) plus TanStack Query hooks for the evaluate, batch-samples, and forbidden-ingredients endpoints.
- Build pages: **Evaluate** (single file upload + a "run all samples" button), **Results** (table with status badges and expandable match explanations), **ForbiddenList** (view current list, upload a replacement CSV).

**Technical notes:**
- Given the project's time budget, a single-page app with tab-based navigation between the three views is preferred over a full multi-route setup, per the open question resolved informally in `ARCHITECTURE.md`.

**Verification:**
- `npm run build` succeeds; `npm run lint` passes.
- Manual click-through against a running backend: evaluate a couple of individual sample files, run the batch-samples flow, and upload a replacement forbidden list, confirming the UI reflects each result correctly.

**Commit:** `feat: add React frontend for evaluate, results, and forbidden-list management`

---

## Phase 10: Documentation, Packaging, and Final Validation

**Goal:** Everything needed for someone else to clone the repo and run it successfully, plus a final end-to-end sanity pass.

**Sub-tasks:**
- Write a root-level setup/run guide (venv activation, `pip install -r requirements.txt`, the Tesseract system-binary install step, required `.env` values, `npm install`/`npm run dev`, example `curl` calls).
- Add a minimal Dockerfile for the backend (and optionally the frontend) as a documented stretch goal, consistent with the venv-first decision in `ARCHITECTURE.md` Section 11.
- Run the full backend test suite and the frontend build one final time, together.
- Run `/evaluate/batch-samples` against all 30 provided sample files and manually review the Accept/Reject decisions for sanity.
- Write `docs/LOOM_NOTES.md`: a short talking-points outline for the required Loom walkthrough (architecture summary, key tradeoffs, live demo script).

**Verification:**
- Full `pytest` suite green; frontend build green.
- Batch evaluation of all 30 samples completes without errors and produces sane-looking decisions.
- Following the setup guide from a clean terminal (fresh venv, fresh `npm install`) successfully reproduces a working app.

**Commit:** `docs: add setup guide, Loom talking points, and final validation pass`
