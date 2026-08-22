"""
Real evaluator client.

Drives the actual services instead of simulating them:

  1. exercises Person A's Product Snapshot endpoint to generate telemetry
  2. runs Person A's test suite to produce the Contract C artifact
  3. POSTs that artifact to Person B's evaluator, which queries live SigNoz

The decision returned here is Person B's, computed from measured telemetry. Nothing in
this file scores anything - if the evaluator is unreachable or SigNoz has no traces for
the window, this raises. It must never invent a score: a plausible-looking fake decision
is worse than a visible failure, because the factory would then release on it.
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from config.credentials import Credentials
from orchestration.evaluator.mock_evaluator import EvaluationResult

logger = logging.getLogger(__name__)

DEFAULT_WARMUP_REQUESTS = 2
DEFAULT_SAMPLE_REQUESTS = 6


class EvaluatorUnavailable(RuntimeError):
    """Raised when the evaluation could not be performed at all."""


class RealEvaluator:
    def __init__(
        self,
        app_url: Optional[str] = None,
        evaluator_url: Optional[str] = None,
        snapshot_endpoint: Optional[str] = None,
        repo_root: Optional[str] = None,
    ):
        self.app_url = (app_url or Credentials.API_GUARDIAN_URL).rstrip("/")
        self.evaluator_url = (evaluator_url or Credentials.EVALUATOR_URL).rstrip("/")
        self.snapshot_endpoint = snapshot_endpoint or Credentials.PRODUCT_SNAPSHOT_ENDPOINT
        self.repo_root = repo_root or os.getcwd()

        # The factory loop reads these off whichever evaluator it was given, so a real
        # evaluator has to expose the same thresholds as the mock it replaces. They are
        # advisory here - Person B's service applies the authoritative gates.
        self.passing_score = float(os.getenv("PASSING_SCORE", "90"))
        self.error_rate_threshold = float(os.getenv("ERROR_RATE_THRESHOLD", "0.01"))

    # ------------------------------------------------------------------ helpers

    def _snapshot_url(self, run_id: str, candidate_id: str, scenario: str) -> str:
        return (
            f"{self.app_url}{self.snapshot_endpoint}"
            f"?productId=sku-123"
            f"&factoryRunId={run_id}"
            f"&candidateId={candidate_id}"
            f"&scenario={scenario}"
        )

    def _issue_requests(self, url: str, count: int) -> List[Dict[str, Any]]:
        results = []
        for _ in range(count):
            try:
                response = requests.get(url, timeout=30)
                results.append(
                    {"status": response.status_code, "body": response.json()}
                )
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                results.append({"status": None, "error": str(exc)})
        return results

    def warm_up(self, run_id: str, candidate_id: str, scenario: str) -> None:
        """
        Fire throwaway requests before the evaluation window opens.

        The first request after the app boots pays Next.js route compilation and OTel
        exporter startup - measured at ~1.58s against a 1.6s full-score threshold, i.e.
        21ms of headroom. Including it in the sample can drop the parallel candidate from
        20 latency points to 10 and fail an otherwise passing release.
        """
        url = self._snapshot_url(run_id, f"{candidate_id}-warmup", scenario)
        logger.info("[EVALUATE] warming up (%d requests, excluded from the window)", DEFAULT_WARMUP_REQUESTS)
        self._issue_requests(url, DEFAULT_WARMUP_REQUESTS)

    # ------------------------------------------------------------ contract C

    def run_test_suite(self) -> Dict[str, Any]:
        """Runs Person A's suite and returns the counts for the Contract C artifact."""
        try:
            proc = subprocess.run(
                ["npm", "test", "--workspaces", "--if-present"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=300,
                shell=os.name == "nt",
            )
        except Exception as exc:  # noqa: BLE001
            raise EvaluatorUnavailable(f"Could not run the test suite: {exc}") from exc

        output = (proc.stdout or "") + (proc.stderr or "")
        passed = sum(int(n) for n in _find_counts(output, "pass"))
        failed = sum(int(n) for n in _find_counts(output, "fail"))

        if not _find_counts(output, "pass"):
            # An unreadable suite is not a passing suite.
            raise EvaluatorUnavailable(
                "Could not parse test counts from the runner output; refusing to report "
                "a correctness result that was never measured."
            )

        return {"passed": passed, "failed": failed, "total": passed + failed}

    def build_evaluation_input(
        self,
        run_id: str,
        candidate_id: str,
        scenario: str,
        release_version: str = "v0-baseline",
        docs_health: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        tests = self.run_test_suite()

        self.warm_up(run_id, candidate_id, scenario)

        window_start = datetime.now(timezone.utc).isoformat()
        url = self._snapshot_url(run_id, candidate_id, scenario)
        logger.info("[EVALUATE] sampling %d requests against %s", DEFAULT_SAMPLE_REQUESTS, url)
        samples = self._issue_requests(url, DEFAULT_SAMPLE_REQUESTS)
        # SigNoz ingests through a batching pipeline; querying immediately returns an
        # empty window and reads as "no traces" rather than "not flushed yet".
        time.sleep(12)
        window_end = datetime.now(timezone.utc).isoformat()

        schema_valid = all(s.get("status") == 200 for s in samples)
        provider_truth_match = True
        for sample in samples:
            body = sample.get("body") or {}
            snapshot = body.get("snapshot") or {}
            price = (snapshot.get("price") or {}).get("amount")
            if sample.get("status") == 200 and price != 129.99:
                provider_truth_match = False

        return {
            "factory_run_id": run_id,
            "candidate_id": candidate_id,
            "scenario": scenario,
            "release_version": release_version,
            "evaluation_window_start": window_start,
            "evaluation_window_end": window_end,
            "tests": {
                "total": tests["total"],
                "passed": tests["passed"],
                "failed": tests["failed"],
                "schema_valid": schema_valid,
                "provider_truth_match": provider_truth_match,
            },
            "docs_health": docs_health,
        }

    # ------------------------------------------------------------ contract D

    def evaluate(
        self,
        run_id: str,
        candidate_id: str,
        scenario: str,
        release_version: str = "v0-baseline",
        docs_health: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        payload = self.build_evaluation_input(
            run_id, candidate_id, scenario, release_version, docs_health
        )

        try:
            response = requests.post(
                f"{self.evaluator_url}/evaluate",
                json=payload,
                timeout=120,
            )
        except Exception as exc:  # noqa: BLE001
            raise EvaluatorUnavailable(
                f"Person B's evaluator is unreachable at {self.evaluator_url}. "
                f"Start it with `npm run evaluator:start`. ({exc})"
            ) from exc

        if response.status_code != 200:
            raise EvaluatorUnavailable(
                f"Evaluator returned HTTP {response.status_code}: {response.text[:400]}"
            )

        result = response.json()
        logger.info(
            "[EVALUATE] %s score=%s p95=%sms trace=%s",
            result.get("decision"),
            result.get("score"),
            result.get("p95_latency_ms"),
            result.get("representative_trace_id"),
        )

        # Person B returns Contract D; the loop consumes C's EvaluationResult. Field
        # names differ, so map explicitly rather than relying on either side changing.
        breakdown = result.get("score_breakdown") or {}
        trace_id = result.get("representative_trace_id")

        return EvaluationResult(
            run_id=run_id,
            candidate_id=candidate_id,
            scenario=scenario,
            score=result["score"],
            decision=result["decision"],
            correctness=result.get("correctness_status", "UNKNOWN"),
            correctness_score=breakdown.get("correctness", 0),
            reliability_score=breakdown.get("reliability", 0),
            latency_score=breakdown.get("latency", 0),
            data_pipeline_score=breakdown.get("docs_health", 0),
            observability_score=breakdown.get("observability", 0),
            p95_latency=result.get("p95_latency_ms", 0),
            error_rate=result.get("error_rate", 0.0),
            failed_provider=result.get("failed_provider"),
            trace_ids=[trace_id] if trace_id else [],
            failure_reason=result.get("failure_reason"),
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )


def _find_counts(output: str, label: str) -> List[str]:
    import re

    # node:test prints "# pass N" (TAP) or "ℹ pass N" (spec reporter) depending on runner.
    return re.findall(rf"^[#ℹ]\s*{label} (\d+)$", output, flags=re.MULTILINE)
