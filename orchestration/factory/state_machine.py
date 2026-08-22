"""
Candidate Lifecycle State Machine

Manages the state transitions for candidate versions through the AVO-lite loop.
"""

from enum import Enum
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class CandidateState(str, Enum):
    """Valid candidate lifecycle states"""
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    PLANNED = "PLANNED"
    IMPLEMENTED = "IMPLEMENTED"
    EVALUATING = "EVALUATING"
    REJECTED = "REJECTED"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    RELEASED = "RELEASED"


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted"""
    pass


class CandidateStateMachine:
    """
    State machine for candidate lifecycle management
    
    Valid transitions:
    DETECTED -> INVESTIGATING
    INVESTIGATING -> PLANNED
    PLANNED -> IMPLEMENTED
    IMPLEMENTED -> EVALUATING
    EVALUATING -> REJECTED | READY_FOR_APPROVAL
    REJECTED -> PLANNED (retry)
    READY_FOR_APPROVAL -> APPROVED
    APPROVED -> RELEASED
    """
    
    # Define valid transitions
    VALID_TRANSITIONS = {
        CandidateState.DETECTED: [CandidateState.INVESTIGATING],
        CandidateState.INVESTIGATING: [CandidateState.PLANNED],
        CandidateState.PLANNED: [CandidateState.IMPLEMENTED],
        CandidateState.IMPLEMENTED: [CandidateState.EVALUATING],
        CandidateState.EVALUATING: [
            CandidateState.REJECTED,
            CandidateState.READY_FOR_APPROVAL
        ],
        CandidateState.REJECTED: [CandidateState.PLANNED],  # Allow retry
        CandidateState.READY_FOR_APPROVAL: [CandidateState.APPROVED],
        CandidateState.APPROVED: [CandidateState.RELEASED],
        CandidateState.RELEASED: []  # Terminal state
    }
    
    def __init__(self, initial_state: CandidateState = CandidateState.DETECTED):
        self.current_state = initial_state
        self.history: list[Dict[str, Any]] = []
        self._record_state(initial_state, "Initial state")
    
    def _record_state(self, state: CandidateState, reason: str):
        """Record state change in history"""
        from datetime import datetime
        self.history.append({
            "state": state.value,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def can_transition_to(self, target_state: CandidateState) -> bool:
        """Check if transition to target state is valid"""
        valid_targets = self.VALID_TRANSITIONS.get(self.current_state, [])
        return target_state in valid_targets
    
    def transition_to(
        self,
        target_state: CandidateState,
        reason: str = ""
    ) -> CandidateState:
        """
        Transition to a new state
        
        Args:
            target_state: Target state to transition to
            reason: Reason for the transition
            
        Returns:
            New current state
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        if not self.can_transition_to(target_state):
            raise StateTransitionError(
                f"Invalid transition from {self.current_state.value} "
                f"to {target_state.value}"
            )
        
        old_state = self.current_state
        self.current_state = target_state
        self._record_state(target_state, reason or f"Transitioned from {old_state.value}")
        
        logger.info(
            f"State transition: {old_state.value} -> {target_state.value} "
            f"({reason})"
        )
        
        return self.current_state
    
    def get_state(self) -> CandidateState:
        """Get current state"""
        return self.current_state
    
    def get_history(self) -> list[Dict[str, Any]]:
        """Get state transition history"""
        return self.history.copy()
    
    def is_terminal(self) -> bool:
        """Check if current state is terminal"""
        return self.current_state in [
            CandidateState.RELEASED,
            CandidateState.REJECTED
        ]
    
    def requires_human_approval(self) -> bool:
        """Check if current state requires human approval"""
        return self.current_state == CandidateState.READY_FOR_APPROVAL
    
    def can_retry(self) -> bool:
        """Check if candidate can be retried"""
        return self.current_state == CandidateState.REJECTED
    
    @classmethod
    def from_state(cls, state: str) -> "CandidateStateMachine":
        """Create state machine from existing state string"""
        try:
            candidate_state = CandidateState(state)
            return cls(initial_state=candidate_state)
        except ValueError:
            raise ValueError(f"Invalid state: {state}")
