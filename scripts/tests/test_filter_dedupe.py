import json
from datetime import date
from scripts.filter_dedupe import filter_new, update_seen, load_seen, save_seen
from scripts.lib.schema import Study


def test_empty_seen_keeps_all(sample_studies, tmp_path):
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(json.dumps({"by_doi": {}, "by_url": {}}))
    seen = load_seen(seen_path)
    new = filter_new(sample_studies, seen)
    assert len(new) == 3


def test_seen_doi_filters_out(sample_studies, tmp_path):
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(json.dumps({
        "by_doi": {"10.1/a": {"first_seen": "2026-04-30"}},
        "by_url": {},
    }))
    seen = load_seen(seen_path)
    new = filter_new(sample_studies, seen)
    titles = [s.title for s in new]
    assert "A" not in titles
    assert "B" in titles
    assert "C" in titles


def test_seen_url_filters_out_doi_less(sample_studies, tmp_path):
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(json.dumps({
        "by_doi": {},
        "by_url": {"https://c.org": {"first_seen": "2026-04-30"}},
    }))
    seen = load_seen(seen_path)
    new = filter_new(sample_studies, seen)
    assert "C" not in [s.title for s in new]


def test_update_seen_appends_new_entries(tmp_path):
    seen_path = tmp_path / "seen.json"
    seen_path.write_text(json.dumps({"by_doi": {}, "by_url": {}}))
    new_studies = [
        Study(title="X", url="https://x.org", doi="10.1/x", source="pubmed", published=date(2026, 5, 1)),
        Study(title="Y", url="https://y.org", source="examine", published=date(2026, 5, 2)),
    ]
    seen = load_seen(seen_path)
    update_seen(seen, new_studies, run_date=date(2026, 5, 15))
    save_seen(seen, seen_path)
    reloaded = load_seen(seen_path)
    assert "10.1/x" in reloaded["by_doi"]
    assert reloaded["by_doi"]["10.1/x"]["first_seen"] == "2026-05-15"
    assert "https://y.org" in reloaded["by_url"]
