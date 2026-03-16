"""Evaluator for product safety pipeline."""

import time

from ..pipeline import run_pipeline


def evaluate_dataset(files):
    """
    Run the pipeline on a list of files and record latency for each run.

    Args:
        files: Iterable of file paths to evaluate.

    Returns:
        A list of result dictionaries (one per file), each augmented with a "latency" field (seconds).
    """
    results = []

    for file in files:
        # Start the timer before running the pipeline.
        start = time.time()

        # Run your main pipeline on the file (should return a dict-like result).
        result = run_pipeline(file)

        # Compute end-to-end latency in seconds.
        latency = time.time() - start

        # Attach latency to the result so downstream code can analyze performance.
        result["latency"] = latency

        results.append(result)

    return results
