import glob
import pandas as pd
from vectra_flow.config import SETTINGS

def _validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in SETTINGS.required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Found: {list(df.columns)}")

def load_inputs(input_glob: str, max_rows: int = 20000) -> pd.DataFrame:
    files = sorted(glob.glob(input_glob))
    if not files:
        raise FileNotFoundError(f"No CSV files found for glob: {input_glob}")

    frames = []
    for f in files:
        df = pd.read_csv(f)
        _validate_columns(df)
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)

    out["date"] = pd.to_datetime(out["date"], errors="coerce", utc=True)
    out["text"] = out["text"].astype(str).fillna("")
    out["product"] = out["product"].astype(str).fillna("unknown")
    out["rating"] = pd.to_numeric(out["rating"], errors="coerce")

    out = out[out["text"].str.strip().astype(bool)]

    if len(out) > max_rows:
        out = out.sort_values("date", ascending=False).head(max_rows)

    return out.reset_index(drop=True)
