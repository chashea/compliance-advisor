import json

import pytest

import compliance_tools


def test_search_knowledge_requires_query():
    with pytest.raises(ValueError):
        compliance_tools.search_knowledge(query="")


def test_search_knowledge_returns_wrapped_results(monkeypatch):
    def _mock_search(**kwargs):
        assert kwargs["query"] == "NIST access control"
        assert kwargs["top"] == 3
        assert kwargs["category"] == "NIST"
        return [{"id": "doc-1", "title": "AC-2", "content": "Account management"}]

    monkeypatch.setattr(compliance_tools, "search_knowledge_documents", _mock_search)
    payload = compliance_tools.search_knowledge(
        query="NIST access control",
        top=3,
        category="NIST",
    )

    parsed = json.loads(payload)
    assert "results" in parsed
    assert parsed["results"][0]["id"] == "doc-1"
