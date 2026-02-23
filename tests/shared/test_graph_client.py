"""Tests for shared.graph_client — model conversion, pagination, HTTP fallback."""
from unittest.mock import patch, MagicMock
import pytest
import requests


class TestModelToDict:
    def test_none_returns_empty_dict(self):
        from shared.graph_client import _model_to_dict
        assert _model_to_dict(None) == {}

    def test_plain_dict_returns_same(self):
        from shared.graph_client import _model_to_dict
        d = {"key": "value"}
        assert _model_to_dict(d) == d

    def test_object_extracts_public_attrs(self):
        from shared.graph_client import _model_to_dict
        obj = MagicMock(spec=[])
        obj.name = "test"
        obj.score = 42
        obj.additional_data = None
        result = _model_to_dict(obj)
        assert result["name"] == "test"
        assert result["score"] == 42

    def test_object_merges_additional_data(self):
        from shared.graph_client import _model_to_dict
        obj = MagicMock(spec=[])
        obj.name = "test"
        obj.additional_data = {"scoreImpact": "high"}
        result = _model_to_dict(obj)
        assert result["scoreImpact"] == "high"


class TestGetSecureScores:
    def test_invalid_days_zero_raises(self):
        from shared.graph_client import get_secure_scores
        with pytest.raises(ValueError):
            get_secure_scores(token="tok", days=0)

    def test_invalid_days_91_raises(self):
        from shared.graph_client import get_secure_scores
        with pytest.raises(ValueError):
            get_secure_scores(token="tok", days=91)

    def test_valid_days_returns_items(self):
        from shared.graph_client import get_secure_scores
        with patch("shared.graph_client._paginate") as mock_pag:
            mock_pag.return_value = iter([{"id": "1"}, {"id": "2"}])
            result = get_secure_scores(token="tok", days=3)
        assert len(result) == 2


class TestPaginate:
    def test_follows_next_link(self):
        from shared.graph_client import _paginate
        page1 = {"value": [{"id": "1"}], "@odata.nextLink": "https://next"}
        page2 = {"value": [{"id": "2"}]}

        with patch("shared.graph_client._get") as mock_get:
            mock_get.side_effect = [page1, page2]
            items = list(_paginate("https://start", "tok"))

        assert len(items) == 2
        assert items[0]["id"] == "1"
        assert items[1]["id"] == "2"


class TestComplianceAssessmentsFallback:
    def test_falls_back_on_404(self):
        from shared.graph_client import get_compliance_assessments

        err = requests.HTTPError(response=MagicMock(status_code=404))
        with patch("shared.graph_client._paginate") as mock_pag:
            mock_pag.side_effect = [err, iter([{"id": "a1"}])]
            result = get_compliance_assessments("tok")

        assert result == [{"id": "a1"}]

    def test_reraises_non_404(self):
        from shared.graph_client import get_compliance_assessments

        err = requests.HTTPError(response=MagicMock(status_code=500))
        with patch("shared.graph_client._paginate") as mock_pag:
            mock_pag.side_effect = err
            with pytest.raises(requests.HTTPError):
                get_compliance_assessments("tok")
