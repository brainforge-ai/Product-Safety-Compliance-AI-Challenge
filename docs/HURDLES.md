# Engineering Hurdles & Lessons

The implementation changed whenever real data disproved an assumption. This is the short version of what failed, what changed, and what each failure taught us.

## 1. Extraction and parsing

### OCR can turn one chemical into another

Tesseract read <code>H2O2</code> as <code>H202</code> and sometimes <code>C</code> as <code>€</code>. Blindly correcting every <code>0</code> to <code>O</code> is unsafe because several corrected formulas can be syntactically valid.

**Decision:** keep the formula parser strict. Apply OCR corrections only inside the matcher, where a real forbidden formula can validate the correction.

**Lesson:** ambiguous cleanup belongs where domain context can disambiguate it.

### PDFs need page-level fallback

Some PDFs contain a mix of embedded text and scanned pages. Treating the whole document as either text or OCR loses information.

**Decision:** extract native text per page and OCR only pages without usable text. Catch the shared PyMuPDF <code>RuntimeError</code> so missing and corrupt files both become controlled extraction errors.

**Lesson:** choose the best extraction strategy at the smallest useful boundary.

### Ingredient parsing has dangerous punctuation

A loose numbered-list regex can treat the <code>1,</code> in <code>1,4-Dioxane</code> as a list marker. Comma splitting can also break chemical names and parenthesized text.

**Decision:** require whitespace after numbered bullets, split commas only when followed by whitespace, and never split inside brackets.

**Lesson:** punctuation is data in chemical names, not merely formatting.

### Parser output is not independent ground truth

<code>expected_ingredients.json</code> was generated from parser output and then reviewed. It is useful for regression testing, but the same systematic bug could exist in both actual and expected data.

**Decision:** use hand-written edge-case tests and a manually derived Accept/Reject ledger as the stronger correctness evidence.

**Lesson:** generated fixtures protect behavior; independent fixtures test truth.

## 2. Matching strategy

### Fuzzy similarity inverted the desired result

<code>Glucose</code> ↔ <code>D-Glucopyranose</code> scores lower than the distinct pair <code>Sodium Laureth Sulfate</code> ↔ <code>Sodium Lauryl Sulfate</code>. No fuzzy threshold can catch the first without false-rejecting a real safe sample.

**Decision:** keep fuzzy matching conservative at **≥ 90** and let the optional LLM tier handle genuine naming synonyms.

**Lesson:** measure positive and negative examples together before choosing a threshold.

### Embeddings had the same problem

MiniLM scored the glucose pair at about **0.35**, while a non-match from an Accepted sample reached about **0.75**. Formula strings also appeared similar because of shared characters rather than chemistry.

**Decision:** use a **0.90** embedding threshold and exclude formula-shaped strings entirely.

**Lesson:** semantic models still need domain-specific negative controls.

### Formula correction must run after a valid-but-wrong parse

<code>H202</code> parses successfully as <code>{H: 202}</code>. Waiting for parsing to fail would skip the exact OCR corruption we need to repair.

**Decision:** compare the parsed result with the target first, then try OCR-corrected variants when they differ.

**Lesson:** valid syntax does not imply correct interpretation.

### Acronym matching has a deliberate limit

Initials can match <code>BHT</code> to <code>Butylated Hydroxytoluene</code>, but <code>Butylated Hydroxyanisole</code> produces <code>BH</code>, not <code>BHA</code>, unless the alternate three-word spelling is used.

**Decision:** keep the heuristic generic instead of adding compound-word exceptions or a hardcoded synonym table.

**Lesson:** document narrow heuristics rather than disguising them as general intelligence.

## 3. Persistence and API behavior

### SQLModel created an empty database

<code>SQLModel.metadata.create_all()</code> only knows about table classes that have already been imported. Unit tests imported the models indirectly, so they passed while a fresh server created zero tables.

**Decision:** import the model module inside <code>create_db_and_tables()</code> and protect the behavior with a fresh-process regression test.

**Lesson:** global-registration frameworks must be tested in a clean process.

### Pagination needed a stable order

Sorting only by <code>created_at</code> is ambiguous when concurrent evaluations share a timestamp.

**Decision:** sort by <code>created_at DESC, id DESC</code>.

**Lesson:** offset pagination requires a unique tiebreaker.

### Local error handling erased HTTP semantics

Route-level catches converted every application error into <code>422</code>, preventing the global handler from returning <code>415</code> for unsupported files.

**Decision:** remove redundant route catches and map domain errors to HTTP responses in one application-level location.

**Lesson:** exception translation should have one owner.

### One uploaded file can contain many products

A multi-row CSV breaks the assumption that one file always produces one result.

**Decision:** keep one <code>POST /api/evaluate</code> endpoint. One resolved product returns <code>EvaluationResult</code>; multiple files or rows return <code>BatchEvaluationResponse</code>. Multi-file failures are isolated per file, while a bad single upload keeps normal <code>415</code>/<code>422</code> behavior.

**Lesson:** API shape should follow resolved domain objects, not file count alone.

### Repository-relative data complicates packaging

