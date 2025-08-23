# Reactive Agent Network Implementation Plan

## Overview

This document outlines the phased implementation of the Reactive Agent Network architecture for Super Todo. The approach emphasizes reactive streams, self-healing capabilities, and agent negotiation protocols.

## Architecture Recap

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

## Phase 1: Basic LangGraph Integration & Simple Agent (Week 1-2)

### Goals
- Set up LangGraph with a simple workflow
- Create orchestrator supervisor that triggers on new AI todos
- Implement a basic search agent
- Auto-complete tasks after agent execution

### Implementation Steps

#### 1.1 Project Setup
```bash
# Dependencies to add
langgraph>=0.2.0
langchain>=0.3.0
langchain-openai>=0.2.0
langchain-anthropic>=0.3.0
redis>=5.0.0  # For message passing
```

#### 1.2 Create Reactive State Model
```python
# app/orchestrator/state.py
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class AgentMessage(TypedDict):
    """Reactive message between agents"""
    id: str
    from_agent: str
    to_agent: str
    message_type: str  # request, response, error, status, negotiate
    content: Dict[str, Any]
    correlation_id: str
    timestamp: datetime

class ReactiveState(TypedDict):
    """Shared state for reactive agent network"""
    todo_id: str
    original_request: str
    
    # Message passing
    message_queue: List[AgentMessage]
    active_messages: Dict[str, AgentMessage]  # correlation_id -> message
    
    # Agent states
    agent_states: Dict[str, Dict[str, Any]]  # agent_id -> state
    active_agents: List[str]
    
    # Execution tracking
    execution_status: str  # initializing, running, negotiating, completing
    results: Dict[str, Any]
    errors: List[Dict[str, Any]]
    
    # Reactive metadata
    last_activity: datetime
    consensus_reached: bool
    negotiation_rounds: int
```

#### 1.3 Supervisor Implementation
```python
# app/orchestrator/supervisor.py
from langgraph.graph import StateGraph, END
from typing import Dict, Any

class OrchestratorSupervisor:
    def __init__(self):
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ReactiveState)
        
        # Add nodes
        workflow.add_node("initialize", self.initialize_network)
        workflow.add_node("broadcast_task", self.broadcast_task)
        workflow.add_node("monitor_agents", self.monitor_agents)
        workflow.add_node("aggregate_results", self.aggregate_results)
        workflow.add_node("complete_task", self.complete_task)
        
        # Define flow
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "broadcast_task")
        workflow.add_edge("broadcast_task", "monitor_agents")
        
        # Conditional routing
        workflow.add_conditional_edges(
            "monitor_agents",
            self.check_completion,
            {
                "continue": "monitor_agents",
                "aggregate": "aggregate_results",
                "error": "complete_task"
            }
        )
        
        workflow.add_edge("aggregate_results", "complete_task")
        workflow.add_edge("complete_task", END)
        
        return workflow.compile()
```

#### 1.4 Basic Search Agent
```python
# app/orchestrator/agents/search.py
class ReactiveSearchAgent:
    def __init__(self, agent_id: str = "search_agent"):
        self.agent_id = agent_id
        self.capabilities = ["research", "information_gathering", "fact_checking"]
        
    async def handle_message(self, message: AgentMessage, state: ReactiveState) -> AgentMessage:
        """React to incoming messages"""
        if message.message_type == "request":
            return await self._handle_request(message, state)
        elif message.message_type == "negotiate":
            return await self._handle_negotiation(message, state)
            
    async def _handle_request(self, message: AgentMessage, state: ReactiveState) -> AgentMessage:
        # Simple search implementation
        query = message.content.get("query", state.original_request)
        results = await self._perform_search(query)
        
        return {
            "id": str(uuid.uuid4()),
            "from_agent": self.agent_id,
            "to_agent": message.from_agent,
            "message_type": "response",
            "content": {
                "results": results,
                "confidence": 0.85
            },
            "correlation_id": message.id,
            "timestamp": datetime.now()
        }
```

