import argparse
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
    args = parser.parse_args()

    df = load_inputs(args.input_glob, max_rows=args.max_rows)
    results = analyze_dataset(df, n_topics=args.n_topics)
    out_paths = write_reports(results, out_dir=Path(args.out_dir))
    print("Generated reports:")
    for p in out_paths:
        print(f"- {p}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
