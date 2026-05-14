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
