import argparse
import json
from pathlib import Path
from vectra_flow.ingest import load_inputs
from vectra_flow.analyze import analyze_dataset
from vectra_flow.report import write_reports

def main() -> int:
    parser = argparse.ArgumentParser(prog="vectra-flow")
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
    args = parser.parse_args()

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

    df = load_inputs(args.input_glob, max_rows=args.max_rows)
    results = analyze_dataset(df, n_topics=args.n_topics)
    out_paths = write_reports(results, out_dir=Path(args.out_dir))
    print("Generated reports:")
    for p in out_paths:
        print(f"- {p}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
