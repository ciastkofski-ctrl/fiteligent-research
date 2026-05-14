from datetime import date
import respx
import httpx
from scripts.collect_structured import fetch_journal_rss


SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Cell Metabolism</title>
    <item>
      <title>Time-restricted eating reduces visceral fat</title>
      <link>https://www.cell.com/cell-metabolism/article/PIIxxx</link>
      <description>RCT shows TRE outperforms continuous CR for visceral adiposity.</description>
      <pubDate>Mon, 05 May 2026 00:00:00 GMT</pubDate>
      <dc:date>2026-05-05</dc:date>
    </item>
    <item>
      <title>Unrelated cardiology paper on stents</title>
      <link>https://www.cell.com/cell-metabolism/article/PIIyyy</link>
      <description>Stent angioplasty cohort.</description>
      <pubDate>Mon, 05 May 2026 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


@respx.mock
def test_fetch_rss_keyword_filters():
    respx.get("https://www.cell.com/cell-metabolism/current.rss").mock(
        return_value=httpx.Response(200, text=SAMPLE_RSS)
    )

    studies = fetch_journal_rss(
        feed_url="https://www.cell.com/cell-metabolism/current.rss",
        journal_name="Cell Metabolism",
        keyword_filters={"obesity": ["visceral", "TRE", "fat", "CR"]},
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 15),
    )

    assert len(studies) == 1
    assert "Time-restricted" in studies[0].title
    assert studies[0].theme_guess == "obesity"
    assert studies[0].journal == "Cell Metabolism"
