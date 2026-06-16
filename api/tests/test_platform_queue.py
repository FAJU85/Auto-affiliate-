"""Tests for api/utils/platform_queue.py."""

from api.utils.platform_queue import get_enabled_platforms, PlatformResult, summarize_results


BLUESKY_CREDS = {"bskyHandle": "user.bsky.social", "bskyAppPassword": "secret"}
MASTODON_CREDS = {"mastodonInstance": "https://mastodon.social", "mastodonToken": "tok"}
X_CREDS = {
    "twitterApiKey": "k",
    "twitterApiSecret": "s",
    "twitterAccessToken": "at",
    "twitterAccessSecret": "as",
}
INSTAGRAM_CREDS = {"instagramToken": "ig_tok"}
FACEBOOK_CREDS = {"facebookToken": "fb_tok"}
THREADS_CREDS = {"threadsToken": "th_tok"}
TUMBLR_CREDS = {"tumblrApiKey": "tk", "tumblrApiSecret": "ts", "tumblrBlogName": "myblog"}


def test_no_creds_returns_empty():
    assert get_enabled_platforms({}) == []


def test_bluesky_enabled_with_both_creds():
    result = get_enabled_platforms(BLUESKY_CREDS)
    assert "bluesky" in result


def test_bluesky_excluded_missing_password():
    result = get_enabled_platforms({"bskyHandle": "user.bsky.social"})
    assert "bluesky" not in result


def test_bluesky_excluded_missing_handle():
    result = get_enabled_platforms({"bskyAppPassword": "secret"})
    assert "bluesky" not in result


def test_mastodon_enabled():
    result = get_enabled_platforms(MASTODON_CREDS)
    assert "mastodon" in result


def test_mastodon_excluded_missing_token():
    result = get_enabled_platforms({"mastodonInstance": "https://mastodon.social"})
    assert "mastodon" not in result


def test_x_enabled_with_all_four_creds():
    result = get_enabled_platforms(X_CREDS)
    assert "x" in result


def test_x_excluded_missing_one_cred():
    partial = {k: v for k, v in X_CREDS.items() if k != "twitterAccessSecret"}
    result = get_enabled_platforms(partial)
    assert "x" not in result


def test_all_platforms_enabled():
    settings = {**BLUESKY_CREDS, **MASTODON_CREDS, **X_CREDS,
                **INSTAGRAM_CREDS, **FACEBOOK_CREDS, **THREADS_CREDS, **TUMBLR_CREDS}
    result = get_enabled_platforms(settings)
    assert set(result) == {"bluesky", "mastodon", "x", "instagram", "facebook", "threads", "tumblr"}


def test_summarize_empty_list():
    result = summarize_results([])
    assert result == {"total": 0, "succeeded": 0, "failed": 0, "platforms": []}


def test_summarize_all_success():
    results = [PlatformResult("bluesky", True, post_url="https://bsky.app/p/1")]
    out = summarize_results(results)
    assert out["total"] == 1
    assert out["succeeded"] == 1
    assert out["failed"] == 0


def test_summarize_mixed():
    results = [
        PlatformResult("bluesky", True, post_url="https://bsky.app/p/1"),
        PlatformResult("mastodon", False, error="timeout"),
    ]
    out = summarize_results(results)
    assert out["total"] == 2
    assert out["succeeded"] == 1
    assert out["failed"] == 1


def test_summarize_platforms_list_shape():
    results = [PlatformResult("x", False, error="auth failed")]
    out = summarize_results(results)
    entry = out["platforms"][0]
    assert entry["platform"] == "x"
    assert entry["success"] is False
    assert entry["error"] == "auth failed"
    assert entry["post_url"] is None


def test_empty_string_cred_excluded():
    result = get_enabled_platforms({"bskyHandle": "", "bskyAppPassword": "secret"})
    assert "bluesky" not in result
