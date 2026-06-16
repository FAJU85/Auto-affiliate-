from api.utils.feed_classifier import classify, classify_batch, category_counts


def test_classify_electronics():
    assert classify("Bluetooth Headphones") == "electronics"


def test_classify_fashion():
    assert classify("Women's Running Shoes") == "fashion"


def test_classify_beauty():
    assert classify("Anti-aging Face Cream") == "beauty"


def test_classify_fitness():
    assert classify("Adjustable Dumbbell Set") == "fitness"


def test_classify_food():
    assert classify("Organic Green Tea") == "food"


def test_classify_home():
    assert classify("Memory Foam Pillow") == "home"


def test_classify_pets():
    assert classify("Dog Collar Adjustable") == "pets"


def test_classify_default_unknown():
    assert classify("xyzzy quux frobble") == "general"


def test_classify_uses_description():
    assert classify("Widget", description="Bluetooth speaker wireless gadget") == "electronics"


def test_classify_batch_adds_category():
    items = [{"title": "Yoga Mat", "description": ""}]
    result = classify_batch(items)
    assert "category" in result[0]


def test_classify_batch_preserves_fields():
    items = [{"title": "Yoga Mat", "price": 29.99}]
    result = classify_batch(items)
    assert result[0]["price"] == 29.99


def test_classify_batch_empty():
    assert classify_batch([]) == []


def test_category_counts_structure():
    items = [
        {"title": "Headphones"},
        {"title": "Laptop"},
        {"title": "Yoga Mat"},
    ]
    counts = category_counts(items)
    assert isinstance(counts, dict)
    assert all(isinstance(v, int) for v in counts.values())


def test_category_counts_sorted():
    items = [{"title": "Headphones"}, {"title": "Laptop"}, {"title": "Yoga Mat fitness workout"}]
    counts = category_counts(items)
    values = list(counts.values())
    assert values == sorted(values, reverse=True)


def test_category_counts_uses_existing_category():
    items = [{"title": "anything", "category": "electronics"}]
    counts = category_counts(items)
    assert counts.get("electronics", 0) == 1
