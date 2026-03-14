"""Centralized configuration loaded from environment variables.

Reads .env via python-dotenv.  Raises immediately if the required
ANTHROPIC_API_KEY is missing so failures are obvious at startup.
"""

import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError(
        "ANTHROPIC_API_KEY not set. "
        "Create a .env file with: ANTHROPIC_API_KEY=sk-ant-..."
    )

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FORBIDDEN_CSV = os.path.join(BASE_DIR, "forbidden_ingredients.csv")
PRODUCT_INDEX_CSV = os.path.join(BASE_DIR, "product_index.csv")
