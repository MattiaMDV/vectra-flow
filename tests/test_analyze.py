"""Tests for vectra_flow.analyze module."""
import pandas as pd
import pytest

from vectra_flow.analyze import analyze_dataset, AnalysisResults


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
                utc=True,
            ),
            "text": [
                "Great product, very happy with the purchase!",
                "Shipping was slow and support was unhelpful.",
                "Acceptable quality for the price paid.",
                "Absolutely love it, will buy again!",
                "Product broke after one week, very disappointed.",
            ],
            "rating": [5.0, 2.0, 3.0, 5.0, 1.0],
            "product": ["Widget A", "Widget B", "Widget A", "Widget A", "Widget B"],
        }
    )


def test_analyze_returns_results(sample_df: pd.DataFrame) -> None:
    results = analyze_dataset(sample_df, n_topics=2)
    assert isinstance(results, AnalysisResults)


def test_analyze_rows_count(sample_df: pd.DataFrame) -> None:
    results = analyze_dataset(sample_df, n_topics=2)
    assert results.rows == len(sample_df)


def test_analyze_sentiment_overall_keys(sample_df: pd.DataFrame) -> None:
    results = analyze_dataset(sample_df, n_topics=2)
    assert "sentiment_compound_mean" in results.sentiment_overall
    assert "rating_mean" in results.sentiment_overall
    assert "rows_with_rating" in results.sentiment_overall


def test_analyze_sentiment_by_product(sample_df: pd.DataFrame) -> None:
    results = analyze_dataset(sample_df, n_topics=2)
    products = {r["product"] for r in results.sentiment_by_product}
    assert "Widget A" in products
    assert "Widget B" in products


def test_analyze_topics_count(sample_df: pd.DataFrame) -> None:
    results = analyze_dataset(sample_df, n_topics=2)
    assert len(results.topics) == 2


def test_analyze_date_range(sample_df: pd.DataFrame) -> None:
    results = analyze_dataset(sample_df, n_topics=2)
    assert results.date_min is not None
    assert results.date_max is not None
    assert results.date_min < results.date_max


def test_analyze_topics_have_terms(sample_df: pd.DataFrame) -> None:
    results = analyze_dataset(sample_df, n_topics=2)
    for topic in results.topics:
        assert len(topic.top_terms) > 0
