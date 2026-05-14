# Fiteligent Research Routine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a weekly automated routine that scans PubMed, journals, Examine.com, podcasts and 15 health-research influencers across 6 themes, then produces a branded English research digest + Polish newsletter angles every Friday 18:00 Europe/Warsaw.

**Architecture:** Python orchestrator runs in a remote scheduled agent. Pipeline = collect (hybrid APIs/RSS + LLM WebSearch) → filter (dedupe via persistent `seen.json`) → synthesize (LLM writes markdown) → render (Jinja2 + premailer applies fiteligent brandbook) → deliver (git commit + branded HTML email). Markdown is canonical; HTML is a pure-presentation derivative.

**Tech Stack:** Python 3.11+, httpx, pydantic v2, pyyaml, feedparser, jinja2, markdown-it-py, premailer, anthropic SDK, pytest. Claude Sonnet 4.6 for synthesis (cost-effective; 4000-word digest is well within its capability).

**Spec reference:** `docs/superpowers/specs/2026-05-14-fiteligent-research-routine-design.md`

---

## File Structure

```
fiteligent-research/
├── README.md                       # how to read/tune/run manually
├── pyproject.toml                  # pinned deps, pytest config
├── .env.example                    # required env vars
├── .gitignore
├── seen.json                       # dedupe state — bootstrapped empty {by_doi:{},by_url:{}}
│
├── config/
│   ├── topics.yaml                 # MeSH/keyword queries per theme (data only)
│   ├── sources.yaml                # API endpoints, RSS URLs, rate limits
│   └── influencers.yaml            # influencer names + URLs
│
├── brand/
│   ├── logo.svg                    # copied from fiteligent-newsletters/svg_export_claude/
│   ├── tokens.css                  # color/font/spacing CSS variables
│   ├── template_digest.html        # Jinja2: 720px dark-theme digest
│   ├── template_angles.html        # Jinja2: 600px newsletter-aligned
│   └── template_email.html         # Jinja2: email-safe (premailer-inlined)
│
├── scripts/
│   ├── __init__.py
│   ├── run.py                      # orchestrator entry point with CLI flags
│   ├── collect_structured.py       # PubMed + bioRxiv + journal RSS
│   ├── collect_unstructured.py     # WebSearch/WebFetch for Examine/podcasts/influencers
│   ├── filter_dedupe.py            # seen.json gate
│   ├── synthesize.py               # LLM → digest.md + angles.md
│   ├── render_html.py              # markdown → branded HTML
│   ├── notify.py                   # SMTP email delivery
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── schema.py               # Study pydantic model + JSON I/O
│   │   └── evidence.py             # study type → ★1-5 rating mapper
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py             # shared fixtures (sample Studies, mocked responses)
│       ├── test_schema.py
│       ├── test_evidence.py
│       ├── test_filter_dedupe.py
│       ├── test_render_html.py
│       └── test_integration_goldenpath.py
│
└── docs/superpowers/
    ├── specs/2026-05-14-fiteligent-research-routine-design.md  # exists
    └── plans/2026-05-14-fiteligent-research-routine-implementation.md  # this file
```

**File responsibilities (one-line each):**
- `lib/schema.py` — defines `Study` pydantic model; only file that knows the on-disk JSON shape
- `lib/evidence.py` — pure function `rate(study) -> int (1-5)` from study type + journal + n
- `filter_dedupe.py` — loads `seen.json`, filters list[Study], returns new ones; never mutates seen.json (caller does)
- `collect_structured.py` — three exported functions: `fetch_pubmed()`, `fetch_biorxiv()`, `fetch_journal_rss()`; each returns list[Study]
- `collect_unstructured.py` — single exported `collect_unstructured(config, lookback_days) -> list[Study]` using WebSearch
- `synthesize.py` — `synthesize(studies: list[Study]) -> tuple[str, str]` returns (digest_md, angles_md)
- `render_html.py` — `render(digest_md, angles_md, brand_dir, out_dir) -> dict[name, path]`
- `notify.py` — `send_email(subject, html_body, attachments) -> None`
- `run.py` — orchestrator, CLI argparse, ties everything together

---

## Task Order Rationale

Bottom-up: foundational types → filter logic → individual collectors → synthesis → rendering → delivery → orchestrator → integration test → docs → cron registration. Each task produces independently testable output.

---

### Task 1: Bootstrap repo scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md` (placeholder; expanded in Task 16)
- Create: `scripts/__init__.py` (empty)
- Create: `scripts/lib/__init__.py` (empty)
- Create: `scripts/tests/__init__.py` (empty)
- Create: `seen.json`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
.pytest_cache/
*.egg-info/

# Environment
.env

# OS
.DS_Store
Thumbs.db

# Dry-run outputs
digests/_dry/

# IDE
.vscode/
.idea/
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "fiteligent-research"
version = "0.1.0"
description = "Weekly automated research-curation routine for fiteligent.pl"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.7.0",
    "pyyaml>=6.0.1",
    "feedparser>=6.0.11",
    "jinja2>=3.1.4",
    "markdown-it-py>=3.0.0",
    "premailer>=3.10.0",
    "anthropic>=0.40.0",
    "python-dotenv>=1.0.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.14.0",
    "respx>=0.21.1",
]

[tool.pytest.ini_options]
testpaths = ["scripts/tests"]
pythonpath = ["."]
```

- [ ] **Step 3: Create `.env.example`**

```
# Anthropic API (synthesis step)
ANTHROPIC_API_KEY=sk-ant-...

# SMTP (email delivery)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ciastkofski@gmail.com
SMTP_PASS=app-password-here
SMTP_FROM=ciastkofski@gmail.com
SMTP_TO=ciastkofski@gmail.com

# Optional: override default LLM model
ANTHROPIC_MODEL=claude-sonnet-4-6
```

- [ ] **Step 4: Create placeholder `README.md`**

```markdown
# fiteligent-research

Weekly research-curation routine for fiteligent.pl. See `docs/superpowers/specs/` for the full design, `docs/superpowers/plans/` for the implementation plan.

Quickstart and operational documentation will be added in Task 16.
```

- [ ] **Step 5: Create empty Python package markers and seen.json**

Create `scripts/__init__.py`, `scripts/lib/__init__.py`, `scripts/tests/__init__.py` as empty files.

Create `seen.json` with:
```json
{
  "by_doi": {},
  "by_url": {}
}
```

- [ ] **Step 6: Install dev dependencies**

Run: `pip install -e ".[dev]"`
Expected: dependencies install cleanly, `pytest --version` works.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore .env.example README.md scripts/__init__.py scripts/lib/__init__.py scripts/tests/__init__.py seen.json
git commit -m "feat: bootstrap fiteligent-research repo scaffolding"
```

---

### Task 2: Study schema (`lib/schema.py`)

**Files:**
- Create: `scripts/lib/schema.py`
- Test: `scripts/tests/test_schema.py`

- [ ] **Step 1: Write failing test for Study creation and JSON round-trip**

Create `scripts/tests/test_schema.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest scripts/tests/test_schema.py -v`
Expected: All FAIL with `ImportError: cannot import name 'Study'`.

- [ ] **Step 3: Implement `scripts/lib/schema.py`**

```python
from __future__ import annotations
import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

SourceKind = Literal[
    "pubmed", "biorxiv", "medrxiv", "rss", "examine", "podcast", "blog", "youtube", "reddit"
]

ThemeKind = Literal[
    "obesity", "longevity", "strength", "supplements", "sleep", "skin_hair"
]


class Study(BaseModel):
    """Canonical Study record — same shape regardless of which collector produced it."""

    title: str
    url: str
    source: SourceKind
    published: date

    # Optional metadata
    doi: str | None = None
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    abstract: str | None = None
    n: int | None = None
    study_type: str | None = None  # "RCT", "meta-analysis", "cohort", "preprint", "podcast", etc.
    theme_guess: ThemeKind | None = None
    cited_by: list[str] = Field(default_factory=list)

    def dedupe_key(self) -> str:
        """Stable key for dedupe: prefer DOI, fall back to URL."""
        return self.doi or self.url


class StudyList(BaseModel):
    """Wrapper for JSON I/O of study collections."""

    studies: list[Study]

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> StudyList:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_schema.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/schema.py scripts/tests/test_schema.py
git commit -m "feat(schema): add Study and StudyList models with JSON I/O"
```

---

### Task 3: Evidence rating (`lib/evidence.py`)

**Files:**
- Create: `scripts/lib/evidence.py`
- Test: `scripts/tests/test_evidence.py`

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/test_evidence.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest scripts/tests/test_evidence.py -v`
Expected: All FAIL with `ImportError`.

- [ ] **Step 3: Implement `scripts/lib/evidence.py`**

```python
from __future__ import annotations
from scripts.lib.schema import Study

HIGH_IMPACT_JOURNALS = {
    "the lancet", "nejm", "new england journal of medicine",
    "nature", "cell metabolism", "cell", "jama", "bmj",
    "cochrane database of systematic reviews",
}