#### 1.5 FastAPI Integration
```python
# app/routers/orchestrator.py
from fastapi import APIRouter, BackgroundTasks, Depends
from app.orchestrator.supervisor import OrchestratorSupervisor

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])

@router.post("/items/{item_id}/execute")
async def execute_ai_task(
    item_id: str,
    background_tasks: BackgroundTasks,
    items_service: ItemsService = Depends(get_items_service)
):
    """Trigger reactive agent network for AI task"""
    item = await items_service.get_item(item_id)
    
    if not item.get("is_ai_task"):
        raise HTTPException(400, "Item is not marked as AI task")
        
    # Initialize supervisor and run in background
    supervisor = OrchestratorSupervisor()
    background_tasks.add_task(
        run_orchestration,
        supervisor,
        item_id,
        item["title"]
    )
    
    return {"message": "Orchestration started", "item_id": item_id}

async def run_orchestration(supervisor, item_id: str, request: str):
    """Background task to run orchestration"""
    initial_state = {
        "todo_id": item_id,
        "original_request": request,
        "message_queue": [],
        "active_messages": {},
        "agent_states": {},
        "active_agents": ["search_agent"],
        "execution_status": "initializing",
        "results": {},
        "errors": [],
        "last_activity": datetime.now(),
        "consensus_reached": False,
        "negotiation_rounds": 0
    }
    
    # Run the graph
    result = await supervisor.graph.ainvoke(initial_state)
    
    # Update todo item status
    await update_item_status(item_id, "completed", result)
```

#### 1.6 Database Schema Updates
```sql
-- Add AI task support
ALTER TABLE public.items ADD COLUMN IF NOT EXISTS 
    is_ai_task boolean DEFAULT false,
    ai_request text,
    orchestration_status text,
    orchestration_result jsonb;

-- Message log for debugging
CREATE TABLE IF NOT EXISTS public.agent_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id uuid REFERENCES public.items(id),
    from_agent text NOT NULL,
    to_agent text NOT NULL,
    message_type text NOT NULL,
    content jsonb,
    correlation_id text,
    created_at timestamptz DEFAULT now()
);
```

### Deliverables - Phase 1
- [ ] LangGraph supervisor that monitors todo creation
- [ ] Basic search agent implementation
- [ ] Automatic task completion after search
- [ ] Message logging for debugging
- [ ] Simple UI indicator for AI tasks

### Success Metrics
- Successfully process a simple search query ("What's the weather in NYC?")
- Complete task automatically within 10 seconds
- Log all agent messages for debugging

## Phase 2: Reactive Message Passing & Multi-Agent (Week 3-4)

### Goals
- Implement reactive message bus
- Add Intent and Planning agents
- Enable parallel agent execution
- Implement basic state synchronization

### Implementation Steps

#### 2.1 Message Bus Implementation
```python
# app/orchestrator/message_bus.py
import redis.asyncio as redis
from typing import Callable, Dict, List

class ReactiveMessageBus:
    def __init__(self):
        self.redis_client = None
        self.subscribers: Dict[str, List[Callable]] = {}
        
    async def connect(self):
        self.redis_client = await redis.from_url("redis://localhost")
        
    async def publish(self, channel: str, message: AgentMessage):
        """Publish message to channel"""
        await self.redis_client.publish(
            channel, 
            json.dumps(message, default=str)
        )
        
    async def subscribe(self, agent_id: str, handler: Callable):
        """Subscribe agent to its channel"""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(agent_id)
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await handler(data)
```

#### 2.2 Intent Agent
```python
# app/orchestrator/agents/intent.py
class ReactiveIntentAgent:
    def __init__(self):
        self.agent_id = "intent_agent"
        self.llm = ChatOpenAI(model="gpt-4")
        
    async def analyze_intent(self, request: str) -> Dict[str, Any]:
        """Analyze user intent and broadcast to network"""
        prompt = f"""
        Analyze the user's request and extract:
        1. Primary intent (research, booking, automation, etc.)
        2. Key entities and parameters
        3. Suggested agents to involve
        4. Priority level
        
        Request: {request}
        """
        
        response = await self.llm.ainvoke(prompt)
        intent_data = self._parse_response(response)
        
        # Broadcast intent to all agents
        await self.broadcast_intent(intent_data)
        
        return intent_data
```

