# Fiteligent Research Routine â€” Design Spec

**Date:** 2026-05-14
**Project:** `fiteligent-research/`
**Owner:** Dr. Jakub StanisÅ‚awski (fiteligent.pl)
**Status:** Approved, ready for implementation plan

---

## 1. Purpose

A weekly automated routine that scans research and expert-commentary sources across the fiteligent topic space (obesity, longevity, health optimization, supplements, fitness, strength training, stretching, skin health & skincare, androgenic alopecia / hair loss) and produces two artifacts per run:

1. **`digest.md`** â€” English, technical, theme-grouped research review (~4000 words, 15â€“25 studies), with evidence-strength ratings. For Dr. StanisÅ‚awski's personal intake and as primary reference material.
2. **`angles.md`** â€” Polish, newsletter-ready editorial angles in Jakub's voice. Slots directly into the existing `fiteligent-newsletters/` workflow.

The output serves both personal research currency and content production for fiteligent.pl newsletters, carousels, and Reels.

---

## 2. Decisions Locked In

| Dimension | Decision |
|---|---|
| Output | Two files â€” English technical digest + Polish publishable angles |
| Frequency | Weekly |
| Schedule | Friday 18:00 Europe/Warsaw |
| Lookback window | 14 days |
| Volume | 15â€“25 studies per run, theme-grouped, evidence-rated |
| Themes (6) | Obesity & Metabolic Health, Longevity, Strength & Hypertrophy, Supplements, Sleep & Recovery, Skin & Hair Health |
| Approach | Hybrid â€” APIs/RSS for structured sources + LLM WebSearch for the rest |
| Dedupe | Persistent `seen.json` keyed by DOI + URL, never pruned |
| Storage | Dedicated `fiteligent-research/` git repo |
| Delivery | Git commit + **branded HTML email** to you@example.com |
| First run | Cold start â€” first digest will be a fat "state of the field" baseline |
| Execution | Remote scheduled agent (via `mcp__scheduled-tasks__create_scheduled_task`) invoking Python orchestrator |
| Visual identity | Fiteligent brandbook â€” Satoshi font, dark theme (`#0a0e27`/`#1a1f3a`), `#016FFA` primary blue, `#FF7B00` accent, brand SVG logo |

---

## 3. Sources

### Structured path (APIs / RSS)

| Source | Mechanism | Notes |
|---|---|---|
| PubMed | E-utilities (esearch + esummary + efetch) | Theme-specific MeSH queries, `[pdat]` 14-day filter |
| bioRxiv / medRxiv | Public JSON API (`/details/biorxiv/<from>/<to>`) | Filtered to nutrition, biophysics, physiology |
| NEJM | RSS TOC | Keyword match against theme terms |
| Nature (subjournals) | RSS TOC | Same |
| The Lancet | RSS TOC | Same |
| Cell Metabolism | RSS TOC | Same |
| JAAD (J. Am. Acad. Dermatology) | RSS TOC | Skin & hair theme â€” keyword match |
| JID (J. Investigative Dermatology) | RSS TOC | Mechanistic skin/hair research |
| Br. J. Dermatology | RSS TOC | Clinical dermatology + AGA |
| Cochrane | RSS new-reviews feed | All new reviews in window |

### Unstructured path (WebSearch + WebFetch)

- **Examine.com** â€” new articles since last run
- **Stronger by Science / MASS** â€” Greg Nuckols, Eric Helms
- **Podcasts (transcripts/show notes):** Huberman, Attia, Rhonda Patrick
- **Influencers** (full list): Huberman, Attia, Patrick, Nuckols, Helms, Israetel, Schoenfeld, Nippard, Henselmans, Norton, Sinclair, Longo, Topol, Lyon, Phillips
- **NSCA / Strength and Conditioning Journal** â€” TOC scrape
- **Dermatology / skincare / hair-loss voices:** evidence-based dermatologists and skincare/hair-loss researchers â€” Dr. Shaaf Husaain, Dr. Dray (Andrea Suarez), Dr. Sam Ellis, LabMuffin (Dr. Michelle Wong), Lorraine Massey & others (TBD list â€” see Section 14)
- **Tressless / Reddit r/tressless** â€” community-curated AGA research threads (signal-noise risk; flag clearly as low evidence unless they cite primary papers)

