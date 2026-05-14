from datetime import date
import respx
import httpx
from scripts.collect_structured import fetch_pubmed


PUBMED_ESEARCH_RESPONSE = """<?xml version="1.0"?>
<eSearchResult>
  <Count>2</Count>
  <IdList>
    <Id>40000001</Id>
    <Id>40000002</Id>
  </IdList>
</eSearchResult>"""

PUBMED_ESUMMARY_RESPONSE = """<?xml version="1.0"?>
<eSummaryResult>
  <DocSum>
    <Id>40000001</Id>
    <Item Name="Title" Type="String">Semaglutide and resistance training preserves lean mass</Item>
    <Item Name="AuthorList" Type="List">
      <Item Name="Author" Type="String">Smith J</Item>
      <Item Name="Author" Type="String">Doe A</Item>
    </Item>
    <Item Name="Source" Type="String">Cell Metab</Item>
    <Item Name="PubDate" Type="Date">2026 May 1</Item>
    <Item Name="DOI" Type="String">10.1016/j.cmet.2026.05.001</Item>
    <Item Name="PubTypeList" Type="List">
      <Item Name="PubType" Type="String">Randomized Controlled Trial</Item>
    </Item>
  </DocSum>
  <DocSum>
    <Id>40000002</Id>
    <Item Name="Title" Type="String">Meta-analysis of GLP-1 receptor agonists in obesity</Item>
    <Item Name="AuthorList" Type="List"><Item Name="Author" Type="String">Brown K</Item></Item>
    <Item Name="Source" Type="String">JAMA</Item>
    <Item Name="PubDate" Type="Date">2026 May 5</Item>
    <Item Name="DOI" Type="String">10.1001/jama.2026.05.002</Item>
    <Item Name="PubTypeList" Type="List"><Item Name="PubType" Type="String">Meta-Analysis</Item></Item>
  </DocSum>
</eSummaryResult>"""

PUBMED_EFETCH_RESPONSE = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">40000001</PMID>
      <Article>
        <Abstract>
          <AbstractText Label="BACKGROUND">Two-arm RCT comparing semaglutide alone vs semaglutide + 3x/wk resistance training.</AbstractText>
          <AbstractText Label="RESULTS">Lean mass loss 4.2 kg vs 1.1 kg favoring RT arm (p&lt;0.001).</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">40000002</PMID>
      <Article>
        <Abstract>
          <AbstractText>Meta-analysis of 14 GLP-1 RCTs.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""


@respx.mock
def test_fetch_pubmed_returns_studies_with_metadata():
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, text=PUBMED_ESEARCH_RESPONSE)
    )
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
        return_value=httpx.Response(200, text=PUBMED_ESUMMARY_RESPONSE)
    )
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
        return_value=httpx.Response(200, text=PUBMED_EFETCH_RESPONSE)
    )

    studies = fetch_pubmed(
        query='"obesity"[MeSH]',
        theme="obesity",
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 15),
        max_results=10,
    )

    assert len(studies) == 2
    s1 = studies[0]
    assert s1.title.startswith("Semaglutide")
    assert s1.doi == "10.1016/j.cmet.2026.05.001"
    assert s1.journal == "Cell Metab"
    assert s1.study_type == "RCT"
    assert s1.theme_guess == "obesity"
    assert s1.authors == ["Smith J", "Doe A"]
    assert s1.abstract is not None and "RCT" in s1.abstract

    s2 = studies[1]
    assert s2.study_type == "meta-analysis"
    assert s2.abstract is not None and "GLP-1" in s2.abstract
