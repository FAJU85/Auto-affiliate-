from api.utils.emoji_injector import category_emoji, sentiment_emoji, inject_emoji, strip_emoji


def test_category_emoji_returns_list():
    assert isinstance(category_emoji("Electronics"), list)


def test_category_emoji_electronics():
    emojis = category_emoji("Electronics")
    assert len(emojis) > 0


def test_category_emoji_unknown_falls_back_to_general():
    result = category_emoji("Unknown")
    assert result == category_emoji("General")


def test_sentiment_emoji_deal():
    result = sentiment_emoji("Save big on this amazing deal today!")
    assert result in ("💸", "⏰")


def test_sentiment_emoji_urgency():
    result = sentiment_emoji("Limited time only! Ends today!")
    assert result == "⏰"


def test_inject_emoji_adds_emoji():
    caption = "Great headphones at a great price"
    result = inject_emoji(caption, {"category": "Electronics"})
    assert result != caption


def test_inject_emoji_empty_caption():
    assert inject_emoji("", {"category": "Electronics"}) == ""


def test_inject_emoji_respects_max():
    caption = "Buy now!"
    result = inject_emoji(caption, {"category": "General"}, max_emoji=1)
    emoji_count = len([c for c in result if ord(c) > 127])
    assert emoji_count <= 3


def test_inject_emoji_does_not_duplicate_when_enough():
    caption = "Amazing deal! ⚡⚡"
    result = inject_emoji(caption, {"category": "Electronics"}, max_emoji=2)
    assert result == caption


def test_strip_emoji_removes_emojis():
    result = strip_emoji("Great product! ⚡🎧")
    assert "⚡" not in result
    assert "🎧" not in result


def test_strip_emoji_returns_string():
    assert isinstance(strip_emoji("hello 🌍"), str)


def test_all_categories_have_emoji():
    from api.utils.emoji_injector import _CATEGORY_EMOJI
    for cat, emojis in _CATEGORY_EMOJI.items():
        assert len(emojis) > 0, f"No emoji for {cat}"
