from api.utils.word_count import count_words, word_stats, check_length, analyze_posts, posts_stats


def test_count_words_simple():
    assert count_words("hello world foo") == 3


def test_count_words_empty():
    assert count_words("") == 0


def test_count_words_punctuation():
    assert count_words("hello, world!") == 2


def test_word_stats_structure():
    s = word_stats("the quick brown fox")
    for key in ("count", "unique", "avg_length", "longest"):
        assert key in s


def test_word_stats_count():
    assert word_stats("one two three")["count"] == 3


def test_word_stats_unique():
    assert word_stats("the the cat")["unique"] == 2


def test_word_stats_longest():
    assert word_stats("cat elephant dog")["longest"] == "elephant"


def test_word_stats_empty():
    s = word_stats("")
    assert s["count"] == 0
    assert s["avg_length"] == 0.0


def test_check_length_optimal():
    text = " ".join(["word"] * 30)
    r = check_length(text, "bluesky")
    assert r["status"] == "optimal"


def test_check_length_too_short():
    r = check_length("hi there", "bluesky")
    assert r["status"] == "too_short"


def test_check_length_too_long():
    text = " ".join(["word"] * 200)
    r = check_length(text, "x")
    assert r["status"] == "too_long"


def test_check_length_unknown_platform():
    r = check_length("hello world", "myspace")
    assert r["status"] == "unknown"


def test_check_length_has_range():
    r = check_length("word " * 30, "bluesky")
    assert isinstance(r["optimal_range"], list)
    assert len(r["optimal_range"]) == 2


def test_analyze_posts_adds_word_count():
    posts = [{"content": "hello world test post here", "platform": "x"}]
    result = analyze_posts(posts)
    assert "word_count" in result[0]
    assert "length_status" in result[0]


def test_analyze_posts_empty():
    assert analyze_posts([]) == []


def test_posts_stats_empty():
    s = posts_stats([])
    assert s["count"] == 0


def test_posts_stats_values():
    posts = [{"content": "one two three"}, {"content": "four five six seven"}]
    s = posts_stats(posts)
    assert s["count"] == 2
    assert s["min"] == 3
    assert s["max"] == 4
