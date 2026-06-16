from api.utils.caption_quality import score_caption, is_quality, rank_captions


def test_empty_caption_scores_zero():
    assert score_caption("")["total"] == 0.0


def test_empty_caption_has_no_breakdown():
    assert score_caption("")["breakdown"] == {}


def test_score_returns_required_keys():
    result = score_caption("Buy this amazing product now!")
    assert "total" in result
    assert "breakdown" in result


def test_breakdown_has_all_dimensions():
    bd = score_caption("Get this deal today! Amazing value.")["breakdown"]
    for key in ("length", "cta_present", "punctuation", "weak_words", "word_count"):
        assert key in bd


def test_cta_word_boosts_score():
    with_cta = score_caption("Get the best deal on Sony headphones now!")["total"]
    without_cta = score_caption("Sony headphones are amazing for music")["total"]
    assert with_cta > without_cta


def test_score_between_0_and_1():
    for caption in ["", "Buy!", "A" * 300, "Great product. Shop now today!"]:
        s = score_caption(caption)["total"]
        assert 0.0 <= s <= 1.0, f"Score {s} out of range for: {caption!r}"


def test_is_quality_true_for_good_caption():
    assert is_quality("Upgrade your home with this amazing deal. Shop now!", threshold=0.4)


def test_is_quality_false_for_empty():
    assert not is_quality("", threshold=0.1)


def test_rank_captions_sorted_descending():
    captions = [
        "Buy this amazing product today! Great deal.",
        "thing",
        "Grab the best headphones on sale now. Limited time offer!",
    ]
    ranked = rank_captions(captions)
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_captions_returns_all():
    captions = ["A buy now!", "B today!", "C shop!"]
    assert len(rank_captions(captions)) == 3


def test_punctuation_present_boosts_score():
    with_p = score_caption("Buy this product now!")["breakdown"]["punctuation"]
    without_p = score_caption("Buy this product now")["breakdown"]["punctuation"]
    assert with_p >= without_p


def test_ideal_length_caption_scores_length_1():
    caption = "x" * 120
    bd = score_caption(caption)["breakdown"]
    assert bd["length"] == 1.0
