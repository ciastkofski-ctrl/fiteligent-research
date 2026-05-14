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
