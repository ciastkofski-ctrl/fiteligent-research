from datetime import date
from unittest.mock import MagicMock
from scripts.synthesize import (
    synthesize,
    select_top_per_theme,
    SYNTH_SYSTEM_PROMPT,
    THEMES_ORDER,
)
from scripts.lib.schema import Study


FAKE_LLM_OUTPUT = """<<DIGEST_START>>
# Fiteligent Research Digest — 2026-05-15

## TL;DR
1. Semaglutide + RT preserves lean mass — ★★★★★

## Obesity & Metabolic Health
### Semaglutide and resistance training preserves lean mass during weight loss
Some body text here.
<<DIGEST_END>>
<<ANGLES_START>>
# Kąty redakcyjne — 2026-05-15

## Kąt 1 — "GLP-1 nie niszczy mięśni"
**Hook:** Każdy mówi, że...
<<ANGLES_END>>"""


def _mock_streaming_client(text: str) -> MagicMock:
    """Mock anthropic.Anthropic where messages.stream() yields `text` once."""
    client = MagicMock()
    stream_ctx = client.messages.stream.return_value
    stream_ctx.__enter__.return_value.text_stream = iter([text])
    return client


def test_synthesize_splits_digest_and_angles():
    mock_client = _mock_streaming_client(FAKE_LLM_OUTPUT)

    studies = [
        Study(
            title="Semaglutide and RT",
            url="https://pubmed.ncbi.nlm.nih.gov/40000001/",
            source="pubmed",
            published=date(2026, 5, 5),
            theme_guess="obesity",
            study_type="RCT",
            journal="Cell Metab",
            n=180,
        ),
    ]

    digest_md, angles_md = synthesize(mock_client, studies, run_date=date(2026, 5, 15))

    assert "Fiteligent Research Digest" in digest_md
    assert "<<DIGEST_START>>" not in digest_md
    assert "<<DIGEST_END>>" not in digest_md

    assert "Kąty redakcyjne" in angles_md
    assert "<<ANGLES_START>>" not in angles_md

    call_args = mock_client.messages.stream.call_args
    assert call_args.kwargs["system"] == SYNTH_SYSTEM_PROMPT


def _study(theme, rating_inputs, pub_day=1):
    """Build a Study whose evidence rating is driven by study_type/journal/n.

    rating_inputs is a (study_type, journal, n) tuple — kept explicit so the
    test reads the way the ranking logic actually works.
    """
    study_type, journal, n = rating_inputs
    return Study(
        title=f"{theme}-{pub_day}-{study_type}",
        url=f"https://example.com/{theme}/{pub_day}",
        source="pubmed",
        published=date(2026, 5, pub_day),
        theme_guess=theme,
        study_type=study_type,
        journal=journal,
        n=n,
    )


def test_select_top_per_theme_caps_each_theme_and_ranks_by_evidence():
    # 10 obesity studies — only top 5 should survive; meta-analysis & big RCT first.
    obesity_studies = [
        _study("obesity", ("meta-analysis", "PLoS ONE", None), pub_day=1),  # 5
        _study("obesity", ("RCT", "NEJM", 800), pub_day=2),                  # 5
        _study("obesity", ("RCT", "PLoS ONE", 50), pub_day=3),               # 4
        _study("obesity", ("cohort", "PLoS ONE", None), pub_day=4),          # 3
        _study("obesity", ("preprint", "bioRxiv", None), pub_day=5),         # 2
        _study("obesity", ("RCT", "PLoS ONE", 50), pub_day=6),               # 4 (newer)
        _study("obesity", ("cohort", "PLoS ONE", None), pub_day=7),          # 3
        _study("obesity", ("preprint", "bioRxiv", None), pub_day=8),         # 2
        _study("obesity", ("cohort", "PLoS ONE", None), pub_day=9),          # 3
        _study("obesity", ("opinion", None, None), pub_day=10),              # 3 (default)
    ]
    # A second theme to confirm per-theme bucketing (not global top-N).
    sleep_studies = [
        _study("sleep", ("RCT", "NEJM", 800), pub_day=1),                    # 5
        _study("sleep", ("cohort", "PLoS ONE", None), pub_day=2),            # 3
    ]
    # Theme_guess=None should be dropped.
    orphan = Study(
        title="orphan", url="https://example.com/orphan",
        source="pubmed", published=date(2026, 5, 1),
        theme_guess=None, study_type="RCT", journal="NEJM", n=1000,
    )

    selected = select_top_per_theme(obesity_studies + sleep_studies + [orphan], per_theme=5)

    obesity_out = [s for s in selected if s.theme_guess == "obesity"]
    sleep_out = [s for s in selected if s.theme_guess == "sleep"]
    assert len(obesity_out) == 5
    assert len(sleep_out) == 2  # only 2 inputs, cap doesn't pad
    assert all(s.theme_guess is not None for s in selected)
    # Highest-rated obesity study (meta-analysis or big-RCT-in-NEJM) should rank first.
    assert obesity_out[0].study_type in ("meta-analysis", "RCT")
    # Themes appear in canonical order, not input order.
    seen_themes = [s.theme_guess for s in selected]
    assert seen_themes.index("obesity") < seen_themes.index("sleep")


def test_select_top_per_theme_caps_total_at_six_themes_times_n():
    # 20 studies in every theme → output bounded at 6 × per_theme.
    inputs = []
    for theme in THEMES_ORDER:
        for day in range(1, 21):
            inputs.append(_study(theme, ("RCT", "PLoS ONE", 50), pub_day=day))
    selected = select_top_per_theme(inputs, per_theme=5)
    assert len(selected) == 6 * 5
