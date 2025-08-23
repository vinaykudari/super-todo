"""Task Analyzer for determining if tasks should be processed by AI agents"""

import re
from typing import Dict, Any, Optional


class TaskAnalyzer:
    """Analyzes tasks to determine if they should be processed by AI agents"""
    
    def __init__(self):
        # Patterns that indicate AI-suitable tasks
        self.ai_patterns = {
            "research": [
                r"\b(research|find|look up|investigate|discover)\b",
                r"\b(what is|how to|why does|when did|where can)\b",
                r"\b(compare|analyze|evaluate|study)\b",
                r"\b(best practices|pros and cons|advantages|trends)\b",
                r"\b(latest|recent|current|new)\b.*\b(developments?|breakthroughs?|advances?)\b",
                r"\b(find|get|gather)\b.*\b(information|data|details)\b"
            ],
            "information_gathering": [
                r"\b(weather|temperature|forecast)\b",
                r"\b(news|latest|current events)\b", 
                r"\b(stock price|market|financial)\b",
                r"\b(time|date|schedule)\b",
                r"\b(recent|latest|current)\b.*\b(updates?|news|info)\b"
            ],
            "web_search": [
                r"\b(search for|google|find online)\b",
                r"\b(website|url|link)\b",
                r"\b(reviews|ratings|feedback)\b"
            ],
            "booking": [
                r"\b(book|reserve|schedule)\b",
                r"\b(appointment|meeting|call)\b",
                r"\b(restaurant|hotel|flight)\b"
            ],
            "automation": [
                r"\b(send email|create document)\b",
                r"\b(fill form|submit application)\b",
                r"\b(download|upload|backup)\b"
            ]
        }
        
        # Patterns that indicate NOT suitable for AI
        self.non_ai_patterns = [
            r"\b(buy|purchase|pay)\b.*\b(grocery|milk|bread)\b",  # Simple shopping
            r"\b(call|text|message)\b.*\b(mom|dad|friend)\b",     # Personal communication
            r"\b(remember|remind me)\b",                          # Simple reminders
            r"\b(pick up|drop off)\b"                            # Physical tasks
        ]
    
    def should_process_with_ai(self, title: str, description: Optional[str] = None) -> Dict[str, Any]:
        """
        Determine if a task should be processed by AI agents
        
        Returns:
            Dict with 'suitable', 'confidence', 'task_type', and 'reasoning'
        """
        
        # Combine title and description for analysis
        text = f"{title} {description or ''}".lower()
        
        # Check for explicit non-AI patterns first
        for pattern in self.non_ai_patterns:
            if re.search(pattern, text):
                return {
                    "suitable": False,
                    "confidence": 0.9,
                    "task_type": "manual",
                    "reasoning": f"Contains pattern indicating manual task: {pattern}"
                }
        
        # Check for AI-suitable patterns
        best_match = None
        best_confidence = 0.0
        
        for task_type, patterns in self.ai_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    # Calculate confidence based on pattern specificity and text length
                    confidence = self._calculate_confidence(pattern, text)
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = {
                            "suitable": True,
                            "confidence": confidence,
                            "task_type": task_type,
                            "reasoning": f"Matches {task_type} pattern: {pattern}"
                        }
        
        # If we found a good match, return it
        if best_match and best_confidence > 0.6:
            return best_match
        
        # Default: not suitable for AI if no clear patterns match
        return {
            "suitable": False,
            "confidence": 0.3,
            "task_type": "unknown",
            "reasoning": "No clear AI-suitable patterns detected"
        }
    
    def _calculate_confidence(self, pattern: str, text: str) -> float:
        """Calculate confidence score for a pattern match"""
        # Base confidence for any match
        confidence = 0.7
        
        # Boost confidence for more specific patterns
        if len(pattern) > 20:  # Complex patterns
            confidence += 0.15
        
        # Boost confidence for longer, more detailed text
        if len(text) > 50:
            confidence += 0.1
        
        # Cap at 0.95 to leave room for uncertainty
        return min(confidence, 0.95)
    
    def get_suggested_agents(self, task_type: str) -> list:
        """Get suggested agents based on task type"""
        agent_mapping = {
            "research": ["search_agent"],
            "information_gathering": ["search_agent"],
            "web_search": ["search_agent"],
            "booking": ["browser_agent", "search_agent"],
            "automation": ["browser_agent"]
        }
        
        return agent_mapping.get(task_type, ["search_agent"])
    
    def create_ai_request(self, title: str, description: Optional[str], task_type: str) -> str:
        """Create a formatted AI request string"""
        base_request = f"Task: {title}"
        
        if description:
            base_request += f"\nDescription: {description}"
        
        # Add task type specific instructions
        if task_type == "research":
            base_request += "\nPlease research this topic and provide comprehensive information with sources."
        elif task_type == "information_gathering":
            base_request += "\nPlease find the latest information about this topic."
        elif task_type == "booking":
            base_request += "\nPlease help with booking or scheduling this request."
        else:
            base_request += f"\nPlease process this {task_type} request."
        
        return base_request