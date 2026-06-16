from api.utils.sentiment import analyze, batch_analyze, sentiment_stats


def test_analyze_structure():
    r = analyze("great product")
    for key in ("score", "label", "positive_signals", "negative_signals"):
        assert key in r


def test_analyze_positive():
    r = analyze("This is an amazing and great deal!")
    assert r["label"] == "positive"
    assert r["score"] > 0


def test_analyze_negative():
    r = analyze("This is terrible and awful, very bad quality")
    assert r["label"] == "negative"
    assert r["score"] < 0


def test_analyze_neutral_empty():
    r = analyze("")
    assert r["label"] == "neutral"
    assert r["score"] == 0.0


def test_analyze_neutral_no_keywords():
    r = analyze("the cat sat on the mat")
    assert r["label"] == "neutral"


def test_analyze_negation():
    r = analyze("not bad at all")
    assert r["positive_signals"] >= 1


def test_analyze_intensifier_boosts_weight():
    r1 = analyze("good product")
    r2 = analyze("very good product")
    assert r2["positive_signals"] >= r1["positive_signals"]


def test_analyze_score_range():
    r = analyze("best premium excellent amazing product")
    assert -1.0 <= r["score"] <= 1.0


def test_batch_analyze_empty():
    assert batch_analyze([]) == []


def test_batch_analyze_structure():
    results = batch_analyze(["great", "terrible"])
    assert len(results) == 2
    for r in results:
        assert "text" in r
        assert "label" in r


def test_batch_analyze_preserves_text():
    results = batch_analyze(["nice deal"])
    assert results[0]["text"] == "nice deal"


def test_sentiment_stats_empty():
    s = sentiment_stats([])
    assert s["count"] == 0
    assert s["avg_score"] == 0.0


def test_sentiment_stats_structure():
    s = sentiment_stats(["great", "terrible", "meh"])
    for key in ("count", "avg_score", "positive", "negative", "neutral"):
        assert key in s


def test_sentiment_stats_counts():
    s = sentiment_stats(["great deal", "terrible awful", "the cat"])
    assert s["positive"] >= 1
    assert s["negative"] >= 1
    assert s["count"] == 3
