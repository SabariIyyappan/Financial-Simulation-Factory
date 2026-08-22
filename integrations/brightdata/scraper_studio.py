"""
Bright Data Scraper Studio, driven from the terminal.

This is the data pipeline the factory runs on. It wraps the `bdata` CLI so the
whole lifecycle - build, run, detect breakage, heal, approve, re-run - happens
in the terminal without visiting the dashboard.

The self-healing here is Bright Data's own: `bdata scraper heal` sends the
collector's code and a description of what broke to Bright Data's AI, which
rewrites the extraction logic and keeps the same collector id. Every trigger and
integration referencing that id keeps working.
"""

import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Fields the factory requires from the provider docs. A collector that returns a
# record missing any of these has gone stale and needs healing.
REQUIRED_FIELDS = [
    "provider_name",
    "api_version",
    "migration_guidance",
    "changelog_date",
    "field_mappings",
]


class ScraperStudioError(RuntimeError):
    """A bdata CLI invocation failed."""


def _decode_balanced(text: str, start: int, opener: str, closer: str) -> Any:
    """
    Decode the JSON value beginning at `start`, if it is well formed.

    Brackets inside string literals are skipped so a value like
    {"note": "has ] bracket"} does not terminate the scan early.
    """
    depth, in_string, escaped = 0, False, False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:index + 1])
                except json.JSONDecodeError:
                    return None
            if depth < 0:
                return None

    return None


@dataclass
class HealthReport:
    """Whether the collector's output still satisfies the factory's contract."""

    healthy: bool
    missing_fields: List[str]
    record: Optional[Dict[str, Any]]
    raw_output: str = ""

    def describe(self) -> str:
        if self.healthy:
            return "all required fields present"
        return f"missing/null: {', '.join(self.missing_fields)}"


