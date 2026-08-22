#!/usr/bin/env python
"""
Run a factory loop scenario end-to-end against Port.

Usage:
    python demo/scripts/run_factory_loop.py baseline-v1
    python demo/scripts/run_factory_loop.py optimized-v1 --auto-approve
    python demo/scripts/run_factory_loop.py --both

Scenarios are idempotent - re-running the same one overwrites its entities in
Port rather than failing, so a beat can be replayed during a live demo.
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from orchestration.factory.loop import FactoryLoop  # noqa: E402

SCENARIOS = {
    "baseline-v1": ("RUN-DEMO-BASELINE", "Sequential provider calls - expect FAIL"),
    "optimized-v1": ("RUN-DEMO-OPTIMIZED", "Parallelized calls - expect PASS"),
    "pricing-v2-break": ("RUN-DEMO-PRICING-BREAK", "Pricing V2 schema break - expect FAIL"),
    "pricing-v2-repaired": ("RUN-DEMO-PRICING-FIX", "Pricing adapter repaired - expect PASS"),
}


def run(scenario: str, service_id: str = "api-guardian") -> dict:
    run_id, description = SCENARIOS[scenario]

    print()
    print("=" * 78)
    print(f"  {scenario}  -  {description}")
    print(f"  run id: {run_id}")
    print("=" * 78)

    result = FactoryLoop().run_factory_loop(
        factory_run_id=run_id,
        service_id=service_id,
        scenario=scenario,
    )

    state = result.get("final_state")
    score = result.get("score")

    print()
    if result.get("error"):
        print(f"  ERROR: {result['error']}")
    elif result.get("success"):
        release = result.get("release", {})
        print(f"  {state} - score {score}/100 - released {release.get('version')}")
        for improvement in release.get("improvements", []):
            print(f"    + {improvement}")
    else:
        print(f"  {state} - score {score}/100")
        print(f"    reason: {result.get('failure_reason')}")
    print()

    return result


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", choices=sorted(SCENARIOS))
    parser.add_argument(
        "--both",
        action="store_true",
        help="Run baseline-v1 (FAIL) then optimized-v1 (PASS)",
    )
    parser.add_argument("--auto-approve", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    if args.auto_approve:
        os.environ["AUTO_APPROVE"] = "true"

    if args.both:
        scenarios = ["baseline-v1", "optimized-v1"]
    elif args.scenario:
        scenarios = [args.scenario]
    else:
        parser.error("give a scenario or --both")

    results = [run(s) for s in scenarios]
    return 0 if all(r.get("error") is None for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
