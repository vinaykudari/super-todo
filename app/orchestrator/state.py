"""Reactive State Management for Agent Network"""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import uuid


class AgentMessage(TypedDict):
    """Message passed between agents in the reactive network"""
    id: str
    from_agent: str
    to_agent: str
    message_type: str  # request, response, error, status, negotiate
    content: Dict[str, Any]
    correlation_id: str
    timestamp: datetime


class ExecutionStatus(str, Enum):
    """Status of orchestration execution"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    NEGOTIATING = "negotiating"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReactiveState(TypedDict):
    """Shared state for reactive agent network"""
    # Core task information
    todo_id: str  # This is the task_id for external systems
    original_request: str
    
    # Task analysis
    task_analysis: Optional[Dict[str, Any]]  # Analysis result from TaskAnalyzer
    ai_request: Optional[str]  # Formatted AI request
    
    # Message passing
    message_queue: List[AgentMessage]
    active_messages: Dict[str, AgentMessage]  # correlation_id -> message
    
    # Agent states
    agent_states: Dict[str, Dict[str, Any]]  # agent_id -> state
    active_agents: List[str]
    
    # Execution tracking
    execution_status: ExecutionStatus
    results: Dict[str, Any]
    errors: List[Dict[str, Any]]
    
    # Reactive metadata
    last_activity: datetime
    consensus_reached: bool
    negotiation_rounds: int


def create_initial_state(todo_id: str, request: str) -> ReactiveState:
    """Create initial reactive state for a new task"""
    return ReactiveState(
        todo_id=todo_id,
        original_request=request,
        task_analysis=None,
        ai_request=None,
        message_queue=[],
        active_messages={},
        agent_states={},
        active_agents=[],  # Will be set by task analysis
        execution_status=ExecutionStatus.INITIALIZING,
        results={},
        errors=[],
        last_activity=datetime.now(),
        consensus_reached=False,
        negotiation_rounds=0
    )


def create_agent_message(
    from_agent: str,
    to_agent: str,
    message_type: str,
    content: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> AgentMessage:
    """Helper to create agent messages"""
    return AgentMessage(
        id=str(uuid.uuid4()),
        from_agent=from_agent,
        to_agent=to_agent,
        message_type=message_type,
        content=content,
        correlation_id=correlation_id or str(uuid.uuid4()),
        timestamp=datetime.now()
    )


def add_message_to_state(state: ReactiveState, message: AgentMessage) -> ReactiveState:
    """Add a message to the state queue"""
    state["message_queue"].append(message)
    state["active_messages"][message["correlation_id"]] = message
    state["last_activity"] = datetime.now()
    return state


def update_agent_state(state: ReactiveState, agent_id: str, agent_data: Dict[str, Any]) -> ReactiveState:
    """Update specific agent's state"""
    if agent_id not in state["agent_states"]:
        state["agent_states"][agent_id] = {}
    
    state["agent_states"][agent_id].update(agent_data)
    state["last_activity"] = datetime.now()
    return state