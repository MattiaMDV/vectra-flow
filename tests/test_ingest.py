"""Tests for vectra_flow.ingest module."""
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from vectra_flow.ingest import load_inputs, _validate_columns


@pytest.fixture()
def tmp_csv(tmp_path: Path) -> Path:
    csv = tmp_path / "sample.csv"
    csv.write_text(
        textwrap.dedent(
            """\
            date,text,rating,product
            2026-01-01,"Great product, very happy!",5,Widget A
            2026-01-02,"Shipping was slow and support unhelpful.",2,Widget B
            2026-01-03,"Acceptable quality for the price.",3,Widget A
            """
        ),
        encoding="utf-8",
    )
    return csv


def test_load_inputs_returns_dataframe(tmp_csv: Path) -> None:
    df = load_inputs(str(tmp_csv))
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3


def test_load_inputs_columns(tmp_csv: Path) -> None:
    df = load_inputs(str(tmp_csv))
    for col in ("date", "text", "rating", "product"):
        assert col in df.columns


def test_load_inputs_date_parsed(tmp_csv: Path) -> None:
    df = load_inputs(str(tmp_csv))
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_load_inputs_no_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_inputs(str(tmp_path / "*.csv"))


def test_load_inputs_missing_column_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("date,text,product\n2026-01-01,hello,Widget A\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required columns"):
        load_inputs(str(bad))


def test_load_inputs_max_rows(tmp_path: Path) -> None:
    rows = "\n".join(
        f"2026-01-{i:02d},\"text {i}\",{i % 5 + 1},Widget A"
        for i in range(1, 22)
    )
    csv = tmp_path / "big.csv"
    csv.write_text(f"date,text,rating,product\n{rows}\n", encoding="utf-8")
    df = load_inputs(str(csv), max_rows=10)
    assert len(df) == 10


def test_validate_columns_missing() -> None:
    df = pd.DataFrame({"date": [], "text": [], "product": []})
    with pytest.raises(ValueError, match="Missing required columns"):
        _validate_columns(df)


def test_load_inputs_column_map(tmp_path: Path) -> None:
    """column_map should rename Italian headers before validation."""
    csv = tmp_path / "italian.csv"
    csv.write_text(
        "Timestamp,Il tuo feedback,Valutazione (1-5),Prodotto\n"
        "2026-03-20,Ottimo prodotto!,5,Widget A\n",
        encoding="utf-8",
    )
    column_map = {
        "Timestamp": "date",
        "Il tuo feedback": "text",
        "Valutazione (1-5)": "rating",
        "Prodotto": "product",
    }
    df = load_inputs(str(csv), column_map=column_map)
    assert list(df.columns[:4]) == ["date", "text", "rating", "product"]
    assert len(df) == 1
