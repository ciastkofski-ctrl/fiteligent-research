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
