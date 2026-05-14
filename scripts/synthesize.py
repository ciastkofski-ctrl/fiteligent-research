from __future__ import annotations
import json
import re
from datetime import date
from typing import Any

from scripts.lib.schema import Study
from scripts.lib.evidence import rate_study


SYNTH_SYSTEM_PROMPT = """You are a research digest writer for fiteligent.pl, the brand of Dr. Jakub Stanisławski (Polish, evidence-based health optimization).

You receive a JSON list of recent research studies + content items, each with:
- title, url, source, published, doi, journal, n, study_type, theme_guess, abstract, cited_by, evidence_rating (1-5)

You produce TWO outputs, separated by literal markers:

<<DIGEST_START>>
[Full English technical digest, ~4000-4500 words]
<<DIGEST_END>>
<<ANGLES_START>>
[Polish newsletter angles, 5-10 angles]
<<ANGLES_END>>

DIGEST structure (English, technical):
1. YAML front matter with date_range, studies_total, themes, generated timestamp
2. # Title with date
3. ## TL;DR (top 5 highlights, each with star rating)
4. Six theme sections in this exact order: Obesity & Metabolic Health, Longevity, Strength & Hypertrophy, Supplements, Sleep & Recovery, Skin & Hair Health
5. Each theme as a level-2 heading; each study as a level-3 heading
6. Per study: evidence stars, authors, journal, DOI link, n if known, study_type, then 150-200 word breakdown with effect sizes, p-values, key numbers if available. Then "Why it matters" (practical implication in 1-2 sentences). Then "Cited by" if the study has cited_by.
7. ## Sources scanned this week (counts per source)
8. ## Run notes (any partial coverage flagged)

ANGLES structure (Polish, in Jakub's voice: conversational, sarcastic-but-warm, no BS):
- 5-10 numbered angles
- Each: bold hook headline in Polish, 2-3 sentence pitch in Jakub's voice, suggested CTA in Polish, "Źródło w digest:" pointer, "Zalecany kąt newslettera:" mapping to one of: Psychology & Mindset, Medical Perspective, Practical How-to, Myth-Busting, The 3 Pillars, Disease Prevention, Marathon Not Sprint, Why People Fail, Patience & Compounds, Start Now

Do not invent studies or numbers. If a field is missing in the input, omit it from the output. Quote effect sizes and statistics verbatim from the abstract when present. Maintain scientific precision — terminology, units, p-values, sample sizes."""


def _study_to_llm_payload(s: Study) -> dict:
    return {
        "title": s.title,
        "url": s.url,
        "doi": s.doi,
        "authors": s.authors,
        "journal": s.journal,
        "published": s.published.isoformat(),
        "source": s.source,
        "abstract": s.abstract,
        "n": s.n,
        "study_type": s.study_type,
        "theme_guess": s.theme_guess,
        "cited_by": s.cited_by,
        "evidence_rating": rate_study(s),
    }


def _extract(text: str, start_marker: str, end_marker: str) -> str:
    pattern = re.escape(start_marker) + r"(.*?)" + re.escape(end_marker)
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def synthesize(
    client: Any,
    studies: list[Study],
    run_date: date,
    model: str = "claude-sonnet-4-6",
) -> tuple[str, str]:
    """LLM-generate digest.md + angles.md from filtered Study list."""

    payload = [_study_to_llm_payload(s) for s in studies]

    user_message = (
        f"Run date: {run_date.isoformat()}\n"
        f"Studies: {json.dumps(payload, indent=2, ensure_ascii=False)}"
    )

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        system=SYNTH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    digest_md = _extract(text, "<<DIGEST_START>>", "<<DIGEST_END>>")
    angles_md = _extract(text, "<<ANGLES_START>>", "<<ANGLES_END>>")

    if not digest_md or not angles_md:
        raise RuntimeError(
            f"Synthesizer output missing markers. Raw output:\n{text[:500]}..."
        )

    return digest_md, angles_md
