"""Browser Agent for Web Automation Tasks"""

import re
from typing import Dict, Any, List
from datetime import datetime

from .base import ReactiveAgent
from ..state import AgentMessage, ReactiveState, create_agent_message
from ...services.browser_service import BrowserService, BrowserTaskRequest


class ReactiveBrowserAgent(ReactiveAgent):
    """Browser agent that handles web automation and browser-based tasks"""
    
    def __init__(self, agent_id: str = "browser_agent"):
        super().__init__(agent_id)
        self.capabilities = ["web_automation", "browser_interaction", "form_filling", "navigation", "scraping"]
        self.browser_service = BrowserService()
        
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
        
        # High confidence patterns for browser tasks
        high_confidence_patterns = [
            r"\b(navigate|browse|visit|go to|open)\b.*\b(website|site|url|page)\b",
            r"\b(click|press|tap|select)\b.*\b(button|link|element)\b",
            r"\b(fill|enter|type|input)\b.*\b(form|field|text)\b",
            r"\b(screenshot|capture|save)\b.*\b(page|screen)\b",
            r"\b(login|sign in|authenticate)\b",
            r"\b(download|upload)\b.*\b(file|document)\b",
            r"\b(automate|automation)\b.*\b(web|browser)\b",
            r"\b(return|cancel|refund)\b.*\b(order|purchase|item)\b",
            r"\b(amazon|ebay|shopping|e-commerce)\b",
            r"\b(scrape|extract|get)\b.*\b(data|information|content)\b"
        ]
        
        # Medium confidence patterns
        medium_confidence_patterns = [
            r"\b(check|verify|confirm)\b.*\b(online|website)\b",
            r"\b(submit|send)\b.*\b(form|application)\b",
            r"\b(interact|use)\b.*\b(website|web)\b"
        ]
        
        for pattern in high_confidence_patterns:
            if re.search(pattern, request):
                return 0.9
                
        for pattern in medium_confidence_patterns:
            if re.search(pattern, request):
                return 0.7
                
        # Check for specific domains mentioned
        if re.search(r"\b[a-zA-Z0-9-]+\.(com|org|net|edu|gov)\b", request):
            return 0.6
            
        return 0.2  # Default low confidence
    
    async def _handle_request(self, message: AgentMessage, state: ReactiveState) -> AgentMessage:
        """Handle browser automation request"""
        try:
            query = message["content"].get("query", state["original_request"])
            task_id = message["content"].get("task_id", state["todo_id"])
            
            # Create browser task request
            browser_request = self._create_browser_request(query, task_id)
            
            # Execute browser task
            result = await self.browser_service.run_task(browser_request)
            
            # Format response based on result type
            if hasattr(result, 'task_id'):  # BrowserTaskCreated (async execution)
                response_content = {
                    "status": "started",
                    "task_id": result.task_id,
                    "session_id": result.session_id,
                    "live_url": result.live_url,
                    "message": "Browser task started. Check live URL for real-time progress.",
                    "query": query,
                    "timestamp": datetime.now().isoformat()
                }
            else:  # BrowserTaskResult (sync execution)
                response_content = {
                    "status": "completed" if result.is_success else "failed",
                    "result": result.done_output,
                    "steps_count": len(result.steps) if result.steps else 0,
                    "session_id": result.session_id,
                    "live_url": result.live_url,
                    "query": query,
                    "timestamp": datetime.now().isoformat()
                }
            
            return create_agent_message(
                from_agent=self.agent_id,
                to_agent="supervisor",
                message_type="response",
                content=response_content,
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
    
    def _create_browser_request(self, query: str, item_id: str) -> BrowserTaskRequest:
        """Create browser task request from query"""
        # Extract allowed domains from query if mentioned
        allowed_domains = self._extract_domains(query)
        
        # Determine if we should save browser data
        save_browser_data = self._should_save_browser_data(query)
        
        # Create the request
        return BrowserTaskRequest(
            task=query,
            item_id=item_id,
            allowed_domains=allowed_domains,
            wait=False,  # Always use async for LangGraph integration
            save_browser_data=save_browser_data
        )
    
    def _extract_domains(self, query: str) -> List[str]:
        """Extract allowed domains from query"""
        domains = []
        
        # Common e-commerce sites
        ecommerce_patterns = {
            r"\bamazon\b": ["https://amazon.com/", "https://*.amazon.com/"],
            r"\bebay\b": ["https://ebay.com/", "https://*.ebay.com/"],
            r"\bwalmart\b": ["https://walmart.com/", "https://*.walmart.com/"],
            r"\btarget\b": ["https://target.com/", "https://*.target.com/"],
        }
        
        query_lower = query.lower()
        for pattern, domain_list in ecommerce_patterns.items():
            if re.search(pattern, query_lower):
                domains.extend(domain_list)
        
        # Extract explicit URLs from query
        url_pattern = r"https?://[^\s]+"
        found_urls = re.findall(url_pattern, query)
        for url in found_urls:
            # Extract base domain and add wildcard
            domain_match = re.match(r"(https?://[^/]+)", url)
            if domain_match:
                base_domain = domain_match.group(1)
                domains.append(f"{base_domain}/")
                # Add wildcard subdomain pattern
                domain_parts = base_domain.split("://")
                if len(domain_parts) == 2:
                    domains.append(f"{domain_parts[0]}://*.{domain_parts[1]}/")
        
        return domains if domains else None
    
    def _should_save_browser_data(self, query: str) -> bool:
        """Determine if browser data should be saved"""
        # Save data for queries that might need user interaction
        save_patterns = [
            r"\b(login|sign in|authenticate)\b",
            r"\b(return|refund|cancel)\b.*\b(order|purchase)\b",
            r"\b(shopping|checkout|cart)\b",
            r"\buser will take over\b",
            r"\b(fill|complete)\b.*\b(form|application)\b"
        ]
        
        query_lower = query.lower()
        for pattern in save_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def _estimate_completion_time(self, task: Dict[str, Any]) -> int:
        """Estimate completion time in seconds"""
        request = task.get("request", "")
        
        # Browser tasks typically take longer
        if "login" in request.lower() or "return" in request.lower():
            return 60  # Complex interactions
        elif "navigate" in request.lower() or "click" in request.lower():
            return 30  # Medium complexity
        else:
            return 20  # Simple tasks