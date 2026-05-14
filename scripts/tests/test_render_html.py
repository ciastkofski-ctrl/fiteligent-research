from pathlib import Path
from scripts.render_html import render_digest, render_angles


SAMPLE_DIGEST_MD = """---
date_range: 2026-05-01 → 2026-05-15
studies_total: 2
---

# Fiteligent Research Digest — 2026-05-15

## TL;DR
1. ★★★★★ Sample obesity finding

## Obesity & Metabolic Health (1 study)

### Sample obesity study
**Evidence:** ★★★★★ · **Journal:** Cell Metabolism

Body text here.

## Sleep & Recovery (1 study)

### Sample sleep study
Body text here.
"""


def test_render_digest_applies_theme_classes(tmp_path):
    brand_dir = Path("brand")  # uses real templates from repo
    out_path = tmp_path / "digest.html"
    render_digest(SAMPLE_DIGEST_MD, brand_dir, out_path, run_date_str="2026-05-15")
    html = out_path.read_text(encoding="utf-8")

    assert "Fiteligent Research Digest" in html
    assert 'class="theme-obesity"' in html or 'theme-obesity' in html
    assert 'class="theme-sleep"' in html or 'theme-sleep' in html
    assert "tokens.css" not in html  # CSS is inlined, not linked
    assert "--brand-primary" in html  # tokens were inlined


def test_render_angles_creates_html(tmp_path):
    brand_dir = Path("brand")
    out_path = tmp_path / "angles.html"
    render_angles("# Kąty\n\n## Kąt 1\nTreść.", brand_dir, out_path, run_date_str="2026-05-15")
    html = out_path.read_text(encoding="utf-8")
    assert "Kąty" in html
    assert "Editorial Angles" in html
