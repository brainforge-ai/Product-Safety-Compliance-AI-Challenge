# Product Safety Compliance AI -- Solution

**Author:** Srinivas Saiteja Tenneti
**Branch:** `feature/Srinivas-Saiteja-Tenneti-solution`

---

## Architecture Overview

```
                  +-------------------------------+
                  |         INPUT FILES            |
                  | TXT, PDF, PNG, JPG, WEBP, BMP, |
                  | CSV, XLSX, JSON, DOCX          |
                  +---------------+---------------+
                                  |
                                  v
                  +---------------+---------------+
                  |          FILE ROUTER           |
                  |    Detects type by extension    |
                  +---+-------+-------+-------+---+
                      |       |       |       |
              +-------+   +---+---+  ++------++  +-------+
              v           v       v   v       v          v
        +-----------+ +-----------+ +---------+ +-----------+
        |   Text    | |  PyMuPDF  | |  Claude | |  Pandas   |
        |  Reader   | |  (PDFs)   | |  Vision | | (CSV/XLSX)|
        | TXT, JSON | |           | | (Images)| |           |
        |   DOCX    | | Per-page  | |   OCR   | | Key-value |
        |           | | fallback  | |         | |  Tabular  |
        |           | | to Vision | |         | | Headerless|
        +-----------+ +-----------+ +---------+ +-----------+
              +-------+---+---+-------+-------+
                                  |
                                  v
                  +---------------+---------------+
                  |      INGREDIENT PARSER         |
                  |  Extracts product metadata     |
                  |  and clean ingredient list     |
                  |  Handles: bullets, commas,     |
                  |  pipes, numbered lists,        |
                  |  chemical formulas with        |
                  |  parentheses, OCR fragments    |
                  +---------------+---------------+
                                  |
                                  v
                  +---------------+---------------+
                  |       FORBIDDEN LIST           |
                  |  Loaded from CSV at runtime    |
                  |  + user-added ingredients      |
                  |  (never hardcoded)             |
                  +---------------+---------------+
                                  |
                                  v
                  +---------------+---------------+
                  |    3-TIER MATCHING ENGINE      |
                  |                                |
                  | Tier 1: Exact match            |
                  |   (case-insensitive)           |
                  |                                |
                  | Tier 2: Normalized match       |
                  |   (strip spaces, hyphens,      |
                  |    special characters)         |
                  |                                |
                  | Tier 3: Claude LLM reasoning   |
                  |   - Synonyms & formulas        |
                  |   - IUPAC / trade names        |
                  |   - Multilingual names         |
                  |   - OCR error correction       |
                  |   Anti-hallucination:          |
                  |   - No substring matching      |
                  |   - Strict formula rules       |
                  +---------------+---------------+
                                  |
                                  v
                  +---------------+---------------+
                  |    VISUAL VERIFICATION         |
                  |    (Images only -- ALWAYS)     |
                  |  Independent safety check:     |
                  |  sends raw image + forbidden   |
                  |  list to Claude for direct     |
                  |  visual inspection             |
                  +---------------+---------------+
                                  |
                                  v
                  +---------------+---------------+
                  |    OCR CONFIDENCE CHECK        |
                  |    (Images only)               |
                  |  If READABILITY = LOW and      |
                  |  no matches found:             |
                  |    -> Needs Review             |
                  +---------------+---------------+
                                  |
                                  v
                  +---------------+---------------+
                  |          DECISION              |
                  |  Rejected:    forbidden found  |
                  |  Needs Review: low quality     |
                  |  Accepted:    all clear        |
                  +---------------+---------------+
                                  |
                        +---------+---------+
                        v                   v
                 +-------------+    +--------------+
                 |   FastAPI   |    |  Streamlit   |
                 |  REST API   |    |   Web UI     |
                 |   :8000     |    |   :8501      |
                 +-------------+    +--------------+
```

### Custom Forbidden Ingredient Upload Flow

