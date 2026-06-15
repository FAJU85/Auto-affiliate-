"""Tests for caption quality evaluator (pydantic-evals integration)."""

import pytest
from api.ai.caption_evals import score_caption, PASS_THRESHOLD, CaptionScore


class TestCaptionScoreUnit:
    def test_good_english_passes(self):
        sc = score_caption("Upgrade your home office with Logitech MX Master 3 — ergonomic bliss. Shop now!")
        assert sc.passed
        assert sc.language == 1.0
        assert sc.cta == 1.0

    def test_arabic_fails_language(self):
        sc = score_caption("احصل على أفضل العروض الآن على منتجاتنا")
        assert sc.language == 0.0
        assert not sc.passed

    def test_camelcase_spam_fails_readability(self):
        sc = score_caption("NorthFaceThermoball SummerDeals ClickNow")
        assert sc.readability == 0.0
        assert not sc.passed

    def test_too_short_fails(self):
        sc = score_caption("Buy!")
        assert sc.length == 0.0
        assert not sc.passed

    def test_url_fails_no_url(self):
        sc = score_caption("Great deal https://example.com/product — grab it today!")
        assert sc.no_url == 0.0

    def test_hashtag_fails_no_url(self):
        sc = score_caption("Amazing headphones #Sony #Deal — get yours now!")
        assert sc.no_url == 0.0

    def test_template_fallback_passes(self):
        sc = score_caption("Save big on Sony WH-1000XM5 — just $279. Get it now!")
        assert sc.passed
        assert sc.total >= PASS_THRESHOLD

    def test_total_weighted_correctly(self):
        sc = CaptionScore(language=1.0, length=1.0, cta=1.0, readability=1.0, no_url=1.0)
        assert sc.total == pytest.approx(1.0)

    def test_pass_threshold_constant(self):
        assert 0.5 <= PASS_THRESHOLD <= 0.9

    def test_str_representation_contains_pass(self):
        sc = score_caption("Save big on Sony WH-1000XM5 — just $279. Get it now!")
        assert "PASS" in str(sc)

    def test_str_representation_contains_fail(self):
        sc = score_caption("احصل")
        assert "FAIL" in str(sc)

    def test_notes_populated_on_failure(self):
        sc = score_caption("احصل على أفضل العروض الآن")
        assert sc.notes

    def test_non_ascii_heavy_text_fails(self):
        # Text where >40% of chars are non-ASCII (all non-Latin)
        sc = score_caption("ΩΩΩΩΩ ΩΩΩΩΩ ΩΩΩΩΩ ΩΩΩΩΩ ΩΩΩΩΩ ΩΩΩΩΩ ΩΩΩΩΩ buy now!")
        assert sc.language == 0.0


class TestCaptionScoreLengthBand:
    def test_ideal_length(self):
        text = "x" * 50 + " buy now"
        sc = score_caption(text)
        assert sc.length == 1.0

    def test_slightly_short(self):
        sc = score_caption("Short text here, buy now!")  # 25 chars
        assert sc.length <= 1.0

    def test_slightly_long(self):
        text = "A" * 210 + " buy now"
        sc = score_caption(text)
        assert sc.length < 1.0


class TestBuildEvalDataset:
    def test_dataset_builds_without_error(self):
        from api.ai.caption_evals import build_eval_dataset
        result = build_eval_dataset()
        assert result is not None
        dataset, evaluator = result
        assert len(dataset.cases) >= 4

    def test_evaluator_callable(self):
        from api.ai.caption_evals import build_eval_dataset
        _, evaluator = build_eval_dataset()
        result = evaluator(
            {"text": "Save big on Sony WH-1000XM5 — just $279. Get it now!"},
            True
        )
        assert "passed" in result
        assert "score" in result
        assert result["passed"] is True
