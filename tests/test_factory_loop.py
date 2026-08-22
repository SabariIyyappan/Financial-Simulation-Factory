"""
Phase C2 regression tests for the factory workflow.

These cover the state machine, the decision gates, and the Port payload shapes
that broke during C2 (naive timestamps, missing score breakdown, query-string
search). They run offline - the Port client is faked - so they stay fast and
do not write demo entities into the live workspace.
"""

import sys
import os
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from integrations.port.client import utc_now  # noqa: E402
from orchestration.evaluator.mock_evaluator import MockEvaluator  # noqa: E402
from orchestration.factory.state_machine import (  # noqa: E402
    CandidateState,
    CandidateStateMachine,
    StateTransitionError,
)


class TestTimestamps:
    """Port's date-time format requires an explicit timezone offset."""

    def test_utc_now_is_timezone_aware(self):
        assert utc_now().endswith("Z")

    def test_utc_now_parses_as_rfc3339(self):
        parsed = datetime.fromisoformat(utc_now().replace("Z", "+00:00"))
        assert parsed.tzinfo is not None


class TestStateMachine:
    def test_happy_path_reaches_released(self):
        sm = CandidateStateMachine()
        for state in [
            CandidateState.INVESTIGATING,
            CandidateState.PLANNED,
            CandidateState.IMPLEMENTED,
            CandidateState.EVALUATING,
            CandidateState.READY_FOR_APPROVAL,
            CandidateState.APPROVED,
            CandidateState.RELEASED,
        ]:
            sm.transition_to(state)
        assert sm.get_state() == CandidateState.RELEASED
        assert sm.is_terminal()

    def test_fail_path_reaches_rejected(self):
        sm = CandidateStateMachine()
        for state in [
            CandidateState.INVESTIGATING,
            CandidateState.PLANNED,
            CandidateState.IMPLEMENTED,
            CandidateState.EVALUATING,
            CandidateState.REJECTED,
        ]:
            sm.transition_to(state)
        assert sm.get_state() == CandidateState.REJECTED
        assert sm.can_retry()

    def test_rejected_can_retry_via_planned(self):
        sm = CandidateStateMachine.from_state("REJECTED")
        sm.transition_to(CandidateState.PLANNED, "retry")
        assert sm.get_state() == CandidateState.PLANNED

    def test_illegal_transition_is_rejected(self):
        sm = CandidateStateMachine()
        with pytest.raises(StateTransitionError):
            sm.transition_to(CandidateState.RELEASED)

    def test_history_records_every_transition(self):
        sm = CandidateStateMachine()
        sm.transition_to(CandidateState.INVESTIGATING, "gathering")
        history = sm.get_history()
        assert [h["state"] for h in history] == ["DETECTED", "INVESTIGATING"]
        assert history[-1]["reason"] == "gathering"


class TestEvaluatorScenarios:
    """The mock evaluator is Person B's contract stand-in - shape matters."""

    @pytest.mark.parametrize(
        "scenario,decision,score",
        [
            ("baseline-v1", "FAIL", 80.0),
            ("optimized-v1", "PASS", 100.0),
            ("pricing-v2-break", "FAIL", 20.0),
            ("pricing-v2-repaired", "PASS", 100.0),
        ],
    )
    def test_scenario_verdicts(self, scenario, decision, score):
        result = MockEvaluator().evaluate("RUN-T", "CAND-T", scenario)
        assert result.decision == decision
        assert result.score == score

    def test_components_sum_to_total(self):
        result = MockEvaluator().evaluate("RUN-T", "CAND-T", "baseline-v1")
        total = (
            result.correctness_score
            + result.reliability_score
            + result.latency_score
            + result.data_pipeline_score
            + result.observability_score
        )
        assert total == result.score

    def test_baseline_fails_on_latency_only(self):
        """The demo story: correct but slow. Latency is the visible culprit."""
        result = MockEvaluator().evaluate("RUN-T", "CAND-T", "baseline-v1")
        assert result.correctness == "PASS"
        assert result.latency_score == 0.0
        assert result.correctness_score == 40.0

    def test_unknown_scenario_raises(self):
        with pytest.raises(ValueError):
            MockEvaluator().evaluate("RUN-T", "CAND-T", "no-such-scenario")


class FakePortClient:
    """Records calls instead of hitting Port."""

    def __init__(self):
        self.evaluations = []
        self.entities = {}

    def create_factory_run(self, run_id, service_id, scenario, trigger_reason, status="DETECTED"):
        self.entities[run_id] = {"status": status}
        return {}

    def update_factory_run_status(self, run_id, status, **kwargs):
        self.entities.setdefault(run_id, {})["status"] = status
        return {}

    def create_candidate(self, candidate_id, factory_run_id, hypothesis, **kwargs):
        self.entities[candidate_id] = {"hypothesis": hypothesis}
        return {}

    def update_candidate_status(self, candidate_id, status, **kwargs):
        self.entities.setdefault(candidate_id, {})["status"] = status
        return {}

    def create_evaluation(self, **kwargs):
        self.evaluations.append(kwargs)
        return {}

    def create_release(self, **kwargs):
        self.entities[kwargs["version"]] = kwargs
        return {}

    def update_entity(self, blueprint, identifier, properties=None, relations=None):
        self.entities.setdefault(identifier, {}).update(properties or {})
        return {}

    def get_entity(self, blueprint, identifier):
        return {"entity": {"properties": {}, "relations": {}}}

    def find_candidates_for_run(self, factory_run_id):
        return []


class TestFactoryLoopPortPayloads:
    """Guard the payloads the loop sends to Port."""

    def _loop(self, port):
        from orchestration.factory.loop import FactoryLoop

        class FakeBrightData:
            def extract_and_validate(self, url, retry_with_self_heal=True):
                return None

        return FactoryLoop(
            port_client=port,
            brightdata_client=FakeBrightData(),
            evaluator=MockEvaluator(),
        )

    def test_fail_run_records_score_breakdown(self):
        port = FakePortClient()
        result = self._loop(port).run_factory_loop("RUN-T-FAIL", scenario="baseline-v1")

        assert result["final_state"] == "REJECTED"
        assert len(port.evaluations) == 1

        # Without the breakdown, a judge cannot see *why* the score was 80.
        evaluation = port.evaluations[0]
        assert evaluation["latency_score"] == 0.0
        assert evaluation["correctness_score"] == 40.0
        assert evaluation["reliability_score"] == 20.0

    def test_pass_run_reaches_release(self):
        port = FakePortClient()
        os.environ["AUTO_APPROVE"] = "true"
        try:
            result = self._loop(port).run_factory_loop(
                "RUN-T-PASS", scenario="optimized-v1"
            )
        finally:
            os.environ.pop("AUTO_APPROVE", None)

        assert result["success"] is True
        assert result["final_state"] == "RELEASED"
        assert result["score"] == 100.0

    def test_correctness_failure_rejects_before_score(self):
        """Correctness is a hard gate - a break must reject on correctness."""
        port = FakePortClient()
        result = self._loop(port).run_factory_loop(
            "RUN-T-BREAK", scenario="pricing-v2-break"
        )
        assert result["final_state"] == "REJECTED"
        assert result["score"] == 20.0
        assert port.evaluations[0]["correctness"] == "FAIL"
        assert port.evaluations[0]["correctness_score"] == 0.0
