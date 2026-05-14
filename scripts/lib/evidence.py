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
