"""
CLI entry point for vectra_flow.

Usage:
    python -m vectra_flow.cli run [--input PATH] [--output PATH]
                                  [--min-score FLOAT] [--top-n INT]
    python -m vectra_flow.cli version
"""

import argparse
import logging
import sys
from pathlib import Path

from vectra_flow import __version__
from vectra_flow.config import Config
from vectra_flow.ingest import ingest
from vectra_flow.analyze import analyze
from vectra_flow.report import generate_report


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        level=getattr(logging, level.upper(), logging.INFO),
    )


def _cmd_run(args: argparse.Namespace) -> int:
    """Execute the full ingest → analyze → report pipeline."""
    cfg = Config()
    _setup_logging(cfg.LOG_LEVEL)

    input_path = Path(args.input) if args.input else None
    output_path = Path(args.output) if args.output else None
    min_score = args.min_score
    top_n = args.top_n

    try:
        records = ingest(input_path)
        results = analyze(records, min_score=min_score, top_n=top_n)
        report_path = generate_report(results, output=output_path)
        print(f"✓ Report generated: {report_path}")
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print(f"✗ Error: {exc}", file=sys.stderr)
        return 1


def _cmd_version(_args: argparse.Namespace) -> int:
    print(f"vectra-flow {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vectra-flow",
        description="vectra-flow: AI-powered niche-software opportunity pipeline",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- run subcommand --
    run_p = subparsers.add_parser("run", help="Run the full pipeline")
    run_p.add_argument(
        "--input",
        metavar="PATH",
        default=None,
        help="Path to input CSV (default: data/sample.csv)",
    )
    run_p.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help="Path for the output HTML report",
    )
    _cfg = Config()
    run_p.add_argument(
        "--min-score",
        type=float,
        default=None,
        dest="min_score",
        help=(
            f"Minimum opportunity score [0–1] "
            f"(default: VECTRA_MIN_SCORE env / {_cfg.MIN_SCORE})"
        ),
    )
    run_p.add_argument(
        "--top-n",
        type=int,
        default=None,
        dest="top_n",
        help=(
            f"Maximum number of results to include in report "
            f"(default: VECTRA_TOP_N env / {_cfg.TOP_N})"
        ),
    )
    run_p.set_defaults(func=_cmd_run)

    # -- version subcommand --
    ver_p = subparsers.add_parser("version", help="Print the package version")
    ver_p.set_defaults(func=_cmd_version)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
