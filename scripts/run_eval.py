#!/usr/bin/env python3
"""
Batch evaluation script for Product Safety Compliance.

Usage:
    python scripts/run_eval.py                        # Process pdfs/, images/, texts/
    python scripts/run_eval.py --index product_index.csv  # Use product index CSV
    python scripts/run_eval.py path/to/files/         # Process specific directory
    python scripts/run_eval.py --output results.json  # Save results to JSON
"""
from __future__ import annotations
import argparse
import asyncio
import csv
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.core.bootstrap import create_pipeline, evaluate_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}


def find_files(paths: list[str]) -> list[Path]:
    """Find all supported files from given paths (files or directories)."""
    files = []

    for path_str in paths:
        path = Path(path_str)

        if path.is_file():
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(path)
        elif path.is_dir():
            for ext in SUPPORTED_EXTENSIONS:
                files.extend(path.glob(f"*{ext}"))
                files.extend(path.glob(f"**/*{ext}"))

    # Deduplicate and sort
    return sorted(set(files))


def load_from_index(index_path: Path, base_dir: Path) -> list[Path]:
    """Load file paths from a product index CSV."""
    files = []
    with open(index_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("filename", "")
            if filename:
                file_path = base_dir / filename
                if file_path.exists():
                    files.append(file_path)
                else:
                    logger.warning(f"File not found: {file_path}")
    return files


def print_results(results: list[dict]) -> None:
    """Print results table."""
    if not results:
        print("\nNo results to display.")
        return

    accepted = sum(1 for r in results if r["status"] == "Accepted")
    rejected = len(results) - accepted

    print("\n" + "━" * 90)
    print(f"  {'FILE':<35} {'STATUS':<12} {'REASONS'}")
    print("━" * 90)

    for r in results:
        status = r["status"]
        if status == "Accepted":
            status_display = f"\033[92m✓ Accepted\033[0m"
        else:
            status_display = f"\033[91m✗ Rejected\033[0m"

        reason_list = r.get("reason", [])
        reason_str = ", ".join(reason_list[:2]) if reason_list else "—"
        if len(reason_list) > 2:
            reason_str += f" (+{len(reason_list) - 2})"

        filename = r["filename"][:33] + ".." if len(r["filename"]) > 35 else r["filename"]
        print(f"  {filename:<35} {status_display:<21} {reason_str}")

    print("━" * 90)
    print(f"  Total: {len(results)}  │  \033[92mAccepted: {accepted}\033[0m  │  \033[91mRejected: {rejected}\033[0m")
    print("━" * 90 + "\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Evaluate product files for forbidden ingredients",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_eval.py                              # Process default directories
  python scripts/run_eval.py --index product_index.csv    # Use product index CSV
  python scripts/run_eval.py pdfs/ images/                # Process specific directories
  python scripts/run_eval.py --output results.json        # Save results to JSON
        """
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["pdfs", "images", "texts"],
        help="Files or directories to process (default: pdfs/ images/ texts/)",
    )
    parser.add_argument(
        "--index", "-i",
        type=str,
        default=None,
        help="Product index CSV file (columns: product_id, filename)",
    )
    parser.add_argument(
        "--forbidden", "-f",
        type=str,
        default=None,
        help="Path to custom forbidden ingredients CSV",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Find files to process
    if args.index:
        # Load from product index CSV
        index_path = Path(args.index)
        if not index_path.exists():
            logger.error(f"Index file not found: {index_path}")
            sys.exit(1)
        base_dir = index_path.parent
        files = load_from_index(index_path, base_dir)
    else:
        # Scan directories
        files = find_files(args.paths)

    if not files:
        logger.error(f"No supported files found")
        logger.info(f"Supported extensions: {SUPPORTED_EXTENSIONS}")
        sys.exit(1)

    print(f"\n  Found {len(files)} files to evaluate\n")

    # Initialize pipeline using shared bootstrap
    logger.info("Initializing pipeline...")
    start_init = time.time()

    forbidden_path = Path(args.forbidden) if args.forbidden else None
    pipeline = await create_pipeline(forbidden_path=forbidden_path)

    logger.info(f"Ready in {time.time() - start_init:.1f}s")

    # Process files
    results = []
    total_start = time.time()

    for i, file_path in enumerate(files, 1):
        try:
            logger.info(f"[{i}/{len(files)}] {file_path.name}")

            result = await evaluate_file(pipeline, file_path)

            results.append({
                "filename": file_path.name,
                "filepath": str(file_path),
                "product_id": result.product_id,
                "product_name": result.product_name,
                "status": result.status.value,
                "reason": result.reason,
                "ingredients": result.ingredients_detected,
                "duration_ms": result.duration_ms,
                "trace": {
                    "layer_a": result.trace.layer_a_hits,
                    "layer_b": result.trace.layer_b_hits,
                    "layer_c": result.trace.layer_c_hits,
                },
            })

        except Exception as e:
            logger.error(f"[{i}/{len(files)}] Failed: {file_path.name} - {e}")
            results.append({
                "filename": file_path.name,
                "filepath": str(file_path),
                "status": "Error",
                "reason": [str(e)],
                "error": True,
            })

    total_time = time.time() - total_start

    # Print results
    print_results(results)

    valid_results = [r for r in results if not r.get("error")]
    if valid_results:
        print(f"  Total time: {total_time:.1f}s  │  Avg: {total_time/len(valid_results)*1000:.0f}ms/file\n")

    # Save JSON if requested
    if args.output:
        output_data = {
            "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(results),
            "accepted": sum(1 for r in results if r.get("status") == "Accepted"),
            "rejected": sum(1 for r in results if r.get("status") == "Rejected"),
            "errors": sum(1 for r in results if r.get("error")),
            "duration_s": round(total_time, 2),
            "results": results,
        }

        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)

        print(f"  Results saved to: {args.output}\n")


if __name__ == "__main__":
    asyncio.run(main())
