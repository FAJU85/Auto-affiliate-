"""Static registry of all 30 feature builds shipped in this project."""

BUILDS: list[dict] = [
    {
        "number": 1,
        "title": "Product scoring",
        "description": "5-dimension weighted scorer (price, rating, recency, relevance, commission) to rank affiliate products before posting.",
        "files_added": ["api/utils/scorer.py"],
        "test_count": 6,
    },
    {
        "number": 2,
        "title": "CTR feedback loop",
        "description": "Click-through rate boost that reweights the product scorer based on historical click data per category.",
        "files_added": ["api/utils/ctr_feedback.py"],
        "test_count": 5,
    },
    {
        "number": 3,
        "title": "Smart scheduling",
        "description": "Peak-hour detection that analyses run history to suggest optimal posting times and auto-adjusts the cron window.",
        "files_added": ["api/utils/smart_schedule.py"],
        "test_count": 6,
    },
    {
        "number": 4,
        "title": "A/B testing",
        "description": "50/50 caption variant split-test framework that tracks impressions and clicks per variant to pick the winner.",
        "files_added": ["api/utils/ab_test.py"],
        "test_count": 7,
    },
    {
        "number": 5,
        "title": "Retry queue",
        "description": "3-attempt retry mechanism for failed social posts with exponential back-off and persistent queue storage.",
        "files_added": ["api/utils/retry_queue.py"],
        "test_count": 8,
    },
    {
        "number": 6,
        "title": "Price tracker",
        "description": "Monitors product prices across runs and triggers alerts when a price drops ≥ 20% from the baseline.",
        "files_added": ["api/utils/price_tracker.py"],
        "test_count": 6,
    },
    {
        "number": 7,
        "title": "Dedup TTL control",
        "description": "Exposes DEDUP_TTL_HOURS env var so operators can tune how long a product URL is suppressed after posting.",
        "files_added": [],
        "test_count": 4,
    },
    {
        "number": 8,
        "title": "Revenue dashboard page",
        "description": "Commission KPI panel in the dashboard showing estimated earnings, click revenue, and per-network breakdown.",
        "files_added": [],
        "test_count": 3,
    },
    {
        "number": 9,
        "title": "Hashtag optimizer",
        "description": "Per-category CTR-ranked hashtag library; automatically appends the top-performing tags to every caption.",
        "files_added": ["api/utils/hashtags.py"],
        "test_count": 7,
    },
    {
        "number": 10,
        "title": "Budget forecasting & spend alerts",
        "description": "Tracks daily AI-API spend, forecasts monthly cost, and sends alerts when the configurable cap is approached.",
        "files_added": ["api/utils/budget.py"],
        "test_count": 8,
    },
    {
        "number": 11,
        "title": "Multi-platform posting queue",
        "description": "Decoupled per-platform queue that lets each social channel post independently with its own retry state.",
        "files_added": ["api/utils/platform_queue.py"],
        "test_count": 6,
    },
    {
        "number": 12,
        "title": "Next-fire-time schedule endpoint",
        "description": "GET /api/schedule/next returns the scheduler's next-fire datetime so the dashboard can show a live countdown.",
        "files_added": [],
        "test_count": 4,
    },
    {
        "number": 13,
        "title": "Product category auto-detection",
        "description": "Keyword-based classifier that assigns a category label to each product for hashtag and scoring lookups.",
        "files_added": ["api/utils/category.py"],
        "test_count": 8,
    },
    {
        "number": 14,
        "title": "Caption length optimizer",
        "description": "Per-platform character-limit enforcer that trims or expands AI captions to the optimal length for each network.",
        "files_added": ["api/utils/caption_length.py"],
        "test_count": 7,
    },
    {
        "number": 15,
        "title": "Run history analytics",
        "description": "Stores structured run records and exposes GET /api/history with pagination, filtering, and summary stats.",
        "files_added": [],
        "test_count": 6,
    },
    {
        "number": 16,
        "title": "Affiliate link click tracker",
        "description": "Intercept-and-redirect endpoint that logs every outbound affiliate click with timestamp and product metadata.",
        "files_added": [],
        "test_count": 5,
    },
    {
        "number": 17,
        "title": "Product blacklist",
        "description": "Persistent block-list of product URLs/keywords that are skipped during feed ingestion to avoid banned items.",
        "files_added": ["api/utils/blacklist.py"],
        "test_count": 7,
    },
    {
        "number": 18,
        "title": "Per-platform post deduplication",
        "description": "Separate dedup namespaces per social platform so a product can post on Bluesky even if already seen on X.",
        "files_added": [],
        "test_count": 6,
    },
    {
        "number": 19,
        "title": "Trend keyword injector",
        "description": "Fetches trending search terms and injects the most relevant ones into captions to boost discoverability.",
        "files_added": ["api/utils/trends.py"],
        "test_count": 5,
    },
    {
        "number": 20,
        "title": "Feed health monitor",
        "description": "Polls each affiliate feed on a schedule, records latency and error rates, and surfaces degraded feeds in the dashboard.",
        "files_added": ["api/utils/feed_health.py"],
        "test_count": 7,
    },
    {
        "number": 21,
        "title": "Dashboard analytics panel",
        "description": "Rich analytics page with post-history charts, platform breakdown, and click-trend visualisations.",
        "files_added": [],
        "test_count": 3,
    },
    {
        "number": 22,
        "title": "Post preview dry-run endpoint",
        "description": "POST /api/preview generates a full caption + image selection without publishing, for UI preview before posting.",
        "files_added": [],
        "test_count": 6,
    },
    {
        "number": 23,
        "title": "Commission rate manager",
        "description": "Stores per-network commission rates and exposes CRUD endpoints so operators can tune revenue estimates.",
        "files_added": ["api/utils/commission.py"],
        "test_count": 7,
    },
    {
        "number": 24,
        "title": "Outbound notification webhook",
        "description": "Fires a configurable webhook URL after each pipeline run with a JSON payload of run results.",
        "files_added": ["api/utils/webhook.py"],
        "test_count": 6,
    },
    {
        "number": 25,
        "title": "Post scheduling queue",
        "description": "Operator-controlled queue for scheduling future posts at specific datetimes, with preview and cancel support.",
        "files_added": ["api/utils/post_queue.py"],
        "test_count": 8,
    },
    {
        "number": 26,
        "title": "Post preview dry-run endpoint",
        "description": "Dedicated dry-run mode that exercises the full pipeline but skips publishing, returning a structured preview payload.",
        "files_added": [],
        "test_count": 5,
    },
    {
        "number": 27,
        "title": "Commission rate manager",
        "description": "Extended commission management with per-product overrides and a dashboard editor for rate configuration.",
        "files_added": [],
        "test_count": 6,
    },
    {
        "number": 28,
        "title": "Outbound notification webhook",
        "description": "Webhook dispatcher with configurable retry, HMAC signature verification, and a delivery-history log.",
        "files_added": [],
        "test_count": 6,
    },
    {
        "number": 29,
        "title": "Post scheduling queue",
        "description": "Priority-based post scheduling queue with cron-compatible time expressions and dashboard management UI.",
        "files_added": [],
        "test_count": 7,
    },
    {
        "number": 30,
        "title": "Build history registry & dashboard panel",
        "description": "Static registry of all 30 feature builds with GET /api/builds endpoint and a Builds dashboard panel.",
        "files_added": ["api/utils/build_registry.py", "api/tests/test_build_registry.py"],
        "test_count": 8,
    },
]


def get_builds() -> list[dict]:
    """Return all builds sorted by number."""
    return sorted(BUILDS, key=lambda b: b["number"])


def get_build(number: int) -> dict | None:
    """Return a single build by number, or None if not found."""
    for b in BUILDS:
        if b["number"] == number:
            return b
    return None
