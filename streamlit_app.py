"""
Product Safety Compliance -- Streamlit UI
==========================================
Run:  streamlit run streamlit_app.py
"""

import os
import re
import tempfile
import pandas as pd
import streamlit as st

from app.config import DEFAULT_FORBIDDEN_CSV, BASE_DIR, PRODUCT_INDEX_CSV
from app.evaluator import evaluate_product, extract_text_from_file
from app.matching_engine import load_forbidden_ingredients

st.set_page_config(
    page_title="Product Safety Compliance",
    page_icon="P",
    layout="wide",
)

# -- Session state initialization ---------------------------------------------
if "added_forbidden" not in st.session_state:
    st.session_state.added_forbidden = []

# -- Custom CSS ---------------------------------------------------------------
st.markdown("""
<style>
    .status-accepted {
        background-color: #0e4429; color: #3fb950;
        padding: 4px 14px; border-radius: 16px;
        font-weight: 600; font-size: 0.85rem; display: inline-block;
    }
    .status-rejected {
        background-color: #4a1219; color: #f85149;
        padding: 4px 14px; border-radius: 16px;
        font-weight: 600; font-size: 0.85rem; display: inline-block;
    }
    .status-review {
        background-color: #3d2e00; color: #d29922;
        padding: 4px 14px; border-radius: 16px;
        font-weight: 600; font-size: 0.85rem; display: inline-block;
    }
    .status-error {
        background-color: #3d2e00; color: #db6d28;
        padding: 4px 14px; border-radius: 16px;
        font-weight: 600; font-size: 0.85rem; display: inline-block;
    }
    .match-card {
        background-color: #1c1215; border-left: 3px solid #f85149;
        padding: 10px 14px; margin: 6px 0; border-radius: 0 6px 6px 0;
    }
    .match-card .tier {
        color: #8b949e; font-size: 0.75rem; text-transform: uppercase;
    }
    .ingredient-tag {
        display: inline-block; background-color: #21262d;
        border: 1px solid #30363d; padding: 2px 8px;
        border-radius: 12px; font-size: 0.8rem; margin: 2px; color: #c9d1d9;
    }
    .forbidden-item {
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.8rem; color: #f85149; padding: 2px 0;
    }
    .added-item {
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.8rem; color: #d29922; padding: 2px 0;
    }
    .section-header {
        font-size: 0.85rem; font-weight: 600; color: #8b949e;
        text-transform: uppercase; letter-spacing: 0.8px;
        margin-top: 16px; margin-bottom: 8px;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    div[data-testid="stMetric"] {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 8px; padding: 12px 16px;
    }
</style>
""", unsafe_allow_html=True)


# -- Helpers -------------------------------------------------------------------

_STATUS_CSS = {
    "Accepted": "status-accepted",
    "Rejected": "status-rejected",
    "Needs Review": "status-review",
    "Error": "status-error",
}

_TIER_LABELS = {
    "exact": "Exact Match",
    "normalized": "Normalized Match",
    "llm": "LLM Chemical Reasoning",
    "visual_verify": "Visual Verification",
}

_SUPPORTED_TYPES = [
    "txt", "pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif",
    "csv", "xlsx", "xls", "json", "docx",
]


def _badge(status: str) -> str:
    css = _STATUS_CSS.get(status, "status-error")
    return f'<span class="{css}">{status}</span>'


_SKIP_PREFIXES = (
    "product id", "product name", "sku", "description",
    "note:", "looking at", "readability:", "category:",
    "custom", "the following", "this file", "this document",
    "ingredient name", "ingredients", "ingredient",
    "notes", "forbidden", "chemical formula",
    "composition", "component", "substance", "compound",
)

_JUNK_EXACT = frozenset({
    "high", "medium", "low",
})


