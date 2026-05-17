from __future__ import annotations
import json
import re
from datetime import date
from typing import Any

from scripts.lib.schema import Study, ThemeKind
from scripts.lib.evidence import rate_study

THEMES_ORDER: tuple[ThemeKind, ...] = (
    "obesity", "longevity", "strength", "supplements", "sleep", "skin_hair",
)
DEFAULT_PER_THEME_CAP = 3
MAX_TOKENS_OUT = 16000


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

DIGEST structure (English, technical, NEUTRAL TONE):
1. YAML front matter with date_range, studies_total, themes, generated timestamp
2. # Title with date
3. ## TL;DR (top 5 highlights, each with star rating)
4. Six theme sections in this exact order: Obesity & Metabolic Health, Longevity, Strength & Hypertrophy, Supplements, Sleep & Recovery, Skin & Hair Health
5. Each theme as a level-2 heading; each study as a level-3 heading
6. Per study, in this exact order:
   a. ### Heading with study title
   b. One-line metadata: evidence stars · n if known · study_type
   c. Blank line, then 150-200 word NEUTRAL factual description. Cover methodology, sample, intervention, key findings, effect sizes, p-values, confidence intervals, and limitations the abstract explicitly states. DO NOT use editorial adjectives ("impressive", "striking", "remarkable", "nuanced", "blunt instrument", "ethically obligatory", "compelling"). DO NOT add interpretive commentary or recommendations. Just describe what the study did and what it found, the way a textbook would.
   d. Blank line, then `Cited by: ...` line if cited_by is non-empty
   e. Blank line, then on its own line: `**Source:** [Authors. Journal (Year). DOI: 10.xxx](https://doi.org/10.xxx)` — use the study.url as the link target if no DOI is available, otherwise build the URL as `https://doi.org/<doi>`. Format the link text as "FirstAuthor et al. JournalName (YYYY). DOI: <doi>". If no DOI, fall back to "FirstAuthor et al. JournalName (YYYY)".
   DO NOT include a "Why it matters" or any editorial commentary section. The digest is a neutral reference; brand voice lives only in `angles`.
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


def select_top_per_theme(
    studies: list[Study],
    per_theme: int = DEFAULT_PER_THEME_CAP,
) -> list[Study]:
    """Pick the strongest `per_theme` studies in each of the 6 themes.

    Ranking within a theme: evidence_rating desc, then published desc, then
    cited_by length desc. Studies with no theme_guess are dropped (they would
    not fit the 6-section digest structure anyway).
    """
    by_theme: dict[ThemeKind, list[Study]] = {t: [] for t in THEMES_ORDER}
    for s in studies:
        if s.theme_guess in by_theme:
            by_theme[s.theme_guess].append(s)

    selected: list[Study] = []
    for theme in THEMES_ORDER:
        ranked = sorted(
            by_theme[theme],
            key=lambda s: (rate_study(s), s.published, len(s.cited_by)),
            reverse=True,
        )
        selected.extend(ranked[:per_theme])
    return selected


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

    text = ""
    stop_reason = None
    with client.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS_OUT,
        system=SYNTH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for chunk in stream.text_stream:
            text += chunk
        final = stream.get_final_message()
        stop_reason = final.stop_reason
        usage = final.usage

    digest_md = _extract(text, "<<DIGEST_START>>", "<<DIGEST_END>>")
    angles_md = _extract(text, "<<ANGLES_START>>", "<<ANGLES_END>>")

    if not digest_md or not angles_md:
        raise RuntimeError(
            f"Synthesizer output missing markers. "
            f"stop_reason={stop_reason}, output_tokens={usage.output_tokens}, "
            f"raw_chars={len(text)}.\nTail of output:\n...{text[-500:]}"
        )

    return digest_md, angles_md