def rate_study(study: Study) -> int:
    """Map study to evidence rating 1-5 stars.

    5 - meta-analysis OR large RCT (n>500) in high-impact journal
    4 - smaller RCT or strong cohort
    3 - observational with good controls / small RCT (default)
    2 - preprint, mechanistic, weak observational
    1 - opinion, anecdote, podcast claim without primary source
    """
    t = (study.study_type or "").lower()
    journal = (study.journal or "").lower()
    is_high_impact = journal in HIGH_IMPACT_JOURNALS

    if t == "meta-analysis":
        return 5
    if t == "rct":
        if (study.n or 0) > 500 and is_high_impact:
            return 5
        return 4
    if t == "cohort":
        return 3
    if t == "preprint" or study.source in ("biorxiv", "medrxiv"):
        return 2
    if study.source in ("podcast", "youtube", "reddit") and not study.cited_by:
        return 1
    return 3
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_evidence.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/evidence.py scripts/tests/test_evidence.py
git commit -m "feat(evidence): add 1-5 star evidence rating mapper"
```

---

### Task 4: Configuration files

**Files:**
- Create: `config/topics.yaml`
- Create: `config/sources.yaml`
- Create: `config/influencers.yaml`

These are data files. No tests — they're verified by being parsed in Task 6+.

- [ ] **Step 1: Create `config/topics.yaml`**

```yaml
# MeSH terms + free-text keywords per theme.
# Used by PubMed E-utilities and as keyword filters for RSS/journal feeds.

themes:
  obesity:
    label: "Obesity & Metabolic Health"
    pubmed_query: '("obesity"[MeSH] OR "metabolic syndrome"[MeSH] OR "weight loss"[MeSH] OR "GLP-1"[All Fields] OR "semaglutide"[All Fields] OR "tirzepatide"[All Fields])'
    keywords: [obesity, glp-1, semaglutide, tirzepatide, metabolic, insulin resistance, weight loss, bariatric]

  longevity:
    label: "Longevity"
    pubmed_query: '("longevity"[MeSH] OR "aging"[MeSH] OR "healthspan"[All Fields] OR "rapamycin"[All Fields] OR "senolytic"[All Fields] OR "caloric restriction"[All Fields])'
    keywords: [longevity, healthspan, aging, rapamycin, senolytic, mTOR, NAD, sirtuin, autophagy, hallmarks of aging]

  strength:
    label: "Strength & Hypertrophy"
    pubmed_query: '("resistance training"[MeSH] OR "muscle, skeletal"[MeSH] OR "hypertrophy"[All Fields] OR "1RM"[All Fields] OR "protein synthesis"[All Fields])'
    keywords: [hypertrophy, resistance training, strength, muscle protein synthesis, sets, reps, 1RM, periodization, deload]

  supplements:
    label: "Supplements"
    pubmed_query: '("dietary supplements"[MeSH] OR "creatine"[MeSH] OR "vitamin D"[MeSH] OR "omega-3 fatty acids"[MeSH] OR "magnesium"[MeSH] OR "ashwagandha"[All Fields])'
    keywords: [creatine, vitamin D, omega-3, magnesium, ashwagandha, NAC, NMN, NR, collagen, protein powder]

  sleep:
    label: "Sleep & Recovery"
    pubmed_query: '("sleep"[MeSH] OR "circadian rhythm"[MeSH] OR "sleep deprivation"[MeSH] OR "REM"[All Fields] OR "deep sleep"[All Fields])'
    keywords: [sleep, circadian, REM, slow-wave, melatonin, sleep deprivation, jetlag, recovery]

  skin_hair:
    label: "Skin & Hair Health"
    pubmed_query: '("skin aging"[MeSH] OR "alopecia, androgenetic"[MeSH] OR "minoxidil"[MeSH] OR "finasteride"[MeSH] OR "microneedling"[All Fields] OR "retinoid"[MeSH] OR "tretinoin"[MeSH])'
    keywords: [skin aging, retinoid, tretinoin, peptide, microneedling, PRP, finasteride, dutasteride, minoxidil, androgenic alopecia, hair loss, dermatology]
```

- [ ] **Step 2: Create `config/sources.yaml`**

```yaml
# API endpoints and RSS feed URLs.

structured:
  pubmed:
    base_url: "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    rate_limit_per_sec: 3  # without API key; 10 with key
    max_results_per_theme: 30

  biorxiv:
    base_url: "https://api.biorxiv.org/details/biorxiv"

  medrxiv:
    base_url: "https://api.biorxiv.org/details/medrxiv"

  journal_rss:
    - name: "NEJM"
      url: "https://www.nejm.org/action/showFeed?type=etoc&feed=rss&jc=nejm"
    - name: "The Lancet"
      url: "https://www.thelancet.com/rssfeed/lancet_current.xml"
    - name: "Cell Metabolism"
      url: "https://www.cell.com/cell-metabolism/current.rss"
    - name: "Nature Medicine"
      url: "https://www.nature.com/nm.rss"
    - name: "Cochrane Library New Reviews"
      url: "https://www.cochranelibrary.com/cdsr/rss/new"
    - name: "JAAD"
      url: "https://www.jaad.org/current.rss"
    - name: "Journal of Investigative Dermatology"
      url: "https://www.jidonline.org/current.rss"
    - name: "British Journal of Dermatology"
      url: "https://onlinelibrary.wiley.com/feed/13652133/most-recent"

unstructured:
  examine_base: "https://examine.com"
  stronger_by_science: "https://www.strongerbyscience.com"
  search_query_template: "site:{site} after:{from_date}"
```

- [ ] **Step 3: Create `config/influencers.yaml`**

```yaml
# Provisional. Edit to add/drop as signal-quality observations accumulate.
core_fitness_strength:
  - name: "Greg Nuckols"
    site: "strongerbyscience.com"
    themes: [strength, supplements]
  - name: "Eric Helms"
    site: "massresearchreview.com"
    themes: [strength, supplements]
  - name: "Mike Israetel"
    site: "rpstrength.com"
    youtube: "@RenaissancePeriodization"
    themes: [strength]
  - name: "Brad Schoenfeld"
    site: "lookgreatnaked.com"
    themes: [strength]
  - name: "Jeff Nippard"
    youtube: "@JeffNippard"
    themes: [strength, supplements]
  - name: "Menno Henselmans"
    site: "mennohenselmans.com"
    themes: [strength, supplements]
  - name: "Layne Norton"
    site: "biolayne.com"
    themes: [strength, supplements, obesity]

core_longevity:
  - name: "Andrew Huberman"
    site: "hubermanlab.com"
    themes: [longevity, sleep, supplements]
  - name: "Peter Attia"
    site: "peterattiamd.com"
    themes: [longevity, obesity]
  - name: "Rhonda Patrick"
    site: "foundmyfitness.com"
    themes: [longevity, supplements]
  - name: "David Sinclair"
    site: "davidsinclair.com"
    themes: [longevity]
  - name: "Valter Longo"
    site: "valterlongo.com"
    themes: [longevity, obesity]
  - name: "Eric Topol"
    site: "erictopol.substack.com"
    themes: [longevity]
  - name: "Gabrielle Lyon"
    site: "drgabriellelyon.com"
    themes: [longevity, strength]
  - name: "Stuart Phillips"
    themes: [strength, longevity]
    note: "researcher; surfaces via PubMed primarily"

skin_hair_provisional:
  - name: "Dr. Shaaf Husaain"
    note: "Vet before Phase 2 — see spec §14"
    themes: [skin_hair]
  - name: "Dr. Andrea Suarez (Dr. Dray)"
    youtube: "@DrDrayzday"
    themes: [skin_hair]
  - name: "Dr. Sam Ellis"
    youtube: "@DrSamEllis"
    themes: [skin_hair]
  - name: "Dr. Michelle Wong (LabMuffin)"
    site: "labmuffin.com"
    themes: [skin_hair]
```

- [ ] **Step 4: Commit**

```bash
git add config/
git commit -m "feat(config): add topics, sources, and influencers YAML"
```

---

### Task 5: Filter / dedupe (`filter_dedupe.py`)

**Files:**
- Create: `scripts/filter_dedupe.py`
- Test: `scripts/tests/test_filter_dedupe.py`
- Create: `scripts/tests/conftest.py`

- [ ] **Step 1: Create `scripts/tests/conftest.py` with shared fixtures**

```python
from datetime import date
import pytest
from scripts.lib.schema import Study


@pytest.fixture
def sample_studies():
    return [
        Study(title="A", url="https://a.org", doi="10.1/a", source="pubmed", published=date(2026, 5, 1)),
        Study(title="B", url="https://b.org", doi="10.1/b", source="pubmed", published=date(2026, 5, 2)),
        Study(title="C", url="https://c.org", source="examine", published=date(2026, 5, 3)),
    ]
```

- [ ] **Step 2: Write failing tests**

Create `scripts/tests/test_filter_dedupe.py`:
```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest scripts/tests/test_filter_dedupe.py -v`
Expected: All FAIL with import error.

- [ ] **Step 4: Implement `scripts/filter_dedupe.py`**

```python
from __future__ import annotations
import json
from datetime import date
from pathlib import Path
from scripts.lib.schema import Study