def _parse_names_from_text(raw_text: str) -> list[str]:
    """Extract plausible ingredient/chemical names from raw text.

    Handles: one-per-line, comma-separated, bullet lists, pipe-separated
    table rows, and structured formats with 'Ingredients:' headers.
    Filters out titles, descriptions, and long sentences.
    """
    raw_text = raw_text.replace("**", "").replace("__", "")
    names = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        lower = line.lower()

        if any(lower.startswith(p) for p in _SKIP_PREFIXES):
            if lower.startswith("readability:"):
                continue
            after = line.split(":", 1)
            if len(after) > 1 and after[1].strip():
                line = after[1].strip()
            else:
                continue

        if len(line.split()) > 10:
            continue

        line = re.sub(r"^[\-\*\u2022\u00b7\u25aa\u25ba]\s*", "", line)
        line = re.sub(r"^\d+[\.\)]\s*", "", line)

        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            for part in parts:
                _collect_name(part, names)
        elif "," in line:
            for part in line.split(","):
                _collect_name(part.strip(), names)
        else:
            _collect_name(line, names)
    return names


def _collect_name(text: str, names: list[str]) -> None:
    """Add a single name to the list if it looks like a chemical/ingredient."""
    text = text.strip()
    if not text or len(text) < 2:
        return
    lower = text.lower()
    if lower in ("unknown", "not found", "n/a", "none", "illegible"):
        return
    if lower in _JUNK_EXACT:
        return
    if any(lower.startswith(p) for p in _SKIP_PREFIXES):
        return
    if len(text.split()) > 6:
        return
    paren = re.search(r"\(([A-Za-z][A-Za-z0-9\s\-]+)\)", text)
    if paren:
        names.append(paren.group(1).strip())
    else:
        names.append(text)


def _render_single(result):
    """Render a single evaluation result."""
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"### {_badge(result.status)}", unsafe_allow_html=True)
    with col2:
        st.markdown(f"**Product:** {result.product_name}")
        if result.product_id:
            st.markdown(f"**ID:** {result.product_id}")
        if result.source_file:
            st.markdown(f"**Source File:** `{result.source_file}`")

    st.divider()

    if result.reason:
        st.markdown('<p class="section-header">Reasons</p>', unsafe_allow_html=True)
        for r in result.reason:
            st.markdown(f"- {r}")

    if result.forbidden_matches:
        st.markdown('<p class="section-header">Match Details</p>', unsafe_allow_html=True)
        for m in result.forbidden_matches:
            tier = _TIER_LABELS.get(m.match_tier, m.match_tier)
            st.markdown(
                f'<div class="match-card">'
                f'<strong>{m.ingredient}</strong> matches '
                f'<code>{m.matched_forbidden}</code><br>'
                f'<span class="tier">{tier}</span> &mdash; {m.explanation}'
                f'</div>',
                unsafe_allow_html=True,
            )

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown('<p class="section-header">Extracted Ingredients</p>', unsafe_allow_html=True)
        if result.ingredients_found:
            tags = " ".join(f'<span class="ingredient-tag">{i}</span>' for i in result.ingredients_found)
            st.markdown(tags, unsafe_allow_html=True)
        else:
            st.markdown("No ingredients extracted.")
    with col_right:
        st.markdown('<p class="section-header">Raw Extracted Text</p>', unsafe_allow_html=True)
        if result.raw_extracted_text:
            st.code(result.raw_extracted_text, language=None)
        else:
            st.markdown("No text extracted.")


