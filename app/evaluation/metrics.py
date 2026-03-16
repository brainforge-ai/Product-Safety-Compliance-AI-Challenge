"""Evaluation metrics for the product safety pipeline.

Used when evaluating the pipeline on a labeled dataset (e.g. data/evaluation/).
Provides helpers to compute accuracy, status-match rate, and latency stats.
"""


def status_accuracy(results, expected_statuses):
    """
    Compare pipeline status (Accepted/Rejected) to expected labels.

    Args:
        results: List of result dicts from run_pipeline, each with "status".
        expected_statuses: List of expected status strings, same order as results.

    Returns:
        Fraction of results where result["status"] == expected (0.0 to 1.0).
    """
    if not results or len(results) != len(expected_statuses):
        return 0.0
    correct = sum(
        1 for r, exp in zip(results, expected_statuses) if r.get("status") == exp
    )
    return correct / len(results)


def latency_stats(results):
    """
    Compute min, max, and mean latency from results that have a "latency" field.

    Args:
        results: List of result dicts (e.g. from evaluate_dataset).

    Returns:
        Dict with "min", "max", "mean" in seconds, or None if no latencies.
    """
    latencies = [r["latency"] for r in results if isinstance(r.get("latency"), (int, float))]
    if not latencies:
        return None
    return {
        "min": min(latencies),
        "max": max(latencies),
        "mean": sum(latencies) / len(latencies),
    }
