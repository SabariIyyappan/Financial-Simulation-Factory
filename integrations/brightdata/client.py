"""
Bright Data Scraper Client for API Guardian

Handles:
- Scraper execution via Bright Data API
- Evidence normalization
- Self-healing trigger
- Validation
"""

import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator
import requests
import time

from integrations.brightdata.extractor import (
    SELECTORS_V1,
    SelectorSet,
    extract_with_selectors,
    rediscover_selectors,
)

logger = logging.getLogger(__name__)


def utc_now() -> str:
    """Current UTC time as an RFC 3339 timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MigrationEvidence(BaseModel):
    """Normalized migration evidence from provider docs"""
    
    provider: str = Field(..., description="Provider name (e.g., 'Pricing API')")
    version: str = Field(..., description="Current API version")
    breaking_change_summary: str = Field(..., description="Summary of breaking changes")
    old_field_price: str = Field(..., description="Old price field path")
    new_field_price: str = Field(..., description="New price field path")
    old_field_currency: str = Field(..., description="Old currency field path")
    new_field_currency: str = Field(..., description="New currency field path")
    migration_guidance: str = Field(..., description="Migration instructions")
    changelog_date: str = Field(..., description="Changelog date")
    source_timestamp: str = Field(default_factory=utc_now)
    scraper_health: str = Field(default="healthy", description="Scraper health status")
    self_heal_attempted: bool = Field(default=False, description="Whether self-healing was attempted")
    selectors_used: str = Field(default="", description="Selector set that produced this evidence")

    @field_validator('version')
    @classmethod
    def validate_version(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Version cannot be empty")
        return v

    @field_validator('old_field_price', 'new_field_price', 'old_field_currency', 'new_field_currency')
    @classmethod
    def validate_field_paths(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Field path cannot be empty")
        return v


class BrightDataClient:
    """Client for Bright Data Scraper Studio API"""
    
    def __init__(
        self,
        api_token: Optional[str] = None,
        scraper_id: Optional[str] = None,
        api_url: Optional[str] = None
    ):
        self.api_token = api_token or os.getenv("BRIGHTDATA_API_TOKEN")
        self.scraper_id = scraper_id or os.getenv("BRIGHTDATA_SCRAPER_ID")
        self.api_url = api_url or os.getenv(
            "BRIGHTDATA_API_URL",
            "https://api.brightdata.com"
        )
        self.zone = os.getenv("BRIGHTDATA_ZONE", "")

        # Hosted retrieval needs a token and a Web Unlocker zone. The Scraper
        # Studio collector id is optional: the zone is what carries the request,
        # and the selector sets below are what turn the page into evidence.
        self.mock_mode = not (self.api_token and self.zone)

        # A real Scraper Studio collector takes priority when one is configured.
        # Its id is a dataset id (gd_...); the placeholder means none exists yet.
        self.use_hosted_collector = bool(
            self.api_token
            and self.scraper_id
            and not self.scraper_id.startswith("your_")
        )

        if self.use_hosted_collector:
            logger.info(
                f"Bright Data Scraper Studio collector {self.scraper_id} configured"
            )
        elif self.mock_mode:
            logger.info(
                "Bright Data zone not configured - fetching pages directly and "
                "applying the same selector sets locally"
            )
        else:
            logger.info(
                f"Bright Data hosted retrieval enabled via zone '{self.zone}'"
            )

        # The selector set the collector is currently configured with. Starting
        # from V1 is what lets a layout change break extraction for real.
        self.selectors: SelectorSet = SELECTORS_V1

        self.session = requests.Session()
        if self.api_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            })
    
    def extract_pricing_docs(
        self,
        url: str,
        wait_for_completion: bool = True,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Run Bright Data scraper on the pricing docs URL
        
        Args:
            url: Target URL to scrape
            wait_for_completion: Whether to wait for scraper to finish
            timeout: Maximum wait time in seconds
            
        Returns:
            Raw scraper results
        """
        if self.use_hosted_collector:
            hosted = self._run_hosted_collector(url, timeout=timeout)
            if hosted is not None:
                return hosted
            logger.warning(
                "Hosted collector returned no usable record - falling back to "
                "local selector extraction"
            )

        html = self._fetch_html(url, timeout=timeout)
        result = extract_with_selectors(html, self.selectors)

        if not result.ok:
            logger.warning(
                "Extraction incomplete using %s selectors - missing: %s",
                self.selectors.version,
                ", ".join(result.missing),
            )

        return result.as_raw_data()

    def _run_hosted_collector(
        self, url: str, timeout: int = 120
    ) -> Optional[Dict[str, Any]]:
        """
        Trigger the Scraper Studio collector and wait for its record.

        Returns None if the collector cannot be run or produced nothing, so the
        caller can fall back rather than crashing mid-demo.
        """
        logger.info(
            f"Triggering Scraper Studio collector {self.scraper_id} for {url}"
        )

        try:
            response = self.session.post(
                f"{self.api_url}/datasets/v3/trigger",
                params={"dataset_id": self.scraper_id, "include_errors": "true"},
                json=[{"url": url}],
                timeout=60,
            )
            response.raise_for_status()
            snapshot_id = response.json().get("snapshot_id")
        except Exception as e:
            logger.error(f"Could not trigger collector: {e}")
            return None

        if not snapshot_id:
            logger.error("Collector trigger returned no snapshot id")
            return None

        record = self._await_snapshot(snapshot_id, timeout=timeout)
        if record is None:
            return None

        return self._normalize_collector_record(record)

    def _await_snapshot(
        self, snapshot_id: str, timeout: int = 120
    ) -> Optional[Dict[str, Any]]:
        """Poll a collector run until its snapshot is ready."""
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                response = self.session.get(
                    f"{self.api_url}/datasets/v3/snapshot/{snapshot_id}",
                    params={"format": "json"},
                    timeout=30,
                )
            except Exception as e:
                logger.error(f"Snapshot poll failed: {e}")
                return None

            # 202 means the run is still building the snapshot.
            if response.status_code == 202:
                time.sleep(3)
                continue

            if not response.ok:
                logger.error(
                    f"Snapshot {snapshot_id} failed: "
                    f"{response.status_code} {response.text[:200]}"
                )
                return None

            rows = response.json()
            if isinstance(rows, dict):
                rows = rows.get("data", [])
            if not rows:
                logger.warning(f"Snapshot {snapshot_id} came back empty")
                return None

            return rows[0]

        logger.error(f"Collector run timed out after {timeout}s")
        return None

    def _normalize_collector_record(
        self, record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Shape a Scraper Studio record like a local extraction result.

        A collector whose selectors have gone stale returns a record with empty
        or missing fields rather than an error, so the same required-field check
        applies here as to local extraction.
        """
        mappings = record.get("field_mappings") or []

        def mapping_for(needle: str) -> Dict[str, str]:
            for row in mappings:
                if needle in str(row.get("old", "")).lower():
                    return row
            return {}

        price = mapping_for("price")
        currency = mapping_for("currency")

        raw = {
            "provider_name": record.get("provider_name", ""),
            "version": record.get("api_version", ""),
            "breaking_change_summary": record.get("migration_guidance", ""),
            "old_field_price": price.get("old", ""),
            "new_field_price": price.get("new", ""),
            "old_field_currency": currency.get("old", ""),
            "new_field_currency": currency.get("new", ""),
            "migration_guidance": record.get("migration_guidance", ""),
            "changelog_date": record.get("changelog_date", ""),
            "selectors_used": f"scraper-studio:{self.scraper_id}",
        }

        missing = [
            name
            for name in ("provider_name", "version", "migration_guidance",
                         "changelog_date")
            if not raw[name]
        ]
        if not price or not currency:
            missing.append("field_mappings")

        raw["missing_fields"] = missing
        raw["extraction_successful"] = not missing

        if missing:
            logger.warning(
                "Hosted collector record incomplete - missing: %s",
                ", ".join(missing),
            )

        return raw

    def _fetch_html(self, url: str, timeout: int = 60) -> str:
        """
        Retrieve the page HTML.

        When a Scraper Studio collector and zone are configured, the fetch goes
        through Bright Data's Web Unlocker so the request carries the same
        network path the hosted collector would use. Otherwise the page is
        fetched directly - the selectors applied afterwards are identical, so
        the failure and self-heal behaviour is the same either way.
        """
        if self.mock_mode:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text

        logger.info(f"Fetching {url} via Bright Data zone '{self.zone}'")
        response = self.session.post(
            f"{self.api_url}/request",
            json={"zone": self.zone, "url": url, "format": "raw"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.text
    
    def normalize_evidence(self, raw_data: Dict[str, Any]) -> MigrationEvidence:
        """
        Convert raw scraper output to normalized evidence object
        
        Args:
            raw_data: Raw data from Bright Data scraper
            
        Returns:
            Normalized MigrationEvidence object
        """
        try:
            evidence = MigrationEvidence(
                provider=raw_data.get("provider_name", "Unknown"),
                version=raw_data.get("version", "unknown"),
                breaking_change_summary=raw_data.get("breaking_change_summary", ""),
                old_field_price=raw_data.get("old_field_price", ""),
                new_field_price=raw_data.get("new_field_price", ""),
                old_field_currency=raw_data.get("old_field_currency", ""),
                new_field_currency=raw_data.get("new_field_currency", ""),
                migration_guidance=raw_data.get("migration_guidance", ""),
                changelog_date=raw_data.get("changelog_date", ""),
                scraper_health="healthy" if raw_data.get("extraction_successful") else "unhealthy",
                selectors_used=raw_data.get("selectors_used", "")
            )
            
            logger.info(f"Successfully normalized evidence for {evidence.provider} v{evidence.version}")
            return evidence
            
        except Exception as e:
            logger.error(f"Failed to normalize evidence: {e}")
            raise
    
    def validate_evidence(self, evidence: MigrationEvidence) -> bool:
        """
        Validate that evidence contains all required fields
        
        Args:
            evidence: MigrationEvidence object to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Pydantic validation happens automatically
            # Additional business logic validation
            
            if evidence.version == "unknown":
                logger.error("Evidence validation failed: version is unknown")
                return False
            
            if not evidence.old_field_price or not evidence.new_field_price:
                logger.error("Evidence validation failed: missing price field mappings")
                return False
            
            if not evidence.old_field_currency or not evidence.new_field_currency:
                logger.error("Evidence validation failed: missing currency field mappings")
                return False
            
            if not evidence.migration_guidance:
                logger.error("Evidence validation failed: missing migration guidance")
                return False
            
            logger.info("Evidence validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Evidence validation error: {e}")
            return False
    
    def trigger_self_healing(self, url: str) -> bool:
        """
        Repair the collector after its saved selectors stop matching the page.

        Bright Data Self-Healing re-derives working selectors from the changed
        page instead of a human rewriting the scraper. On success the client's
        selector set is replaced, so the next extraction uses the repaired
        configuration.

        Args:
            url: The docs URL whose layout changed

        Returns:
            True if a working selector set was found
        """
        logger.info(
            "Self-healing: %s selectors no longer match %s - re-deriving",
            self.selectors.version,
            url,
        )

        try:
            html = self._fetch_html(url)
        except Exception as e:
            logger.error(f"Self-healing could not retrieve the page: {e}")
            return False

        healed = rediscover_selectors(html)
        if healed is None:
            logger.error("Self-healing failed - no selector set matches the page")
            return False

        previous = self.selectors.version
        self.selectors = healed
        logger.info(
            "Self-healing repaired the collector: %s -> %s",
            previous,
            healed.version,
        )
        return True
    
    def get_scraper_health(self, url: str) -> Dict[str, Any]:
        """
        Report whether the current selector set still matches the live page.

        This is the data-quality signal the factory reacts to: a collector that
        returns a page but no longer finds the required fields is degraded, not
        healthy.

        Args:
            url: The docs URL to check

        Returns:
            Health status including which fields are missing, if any
        """
        try:
            html = self._fetch_html(url)
        except Exception as e:
            logger.error(f"Scraper health check could not reach {url}: {e}")
            return {
                "status": "unreachable",
                "selectors": self.selectors.version,
                "error": str(e),
                "checked_at": utc_now(),
            }

        result = extract_with_selectors(html, self.selectors)

        return {
            "status": "healthy" if result.ok else "degraded",
            "selectors": self.selectors.version,
            "missing_fields": result.missing,
            "field_mappings_found": len(result.field_pairs),
            "checked_at": utc_now(),
        }
    
    def extract_and_validate(
        self,
        url: str,
        retry_with_self_heal: bool = True
    ) -> Optional[MigrationEvidence]:
        """
        Complete workflow: extract, normalize, validate, and optionally self-heal
        
        Args:
            url: Target URL to scrape
            retry_with_self_heal: Whether to trigger self-healing on validation failure
            
        Returns:
            Validated MigrationEvidence or None if failed
        """
        self_healed = False

        try:
            raw_data = self.extract_pricing_docs(url)

            if not raw_data.get("extraction_successful", False):
                missing = ", ".join(raw_data.get("missing_fields", []))
                logger.warning(
                    "Extraction failed data-quality validation - missing: %s",
                    missing,
                )

                if not retry_with_self_heal:
                    return None

                if not self.trigger_self_healing(url):
                    logger.error("Self-healing failed - no evidence available")
                    return None

                self_healed = True

                logger.info("Re-running extraction with repaired selectors")
                raw_data = self.extract_pricing_docs(url)

                if not raw_data.get("extraction_successful", False):
                    logger.error("Extraction still failing after self-healing")
                    return None

            evidence = self.normalize_evidence(raw_data)
            evidence.self_heal_attempted = self_healed

            # Revalidate before the evidence reaches the repair workflow -
            # a healed scrape is not trusted until it passes the same gate.
            if not self.validate_evidence(evidence):
                logger.error("Evidence validation failed")
                return None

            return evidence

        except Exception as e:
            logger.error(f"Extract and validate workflow failed: {e}")
            return None