### Cited-study seedback

When an unstructured source cites a primary paper with a DOI (e.g., Attia podcast referencing a Cell Metabolism study), the routine pulls the primary paper from PubMed and prefers it as the canonical entry, noting the podcast/blog as a "cited by" cross-reference.

---

## 4. Architecture

```
Friday 18:00 Europe/Warsaw  â†’  Scheduled remote agent fires
                                        â†“
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚ 1. COLLECT (hybrid)                              â”‚
   â”‚    Path A: collect_structured.py (APIs/RSS)      â”‚
   â”‚    Path B: collect_unstructured.py (WebSearch)   â”‚
   â”‚    â†’ raw_studies.json                            â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â†“
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚ 2. FILTER (filter_dedupe.py)                     â”‚
   â”‚    Load seen.json â†’ drop already-covered items   â”‚
   â”‚    â†’ new_studies.json                            â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â†“
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚ 3. SYNTHESIZE (synthesize.py)                    â”‚
   â”‚    LLM theme-groups across 6 themes:             â”‚
   â”‚    obesity / longevity / strength /              â”‚
   â”‚    supplements / sleep / skin & hair             â”‚
   â”‚    Rates evidence, writes:                       â”‚
   â”‚    â†’ digest.md  (English, ~4000-4500 words)      â”‚
   â”‚    â†’ angles.md  (Polish, newsletter-ready)       â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â†“
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚ 4. RENDER (render_html.py)                       â”‚
   â”‚    Apply fiteligent brandbook template:          â”‚
   â”‚    â†’ digest.html (branded, dark theme)           â”‚
   â”‚    â†’ angles.html (branded, dark theme)           â”‚
   â”‚    â†’ email_body.html (inlined CSS for clients)   â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                        â†“
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚ 5. DELIVER (notify.py + git)                     â”‚
   â”‚    Update seen.json, git commit + push,          â”‚
   â”‚    email branded HTML digest to ciastkofski@...  â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Why a Python orchestrator instead of a pure-prompt agent

- **Determinism** â€” same logic each run; debuggable
- **Cost** â€” only synthesize step needs LLM tokens
- **Testability** â€” manual trigger, dry-run mode, per-source replay all become trivial

The scheduled agent's prompt is ~30 lines: clone repo, run `python scripts/run.py`, report success/failure.

---

## 5. Repo Structure

```
fiteligent-research/
â”œâ”€â”€ README.md                       # how to read, tune, run manually
â”œâ”€â”€ seen.json                       # dedupe state (DOIs + URLs ever digested)
â”œâ”€â”€ config/
â”‚   â”œâ”€â”€ topics.yaml                 # MeSH terms + keywords per theme
â”‚   â”œâ”€â”€ sources.yaml                # API endpoints, RSS URLs, rate limits
â”‚   â””â”€â”€ influencers.yaml            # influencer names + canonical URLs/handles
â”œâ”€â”€ scripts/
â”‚   â”œâ”€â”€ collect_structured.py
â”‚   â”œâ”€â”€ collect_unstructured.py
â”‚   â”œâ”€â”€ filter_dedupe.py
â”‚   â”œâ”€â”€ synthesize.py
â”‚   â”œâ”€â”€ render_html.py              # markdown â†’ branded HTML via template
â”‚   â”œâ”€â”€ notify.py
â”‚   â”œâ”€â”€ run.py                      # orchestrator entry point
â”‚   â”œâ”€â”€ lib/
â”‚   â”‚   â”œâ”€â”€ schema.py               # Study dataclass + JSON I/O
â”‚   â”‚   â””â”€â”€ evidence.py             # study type â†’ evidence rating
â”‚   â””â”€â”€ tests/
â”‚       â”œâ”€â”€ test_schema.py
â”‚       â”œâ”€â”€ test_evidence.py
â”‚       â”œâ”€â”€ test_filter_dedupe.py
â”‚       â””â”€â”€ test_integration_goldenpath.py
â”œâ”€â”€ brand/                          # fiteligent brandbook assets (self-contained)
â”‚   â”œâ”€â”€ template_digest.html        # HTML shell for digest (dark theme)
â”‚   â”œâ”€â”€ template_angles.html        # HTML shell for angles
â”‚   â”œâ”€â”€ template_email.html         # email-safe variant (inlined CSS)
â”‚   â”œâ”€â”€ tokens.css                  # color/font/spacing tokens
â”‚   â”œâ”€â”€ logo.svg                    # fiteligent wordmark (white on gradient)
â”‚   â””â”€â”€ icons/                      # theme icons (obesity, longevity, etc.)
â”œâ”€â”€ digests/
â”‚   â””â”€â”€ 2026-05-15/                 # ISO date of run
â”‚       â”œâ”€â”€ digest.md               # source markdown (canonical)
â”‚       â”œâ”€â”€ digest.html             # branded HTML render
â”‚       â”œâ”€â”€ angles.md               # source markdown
â”‚       â”œâ”€â”€ angles.html             # branded HTML render
â”‚       â”œâ”€â”€ email_body.html         # inlined-CSS variant sent in email
â”‚       â”œâ”€â”€ raw_studies.json
â”‚       â”œâ”€â”€ new_studies.json
â”‚       â””â”€â”€ run.log
â”œâ”€â”€ docs/superpowers/specs/
â”‚   â””â”€â”€ 2026-05-14-fiteligent-research-routine-design.md
â”œâ”€â”€ pyproject.toml                  # pinned deps
â”œâ”€â”€ .env.example
â””â”€â”€ .gitignore
```

### `seen.json` schema

```json
{
  "by_doi": {
    "10.1056/NEJMxxx": { "first_seen": "2026-05-15", "digest": "2026-05-15" }
  },
  "by_url": {
    "https://examine.com/articles/...": { "first_seen": "2026-05-15" }
  }
}
```

Append-only. ~50 KB after a year, ~3 MB after a decade â€” negligible.

### Config-driven

`config/topics.yaml`, `config/sources.yaml`, `config/influencers.yaml` are the tuning surface. Adding a new influencer or dropping a low-signal feed means editing YAML, never code.

---

## 6. Output Format

### `digest.md` (English, ~4000 words)

Front matter (YAML): date range, study count, themes, generation timestamp.

Structure:
1. **TL;DR** â€” top 5 highlights with star ratings
2. **6 theme sections** â€” Obesity, Longevity, Strength, Supplements, Sleep, Skin & Hair
3. Per study within a section:
   - Title (H3)
   - Evidence stars, authors, journal, DOI link, n, study type
   - 150â€“200 word breakdown with key numbers (effect size, p, CIs)
   - "Why it matters" â€” practical implication
   - "Cited by" â€” cross-reference to any podcast/blog that surfaced it
4. **Sources scanned this week** â€” counts per source
5. **Run notes** â€” any failures or partial coverage

### Evidence rating scale (`lib/evidence.py`)

| Rating | Criteria |
|---|---|
| â˜…â˜…â˜…â˜…â˜… | Meta-analysis or large RCT (n>500) in high-impact journal |
| â˜…â˜…â˜…â˜…â˜† | Smaller RCT or strong cohort study |
| â˜…â˜…â˜…â˜†â˜† | Observational with good controls / small RCT |
| â˜…â˜…â˜†â˜†â˜† | Preprint, mechanistic, or weak observational |
| â˜…â˜†â˜†â˜†â˜† | Opinion, anecdote, podcast claim without cited source |

### `angles.md` (Polish, newsletter-ready)

Front matter: date, language, link back to digest.

Structure: 5â€“10 numbered angles. Each angle:
- **Hook headline** (Polish, in Jakub's voice â€” sarcastic, no BS)
- **Pitch** (2â€“3 sentences, conversational)
- **Suggested CTA** (Polish)
- **Å¹rÃ³dÅ‚o w digest** â€” pointer to the digest entry that inspired it
- **Zalecany kÄ…t newslettera** â€” mapping to one of the 10 newsletter angle slots from `fiteligent-newsletters/TEMPLATE.md`

Mapping to existing newsletter angles is mandatory so handoff is mechanical.

---

## 6b. Visual Presentation (Fiteligent Brandbook)

Two output surfaces follow the fiteligent brandbook: the email body (Friday delivery) and the HTML siblings of each digest written to disk. Markdown remains the canonical source so the routine stays diffable and tool-friendly; HTML is a rendered derivative.

### Source of truth

The brandbook template already used by `fiteligent-newsletters/DARK_TEMPLATE_BASE.html` is the visual baseline. The research repo gets its own copy in `brand/` so it's self-contained (no cross-repo dependency at runtime).

### Design tokens (`brand/tokens.css`)

```css
:root {
  /* Surfaces */
  --bg-page:       #0a0e27;   /* page background */
  --bg-container:  #1a1f3a;   /* digest card */
  --bg-footer:     #0a0e27;

  /* Brand colors */
  --brand-primary: #016FFA;   /* primary blue */
  --brand-deep:    #0047CC;   /* gradient deep stop */
  --brand-light:   #66A8FF;   /* gradient light stop, links */
  --accent:        #FF7B00;   /* CTAs, highlights, evidence stars */
  --accent-hover:  #E56A00;

  /* Text */
  --text-strong:   #ffffff;
  --text-body:     #e0e0e0;
  --text-muted:    #c0c0c0;
  --text-footer:   #808080;

  /* Type */
  --font-sans:     'Satoshi', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

  /* Layout */
  --container-max: 720px;     /* slightly wider than newsletter for denser digest */
  --radius:        12px;
}
```

The digest container is **720px** (vs. 600px for newsletters) â€” research content is denser and reads better with more horizontal room. Newsletter angles stay at 600px to match the existing newsletter ecosystem.

### Visual language per surface

| Surface | Container width | Layout style |
|---|---|---|
| `digest.html` | 720px | Full-screen reading: TL;DR cards at top, theme sections with colored left-borders (one accent color per theme), evidence stars in `--accent`, "Why it matters" callout boxes |
| `angles.html` | 600px | Newsletter-aligned: each angle as a hero card with hook headline (large), pitch, source pointer in muted, suggested-angle badge |
| `email_body.html` | 600px | Email-client-safe: tables-based layout, inlined CSS (via `premailer` or equivalent), one screen of TL;DR + "open full digest â†’" CTA linking to `digest.html` on disk/repo |

### Theme accent colors (consistent across all 3 surfaces)

Each of the 6 themes gets a dedicated accent color used for section borders, icons, and badges. Picked from the brand palette extended with sympathetic hues:

| Theme | Accent | Icon (SVG in `brand/icons/`) |
|---|---|---|
| Obesity & Metabolic Health | `#FF7B00` (brand orange) | scale / waistline |
| Longevity | `#66A8FF` (brand light blue) | hourglass |
| Strength & Hypertrophy | `#016FFA` (brand primary) | barbell (uses existing `LOGO_HANTEL.svg`) |
| Supplements | `#9D7BFF` (brand-adjacent violet) | capsule |
| Sleep & Recovery | `#3D5AFE` (brand-adjacent indigo) | moon |
| Skin & Hair Health | `#F472B6` (brand-adjacent rose) | droplet / follicle |

