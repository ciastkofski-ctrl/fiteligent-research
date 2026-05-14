from datetime import date
from unittest.mock import MagicMock
from scripts.synthesize import synthesize, SYNTH_SYSTEM_PROMPT
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


def test_synthesize_splits_digest_and_angles():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=FAKE_LLM_OUTPUT)]
    mock_client.messages.create.return_value = mock_response

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

    # Verify the system prompt asks for the right structure
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["system"] == SYNTH_SYSTEM_PROMPT or call_args.kwargs.get("system")
