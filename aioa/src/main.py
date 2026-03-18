"""CLI entrypoint for AIO Analyzer.

Usage:
    python -m src.main run --prompts config/prompts_v1.json --terms config/terms_v1.json
    python -m src.main query "What is the best MCP runtime?"
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from src.input_layer import load_competitors, load_prompts, load_terms
from src.pipeline import run_ad_hoc_query, run_full_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aio-analyzer",
        description="AI & Search Visibility Benchmarking Tool — measure competitive positioning across LLMs and search engines.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run command ---
    run_parser = subparsers.add_parser("run", help="Run the full benchmarking pipeline.")
    run_parser.add_argument(
        "--prompts",
        default="config/prompts_v1.json",
        help="Path to prompt set JSON file (default: config/prompts_v1.json)",
    )
    run_parser.add_argument(
        "--terms",
        default="config/terms_v1.json",
        help="Path to term set JSON file (default: config/terms_v1.json)",
    )
    run_parser.add_argument(
        "--competitors",
        default="config/competitors.json",
        help="Path to competitor config JSON file (default: config/competitors.json)",
    )
    run_parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory for output files (default: data)",
    )

    # --- query command ---
    query_parser = subparsers.add_parser("query", help="Run an ad-hoc competitive query.")
    query_parser.add_argument(
        "query_text",
        help="The query string to run as both an LLM prompt and search term.",
    )
    query_parser.add_argument(
        "--competitors",
        default="config/competitors.json",
        help="Path to competitor config JSON file (default: config/competitors.json)",
    )
    query_parser.add_argument(
        "--output-dir",
        default="data",
        help="Directory for output files (default: data)",
    )

    return parser


async def cmd_run(args: argparse.Namespace) -> None:
    """Handle the 'run' command."""
    print("[aio-analyzer] Loading configuration...")
    competitors = load_competitors(args.competitors)
    prompt_set = load_prompts(args.prompts)
    term_set = load_terms(args.terms)

    print(f"[aio-analyzer] Target: {competitors.target}")
    print(f"[aio-analyzer] Competitors: {', '.join(competitors.competitors)}")
    print(f"[aio-analyzer] Prompts: {len(prompt_set.prompts)} | Terms: {len(term_set.terms)}")

    await run_full_pipeline(
        prompt_set=prompt_set,
        term_set=term_set,
        competitors=competitors,
        output_dir=args.output_dir,
    )


async def cmd_query(args: argparse.Namespace) -> None:
    """Handle the 'query' command."""
    competitors = load_competitors(args.competitors)
    print(f"[aio-analyzer] Ad-hoc query: \"{args.query_text}\"")
    print(f"[aio-analyzer] Target: {competitors.target}")

    await run_ad_hoc_query(
        query=args.query_text,
        competitors=competitors,
        output_dir=args.output_dir,
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "query":
        asyncio.run(cmd_query(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