class ScraperStudioClient:
    """
    Terminal-driven client for a Scraper Studio collector.

    Args:
        collector_id: The `c_*` id returned by `bdata scraper create`.
        api_key: Bright Data API key; falls back to BRIGHTDATA_API_TOKEN.
        timeout: Seconds to allow each CLI call.
    """

    def __init__(
        self,
        collector_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 900,
    ):
        self.collector_id = collector_id or os.getenv("BRIGHTDATA_COLLECTOR_ID", "")
        self.api_key = api_key or os.getenv("BRIGHTDATA_API_TOKEN", "")
        self.timeout = timeout

        if not self.api_key:
            raise ScraperStudioError("BRIGHTDATA_API_TOKEN is not set")

    # -- CLI plumbing ------------------------------------------------------

    def _bdata(self, *args: str, timeout: Optional[int] = None) -> str:
        """
        Invoke the bdata CLI.

        Uses `npx -y -p @brightdata/cli` so there is nothing to install and the
        pipeline is reproducible from a clean checkout.
        """
        npx = shutil.which("npx") or shutil.which("npx.cmd")
        if npx is None:
            raise ScraperStudioError("npx not found - Node.js is required")

        command = [
            npx, "-y", "-p", "@brightdata/cli", "bdata",
            *args,
            "-k", self.api_key,
        ]

        printable = " ".join(a for a in args)
        logger.info(f"$ bdata {printable}")

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired as e:
            raise ScraperStudioError(f"bdata {printable} timed out") from e

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise ScraperStudioError(
                f"bdata {printable} failed ({completed.returncode}): {detail[:400]}"
            )

        return completed.stdout

    @staticmethod
    def _parse_records(output: str) -> List[Dict[str, Any]]:
        """
        Pull JSON records out of CLI output.

        The CLI interleaves progress lines with the payload, so scan for the
        first balanced JSON array or object rather than parsing the whole blob.
        """
        # Scan left to right over both bracket types together. Taking the
        # earliest opener matters: a nested array inside the payload object
        # would otherwise be returned instead of the object itself.
        pairs = {"[": "]", "{": "}"}
        index = 0

        while index < len(output):
            char = output[index]
            if char in pairs:
                parsed = _decode_balanced(output, index, char, pairs[char])
                if isinstance(parsed, list) and any(
                    isinstance(r, dict) for r in parsed
                ):
                    return [r for r in parsed if isinstance(r, dict)]
                if isinstance(parsed, dict):
                    return [parsed]
            index += 1

        return []

    # -- Lifecycle ---------------------------------------------------------

    def create(self, url: str, description: str, name: str) -> str:
        """
        Build a new collector with Bright Data's AI and return its id.

        This is the only step that is slow (minutes) - it runs Bright Data's
        multi-stage build pipeline.
        """
        output = self._bdata(
            "scraper", "create", url, description, "--name", name,
            "--timeout", str(self.timeout),
        )

        for token in output.replace('"', " ").replace("'", " ").split():
            if token.startswith("c_"):
                self.collector_id = token.strip(".,)")
                logger.info(f"Collector created: {self.collector_id}")
                return self.collector_id

        raise ScraperStudioError(f"No collector id in output: {output[-400:]}")

    def run(self, url: str) -> List[Dict[str, Any]]:
        """Run the collector against a URL and return its records."""
        if not self.collector_id:
            raise ScraperStudioError("No collector id configured")

        output = self._bdata("scraper", "run", self.collector_id, url, "--pretty")
        records = self._parse_records(output)

        if not records:
            logger.warning("Collector returned no records")

        return records

    def check_health(self, url: str) -> HealthReport:
        """
        Run the collector and report whether its output still satisfies the
        factory's required-field contract.

        A stale collector typically returns a record with null or missing
        fields rather than an error, so this is what detects a site redesign.
        """
        try:
            records = self.run(url)
        except ScraperStudioError as e:
            logger.error(f"Collector run failed: {e}")
            return HealthReport(False, list(REQUIRED_FIELDS), None, str(e))

        if not records:
            return HealthReport(False, list(REQUIRED_FIELDS), None)

        record = records[0]
        missing = [
            field for field in REQUIRED_FIELDS
            if not record.get(field)
        ]

        if missing:
            logger.warning(
                "Collector output degraded - missing/null: %s", ", ".join(missing)
            )

        return HealthReport(not missing, missing, record)

    # -- Healing -----------------------------------------------------------
    #
    # Driven over the REST API rather than `bdata scraper heal`. The CLI's
    # --auto-approve does not reliably catch the automation's `pending_answer`
    # window, so the repaired code passes validation and is then discarded -
    # the run reports success while the collector keeps its old selectors.
    # Polling for that window and posting resume_automation_job is what makes
    # the fix persist.

    def _api(self, method: str, path: str, **kwargs) -> requests.Response:
        return requests.request(
            method,
            f"https://api.brightdata.com/dca/collectors/{self.collector_id}{path}",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=kwargs.pop("timeout", 60),
            **kwargs,
        )

    def heal(self, url: str, description: str, auto_approve: bool = True) -> bool:
        """
        Ask Bright Data's AI to repair the collector in place.

        The collector id is preserved, so every trigger and integration
        referencing it keeps working.

        Args:
            url: The page whose structure changed (must be serving the new
                 markup - the AI inspects it live).
            description: What broke, in plain language (kept under 1000 chars).
            auto_approve: Commit the AI's fix as soon as it awaits approval.
        """
        if not self.collector_id:
            raise ScraperStudioError("No collector id configured")

        logger.info(f"Healing {self.collector_id}: {description[:120]}")

        started = self._api(
            "POST", "/refactor_template", json={"prompt": description[:990]}
        )
        if not started.ok:
            logger.error(f"Could not start heal: {started.status_code} {started.text[:200]}")
            return False

        return self._await_heal(auto_approve=auto_approve)

    def _await_heal(self, auto_approve: bool, timeout: int = 900) -> bool:
        """
        Follow the heal to completion, approving it when it asks.

        The approval step appears as status `pending_answer`; the repaired code
        is only written to the collector once resume_automation_job accepts it.
        """
        deadline = time.time() + timeout
        approved = False
        last_step = None

        while time.time() < deadline:
            progress = self._api("GET", "/refactor_template/progress", timeout=30)
            if not progress.ok:
                logger.error(f"Heal progress unavailable: {progress.status_code}")
                return False

            state = progress.json()
            step, status = state.get("step"), state.get("status")

            if step != last_step:
                logger.info(f"  heal: {step} ({status})")
                last_step = step

            if status == "pending_answer" and auto_approve and not approved:
                resumed = self._api(
                    "POST",
                    "/resume_automation_job",
                    json={"message": True, "auto_save": True},
                )
                if not resumed.ok:
                    logger.error(
                        f"Could not commit the repaired code: "
                        f"{resumed.status_code} {resumed.text[:200]}"
                    )
                    return False
                logger.info("  heal: repaired code committed")
                approved = True

            if status in ("done", "failed", "error"):
                if not state.get("success"):
                    logger.error(f"Heal finished unsuccessfully: {status}")
                    return False
                if not approved and auto_approve:
                    # Finished without ever offering the approval window, which
                    # means nothing was written to the collector.
                    logger.error(
                        "Heal completed without an approval step - the fix was "
                        "not saved"
                    )
                    return False
                logger.info("Heal completed and saved")
                return True

            time.sleep(4)

        logger.error("Heal timed out")
        return False

    def approve(self, url: str, reject: bool = False) -> bool:
        """Approve (or reject) a heal that is awaiting a decision."""
        if not self.collector_id:
            raise ScraperStudioError("No collector id configured")

        args = ["scraper", "approve", self.collector_id]
        args += ["--reject"] if reject else ["--url", url]

        try:
            self._bdata(*args)
            return True
        except ScraperStudioError as e:
            logger.error(f"Approve failed: {e}")
            return False

    # -- The pipeline ------------------------------------------------------

    def to_migration_evidence(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reshape a collector record into the factory's evidence contract.

        The collector returns field moves as a list of {old_field, new_field}
        rows; the factory wants the price and currency moves named explicitly.
        """
        mappings = record.get("field_mappings") or []

        def mapping_for(needle: str) -> Dict[str, str]:
            for row in mappings:
                if needle in str(row.get("old_field", "")).lower():
                    return row
            return {}

        price = mapping_for("price")
        currency = mapping_for("currency")

        # The collector normalises the changelog date to ISO; keep just the day.
        changelog_date = str(record.get("changelog_date", ""))
        if "T" in changelog_date:
            changelog_date = changelog_date.split("T")[0]

        return {
            "provider_name": record.get("provider_name", ""),
            "version": record.get("api_version", ""),
            "breaking_change_summary": record.get("migration_guidance", ""),
            "old_field_price": price.get("old_field", ""),
            "new_field_price": price.get("new_field", ""),
            "old_field_currency": currency.get("old_field", ""),
            "new_field_currency": currency.get("new_field", ""),
            "migration_guidance": record.get("migration_guidance", ""),
            "changelog_date": changelog_date,
            "extraction_successful": True,
            "missing_fields": [],
            "selectors_used": f"scraper-studio:{self.collector_id}",
        }

    def extract_with_self_healing(
        self, url: str, auto_approve: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Run the collector; if its output has degraded, heal and re-run.

        Returns the validated record, or None if healing could not recover it.
        A broken pipeline yields no data rather than stale or partial data.
        """
        health = self.check_health(url)

        if health.healthy:
            logger.info("Collector healthy - evidence extracted")
            return health.record

        logger.warning(f"Collector degraded ({health.describe()}) - healing")

        prompt = (
            f"The target site was redesigned and the scraper no longer returns "
            f"these fields: {', '.join(health.missing_fields)}. The page still "
            f"shows the same information - the HTML structure, class names and "
            f"nesting changed. Update the selectors to locate the fields in the "
            f"new markup."
        )

        if not self.heal(url, prompt, auto_approve=auto_approve):
            return None

        recovered = self.check_health(url)
        if not recovered.healthy:
            logger.error(
                f"Still degraded after healing ({recovered.describe()})"
            )
            return None

        logger.info("Self-healing recovered the pipeline")
        return recovered.record
