from datetime import date
import pytest
from scripts.lib.schema import Study


@pytest.fixture
def sample_studies():
    return [
        Study(title="A", url="https://a.org", doi="10.1/a", source="pubmed", published=date(2026, 5, 1)),
        Study(title="B", url="https://b.org", doi="10.1/b", source="pubmed", published=date(2026, 5, 2)),
        Study(title="C", url="https://c.org", source="examine", published=date(2026, 5, 3)),
    ]
