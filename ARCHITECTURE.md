# Super Todo - Orchestrator Agent Architecture

## Overview

The Super Todo orchestrator agent is the brain of the agentic todo list application. It analyzes user intent from voice or text input, creates execution plans, delegates tasks to specialized agents (Voice, Browser, Search), and manages the entire task lifecycle autonomously.

## Architecture Options

### Option 1: Hierarchical Agent Graph

**Architecture Overview:**
```
TodoItem (with AI flag) → Orchestrator Node → Intent Classifier → Agent Router → Specialized Agents
                               ↓                    ↓                  ↓
                         State Manager         Plan Generator    Result Aggregator
```

**Key Components:**
- **Master Orchestrator**: Central coordinator that receives tasks
- **Intent Classification Node**: Uses LLM to understand task type and requirements
- **Planning Node**: Decomposes complex tasks into subtasks
- **Agent Router**: Selects appropriate agent(s) based on task requirements
- **Specialized Agent Nodes**: Voice (VAPI), Browser, Search agents
- **Result Aggregator**: Combines outputs from multiple agents

**State Management:**
```python
class OrchestratorState(TypedDict):
    todo_id: str
    original_request: str
    intent: Dict[str, Any]  # type, confidence, parameters
    plan: List[Dict]        # subtasks with dependencies
    active_agents: List[str]
    results: Dict[str, Any]
    status: str  # planning, executing, aggregating, completed
    errors: List[str]
```

### Option 2: Event-Driven Pipeline

**Architecture Overview:**
```
Event Bus
    ↓
[Intent Analysis] → [Task Queue] → [Agent Pool] → [Result Handler]
         ↓                ↓              ↓              ↓
    [State Store]    [Scheduler]   [Monitors]    [Notifier]
```

**Key Components:**
- **Event-Driven Core**: Async message passing between components
- **Parallel Processing**: Multiple agents can work simultaneously
- **Dynamic Scaling**: Agent pool grows/shrinks based on load
- **Checkpointing**: Save state after each major step

**State Management:**
```python
class TaskEvent(TypedDict):
    event_type: str  # task_created, agent_assigned, result_ready
    todo_id: str
    timestamp: datetime
    payload: Dict[str, Any]
    
class TaskState(TypedDict):
    todo_id: str
    events: List[TaskEvent]
    current_phase: str
    agent_assignments: Dict[str, str]  # subtask_id: agent_id
    checkpoints: List[Dict]  # for failure recovery
```

### Option 3: Reactive Agent Network

**Architecture Overview:**
```
              ┌─────────────────┐
              │   Orchestrator  │
              │   Supervisor    │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
   ┌─────────┐   ┌──────────┐   ┌────────┐
   │ Intent  │   │ Planning │   │ Broker │
   │ Agent   │   │  Agent   │   │ Agent  │
   └─────────┘   └──────────┘   └────┬───┘
                                      │
                    ┌─────────────────┼────────────┐
                    ↓                 ↓            ↓
              ┌──────────┐      ┌─────────┐  ┌────────┐
              │  Voice   │      │ Browser │  │ Search │
              │  Agent   │      │  Agent  │  │ Agent  │
              └──────────┘      └─────────┘  └────────┘
```

**Key Components:**
- **Supervisor Pattern**: Main orchestrator supervises child agents
- **Reactive Streams**: Agents react to state changes
- **Self-Healing**: Automatic retry and fallback mechanisms
- **Negotiation Protocol**: Agents can negotiate task assignments

## Recommended Approach: Hybrid Architecture

We recommend a hybrid architecture that combines the best elements of all three approaches, leveraging LangGraph's capabilities for stateful, durable workflow execution.

### Unified State Management

```python
from typing import TypedDict, List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

class AgentType(str, Enum):
    VOICE = "voice"
    BROWSER = "browser" 
    SEARCH = "search"
    ORCHESTRATOR = "orchestrator"

class TaskPhase(str, Enum):
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"

class OrchestratorState(TypedDict):
    # Core Task Information
    todo_id: str
    is_ai_task: bool
    original_request: str
    created_at: datetime
    
    # Intent Analysis
    intent: Dict[str, Any]  # {type, confidence, entities, parameters}
    task_category: str  # research, booking, automation, information
    
    # Execution Plan
    plan: List[Dict[str, Any]]  # List of subtasks with dependencies
    subtask_graph: Dict[str, List[str]]  # Dependency graph
    
    # Runtime State
    current_phase: TaskPhase
    active_subtasks: Dict[str, str]  # subtask_id: agent_id
    completed_subtasks: List[str]
    
    # Results & Errors
    subtask_results: Dict[str, Any]
    aggregated_result: Optional[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    
    # Persistence & Recovery
    checkpoints: List[Dict[str, Any]]
    last_checkpoint: datetime
    retry_count: int
    
    # Metadata
    execution_history: List[Dict[str, Any]]
    total_cost: float  # API costs
    performance_metrics: Dict[str, float]
```

