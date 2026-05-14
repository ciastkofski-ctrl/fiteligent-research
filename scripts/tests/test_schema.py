import json
from datetime import date
from scripts.lib.schema import Study, StudyList


def test_study_minimal_fields():
    s = Study(
        title="Semaglutide and resistance training",
        url="https://example.org/paper",
        source="pubmed",
        published=date(2026, 5, 1),
    )
    assert s.title == "Semaglutide and resistance training"
    assert s.doi is None
    assert s.theme_guess is None


def test_study_full_fields():
    s = Study(
        title="Effect of creatine on hypertrophy",
        url="https://doi.org/10.1234/example",
        doi="10.1234/example",
        authors=["Smith J", "Doe A"],
        journal="Cell Metabolism",
        published=date(2026, 5, 1),
        source="pubmed",
        abstract="A 12-week RCT...",
        n=180,
        study_type="RCT",
        theme_guess="strength",
        cited_by=["huberman_podcast_298"],
    )
    assert s.n == 180
    assert s.cited_by == ["huberman_podcast_298"]


def test_study_json_roundtrip():
    s = Study(
        title="Test",
        url="https://example.org",
        source="biorxiv",
        published=date(2026, 5, 1),
    )
    payload = s.model_dump_json()
    parsed = json.loads(payload)
    assert parsed["title"] == "Test"
    restored = Study.model_validate_json(payload)
    assert restored == s


def test_studylist_save_and_load(tmp_path):
    s1 = Study(title="A", url="https://a.org", source="pubmed", published=date(2026, 5, 1))
    s2 = Study(title="B", url="https://b.org", source="biorxiv", published=date(2026, 5, 2))
    lst = StudyList(studies=[s1, s2])
    path = tmp_path / "studies.json"
    lst.save(path)
    loaded = StudyList.load(path)
    assert len(loaded.studies) == 2
    assert loaded.studies[0].title == "A"
