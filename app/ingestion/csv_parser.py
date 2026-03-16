"""CSV file parsing utilities."""

import pandas as pd


def extract_csv(file_path):
    """
    Extract text from a .csv file by reading it as a DataFrame and converting to string.
    """
    df = pd.read_csv(file_path)
    # Convert the entire DataFrame to a string representation
    text = df.to_string(index=False)
    return text