### Agent Routing Strategy

#### Intent-Based Routing Rules

```python
ROUTING_RULES = {
    "research": {
        "primary": AgentType.SEARCH,
        "secondary": [AgentType.BROWSER],
        "patterns": ["research", "find out", "what is", "how to", "compare"]
    },
    "booking": {
        "primary": AgentType.BROWSER,
        "secondary": [AgentType.SEARCH, AgentType.VOICE],
        "patterns": ["book", "reserve", "schedule", "appointment"]
    },
    "information_gathering": {
        "primary": AgentType.SEARCH,
        "secondary": [],
        "patterns": ["news", "weather", "stock price", "latest"]
    },
    "voice_interaction": {
        "primary": AgentType.VOICE,
        "secondary": [],
        "patterns": ["call", "speak to", "voice", "tell me"]
    },
    "web_automation": {
        "primary": AgentType.BROWSER,
        "secondary": [],
        "patterns": ["fill form", "submit", "click", "navigate", "download"]
    }
}
```

#### Dynamic Agent Selection Algorithm

```python
class AgentSelector:
    """
    Selects appropriate agents based on:
    1. Task intent and requirements
    2. Agent availability and load
    3. Historical performance
    4. Cost optimization
    """
    
    def select_agents(self, state: OrchestratorState) -> List[AgentAssignment]:
        # Step 1: Intent-based primary selection
        primary_agent = self.get_primary_agent(state.intent)
        
        # Step 2: Capability matching
        required_capabilities = self.extract_capabilities(state.plan)
        capable_agents = self.match_capabilities(required_capabilities)
        
        # Step 3: Load balancing
        available_agents = self.check_availability(capable_agents)
        
        # Step 4: Cost-performance optimization
        optimal_agents = self.optimize_selection(
            available_agents, 
            state.intent["priority"],
            state.intent["budget"]
        )
        
        return optimal_agents
```

#### LangGraph Workflow Implementation

```python
def create_routing_graph():
    """Create LangGraph workflow with conditional routing"""
    
    workflow = StateGraph(OrchestratorState)
    
    # Add nodes
    workflow.add_node("analyze_intent", analyze_intent_node)
    workflow.add_node("create_plan", create_plan_node)
    workflow.add_node("route_to_agent", route_to_agent_node)
    workflow.add_node("voice_agent", voice_agent_node)
    workflow.add_node("browser_agent", browser_agent_node)
    workflow.add_node("search_agent", search_agent_node)
    workflow.add_node("aggregate_results", aggregate_results_node)
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "analyze_intent",
        should_create_plan,  # Returns "create_plan" or "simple_execution"
        {
            "create_plan": "create_plan",
            "simple_execution": "route_to_agent"
        }
    )
    
    workflow.add_conditional_edges(
        "route_to_agent",
        select_agent_type,  # Returns agent type based on task
        {
            AgentType.VOICE: "voice_agent",
            AgentType.BROWSER: "browser_agent",
            AgentType.SEARCH: "search_agent"
        }
    )
    
    # Add fallback routing
    workflow.add_edge("voice_agent", "aggregate_results")
    workflow.add_edge("browser_agent", "aggregate_results")
    workflow.add_edge("search_agent", "aggregate_results")
    
    return workflow.compile()
```

## FastAPI Backend Integration

### API Extensions