Violet, indigo, and rose are introduced specifically to give each theme visual separation; they sit within the brand's blue/purple register (rose extends warm-side), not foreign to the palette. The rose pairs naturally with the existing brand orange.

### Logo usage

- **Email header:** white wordmark on the `#0047CC â†’ #016FFA â†’ #66A8FF` gradient (same as `DARK_TEMPLATE_BASE.html`)
- **digest.html / angles.html:** same gradient header
- **Source:** `brand/logo.svg` (copied from `fiteligent-newsletters/svg_export_claude/`)

### Rendering pipeline (`render_html.py`)

```
1. Load brand/template_digest.html (Jinja2 template)
2. Parse digest.md â†’ AST (via markdown-it-py)
3. Map AST â†’ template blocks: TL;DR cards, theme sections, study cards, footer
4. Inject theme accent colors per section
5. Write digest.html
6. Same flow for angles.md â†’ angles.html (using template_angles.html)
7. Run premailer to produce email_body.html (inlined CSS for Gmail/Outlook safety)
```

The synthesize step writes markdown only; the render step is pure presentation. They stay separate so prompt iteration on synthesize doesn't risk breaking the visual layer, and vice versa.

### Bootstrapping `brand/`

Phase 1 of the rollout will copy these assets from `fiteligent-newsletters/`:

