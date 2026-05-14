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
