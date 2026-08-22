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
from typing import Dict, Optional, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, validator
import requests
import time

logger = logging.getLogger(__name__)


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
    source_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    scraper_health: str = Field(default="healthy", description="Scraper health status")
    self_heal_attempted: bool = Field(default=False, description="Whether self-healing was attempted")
    
    @validator('version')
    def validate_version(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Version cannot be empty")
        return v
    
    @validator('old_field_price', 'new_field_price', 'old_field_currency', 'new_field_currency')
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
        
        if not self.api_token:
            logger.warning("Bright Data API token not provided - using mock mode")
            self.mock_mode = True
        else:
            self.mock_mode = False
        
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
        if self.mock_mode:
            logger.info(f"Mock mode: Simulating scrape of {url}")
            return self._mock_scrape(url)
        
        if not self.scraper_id:
            raise ValueError("Scraper ID not configured")
        
        logger.info(f"Starting Bright Data scraper for {url}")
        
        # Trigger scraper
        response = self.session.post(
            f"{self.api_url}/scrapers/{self.scraper_id}/runs",
            json={"url": url}
        )
        response.raise_for_status()
        
        run_id = response.json()["run_id"]
        logger.info(f"Scraper run started: {run_id}")
        
        if not wait_for_completion:
            return {"run_id": run_id, "status": "running"}
        
        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < timeout:
            status_response = self.session.get(
                f"{self.api_url}/scrapers/{self.scraper_id}/runs/{run_id}"
            )
            status_response.raise_for_status()
            
            status_data = status_response.json()
            status = status_data.get("status")
            
            if status == "completed":
                logger.info(f"Scraper run completed: {run_id}")
                return status_data.get("results", {})
            elif status == "failed":
                logger.error(f"Scraper run failed: {run_id}")
                raise Exception(f"Scraper failed: {status_data.get('error')}")
            
            time.sleep(2)
        
        raise TimeoutError(f"Scraper run timed out after {timeout}s")
    
    def _mock_scrape(self, url: str) -> Dict[str, Any]:
        """Mock scraper for development/testing"""
        # Simulate scraping the local docs site
        # In real implementation, this would be replaced by actual Bright Data results
        
        # Check if we can reach the URL
        try:
            response = requests.get(url, timeout=5)
            html_content = response.text
            
            # Simple extraction logic for demo purposes
            # In production, Bright Data handles this
            if "Layout V2" in html_content or "version-badge" in html_content:
                # V2 layout - different selectors
                layout_version = "v2"
            else:
                # V1 layout
                layout_version = "v1"
            
            # Extract data based on layout
            return {
                "provider_name": "Pricing API",
                "version": "v2",
                "breaking_change_summary": "Price and currency fields moved to nested pricing object",
                "old_field_price": "price",
                "new_field_price": "pricing.amount",
                "old_field_currency": "currency",
                "new_field_currency": "pricing.currency",
                "migration_guidance": "Update client code to access pricing.amount and pricing.currency instead of root-level fields",
                "changelog_date": "January 15, 2024",
                "layout_detected": layout_version,
                "extraction_successful": True
            }
        except Exception as e:
            logger.error(f"Mock scrape failed: {e}")
            return {
                "extraction_successful": False,
                "error": str(e)
            }
    
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
                scraper_health="healthy" if raw_data.get("extraction_successful") else "unhealthy"
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
    
    def trigger_self_healing(self, scraper_id: Optional[str] = None) -> bool:
        """
        Trigger Bright Data Self-Healing for the scraper
        
        Args:
            scraper_id: Optional scraper ID (uses default if not provided)
            
        Returns:
            True if self-healing was triggered successfully
        """
        scraper_id = scraper_id or self.scraper_id
        
        if self.mock_mode:
            logger.info(f"Mock mode: Simulating self-healing for scraper {scraper_id}")
            # In mock mode, just log and return success
            return True
        
        if not scraper_id:
            raise ValueError("Scraper ID not configured")
        
        logger.info(f"Triggering self-healing for scraper {scraper_id}")
        
        try:
            response = self.session.post(
                f"{self.api_url}/scrapers/{scraper_id}/self-heal"
            )
            response.raise_for_status()
            
            logger.info("Self-healing triggered successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to trigger self-healing: {e}")
            return False
    
    def get_scraper_health(self, scraper_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current health status of the scraper
        
        Args:
            scraper_id: Optional scraper ID (uses default if not provided)
            
        Returns:
            Health status information
        """
        scraper_id = scraper_id or self.scraper_id
        
        if self.mock_mode:
            return {
                "scraper_id": scraper_id,
                "status": "healthy",
                "last_successful_run": datetime.utcnow().isoformat(),
                "mock_mode": True
            }
        
        if not scraper_id:
            raise ValueError("Scraper ID not configured")
        
        try:
            response = self.session.get(
                f"{self.api_url}/scrapers/{scraper_id}/health"
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get scraper health: {e}")
            return {
                "scraper_id": scraper_id,
                "status": "unknown",
                "error": str(e)
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
        try:
            # Extract
            raw_data = self.extract_pricing_docs(url)
            
            # Check if extraction was successful
            if not raw_data.get("extraction_successful", False):
                logger.warning("Initial extraction failed")
                
                if retry_with_self_heal:
                    logger.info("Attempting self-healing...")
                    if self.trigger_self_healing():
                        # Wait a bit for self-healing to complete
                        time.sleep(5)
                        
                        # Retry extraction
                        logger.info("Retrying extraction after self-healing...")
                        raw_data = self.extract_pricing_docs(url)
                        
                        if not raw_data.get("extraction_successful", False):
                            logger.error("Extraction failed even after self-healing")
                            return None
                    else:
                        logger.error("Self-healing failed")
                        return None
                else:
                    return None
            
            # Normalize
            evidence = self.normalize_evidence(raw_data)
            
            # Mark if self-healing was used
            if retry_with_self_heal and not raw_data.get("extraction_successful", False):
                evidence.self_heal_attempted = True
            
            # Validate
            if not self.validate_evidence(evidence):
                logger.error("Evidence validation failed")
                return None
            
            return evidence
            
        except Exception as e:
            logger.error(f"Extract and validate workflow failed: {e}")
            return None
