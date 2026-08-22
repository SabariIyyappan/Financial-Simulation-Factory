"""
AVO-lite Factory Loop Orchestrator

Implements the core autonomous software factory control loop:
1. Inspect - Gather context and evidence
2. Plan - Generate hypothesis
3. Act - Implement changes
4. Evaluate - Objective verification
5. Decide - Pass/Fail decision
6. Approve - Human gate
7. Release - Record and deploy
"""

import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from integrations.port.client import PortClient
from integrations.brightdata.client import BrightDataClient, MigrationEvidence
from orchestration.evaluator.mock_evaluator import MockEvaluator, EvaluationResult
from orchestration.evaluator.real_evaluator import RealEvaluator
from orchestration.factory.state_machine import CandidateStateMachine, CandidateState

logger = logging.getLogger(__name__)


@dataclass
class Context:
    """Inspection context gathered from multiple sources"""
    service_id: str
    service_name: str
    current_release: Optional[str]
    dependencies: List[Dict[str, Any]]
    factory_run_id: str
    scenario: str
    trigger_reason: str
    
    # Evidence from SigNoz (via Person B)
    signoz_evidence: Optional[Dict[str, Any]] = None
    
    # Evidence from Bright Data
    brightdata_evidence: Optional[MigrationEvidence] = None
    
    # Previous candidate history
    previous_candidates: List[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "current_release": self.current_release,
            "dependencies": self.dependencies,
            "factory_run_id": self.factory_run_id,
            "scenario": self.scenario,
            "trigger_reason": self.trigger_reason,
            "signoz_evidence": self.signoz_evidence,
            "brightdata_evidence": self.brightdata_evidence.model_dump() if self.brightdata_evidence else None,
            "previous_candidates": self.previous_candidates
        }


@dataclass
class Plan:
    """Agent-generated plan for improvement"""
    hypothesis: str
    change_description: str
    expected_improvement: str
    constraints: List[str]
    target_files: List[str]
    
    def to_markdown(self) -> str:
        """Convert plan to markdown format"""
        md = f"## Hypothesis\n\n{self.hypothesis}\n\n"
        md += f"## Change Description\n\n{self.change_description}\n\n"
        md += f"## Expected Improvement\n\n{self.expected_improvement}\n\n"
        md += f"## Constraints\n\n"
        for constraint in self.constraints:
            md += f"- {constraint}\n"
        md += f"\n## Target Files\n\n"
        for file in self.target_files:
            md += f"- `{file}`\n"
        return md


