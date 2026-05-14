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