| Copied from | Copied to | Notes |
|---|---|---|
| `svg_export_claude/logo_same.svg` (or best wordmark variant) | `brand/logo.svg` | Verify it's the same wordmark used in DARK_TEMPLATE_BASE.html |
| `svg_export_claude/LOGO_HANTEL.svg` | `brand/icons/strength.svg` | Strength theme icon |
| `DARK_TEMPLATE_BASE.html` | `brand/template_email.html` | Adapt â€” replace `{{CONTENT}}` with Jinja2 blocks for digest TL;DR + theme sections |
| (derived from brandbook PDF colors) | `brand/tokens.css` | Already specified above |

The remaining theme icons (`obesity.svg`, `longevity.svg`, `supplements.svg`, `sleep.svg`, `skin-hair.svg`) need to be either sourced from the brandbook PDF or commissioned. **Open question** â€” see Section 14.

---

## 7. `run.py` Orchestrator Flow

```
1. Load configs (topics.yaml, sources.yaml, influencers.yaml)
2. collect_structured()   â†’ list[Study]
3. collect_unstructured() â†’ list[Study]
4. merge + filter_dedupe() against seen.json
5. if len(new_studies) < 5: send "thin week" alert and abort gracefully
6. synthesize() â†’ digest.md + angles.md
7. render_html() â†’ digest.html + angles.html + email_body.html
8. update seen.json with new DOIs/URLs
9. git add + commit "weekly digest YYYY-MM-DD (N studies)" + push
10. notify() â†’ send email_body.html to you@example.com (with repo commit link)
11. write digests/<date>/run.log with per-source counts and any errors
```