```
  +-------------------------------------------+
  |  User uploads file via Streamlit sidebar   |
  |  (any format: TXT, PDF, PNG, CSV, DOCX…)  |
  |  OR types ingredient name manually         |
  +---------------------+---------------------+
                        |
                        v
  +---------------------+---------------------+
  |        FILE EXTRACTION                     |
  |  Same pipeline as product evaluation:      |
  |  Text / PyMuPDF / Claude Vision / Pandas   |
  +---------------------+---------------------+
                        |
                        v
  +---------------------+---------------------+
  |        NAME PARSER                         |
  |  Splits by lines, commas, pipes            |
  |  Filters titles, descriptions, sentences   |
  |  Strips metadata headers and bullets       |
  |  Extracts English names from parentheses   |
  +---------------------+---------------------+
                        |
                        v
  +---------------------+---------------------+
  |        DEDUPLICATION                       |
  |  Case-insensitive check against existing   |
  |  default + already-added ingredients       |
  +---------------------+---------------------+
                        |
                        v
  +---------------------+---------------------+
  |     SESSION FORBIDDEN LIST                 |
  |  Merged with default CSV at runtime        |
  |  Persists until user removes or clears     |
  |  Individual remove (X) or Clear All        |
  +---------------------+---------------------+
                        |
                        v
  +---------------------+---------------------+
  |  All subsequent evaluations check against  |
  |  the combined (default + added) list       |
  +-------------------------------------------+
```

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### Install

```bash
cd Product-Safety-Compliance-AI-Challenge
git checkout feature/Srinivas-Saiteja-Tenneti-solution

python -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Run

```bash
# Terminal 1 -- REST API
uvicorn main:app --reload --port 8000

# Terminal 2 -- Web UI
streamlit run streamlit_app.py
```

- API docs: http://localhost:8000/docs
- Streamlit UI: http://localhost:8501

---

## API Endpoints

### POST `/evaluate_product`

Evaluate a single product file.

**Parameters:**
- `file` (required): Product file upload (PDF, PNG, JPG, TXT, CSV, XLSX, JSON, DOCX)
- `forbidden_list` (optional): Custom forbidden ingredients CSV

**Response:**
```json
{
  "product_id": "P-2025-0029",
  "product_name": "Fresh Cleanser",
  "source_file": "P-2025-0029_Fresh_Cleanser.png",
  "status": "Rejected",
  "reason": ["Contains Sodium Lauryl Sulfate"],
  "raw_extracted_text": "Product ID: P-2025-0029\nProduct Name: ...",
  "ingredients_found": ["Benzyl Alcohol", "Sodium Chloride", "Sodium Lauryl Sulfate"],
  "forbidden_matches": [
    {
      "ingredient": "Sodium Lauryl Sulfate",
      "matched_forbidden": "Sodium Lauryl Sulfate",
      "match_tier": "exact",
      "explanation": "Exact match with 'Sodium Lauryl Sulfate'"
    }
  ]
}
```

### POST `/evaluate_batch`

Evaluate multiple product files in one request.

### POST `/evaluate_index`

Evaluate all products listed in `product_index.csv`.

---

## File Structure

```
.
├── main.py                        # FastAPI REST API application
├── streamlit_app.py               # Streamlit interactive web UI
├── requirements.txt               # Python dependencies
├── .env                           # API keys (not committed)
├── .env.example                   # Template for environment variables
├── .gitignore
├── SOLUTION.md                    # This file
├── forbidden_ingredients.csv      # Default forbidden ingredient list
├── product_index.csv              # Product-to-file mapping (30 products)
├── images/                        # Sample product images (PNG)
├── pdfs/                          # Sample product PDFs
├── texts/                         # Sample product text files
└── app/
    ├── __init__.py
    ├── config.py                  # Environment config loader
    ├── models.py                  # Pydantic response models
    ├── file_router.py             # File type detection by extension
    ├── evaluator.py               # Core evaluation orchestrator
    ├── ingredient_parser.py       # Raw text -> ingredient list parser
    ├── matching_engine.py         # 3-tier matcher + visual verification
    └── extractors/
        ├── __init__.py
        ├── text_extractor.py      # TXT, JSON, DOCX extraction
        ├── pdf_extractor.py       # PDF (PyMuPDF + per-page Claude Vision fallback)
        ├── image_extractor.py     # Image OCR (Claude Vision API)
        └── csv_extractor.py       # CSV/Excel (pandas, key-value, tabular)