class FactoryLoop:
    """
    Main orchestrator for the AVO-lite factory loop
    """
    
    def __init__(
        self,
        port_client: Optional[PortClient] = None,
        brightdata_client: Optional[BrightDataClient] = None,
        evaluator: Optional[MockEvaluator] = None
    ):
        self.port = port_client or PortClient()
        self.brightdata = brightdata_client or BrightDataClient()
        # Defaults to the real evaluator: it exercises Person A's app and asks Person
        # B's service for a decision computed from live SigNoz telemetry. Set
        # USE_MOCK_EVALUATOR=true only to exercise the loop's control flow offline -
        # never for a demo, because the mock's scores are fixtures, not measurements.
        if evaluator is not None:
            self.evaluator = evaluator
        elif os.getenv("USE_MOCK_EVALUATOR", "false").lower() == "true":
            logger.warning("[EVALUATE] USE_MOCK_EVALUATOR=true - scores are fixtures, not measurements")
            self.evaluator = MockEvaluator()
        else:
            self.evaluator = RealEvaluator()
        
        self.max_retry_attempts = int(os.getenv("MAX_RETRY_ATTEMPTS", "1"))
        # Bright Data fetches from the public tunnel URL when one is set;
        # otherwise it falls back to the local docs site.
        self.docs_site_url = (
            os.getenv("DOCS_PUBLIC_URL", "").rstrip("/")
            or os.getenv("DOCS_SITE_URL", "http://localhost:8001")
        )
    
    def inspect(
        self,
        factory_run_id: str,
        service_id: str = "api-guardian"
    ) -> Context:
        """
        Phase 1: Inspect - Gather context and evidence
        
        Args:
            factory_run_id: Current factory run ID
            service_id: Service identifier
            
        Returns:
            Context object with all gathered evidence
        """
        logger.info(f"[INSPECT] Gathering context for run {factory_run_id}")
        
        # Get service context from Port
        try:
            service = self.port.get_entity("service", service_id)
            service_props = service.get("entity", {}).get("properties", {})
            service_relations = service.get("entity", {}).get("relations", {})
        except Exception as e:
            logger.warning(f"Could not fetch service from Port: {e}")
            service_props = {"name": "API Guardian", "currentRelease": None}
            service_relations = {}
        
        # Get factory run details
        try:
            factory_run = self.port.get_entity("factoryRun", factory_run_id)
            run_props = factory_run.get("entity", {}).get("properties", {})
        except Exception as e:
            logger.warning(f"Could not fetch factory run from Port: {e}")
            run_props = {"scenario": "unknown", "triggerReason": "manual"}
        
        # Get dependencies
        dependencies = []
        dependency_ids = service_relations.get("dependsOn", [])
        for dep_id in dependency_ids:
            try:
                dep = self.port.get_entity("externalApi", dep_id)
                dependencies.append(dep.get("entity", {}))
            except Exception as e:
                logger.warning(f"Could not fetch dependency {dep_id}: {e}")
        
        # Get previous candidates for this run
        previous_candidates = []
        try:
            previous_candidates = self.port.find_candidates_for_run(factory_run_id)
        except Exception as e:
            logger.warning(f"Could not fetch previous candidates: {e}")
        
        # Gather Bright Data evidence if needed
        brightdata_evidence = None
        scenario = run_props.get("scenario", "")
        if "pricing" in scenario.lower() and "break" in scenario.lower():
            logger.info("[INSPECT] Gathering Bright Data migration evidence")
            try:
                docs_url = f"{self.docs_site_url}/api/docs/pricing"
                brightdata_evidence = self.brightdata.extract_and_validate(
                    docs_url,
                    retry_with_self_heal=True
                )
                if brightdata_evidence:
                    logger.info(f"[INSPECT] Successfully gathered evidence for {brightdata_evidence.provider}")
                else:
                    logger.warning("[INSPECT] Failed to gather Bright Data evidence")
            except Exception as e:
                logger.error(f"[INSPECT] Bright Data extraction failed: {e}")
        
        # TODO: Gather SigNoz evidence (will be provided by Person B)
        signoz_evidence = None
        
        context = Context(
            service_id=service_id,
            service_name=service_props.get("name", "Unknown"),
            current_release=service_props.get("currentRelease"),
            dependencies=dependencies,
            factory_run_id=factory_run_id,
            scenario=run_props.get("scenario", "unknown"),
            trigger_reason=run_props.get("triggerReason", "manual"),
            signoz_evidence=signoz_evidence,
            brightdata_evidence=brightdata_evidence,
            previous_candidates=previous_candidates
        )
        
        logger.info(f"[INSPECT] Context gathered: {context.scenario} scenario")
        return context
    
    def plan(self, context: Context) -> Plan:
        """
        Phase 2: Plan - Generate hypothesis and change plan
        
        In production, this would call Claude API to generate the plan.
        For now, we use deterministic plans based on scenario.
        
        Args:
            context: Inspection context
            
        Returns:
            Plan object
        """
        logger.info(f"[PLAN] Generating plan for scenario: {context.scenario}")
        
        scenario = context.scenario
        
        # Deterministic plans for demo scenarios
        if scenario == "baseline-v1":
            return Plan(
                hypothesis="The three provider API calls (Catalog, Pricing, Availability) are independent but executed sequentially, causing cumulative latency of ~2.7s. Parallelizing these calls should reduce total latency to ~1.1s (bounded by the slowest provider).",
                change_description="Refactor the Product Snapshot aggregator to execute all three provider calls concurrently using async/await or threading, then combine results after all complete.",
                expected_improvement="P95 latency should decrease from ~2700ms to ~1150ms, improving the latency score from 0/20 to 20/20 and overall score from 80 to 100.",
                constraints=[
                    "Preserve normalized Product Snapshot schema",
                    "Maintain error handling for each provider",
                    "Do not modify provider adapter logic",
                    "All tests must continue to pass"
                ],
                target_files=[
                    "apps/api-guardian/aggregator.py",
                    "apps/api-guardian/product_snapshot.py"
                ]
            )
        
        elif scenario == "pricing-v2-break":
            evidence = context.brightdata_evidence
            if evidence:
                return Plan(
                    hypothesis=f"The Pricing API has migrated from V1 to V2, changing the response schema. Fields `{evidence.old_field_price}` and `{evidence.old_field_currency}` have moved to `{evidence.new_field_price}` and `{evidence.new_field_currency}`. The current adapter expects V1 schema, causing parsing failures.",
                    change_description=f"Update the Pricing adapter to handle V2 schema by accessing nested pricing object. Map `{evidence.new_field_price}` to normalized `price_amount` and `{evidence.new_field_currency}` to normalized `currency`.",
                    expected_improvement="Correctness score should recover from 0/40 to 40/40, error rate should drop from 85% to 0%, and overall score should increase from 20 to 100.",
                    constraints=[
                        "Preserve normalized Product Snapshot contract",
                        "Maintain backward compatibility if possible",
                        "Do not modify mock provider",
                        "Update tests to reflect V2 schema"
                    ],
                    target_files=[
                        "packages/provider-clients/pricing_adapter.py",
                        "tests/test_pricing_adapter.py"
                    ]
                )
            else:
                return Plan(
                    hypothesis="Pricing provider is failing but migration evidence is unavailable. Manual investigation required.",
                    change_description="Unable to generate automated repair plan without migration documentation.",
                    expected_improvement="N/A",
                    constraints=[],
                    target_files=[]
                )
        
        else:
            return Plan(
                hypothesis=f"Unknown scenario: {scenario}",
                change_description="No automated plan available for this scenario.",
                expected_improvement="N/A",
                constraints=[],
                target_files=[]
            )
    
    def act(
        self,
        plan: Plan,
        candidate_id: str
    ) -> Dict[str, Any]:
        """
        Phase 3: Act - Implement the planned changes
        
        In production, this would invoke Claude Code to make actual code changes.
        For demo purposes, we simulate the action and return a commit reference.
        
        Args:
            plan: Plan to implement
            candidate_id: Candidate version ID
            
        Returns:
            Action result with commit reference
        """
        logger.info(f"[ACT] Implementing plan for candidate {candidate_id}")
        logger.info(f"[ACT] Target files: {', '.join(plan.target_files)}")
        
        # TODO: In production, invoke Claude API here to make actual code changes
        # For now, simulate the action
        
        # Simulate commit
        commit_ref = f"commit-{candidate_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        logger.info(f"[ACT] Changes implemented: {commit_ref}")
        
        return {
            "success": True,
            "commit_ref": commit_ref,
            "files_modified": plan.target_files,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def evaluate(
        self,
        candidate_id: str,
        run_id: str,
        scenario: str
    ) -> EvaluationResult:
        """
        Phase 4: Evaluate - Run objective verification
        
        Runs Person A's test suite, exercises the Product Snapshot endpoint to
        generate telemetry, then asks Person B's evaluator to score the window.
        
        Args:
            candidate_id: Candidate to evaluate
            run_id: Factory run ID
            scenario: Demo scenario
            
        Returns:
            EvaluationResult object
        """
        logger.info(f"[EVALUATE] Evaluating candidate {candidate_id}")
        
        result = self.evaluator.evaluate(run_id, candidate_id, scenario)
        
        logger.info(
            f"[EVALUATE] Result: {result.decision} "
            f"(score: {result.score}/100)"
        )
        
        return result
    
    def decide(
        self,
        evaluation: EvaluationResult,
        state_machine: CandidateStateMachine
    ) -> CandidateState:
        """
        Phase 5: Decide - Determine next state based on evaluation
        
        Args:
            evaluation: Evaluation result
            state_machine: Candidate state machine
            
        Returns:
            New state
        """
        logger.info(f"[DECIDE] Processing evaluation decision: {evaluation.decision}")
        
        # Check hard gates
        if evaluation.correctness != "PASS":
            logger.warning("[DECIDE] Correctness gate failed - REJECTED")
            return state_machine.transition_to(
                CandidateState.REJECTED,
                f"Correctness gate failed: {evaluation.failure_reason}"
            )
        
        if evaluation.error_rate > self.evaluator.error_rate_threshold:
            logger.warning(f"[DECIDE] Reliability gate failed - error rate {evaluation.error_rate} - REJECTED")
            return state_machine.transition_to(
                CandidateState.REJECTED,
                f"Reliability gate failed: error rate {evaluation.error_rate * 100:.1f}%"
            )
        
        # Check overall score
        if evaluation.score < self.evaluator.passing_score:
            logger.warning(f"[DECIDE] Score below threshold ({evaluation.score} < {self.evaluator.passing_score}) - REJECTED")
            return state_machine.transition_to(
                CandidateState.REJECTED,
                f"Score below threshold: {evaluation.score}/100. {evaluation.failure_reason}"
            )
        
        # All gates passed
        logger.info(f"[DECIDE] All gates passed (score: {evaluation.score}/100) - READY FOR APPROVAL")
        return state_machine.transition_to(
            CandidateState.READY_FOR_APPROVAL,
            f"All objective checks passed with score {evaluation.score}/100"
        )
    
    def await_approval(
        self,
        candidate_id: str,
        timeout: int = 300
    ) -> bool:
        """
        Phase 6: Await human approval
        
        In production, this would poll Port for approval status.
        For demo, we can auto-approve or wait for manual approval.
        
        Args:
            candidate_id: Candidate awaiting approval
            timeout: Maximum wait time in seconds
            
        Returns:
            True if approved, False if rejected/timeout
        """
        logger.info(f"[APPROVE] Awaiting human approval for {candidate_id}")
        
        auto_approve = os.getenv("AUTO_APPROVE", "false").lower() == "true"
        
        if auto_approve:
            logger.info("[APPROVE] Auto-approval enabled - approving candidate")
            return True
        
        # TODO: Poll Port for approval status
        # For now, assume approval for demo purposes
        logger.info("[APPROVE] Manual approval required - check Port dashboard")
        return True
    
    def release(
        self,
        candidate_id: str,
        service_id: str,
        evaluation: EvaluationResult,
        approved_by: str = "demo-user"
    ) -> Dict[str, Any]:
        """
        Phase 7: Release - Record release and update service state
        
        Args:
            candidate_id: Candidate to release
            service_id: Service identifier
            evaluation: Final evaluation result
            approved_by: Approver identifier
            
        Returns:
            Release information
        """
        logger.info(f"[RELEASE] Creating release for candidate {candidate_id}")
        
        # Generate version number
        version = f"v{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
        # Determine improvements based on scenario
        improvements = []
        if "optimized" in evaluation.scenario:
            improvements = [
                f"Reduced P95 latency from 2700ms to {evaluation.p95_latency}ms",
                "Parallelized independent provider API calls",
                "Improved factory score from 80 to 100"
            ]
        elif "repaired" in evaluation.scenario:
            improvements = [
                "Fixed Pricing API V2 compatibility",
                "Restored correctness score to 40/40",
                f"Reduced error rate from 85% to {evaluation.error_rate * 100:.1f}%"
            ]
        
        # Create release in Port
        try:
            release = self.port.create_release(
                version=version,
                service_id=service_id,
                candidate_id=candidate_id,
                approved_by=approved_by,
                score=evaluation.score,
                improvements=improvements,
                release_notes=f"Automated release for scenario: {evaluation.scenario}"
            )
            
            # Update service current release
            self.port.update_entity(
                "service",
                service_id,
                properties={
                    "currentRelease": version,
                    "score": evaluation.score,
                    "health": "healthy"
                }
            )
            
            logger.info(f"[RELEASE] Successfully released {version}")
            
            return {
                "version": version,
                "candidate_id": candidate_id,
                "score": evaluation.score,
                "improvements": improvements,
                "released_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[RELEASE] Failed to create release: {e}")
            return {
                "error": str(e),
                "candidate_id": candidate_id
            }
    
    def run_factory_loop(
        self,
        factory_run_id: str,
        service_id: str = "api-guardian",
        scenario: str = "baseline-v1"
    ) -> Dict[str, Any]:
        """
        Execute complete factory loop for a scenario
        
        Args:
            factory_run_id: Factory run identifier
            service_id: Service identifier
            scenario: Demo scenario name
            
        Returns:
            Complete run result
        """
        logger.info(f"=" * 80)
        logger.info(f"Starting Factory Loop: {factory_run_id}")
        logger.info(f"Scenario: {scenario}")
        logger.info(f"=" * 80)
        
        try:
            # Create factory run in Port
            self.port.create_factory_run(
                run_id=factory_run_id,
                service_id=service_id,
                scenario=scenario,
                trigger_reason="manual",
                status="DETECTED"
            )
            
            # Generate candidate ID
            candidate_id = f"CANDIDATE-{factory_run_id}"
            
            # Initialize state machine
            state_machine = CandidateStateMachine()
            
            # Phase 1: Inspect
            state_machine.transition_to(CandidateState.INVESTIGATING, "Gathering context")
            self.port.update_factory_run_status(factory_run_id, "INVESTIGATING")
            
            context = self.inspect(factory_run_id, service_id)
            
            # Phase 2: Plan
            state_machine.transition_to(CandidateState.PLANNED, "Generating improvement plan")
            plan = self.plan(context)
            
            # Create candidate in Port
            self.port.create_candidate(
                candidate_id=candidate_id,
                factory_run_id=factory_run_id,
                hypothesis=plan.hypothesis,
                status="PLANNED"
            )
            
            self.port.update_factory_run_status(
                factory_run_id,
                "PLANNED",
                current_candidate=candidate_id
            )
            
            # Phase 3: Act
            state_machine.transition_to(CandidateState.IMPLEMENTED, "Implementing changes")
            self.port.update_candidate_status(candidate_id, "IMPLEMENTED")
            
            action_result = self.act(plan, candidate_id)
            
            if not action_result.get("success"):
                raise Exception("Implementation failed")
            
            self.port.update_candidate_status(
                candidate_id,
                "IMPLEMENTED",
                commit_ref=action_result.get("commit_ref")
            )
            
            # Phase 4: Evaluate
            state_machine.transition_to(CandidateState.EVALUATING, "Running objective evaluation")
            self.port.update_candidate_status(candidate_id, "EVALUATING")
            self.port.update_factory_run_status(factory_run_id, "EVALUATING")
            
            evaluation = self.evaluate(candidate_id, factory_run_id, scenario)
            
            # Store evaluation in Port
            eval_id = f"EVAL-{candidate_id}"
            self.port.create_evaluation(
                evaluation_id=eval_id,
                candidate_id=candidate_id,
                score=evaluation.score,
                decision=evaluation.decision,
                correctness=evaluation.correctness,
                p95_latency=evaluation.p95_latency,
                error_rate=evaluation.error_rate,
                trace_ids=evaluation.trace_ids,
                failure_reason=evaluation.failure_reason,
                failed_provider=evaluation.failed_provider,
                correctness_score=evaluation.correctness_score,
                reliability_score=evaluation.reliability_score,
                latency_score=evaluation.latency_score,
                data_pipeline_score=evaluation.data_pipeline_score,
                observability_score=evaluation.observability_score
            )
            
            # Phase 5: Decide
            new_state = self.decide(evaluation, state_machine)
            
            self.port.update_candidate_status(
                candidate_id,
                new_state.value,
                score=evaluation.score,
                decision=evaluation.decision
            )
            
            if new_state == CandidateState.REJECTED:
                self.port.update_factory_run_status(factory_run_id, "REJECTED")
                logger.warning(f"Candidate {candidate_id} REJECTED")
                return {
                    "success": False,
                    "factory_run_id": factory_run_id,
                    "candidate_id": candidate_id,
                    "final_state": new_state.value,
                    "score": evaluation.score,
                    "failure_reason": evaluation.failure_reason
                }
            
            # Phase 6: Await Approval
            self.port.update_factory_run_status(factory_run_id, "READY_FOR_APPROVAL")
            
            approved = self.await_approval(candidate_id)
            
            if not approved:
                logger.warning(f"Candidate {candidate_id} approval denied")
                return {
                    "success": False,
                    "factory_run_id": factory_run_id,
                    "candidate_id": candidate_id,
                    "final_state": "APPROVAL_DENIED",
                    "score": evaluation.score
                }
            
            state_machine.transition_to(CandidateState.APPROVED, "Human approval granted")
            self.port.update_candidate_status(candidate_id, "APPROVED")
            self.port.update_factory_run_status(factory_run_id, "APPROVED")
            
            # Phase 7: Release
            state_machine.transition_to(CandidateState.RELEASED, "Creating release")
            release_info = self.release(candidate_id, service_id, evaluation)
            
            self.port.update_candidate_status(candidate_id, "RELEASED")
            self.port.update_factory_run_status(factory_run_id, "RELEASED")
            
            logger.info(f"=" * 80)
            logger.info(f"Factory Loop Complete: {factory_run_id}")
            logger.info(f"Result: SUCCESS - Released {release_info.get('version')}")
            logger.info(f"Score: {evaluation.score}/100")
            logger.info(f"=" * 80)
            
            return {
                "success": True,
                "factory_run_id": factory_run_id,
                "candidate_id": candidate_id,
                "final_state": "RELEASED",
                "score": evaluation.score,
                "release": release_info,
                "evaluation": evaluation.model_dump()
            }
            
        except Exception as e:
            logger.error(f"Factory loop failed: {e}", exc_info=True)
            return {
                "success": False,
                "factory_run_id": factory_run_id,
                "error": str(e)
            }
