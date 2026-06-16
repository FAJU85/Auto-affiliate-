from api.utils.ab_exporter import to_json, to_csv, to_markdown, export_summary
import json


_RESULTS = [
    {"variant": "A", "clicks": 100, "conversions": 5, "stats": {"ctr": 0.05}},
    {"variant": "B", "clicks": 120, "conversions": 8, "stats": {"ctr": 0.067}},
]


def test_to_json_returns_string():
    assert isinstance(to_json(_RESULTS), str)


def test_to_json_valid():
    parsed = json.loads(to_json(_RESULTS))
    assert len(parsed) == 2


def test_to_json_empty():
    assert to_json([]) == "[]"


def test_to_csv_has_header():
    csv_out = to_csv(_RESULTS)
    assert "variant" in csv_out
    assert "clicks" in csv_out


def test_to_csv_has_rows():
    csv_out = to_csv(_RESULTS)
    lines = [l for l in csv_out.strip().splitlines() if l]
    assert len(lines) == 3  # header + 2 rows


def test_to_csv_empty():
    assert to_csv([]) == ""


def test_to_csv_flattens_nested():
    csv_out = to_csv(_RESULTS)
    assert "stats_ctr" in csv_out


def test_to_markdown_has_header_row():
    md = to_markdown(_RESULTS)
    assert "|" in md
    assert "variant" in md


def test_to_markdown_has_separator():
    md = to_markdown(_RESULTS)
    assert "---" in md


def test_to_markdown_empty():
    assert "No results" in to_markdown([])


def test_to_markdown_row_count():
    md = to_markdown(_RESULTS)
    lines = [l for l in md.strip().splitlines() if l]
    assert len(lines) == 4  # header + sep + 2 rows


def test_export_summary_structure():
    s = export_summary(_RESULTS)
    for key in ("exported_at", "count", "variants"):
        assert key in s


def test_export_summary_count():
    s = export_summary(_RESULTS)
    assert s["count"] == 2


def test_export_summary_variants():
    s = export_summary(_RESULTS)
    assert "A" in s["variants"]
    assert "B" in s["variants"]


def test_export_summary_empty():
    s = export_summary([])
    assert s["count"] == 0
    assert s["variants"] == []