#### 2.3 Planning Agent
```python
# app/orchestrator/agents/planner.py
class ReactivePlanningAgent:
    def __init__(self):
        self.agent_id = "planning_agent"
        
    async def create_plan(self, intent: Dict[str, Any], agent_capabilities: Dict[str, List[str]]) -> List[Dict]:
        """Create execution plan based on intent and available agents"""
        # Reactive planning - adapt based on agent responses
        plan = []
        
        # Match intent to capabilities
        for agent_id, capabilities in agent_capabilities.items():
            if self._matches_intent(intent, capabilities):
                plan.append({
                    "agent_id": agent_id,
                    "subtask": self._create_subtask(intent, agent_id),
                    "priority": self._calculate_priority(intent, agent_id),
                    "dependencies": []
                })
                
        return plan
```

### Deliverables - Phase 2
- [ ] Redis-based message bus
- [ ] Intent analysis agent
- [ ] Planning agent for task decomposition
- [ ] Parallel agent execution
- [ ] Real-time message visualization

## Phase 3: Agent Negotiation Protocol (Week 5-6)

### Goals
- Implement agent negotiation for task assignment
- Add capability advertising
- Enable dynamic task redistribution
- Implement consensus mechanisms

### Implementation Steps

#### 3.1 Negotiation Protocol
```python
# app/orchestrator/protocols/negotiation.py
class NegotiationProtocol:
    """
    Agents can:
    1. Advertise capabilities
    2. Bid on tasks
    3. Negotiate workload
    4. Form consensus
    """
    
    async def initiate_negotiation(self, task: Dict, available_agents: List[str]) -> Dict[str, Any]:
        # Broadcast task to agents
        bids = await self.collect_bids(task, available_agents)
        
        # Evaluate bids
        winner = self.evaluate_bids(bids)
        
        # Confirm assignment
        confirmation = await self.confirm_assignment(winner, task)
        
        return confirmation
```

#### 3.2 Broker Agent
```python
# app/orchestrator/agents/broker.py
class ReactiveBrokerAgent:
    """Mediates between agents and manages negotiations"""
    
    def __init__(self):
        self.agent_id = "broker_agent"
        self.agent_registry = {}
        
    async def register_agent(self, agent_id: str, capabilities: List[str]):
        """Register agent with capabilities"""
        self.agent_registry[agent_id] = {
            "capabilities": capabilities,
            "status": "available",
            "current_load": 0
        }
        
    async def negotiate_task_assignment(self, task: Dict) -> str:
        """Negotiate which agent should handle task"""
        candidates = self._find_capable_agents(task)
        
        if len(candidates) == 1:
            return candidates[0]
            
        # Multi-agent negotiation
        negotiation_result = await self._run_negotiation(task, candidates)
        return negotiation_result["selected_agent"]
```

### Deliverables - Phase 3
- [ ] Agent capability registry
- [ ] Negotiation protocol implementation
- [ ] Broker agent for mediation
- [ ] Dynamic task redistribution
- [ ] Consensus tracking

## Phase 4: Self-Healing Mechanisms (Week 7-8)

### Goals
- Implement automatic retry logic
- Add fallback strategies
- Enable agent health monitoring
- Implement circuit breakers

### Implementation Steps

#### 4.1 Health Monitoring
```python
# app/orchestrator/monitoring/health.py
class AgentHealthMonitor:
    def __init__(self):
        self.health_stats = {}
        self.failure_thresholds = {
            "error_rate": 0.3,
            "timeout_rate": 0.2,
            "consecutive_failures": 3
        }
        
    async def monitor_agent_health(self, agent_id: str) -> Dict[str, Any]:
        """Monitor agent health metrics"""
        stats = self.health_stats.get(agent_id, self._default_stats())
        
        return {
            "agent_id": agent_id,
            "health_score": self._calculate_health_score(stats),
            "status": self._determine_status(stats),
            "recommendations": self._get_recommendations(stats)
        }
```