```python
# New endpoints in app/routers/orchestrator.py
@router.post("/items/{item_id}/orchestrate")
async def trigger_orchestration(
    item_id: str,
    background_tasks: BackgroundTasks,
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service)
):
    """Trigger orchestrator for AI-flagged todo items"""
    # Validate item exists and has AI flag
    # Queue orchestration task
    # Return task ID for tracking
    
@router.get("/orchestration/{task_id}/status")
async def get_orchestration_status(
    task_id: str,
    orchestrator_service: OrchestratorService = Depends(get_orchestrator_service)
):
    """Get real-time status of orchestration task"""
    # Return current phase, active agents, progress
    
@router.ws("/orchestration/{task_id}/stream")
async def orchestration_stream(
    websocket: WebSocket,
    task_id: str
):
    """WebSocket endpoint for real-time updates"""
    # Stream state changes, agent outputs, progress
```

### Database Schema Extensions

```sql
-- Add AI task fields to items table
ALTER TABLE public.items ADD COLUMN IF NOT EXISTS 
    is_ai_task boolean DEFAULT false,
    ai_metadata jsonb,
    orchestration_id uuid REFERENCES public.orchestrations(id);

-- Orchestration tracking table
CREATE TABLE IF NOT EXISTS public.orchestrations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id uuid NOT NULL REFERENCES public.items(id),
    state jsonb NOT NULL,  -- Full LangGraph state
    status text NOT NULL,  -- active, completed, failed
    started_at timestamptz DEFAULT now(),
    completed_at timestamptz,
    cost_usd numeric(10,4),
    created_at timestamptz DEFAULT now()
);

-- Agent execution logs
CREATE TABLE IF NOT EXISTS public.agent_executions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    orchestration_id uuid REFERENCES public.orchestrations(id),
    agent_type text NOT NULL,
    subtask_id text NOT NULL,
    input jsonb,
    output jsonb,
    error text,
    duration_ms integer,
    created_at timestamptz DEFAULT now()
);
```

### Service Layer Architecture

```python
# app/services/orchestrator_service.py
class OrchestratorService:
    def __init__(
        self,
        supabase_client: Client,
        langgraph_app: CompiledGraph,
        agent_registry: AgentRegistry
    ):
        self.db = supabase_client
        self.graph = langgraph_app
        self.agents = agent_registry
        
    async def start_orchestration(self, item_id: str) -> str:
        """Initialize orchestration for a todo item"""
        # 1. Load item from database
        # 2. Create initial state
        # 3. Start LangGraph execution
        # 4. Return orchestration ID
        
    async def get_state(self, orchestration_id: str) -> OrchestratorState:
        """Get current orchestration state"""
        # Fetch from persistence layer
        
    async def handle_agent_callback(self, agent_id: str, result: Dict):
        """Process agent results and update state"""
        # Update state in LangGraph
        # Persist to database
        # Trigger next steps
```

### Event-Driven Communication

```python
# app/events/orchestrator_events.py
class OrchestratorEventBus:
    """Pub/sub for orchestrator events"""
    
    async def publish(self, event: OrchestratorEvent):
        # Publish to Redis/RabbitMQ/Kafka
        # Notify WebSocket clients
        # Update monitoring dashboards
        
    async def subscribe(self, event_types: List[str], handler: Callable):
        # Subscribe to specific event types
        # Handle callbacks asynchronously

# Event types
@dataclass
class TaskAnalyzed(OrchestratorEvent):
    orchestration_id: str
    intent: Dict[str, Any]
    plan: List[Dict[str, Any]]

@dataclass 
class AgentAssigned(OrchestratorEvent):
    orchestration_id: str
    agent_id: str
    subtask_id: str
    
@dataclass
class SubtaskCompleted(OrchestratorEvent):
    orchestration_id: str
    subtask_id: str
    result: Dict[str, Any]
```

## Implementation Plan

### Phase 1: Foundation (Week 1-2)

#### Project Setup
- [ ] Add LangGraph and LangChain dependencies to `pyproject.toml`
- [ ] Create orchestrator package structure:
  ```
  app/orchestrator/
  ├── __init__.py
  ├── state.py          # State definitions
  ├── graph.py          # LangGraph workflow
  ├── nodes/            # Graph nodes
  │   ├── __init__.py
  │   ├── intent.py
  │   ├── planner.py
  │   └── router.py
  └── agents/           # Agent implementations
      ├── __init__.py
      ├── base.py
      ├── voice.py
      ├── browser.py
      └── search.py
  ```

#### Database Updates
- [ ] Run migrations to add orchestration tables
- [ ] Add `is_ai_task` flag to items
- [ ] Create indexes for performance

#### Basic State Management
- [ ] Implement `OrchestratorState` class
- [ ] Set up state persistence with Supabase
- [ ] Create checkpointing mechanism