def load_seen(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_seen(seen: dict, path: Path) -> None:
    path.write_text(json.dumps(seen, indent=2, sort_keys=True), encoding="utf-8")


def filter_new(studies: list[Study], seen: dict) -> list[Study]:
    """Return studies whose DOI or URL is not already in seen."""
    out = []
    for s in studies:
        if s.doi and s.doi in seen["by_doi"]:
            continue
        if s.url in seen["by_url"]:
            continue
        out.append(s)
    return out


def update_seen(seen: dict, new_studies: list[Study], run_date: date) -> None:
    """Mutate seen dict in place to record new_studies."""
    iso = run_date.isoformat()
    for s in new_studies:
        if s.doi:
            seen["by_doi"][s.doi] = {"first_seen": iso, "digest": iso}
        seen["by_url"][s.url] = {"first_seen": iso}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest scripts/tests/test_filter_dedupe.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/filter_dedupe.py scripts/tests/test_filter_dedupe.py scripts/tests/conftest.py
git commit -m "feat(filter): add DOI+URL dedupe against seen.json"
```

---

### Task 6: PubMed collector

**Files:**
- Create: `scripts/collect_structured.py`
- Test: extend `scripts/tests/test_filter_dedupe.py`? No — new test file.
- Create: `scripts/tests/test_collect_pubmed.py`

- [ ] **Step 1: Write failing test with mocked HTTP**

Create `scripts/tests/test_collect_pubmed.py`:
```python
from datetime import date
import respx
import httpx
from scripts.collect_structured import fetch_pubmed


PUBMED_ESEARCH_RESPONSE = """<?xml version="1.0"?>
<eSearchResult>
  <Count>2</Count>
  <IdList>
    <Id>40000001</Id>
    <Id>40000002</Id>
  </IdList>
</eSearchResult>"""

PUBMED_ESUMMARY_RESPONSE = """<?xml version="1.0"?>
<eSummaryResult>
  <DocSum>
    <Id>40000001</Id>
    <Item Name="Title" Type="String">Semaglutide and resistance training preserves lean mass</Item>
    <Item Name="AuthorList" Type="List">
      <Item Name="Author" Type="String">Smith J</Item>
      <Item Name="Author" Type="String">Doe A</Item>
    </Item>
    <Item Name="Source" Type="String">Cell Metab</Item>
    <Item Name="PubDate" Type="Date">2026 May 1</Item>
    <Item Name="DOI" Type="String">10.1016/j.cmet.2026.05.001</Item>
    <Item Name="PubTypeList" Type="List">
      <Item Name="PubType" Type="String">Randomized Controlled Trial</Item>
    </Item>
  </DocSum>
  <DocSum>
    <Id>40000002</Id>
    <Item Name="Title" Type="String">Meta-analysis of GLP-1 receptor agonists in obesity</Item>
    <Item Name="AuthorList" Type="List"><Item Name="Author" Type="String">Brown K</Item></Item>
    <Item Name="Source" Type="String">JAMA</Item>
    <Item Name="PubDate" Type="Date">2026 May 5</Item>
    <Item Name="DOI" Type="String">10.1001/jama.2026.05.002</Item>
    <Item Name="PubTypeList" Type="List"><Item Name="PubType" Type="String">Meta-Analysis</Item></Item>
  </DocSum>
</eSummaryResult>"""


@respx.mock
def test_fetch_pubmed_returns_studies_with_metadata():
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, text=PUBMED_ESEARCH_RESPONSE)
    )
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
        return_value=httpx.Response(200, text=PUBMED_ESUMMARY_RESPONSE)
    )

    studies = fetch_pubmed(
        query='"obesity"[MeSH]',
        theme="obesity",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 15),
        max_results=10,
    )

    assert len(studies) == 2
    s1 = studies[0]
    assert s1.title.startswith("Semaglutide")
    assert s1.doi == "10.1016/j.cmet.2026.05.001"
    assert s1.journal == "Cell Metab"
    assert s1.study_type == "RCT"
    assert s1.theme_guess == "obesity"
    assert s1.authors == ["Smith J", "Doe A"]

    s2 = studies[1]
    assert s2.study_type == "meta-analysis"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest scripts/tests/test_collect_pubmed.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement PubMed fetcher in `scripts/collect_structured.py`**

```python
from __future__ import annotations
import re
import time
from datetime import date
from xml.etree import ElementTree as ET
from typing import Literal

import httpx

from scripts.lib.schema import Study, ThemeKind

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Maps PubMed PubType strings to our normalized study_type field
PUBTYPE_NORMALIZE = {
    "Randomized Controlled Trial": "RCT",
    "Meta-Analysis": "meta-analysis",
    "Systematic Review": "meta-analysis",
    "Clinical Trial": "RCT",
    "Cohort Studies": "cohort",
    "Observational Study": "cohort",
    "Review": "review",
}


def _parse_pubdate(raw: str) -> date:
    """PubMed dates look like '2026 May 1' or '2026 May' or '2026'. Be lenient."""
    raw = raw.strip()
    parts = raw.split()
    try:
        year = int(parts[0])
        month = 1
        day = 1
        if len(parts) >= 2:
            month = {
                "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
            }.get(parts[1][:3], 1)
        if len(parts) >= 3:
            day = int(re.sub(r"\D", "", parts[2]) or 1)
        return date(year, month, day)
    except (ValueError, IndexError):
        return date(date.today().year, 1, 1)


def fetch_pubmed(
    query: str,
    theme: ThemeKind,
    date_from: date,
    date_to: date,
    max_results: int = 30,
) -> list[Study]:
    """Query PubMed via E-utilities. Returns list of Study."""

    full_query = f"{query} AND ({date_from:%Y/%m/%d}:{date_to:%Y/%m/%d}[pdat])"

    with httpx.Client(timeout=30.0) as client:
        # 1. esearch to get PMIDs
        esearch = client.get(
            f"{PUBMED_BASE}/esearch.fcgi",
            params={"db": "pubmed", "term": full_query, "retmax": max_results},
        )
        esearch.raise_for_status()
        root = ET.fromstring(esearch.text)
        pmids = [el.text for el in root.findall(".//Id") if el.text]

        if not pmids:
            return []

        time.sleep(0.4)  # rate limit

        # 2. esummary for metadata
        esummary = client.get(
            f"{PUBMED_BASE}/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(pmids)},
        )
        esummary.raise_for_status()
        sroot = ET.fromstring(esummary.text)

    studies: list[Study] = []
    for ds in sroot.findall(".//DocSum"):
        pmid = ds.find(".//Id").text  # type: ignore[union-attr]
        items = {it.attrib.get("Name"): it for it in ds.findall("./Item")}

        title = items["Title"].text if "Title" in items and items["Title"].text else "Untitled"
        journal = items["Source"].text if "Source" in items else None
        pubdate_raw = items["PubDate"].text if "PubDate" in items else ""
        doi = items["DOI"].text if "DOI" in items and items["DOI"].text else None

        authors = []
        if "AuthorList" in items:
            authors = [a.text for a in items["AuthorList"].findall("./Item") if a.text]

        pubtype_raw = None
        if "PubTypeList" in items:
            pt_items = items["PubTypeList"].findall("./Item")
            for pt in pt_items:
                if pt.text in PUBTYPE_NORMALIZE:
                    pubtype_raw = pt.text
                    break
            if not pubtype_raw and pt_items:
                pubtype_raw = pt_items[0].text

        study_type = PUBTYPE_NORMALIZE.get(pubtype_raw or "", None)

        studies.append(
            Study(
                title=title,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                doi=doi,
                authors=authors,
                journal=journal,
                published=_parse_pubdate(pubdate_raw),
                source="pubmed",
                study_type=study_type,
                theme_guess=theme,
            )
        )

    return studies
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_collect_pubmed.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_structured.py scripts/tests/test_collect_pubmed.py
git commit -m "feat(collect): add PubMed E-utilities fetcher"
```

---

### Task 7: bioRxiv / medRxiv collector

**Files:**
- Modify: `scripts/collect_structured.py`
- Test: `scripts/tests/test_collect_biorxiv.py`

- [ ] **Step 1: Write failing test**

Create `scripts/tests/test_collect_biorxiv.py`:
```python
from datetime import date
import json
import respx
import httpx
from scripts.collect_structured import fetch_biorxiv


BIORXIV_RESPONSE = json.dumps({
    "messages": [{"status": "ok", "total": 2}],
    "collection": [
        {
            "doi": "10.1101/2026.05.01.123456",
            "title": "Senolytic combination extends healthspan in aged mice",
            "authors": "Tanaka A.; Garcia M.",
            "abstract": "Mice given dasatinib+quercetin...",
            "category": "physiology",
            "date": "2026-05-03",
            "type": "new",
        },
        {
            "doi": "10.1101/2026.05.02.234567",
            "title": "rapamycin and skeletal muscle protein synthesis",
            "authors": "Lee K.",
            "abstract": "Acute mTOR inhibition...",
            "category": "biochemistry",
            "date": "2026-05-04",
            "type": "new",
        },
    ],
})


@respx.mock
def test_fetch_biorxiv_returns_preprints():
    respx.get(
        "https://api.biorxiv.org/details/biorxiv/2026-05-01/2026-05-15"
    ).mock(return_value=httpx.Response(200, text=BIORXIV_RESPONSE))

    studies = fetch_biorxiv(
        server="biorxiv",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 15),
    )

    assert len(studies) == 2
    assert studies[0].doi == "10.1101/2026.05.01.123456"
    assert studies[0].source == "biorxiv"
    assert studies[0].study_type == "preprint"
    assert studies[0].authors == ["Tanaka A.", "Garcia M."]
    assert studies[1].title.startswith("rapamycin")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest scripts/tests/test_collect_biorxiv.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Extend `scripts/collect_structured.py` with `fetch_biorxiv`**

Append to the file:
```python
BIORXIV_BASE = "https://api.biorxiv.org/details"


