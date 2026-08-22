#!/usr/bin/env python
"""
Bright Data Scraper Studio pipeline - build, break, detect, heal, recover.

Runs entirely from the terminal against a real Scraper Studio collector. The
collector is Bright Data's own AI-generated code; when the docs site changes its
HTML, the collector's output degrades and Bright Data's self-healing rewrites the
extraction logic in place, keeping the same collector id.

Usage:
    python demo/scripts/run_scraper_pipeline.py --status
    python demo/scripts/run_scraper_pipeline.py --switch v2
    python demo/scripts/run_scraper_pipeline.py            # full break/heal demo
    python demo/scripts/run_scraper_pipeline.py --create   # build a new collector

Requires DOCS_PUBLIC_URL (a tunnel to the local docs site) so Bright Data's
cloud can reach the page.
"""

import argparse
import json
import logging
import os
import sys

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from integrations.brightdata.scraper_studio import (  # noqa: E402
    ScraperStudioClient,
    ScraperStudioError,
)

EXTRACTION_SPEC = (
    "Extract the API migration guide: provider_name (page title), api_version, "
    "migration_guidance paragraph, changelog_date (the Released date of version "
    "2.0.0), and field_mappings as a list of old field path to new field path "
    "pairs shown with arrows (price to pricing.amount, currency to "
    "pricing.currency)"
)


def banner(title: str) -> None:
    print()
    print("=" * 78)
    print(f"  {title}")
    print("=" * 78)


def switch_layout(base_url: str, version: str) -> None:
    response = requests.post(
        f"{base_url}/api/docs/layout", params={"version": version}, timeout=10
    )
    response.raise_for_status()
    print(f"  docs site now serving layout {version}")


def show(record: dict) -> None:
    for key in (
        "provider_name", "api_version", "migration_guidance", "changelog_date"
    ):
        value = str(record.get(key) or "(missing)")
        if len(value) > 62:
            value = value[:59] + "..."
        print(f"    {key:20}: {value}")

    mappings = record.get("field_mappings") or []
    if mappings:
        for row in mappings:
            print(f"    {'field mapping':20}: {row.get('old_field')} -> {row.get('new_field')}")
    else:
        print(f"    {'field mappings':20}: (none found)")


def main() -> int:
    load_dotenv(override=True)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true",
                        help="Build a new collector and print its id")
    parser.add_argument("--status", action="store_true",
                        help="Report collector health without changing anything")
    parser.add_argument("--switch", choices=["v1", "v2"],
                        help="Only switch the docs layout, then exit")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    local_url = os.getenv("DOCS_SITE_URL", "http://localhost:8001")
    public_url = os.getenv("DOCS_PUBLIC_URL", "").rstrip("/")

    if not public_url:
        print("DOCS_PUBLIC_URL is not set.")
        print("Bright Data's cloud cannot reach localhost - start a tunnel:")
        print("  cloudflared tunnel --url http://localhost:8001")
        return 1

    docs_url = f"{public_url}/api/docs/pricing"

    try:
        requests.get(f"{local_url}/health", timeout=5).raise_for_status()
    except Exception:
        print(f"docs site unreachable at {local_url}")
        print("start it:  python provider-docs-site/server.py")
        return 1

    if args.switch:
        switch_layout(local_url, args.switch)
        return 0

    if args.create:
        banner("Building a new Scraper Studio collector")
        print("  this runs Bright Data's AI build pipeline (5-25 minutes)")
        client = ScraperStudioClient(collector_id="")
        collector_id = client.create(
            docs_url, EXTRACTION_SPEC, "api-guardian-pricing-docs"
        )
        print()
        print(f"  collector id: {collector_id}")
        print(f"  add to .env:  BRIGHTDATA_COLLECTOR_ID={collector_id}")
        return 0

    try:
        client = ScraperStudioClient()
    except ScraperStudioError as e:
        print(f"{e}")
        return 1

    if not client.collector_id:
        print("BRIGHTDATA_COLLECTOR_ID is not set - run with --create first")
        return 1

    print(f"collector: {client.collector_id}")

    if args.status:
        banner("Collector health")
        health = client.check_health(docs_url)
        print(f"  status: {'healthy' if health.healthy else 'degraded'}")
        print(f"  {health.describe()}")
        if health.record:
            show(health.record)
        return 0 if health.healthy else 2

    # ---- 1: baseline ----------------------------------------------------
    banner("STEP 1 - Collector is healthy against the current layout")
    health = client.check_health(docs_url)
    if not health.healthy:
        print(f"  collector is already degraded ({health.describe()})")
        print("  healing it first so the demo starts from a working state")
        if not client.heal(
            docs_url,
            "The scraper returns null or empty for "
            f"{', '.join(health.missing_fields)}. The page still shows all of "
            "that information under different markup. Update the selectors.",
        ):
            print("  could not restore the collector")
            return 1
        health = client.check_health(docs_url)
        if not health.healthy:
            print("  still degraded - stopping")
            return 1

    print("  extraction OK")
    show(health.record)

    # ---- 2: break -------------------------------------------------------
    current = requests.get(
        f"{local_url}/api/docs/layout/current", timeout=10
    ).json()["version"]
    broken = "v2" if current == "v1" else "v1"

    banner(f"STEP 2 - Provider redesigns their docs ({current} -> {broken})")
    switch_layout(local_url, broken)
    print("  the human-visible content is unchanged; the HTML structure is not")

    # ---- 3: detect ------------------------------------------------------
    banner("STEP 3 - The collector's output degrades")
    degraded = client.check_health(docs_url)
    print(f"  status: {'healthy' if degraded.healthy else 'degraded'}")
    print(f"  {degraded.describe()}")
    if degraded.record:
        show(degraded.record)

    if degraded.healthy:
        print("  UNEXPECTED - the redesign did not break extraction")
        return 1

    # ---- 4+5: heal and recover -----------------------------------------
    banner("STEP 4 - Bright Data self-healing rewrites the collector")
    print("  the collector id is preserved, so integrations keep working")

    recovered = client.extract_with_self_healing(docs_url)
    if recovered is None:
        print("  self-healing did not recover the pipeline")
        return 1

    banner("STEP 5 - Evidence recovered from the redesigned page")
    show(recovered)

    print()
    print("  normalized for the factory:")
    print(json.dumps(client.to_migration_evidence(recovered), indent=2))

    banner("Result")
    print("  The provider changed their documentation's HTML and the pipeline")
    print("  repaired itself. No selectors were edited by hand, and the")
    print(f"  collector id ({client.collector_id}) never changed.")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
