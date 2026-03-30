"""Tests for vectra_flow.asset_ingest module."""
import textwrap
from pathlib import Path

import pytest

from vectra_flow.asset_ingest import _validate_columns, load_assets
from vectra_flow.asset_score import AssetOpportunity
import pandas as pd


@pytest.fixture()
def tmp_assets_csv(tmp_path: Path) -> Path:
    csv = tmp_path / "assets.csv"
    csv.write_text(
        textwrap.dedent(
            """\
            url,title,asking_price,monthly_revenue,monthly_traffic,tech_stack,category,has_email_list,current_monetization
            https://example.com/a,App Alpha,200,20,1000,"Python, Flask",micro-saas,false,ads
            https://example.com/b,App Beta,500,40,5000,"Node.js",web-tool,true,subscription
            https://example.com/c,App Gamma,150,0,300,"PHP5",micro-saas,false,
            """
        ),
        encoding="utf-8",
    )
    return csv


def test_load_assets_returns_list(tmp_assets_csv: Path) -> None:
    assets = load_assets(str(tmp_assets_csv))
    assert isinstance(assets, list)
    assert len(assets) == 3


def test_load_assets_types(tmp_assets_csv: Path) -> None:
    assets = load_assets(str(tmp_assets_csv))
    for a in assets:
        assert isinstance(a, AssetOpportunity)


def test_load_assets_numeric_fields(tmp_assets_csv: Path) -> None:
    assets = load_assets(str(tmp_assets_csv))
    assert assets[0].asking_price == pytest.approx(200.0)
    assert assets[0].monthly_revenue == pytest.approx(20.0)
    assert assets[0].monthly_traffic == 1000


def test_load_assets_tech_stack_parsed(tmp_assets_csv: Path) -> None:
    assets = load_assets(str(tmp_assets_csv))
    assert "Python" in assets[0].tech_stack
    assert "Flask" in assets[0].tech_stack


def test_load_assets_has_email_list(tmp_assets_csv: Path) -> None:
    assets = load_assets(str(tmp_assets_csv))
    assert assets[0].has_email_list is False
    assert assets[1].has_email_list is True


def test_load_assets_max_rows(tmp_assets_csv: Path) -> None:
    assets = load_assets(str(tmp_assets_csv), max_rows=2)
    assert len(assets) == 2


def test_load_assets_no_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_assets(str(tmp_path / "*.csv"))


def test_load_assets_missing_column_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "url,title,asking_price,monthly_revenue\n"
        "https://x.com,Test,100,10\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Missing required columns"):
        load_assets(str(bad))


def test_load_assets_empty_optional_columns(tmp_path: Path) -> None:
    csv = tmp_path / "minimal.csv"
    csv.write_text(
        "url,title,asking_price,monthly_revenue,monthly_traffic\n"
        "https://example.com,Minimal,300,15,500\n",
        encoding="utf-8",
    )
    assets = load_assets(str(csv))
    assert len(assets) == 1
    assert assets[0].tech_stack == []
    assert assets[0].has_email_list is False
    assert assets[0].category == "micro-saas"


def test_validate_columns_missing_raises() -> None:
    df = pd.DataFrame({"url": [], "title": [], "asking_price": []})
    with pytest.raises(ValueError, match="Missing required columns"):
        _validate_columns(df, path="test.csv")


def test_validate_columns_passes_when_all_present() -> None:
    df = pd.DataFrame(
        {
            "url": [],
            "title": [],
            "asking_price": [],
            "monthly_revenue": [],
            "monthly_traffic": [],
        }
    )
    _validate_columns(df)  # should not raise


def test_load_assets_with_column_map(tmp_path: Path) -> None:
    """Column mapping should rename form columns before validation."""
    csv = tmp_path / "form_export.csv"
    csv.write_text(
        "URL asset,Nome asset,Prezzo richiesto,MRR attuale,Traffico mensile\n"
        "https://example.com/x,My App,300,25,2000\n",
        encoding="utf-8",
    )
    column_map = {
        "URL asset": "url",
        "Nome asset": "title",
        "Prezzo richiesto": "asking_price",
        "MRR attuale": "monthly_revenue",
        "Traffico mensile": "monthly_traffic",
    }
    assets = load_assets(str(csv), column_map=column_map)
    assert len(assets) == 1
    assert assets[0].url == "https://example.com/x"
    assert assets[0].title == "My App"
    assert assets[0].asking_price == pytest.approx(300.0)
    assert assets[0].monthly_revenue == pytest.approx(25.0)
    assert assets[0].monthly_traffic == 2000


def test_load_assets_column_map_partial(tmp_path: Path) -> None:
    """Column map may contain keys not present in the CSV; they are ignored."""
    csv = tmp_path / "partial.csv"
    csv.write_text(
        "URL asset,Nome asset,asking_price,monthly_revenue,monthly_traffic\n"
        "https://example.com/y,App Y,100,10,500\n",
        encoding="utf-8",
    )
    column_map = {
        "URL asset": "url",
        "Nome asset": "title",
        "NonExistentColumn": "category",
    }
    assets = load_assets(str(csv), column_map=column_map)
    assert len(assets) == 1
    assert assets[0].url == "https://example.com/y"
