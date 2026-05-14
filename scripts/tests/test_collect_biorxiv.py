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
