from api.utils.dedup_fingerprint import fingerprint, similarity, is_duplicate, deduplicate


def test_fingerprint_is_string():
    assert isinstance(fingerprint("hello world"), str)


def test_fingerprint_length():
    assert len(fingerprint("hello world")) == 16


def test_fingerprint_deterministic():
    assert fingerprint("Buy this now!") == fingerprint("Buy this now!")


def test_fingerprint_different_texts():
    assert fingerprint("apple") != fingerprint("orange")


def test_fingerprint_strips_urls():
    assert fingerprint("Check https://example.com out") == fingerprint("Check  out")


def test_fingerprint_case_insensitive():
    assert fingerprint("Hello World") == fingerprint("hello world")


def test_similarity_identical():
    assert similarity("the quick brown fox", "the quick brown fox") == 1.0


def test_similarity_empty():
    assert similarity("", "") == 1.0


def test_similarity_no_overlap():
    s = similarity("apple banana cherry", "dog elephant frog")
    assert s == 0.0


def test_similarity_partial():
    s = similarity("the quick brown fox jumps over", "the quick brown fox leaps over")
    assert 0.0 < s < 1.0


def test_is_duplicate_exact():
    assert is_duplicate("hello world foo bar", ["hello world foo bar"])


def test_is_duplicate_empty_seen():
    assert not is_duplicate("hello", [])


def test_is_duplicate_dissimilar():
    assert not is_duplicate("apple banana cherry mango", ["dog elephant frog tiger"])


def test_deduplicate_removes_near_dups():
    texts = [
        "the quick brown fox jumps high",
        "the quick brown fox jumps high",
        "completely different text here",
    ]
    result = deduplicate(texts)
    assert len(result) == 2


def test_deduplicate_empty():
    assert deduplicate([]) == []


def test_deduplicate_all_unique():
    texts = ["alpha beta gamma delta", "one two three four", "red green blue yellow"]
    assert len(deduplicate(texts)) == 3
