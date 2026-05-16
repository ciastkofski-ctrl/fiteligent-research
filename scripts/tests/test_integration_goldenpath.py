import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock
from scripts.lib.schema import StudyList
from scripts.filter_dedupe import filter_new, update_seen
from scripts.synthesize import synthesize
from scripts.render_html import render_digest, render_angles


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_studies.json"


def _load_fixture_studies():
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return StudyList.model_validate(data).studies


FAKE_DIGEST_OUTPUT = """<<DIGEST_START>>
---
date_range: 2026-05-01 → 2026-05-15
studies_total: 6
themes: [obesity, longevity, strength, supplements, sleep, skin_hair]
---

# Fiteligent Research Digest — 2026-05-15

## TL;DR
1. ★★★★★ Semaglutide + RT preserves lean mass — Cell Metab RCT
2. ★★★★★ Creatine 10g/day no better than 5g/day — meta-analysis (k=14)
3. ★★★★☆ Microneedling + minoxidil 1.7x hair density vs monotherapy
4. ★★★☆☆ Sleep restriction blunts post-RT MPS by 27%
5. ★★☆☆☆ Rapamycin extends mouse lifespan 21% — preprint

## Obesity & Metabolic Health
### Semaglutide + RT preserves lean mass
Body text.

## Longevity
### Rapamycin in aged mice
Body text.

## Strength & Hypertrophy
### Creatine 5g/day vs 10g/day
Body text.

## Supplements
### Examine: ashwagandha and sleep
Body text.

## Sleep & Recovery
### Sleep restriction blunts MPS
Body text.

## Skin & Hair Health
### Microneedling + minoxidil for AGA
Body text.

## Sources scanned this week
- PubMed: 4 studies
<<DIGEST_END>>
<<ANGLES_START>>
# Kąty redakcyjne — 2026-05-15

## Kąt 1 — "GLP-1 nie niszczy mięśni"
Pitch.
<<ANGLES_END>>"""


def test_full_pipeline_with_mocked_llm(tmp_path):
    studies = _load_fixture_studies()

    # Filter with empty seen — all 6 are new
    seen = {"by_doi": {}, "by_url": {}}
    new_studies = filter_new(studies, seen)
    assert len(new_studies) == 6

    # Synthesize (mocked streaming client)
    mock_client = MagicMock()
    stream_ctx = mock_client.messages.stream.return_value
    stream_ctx.__enter__.return_value.text_stream = iter([FAKE_DIGEST_OUTPUT])

    digest_md, angles_md = synthesize(mock_client, new_studies, run_date=date(2026, 5, 15))
    assert "Fiteligent Research Digest" in digest_md
    assert "Skin & Hair Health" in digest_md
    assert "Kąty redakcyjne" in angles_md

    # Render
    brand_dir = Path(__file__).resolve().parents[2] / "brand"
    digest_html_path = tmp_path / "digest.html"
    render_digest(digest_md, brand_dir, digest_html_path, run_date_str="2026-05-15")

    html = digest_html_path.read_text(encoding="utf-8")
    assert "Fiteligent Research Digest" in html
    # All 6 themes' classes should appear
    for cls in ("theme-obesity", "theme-longevity", "theme-strength",
                "theme-supplements", "theme-sleep", "theme-skin-hair"):
        assert cls in html, f"missing theme class: {cls}"

    # Update seen
    update_seen(seen, new_studies, run_date=date(2026, 5, 15))
    assert len(seen["by_doi"]) == 5  # 5 of 6 studies have DOIs
    assert len(seen["by_url"]) == 6

    # Re-filter with updated seen — everything should be dropped
    new_studies_round2 = filter_new(studies, seen)
    assert len(new_studies_round2) == 0
