"""Extract text from CSV and Excel files using pandas.

Handles three layouts:
- Key-value (2 columns: field name | value)
- Headerless simple lists (no recognized column headers)
- Standard tabular data (with named columns)
"""

import pandas as pd


_FIELD_KEYWORDS = {
    "product id", "product name", "sku", "description", "ingredients",
    "chemical", "formula", "composition", "component", "compound",
    "substance", "name", "id",
}

_HEADER_KEYWORDS = {
    "ingredient", "chemical", "formula", "compound", "substance",
    "name", "id", "product", "sku", "description", "notes", "category",
    "component", "composition",
}


def extract_from_csv(file_path: str) -> str:
    """Read CSV and convert to text for the ingredient parser."""
    df = pd.read_csv(file_path)
    if _is_key_value(df):
        return _key_value_to_text(pd.read_csv(file_path, header=None))
    if _needs_headerless_read(df):
        df = pd.read_csv(file_path, header=None)
        return _simple_list_to_text(df)
    return _dataframe_to_text(df)


def extract_from_excel(file_path: str) -> str:
    """Read Excel file and convert to text."""
    df = pd.read_excel(file_path)
    if _is_key_value(df):
        return _key_value_to_text(pd.read_excel(file_path, header=None))
    if _needs_headerless_read(df):
        df = pd.read_excel(file_path, header=None)
        return _simple_list_to_text(df)
    return _dataframe_to_text(df)


def _is_key_value(df: pd.DataFrame) -> bool:
    """Detect if the DataFrame is a 2-column key-value format."""
    if len(df.columns) != 2:
        return False
    col_a_name = str(df.columns[0]).lower().strip()
    if any(kw in col_a_name for kw in _FIELD_KEYWORDS):
        return True
    col_a_vals = df.iloc[:, 0].dropna().astype(str).str.lower().str.strip()
    matches = sum(1 for v in col_a_vals if any(kw in v for kw in _FIELD_KEYWORDS))
    return matches >= 2


def _needs_headerless_read(df: pd.DataFrame) -> bool:
    """Detect if pandas wrongly used the first data row as column headers.

    This happens with simple lists (1-2 columns) where the first row is
    actual data, not a header.  E.g. a CSV with just ingredient names.
    """
    if len(df.columns) > 3:
        return False
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(kw == col_lower for kw in _HEADER_KEYWORDS):
            return False
    has_header_like = any(
        any(kw in str(col).lower() for kw in _HEADER_KEYWORDS)
        for col in df.columns
    )
    if has_header_like:
        return False
    return True


def _simple_list_to_text(df: pd.DataFrame) -> str:
    """Convert a headerless DataFrame into a simple line-per-value text."""
    lines = []
    for _, row in df.iterrows():
        vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
        if vals:
            lines.append(" | ".join(vals))
    return "\n".join(lines)


def _key_value_to_text(df: pd.DataFrame) -> str:
    """Convert a 2-column key-value DataFrame to structured text."""
    lines = []
    for _, row in df.iterrows():
        key = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        val = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        if not key or not val:
            continue
        val = _normalize_separators(val)
        lines.append(f"{key}: {val}")
    return "\n".join(lines)


def _normalize_separators(text: str) -> str:
    """Convert pipe-separated values to comma-separated."""
    if "|" in text:
        parts = [p.strip() for p in text.split("|") if p.strip()]
        return ", ".join(parts)
    return text


def _dataframe_to_text(df: pd.DataFrame) -> str:
    """Convert a tabular DataFrame into structured text."""
    ingredient_columns = [
        col for col in df.columns
        if any(kw in col.lower() for kw in [
            "ingredient", "chemical", "formula", "composition",
            "component", "substance", "compound",
        ])
    ]

    lines = []
    for _, row in df.iterrows():
        for col in df.columns:
            val = row[col]
            if pd.notna(val):
                val_str = _normalize_separators(str(val))
                lines.append(f"{col}: {val_str}")
        lines.append("")

    if ingredient_columns:
        lines.append("Ingredients / Chemical Formulas:")
        for col in ingredient_columns:
            for val in df[col].dropna().unique():
                val_str = _normalize_separators(str(val))
                for item in val_str.split(","):
                    item = item.strip()
                    if item:
                        lines.append(f"- {item}")

    return "\n".join(lines)
