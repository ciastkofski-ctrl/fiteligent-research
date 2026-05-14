from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

# Allow `python scripts/run.py` direct invocation (no -m) in addition to
# the standard `python -m scripts.run` / import path.
_REPO_ROOT_EARLY = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT_EARLY) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_EARLY))

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
            repo_url = os.environ.get("REPO_DIGEST_URL_BASE", "")
            digest_url = f"{repo_url}/{run_date.isoformat()}/digest.html" if repo_url else f"file://{out_dir}/digest.html"
            render_email_body(
                digest_md, brand_dir, out_dir / "email_body.html",
                run_date.isoformat(),
                digest_url=digest_url,
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