### Phase 2: Core Orchestrator (Week 3-4)

#### LangGraph Workflow
- [ ] Build the main orchestration graph
- [ ] Implement intent analysis node
- [ ] Create planning node for task decomposition
- [ ] Add routing logic with conditional edges

#### Agent Base Classes
- [ ] Define `BaseAgent` abstract class
- [ ] Implement agent registry pattern
- [ ] Create agent communication protocol
- [ ] Add error handling and retry logic

#### Integration Layer
- [ ] Create `OrchestratorService`
- [ ] Add FastAPI endpoints
- [ ] Implement WebSocket support
- [ ] Set up background task processing

### Phase 3: Specialized Agents (Week 5-6)

#### Search Agent
- [ ] Integrate web search APIs (Google, Bing, etc.)
- [ ] Implement result parsing and ranking
- [ ] Add source credibility scoring
- [ ] Create summary generation

#### Browser Agent
- [ ] Set up Playwright/Selenium
- [ ] Create action primitives (click, fill, navigate)
- [ ] Implement page understanding with LLMs
- [ ] Add screenshot capabilities

#### Voice Agent
- [ ] Integrate VAPI platform
- [ ] Implement voice command parsing
- [ ] Add text-to-speech for responses
- [ ] Create conversation state management

### Phase 4: Advanced Features (Week 7-8)

#### Multi-Agent Coordination
- [ ] Implement parallel execution
- [ ] Add inter-agent communication
- [ ] Create result aggregation strategies
- [ ] Build consensus mechanisms

#### Monitoring & Observability
- [ ] Integrate LangSmith for tracing
- [ ] Add performance metrics
- [ ] Create debugging interface
- [ ] Implement cost tracking

#### Failure Handling
- [ ] Add automatic retries
- [ ] Implement fallback strategies
- [ ] Create manual intervention hooks
- [ ] Build recovery mechanisms

### Phase 5: Production Readiness (Week 9-10)

#### Performance Optimization
- [ ] Add caching layers
- [ ] Implement connection pooling
- [ ] Optimize database queries
- [ ] Add rate limiting

#### Security & Compliance
- [ ] Add authentication to orchestrator endpoints
- [ ] Implement agent sandboxing
- [ ] Create audit logging
- [ ] Add PII detection and masking

#### Testing & Documentation
- [ ] Write unit tests for each component
- [ ] Create integration test suite
- [ ] Add end-to-end workflow tests
- [ ] Document API changes

## Key Technical Decisions

1. **Message Queue**: Use Redis Streams for lightweight queuing initially, migrate to RabbitMQ/Kafka if needed
2. **State Persistence**: LangGraph's built-in persistence with Supabase adapter
3. **Agent Runtime**: Containerized agents for isolation and scaling
4. **Monitoring**: OpenTelemetry for distributed tracing
5. **API Design**: REST for CRUD, WebSockets for real-time updates, gRPC for inter-agent communication

## Success Criteria

- [ ] Successfully route 3 different task types to appropriate agents
- [ ] Complete end-to-end workflow in < 30 seconds for simple tasks
- [ ] Handle agent failures gracefully with automatic recovery
- [ ] Support concurrent orchestration of 10+ tasks
- [ ] Achieve 90%+ task completion rate in testing

## Example Workflows

### Voice-First Workflow
1. User speaks: "Book a dinner reservation for 4 people at an Italian restaurant this Friday"
2. System captures and transcribes speech
3. Orchestrator analyzes intent:
   - Task type: Reservation booking
   - Parameters: 4 people, Italian cuisine, specific date
4. Browser agent activated to:
   - Search for Italian restaurants
   - Check availability
   - Make reservation
5. Confirmation sent to user
6. Task marked as completed

### Research Workflow
1. User types: "Research the best practices for Python async programming"
2. Orchestrator identifies research task
3. Web search agent:
   - Queries multiple sources
   - Compiles findings
   - Creates summary document
4. Results attached to todo item
5. Task completed with deliverable

### Multi-Step Workflow
1. User: "Plan a weekend trip to Seattle"
2. Orchestrator creates subtasks:
   - Research attractions
   - Find accommodation
   - Check weather
   - Create itinerary
3. Multiple agents work in parallel
4. Results aggregated
5. Comprehensive plan delivered