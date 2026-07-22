# Phased Implementation Plan

This plan breaks the build described in `docs/ARCHITECTURE.md` into small, independently verifiable phases. Every phase ends with the same three steps: run the test suite, run a manual verification pass, then commit. No phase should be considered done until its tests pass and its commit is made; the next phase should not start on top of an unverified one.

**Commit policy:** commits are gated on explicit user permission. Each phase below still lists a suggested commit message for when that permission is given, but the agent must not run `git commit` (or `git add` in preparation for one) at the end of a phase by default. Verification (tests + manual checks) still happens at the end of every phase regardless; only the act of committing waits for a go-ahead.

**Convention used below:**
- **Sub-tasks**: concrete implementation steps for the phase.
- **Technical notes**: implementation details, gotchas, and references back to `docs/ARCHITECTURE.md`.
- **Verification**: what to run/check before committing.
- **Commit**: the suggested commit message, to be used only once the user explicitly grants permission to commit.

---

## Phase 0: Repository & Environment Scaffolding

**Status:** Done

**Goal:** A running, empty-but-real FastAPI app with the full folder layout in place, so every later phase has a home to slot code into.

**Sub-tasks:**
- Create the `backend/` and `frontend/` directory skeletons matching Section 9 of `ARCHITECTURE.md` (empty `__init__.py` files for now).
- Create a Python virtual environment (`python3.11 -m venv .venv`) and a `requirements.txt` with the core runtime deps: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`.
- Add a `.gitignore` covering `.venv/`, `__pycache__/`, `*.db`, `.env`, `node_modules/`, `dist/`, `.pytest_cache/`.
- Add Ruff configuration (`pyproject.toml` `[tool.ruff]` section or `ruff.toml`).
- Add `.env.example` listing every config flag from `ARCHITECTURE.md` Sections 7 and 8 (`ENABLE_LLM_MATCHING`, `LLM_PROVIDER`, `LLM_MODEL`, `GOOGLE_API_KEY`, `ENABLE_PERSISTENCE`, `DATABASE_URL`, `ENABLE_EMBEDDING_MATCHING`), all with safe defaults or placeholders.
- Build a minimal FastAPI app (`app/main.py`) with an app factory and a single `GET /api/health` route.
- Add `pytest` and `httpx` as dev dependencies, with a first smoke test hitting `/api/health`.
- Confirm Swagger UI is served at `/docs` (FastAPI's default; explicitly set `docs_url`/`redoc_url`/`openapi_url` in the app factory for clarity) with a test asserting `/docs` and `/openapi.json` respond.

**Technical notes:**
- Keep `app/main.py` as just wiring (app factory, router mounting, lifespan hook placeholder); no business logic lives here per the ports-and-adapters principle in Section 3.
- The `.env.example` should be safe to commit; the real `.env` (with a live `GOOGLE_API_KEY`) must be gitignored.

**Verification:**
- `pip install -r requirements.txt` succeeds inside the venv.
- `uvicorn app.main:app --reload` boots without error.
- `curl localhost:8000/api/health` returns `200`.
- `curl localhost:8000/docs` returns `200` (Swagger UI).
- `pytest` passes (the health smoke test).
- `ruff check .` passes with no errors.

**Commit:** `chore: scaffold backend project structure and FastAPI health check`

---

## Phase 1: Domain Models, Settings, and Cross-Cutting Concerns

**Status:** Done

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

**Status:** Done

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

**Status:** Done

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

**Status:** Done

**Goal:** Canonicalize ingredient strings so downstream matching tiers compare apples to apples.

**Sub-tasks:**
- Implement `domain/normalization/text_normalizer.py`: lowercase, strip punctuation/whitespace, Unicode normalize.
- Implement `domain/normalization/formula_parser.py`: tokenize formulas like `C6H6` or `H2O2` into a sorted `{element: count}` dict; provide an `is_formula(text) -> bool` heuristic and a formula-equality comparison function that is order-independent (`H2O2` equals `O2H2`).

**Technical notes:**
- The formula parser only needs to handle simple flat formulas (no nested parentheses/hydrates) since that is what appears in the dataset; document this as a known limitation rather than over-engineering it.
- **OCR formula corruption (observed in Phase 2 spot-checks):** Tesseract reliably misreads capital `O` as digit `0` in formulas (`H2O2` → `H202`, `C8H10N4O2` → `C8H10N402`), and occasionally misreads a leading `C` as `€` (`C12H24O12` → `€12H24012`). Since `forbidden_ingredients.csv` contains formula entries, an uncorrected misread on a scanned product causes a false **Accept** — the worst-case failure for a compliance system. Real corrupted samples are captured in `backend/tests/fixtures/ocr_formula_corruption_samples.json`.
  - **Correction does NOT belong in this phase's parser.** `parse_formula` must stay strict (no guessing): context-free, a corrupted string like `C20H4002` is genuinely ambiguous (`H:4002` vs `H:40,O:2` vs `H:4,O:2` are all syntactically valid parses; neither fewest-edits nor smallest-count breaks the tie). `is_formula`/`parse_formula` should stay permissive enough that corrupted strings are still *recognized as formula-shaped* (so they route into the formula matching tier at all), but must not attempt to resolve which correction is "true".
  - **Correction belongs in Phase 5's formula matcher instead**, where the ambiguity is decidable: given a specific forbidden-list formula to test against, try `0→O` (and `€→C`) corrected variants of the product ingredient and check whether *any* variant's strict parse equals that forbidden formula. The forbidden list is the oracle that disambiguates; a wrong variant simply fails to match rather than needing to be identified as wrong up front.
  - Discriminating regression check for Phase 5: sample product **P-2025-0026 (Radiant Sunscreen)** must come out **Rejected** — its only forbidden ingredient is OCR-corrupted `H202` (true `H2O2`), and every other ingredient is clean, so its Accept/Reject outcome flips entirely on this correction working (P-2025-0007/0029 also carry a corrupted formula but have another *clean-text* forbidden ingredient too, so they'd reject regardless — 0026 is the true canary). Confirm it's caught via the formula tier specifically, not incidentally by fuzzy matching.

**Verification:**
- `pytest` passes: normalization idempotency tests, formula equivalence tests (including reordered element sequences), and rejection of non-formula strings (e.g. `"Sodium Hydroxide"` is not treated as a formula).
- `ruff check .` passes.

**Commit:** `feat: add text normalizer and molecular formula canonicalization`

---

## Phase 5: Rule-Based Matching Pipeline (Tiers 1-4) & Decision Engine

**Status:** Done

**Goal:** The deterministic backbone of the system: exact, formula, fuzzy, and acronym matching, composed into a pipeline, feeding an accept/reject decision.

**Sub-tasks:**
- Implement `domain/matching/base.py`: a `Matcher` protocol (`match(ingredient, forbidden_entry) -> MatchResult | None`).
- Implement `exact_matcher.py`, `formula_matcher.py` (using Phase 4's formula parser), `fuzzy_matcher.py` (`rapidfuzz` token/partial ratio with a configurable threshold), and `acronym_matcher.py` (initials-based heuristic, not a hardcoded lookup table).
- Implement `domain/matching/pipeline.py`: a `MatchPipeline` that runs matchers in order and short-circuits on the first confident match; built to accept an extensible list of matchers so tiers 5-6 can be registered later without changing this code.
- Implement `domain/decision/engine.py`: aggregates per-ingredient `MatchResult`s into an `EvaluationResult` (`Accepted`/`Rejected` plus `reason` strings in the `"Contains X"` format from the README).
- Implement `domain/forbidden_list/repository.py`: a CSV-backed repository that loads the default forbidden list and supports in-memory replacement (persistence of uploaded lists is wired in Phase 6).

**Technical notes:**
- The acronym matcher must compute initials generically from any multi-word forbidden ingredient name; it must not contain any dataset-specific lookup table (per the generalization principle in Section 3). The synthetic test uses the "Butylated Hydroxy Anisole" (3-word) spelling of BHA — a legitimate real-world spacing variant — since naive per-word initials cannot decompose the single-word "Hydroxyanisole" form without a hardcoded lookup; documented as a known limitation, not fixed.
- **Formula matcher must gate correction on "parsed but didn't match", not on "failed to parse".** Per Phase 4, `parse_formula("H202")` *succeeds* (returns `{H: 202}`) — it just parses to the wrong value. So the formula tier must: (1) try direct `formulas_equal(ingredient, forbidden_entry)`; (2) if that's False, try `0→O` and `€→C` corrected variants of the ingredient against that same forbidden entry. Gating correction on `parse_formula(...) is None` instead would silently skip `H202`-style corruption, since it never returns `None` in the first place.
- **Fuzzy threshold is set conservatively (>=90 on rapidfuzz `ratio` over normalized text), and does NOT catch the README's `Glucose`/`D-Glucopyranose` example.** Empirically verified: every standard metric tried (rapidfuzz `ratio`/`partial_ratio`/`token_sort_ratio`/`token_set_ratio`/`WRatio`, Levenshtein distance, Jaro-Winkler) scores `Glucose` vs `D-Glucopyranose` (~0.65-0.76) *lower* than real sample P-2025-0024's `Sodium Laureth Sulfate` vs forbidden `Sodium Lauryl Sulfate` (~0.85-0.91). Since 0024 must be Accepted (see ledger below), no threshold can catch the true positive without also false-rejecting the real sample — real data wins the tension over a synthetic doc example. See `ARCHITECTURE.md` Section 6 correction note and the Phase 8 open risk below.
- **Hand-derived Accept/Reject ledger for all 30 samples** (independent ground truth, built from `forbidden_ingredients.csv` against each sample's parsed ingredients — not from the matcher itself, so it's safe to test against without circularity):
  - **Accepted:** P-2025-0003, 0014, 0022, 0024, 0025, 0028.
  - **Rejected:** every other sample, **except** P-2025-0026, which is conditional — see below.
  - **P-2025-0026 (Radiant Sunscreen) is the formula-correction canary.** Its only forbidden ingredient is OCR-corrupted `H202` (true `H2O2`); every other ingredient is clean. It comes out **Accepted if formula correction is missing/broken, Rejected if it works** — the one sample whose outcome flips entirely on that logic. (P-2025-0007/0017/0020/0023/0029 also carry OCR-corrupted formulas, but each also carries an independent clean-text forbidden ingredient, so they reject regardless of correction — 0026 is the only sample where correction is load-bearing.)
  - **P-2025-0024 is the fuzzy-matcher false-positive canary.** It contains "Sodium Laureth Sulfate" (SLES) — a different real ingredient from the forbidden "Sodium **Lauryl** Sulfate" (SLS), differing only in one middle token. It must come out **Accepted**; this is the binding constraint on the fuzzy threshold (see above), not `Glucose`/`D-Glucopyranose`.

**Verification:**
- `pytest` passes: isolated tests per matcher tier (including the `BHA` vs `Butylated Hydroxy Anisole` acronym case, and a fuzzy test asserting SLES vs SLS does NOT match at the production threshold rather than asserting a `Glucose`/`D-Glucopyranose` match), a full-pipeline test on a synthetic ingredient/forbidden list, and decision-engine tests for both `Accepted` and `Rejected` outcomes.
- Manual end-to-end run: pipe all 30 real sample products (post-Phase-3 parsing) through the tiers 1-4 pipeline against the real `forbidden_ingredients.csv` and spot-check that products containing `Coumarin`, `Propylparaben`, `BHT`, etc. are correctly flagged.
- `ruff check .` passes.

**Commit:** `feat: implement tiered rule-based ingredient matcher and decision engine`

---

## Phase 6: Persistence Layer (Toggleable SQLite)

**Status:** Done

**Goal:** Evaluation history and forbidden-list versioning, fully removable via one flag.

**Sub-tasks:**
- Implement `infra/db/models.py`: SQLModel tables `EvaluationRecord` and `ForbiddenListVersion`.
- Implement `infra/db/session.py`: engine/session factory reading `DATABASE_URL`.
- Implement an `EvaluationRepository` protocol with two implementations: `SqliteEvaluationRepository` and `NoopEvaluationRepository`.
- Wire selection between the two implementations at startup based on `ENABLE_PERSISTENCE`, via dependency injection (not an `if` scattered through service code).
- Use `SQLModel.metadata.create_all()` at startup for schema bootstrap; a full Alembic migration setup is out of scope given the project's size.

**Technical notes:**
- The forbidden-list repository from Phase 5 stays in-memory when persistence is off; when persistence is on, uploaded forbidden lists are additionally versioned and stored via `ForbiddenListVersion`.
- `EvaluationRepository` is the single protocol (in `domain/persistence/base.py`, framework-free) covering both evaluation-record writes/reads and forbidden-list-version writes; `NoopEvaluationRepository` lives alongside it in `domain/persistence/` since it needs no SQLModel/database dependency, while `SqliteEvaluationRepository` lives in `infra/db/`.
- **Real bug caught during manual verification: `SQLModel.metadata.create_all()` silently created zero tables in a real server run.** SQLModel only registers a table class on `SQLModel.metadata` when that class has actually been imported somewhere in the process. `app/infra/db/session.py` called `create_all()` without ever importing `app/infra/db/models.py`, and `main.py`'s lifespan hook only imports `session.py` — so in production, `create_db_and_tables()` ran against empty metadata and created an empty database file. Every automated test happened to pass anyway, because test modules imported `EvaluationRecord`/`ForbiddenListVersion` directly, silently registering the tables before `create_all()` ran. Caught only by manually starting the server with `ENABLE_PERSISTENCE=true` and inspecting the resulting `.db` file with `sqlite3`. **Fix:** `create_db_and_tables()` now imports `app.infra.db.models` itself before calling `create_all()`. **Regression guard:** an in-process test can't detect this class of bug at all, since one test module importing the models poisons `SQLModel.metadata` for the whole pytest session; the real guard is a subprocess-spawned test (`tests/integration/test_persistence_lifespan.py`) that boots the app in a fresh interpreter and inspects the created table names.
- `list_evaluations` orders by `created_at DESC, id DESC` (not `created_at` alone) — a non-unique sort key would make offset-based pagination skip or duplicate rows whenever two records share a timestamp, which concurrent writes (Phase 7's batch endpoints) make possible.

**Verification:**
- `pytest` passes: a repository round-trip test with `ENABLE_PERSISTENCE=true` against a temporary/in-memory SQLite database, and a test confirming `NoopEvaluationRepository` performs no writes and requires no database.
- Manual check: toggling `ENABLE_PERSISTENCE` between `true`/`false` and restarting the app produces no code changes, only different DI wiring. (This manual check is what surfaced the `create_all()` bug above — automated tests alone missed it.)
- `ruff check .` passes.

**Commit:** `feat: add toggleable SQLite persistence for evaluation history and forbidden list versions`

---

## Phase 7: API Layer

**Status:** Not started

**Goal:** Wire everything built so far behind the REST endpoints defined in Section 10 of `ARCHITECTURE.md`.

**Sub-tasks:**
- Define request/response schemas in `api/schemas/` mirroring the exact JSON contract from the challenge README plus the additive `matches` field.
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

**Status:** Not started

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
- **Open risk carried from Phase 5, first thing to check in this phase:** the challenge README explicitly requires detecting `Glucose` vs `D-Glucopyranose` as a naming-convention variation. Phase 5 empirically proved tiers 1-4 cannot catch this without false-rejecting real sample P-2025-0024 (see Phase 5 notes and `ARCHITECTURE.md` Section 6). Before building tier 5, **score this exact pair (and the SLES/SLS pair) with the actual embedding model** — the working hypothesis (not yet verified) is that cosine similarity will show the same inversion fuzzy did, since both pairs share comparable subword overlap, which would make tier 5 unable to help either. If that holds, tier 6 (LLM chemistry reasoning) is the only reliable path, which conflicts with the "must work with zero API keys" goal — surface this tradeoff to the user explicitly (LLM-default-with-fallback vs. sourcing an offline chemical-synonym/CAS dictionary) rather than silently picking one.

**Verification:**
- `pytest` passes fully offline (LLM client mocked, embedding model either mocked or run locally with no network calls).
- Manual smoke test: with a real `GOOGLE_API_KEY`, run one product with a deliberately obscure ingredient synonym through the full pipeline and confirm tier 6 produces a sensible match.
- Score `Glucose`/`D-Glucopyranose` and `Sodium Laureth Sulfate`/`Sodium Lauryl Sulfate` through the tier-5 embedding model and record whether the same false-positive-outranks-true-positive inversion occurs (see open risk above).
- `ruff check .` passes.

**Commit:** `feat: add optional embedding and Gemini (Pydantic AI) matching tiers with caching`

---

## Phase 9: Frontend Application

**Status:** Not started

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

**Status:** Not started

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