def fetch_biorxiv(
    server: Literal["biorxiv", "medrxiv"],
    date_from: date,
    date_to: date,
) -> list[Study]:
    """Fetch preprints from bioRxiv or medRxiv API."""
    url = f"{BIORXIV_BASE}/{server}/{date_from:%Y-%m-%d}/{date_to:%Y-%m-%d}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

    studies: list[Study] = []
    for item in data.get("collection", []):
        authors_raw = item.get("authors", "")
        authors = [a.strip() for a in authors_raw.split(";") if a.strip()]
        try:
            pub = date.fromisoformat(item["date"])
        except (ValueError, KeyError):
            continue
        studies.append(
            Study(
                title=item.get("title", "Untitled"),
                url=f"https://www.{server}.org/content/{item['doi']}v1",
                doi=item.get("doi"),
                authors=authors,
                published=pub,
                source=server,
                abstract=item.get("abstract"),
                study_type="preprint",
            )
        )
    return studies
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_collect_biorxiv.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_structured.py scripts/tests/test_collect_biorxiv.py
git commit -m "feat(collect): add bioRxiv/medRxiv preprint fetcher"
```

---

### Task 8: Journal RSS collector

**Files:**
- Modify: `scripts/collect_structured.py`
- Test: `scripts/tests/test_collect_rss.py`

- [ ] **Step 1: Write failing test**

Create `scripts/tests/test_collect_rss.py`:
```python
from datetime import date
import respx
import httpx
from scripts.collect_structured import fetch_journal_rss


SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Cell Metabolism</title>
    <item>
      <title>Time-restricted eating reduces visceral fat</title>
      <link>https://www.cell.com/cell-metabolism/article/PIIxxx</link>
      <description>RCT shows TRE outperforms continuous CR for visceral adiposity.</description>
      <pubDate>Mon, 05 May 2026 00:00:00 GMT</pubDate>
      <dc:date>2026-05-05</dc:date>
    </item>
    <item>
      <title>Unrelated cardiology paper on stents</title>
      <link>https://www.cell.com/cell-metabolism/article/PIIyyy</link>
      <description>Stent angioplasty cohort.</description>
      <pubDate>Mon, 05 May 2026 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


@respx.mock
def test_fetch_rss_keyword_filters():
    respx.get("https://www.cell.com/cell-metabolism/current.rss").mock(
        return_value=httpx.Response(200, text=SAMPLE_RSS)
    )

    studies = fetch_journal_rss(
        feed_url="https://www.cell.com/cell-metabolism/current.rss",
        journal_name="Cell Metabolism",
        keyword_filters={"obesity": ["visceral", "TRE", "fat", "CR"]},
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 15),
    )

    assert len(studies) == 1
    assert "Time-restricted" in studies[0].title
    assert studies[0].theme_guess == "obesity"
    assert studies[0].journal == "Cell Metabolism"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest scripts/tests/test_collect_rss.py -v`
Expected: FAIL.

- [ ] **Step 3: Extend `scripts/collect_structured.py` with `fetch_journal_rss`**

Append:
```python
import feedparser
from email.utils import parsedate_to_datetime


def fetch_journal_rss(
    feed_url: str,
    journal_name: str,
    keyword_filters: dict[ThemeKind, list[str]],
    date_from: date,
    date_to: date,
) -> list[Study]:
    """Parse a journal RSS feed; keep entries matching any theme's keywords.

    keyword_filters maps theme -> lowercase keyword list. First matching theme wins.
    """
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(feed_url, follow_redirects=True)
        resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    studies: list[Study] = []

    for entry in feed.entries:
        title = entry.get("title", "Untitled")
        link = entry.get("link", "")
        summary = entry.get("summary", "") or entry.get("description", "")

        # date
        pub: date | None = None
        if entry.get("published"):
            try:
                pub = parsedate_to_datetime(entry.published).date()
            except (TypeError, ValueError):
                pass
        if not pub:
            continue
        if not (date_from <= pub <= date_to):
            continue

        haystack = f"{title} {summary}".lower()
        theme_match: ThemeKind | None = None
        for theme, keywords in keyword_filters.items():
            if any(kw.lower() in haystack for kw in keywords):
                theme_match = theme
                break
        if not theme_match:
            continue

        studies.append(
            Study(
                title=title,
                url=link,
                journal=journal_name,
                published=pub,
                source="rss",
                abstract=summary[:1000] or None,
                theme_guess=theme_match,
            )
        )
    return studies
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_collect_rss.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_structured.py scripts/tests/test_collect_rss.py
git commit -m "feat(collect): add keyword-filtered journal RSS parser"
```

---

### Task 9: Unstructured collector (WebSearch via Anthropic SDK)

The unstructured collector uses Claude's web search capability via the Anthropic SDK's `web_search` tool. It's a single LLM call per source, with structured JSON output.

**Files:**
- Create: `scripts/collect_unstructured.py`
- Test: `scripts/tests/test_collect_unstructured.py`

- [ ] **Step 1: Write failing test with mocked Anthropic client**

Create `scripts/tests/test_collect_unstructured.py`:
```python
from datetime import date
import json
from unittest.mock import MagicMock, patch
from scripts.collect_unstructured import collect_for_source


FAKE_RESPONSE_JSON = {
    "studies": [
        {
            "title": "New Examine article: Creatine micronization claims",
            "url": "https://examine.com/articles/creatine-micronization",
            "published": "2026-05-08",
            "summary": "Reviews evidence for and against micronized creatine.",
            "theme_guess": "supplements",
            "cited_dois": [],
        },
        {
            "title": "Huberman podcast: sleep architecture & longevity",
            "url": "https://hubermanlab.com/episode-298",
            "published": "2026-05-10",
            "summary": "Episode covers REM/SWS, melatonin, and longevity outcomes.",
            "theme_guess": "sleep",
            "cited_dois": ["10.1056/NEJMxxx"],
        },
    ]
}