#### 4.2 Self-Healing Supervisor
```python
# app/orchestrator/healing/supervisor.py
class SelfHealingSupervisor:
    def __init__(self):
        self.retry_policies = {}
        self.fallback_chains = {}
        
    async def handle_agent_failure(self, agent_id: str, error: Exception, context: Dict):
        """Handle agent failures with self-healing"""
        # 1. Check retry policy
        if self._should_retry(agent_id, error):
            return await self._retry_with_backoff(agent_id, context)
            
        # 2. Try fallback agent
        fallback = self._get_fallback_agent(agent_id)
        if fallback:
            return await self._execute_fallback(fallback, context)
            
        # 3. Graceful degradation
        return await self._graceful_degradation(context)
```

### Deliverables - Phase 4
- [ ] Agent health monitoring dashboard
- [ ] Automatic retry with exponential backoff
- [ ] Fallback agent chains
- [ ] Circuit breaker implementation
- [ ] Self-healing metrics

## Phase 5: Full Reactive Network (Week 9-10)

### Goals
- Complete reactive agent network
- Add advanced negotiation strategies
- Implement learning from past executions
- Production-ready deployment

### Implementation Steps

#### 5.1 Advanced Features
- Dynamic agent spawning based on load
- Multi-round negotiations with bidding
- Reputation system for agents
- Cost optimization algorithms

#### 5.2 Production Deployment
- Kubernetes deployment configs
- Horizontal scaling for agents
- Monitoring and alerting
- Performance optimization

### Deliverables - Phase 5
- [ ] Complete reactive agent network
- [ ] Production deployment scripts
- [ ] Performance benchmarks
- [ ] Operational runbooks
- [ ] User documentation

## Extension Milestones

### Milestone 1: Voice Integration (2 weeks)
- Integrate VAPI for voice input
- Add voice agent to network
- Enable voice feedback

### Milestone 2: Browser Automation (3 weeks)
- Implement browser agent with Playwright
- Add visual understanding with GPT-4V
- Enable complex web interactions

### Milestone 3: Learning System (2 weeks)
- Track successful patterns
- Improve agent selection over time
- Optimize execution paths

### Milestone 4: Team Collaboration (3 weeks)
- Multi-user support
- Shared task delegation
- Permission system

### Milestone 5: Custom Agents (2 weeks)
- Agent SDK
- Custom agent registration
- Marketplace for agents

## Success Metrics

### Phase 1 Success Criteria
- [ ] Process simple search query in < 10 seconds
- [ ] 95% success rate for single-agent tasks
- [ ] Complete message trace for debugging

### Overall Success Criteria
- [ ] Handle 10+ concurrent orchestrations
- [ ] < 30 second completion for complex tasks
- [ ] 90%+ task success rate
- [ ] Automatic recovery from 80% of failures
- [ ] Support for 5+ agent types

## Technical Stack

### Core Dependencies
```toml
[dependencies]
langgraph = ">=0.2.0"
langchain = ">=0.3.0"
langchain-openai = ">=0.2.0"
redis = ">=5.0.0"
asyncio = ">=3.4.3"
pydantic = ">=2.5.0"
```

### Infrastructure
- Redis for message passing
- PostgreSQL for state persistence
- Kubernetes for agent scaling
- Prometheus for monitoring
- Grafana for visualization

## Development Guidelines

### Agent Development
1. All agents must implement `ReactiveAgent` interface
2. Support async message handling
3. Implement health check endpoint
4. Include retry logic
5. Log all decisions for debugging

### Message Protocol
1. Use correlation IDs for request tracking
2. Include timestamps on all messages
3. Implement message versioning
4. Support both sync and async patterns

### Testing Strategy
1. Unit tests for each agent
2. Integration tests for message flows
3. Chaos testing for resilience
4. Load testing for scalability