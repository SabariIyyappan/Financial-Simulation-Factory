#!/usr/bin/env python
"""
Phase C8 demo: break the docs layout and let the scraper heal itself.

Runs the five beats the plan calls for:

  1. extract successfully against docs-layout-v1
  2. switch the site to docs-layout-v2 (same visible text, new DOM)
  3. re-run the saved scraper - required fields go missing
  4. invoke Bright Data Self-Healing
  5. re-run and revalidate - evidence recovers

The scraper is never edited by hand between steps, which is the point of the
demonstration.

Usage:
    python demo/scripts/run_docs_selfheal.py
    python demo/scripts/run_docs_selfheal.py --keep-v2   # leave site broken
"""

import argparse
import logging
import os
import sys

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from integrations.brightdata.client import BrightDataClient  # noqa: E402


def banner(step: str, title: str) -> None:
    print()
    print("=" * 78)
    print(f"  STEP {step}  -  {title}")
    print("=" * 78)


def switch_layout(base_url: str, version: str) -> None:
    response = requests.post(
        f"{base_url}/api/docs/layout", params={"version": version}, timeout=10
    )
    response.raise_for_status()
    print(f"  docs site now serving {version}")


def describe(evidence) -> None:
    print(f"    provider        : {evidence.provider}")
    print(f"    version         : {evidence.version}")
    print(f"    price field     : {evidence.old_field_price} -> {evidence.new_field_price}")
    print(f"    currency field  : {evidence.old_field_currency} -> {evidence.new_field_currency}")
    print(f"    changelog date  : {evidence.changelog_date}")
    print(f"    selectors used  : {evidence.selectors_used}")
    print(f"    self-healed     : {evidence.self_heal_attempted}")


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-v2",
        action="store_true",
        help="Leave the docs site on layout v2 instead of resetting to v1",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    # Layout switching is a local control; scraping goes through the public
    # tunnel URL so Bright Data's cloud can actually reach the page.
    base_url = os.getenv("DOCS_SITE_URL", "http://localhost:8001")
    public_url = os.getenv("DOCS_PUBLIC_URL", "").rstrip("/") or base_url
    docs_url = f"{public_url}/api/docs/pricing"

    if public_url != base_url:
        print(f"  scraping via public URL : {public_url}")
        print(f"  layout control via      : {base_url}")

    try:
        requests.get(f"{base_url}/health", timeout=5).raise_for_status()
    except Exception:
        print(f"docs site is not reachable at {base_url}")
        print("start it first:  python provider-docs-site/server.py")
        return 1

    client = BrightDataClient()

    # ---- Step 1 ------------------------------------------------------------
    banner("1", "Extract migration evidence from docs-layout-v1")
    switch_layout(base_url, "v1")
    baseline = client.extract_and_validate(docs_url)
    if baseline is None:
        print("  FAILED - could not extract evidence from the original layout")
        return 1
    print("  extraction OK")
    describe(baseline)

    # ---- Step 2 ------------------------------------------------------------
    banner("2", "Provider redesigns their docs (switch to docs-layout-v2)")
    switch_layout(base_url, "v2")
    print("  human-visible content is unchanged; the DOM is not")

    # ---- Step 3 ------------------------------------------------------------
    banner("3", "Re-run the saved scraper - it no longer matches the page")
    health = client.get_scraper_health(docs_url)
    print(f"  scraper health  : {health['status']}")
    print(f"  selectors       : {health['selectors']}")
    print(f"  missing fields  : {', '.join(health['missing_fields'])}")
    print(f"  field mappings  : {health['field_mappings_found']} found")

    if health["status"] != "degraded":
        print("  UNEXPECTED - the layout switch did not break extraction")
        return 1

    # ---- Steps 4 and 5 -----------------------------------------------------
    banner("4+5", "Bright Data Self-Healing, then re-extract and revalidate")
    recovered = client.extract_and_validate(docs_url, retry_with_self_heal=True)
    if recovered is None:
        print("  FAILED - self-healing did not recover extraction")
        return 1

    print("  evidence recovered without editing the scraper by hand")
    describe(recovered)

    # ---- Result ------------------------------------------------------------
    banner("=", "Result")
    same = (
        baseline.old_field_price == recovered.old_field_price
        and baseline.new_field_price == recovered.new_field_price
        and baseline.old_field_currency == recovered.old_field_currency
        and baseline.new_field_currency == recovered.new_field_currency
    )
    print(f"  selectors changed : {baseline.selectors_used} -> {recovered.selectors_used}")
    print(f"  evidence matches  : {same}")
    print()
    print("  The provider changed their documentation's structure and the data")
    print("  acquisition layer recovered on its own.")
    print()

    if not args.keep_v2:
        switch_layout(base_url, "v1")

    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