def test_collect_for_source_parses_llm_json_response():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(FAKE_RESPONSE_JSON))]
    mock_client.messages.create.return_value = mock_response

    studies = collect_for_source(
        client=mock_client,
        source_name="Examine.com",
        source_url="https://examine.com",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 15),
        themes=["supplements", "obesity"],
    )

    assert len(studies) == 2
    assert studies[0].title.startswith("New Examine")
    assert studies[0].source == "examine"
    assert studies[0].theme_guess == "supplements"
    assert studies[1].cited_by == ["10.1056/NEJMxxx"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest scripts/tests/test_collect_unstructured.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `scripts/collect_unstructured.py`**

```python
from __future__ import annotations
import json
import re
from datetime import date
from typing import Any

from scripts.lib.schema import Study, SourceKind, ThemeKind


PROMPT_TEMPLATE = """You are a research assistant for fiteligent.pl, scanning the web for recent health-research content.

Use web_search to find new content from {source_name} ({source_url}) published between {date_from} and {date_to}.
Focus on these themes: {themes}.

For each result, extract:
- title (the article/episode/post title)
- url (canonical URL)
- published (ISO date YYYY-MM-DD; estimate if unclear)
- summary (1-2 sentences describing the content)
- theme_guess (one of: obesity, longevity, strength, supplements, sleep, skin_hair)
- cited_dois (list of DOIs referenced in the content, if any)

Return ONLY a JSON object with this shape:
{{"studies": [{{...}}, ...]}}

If no relevant content found, return {{"studies": []}}. Do not include any text outside the JSON object."""


def _source_kind_from_url(url: str) -> SourceKind:
    u = url.lower()
    if "examine.com" in u:
        return "examine"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "reddit.com" in u or "tressless" in u:
        return "reddit"
    if any(p in u for p in ["hubermanlab", "peterattiamd", "foundmyfitness", ".fm/", "/podcast"]):
        return "podcast"
    return "blog"


def collect_for_source(
    client: Any,
    source_name: str,
    source_url: str,
    date_from: date,
    date_to: date,
    themes: list[ThemeKind],
    model: str = "claude-sonnet-4-6",
) -> list[Study]:
    """Use Claude web_search to find recent content from a single source.

    `client` must be an instance of anthropic.Anthropic.
    """
    prompt = PROMPT_TEMPLATE.format(
        source_name=source_name,
        source_url=source_url,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        themes=", ".join(themes),
    )

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    studies: list[Study] = []
    for item in data.get("studies", []):
        try:
            pub = date.fromisoformat(item["published"])
        except (KeyError, ValueError):
            continue
        if not (date_from <= pub <= date_to):
            continue
        studies.append(
            Study(
                title=item.get("title", "Untitled"),
                url=item["url"],
                published=pub,
                source=_source_kind_from_url(item["url"]),
                abstract=item.get("summary"),
                theme_guess=item.get("theme_guess"),
                cited_by=item.get("cited_dois", []),
                study_type=(
                    "podcast" if _source_kind_from_url(item["url"]) == "podcast"
                    else None
                ),
            )
        )
    return studies


def collect_unstructured(
    client: Any,
    config: dict,
    influencers: dict,
    date_from: date,
    date_to: date,
    model: str = "claude-sonnet-4-6",
) -> list[Study]:
    """Iterate all unstructured sources defined in config + influencers."""
    all_studies: list[Study] = []

    # Direct sources from config
    direct_sources = [
        ("Examine.com", "https://examine.com"),
        ("Stronger by Science", "https://www.strongerbyscience.com"),
    ]
    for name, url in direct_sources:
        try:
            all_studies.extend(
                collect_for_source(
                    client, name, url, date_from, date_to,
                    themes=["obesity", "longevity", "strength", "supplements", "sleep", "skin_hair"],
                    model=model,
                )
            )
        except Exception as e:
            print(f"[collect_unstructured] {name} failed: {e}")

    # Influencers
    for category in influencers.values():
        if not isinstance(category, list):
            continue
        for inf in category:
            url = inf.get("site") or inf.get("youtube")
            if not url:
                continue
            name = inf["name"]
            themes = inf.get("themes", ["longevity"])
            try:
                all_studies.extend(
                    collect_for_source(
                        client, name, url if url.startswith("http") else f"https://{url}",
                        date_from, date_to, themes=themes, model=model,
                    )
                )
            except Exception as e:
                print(f"[collect_unstructured] {name} failed: {e}")

    return all_studies
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_collect_unstructured.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_unstructured.py scripts/tests/test_collect_unstructured.py
git commit -m "feat(collect): add LLM web-search unstructured collector"
```

---

### Task 10: Synthesizer

**Files:**
- Create: `scripts/synthesize.py`
- Test: `scripts/tests/test_synthesize.py`

The synthesizer is the most LLM-heavy step. Its output is non-deterministic, so we test only that:
1. It successfully invokes the API with the right system prompt
2. It splits the response correctly into digest_md + angles_md

- [ ] **Step 1: Write failing test**

Create `scripts/tests/test_synthesize.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest scripts/tests/test_synthesize.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `scripts/synthesize.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_synthesize.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/synthesize.py scripts/tests/test_synthesize.py
git commit -m "feat(synth): add LLM digest+angles synthesizer with marker-delimited output"
```

---

### Task 11: Brand assets bootstrap

**Files:**
- Create: `brand/logo.svg`
- Create: `brand/tokens.css`
- Create: `brand/template_digest.html`
- Create: `brand/template_angles.html`
- Create: `brand/template_email.html`

- [ ] **Step 1: Copy logo from fiteligent-newsletters**

```bash
cp "C:/Users/Bonsky/fiteligent-newsletters/svg_export_claude/logo_same.svg" brand/logo.svg
```

- [ ] **Step 2: Create `brand/tokens.css`**

```css
:root {
  /* Surfaces */
  --bg-page:       #0a0e27;
  --bg-container:  #1a1f3a;
  --bg-footer:     #0a0e27;

  /* Brand colors */
  --brand-primary: #016FFA;
  --brand-deep:    #0047CC;
  --brand-light:   #66A8FF;
  --accent:        #FF7B00;
  --accent-hover:  #E56A00;

  /* Text */
  --text-strong:   #ffffff;
  --text-body:     #e0e0e0;
  --text-muted:    #c0c0c0;
  --text-footer:   #808080;

  /* Type */
  --font-sans:     'Satoshi', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

  /* Layout */
  --container-max: 720px;
  --radius:        12px;

  /* Theme accents */
  --theme-obesity:    #FF7B00;
  --theme-longevity:  #66A8FF;
  --theme-strength:   #016FFA;
  --theme-supplements:#9D7BFF;
  --theme-sleep:      #3D5AFE;
  --theme-skin-hair:  #F472B6;
}
```

- [ ] **Step 3: Create `brand/template_digest.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Fiteligent Research Digest — {{ date }}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Satoshi:wght@400;500;700&display=swap');
{{ tokens_css | safe }}
* { box-sizing: border-box; }
body { font-family: var(--font-sans); background: var(--bg-page); color: var(--text-body); margin: 0; padding: 24px; line-height: 1.7; }
.container { max-width: var(--container-max); margin: 0 auto; background: var(--bg-container); border-radius: var(--radius); overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.4); }
.header { background: linear-gradient(165deg, var(--brand-deep) 0%, var(--brand-primary) 55%, var(--brand-light) 100%); padding: 48px 32px; text-align: center; }
.header .logo { max-width: 200px; height: auto; }
.content { padding: 48px 56px; }
h1 { color: var(--text-strong); font-size: 28px; margin: 0 0 8px; font-weight: 700; }
h1 + .subtitle { color: var(--text-muted); margin: 0 0 32px; font-size: 14px; }
h2 { color: var(--text-strong); font-size: 22px; margin: 48px 0 16px; padding-left: 16px; border-left: 4px solid var(--theme-accent, var(--accent)); font-weight: 700; }
h2.theme-obesity     { --theme-accent: var(--theme-obesity); }
h2.theme-longevity   { --theme-accent: var(--theme-longevity); }
h2.theme-strength    { --theme-accent: var(--theme-strength); }
h2.theme-supplements { --theme-accent: var(--theme-supplements); }
h2.theme-sleep       { --theme-accent: var(--theme-sleep); }
h2.theme-skin-hair   { --theme-accent: var(--theme-skin-hair); }
h3 { color: var(--text-strong); font-size: 17px; margin: 32px 0 8px; font-weight: 700; }
.meta { color: var(--text-muted); font-size: 13px; margin: 0 0 12px; }
.stars { color: var(--accent); letter-spacing: 1px; font-weight: 700; }
a { color: var(--brand-light); text-decoration: none; }
a:hover { text-decoration: underline; }
.why-it-matters { background: rgba(255, 123, 0, 0.1); border-left: 3px solid var(--accent); padding: 12px 16px; margin: 16px 0; border-radius: 4px; color: var(--text-strong); font-weight: 500; }
.footer { background: var(--bg-footer); padding: 32px; text-align: center; color: var(--text-footer); font-size: 12px; }
.footer a { color: var(--brand-light); margin: 0 8px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <img src="logo.svg" alt="fiteligent" class="logo">
  </div>
  <div class="content">
    {{ content_html | safe }}
  </div>
  <div class="footer">
    <p><strong>fiteligent</strong> · Research Digest</p>
    <p>Optymizacja zdrowia oparta na nauce</p>
    <p><a href="https://fiteligent.pl">fiteligent.pl</a></p>
  </div>
</div>
</body>
</html>
```

- [ ] **Step 4: Create `brand/template_angles.html`**

Same structure as digest but 600px-wide and styled for the angles content. Copy `template_digest.html` and change:
- `<title>Fiteligent Editorial Angles — {{ date }}</title>`
- `.container { max-width: 600px; ... }`
- `h1 { font-size: 24px; }`

```html
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>Fiteligent Editorial Angles — {{ date }}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Satoshi:wght@400;500;700&display=swap');
{{ tokens_css | safe }}
* { box-sizing: border-box; }
body { font-family: var(--font-sans); background: var(--bg-page); color: var(--text-body); margin: 0; padding: 24px; line-height: 1.7; }
.container { max-width: 600px; margin: 0 auto; background: var(--bg-container); border-radius: var(--radius); overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.4); }
.header { background: linear-gradient(165deg, var(--brand-deep) 0%, var(--brand-primary) 55%, var(--brand-light) 100%); padding: 40px 24px; text-align: center; }
.header .logo { max-width: 160px; }
.content { padding: 40px; }
h1 { color: var(--text-strong); font-size: 24px; margin: 0 0 24px; }
h2 { color: var(--text-strong); font-size: 19px; margin: 32px 0 12px; }
h3 { color: var(--accent); font-size: 17px; margin: 24px 0 8px; }
.pitch { color: var(--text-body); font-style: italic; padding: 12px 16px; border-left: 3px solid var(--brand-light); margin: 8px 0; }
.source-ref { color: var(--text-muted); font-size: 12px; }
a { color: var(--brand-light); text-decoration: none; }
.footer { background: var(--bg-footer); padding: 24px; text-align: center; color: var(--text-footer); font-size: 11px; }
</style>
</head>
<body>
<div class="container">
  <div class="header"><img src="logo.svg" alt="fiteligent" class="logo"></div>
  <div class="content">{{ content_html | safe }}</div>
  <div class="footer"><p>fiteligent · Editorial Angles</p></div>
</div>
</body>
</html>
```

- [ ] **Step 5: Create `brand/template_email.html`**

Email-safe version. Same DOM structure as digest but explicit inline-friendly markup (Jinja blocks render compact HTML which premailer will inline).

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ subject }}</title>
<style>
{{ tokens_css | safe }}
body { font-family: 'Satoshi', Arial, sans-serif; background: var(--bg-page); margin: 0; padding: 20px; }
.container { max-width: 600px; margin: 0 auto; background: var(--bg-container); border-radius: 12px; overflow: hidden; }
.header { background: linear-gradient(165deg, #0047CC 0%, #016FFA 55%, #66A8FF 100%); padding: 40px 20px; text-align: center; }
.header img { max-width: 160px; }
.content { padding: 40px; color: var(--text-body); line-height: 1.7; }
.content h1 { color: var(--text-strong); font-size: 22px; margin: 0 0 16px; }
.content h2 { color: var(--text-strong); font-size: 18px; margin: 24px 0 8px; border-left: 3px solid var(--accent); padding-left: 12px; }
.content a { color: var(--brand-light); }
.cta { display: inline-block; background: var(--accent); color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 700; margin-top: 24px; }
.footer { background: var(--bg-footer); padding: 24px; text-align: center; color: var(--text-footer); font-size: 11px; }
</style>
</head>
<body>
<div class="container">
  <div class="header"><img src="cid:logo" alt="fiteligent"></div>
  <div class="content">
    {{ summary_html | safe }}
    <p><a class="cta" href="{{ digest_url }}">Read full digest →</a></p>
  </div>
  <div class="footer"><p>fiteligent · {{ date }}</p></div>
</div>
</body>
</html>
```

