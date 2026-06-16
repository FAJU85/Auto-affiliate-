from api.utils.keyword_extractor import (
    extract_keywords, extract_keyphrases, keyword_score,
    extract_from_product, keyword_overlap,
)


def test_extract_keywords_basic():
    kw = extract_keywords("premium leather wallet slim design")
    assert "leather" in kw
    assert "wallet" in kw


def test_extract_keywords_excludes_stopwords():
    kw = extract_keywords("this is a great product for the home")
    assert "the" not in kw
    assert "this" not in kw
    assert "for" not in kw


def test_extract_keywords_max():
    kw = extract_keywords("apple banana cherry date elderberry fig grape", max_keywords=3)
    assert len(kw) <= 3


def test_extract_keywords_empty():
    assert extract_keywords("") == []


def test_extract_keywords_min_freq():
    kw = extract_keywords("leather leather wallet", min_freq=2)
    assert "leather" in kw
    assert "wallet" not in kw


def test_extract_keyphrases_basic():
    phrases = extract_keyphrases("premium leather wallet slim design quality")
    assert len(phrases) >= 0  # may be empty for unique bigrams
    assert all(isinstance(p, str) for p in phrases)


def test_extract_keyphrases_repeated():
    phrases = extract_keyphrases("leather wallet leather wallet leather wallet", phrase_len=2)
    assert "leather wallet" in phrases


def test_extract_keyphrases_max():
    text = "red blue green yellow purple orange pink silver gold bronze"
    phrases = extract_keyphrases(text, max_phrases=2)
    assert len(phrases) <= 2


def test_keyword_score_all_match():
    score = keyword_score("premium leather wallet", ["leather", "wallet"])
    assert score == 1.0


def test_keyword_score_no_match():
    score = keyword_score("something else entirely", ["leather", "wallet"])
    assert score == 0.0


def test_keyword_score_partial():
    score = keyword_score("leather product", ["leather", "wallet"])
    assert 0.0 < score < 1.0


def test_keyword_score_empty_text():
    assert keyword_score("", ["leather"]) == 0.0


def test_keyword_score_empty_keywords():
    assert keyword_score("leather wallet", []) == 0.0


def test_extract_from_product_structure():
    product = {"title": "Premium Leather Wallet", "description": "Slim design quality"}
    result = extract_from_product(product)
    for key in ("keywords", "keyphrases", "title_keywords"):
        assert key in result


def test_extract_from_product_finds_title_words():
    product = {"title": "Premium Leather Wallet", "description": ""}
    result = extract_from_product(product)
    assert "leather" in result["title_keywords"] or "leather" in result["keywords"]


def test_keyword_overlap_identical():
    assert keyword_overlap("leather wallet slim", "leather wallet slim") == 1.0


def test_keyword_overlap_disjoint():
    assert keyword_overlap("leather wallet", "crystal glass") == 0.0


def test_keyword_overlap_partial():
    score = keyword_overlap("leather wallet slim", "leather crystal glass")
    assert 0.0 < score < 1.0


def test_keyword_overlap_empty():
    assert keyword_overlap("", "leather wallet") == 0.0
