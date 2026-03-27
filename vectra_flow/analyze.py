from dataclasses import dataclass
from typing import Any
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

@dataclass
class TopicSummary:
    topic_id: int
    size: int
    top_terms: list[str]
    examples: list[dict[str, Any]]

@dataclass
class AnalysisResults:
    generated_at_utc: str
    rows: int
    date_min: str | None
    date_max: str | None
    sentiment_overall: dict[str, float]
    sentiment_by_product: list[dict[str, Any]]
    topics: list[TopicSummary]

def analyze_dataset(df: pd.DataFrame, n_topics: int = 8) -> AnalysisResults:
    df = df.copy()
    analyzer = SentimentIntensityAnalyzer()
    df["sentiment_compound"] = [analyzer.polarity_scores(t)["compound"] for t in df["text"].tolist()]

    overall = {
        "sentiment_compound_mean": float(np.nanmean(df["sentiment_compound"])),
        "rating_mean": float(np.nanmean(df["rating"])) if df["rating"].notna().any() else float("nan"),
        "rows_with_rating": int(df["rating"].notna().sum()),
    }

    by_prod = []
    for product, g in df.groupby("product"):
        by_prod.append({
            "product": product,
            "rows": int(len(g)),
            "sentiment_compound_mean": float(np.nanmean(g["sentiment_compound"])),
            "rating_mean": float(np.nanmean(g["rating"])) if g["rating"].notna().any() else float("nan"),
        })
    by_prod.sort(key=lambda x: x["rows"], reverse=True)

    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1 if len(df) < 10 else 2,
    )
    X = vectorizer.fit_transform(df["text"].tolist())
    n_topics = max(2, min(n_topics, X.shape[0]))

    km = KMeans(n_clusters=n_topics, n_init="auto", random_state=42)
    labels = km.fit_predict(X)
    df["topic_id"] = labels

    terms = np.array(vectorizer.get_feature_names_out())
    order_centroids = km.cluster_centers_.argsort(axis=1)[:, ::-1]

    topics: list[TopicSummary] = []
    for tid in range(n_topics):
        top_terms = terms[order_centroids[tid, :8]].tolist()
        g = df[df["topic_id"] == tid].copy().sort_values(["sentiment_compound"], ascending=True)

        examples = []
        for _, row in g.head(3).iterrows():
            examples.append({
                "date": None if pd.isna(row["date"]) else row["date"].isoformat(),
                "product": row["product"],
                "rating": None if pd.isna(row["rating"]) else float(row["rating"]),
                "sentiment_compound": float(row["sentiment_compound"]),
                "text": str(row["text"])[:280],
            })

        topics.append(TopicSummary(topic_id=int(tid), size=int(len(g)), top_terms=top_terms, examples=examples))

    topics.sort(key=lambda t: t.size, reverse=True)

    date_min = None if df["date"].isna().all() else df["date"].min().isoformat()
    date_max = None if df["date"].isna().all() else df["date"].max().isoformat()
    generated_at_utc = pd.Timestamp.now("UTC").isoformat()

    return AnalysisResults(
        generated_at_utc=generated_at_utc,
        rows=int(len(df)),
        date_min=date_min,
        date_max=date_max,
        sentiment_overall=overall,
        sentiment_by_product=by_prod,
        topics=topics,
    )