- [ ] **Step 6: Commit**

```bash
git add brand/
git commit -m "feat(brand): bootstrap brandbook assets — logo, tokens, 3 Jinja templates"
```

---

### Task 12: HTML renderer

**Files:**
- Create: `scripts/render_html.py`
- Test: `scripts/tests/test_render_html.py`

- [ ] **Step 1: Write failing test**

Create `scripts/tests/test_render_html.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest scripts/tests/test_render_html.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `scripts/render_html.py`**

```python
from __future__ import annotations
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt


THEME_HEADING_MAP = {
    "obesity": "theme-obesity",
    "metabolic": "theme-obesity",
    "longevity": "theme-longevity",
    "strength": "theme-strength",
    "hypertrophy": "theme-strength",
    "supplement": "theme-supplements",
    "sleep": "theme-sleep",
    "recovery": "theme-sleep",
    "skin": "theme-skin-hair",
    "hair": "theme-skin-hair",
}


def _apply_theme_classes(html: str) -> str:
    """Add theme-* class to <h2> elements based on heading text."""
    def repl(match: re.Match) -> str:
        text = match.group(1).lower()
        for kw, cls in THEME_HEADING_MAP.items():
            if kw in text:
                return f'<h2 class="{cls}">{match.group(1)}</h2>'
        return match.group(0)
    return re.sub(r"<h2>(.*?)</h2>", repl, html, flags=re.DOTALL)


def _strip_frontmatter(md: str) -> tuple[str, str]:
    """Strip YAML front matter, return (frontmatter_text, body_md)."""
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[3:end].strip(), md[end + 4:].lstrip()
    return "", md


def _md_to_html(md: str) -> str:
    parser = MarkdownIt("commonmark", {"html": False, "linkify": True})
    return parser.render(md)


def _load_template(brand_dir: Path, template_name: str):
    env = Environment(
        loader=FileSystemLoader(brand_dir),
        autoescape=select_autoescape(default=False),
    )
    return env.get_template(template_name)


def render_digest(
    digest_md: str,
    brand_dir: Path,
    out_path: Path,
    run_date_str: str,
) -> None:
    _frontmatter, body_md = _strip_frontmatter(digest_md)
    content_html = _md_to_html(body_md)
    content_html = _apply_theme_classes(content_html)

    tokens_css = (brand_dir / "tokens.css").read_text(encoding="utf-8")
    template = _load_template(brand_dir, "template_digest.html")
    html = template.render(
        date=run_date_str,
        content_html=content_html,
        tokens_css=tokens_css,
    )
    out_path.write_text(html, encoding="utf-8")


def render_angles(
    angles_md: str,
    brand_dir: Path,
    out_path: Path,
    run_date_str: str,
) -> None:
    _frontmatter, body_md = _strip_frontmatter(angles_md)
    content_html = _md_to_html(body_md)
    tokens_css = (brand_dir / "tokens.css").read_text(encoding="utf-8")
    template = _load_template(brand_dir, "template_angles.html")
    html = template.render(
        date=run_date_str,
        content_html=content_html,
        tokens_css=tokens_css,
    )
    out_path.write_text(html, encoding="utf-8")


