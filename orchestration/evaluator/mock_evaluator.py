"""
Mock Evaluator for API Guardian Factory

Simulates Person B's evaluation system until real SigNoz integration is ready.
Provides deterministic evaluation results for each demo scenario.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EvaluationResult(BaseModel):
    """Evaluation result matching contract with Person B"""
    
    run_id: str
    candidate_id: str
    scenario: str
    score: float
    decision: str  # PASS or FAIL
    correctness: str  # PASS or FAIL
    correctness_score: float
    reliability_score: float
    latency_score: float
    data_pipeline_score: float
    observability_score: float
    p95_latency: float
    error_rate: float
    failed_provider: Optional[str] = None
    trace_ids: List[str]
    failure_reason: Optional[str] = None
    evaluated_at: str


class MockEvaluator:
    """
    Mock evaluator providing deterministic results for demo scenarios
    
    Scoring breakdown (100 points total):
    - Correctness: 40 points (hard gate)
    - Reliability: 20 points (hard gate)
    - Latency: 20 points
    - Data Pipeline: 10 points
    - Observability: 10 points
    """
    
    def __init__(self):
        self.p95_threshold_full = 1600  # ms
        self.p95_threshold_partial = 2200  # ms
        self.error_rate_threshold = 0.01  # 1%
        self.passing_score = 90
    
    def evaluate_baseline_v1(
        self,
        run_id: str,
        candidate_id: str = "BASELINE"
    ) -> EvaluationResult:
        """
        Evaluate baseline sequential implementation
        
        Expected: Correct but slow (~2.7s latency)
        Result: FAIL due to poor latency
        """
        logger.info(f"Evaluating baseline-v1 scenario for {candidate_id}")
        
        # Correctness: PASS (40/40)
        correctness_score = 40.0
        
        # Reliability: PASS (20/20)
        reliability_score = 20.0
        
        # Latency: FAIL (0/20) - way over threshold
        p95_latency = 2700.0  # ms
        latency_score = 0.0
        
        # Data Pipeline: PASS (10/10)
        data_pipeline_score = 10.0
        
        # Observability: PASS (10/10)
        observability_score = 10.0
        
        total_score = (
            correctness_score +
            reliability_score +
            latency_score +
            data_pipeline_score +
            observability_score
        )
        
        return EvaluationResult(
            run_id=run_id,
            candidate_id=candidate_id,
            scenario="baseline-v1",
            score=total_score,
            decision="FAIL",
            correctness="PASS",
            correctness_score=correctness_score,
            reliability_score=reliability_score,
            latency_score=latency_score,
            data_pipeline_score=data_pipeline_score,
            observability_score=observability_score,
            p95_latency=p95_latency,
            error_rate=0.0,
            failed_provider=None,
            trace_ids=[f"trace-{run_id}-baseline-001"],
            failure_reason=f"p95 latency exceeds threshold ({p95_latency}ms > {self.p95_threshold_partial}ms). Sequential provider calls detected.",
            evaluated_at=datetime.utcnow().isoformat()
        )
    
    def evaluate_optimized_v1(
        self,
        run_id: str,
        candidate_id: str = "CANDIDATE-PARALLEL"
    ) -> EvaluationResult:
        """
        Evaluate parallelized implementation
        
        Expected: Correct and fast (~1.1s latency)
        Result: PASS
        """
        logger.info(f"Evaluating optimized-v1 scenario for {candidate_id}")
        
        # Correctness: PASS (40/40)
        correctness_score = 40.0
        
        # Reliability: PASS (20/20)
        reliability_score = 20.0
        
        # Latency: PASS (20/20) - under threshold
        p95_latency = 1150.0  # ms
        latency_score = 20.0
        
        # Data Pipeline: PASS (10/10)
        data_pipeline_score = 10.0
        
        # Observability: PASS (10/10)
        observability_score = 10.0
        
        total_score = (
            correctness_score +
            reliability_score +
            latency_score +
            data_pipeline_score +
            observability_score
        )
        
        return EvaluationResult(
            run_id=run_id,
            candidate_id=candidate_id,
            scenario="optimized-v1",
            score=total_score,
            decision="PASS",
            correctness="PASS",
            correctness_score=correctness_score,
            reliability_score=reliability_score,
            latency_score=latency_score,
            data_pipeline_score=data_pipeline_score,
            observability_score=observability_score,
            p95_latency=p95_latency,
            error_rate=0.0,
            failed_provider=None,
            trace_ids=[f"trace-{run_id}-optimized-001"],
            failure_reason=None,
            evaluated_at=datetime.utcnow().isoformat()
        )
    
    def evaluate_pricing_v2_break(
        self,
        run_id: str,
        candidate_id: str = "PRICING-V2-FAIL"
    ) -> EvaluationResult:
        """
        Evaluate after Pricing API schema break
        
        Expected: Parsing errors, high error rate
        Result: FAIL due to correctness and reliability
        """
        logger.info(f"Evaluating pricing-v2-break scenario for {candidate_id}")
        
        # Correctness: FAIL (0/40) - schema validation fails
        correctness_score = 0.0
        
        # Reliability: FAIL (0/20) - high error rate
        reliability_score = 0.0
        
        # Latency: N/A (0/20) - requests failing
        latency_score = 0.0
        
        # Data Pipeline: PASS (10/10) - Bright Data still works
        data_pipeline_score = 10.0
        
        # Observability: PASS (10/10) - traces show the error
        observability_score = 10.0
        
        total_score = (
            correctness_score +
            reliability_score +
            latency_score +
            data_pipeline_score +
            observability_score
        )
        
        return EvaluationResult(
            run_id=run_id,
            candidate_id=candidate_id,
            scenario="pricing-v2-break",
            score=total_score,
            decision="FAIL",
            correctness="FAIL",
            correctness_score=correctness_score,
            reliability_score=reliability_score,
            latency_score=latency_score,
            data_pipeline_score=data_pipeline_score,
            observability_score=observability_score,
            p95_latency=0.0,  # N/A - requests failing
            error_rate=0.85,  # 85% error rate
            failed_provider="pricing",
            trace_ids=[f"trace-{run_id}-pricing-fail-001"],
            failure_reason="Pricing provider adapter failed: KeyError 'price'. Expected field not found in V2 response. Error rate: 85%",
            evaluated_at=datetime.utcnow().isoformat()
        )
    
    def evaluate_pricing_v2_repaired(
        self,
        run_id: str,
        candidate_id: str = "CANDIDATE-PRICING-V2-FIX"
    ) -> EvaluationResult:
        """
        Evaluate after Pricing adapter repair
        
        Expected: Correct, fast, healthy
        Result: PASS
        """
        logger.info(f"Evaluating pricing-v2-repaired scenario for {candidate_id}")
        
        # Correctness: PASS (40/40)
        correctness_score = 40.0
        
        # Reliability: PASS (20/20)
        reliability_score = 20.0
        
        # Latency: PASS (20/20) - still parallel
        p95_latency = 1180.0  # ms
        latency_score = 20.0
        
        # Data Pipeline: PASS (10/10)
        data_pipeline_score = 10.0
        
        # Observability: PASS (10/10)
        observability_score = 10.0
        
        total_score = (
            correctness_score +
            reliability_score +
            latency_score +
            data_pipeline_score +
            observability_score
        )
        
        return EvaluationResult(
            run_id=run_id,
            candidate_id=candidate_id,
            scenario="pricing-v2-repaired",
            score=total_score,
            decision="PASS",
            correctness="PASS",
            correctness_score=correctness_score,
            reliability_score=reliability_score,
            latency_score=latency_score,
            data_pipeline_score=data_pipeline_score,
            observability_score=observability_score,
            p95_latency=p95_latency,
            error_rate=0.0,
            failed_provider=None,
            trace_ids=[f"trace-{run_id}-repaired-001"],
            failure_reason=None,
            evaluated_at=datetime.utcnow().isoformat()
        )
    
    def evaluate(
        self,
        run_id: str,
        candidate_id: str,
        scenario: str
    ) -> EvaluationResult:
        """
        Main evaluation entry point - routes to appropriate scenario evaluator
        
        Args:
            run_id: Factory run ID
            candidate_id: Candidate version ID
            scenario: Demo scenario name
            
        Returns:
            EvaluationResult object
        """
        scenario_map = {
            "baseline-v1": self.evaluate_baseline_v1,
            "optimized-v1": self.evaluate_optimized_v1,
            "pricing-v2-break": self.evaluate_pricing_v2_break,
            "pricing-v2-repaired": self.evaluate_pricing_v2_repaired
        }
        
        evaluator_func = scenario_map.get(scenario)
        if not evaluator_func:
            raise ValueError(f"Unknown scenario: {scenario}")
        
        return evaluator_func(run_id, candidate_id)
    
    def get_evaluation_summary(self, result: EvaluationResult) -> Dict[str, Any]:
        """
        Generate human-readable evaluation summary
        
        Args:
            result: EvaluationResult object
            
        Returns:
            Summary dictionary
        """
        return {
            "candidate_id": result.candidate_id,
            "scenario": result.scenario,
            "decision": result.decision,
            "score": f"{result.score}/100",
            "breakdown": {
                "correctness": f"{result.correctness_score}/40 ({result.correctness})",
                "reliability": f"{result.reliability_score}/20",
                "latency": f"{result.latency_score}/20 (p95: {result.p95_latency}ms)",
                "data_pipeline": f"{result.data_pipeline_score}/10",
                "observability": f"{result.observability_score}/10"
            },
            "metrics": {
                "p95_latency_ms": result.p95_latency,
                "error_rate": f"{result.error_rate * 100:.1f}%"
            },
            "failure_reason": result.failure_reason,
            "trace_ids": result.trace_ids
        }