The dataset lives above <code>backend/</code>, so a backend-only container would not inherit the current default paths.

**Decision:** keep configurable paths and use the verified virtual-environment setup instead of adding an untested Docker image.

**Lesson:** packaging is complete only when data layout and system dependencies are reproduced too.

## 4. Optional AI tiers

### The LLM could not be a normal matcher

The main pipeline is synchronous and compares one pair at a time. Gemini is asynchronous, should receive all unresolved ingredients together, and must remain safe under concurrent product evaluation.

**Decision:** run embeddings inside the matcher pipeline, but run Gemini once per product from <code>EvaluationService</code>.

**Lesson:** integration boundaries should reflect execution semantics, not force every tool into one interface.

### Heavy AI dependencies threatened the zero-config path

<code>sentence-transformers</code> brings in PyTorch, while Gemini requires Pydantic AI and an API key.

**Decision:** move AI packages to <code>requirements-ai.txt</code>, import them lazily, and keep both feature flags off by default.

**Lesson:** optional capability should not tax the default runtime.

### Cache invalidation could not depend on persistence

The LLM cache must work even when SQLite is disabled.

**Decision:** key cached verdicts by normalized ingredient plus a stable hash of the active forbidden list. Replacing the list naturally invalidates old results.

**Lesson:** cache keys must include every input that can change the answer.

### Live Gemini tests exposed confident hallucinations

Gemini incorrectly matched citric acid to caffeine and later matched water (<code>Aqua</code>) to hydrogen peroxide, both with confidence **1.0**. Mock clients could not reveal this because mocks only return the cases written into tests.

**Decision:** never send formula-shaped ingredients or forbidden entries to embeddings or the LLM. Tier 2 owns formula equality. Add regressions using the exact failed pairs.

**Tradeoff:** a common name such as <code>Benzene</code> cannot currently match a forbidden entry listed only as <code>C6H6</code>. This favors precision over speculative recall.

**Lesson:** validate probabilistic components against real models and real negative cases.

### The supplied data does not require AI

Tiers 1–4 correctly handle all 30 supplied products. The LLM adds no matches to that ledger.

**Decision:** use separate fixtures to demonstrate where AI is valuable:

- <code>D-Glucopyranose</code> → <code>Glucose</code>
- <code>Butyl 4-hydroxybenzoate</code> → <code>Butylparaben</code>

**Lesson:** distinguish “does not regress the dataset” from “adds capability beyond the dataset.”

## 5. LLM extraction and usage reporting

### The extraction fallback was declared but never consumed

Parsers set <code>needs_llm_fallback</code>, but the evaluation service originally ignored it. A parser miss could therefore look like a product with no forbidden ingredients.

**Decision:** retry unresolved extraction through Gemini when enabled. If no ingredients remain afterward, return <code>422</code> rather than silently Accepting the product.

**Lesson:** a fallback is not implemented until the orchestration layer actually calls it.

### Usage data is call metadata, not model output

Asking the model to report its own tokens or cost would produce invented numbers. Shared “last usage” state would also race between concurrent products.

**Decision:** read usage from Pydantic AI after each call, price it with <code>genai-prices</code>, and return it alongside the result. Combine extraction and matching usage through return values only.

**Known gap:** usage is visible in live responses but is not stored in SQLite history.

**Lesson:** operational metadata should come from the client and flow explicitly through the call graph.

## 6. Environment and demo reliability

### The “offline tests pass” claim was initially false

The long-lived development environment already contained optional AI packages, hiding missing-dependency failures.

**Decision:** verify the documented install in a fresh virtual environment and skip only tests that genuinely require unavailable optional packages.

**Lesson:** test setup instructions from a clean environment, not from a developer machine with accumulated state.

### The LLM demo looked broken because the flag was off

An API key was present, but <code>ENABLE_LLM_MATCHING=false</code>. Settings are cached at startup, so changing the file without restarting the backend had no effect.

**Decision:** make the feature flag and restart requirement part of the demo checklist. Add a real-list fixture so the LLM demo does not require replacing the forbidden list.

**Lesson:** verify runtime configuration, not just credentials, before debugging a feature.

## Final audit

The pre-demo audit added ordinary ingredient headers, inline and comma-delimited lists, mixed-page PDF OCR, grouped and hydrate formulas, formula exclusion from fuzzy matching, fail-closed parser behavior, isolated feature flags, and correct handling of transient LLM failures.

Current verification:

- **190 backend tests pass offline**
- **Ruff, bytecode compilation, frontend build, and frontend lint pass**
- **30 supplied products:** 24 Rejected, 6 Accepted, 0 ledger mismatches
- **Five sequential batches:** about 0.46 seconds each with identical output
- **Four concurrent batches:** 0 mismatches
- **Live Gemini:** naming variant matched; identical retry returned from cache in about 2 ms

## Takeaways

1. Prefer deterministic evidence before similarity or AI.
2. Test negative examples as seriously as positive examples.
3. Fail closed when extraction cannot support a decision.
4. Use clean processes and real integrations to expose hidden state.
5. Record limitations and tradeoffs instead of overstating coverage.
