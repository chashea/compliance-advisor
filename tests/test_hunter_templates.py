"""Tests for hunter query templates."""

from collector.hunter.templates import (
    build_examples_prompt,
    get_template,
    list_templates,
    render_template,
)


def test_list_templates_returns_all():
    templates = list_templates()
    assert len(templates) == 14
    names = {t.name for t in templates}
    assert "label-downgrade" in names
    assert "usb-exfil" in names
    assert "comm-compliance" in names


def test_get_template_found():
    t = get_template("label-downgrade")
    assert t is not None
    assert t.name == "label-downgrade"
    assert t.table == "DataSecurityEvents"


def test_get_template_not_found():
    assert get_template("nonexistent") is None


def test_render_template_defaults():
    t = get_template("label-downgrade")
    kql = render_template(t, days=30, limit=50)
    assert "ago(30d)" in kql
    assert "limit 50" in kql
    assert "SensitivityLabelDowngraded" in kql


def test_render_template_custom_params():
    t = get_template("usb-exfil")
    kql = render_template(t, days=7, limit=100)
    assert "ago(7d)" in kql
    assert "limit 100" in kql


def test_all_templates_render():
    """Verify all templates render without KeyError."""
    for t in list_templates():
        kql = render_template(t, days=14, limit=25)
        assert "ago(14d)" in kql
        assert "limit 25" in kql
        assert t.table in kql


def test_build_examples_prompt():
    prompt = build_examples_prompt()
    assert "Question:" in prompt
    assert "KQL:" in prompt
    # Should include first 6 templates
    assert "label-downgrade" not in prompt or "SensitivityLabelDowngraded" in prompt