def _render_batch(results):
    """Render batch evaluation results."""
    accepted = sum(1 for r in results if r.status == "Accepted")
    rejected = sum(1 for r in results if r.status == "Rejected")
    review = sum(1 for r in results if r.status == "Needs Review")
    errors = sum(1 for r in results if r.status == "Error")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Accepted", accepted)
    c2.metric("Rejected", rejected)
    c3.metric("Needs Review", review)
    c4.metric("Errors", errors)

    rows = [{
        "Product ID": r.product_id or "-",
        "Product Name": r.product_name,
        "Source File": r.source_file or "-",
        "Status": r.status,
        "Reasons": "; ".join(r.reason) if r.reason else "-",
    } for r in results]

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown('<p class="section-header">Detailed Results</p>', unsafe_allow_html=True)
    for r in results:
        label = r.source_file or r.product_name
        with st.expander(f"{label} -- {r.status}"):
            st.markdown(f"**Status:** {_badge(r.status)}", unsafe_allow_html=True)
            if r.product_id:
                st.markdown(f"**Product ID:** {r.product_id}")
            if r.source_file:
                st.markdown(f"**Source File:** `{r.source_file}`")

            if r.reason:
                st.markdown('<p class="section-header">Reasons</p>', unsafe_allow_html=True)
                for reason in r.reason:
                    st.markdown(f"- {reason}")

            if r.forbidden_matches:
                st.markdown('<p class="section-header">Match Details</p>', unsafe_allow_html=True)
                for m in r.forbidden_matches:
                    tier = _TIER_LABELS.get(m.match_tier, m.match_tier)
                    st.markdown(
                        f'<div class="match-card">'
                        f'<strong>{m.ingredient}</strong> matches '
                        f'<code>{m.matched_forbidden}</code><br>'
                        f'<span class="tier">{tier}</span> &mdash; {m.explanation}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown('<p class="section-header">Extracted Ingredients</p>', unsafe_allow_html=True)
            if r.ingredients_found:
                tags = " ".join(f'<span class="ingredient-tag">{i}</span>' for i in r.ingredients_found)
                st.markdown(tags, unsafe_allow_html=True)
            else:
                st.markdown("No ingredients extracted.")

            if r.raw_extracted_text:
                with st.expander("Raw Extracted Text"):
                    st.code(r.raw_extracted_text, language=None)


# -- Sidebar -------------------------------------------------------------------
with st.sidebar:
    st.title("Settings")

    # -- Default forbidden list ------------------------------------------------
    base_forbidden = load_forbidden_ingredients(DEFAULT_FORBIDDEN_CSV)

    # -- Add new forbidden ingredients -----------------------------------------
    st.markdown(
        '<p class="section-header">Add Forbidden Ingredients</p>',
        unsafe_allow_html=True,
    )
    st.caption("Upload any file (text, PDF, image, CSV, etc.) containing ingredient names to add to the forbidden list.")

    add_file = st.file_uploader(
        "Upload file with ingredients to forbid",
        type=_SUPPORTED_TYPES,
        key="add_forbidden_file",
        label_visibility="collapsed",
    )

    if add_file and st.button("Extract and Add", key="btn_add_forbidden", type="primary"):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{add_file.name}")
        tmp.write(add_file.read())
        tmp.close()

        with st.spinner("Extracting ingredient names..."):
            try:
                raw = extract_text_from_file(tmp.name)
                parsed = _parse_names_from_text(raw)
            except Exception as exc:
                parsed = []
                st.error(f"Failed to extract: {exc}")
            finally:
                os.unlink(tmp.name)

        if parsed:
            existing_lower = {f.lower() for f in base_forbidden}
            existing_lower.update(f.lower() for f in st.session_state.added_forbidden)
            new_items = [n for n in parsed if n.lower() not in existing_lower]
            if new_items:
                st.session_state.added_forbidden.extend(new_items)
                st.success(f"Added {len(new_items)} ingredient(s)")
                st.rerun()
            else:
                st.info("All extracted ingredients are already in the forbidden list.")
        else:
            st.warning("No ingredient names could be extracted from this file.")

    # Manual text input as alternative
    manual_input = st.text_input(
        "Or type ingredient name to add:",
        key="manual_forbidden",
        placeholder="e.g. Glucose",
    )
    if manual_input and st.button("Add", key="btn_add_manual"):
        name = manual_input.strip()
        existing_lower = {f.lower() for f in base_forbidden}
        existing_lower.update(f.lower() for f in st.session_state.added_forbidden)
        if name.lower() not in existing_lower:
            st.session_state.added_forbidden.append(name)
            st.rerun()
        else:
            st.info("Already in the forbidden list.")

    # -- Show added ingredients with remove buttons ----------------------------
    if st.session_state.added_forbidden:
        st.divider()
        st.markdown(
            f'<p class="section-header">Added Ingredients ({len(st.session_state.added_forbidden)})</p>',
            unsafe_allow_html=True,
        )
        st.caption("These are temporarily added and will be checked alongside the default list.")

        to_remove = []
        for i, name in enumerate(st.session_state.added_forbidden):
            col_name, col_btn = st.columns([3, 1])
            with col_name:
                st.markdown(f'<p class="added-item">{name}</p>', unsafe_allow_html=True)
            with col_btn:
                if st.button("X", key=f"rm_{i}"):
                    to_remove.append(i)

        if to_remove:
            st.session_state.added_forbidden = [
                n for i, n in enumerate(st.session_state.added_forbidden)
                if i not in to_remove
            ]
            st.rerun()

        if st.button("Clear All Added", key="btn_clear_added"):
            st.session_state.added_forbidden = []
            st.rerun()

    # -- Show full forbidden list ----------------------------------------------
    st.divider()
    total = len(base_forbidden) + len(st.session_state.added_forbidden)
    st.markdown(
        f'<p class="section-header">Default Forbidden List ({len(base_forbidden)})</p>',
        unsafe_allow_html=True,
    )
    for ing in base_forbidden:
        st.markdown(f'<p class="forbidden-item">{ing}</p>', unsafe_allow_html=True)


# -- Main Area -----------------------------------------------------------------
st.title("Product Safety Compliance Checker")
st.markdown(
    "Upload product files (PDF, Image, Text, CSV) to check for forbidden "
    "chemical ingredients. The system uses AI to detect ingredient name "
    "variations across languages, formulas, and synonyms."
)

extra = st.session_state.added_forbidden if st.session_state.added_forbidden else None

tab1, tab2, tab3 = st.tabs(["Single File", "Batch Upload", "Evaluate Product Index"])

# -- Tab 1: Single file -------------------------------------------------------
with tab1:
    uploaded = st.file_uploader("Upload a product file", type=_SUPPORTED_TYPES, key="single")

    if uploaded and st.button("Evaluate Product", key="btn_single", type="primary"):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded.name}")
        tmp.write(uploaded.read())
        tmp.close()

        with st.spinner("Analyzing..."):
            result = evaluate_product(
                tmp.name, DEFAULT_FORBIDDEN_CSV, extra,
                source_filename=uploaded.name,
            )
        os.unlink(tmp.name)

        st.markdown("")
        _render_single(result)


