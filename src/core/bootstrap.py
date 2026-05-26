"""
Shared bootstrap logic for pipeline initialization.

Single source of truth for creating the MatchPipeline - used by API, UI, and CLI.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

from src.core.matching import ForbiddenIndex, MatchPipeline, PubChemClient
from src.core.extractors import extract_product
from src.core.models import EvaluationResult

logger = logging.getLogger(__name__)


def find_forbidden_csv(custom_path: Optional[Path] = None) -> Path:
    """
    Find the forbidden ingredients CSV file.

    Search order:
    1. Custom path if provided
    2. Project root (relative to this file)
    3. Current working directory
    """
    if custom_path and custom_path.exists():
        return custom_path

    # Project root (src/core/bootstrap.py -> ../../../)
    project_root = Path(__file__).parent.parent.parent
    default_path = project_root / "forbidden_ingredients.csv"

    if default_path.exists():
        return default_path

    # Try current directory
    cwd_path = Path("forbidden_ingredients.csv")
    if cwd_path.exists():
        return cwd_path

    raise FileNotFoundError(
        f"Forbidden ingredients CSV not found. Checked:\n"
        f"  - {custom_path}\n"
        f"  - {default_path}\n"
        f"  - {cwd_path}"
    )


async def create_pipeline(
    forbidden_path: Optional[Path] = None,
    max_concurrent: int = 3,
) -> MatchPipeline:
    """
    Create and initialize the matching pipeline.

    This is the canonical way to create a MatchPipeline. It handles:
    - Finding the forbidden ingredients CSV
    - Loading and resolving all forbidden ingredients via PubChem
    - Creating the pipeline instance

    Args:
        forbidden_path: Optional custom path to forbidden ingredients CSV
        max_concurrent: Max concurrent PubChem API requests

    Returns:
        Initialized MatchPipeline ready for evaluation
    """
    csv_path = find_forbidden_csv(forbidden_path)
    logger.info(f"Loading forbidden ingredients from: {csv_path}")

    # Load forbidden index
    forbidden_index = ForbiddenIndex.from_csv(csv_path)

    # Initialize PubChem client
    pubchem_client = PubChemClient(max_concurrent=max_concurrent)

    # Pre-resolve all forbidden ingredients via PubChem
    logger.info("Pre-resolving forbidden ingredients...")
    await forbidden_index.resolve_all(pubchem_client)

    # Create and return pipeline
    pipeline = MatchPipeline(forbidden_index, pubchem_client)
    logger.info("Pipeline initialized successfully")

    return pipeline


async def evaluate_file(
    pipeline: MatchPipeline,
    file_path: Path,
) -> EvaluationResult:
    """
    Evaluate a single file using the pipeline.

    Canonical evaluation path - extract then evaluate.

    Args:
        pipeline: Initialized MatchPipeline
        file_path: Path to the file to evaluate

    Returns:
        EvaluationResult with status and match details
    """
    extraction = await extract_product(file_path)
    result = await pipeline.evaluate(extraction, file_path.name)
    return result
