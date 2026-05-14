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
