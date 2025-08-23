"""Base Agent Interface for Reactive Network"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from ..state import AgentMessage, ReactiveState


class ReactiveAgent(ABC):
    """Base class for all reactive agents"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.capabilities: List[str] = []
        self.status = "available"
        
    @abstractmethod
    async def handle_message(self, message: AgentMessage, state: ReactiveState) -> AgentMessage:
        """Handle incoming messages from other agents"""
        pass
        
    @abstractmethod
    async def can_handle_task(self, task: Dict[str, Any]) -> float:
        """Return confidence score (0-1) for handling this task"""
        pass
        
    def get_capabilities(self) -> List[str]:
        """Return list of capabilities this agent supports"""
        return self.capabilities
        
    def get_status(self) -> Dict[str, Any]:
        """Return current agent status"""
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "capabilities": self.capabilities
        }