"""
Phase C4/C8 tests for provider-docs extraction and scraper self-healing.

These read the real layout files, so they fail if the docs site is edited in a
way that breaks the demo - notably if the two layouts stop being genuinely
different, or if their visible content drifts apart.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from integrations.brightdata.client import BrightDataClient  # noqa: E402
from integrations.brightdata.extractor import (  # noqa: E402
    SELECTORS_V1,
    SELECTORS_V2,
    extract_with_selectors,
    rediscover_selectors,
)

LAYOUTS = Path(__file__).resolve().parent.parent / "provider-docs-site" / "layouts"


def load(version: str) -> str:
    return (LAYOUTS / version / "pricing-docs.html").read_text(encoding="utf-8")


@pytest.fixture
def v1_html():
    return load("v1")


@pytest.fixture
def v2_html():
    return load("v2")


class TestExtractionOnTrainedLayout:
    def test_v1_selectors_extract_v1_completely(self, v1_html):
        result = extract_with_selectors(v1_html, SELECTORS_V1)
        assert result.ok
        assert result.missing == []

    def test_v2_selectors_extract_v2_completely(self, v2_html):
        result = extract_with_selectors(v2_html, SELECTORS_V2)
        assert result.ok
        assert result.missing == []

    def test_field_mappings_are_captured(self, v1_html):
        result = extract_with_selectors(v1_html, SELECTORS_V1)
        pairs = {p["old"]: p["new"] for p in result.field_pairs}
        assert pairs == {
            "price": "pricing.amount",
            "currency": "pricing.currency",
        }

    def test_changelog_date_label_is_stripped(self, v1_html):
        result = extract_with_selectors(v1_html, SELECTORS_V1)
        assert result.fields["changelog_date"] == "January 15, 2024"

    def test_inline_tags_do_not_weld_words(self, v1_html):
        """<code> tags inside the guidance must not produce 'nestedpricingobject'."""
        result = extract_with_selectors(v1_html, SELECTORS_V1)
        assert "nested pricing object" in result.fields["migration_guidance"]


class TestLayoutBreakIsReal:
    """
    The self-heal demo is only meaningful if the break is genuine. These guard
    against someone "fixing" the demo by making V1 selectors match both layouts.
    """

    def test_v1_selectors_fail_on_v2(self, v2_html):
        result = extract_with_selectors(v2_html, SELECTORS_V1)
        assert not result.ok
        assert "field_mappings" in result.missing

    def test_v1_selectors_find_no_field_pairs_on_v2(self, v2_html):
        result = extract_with_selectors(v2_html, SELECTORS_V1)
        assert result.field_pairs == []

    def test_v2_selectors_fail_on_v1(self, v1_html):
        result = extract_with_selectors(v1_html, SELECTORS_V2)
        assert not result.ok

    def test_layouts_have_disjoint_structural_selectors(self, v1_html, v2_html):
        assert SELECTORS_V1.field_rows not in v2_html
        assert SELECTORS_V2.field_rows not in v1_html


class TestVisibleContentParity:
    """
    A judge (and a scraper) must not be able to tell the layouts apart from the
    text. Only the DOM differs.
    """

    def test_both_layouts_carry_the_same_evidence(self, v1_html, v2_html):
        from_v1 = extract_with_selectors(v1_html, SELECTORS_V1).as_raw_data()
        from_v2 = extract_with_selectors(v2_html, SELECTORS_V2).as_raw_data()

        for key in [
            "provider_name",
            "version",
            "old_field_price",
            "new_field_price",
            "old_field_currency",
            "new_field_currency",
            "migration_guidance",
            "changelog_date",
        ]:
            assert from_v1[key] == from_v2[key], f"{key} differs between layouts"

    def test_layout_version_does_not_leak_into_text(self, v1_html, v2_html):
        for html in (v1_html, v2_html):
            assert "Layout V1" not in html
            assert "Layout V2" not in html


class TestSelfHealing:
    def test_rediscovers_selectors_for_v2(self, v2_html):
        healed = rediscover_selectors(v2_html)
        assert healed is not None
        assert healed.version == "docs-layout-v2"

    def test_rediscovers_selectors_for_v1(self, v1_html):
        healed = rediscover_selectors(v1_html)
        assert healed is not None
        assert healed.version == "docs-layout-v1"

    def test_gives_up_on_unrecognisable_page(self):
        assert rediscover_selectors("<html><body><p>nothing</p></body></html>") is None


class StubClient(BrightDataClient):
    """A client whose page fetch is driven by a settable layout."""

    def __init__(self, layout: str):
        os.environ.pop("BRIGHTDATA_ZONE", None)
        super().__init__(api_token=None, scraper_id=None)
        self.layout = layout
        self.fetches = 0

    def _fetch_html(self, url: str, timeout: int = 60) -> str:
        self.fetches += 1
        return load(self.layout)


class TestClientSelfHealWorkflow:
    def test_extracts_cleanly_before_the_break(self):
        client = StubClient("v1")
        evidence = client.extract_and_validate("http://docs.test/pricing")
        assert evidence is not None
        assert evidence.self_heal_attempted is False
        assert evidence.selectors_used == "docs-layout-v1"

    def test_health_reports_degraded_after_the_break(self):
        client = StubClient("v1")
        client.extract_and_validate("http://docs.test/pricing")

        client.layout = "v2"
        health = client.get_scraper_health("http://docs.test/pricing")
        assert health["status"] == "degraded"
        assert health["field_mappings_found"] == 0

    def test_self_heal_recovers_the_same_evidence(self):
        client = StubClient("v1")
        before = client.extract_and_validate("http://docs.test/pricing")

        client.layout = "v2"
        after = client.extract_and_validate("http://docs.test/pricing")

        assert after is not None
        assert after.self_heal_attempted is True
        assert after.selectors_used == "docs-layout-v2"

        # The provider's truth did not change - only the page structure did.
        assert after.old_field_price == before.old_field_price
        assert after.new_field_price == before.new_field_price
        assert after.new_field_currency == before.new_field_currency

    def test_no_evidence_when_self_heal_is_disabled(self):
        client = StubClient("v1")
        client.extract_and_validate("http://docs.test/pricing")

        client.layout = "v2"
        result = client.extract_and_validate(
            "http://docs.test/pricing", retry_with_self_heal=False
        )
        assert result is None, "a broken scraper must yield no evidence, not stale evidence"
