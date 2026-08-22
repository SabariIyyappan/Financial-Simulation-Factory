"""
Selector-based extraction of migration evidence from provider docs HTML.

This module models what a Bright Data Scraper Studio collector does: a saved set
of CSS selectors is applied to the page, and whatever they capture becomes the
structured record.

The important property for the demo is that the selectors are *real*. A selector
set trained on docs-layout-v1 finds nothing in docs-layout-v2, so switching the
layout produces a genuine extraction failure rather than a simulated one. That
failure is what Bright Data Self-Healing then repairs.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class SelectorSet:
    """
    A saved collector configuration - the selectors Scraper Studio applies.

    `version` names the layout the selectors were trained against, which is what
    makes a stale set diagnosable after a site redesign.
    """

    version: str
    provider_name: str
    api_version: str
    field_rows: str
    old_field: str
    new_field: str
    migration_guidance: str
    changelog_date: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "trained_on": self.version,
            "provider_name": self.provider_name,
            "api_version": self.api_version,
            "field_rows": self.field_rows,
            "old_field": self.old_field,
            "new_field": self.new_field,
            "migration_guidance": self.migration_guidance,
            "changelog_date": self.changelog_date,
        }


# Selectors captured when the scraper was first configured against layout V1.
# This is the "saved scraper" that breaks when the provider redesigns their docs.
SELECTORS_V1 = SelectorSet(
    version="docs-layout-v1",
    provider_name=".header h1",
    api_version=".version-info .version",
    field_rows=".migration-section .field-change",
    old_field=".old-field",
    new_field=".new-field",
    migration_guidance=".migration-section h3 + p",
    changelog_date=".changelog .changelog-entry .date",
)

# Selectors that Self-Healing converges on after the layout V2 redesign.
SELECTORS_V2 = SelectorSet(
    version="docs-layout-v2",
    provider_name=".header h1",
    api_version=".version-badge span",
    field_rows=".breaking-changes-container .field-mapping",
    old_field=".deprecated",
    new_field=".current",
    migration_guidance=".breaking-changes-container h3 + p",
    changelog_date=".version-history .history-item .timestamp",
)

KNOWN_SELECTOR_SETS = [SELECTORS_V1, SELECTORS_V2]


@dataclass
class ExtractionResult:
    """Raw output of applying a selector set to a page."""

    fields: Dict[str, str] = field(default_factory=dict)
    field_pairs: List[Dict[str, str]] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    selectors_used: str = ""

    @property
    def ok(self) -> bool:
        return not self.missing

    def as_raw_data(self) -> Dict[str, object]:
        """Shape the result the way the Bright Data client expects it."""
        price = self._pair_for("price")
        currency = self._pair_for("currency")

        return {
            "provider_name": self.fields.get("provider_name", ""),
            "version": self.fields.get("api_version", ""),
            "breaking_change_summary": self.fields.get("migration_guidance", ""),
            "old_field_price": price.get("old", ""),
            "new_field_price": price.get("new", ""),
            "old_field_currency": currency.get("old", ""),
            "new_field_currency": currency.get("new", ""),
            "migration_guidance": self.fields.get("migration_guidance", ""),
            "changelog_date": self.fields.get("changelog_date", ""),
            "extraction_successful": self.ok,
            "missing_fields": self.missing,
            "selectors_used": self.selectors_used,
        }

    def _pair_for(self, needle: str) -> Dict[str, str]:
        for pair in self.field_pairs:
            if needle in pair.get("old", "").lower():
                return pair
        return {}


# Fields that must be present for evidence to be usable by the repair workflow.
REQUIRED_FIELDS = [
    "provider_name",
    "api_version",
    "migration_guidance",
    "changelog_date",
]


def _text(soup: BeautifulSoup, selector: str) -> Optional[str]:
    node = soup.select_one(selector)
    if node is None:
        return None
    # Join with a space so inline tags (<code>, <strong>) do not weld words
    # together, then collapse the runs that introduces.
    value = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
    return value or None


def extract_with_selectors(html: str, selectors: SelectorSet) -> ExtractionResult:
    """
    Apply a selector set to a docs page.

    Returns a result listing whatever the selectors could not find, rather than
    raising - a partial scrape is a data-quality signal, not a crash.
    """
    soup = BeautifulSoup(html, "html.parser")
    result = ExtractionResult(selectors_used=selectors.version)

    simple_fields = {
        "provider_name": selectors.provider_name,
        "api_version": selectors.api_version,
        "migration_guidance": selectors.migration_guidance,
        "changelog_date": selectors.changelog_date,
    }

    for name, selector in simple_fields.items():
        value = _text(soup, selector)
        if value is None:
            result.missing.append(name)
        else:
            result.fields[name] = value

    # Field mappings (old path -> new path) come from repeated rows.
    for row in soup.select(selectors.field_rows):
        old = row.select_one(selectors.old_field)
        new = row.select_one(selectors.new_field)
        if old is None or new is None:
            continue
        result.field_pairs.append(
            {
                "old": old.get_text(strip=True),
                "new": new.get_text(strip=True),
            }
        )

    if not result.field_pairs:
        result.missing.append("field_mappings")

    # A changelog date like "Released: January 15, 2024" carries a label.
    raw_date = result.fields.get("changelog_date")
    if raw_date:
        result.fields["changelog_date"] = re.sub(
            r"^\s*Released:\s*", "", raw_date
        ).strip()

    if result.missing:
        logger.warning(
            "Extraction with %s selectors incomplete - missing: %s",
            selectors.version,
            ", ".join(result.missing),
        )
    else:
        logger.info(
            "Extraction with %s selectors captured all required fields",
            selectors.version,
        )

    return result


def rediscover_selectors(html: str) -> Optional[SelectorSet]:
    """
    Find a selector set that fits the current page.

    This stands in for Bright Data Self-Healing: when the saved selectors stop
    matching, the collector re-derives working ones from the page itself rather
    than a human rewriting the scraper.
    """
    for candidate in KNOWN_SELECTOR_SETS:
        result = extract_with_selectors(html, candidate)
        if result.ok:
            logger.info("Self-healing converged on %s selectors", candidate.version)
            return candidate

    logger.error("Self-healing could not find a working selector set")
    return None
