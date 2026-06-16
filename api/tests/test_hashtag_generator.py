from api.utils.hashtag_generator import generate, format_hashtags


def test_returns_list():
    assert isinstance(generate("Wireless Headphones"), list)


def test_tags_start_with_hash():
    tags = generate("Cool Gadget", category="tech")
    assert all(t.startswith("#") for t in tags)


def test_max_tags_respected():
    tags = generate("Wireless Bluetooth Noise Cancelling Headphones Premium Quality", max_tags=3)
    assert len(tags) <= 3


def test_category_tags_included():
    tags = generate("some product", category="tech")
    assert "#tech" in tags


def test_stop_words_excluded():
    tags = generate("the best product for you")
    lower = [t.lower() for t in tags]
    assert "#the" not in lower
    assert "#for" not in lower
    assert "#you" not in lower


def test_deal_tags_when_enabled():
    tags = generate("Product Name", include_deal=True)
    assert "#deal" in tags or "#sale" in tags


def test_no_deal_tags_by_default():
    tags = generate("Product Name")
    assert "#deal" not in tags


def test_no_duplicates():
    tags = generate("Tech gadgets tech stuff", category="tech")
    assert len(tags) == len(set(tags))


def test_empty_title():
    tags = generate("")
    assert isinstance(tags, list)


def test_format_hashtags_space():
    tags = ["#tech", "#gadgets"]
    assert format_hashtags(tags) == "#tech #gadgets"


def test_format_hashtags_custom_separator():
    tags = ["#tech", "#gadgets"]
    assert format_hashtags(tags, separator="\n") == "#tech\n#gadgets"


def test_format_empty():
    assert format_hashtags([]) == ""


def test_short_words_excluded():
    tags = generate("an ox")
    assert "#ox" not in tags


def test_beauty_category():
    tags = generate("Face Cream", category="beauty")
    assert "#beauty" in tags or "#skincare" in tags


def test_tags_lowercase():
    tags = generate("PREMIUM WIRELESS HEADPHONES", category="tech")
    assert all(t == t.lower() for t in tags)
