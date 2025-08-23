"""Orchestrator Supervisor using LangGraph"""

import logging
from datetime import datetime
from typing import Dict, Any, Literal

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from .state import ReactiveState, ExecutionStatus, create_agent_message, add_message_to_state, update_agent_state
from .agents.search import ReactiveSearchAgent
from .task_analyzer import TaskAnalyzer

logger = logging.getLogger(__name__)


class OrchestratorSupervisor:
    """Reactive supervisor that coordinates agent network"""
    
    def __init__(self):
        self.graph: CompiledStateGraph = self._build_graph()
        self.agents = {
            "search_agent": ReactiveSearchAgent()
        }
        self.task_analyzer = TaskAnalyzer()
        
    def _build_graph(self) -> CompiledStateGraph:
        """Build LangGraph workflow"""
        workflow = StateGraph(ReactiveState)
        
        # Add nodes
        workflow.add_node("analyze_task", self.analyze_task)
        workflow.add_node("initialize", self.initialize_network)
        workflow.add_node("broadcast_task", self.broadcast_task)
        workflow.add_node("monitor_agents", self.monitor_agents)
        workflow.add_node("aggregate_results", self.aggregate_results)
        workflow.add_node("complete_task", self.complete_task)
        
        # Define flow
        workflow.set_entry_point("analyze_task")
        workflow.add_conditional_edges(
            "analyze_task",
            self.should_process_task,
            {
                "process": "initialize",
                "skip": "complete_task"
            }
        )
        workflow.add_edge("initialize", "broadcast_task")
        workflow.add_edge("broadcast_task", "monitor_agents")
        
        # Conditional routing from monitoring
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
    
    async def initialize_network(self, state: ReactiveState) -> ReactiveState:
        """Initialize the reactive agent network"""
        logger.info(f"Initializing network for task: {state['todo_id']}")
        
        state["execution_status"] = ExecutionStatus.RUNNING
        state["last_activity"] = datetime.now()
        
        # Initialize agent states
        for agent_id in state["active_agents"]:
            update_agent_state(state, agent_id, {
                "status": "ready",
                "initialized_at": datetime.now()
            })
        
        logger.info(f"Network initialized with agents: {state['active_agents']}")
        return state
    
    async def broadcast_task(self, state: ReactiveState) -> ReactiveState:
        """Broadcast task to relevant agents"""
        logger.info(f"Broadcasting task to agents: {state['active_agents']}")
        
        # For Phase 1, directly assign to search agent
        search_agent = self.agents.get("search_agent")
        if search_agent:
            # Create request message
            request_message = create_agent_message(
                from_agent="supervisor",
                to_agent="search_agent",
                message_type="request",
                content={
                    "query": state["original_request"],
                    "task_type": "search",
                    "priority": "normal"
                }
            )
            
            # Add message to state
            add_message_to_state(state, request_message)
            
            # Process message with agent
            try:
                response = await search_agent.handle_message(request_message, state)
                add_message_to_state(state, response)
                
                # Update agent state
                update_agent_state(state, "search_agent", {
                    "status": "processing",
                    "started_at": datetime.now()
                })
                
            except Exception as e:
                logger.error(f"Error processing with search agent: {e}")
                state["errors"].append({
                    "agent_id": "search_agent",
                    "error": str(e),
                    "timestamp": datetime.now()
                })
        
        return state
    
    async def monitor_agents(self, state: ReactiveState) -> ReactiveState:
        """Monitor agent progress"""
        logger.debug("Monitoring agent progress")
        
        # Process any pending messages
        for message in state["message_queue"]:
            if message["to_agent"] == "supervisor" and message["message_type"] == "response":
                # Agent completed task
                agent_id = message["from_agent"]
                results = message["content"]
                
                state["results"][agent_id] = results
                
                update_agent_state(state, agent_id, {
                    "status": "completed",
                    "completed_at": datetime.now()
                })
                
                logger.info(f"Agent {agent_id} completed task")
        
        state["last_activity"] = datetime.now()
        return state
    
    def check_completion(self, state: ReactiveState) -> Literal["continue", "aggregate", "error"]:
        """Check if orchestration should continue or complete"""
        
        # Check for errors
        if state["errors"]:
            logger.error(f"Errors detected: {len(state['errors'])}")
            return "error"
        
        # Check if all agents completed
        completed_agents = []
        for agent_id in state["active_agents"]:
            agent_state = state["agent_states"].get(agent_id, {})
            if agent_state.get("status") == "completed":
                completed_agents.append(agent_id)
        
        if len(completed_agents) == len(state["active_agents"]):
            logger.info("All agents completed - ready to aggregate")
            return "aggregate"
        
        # Continue monitoring
        return "continue"
    
    async def aggregate_results(self, state: ReactiveState) -> ReactiveState:
        """Aggregate results from all agents"""
        logger.info("Aggregating results from agents")
        
        state["execution_status"] = ExecutionStatus.COMPLETING
        
        # Simple aggregation for Phase 1
        aggregated = {
            "total_agents": len(state["active_agents"]),
            "successful_agents": len([a for a in state["active_agents"] if a in state["results"]]),
            "results": state["results"],
            "completed_at": datetime.now()
        }
        
        state["results"]["aggregated"] = aggregated
        state["consensus_reached"] = True
        
        logger.info(f"Results aggregated: {aggregated['successful_agents']}/{aggregated['total_agents']} agents successful")
        return state
    
    async def complete_task(self, state: ReactiveState) -> ReactiveState:
        """Complete the orchestration"""
        logger.info(f"Completing orchestration for task: {state['todo_id']}")
        
        if state["errors"]:
            state["execution_status"] = ExecutionStatus.FAILED
            logger.error(f"Task failed with {len(state['errors'])} errors")
        else:
            state["execution_status"] = ExecutionStatus.COMPLETED
            logger.info("Task completed successfully")
        
        # Final state update
        state["last_activity"] = datetime.now()
        
        return state
    
    async def analyze_task(self, state: ReactiveState) -> ReactiveState:
        """Analyze if task should be processed by AI agents"""
        logger.info(f"Analyzing task: {state['todo_id']}")
        
        # Extract title and description from original request
        # For now, we'll use the whole request as the title
        request = state["original_request"]
        
        # Analyze with TaskAnalyzer
        analysis = self.task_analyzer.should_process_with_ai(request)
        
        # Store analysis in state
        state["task_analysis"] = analysis
        
        logger.info(f"Task analysis: suitable={analysis['suitable']}, "
                   f"confidence={analysis['confidence']}, type={analysis['task_type']}")
        
        if analysis['suitable']:
            # Create AI request for processing
            ai_request = self.task_analyzer.create_ai_request(
                request, None, analysis['task_type']
            )
            state["ai_request"] = ai_request
            
            # Get suggested agents
            suggested_agents = self.task_analyzer.get_suggested_agents(analysis['task_type'])
            state["active_agents"] = suggested_agents
            
            logger.info(f"Task marked for AI processing with agents: {suggested_agents}")
        
        return state
    
    def should_process_task(self, state: ReactiveState) -> Literal["process", "skip"]:
        """Decide if task should be processed by agents"""
        analysis = state.get("task_analysis", {})
        
        # Process if suitable and confidence > threshold
        if analysis.get("suitable", False) and analysis.get("confidence", 0) > 0.6:
            return "process"
        else:
            logger.info(f"Skipping task - not suitable for AI processing: {analysis.get('reasoning')}")
            return "skip"
    
    async def execute_task(self, todo_id: str, request: str, title: str = None, description: str = None) -> ReactiveState:
        """Execute a task through the reactive network"""
        from .state import create_initial_state
        
        initial_state = create_initial_state(todo_id, request)
        
        logger.info(f"Starting orchestration for task: {todo_id}")
        logger.info(f"Request: {request}")
        
        try:
            # Run the graph
            result = await self.graph.ainvoke(initial_state)
            
            logger.info(f"Orchestration completed with status: {result['execution_status']}")
            return result
            
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            # Return failed state
            initial_state["execution_status"] = ExecutionStatus.FAILED
            initial_state["errors"].append({
                "error": str(e),
                "timestamp": datetime.now()
            })
            return initial_state