#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
CLI Entry Point for RAG Evaluation

Usage:
    # Generate golden dataset from hotel markdown files
    python -m scripts.eval.run_evaluation --generate-dataset

    # Run full evaluation
    python -m scripts.eval.run_evaluation

    # Custom settings
    python -m scripts.eval.run_evaluation \\
        --endpoint http://localhost:8081 \\
        --output results.html \\
        --threshold 0.7

    # Run with specific judge model
    python -m scripts.eval.run_evaluation --judge-model qwen/qwen3-max
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import get_config
from .golden_dataset import generate_golden_dataset, load_golden_dataset, get_dataset_stats
from .evaluation import HotelRAGEvaluator
from .report import generate_html_report, generate_json_report


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Hotel RAG Evaluation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate golden dataset
  python -m scripts.eval.run_evaluation --generate-dataset

  # Run evaluation with defaults
  python -m scripts.eval.run_evaluation

  # Custom endpoint and output
  python -m scripts.eval.run_evaluation --endpoint http://localhost:8081 --output results.html

  # Set pass threshold
  python -m scripts.eval.run_evaluation --threshold 0.8

Environment Variables:
  OPENROUTER_API_KEY      OpenRouter API key (required)
  EVAL_ENDPOINT_URL       FastAPI endpoint URL (default: http://localhost:8081)
  DEEPEVAL_JUDGE_MODEL    LLM judge model (default: qwen/qwen3-max)
  EVAL_PASS_THRESHOLD     Metric pass threshold (default: 0.7)
        """,
    )

    parser.add_argument(
        "--generate-dataset",
        action="store_true",
        help="Generate golden dataset from hotel markdown files",
    )

    parser.add_argument(
        "--endpoint",
        type=str,
        default=None,
        help="FastAPI endpoint URL (default: http://localhost:8081)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="test_results.html",
        help="Output report path (default: test_results.html)",
    )

    parser.add_argument(
        "--json-output",
        type=str,
        default=None,
        help="Optional JSON report output path",
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Pass threshold for metrics (0.0-1.0, default: 0.7)",
    )

    parser.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help="OpenRouter model for LLM judge (default: qwen/qwen3-max)",
    )

    parser.add_argument(
        "--dataset",
        type=str,
        default="scripts/eval/dataset.json",
        help="Path to golden dataset JSON (default: scripts/eval/dataset.json)",
    )

    parser.add_argument(
        "--hotel-data",
        type=str,
        default="data/hotel",
        help="Path to hotel data directory (default: data/hotel)",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without running evaluation",
    )

    return parser.parse_args()


def cmd_generate_dataset(args):
    """Generate golden dataset command."""
    print("=" * 60)
    print("Generating Golden Dataset")
    print("=" * 60)
    print(f"Hotel data: {args.hotel_data}")
    print(f"Output: {args.dataset}")
    print("=" * 60)

    # Generate dataset
    dataset = generate_golden_dataset(
        hotel_data_dir=args.hotel_data,
        output_path=args.dataset,
    )

    # Print statistics
    stats = get_dataset_stats(dataset)
    print()
    print("Dataset Statistics:")
    print(f"  Total pairs: {stats['total']}")
    print(f"  By language:")
    for lang, count in stats["by_language"].items():
        print(f"    {lang.upper()}: {count}")
    print(f"  By category:")
    for cat, count in stats["by_category"].items():
        print(f"    {cat}: {count}")
    print(f"  By difficulty:")
    for diff, count in stats["by_difficulty"].items():
        print(f"    {diff}: {count}")

    print()
    print(f"Dataset saved to: {args.dataset}")
    return 0


async def cmd_run_evaluation(args):
    """Run evaluation command."""
    # Build config from args
    config_overrides = {}

    if args.endpoint:
        config_overrides["endpoint_url"] = args.endpoint
    if args.threshold:
        config_overrides["pass_threshold"] = args.threshold
    if args.judge_model:
        config_overrides["judge_model"] = args.judge_model
    if args.dataset:
        config_overrides["dataset_path"] = args.dataset
    if args.output:
        config_overrides["report_path"] = args.output

    config = get_config(**config_overrides)

    # Validate config
    try:
        config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1

    if args.dry_run:
        print("Configuration valid. Dry run complete.")
        print(f"  Endpoint: {config.endpoint_url}")
        print(f"  Judge Model: {config.judge_model}")
        print(f"  Pass Threshold: {config.pass_threshold}")
        print(f"  Dataset: {config.dataset_path}")
        print(f"  Report: {config.report_path}")
        return 0

    # Load dataset
    dataset_path = Path(config.dataset_path)
    if not dataset_path.exists():
        print(f"Dataset not found at {config.dataset_path}")
        print("Generating golden dataset...")
        dataset = generate_golden_dataset(
            hotel_data_dir=args.hotel_data,
            output_path=config.dataset_path,
        )
    else:
        dataset = load_golden_dataset(config.dataset_path)

    # Create evaluator and run
    evaluator = HotelRAGEvaluator(config)
    results, summary = await evaluator.run_evaluation(dataset)

    # Generate HTML report
    html_path = generate_html_report(results, summary, config.report_path)

    # Generate JSON report if requested
    if args.json_output:
        json_path = generate_json_report(results, summary, args.json_output)
        print(f"JSON report: {json_path}")

    print()
    print(f"HTML report: {html_path}")

    # Return exit code based on pass rate
    if summary.pass_rate >= 80:
        return 0  # Success
    elif summary.pass_rate >= 60:
        return 1  # Warning
    else:
        return 2  # Failure


def main():
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    try:
        if args.generate_dataset:
            return cmd_generate_dataset(args)
        else:
            return asyncio.run(cmd_run_evaluation(args))

    except KeyboardInterrupt:
        print("\nEvaluation cancelled.")
        return 130
    except Exception as e:
        logging.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