---

## 8. Failure Handling

| Failure mode | Behavior |
|---|---|
| Single source fails | Log, continue, note in `run.log` and at bottom of `digest.md` |
| Path A fully fails | Continue with Path B alone, mark digest "PARTIAL" |
| Synthesize fails | Don't commit; email alert with raw collected JSON attached |
| Render fails | Markdown succeeded â€” commit anyway, email plain-text body with `digest.md` attached; subject tagged `RENDER_FAILED` |
| Git push fails | Save locally, email alert with manual-recovery instructions |
| Email fails | Already committed to git; warn in next run's log |
| < 5 new studies | "Thin week" alert email, skip digest generation |

Email subject reflects state:
- `[Fiteligent Research] Digest 2026-05-15 (22 studies)` â€” normal
- `[Fiteligent Research] PARTIAL 2026-05-15 (8 studies, see notes)` â€” degraded
- `[Fiteligent Research] FAILED 2026-05-15` â€” full failure with diagnostics
- `[Fiteligent Research] THIN WEEK 2026-05-15` â€” < 5 new studies

---

## 9. Manual Triggers & Modes

| Command | Purpose |
|---|---|
| `python scripts/run.py` | Default â€” what the cron fires |
| `python scripts/run.py --manual` | Same as default but tagged "manual" in logs/email |
| `python scripts/run.py --dry-run` | Full pipeline â†’ `digests/_dry/<timestamp>/`; no commit, no email |
| `python scripts/run.py --since 2026-04-01` | Override 14-day lookback for backfill |
| `python scripts/run.py --source pubmed` | Run a single source path (debugging) |
| `python scripts/run.py --no-render` | Skip HTML rendering (markdown only) |
| `python scripts/render_html.py digests/<date>/` | Re-render HTML from existing markdown (template tweaks without rerunning collection) |

---

## 10. Testing Strategy

This is an aggregator, not a typical library. Tests have a narrow scope.

**Tested:**
- `lib/schema.py` â€” Study dataclass JSON round-trip
- `lib/evidence.py` â€” study type â†’ star rating table-driven
- `filter_dedupe.py` â€” given known `seen.json` + input, drops the right items
- `render_html.py` â€” given canonical `digest.md` fixture â†’ produces HTML matching golden file (smoke test: contains expected theme sections, accent colors are applied, no broken Jinja blocks)
- One **golden-path integration test** with mocked API responses â†’ assert `digest.md` is generated with expected structure (sections, counts, evidence ratings)

