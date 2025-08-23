"""Basic Search Agent for Information Retrieval"""

import json
import re
from typing import Dict, Any, List
import httpx
from datetime import datetime

from .base import ReactiveAgent
from ..state import AgentMessage, ReactiveState, create_agent_message


class ReactiveSearchAgent(ReactiveAgent):
    """Search agent that handles research and information gathering tasks"""
    
    def __init__(self, agent_id: str = "search_agent"):
        super().__init__(agent_id)
        self.capabilities = ["research", "information_gathering", "fact_checking", "web_search"]
        
    async def handle_message(self, message: AgentMessage, state: ReactiveState) -> AgentMessage:
        """React to incoming messages"""
        if message["message_type"] == "request":
            return await self._handle_request(message, state)
        elif message["message_type"] == "negotiate":
            return await self._handle_negotiation(message, state)
        else:
            return create_agent_message(
                from_agent=self.agent_id,
                to_agent=message["from_agent"],
                message_type="error",
                content={"error": f"Unknown message type: {message['message_type']}"},
                correlation_id=message["id"]
            )
    
    async def can_handle_task(self, task: Dict[str, Any]) -> float:
        """Assess if this agent can handle the task"""
        request = task.get("request", "").lower()
        
        # High confidence keywords
        high_confidence_patterns = [
            r"\b(research|find|search|look up|what is|how to|compare)\b",
            r"\b(information|data|facts|details)\b",
            r"\b(weather|news|stock|price)\b"
        ]
        
        # Medium confidence patterns
        medium_confidence_patterns = [
            r"\b(tell me|explain|describe)\b",
            r"\b(latest|current|recent)\b"
        ]
        
        for pattern in high_confidence_patterns:
            if re.search(pattern, request):
                return 0.9
                
        for pattern in medium_confidence_patterns:
            if re.search(pattern, request):
                return 0.7
                
        return 0.3  # Default low confidence
    
    async def _handle_request(self, message: AgentMessage, state: ReactiveState) -> AgentMessage:
        """Handle task request"""
        try:
            query = message["content"].get("query", state["original_request"])
            results = await self._perform_search(query)
            
            return create_agent_message(
                from_agent=self.agent_id,
                to_agent="supervisor",
                message_type="response",
                content={
                    "results": results,
                    "confidence": await self.can_handle_task({"request": query}),
                    "query": query,
                    "timestamp": datetime.now().isoformat()
                },
                correlation_id=message["id"]
            )
        except Exception as e:
            return create_agent_message(
                from_agent=self.agent_id,
                to_agent="supervisor",
                message_type="error",
                content={"error": str(e), "query": query},
                correlation_id=message["id"]
            )
    
    async def _handle_negotiation(self, message: AgentMessage, state: ReactiveState) -> AgentMessage:
        """Handle negotiation for task assignment"""
        task = message["content"].get("task", {})
        confidence = await self.can_handle_task(task)
        
        return create_agent_message(
            from_agent=self.agent_id,
            to_agent="supervisor",
            message_type="negotiate",
            content={
                "bid": confidence,
                "capabilities": self.capabilities,
                "current_load": 0,  # Simple implementation
                "estimated_time": self._estimate_completion_time(task)
            },
            correlation_id=message["id"]
        )
    
    async def _perform_search(self, query: str) -> Dict[str, Any]:
        """Perform actual search - simplified implementation for Phase 1"""
        
        # For Phase 1, we'll simulate search results
        # In later phases, integrate with real search APIs
        
        simulated_results = {
            "query": query,
            "results": [
                {
                    "title": f"Search result for: {query}",
                    "summary": f"This is a simulated search result for the query '{query}'. In a real implementation, this would contain actual search results from web APIs.",
                    "url": "https://example.com/search-result",
                    "confidence": 0.85
                }
            ],
            "total_results": 1,
            "search_time_ms": 150,
            "sources": ["simulated_search_engine"]
        }
        
        # Simple pattern matching for common queries
        query_lower = query.lower()
        
        if "weather" in query_lower:
            simulated_results["results"] = [{
                "title": "Weather Information",
                "summary": "Current weather conditions and forecast. This is a simulated response - integrate with weather API in production.",
                "temperature": "22°C",
                "condition": "Partly cloudy",
                "url": "https://weather.example.com"
            }]
        
        elif "time" in query_lower:
            simulated_results["results"] = [{
                "title": "Current Time",
                "summary": f"The current time is {datetime.now().strftime('%H:%M:%S')}",
                "timestamp": datetime.now().isoformat(),
                "url": "https://time.example.com"
            }]
        
        elif any(word in query_lower for word in ["python", "programming", "code"]):
            simulated_results["results"] = [{
                "title": "Programming Information",
                "summary": f"Information about {query}. This would contain relevant programming resources and documentation.",
                "category": "programming",
                "url": "https://docs.example.com"
            }]
        
        return simulated_results
    
    def _estimate_completion_time(self, task: Dict[str, Any]) -> int:
        """Estimate completion time in seconds"""
        # Simple heuristic based on query complexity
        request = task.get("request", "")
        
        if len(request) < 50:
            return 5  # Simple queries
        elif len(request) < 150:
            return 10  # Medium queries
        else:
            return 20  # Complex queries