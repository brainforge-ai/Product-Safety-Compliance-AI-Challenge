"""Text reading utilities."""


def extract_txt(file_path):
    """
    Read the entire contents of a plain-text file and return it as a string.
    Tries UTF-8 first, then Windows-1252 / Latin-1 so non-UTF-8 files (e.g. from Windows) don't raise.
    """
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(file_path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    # latin-1 accepts every byte, so we should not reach here
    with open(file_path, encoding="latin-1") as f:
        return f.read()
