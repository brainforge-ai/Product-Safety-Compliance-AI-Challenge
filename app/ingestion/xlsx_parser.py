"""XLSX file parsing utilities."""

import pandas as pd


def extract_xlsx(file_path):
    """
    Extract text from a .xlsx file by reading all sheets and converting to string.
    """
    # Read all sheets
    xls = pd.ExcelFile(file_path)
    text = ""
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        text += f"Sheet: {sheet_name}\n{df.to_string(index=False)}\n\n"
    return text