**Not tested:**
- Live API calls (network-brittle)
- LLM synthesis output (non-deterministic â€” covered by human review in rollout)
- Cron firing itself (trusted infrastructure)

Tests live in `scripts/tests/`, run via `pytest`. Target: ~150 lines.

---

## 11. Rollout Plan

**Phase 1 â€” Manual dry runs (week 1)**
- Bootstrap `brand/` (copy logo, adapt `DARK_TEMPLATE_BASE.html` into Jinja2 templates, write `tokens.css`)
- Build scripts, run `--dry-run` repeatedly
- Render HTML samples and verify they match the fiteligent visual identity (open `digest.html` in browser, send `email_body.html` test to inbox to check Gmail/Outlook rendering)
- Tune `topics.yaml` keywords as PubMed results come in
- No email, no cron

**Phase 2 â€” Manual trigger, real output (week 2)**
- One `--manual` run, full pipeline live
- Email delivered, commit made, cron still off
- Human review of first real `digest.md` + `angles.md`
- Tune synthesize prompt based on what looks off

**Phase 3 â€” Cron on (week 3+)**
- Register scheduled task, autonomous Friday runs
- First 4 weeks: skim `run.log` each Saturday morning
- After a month clean: fully autonomous

---

## 12. Observability

- **Per-run:** `digests/<date>/run.log` â€” per-source counts, errors, timing
- **Across runs:** `git log` on the `digests/` directory shows run cadence at a glance
- **Canary:** missing Saturday email = scheduler issue (visible within a week)

---

## 13. Secrets

| Secret | Purpose | Source |
|---|---|---|
| `ANTHROPIC_API_KEY` | LLM synthesis | Scheduled-agent environment |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` | Email delivery | Same |
| `GIT_PUSH_TOKEN` | Push to research repo | Same |

`.env.example` documents required vars; real `.env` is gitignored.

---

## 14. Open Questions / Deferred

**Open items for v1:**

- **Theme icons (`brand/icons/obesity.svg`, `longevity.svg`, `supplements.svg`, `sleep.svg`, `skin-hair.svg`)** â€” `strength.svg` reuses the existing `LOGO_HANTEL.svg`, but the other five don't have brand-native equivalents. Options: (a) source from the brandbook PDF if present, (b) commission/design new ones in fiteligent style, (c) ship v1 with text-only theme headers and add icons in v1.1. Recommended default: **(c)** â€” don't block rollout on icons.
- **Dermatology / skincare / hair-loss influencer list** â€” initial Section 3 list (Dr. Husaain, Dr. Dray, Dr. Sam Ellis, LabMuffin) is provisional. Before Phase 2 rollout, vet candidates against the "evidence-grade signal vs. opinion noise" bar applied to the core 15 influencers. Drop pure-aesthetic/beauty voices that don't cite primary literature.

**Items intentionally deferred from scope:**

- **Polish-language influencer coverage** (Parol, OstrÄ™ga, Mauricz) â€” deferred per user decision; can be added later by extending `influencers.yaml`
- **Notion / Drive cross-posting** â€” explicitly rejected; git + email only
- **Web dashboard / published research blog** â€” not in scope; the HTML files in the repo are the UI. If you later want a public research page on fiteligent.pl, the HTML output is already styled correctly and can be lifted directly.
- **Per-angle A/B newsletter analytics feedback loop** â€” interesting but out of scope for v1
- **Polish translation of `digest.md`** â€” synthesize step writes English digest only; if you want a Polish translation later, add a `translate.py` step between synthesize and render

---

## 15. Success Criteria

The routine succeeds if:

1. A Friday digest arrives in inbox 4 weeks running with zero manual intervention
2. â‰¥ 80% of digest studies are *new* (dedupe is working)
3. Each digest produces â‰¥ 3 angles that actually become newsletter content over the following month
4. Time-to-produce-newsletter-draft drops from current (cold-start research) to <30 minutes (start from `angles.md`, pick one, expand)
5. No silent failures â€” every degraded run produces a clearly-tagged email
