"""Tests for prepare_briefing_data — pure Python data transformation."""
from prepare_briefing_data import prepare_briefing_data


class TestEmptyScores:
    def test_returns_has_data_false(self):
        result = prepare_briefing_data([], [], [], [], [])
        assert result["has_data"] is False
        assert result["scope"] == "Enterprise-wide"

    def test_department_filter_in_scope(self):
        result = prepare_briefing_data([], [], [], [], [], department_filter="Finance")
        assert result["scope"] == "Finance"


class TestSummaryCalculations:
    def _scores(self, pcts):
        return [{"compliance_pct": p, "display_name": f"T{i}",
                 "department": "D", "risk_tier": "Low"}
                for i, p in enumerate(pcts)]

    def test_avg_compliance_pct(self):
        result = prepare_briefing_data(self._scores([60, 80]), [], [], None, [])
        assert result["summary"]["avg_compliance_pct"] == 70.0

    def test_min_max_compliance_pct(self):
        result = prepare_briefing_data(self._scores([55, 90, 70]), [], [], None, [])
        assert result["summary"]["min_compliance_pct"] == 55.0
        assert result["summary"]["max_compliance_pct"] == 90.0

    def test_weakest_limited_to_three(self):
        result = prepare_briefing_data(self._scores([10, 20, 30, 40, 50]), [], [], None, [])
        assert len(result["weakest_tenants"]) == 3
        assert result["weakest_tenants"][0]["compliance_pct"] == 10

    def test_strongest_limited_to_three(self):
        result = prepare_briefing_data(self._scores([10, 20, 30, 40, 50]), [], [], None, [])
        assert len(result["strongest_tenants"]) == 3
        assert result["strongest_tenants"][0]["compliance_pct"] == 50


class TestTrendClassification:
    def test_counts_correct(self):
        trends = [
            {"trend_direction": "Improving", "wow_change": 5, "display_name": "A"},
            {"trend_direction": "Declining", "wow_change": -3, "display_name": "B"},
            {"trend_direction": "Stable", "wow_change": 0, "display_name": "C"},
        ]
        scores = [{"compliance_pct": 50, "display_name": "X", "department": "D", "risk_tier": "L"}]
        result = prepare_briefing_data(scores, trends, [], None, [])
        ts = result["trend_summary"]
        assert ts["improving_count"] == 1
        assert ts["declining_count"] == 1
        assert ts["stable_count"] == 1

    def test_improving_sorted_descending(self):
        trends = [
            {"trend_direction": "Improving", "wow_change": 2, "display_name": "A"},
            {"trend_direction": "Improving", "wow_change": 10, "display_name": "B"},
        ]
        scores = [{"compliance_pct": 50, "display_name": "X", "department": "D", "risk_tier": "L"}]
        result = prepare_briefing_data(scores, trends, [], None, [])
        assert result["trend_summary"]["top_improvers"][0]["change"] == 10

    def test_declining_sorted_ascending(self):
        trends = [
            {"trend_direction": "Declining", "wow_change": -1, "display_name": "A"},
            {"trend_direction": "Declining", "wow_change": -8, "display_name": "B"},
        ]
        scores = [{"compliance_pct": 50, "display_name": "X", "department": "D", "risk_tier": "L"}]
        result = prepare_briefing_data(scores, trends, [], None, [])
        assert result["trend_summary"]["top_decliners"][0]["change"] == -8


class TestAssessmentSummary:
    def test_none_assessment_summary_handled(self):
        scores = [{"compliance_pct": 50, "display_name": "X", "department": "D", "risk_tier": "L"}]
        result = prepare_briefing_data(scores, [], [], None, [])
        assert result["summary"]["total_assessments"] == 0

    def test_top_gaps_limited_to_10(self):
        scores = [{"compliance_pct": 50, "display_name": "X", "department": "D", "risk_tier": "L"}]
        gaps = [{"id": i} for i in range(15)]
        result = prepare_briefing_data(scores, [], [], None, gaps)
        assert len(result["top_gaps"]) == 10

    def test_low_scoring_sorted_ascending(self):
        scores = [{"compliance_pct": 50, "display_name": "X", "department": "D", "risk_tier": "L"}]
        assessments = [
            {"regulation": "A", "compliance_score": 90},
            {"regulation": "B", "compliance_score": 30},
            {"regulation": "C", "compliance_score": 60},
        ]
        result = prepare_briefing_data(scores, [], [], assessments, [])
        assert result["assessment_summary"][0]["compliance_score"] == 30