```

---

## Key Design Decisions

### 1. Forbidden List is Never Hardcoded

The forbidden ingredients list is loaded dynamically from CSV at runtime. It can be:
- Overridden via API upload
- Extended via the Streamlit sidebar (upload any file type or type manually)
- Restored to default by clearing added ingredients

The system works with any forbidden list -- no assumptions about specific chemicals.

### 2. 3-Tier Matching for Accuracy

- **Tier 1 (Exact):** Instant, free, case-insensitive string comparison.
- **Tier 2 (Normalized):** Strips whitespace, hyphens, and special characters before comparing. Catches formatting variations.
- **Tier 3 (LLM Chemical Reasoning):** Uses Claude to identify chemical identity across synonyms, formulas, IUPAC names, trade names, abbreviations, and names in any language or script. Includes strict anti-hallucination rules to prevent false positives (e.g., C6H12O6 is glucose, NOT benzene C6H6).

### 3. Visual Verification Safety Net

For every image input, a second independent Claude call sends the raw image alongside the forbidden list for direct visual inspection. This runs **always** -- not just when other tiers find nothing -- because OCR can hallucinate incorrect ingredient names on blurry or low-contrast images.

### 4. OCR Confidence Assessment

Claude Vision reports a readability level (HIGH / MEDIUM / LOW) for each image. If readability is LOW and no forbidden ingredients are found, the system returns "Needs Review" instead of "Accepted." This prevents false negatives on unreadable images -- the system honestly reports uncertainty rather than giving a false sense of safety.

### 5. Claude Vision for OCR

Chosen over Tesseract/EasyOCR because it handles:
- Blurry and low-contrast photos
- Handwritten text (cursive, messy)
- Chemical formulas and notation
- Non-Latin scripts (Devanagari, Telugu, Tamil, CJK, Arabic, Cyrillic, etc.)
- Product label photographs from phone cameras

The OCR prompt is engineered to prevent hallucination: Claude must read actual visible characters and use "?" for truly illegible ones, rather than substituting plausible but incorrect words.

### 6. Chemical Formula Awareness

- The OCR prompt includes all two-letter element symbols (Cl, Al, Br, Fe, Na, etc.) to prevent common misreads like "Cl" -> "C1".
- The ingredient parser preserves chemical formulas with parentheses (e.g., Pb(C2H3O2)2) as single units.
- The matching engine has strict formula rules: different molecular formulas = different chemicals, regardless of superficial text similarity.

### 7. No Hardcoded Training

The system generalizes to unseen products, chemicals, languages, and file formats. All intelligence comes from Claude's general knowledge combined with the dynamically loaded forbidden list.

### 8. Modular Architecture

Each component (extractors, parser, matcher, evaluator) is independent. New file formats, matching tiers, or extraction methods can be added without modifying other modules.

### 9. Prompt Caching for Cost Efficiency

All Claude API calls use Anthropic's prompt caching with `cache_control: {"type": "ephemeral"}`. Static instruction prompts and the forbidden list form a cached prefix. In a batch of 30 products, calls 2-30 read from cache at 90% lower input token cost. Cache auto-invalidates when the forbidden list changes.

### 10. Dynamic Forbidden List Management (UI)

Users can add forbidden ingredients at runtime by:
- Uploading **any file type** (TXT, PDF, image, CSV, Excel, JSON, DOCX)
- Typing names manually

The full extraction pipeline processes uploaded files to extract ingredient names. Added ingredients are merged with the default list and persist until the user removes them individually or clears all.

---

## Assumptions

- The forbidden ingredients CSV follows the provided format: a header row and one ingredient per line.
- Products are **optimized for** structured ingredient lists (bulleted, comma-separated, or tabular), but the system also handles unstructured text through LLM reasoning and visual verification.
- Chemical formula matching requires LLM reasoning (exact string matching cannot detect that C6H6 = Benzene or Methanal = Formaldehyde).
- Image quality affects OCR accuracy. Very blurry or faded images may result in "Needs Review" rather than a definitive accept/reject.
- The LLM matching is calibrated to avoid false positives (wrongly rejecting a safe product). For uncertain cases -- such as low-quality images where OCR is unreliable -- the system returns "Needs Review" instead of a silent accept, ensuring safety without over-flagging.

---

## Tech Stack

| Tool          | Purpose                                      |
|---------------|----------------------------------------------|
| FastAPI       | REST API framework                           |
| Streamlit     | Interactive web UI                           |
| Claude API    | Vision OCR + LLM chemical reasoning          |
| PyMuPDF       | PDF text extraction (with Vision fallback)   |
| pandas        | CSV/Excel data handling                      |
| python-docx   | DOCX text and table extraction               |
| pydantic      | Data validation and structured response models|
| python-dotenv | Environment variable configuration           |

---

## Loom Video

[Watch the walkthrough](https://www.loom.com/share/9a3bfb9028ac400a90d96e0f7c075be0) -- 5-10 minute video explaining the approach, thought process, and architecture with a live demo.