# -- Tab 2: Batch Upload ------------------------------------------------------
with tab2:
    files = st.file_uploader(
        "Upload multiple product files",
        type=_SUPPORTED_TYPES,
        accept_multiple_files=True,
        key="batch",
    )

    if files and st.button("Evaluate All", key="btn_batch", type="primary"):
        tmp_paths = []
        for f in files:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{f.name}")
            tmp.write(f.read())
            tmp.close()
            tmp_paths.append(tmp.name)

        progress = st.progress(0, text="Evaluating...")
        results = []
        for i, tp in enumerate(tmp_paths):
            with st.spinner(f"Evaluating {files[i].name}..."):
                res = evaluate_product(
                    tp, DEFAULT_FORBIDDEN_CSV, extra,
                    source_filename=files[i].name,
                )
                results.append(res)
            progress.progress((i + 1) / len(tmp_paths), text=f"Evaluated {i + 1} of {len(tmp_paths)}")

        for tp in tmp_paths:
            os.unlink(tp)

        progress.empty()
        _render_batch(results)


# -- Tab 3: Evaluate from product_index.csv -----------------------------------
with tab3:
    st.markdown(
        "Evaluate all products listed in `product_index.csv`. "
        "Each row maps a product to its data file."
    )

    if st.button("Run Full Evaluation", key="btn_index", type="primary"):
        if not os.path.exists(PRODUCT_INDEX_CSV):
            st.error("product_index.csv not found in the project root.")
        else:
            df = pd.read_csv(PRODUCT_INDEX_CSV)
            file_paths = [os.path.join(BASE_DIR, row["filename"]) for _, row in df.iterrows()]

            progress = st.progress(0, text="Evaluating products...")
            results = []
            for i, fp in enumerate(file_paths):
                with st.spinner(f"Evaluating {os.path.basename(fp)}..."):
                    res = evaluate_product(fp, DEFAULT_FORBIDDEN_CSV, extra)
                    results.append(res)
                progress.progress((i + 1) / len(file_paths), text=f"Evaluated {i + 1} of {len(file_paths)}")

            progress.empty()
            _render_batch(results)
