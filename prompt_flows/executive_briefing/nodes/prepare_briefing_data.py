"""
Prepare and structure the data payload for the executive briefing prompt.
Operates on Compliance Manager data — assessments, compliance scores, and controls.
"""


def prepare_briefing_data(
    scores: list[dict],
    trends: list[dict],
    department_rollup: list[dict],
    assessment_summary: list[dict],
    top_gaps: list[dict],
    department_filter: str = "",
) -> dict:
    if not scores:
        return {
            "has_data": False,
            "scope": department_filter or "Enterprise-wide",
        }

    # Enterprise / department compliance summary
    total_tenants = len(scores)
    avg_pct = round(sum(s.get("compliance_pct", 0) for s in scores) / total_tenants, 1)
    min_pct = round(min(s.get("compliance_pct", 0) for s in scores), 1)
    max_pct = round(max(s.get("compliance_pct", 0) for s in scores), 1)

    weakest = sorted(scores, key=lambda s: s.get("compliance_pct", 0))[:3]
    strongest = sorted(scores, key=lambda s: s.get("compliance_pct", 0), reverse=True)[:3]

    # Classify trends
    improving = [t for t in trends if t.get("trend_direction") == "Improving"]
    declining = [t for t in trends if t.get("trend_direction") == "Declining"]
    stable = [t for t in trends if t.get("trend_direction") == "Stable"]

    # Sort by magnitude of change
    improving.sort(key=lambda t: t.get("wow_change", 0), reverse=True)
    declining.sort(key=lambda t: t.get("wow_change", 0))

    # Assessment highlights
    total_assessments = len(assessment_summary) if assessment_summary else 0
    regulations = list({a.get("regulation", "Unknown") for a in (assessment_summary or [])})
    low_scoring = sorted(
        (assessment_summary or []),
        key=lambda a: a.get("compliance_score", a.get("pass_rate", 100)),
    )[:5]

    return {
        "has_data": True,
        "scope": department_filter or "Enterprise-wide",
        "generated_at": _utcnow(),
        "summary": {
            "total_tenants": total_tenants,
            "avg_compliance_pct": avg_pct,
            "min_compliance_pct": min_pct,
            "max_compliance_pct": max_pct,
            "total_assessments": total_assessments,
            "regulations_tracked": regulations,
        },
        "weakest_tenants": [
            {"name": s.get("display_name"), "department": s.get("department"),
             "compliance_pct": s.get("compliance_pct"), "risk_tier": s.get("risk_tier")}
            for s in weakest
        ],
        "strongest_tenants": [
            {"name": s.get("display_name"), "department": s.get("department"),
             "compliance_pct": s.get("compliance_pct")}
            for s in strongest
        ],
        "trend_summary": {
            "improving_count": len(improving),
            "declining_count": len(declining),
            "stable_count": len(stable),
            "top_improvers": [
                {"name": t.get("display_name"), "change": t.get("wow_change")}
                for t in improving[:3]
            ],
            "top_decliners": [
                {"name": t.get("display_name"), "change": t.get("wow_change")}
                for t in declining[:3]
            ],
        },
        "department_rollup": department_rollup,
        "assessment_summary": low_scoring,
        "top_gaps": top_gaps[:10],
    }


def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
