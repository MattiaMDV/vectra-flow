from dataclasses import dataclass, field
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
    # Trend direction based on temporal sentiment change: "growing", "stable", or "declining".
    trend_direction: str = "stable"
    # Actionable recommendations derived from topic analysis.
    solutions: list[str] = field(default_factory=list)

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

    trend_direction = _compute_trend(df)
    solutions = _generate_solutions(topics, trend_direction)

    return AnalysisResults(
        generated_at_utc=generated_at_utc,
        rows=int(len(df)),
        date_min=date_min,
        date_max=date_max,
        sentiment_overall=overall,
        sentiment_by_product=by_prod,
        topics=topics,
        trend_direction=trend_direction,
        solutions=solutions,
    )


# ── Trend & solution helpers ──────────────────────────────────────────────────

_TREND_THRESHOLD = 0.05  # minimum sentiment delta to declare a trend


def _compute_trend(df: pd.DataFrame) -> str:
    """Return ``"growing"``, ``"declining"``, or ``"stable"`` for the dataset.

    Splits rows by date into two halves and compares average VADER compound
    sentiment.  Falls back to ``"stable"`` when dates are unavailable or all
    timestamps are identical.
    """
    dated = df.dropna(subset=["date"]).sort_values("date")
    if len(dated) < 4:
        return "stable"

    mid = len(dated) // 2
    first_half = float(np.nanmean(dated.iloc[:mid]["sentiment_compound"]))
    second_half = float(np.nanmean(dated.iloc[mid:]["sentiment_compound"]))
    delta = second_half - first_half

    if delta >= _TREND_THRESHOLD:
        return "growing"
    if delta <= -_TREND_THRESHOLD:
        return "declining"
    return "stable"


def _generate_solutions(topics: list[TopicSummary], trend_direction: str) -> list[str]:
    """Derive short, actionable recommendations from *topics* and *trend_direction*."""
    solutions: list[str] = []

    for t in topics:
        if not t.top_terms:
            continue
        term_phrase = ", ".join(t.top_terms[:4])

        avg_sentiment = float(np.nanmean([
            ex["sentiment_compound"] for ex in t.examples
        ])) if t.examples else 0.0

        if avg_sentiment < -0.1:
            solutions.append(
                f"Affrontare le problematiche relative a: {term_phrase}. "
                "I consumatori esprimono insoddisfazione — valuta miglioramenti rapidi."
            )
        elif avg_sentiment > 0.1:
            solutions.append(
                f"Valorizzare il punto di forza: {term_phrase}. "
                "Il sentiment positivo in quest'area può essere amplificato con comunicazione mirata."
            )
        else:
            solutions.append(
                f"Monitorare l'area: {term_phrase}. "
                "Il sentiment è neutro — potrebbe evolversi in opportunità o rischio."
            )

    if trend_direction == "growing":
        solutions.append(
            "Il trend complessivo è in crescita: capitalizza lo slancio positivo "
            "con promozioni o lancio di nuovi prodotti/servizi."
        )
    elif trend_direction == "declining":
        solutions.append(
            "Il trend complessivo è in calo: intervieni con azioni correttive urgenti "
            "(assistenza clienti, revisione qualità, campagna di recupero)."
        )
    else:
        solutions.append(
            "Il trend è stabile: mantieni la qualità attuale e cerca "
            "segnali anticipatori di cambiamento nei topic emergenti."
        )

    return solutions
