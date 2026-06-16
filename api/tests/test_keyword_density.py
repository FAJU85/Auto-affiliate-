from api.utils.keyword_density import keyword_density, coverage_score, top_keywords, keyword_overlap


def test_empty_text_returns_empty():
    assert keyword_density("") == {}


def test_stop_words_excluded():
    result = keyword_density("the and or is a an")
    assert result == {}


def test_word_frequencies_sum_to_1():
    result = keyword_density("apple apple banana cherry")
    assert abs(sum(result.values()) - 1.0) < 0.01


def test_most_common_word_highest_density():
    result = keyword_density("deal deal deal save once")
    assert list(result.keys())[0] == "deal"


def test_coverage_score_full_match():
    product = {"name": "Sony Headphones", "description": "", "category": "Electronics"}
    caption = "sony headphones electronics audio best deal"
    score = coverage_score(caption, product)
    assert score > 0.5


def test_coverage_score_no_match():
    product = {"name": "Sony Headphones", "description": "", "category": ""}
    score = coverage_score("completely unrelated text about cooking", product)
    assert score < 0.5


def test_coverage_score_empty_product():
    score = coverage_score("some caption text here", {})
    assert score == 1.0


def test_top_keywords_length():
    result = top_keywords("buy this amazing product deal offer sale today", n=3)
    assert len(result) <= 3


def test_top_keywords_returns_list():
    assert isinstance(top_keywords("buy now deal save"), list)


def test_keyword_overlap_identical():
    assert keyword_overlap("buy deal save now", "buy deal save now") == 1.0


def test_keyword_overlap_no_overlap():
    result = keyword_overlap("apple banana cherry", "xyz qrs abc")
    assert result == 0.0


def test_keyword_overlap_partial():
    result = keyword_overlap("apple banana cherry", "apple mango grape")
    assert 0 < result < 1.0


def test_keyword_overlap_empty_strings():
    assert keyword_overlap("", "") == 0.0
