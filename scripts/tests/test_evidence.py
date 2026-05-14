from datetime import date
from scripts.lib.evidence import rate_study
from scripts.lib.schema import Study


def _study(study_type=None, journal=None, n=None, source="pubmed"):
    return Study(
        title="x", url="https://x.org", source=source,
        published=date(2026, 5, 1),
        study_type=study_type, journal=journal, n=n,
    )


def test_large_rct_in_high_impact_journal_is_five_stars():
    s = _study(study_type="RCT", journal="The Lancet", n=1200)
    assert rate_study(s) == 5


def test_meta_analysis_is_five_stars():
    s = _study(study_type="meta-analysis", n=None)
    assert rate_study(s) == 5


def test_small_rct_is_four_stars():
    s = _study(study_type="RCT", journal="Journal of Strength and Conditioning Research", n=120)
    assert rate_study(s) == 4


def test_cohort_study_is_three_stars():
    s = _study(study_type="cohort", n=2000)
    assert rate_study(s) == 3


def test_preprint_is_two_stars():
    s = _study(study_type="preprint", source="biorxiv")
    assert rate_study(s) == 2


def test_podcast_claim_without_source_is_one_star():
    s = _study(study_type="podcast", source="podcast")
    assert rate_study(s) == 1


def test_unknown_study_type_defaults_to_three():
    s = _study(study_type=None)
    assert rate_study(s) == 3