def render_email_body(
    digest_md: str,
    brand_dir: Path,
    out_path: Path,
    run_date_str: str,
    digest_url: str,
    subject: str,
) -> None:
    """Render an email-safe HTML body with inlined CSS (via premailer)."""
    from premailer import transform

    # Extract just TL;DR for the email summary
    _frontmatter, body_md = _strip_frontmatter(digest_md)
    summary_match = re.search(r"##\s*TL;DR.*?(?=\n##\s)", body_md, re.DOTALL)
    summary_md = summary_match.group(0) if summary_match else body_md[:1000]
    summary_html = _md_to_html(summary_md)

    tokens_css = (brand_dir / "tokens.css").read_text(encoding="utf-8")
    template = _load_template(brand_dir, "template_email.html")
    raw_html = template.render(
        subject=subject,
        summary_html=summary_html,
        digest_url=digest_url,
        date=run_date_str,
        tokens_css=tokens_css,
    )

    inlined = transform(raw_html, base_url=None)
    out_path.write_text(inlined, encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest scripts/tests/test_render_html.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/render_html.py scripts/tests/test_render_html.py
git commit -m "feat(render): add Jinja2 markdown->branded-HTML renderer with theme classes"
```

---

### Task 13: Email notifier

**Files:**
- Create: `scripts/notify.py`

Email delivery is hard to unit-test without a real SMTP server. Manual smoke test in Task 15.

- [ ] **Step 1: Implement `scripts/notify.py`**

```python
from __future__ import annotations
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_email(
    subject: str,
    html_body: str,
    plain_fallback: str | None = None,
    attachments: list[Path] | None = None,
    logo_path: Path | None = None,
) -> None:
    """Send the digest email via SMTP using env vars.

    Required env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TO
    """
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    sender = os.environ["SMTP_FROM"]
    recipient = os.environ["SMTP_TO"]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    if plain_fallback:
        msg.set_content(plain_fallback)
    else:
        msg.set_content("This email requires an HTML-capable client.")

    msg.add_alternative(html_body, subtype="html")

    # Inline the logo as a CID-referenced attachment if requested
    if logo_path and logo_path.exists():
        with open(logo_path, "rb") as f:
            # Find the HTML alternative and attach the inline image to it
            for part in msg.iter_parts():
                if part.get_content_subtype() == "html":
                    part.add_related(
                        f.read(),
                        maintype="image",
                        subtype="svg+xml",
                        cid="logo",
                        filename=logo_path.name,
                    )
                    break

    for att in attachments or []:
        with open(att, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="octet-stream",
                filename=att.name,
            )

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


def send_failure_alert(stage: str, error: str, run_date_iso: str) -> None:
    """Lightweight plain-text alert for run failures."""
    send_email(
        subject=f"[Fiteligent Research] FAILED {run_date_iso}",
        html_body=f"<pre>{error}</pre>",
        plain_fallback=f"Stage: {stage}\n\n{error}",
    )
```

- [ ] **Step 2: Commit**

```bash
git add scripts/notify.py
git commit -m "feat(notify): add SMTP email delivery with inline logo + attachments"
```

---

### Task 14: Orchestrator (`run.py`) with CLI

**Files:**
- Create: `scripts/run.py`

This is the entry point. It ties every collector together, handles flags, and produces final outputs.

- [ ] **Step 1: Implement `scripts/run.py`**

```python
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

from scripts.collect_structured import fetch_pubmed, fetch_biorxiv, fetch_journal_rss
from scripts.collect_unstructured import collect_unstructured
from scripts.filter_dedupe import load_seen, save_seen, filter_new, update_seen
from scripts.lib.schema import Study, StudyList, ThemeKind
from scripts.synthesize import synthesize
from scripts.render_html import render_digest, render_angles, render_email_body
from scripts.notify import send_email, send_failure_alert

REPO_ROOT = Path(__file__).resolve().parent.parent
THIN_WEEK_THRESHOLD = 5


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _log(run_log: list[str], msg: str) -> None:
    line = f"[{_now_iso()}] {msg}"
    print(line)
    run_log.append(line)


def collect_all(
    topics_cfg: dict,
    sources_cfg: dict,
    influencers_cfg: dict,
    date_from: date,
    date_to: date,
    run_log: list[str],
    anthropic_client,
    model: str,
    only_source: str | None = None,
) -> list[Study]:
    all_studies: list[Study] = []

    # Structured: PubMed per theme
    if only_source in (None, "pubmed"):
        for theme_key, theme_def in topics_cfg["themes"].items():
            try:
                studies = fetch_pubmed(
                    query=theme_def["pubmed_query"],
                    theme=theme_key,
                    date_from=date_from,
                    date_to=date_to,
                    max_results=sources_cfg["structured"]["pubmed"]["max_results_per_theme"],
                )
                _log(run_log, f"pubmed[{theme_key}]: {len(studies)} hits")
                all_studies.extend(studies)
            except Exception as e:
                _log(run_log, f"pubmed[{theme_key}] FAILED: {e}")

    # Structured: bioRxiv + medRxiv
    if only_source in (None, "biorxiv"):
        for server in ("biorxiv", "medrxiv"):
            try:
                studies = fetch_biorxiv(server=server, date_from=date_from, date_to=date_to)
                _log(run_log, f"{server}: {len(studies)} hits")
                all_studies.extend(studies)
            except Exception as e:
                _log(run_log, f"{server} FAILED: {e}")

    # Structured: journal RSS
    if only_source in (None, "rss"):
        keyword_filters: dict[ThemeKind, list[str]] = {
            k: v["keywords"] for k, v in topics_cfg["themes"].items()
        }
        for feed in sources_cfg["structured"]["journal_rss"]:
            try:
                studies = fetch_journal_rss(
                    feed_url=feed["url"],
                    journal_name=feed["name"],
                    keyword_filters=keyword_filters,
                    date_from=date_from,
                    date_to=date_to,
                )
                _log(run_log, f"rss[{feed['name']}]: {len(studies)} hits")
                all_studies.extend(studies)
            except Exception as e:
                _log(run_log, f"rss[{feed['name']}] FAILED: {e}")

    # Unstructured
    if only_source in (None, "unstructured"):
        try:
            studies = collect_unstructured(
                client=anthropic_client,
                config=sources_cfg,
                influencers=influencers_cfg,
                date_from=date_from,
                date_to=date_to,
                model=model,
            )
            _log(run_log, f"unstructured: {len(studies)} hits")
            all_studies.extend(studies)
        except Exception as e:
            _log(run_log, f"unstructured FAILED: {e}")

    return all_studies


def main() -> int:
    parser = argparse.ArgumentParser(description="Fiteligent research routine.")
    parser.add_argument("--manual", action="store_true", help="Tag run as manual in logs/email")
    parser.add_argument("--dry-run", action="store_true", help="Write to digests/_dry/, no commit, no email")
    parser.add_argument("--since", type=str, help="ISO date override for lookback start")
    parser.add_argument("--source", type=str, help="Run only one source path: pubmed|biorxiv|rss|unstructured")
    parser.add_argument("--no-render", action="store_true", help="Skip HTML rendering")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")

    run_date = date.today()
    date_to = run_date
    if args.since:
        date_from = date.fromisoformat(args.since)
    else:
        date_from = run_date - timedelta(days=14)

    run_log: list[str] = []
    _log(run_log, f"run started — date_from={date_from} date_to={date_to} manual={args.manual} dry_run={args.dry_run}")

    # Output directory
    if args.dry_run:
        out_dir = REPO_ROOT / "digests" / "_dry" / run_date.isoformat()
    else:
        out_dir = REPO_ROOT / "digests" / run_date.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Anthropic client
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # Load configs
    topics_cfg = _load_yaml(REPO_ROOT / "config" / "topics.yaml")
    sources_cfg = _load_yaml(REPO_ROOT / "config" / "sources.yaml")
    influencers_cfg = _load_yaml(REPO_ROOT / "config" / "influencers.yaml")

    # === COLLECT ===
    try:
        raw_studies = collect_all(
            topics_cfg, sources_cfg, influencers_cfg,
            date_from, date_to, run_log, client, model,
            only_source=args.source,
        )
    except Exception as e:
        _log(run_log, f"COLLECT stage failed entirely: {e}\n{traceback.format_exc()}")
        (out_dir / "run.log").write_text("\n".join(run_log), encoding="utf-8")
        if not args.dry_run:
            send_failure_alert("collect", traceback.format_exc(), run_date.isoformat())
        return 1

    StudyList(studies=raw_studies).save(out_dir / "raw_studies.json")

    # === FILTER ===
    seen_path = REPO_ROOT / "seen.json"
    seen = load_seen(seen_path)
    new_studies = filter_new(raw_studies, seen)
    _log(run_log, f"filter: {len(raw_studies)} raw -> {len(new_studies)} new (dedupe)")
    StudyList(studies=new_studies).save(out_dir / "new_studies.json")

    if len(new_studies) < THIN_WEEK_THRESHOLD:
        msg = f"Only {len(new_studies)} new studies this week — below threshold {THIN_WEEK_THRESHOLD}."
        _log(run_log, f"THIN WEEK: {msg}")
        (out_dir / "run.log").write_text("\n".join(run_log), encoding="utf-8")
        if not args.dry_run:
            send_email(
                subject=f"[Fiteligent Research] THIN WEEK {run_date.isoformat()}",
                html_body=f"<p>{msg}</p><p>Skipping digest generation.</p>",
                plain_fallback=msg,
            )
        return 0

    # === SYNTHESIZE ===
    try:
        digest_md, angles_md = synthesize(client, new_studies, run_date=run_date, model=model)
    except Exception as e:
        _log(run_log, f"SYNTHESIZE failed: {e}\n{traceback.format_exc()}")
        (out_dir / "run.log").write_text("\n".join(run_log), encoding="utf-8")
        if not args.dry_run:
            send_failure_alert("synthesize", traceback.format_exc(), run_date.isoformat())
        return 1

    (out_dir / "digest.md").write_text(digest_md, encoding="utf-8")
    (out_dir / "angles.md").write_text(angles_md, encoding="utf-8")
    _log(run_log, "synthesize: digest.md + angles.md written")

    # === RENDER ===
    render_failed = False
    if not args.no_render:
        try:
            brand_dir = REPO_ROOT / "brand"
            render_digest(digest_md, brand_dir, out_dir / "digest.html", run_date.isoformat())
            render_angles(angles_md, brand_dir, out_dir / "angles.html", run_date.isoformat())
            render_email_body(
                digest_md, brand_dir, out_dir / "email_body.html",
                run_date.isoformat(),
                digest_url=f"https://github.com/your-org/fiteligent-research/blob/main/digests/{run_date.isoformat()}/digest.html",
                subject=f"[Fiteligent Research] Digest {run_date.isoformat()}",
            )
            _log(run_log, "render: HTML siblings written")
        except Exception as e:
            render_failed = True
            _log(run_log, f"RENDER failed: {e}\n{traceback.format_exc()}")

    # === DELIVER ===
    update_seen(seen, new_studies, run_date=run_date)
    if not args.dry_run:
        save_seen(seen, seen_path)

        # Git commit + push
        subprocess.run(["git", "add", "digests/", "seen.json"], cwd=REPO_ROOT, check=True)
        subject_tag = "PARTIAL" if any("FAILED" in line for line in run_log) else "Digest"
        if render_failed:
            subject_tag = "RENDER_FAILED"
        subprocess.run(
            ["git", "commit", "-m",
             f"weekly digest {run_date.isoformat()} ({len(new_studies)} studies)"],
            cwd=REPO_ROOT, check=False,
        )
        # push is optional — only if remote exists
        push_result = subprocess.run(
            ["git", "push"], cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if push_result.returncode != 0:
            _log(run_log, f"git push skipped/failed: {push_result.stderr.strip()}")

        # Email
        manual_tag = " (manual)" if args.manual else ""
        subject = f"[Fiteligent Research] {subject_tag} {run_date.isoformat()} ({len(new_studies)} studies){manual_tag}"
        if not render_failed:
            html_body = (out_dir / "email_body.html").read_text(encoding="utf-8")
            send_email(
                subject=subject,
                html_body=html_body,
                attachments=[out_dir / "digest.md", out_dir / "angles.md"],
                logo_path=REPO_ROOT / "brand" / "logo.svg",
            )
        else:
            send_email(
                subject=subject,
                html_body=f"<p>Render failed; markdown attached.</p><pre>{digest_md[:2000]}</pre>",
                plain_fallback=digest_md,
                attachments=[out_dir / "digest.md", out_dir / "angles.md"],
            )

    (out_dir / "run.log").write_text("\n".join(run_log), encoding="utf-8")
    _log(run_log, "run complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add scripts/run.py
git commit -m "feat(run): add orchestrator with CLI flags (--manual, --dry-run, --since, --source, --no-render)"
```

---

### Task 15: Golden-path integration test

**Files:**
- Create: `scripts/tests/test_integration_goldenpath.py`
- Create: `scripts/tests/fixtures/golden_studies.json`

- [ ] **Step 1: Create canned input fixture**

Create `scripts/tests/fixtures/golden_studies.json`:
```json
{
  "studies": [
    {
      "title": "Semaglutide + RT preserves lean mass",
      "url": "https://pubmed.ncbi.nlm.nih.gov/40000001/",
      "doi": "10.1016/j.cmet.2026.05.001",
      "authors": ["Smith J", "Doe A"],
      "journal": "Cell Metabolism",
      "published": "2026-05-05",
      "source": "pubmed",
      "abstract": "Two-arm RCT (n=180) comparing semaglutide alone vs semaglutide + 3x/wk resistance training. Lean mass loss 4.2 kg vs 1.1 kg favoring RT arm (p<0.001).",
      "n": 180,
      "study_type": "RCT",
      "theme_guess": "obesity",
      "cited_by": []
    },
    {
      "title": "Microneedling + topical minoxidil for AGA",
      "url": "https://www.jaad.org/article/PIIxxx",
      "doi": "10.1016/j.jaad.2026.04.015",
      "authors": ["Tanaka K"],
      "journal": "JAAD",
      "published": "2026-05-02",
      "source": "rss",
      "abstract": "12-week RCT (n=80) shows microneedling + 5% minoxidil produces 1.7x hair density increase vs minoxidil alone.",
      "n": 80,
      "study_type": "RCT",
      "theme_guess": "skin_hair",
      "cited_by": []
    },
    {
      "title": "Sleep restriction blunts MPS response to RT",
      "url": "https://pubmed.ncbi.nlm.nih.gov/40000003/",
      "doi": "10.1152/japplphysiol.2026.05.003",
      "authors": ["Wong J"],
      "journal": "J Appl Physiol",
      "published": "2026-05-08",
      "source": "pubmed",
      "abstract": "Crossover trial (n=24) shows 4h sleep restriction reduces post-RT muscle protein synthesis by 27%.",
      "n": 24,
      "study_type": "RCT",
      "theme_guess": "sleep",
      "cited_by": []
    },
    {
      "title": "Rapamycin in aged mice — ITP follow-up",
      "url": "https://www.biorxiv.org/content/10.1101/2026.05.001v1",
      "doi": "10.1101/2026.05.001",
      "authors": ["Patel S"],
      "published": "2026-05-09",
      "source": "biorxiv",
      "abstract": "Preprint: rapamycin at 14ppm extends median lifespan by 21% in 24mo C57BL/6J.",
      "study_type": "preprint",
      "theme_guess": "longevity",
      "cited_by": []
    },
    {
      "title": "Creatine 5g/day vs 10g/day — meta-analysis",
      "url": "https://pubmed.ncbi.nlm.nih.gov/40000005/",
      "doi": "10.1186/s12970-2026-05-005",
      "authors": ["Garcia M"],
      "journal": "J Int Soc Sports Nutr",
      "published": "2026-05-06",
      "source": "pubmed",
      "abstract": "Meta-analysis (k=14, n=872) — no hypertrophy benefit at 10g/day over 5g/day.",
      "study_type": "meta-analysis",
      "theme_guess": "supplements",
      "cited_by": []
    },
    {
      "title": "Examine: New evidence on ashwagandha and sleep",
      "url": "https://examine.com/articles/ashwagandha-sleep-2026",
      "published": "2026-05-10",
      "source": "examine",
      "abstract": "Review of 3 new RCTs on ashwagandha for sleep onset latency.",
      "theme_guess": "supplements",
      "cited_by": ["10.1186/s12970-2026-05-005"]
    }
  ]
}
```

- [ ] **Step 2: Write the integration test**

Create `scripts/tests/test_integration_goldenpath.py`:
```python
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

    # Synthesize (mocked)
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=FAKE_DIGEST_OUTPUT)]
    mock_client.messages.create.return_value = mock_response

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
```

- [ ] **Step 3: Run integration test**

Run: `pytest scripts/tests/test_integration_goldenpath.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add scripts/tests/test_integration_goldenpath.py scripts/tests/fixtures/
git commit -m "test(integration): add golden-path pipeline test with 6-study fixture"
```

---

### Task 16: README + Phase 1 dry-run verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite `README.md`**

```markdown
# fiteligent-research

Weekly automated research-curation routine for [fiteligent.pl](https://fiteligent.pl).

Every Friday 18:00 Europe/Warsaw, the routine:

1. Scans PubMed, bioRxiv/medRxiv, journal RSS (NEJM, Lancet, Cell Metab, JAAD, etc.), Examine.com, and 15 health-research influencers
2. Filters out studies already digested (persistent `seen.json` dedupe)
3. LLM-synthesizes a 6-theme English digest + Polish newsletter angles
4. Renders branded HTML using the fiteligent brandbook
5. Commits the output to git and emails it to the configured address

## Repo layout

See `docs/superpowers/specs/2026-05-14-fiteligent-research-routine-design.md` for the full design rationale.

## Setup

```bash
git clone <repo>
cd fiteligent-research
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env  # then edit secrets
```

Required env vars (see `.env.example`):
- `ANTHROPIC_API_KEY` — for LLM synthesis
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_TO` — for email delivery

## Run manually

```bash
# Default — full pipeline, commits + emails
python scripts/run.py

# Dry-run — writes to digests/_dry/<date>/, no commit, no email
python scripts/run.py --dry-run

# Manual trigger (same as default but tagged "manual" in subject)
python scripts/run.py --manual

# Backfill — override 14-day lookback
python scripts/run.py --since 2026-04-01

# Single source (debugging)
python scripts/run.py --source pubmed
python scripts/run.py --source biorxiv
python scripts/run.py --source rss
python scripts/run.py --source unstructured

# Skip HTML rendering
python scripts/run.py --no-render

# Re-render an existing run
python scripts/render_html.py digests/2026-05-15/
```

## Tune

- `config/topics.yaml` — MeSH terms + keywords per theme
- `config/sources.yaml` — API endpoints, RSS feeds
- `config/influencers.yaml` — influencer list

## Tests

```bash
pytest
```

## Schedule

Production cron: Friday 18:00 Europe/Warsaw via `mcp__scheduled-tasks__create_scheduled_task` (Task 17 of the implementation plan).
```

- [ ] **Step 2: Run unit suite to confirm everything still passes**

Run: `pytest -v`
Expected: all tests pass (~15 tests across 6 test files).

- [ ] **Step 3: Run a real dry-run end-to-end**

```bash
python scripts/run.py --dry-run --since 2026-05-01
```

Inspect:
- `digests/_dry/<today>/run.log` — should show per-source counts
- `digests/_dry/<today>/raw_studies.json` — should contain studies from at least PubMed (other paths may fail silently if API keys missing)
- `digests/_dry/<today>/digest.md` — should be well-formed if LLM step ran
- `digests/_dry/<today>/digest.html` — open in a browser; verify brand colors, theme borders, logo

Expected: at minimum PubMed produces results. If LLM/SMTP env vars are missing, those stages will fail but the run should not crash.

- [ ] **Step 4: Commit README**

```bash
git add README.md
git commit -m "docs: write README with setup, run, tune, schedule instructions"
```

---

### Task 17: Register the scheduled task

**Files:** none (uses MCP)

- [ ] **Step 1: Verify pre-flight**

Before scheduling, confirm:
- `python scripts/run.py --manual` runs successfully end-to-end at least once (Phase 2 of the rollout plan from the spec)
- The first real digest has been reviewed and the synthesize prompt has been tuned if needed
- `seen.json` has been populated with the first run's studies (cold start — first run produces a fat baseline digest)

If any of the above is missing, halt and complete it first.

- [ ] **Step 2: Register cron via `mcp__scheduled-tasks__create_scheduled_task`**

Invoke the tool with these parameters:
- **Cron expression:** `0 17 * * 5` (17:00 UTC = 18:00 CET winter / 19:00 CEST summer — see spec §5 timezone note)
- **Command:** `cd <absolute-path-to-fiteligent-research> && python scripts/run.py` — substitute the absolute repo path on whatever host the scheduled agent runs on (read it from `pwd` at scheduling time)
- **Description:** "Fiteligent weekly research digest — runs Fridays, sends to ciastkofski@gmail.com"
- **Timezone:** `Europe/Warsaw` if the tool accepts IANA timezones; otherwise document the DST drift in `run.log`

- [ ] **Step 3: Verify the schedule was created**

Use `mcp__scheduled-tasks__list_scheduled_tasks` to confirm the entry exists.

- [ ] **Step 4: Document the schedule in README**

Append to the Schedule section in README:
```markdown
**Schedule ID:** <task-id-from-step-2>
**Created:** <ISO date>
**Cron:** `0 17 * * 5` (Friday 18:00 CET / 19:00 CEST)
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: record production schedule task ID and cron expression"
```

---

## Self-Review Notes

After writing this plan, I cross-checked against the spec:

**Spec coverage:**
- §1 Purpose → Tasks 10 (synth produces both files), 12 (render to branded HTML), 13-14 (deliver via email + git)
- §2 Decisions (6 themes, weekly, Friday 18:00 Europe/Warsaw, 14d lookback, hybrid, dedup, git+email, cold start) → Tasks 4 (topics), 5 (dedup), 6-9 (collectors), 14 (cron expr, lookback), 17 (cron)
- §3 Sources → Tasks 6 (PubMed), 7 (bioRxiv), 8 (RSS incl. JAAD/JID/Br.J.Derm), 9 (unstructured + skincare influencers)
- §4 Architecture (5-stage pipeline) → Tasks 6-9 (collect), 5 (filter), 10 (synth), 12 (render), 13-14 (deliver)
- §5 Repo structure → Task 1 (scaffold) + Task 4 (config) + Task 11 (brand)
- §6 Output format → Task 10 (synthesizer prompt enforces structure)
- §6b Visual presentation (tokens, 3 templates, per-theme accents, brand bootstrap) → Task 11 + Task 12 (theme class application)
- §7 Orchestrator flow (11 steps) → Task 14 covers each step
- §8 Failure handling (per-source, partial, synth fail, render fail, push fail, email fail, thin week) → Task 14 (try/except per stage, subject tags, send_failure_alert)
- §9 Manual triggers + modes → Task 14 (argparse: --manual, --dry-run, --since, --source, --no-render)
- §10 Testing (schema, evidence, dedupe, render golden, integration golden-path) → Tasks 2, 3, 5, 12, 15
- §11 Rollout (Phase 1 dry-run, Phase 2 manual, Phase 3 cron) → Task 16 (dry-run verification), Task 17 prereqs (Phase 2 confirmation), Task 17 (Phase 3)
- §12 Observability → Task 14 (run.log written per run)
- §13 Secrets → Task 1 (.env.example), Task 13 (notify reads env)
- §14 Open questions (theme icons, derm influencer vetting) → deferred to v1.1, documented in spec; Task 4 marks skin_hair influencers as provisional
- §15 Success criteria → measurable post-deployment; no direct tasks

**Type / signature consistency check:**
- `Study` field names consistent across schema, evidence, filter, all collectors, synthesize, render
- `ThemeKind` literal used in topics.yaml keys, filter, synthesize prompt, render theme classes — all match: obesity, longevity, strength, supplements, sleep, skin_hair
- `SourceKind` enum matches usage in all collectors: pubmed, biorxiv, medrxiv, rss, examine, podcast, blog, youtube, reddit
- `synthesize()` returns `tuple[str, str]` — consumed correctly in run.py
- `render_digest/angles/email_body()` signatures consistent

**Placeholder scan:** none found.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-14-fiteligent-research-routine-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a 17-task plan with TDD discipline at each step.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Faster for the human if you're going to be at the keyboard the whole time.

**Which approach?**
