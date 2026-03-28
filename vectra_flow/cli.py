import argparse
import json
from pathlib import Path
from vectra_flow.ingest import load_inputs
from vectra_flow.analyze import analyze_dataset
from vectra_flow.report import write_reports

def main() -> int:
    parser = argparse.ArgumentParser(prog="vectra-flow")
    parser.add_argument(
        "--mode",
        choices=["feedback", "assets", "scout"],
        default="feedback",
        help=(
            "Operating mode: "
            "'feedback' (default) runs the sentiment & topic analysis pipeline; "
            "'assets' runs the Digital Real Estate & Flip portfolio manager; "
            "'scout' scans crypto forums for undervalued digital assets and "
            "generates partnership outreach notifications."
        ),
    )
    parser.add_argument("--input-glob", default="data/*.csv")
    parser.add_argument("--out-dir", default="reports")
    parser.add_argument("--n-topics", type=int, default=8)
    parser.add_argument("--max-rows", type=int, default=20000)
    parser.add_argument(
        "--sheet-url",
        default="",
        metavar="URL",
        help=(
            "HTTP(S) URL of a CSV to fetch before analysis "
            "(e.g. a Google Sheets 'Publish to web' CSV export URL). "
            "The file is saved to data/sheet.csv and picked up by --input-glob."
        ),
    )
    parser.add_argument(
        "--column-map",
        default="",
        metavar="JSON",
        help=(
            "JSON object mapping source column names (from the downloaded sheet) "
            "to the required column names (date, text, rating, product). "
            "Example: '{\"Timestamp\":\"date\",\"Feedback\":\"text\",\"Score\":\"rating\",\"Product\":\"product\"}'"
        ),
    )
    parser.add_argument(
        "--web-urls",
        default="",
        metavar="URL[,URL,…]",
        help=(
            "Comma-separated list of public web/forum URLs to scrape for text. "
            "Extracted paragraphs are merged with the CSV data before analysis. "
            "Example: 'https://www.reddit.com/r/myproduct/,https://forum.example.com/t/123'"
        ),
    )
    parser.add_argument(
        "--scout-urls",
        default="",
        metavar="URL[,URL,…]",
        help=(
            "Comma-separated list of forum URLs for --mode scout to scan. "
            "Defaults to the built-in list (Reddit, Bitcointalk, governance forums, "
            "Binance Square) when not provided."
        ),
    )
    parser.add_argument(
        "--notify-dir",
        default="",
        metavar="DIR",
        help=(
            "Directory where scout partnership-notification files are written. "
            "Defaults to 'reports/notifications'."
        ),
    )
    parser.add_argument(
        "--min-scout-score",
        type=float,
        default=0.3,
        metavar="SCORE",
        help=(
            "Minimum relevance score (0.0–1.0) for the scout to surface an asset. "
            "Default: 0.3"
        ),
    )
    args = parser.parse_args()

    if args.mode == "assets":
        return _run_assets(args, parser)
    if args.mode == "scout":
        return _run_scout(args, parser)
    return _run_feedback(args, parser)


def _run_feedback(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Original sentiment & topic analysis pipeline."""
    column_map = None
    if args.column_map:
        try:
            column_map = json.loads(args.column_map)
            if not isinstance(column_map, dict):
                raise TypeError("--column-map must be a JSON object")
        except (json.JSONDecodeError, TypeError) as exc:
            parser.error(f"Invalid --column-map value: {exc}")

    if args.sheet_url:
        from vectra_flow.fetch_inputs import fetch_sheet
        sheet_dest = Path("data/sheet.csv")
        fetch_sheet(args.sheet_url, sheet_dest, column_map=column_map)
        print(f"Fetched sheet data → {sheet_dest}")

    import pandas as pd
    df = load_inputs(args.input_glob, max_rows=args.max_rows, column_map=column_map)

    if args.web_urls:
        from vectra_flow.fetch_web import fetch_web_sources
        urls = [u.strip() for u in args.web_urls.split(",") if u.strip()]
        if urls:
            web_df = fetch_web_sources(urls)
            if not web_df.empty:
                df = pd.concat([df, web_df], ignore_index=True)
                print(f"Fetched {len(web_df)} paragraphs from {len(urls)} web source(s).")

    results = analyze_dataset(df, n_topics=args.n_topics)
    out_paths = write_reports(results, out_dir=Path(args.out_dir))
    print("Generated reports:")
    for p in out_paths:
        print(f"- {p}")
    return 0


def _run_assets(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:  # noqa: ARG001
    """Digital Real Estate & Flip pipeline."""
    from vectra_flow.asset_ingest import load_assets
    from vectra_flow.asset_score import score_assets
    from vectra_flow.asset_report import write_asset_reports

    input_glob = args.input_glob if args.input_glob != "data/*.csv" else "data/assets/*.csv"
    assets = load_assets(input_glob, max_rows=args.max_rows)
    scored = score_assets(assets)

    out_paths = write_asset_reports(scored, out_dir=Path(args.out_dir))
    print(f"Digital Real Estate & Flip — {len(scored)} asset(s) analysed.")
    print("Generated reports:")
    for p in out_paths:
        print(f"- {p}")
    return 0


def _run_scout(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:  # noqa: ARG001
    """Asset Scout — scan crypto forums and send partnership notifications."""
    from vectra_flow.asset_scout import scan_forums, DEFAULT_SCOUT_URLS
    from vectra_flow.partnership_notify import create_proposals, write_proposals

    urls = (
        [u.strip() for u in args.scout_urls.split(",") if u.strip()]
        if args.scout_urls
        else DEFAULT_SCOUT_URLS
    )

    notify_dir = Path(args.notify_dir) if args.notify_dir else Path("reports/notifications")

    print(f"Scout: scanning {len(urls)} forum source(s) …")
    assets = scan_forums(
        urls,
        min_score=args.min_scout_score,
    )
    print(f"Scout: found {len(assets)} asset mention(s) with score ≥ {args.min_scout_score}.")

    if not assets:
        print("No qualifying assets discovered. Try lowering --min-scout-score.")
        return 0

    proposals = create_proposals(assets)
    out_paths = write_proposals(proposals, out_dir=notify_dir)

    print(f"Partnership notifications generated for {len(proposals)} asset(s):")
    for p in out_paths:
        print(f"- {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
