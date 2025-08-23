"""Simplified VAPI Voice Agent using vapi_server_sdk"""

import os
import re
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from vapi import Vapi
from .base import ReactiveAgent
from ..state import AgentMessage, ReactiveState, create_agent_message
from ...services.call_metadata_service import CallMetadataService

logger = logging.getLogger(__name__)


class VAPIVoiceAgent(ReactiveAgent):
    """Simplified voice agent powered by VAPI platform"""
    
    def __init__(self, agent_id: str = "voice_agent"):
        super().__init__(agent_id)
        self.capabilities = ["voice_call", "phone_booking", "customer_contact", "appointment_scheduling"]
        
        # Initialize VAPI client
        self.vapi_token = self._get_vapi_token()
        self.vapi = Vapi(token=self.vapi_token)
        
        # Initialize call metadata service
        self.call_service = CallMetadataService()
        
        # Configuration
        self.assistant_id = os.getenv("VAPI_ASSISTANT_ID", "ab2953ac-1a50-403a-af6e-710cfa8bec1f")
        self.phone_number_id = self._get_phone_number_id()
        
        logger.info(f"VAPIVoiceAgent initialized with assistant ID: {self.assistant_id}")
    
    async def handle_message(self, message: AgentMessage, state: ReactiveState) -> AgentMessage:
        """Handle incoming voice call requests"""
        logger.info(f"VAPIVoiceAgent received message: {message['message_type']}")
        
        if message["message_type"] == "request":
            return await self._handle_voice_call_request(message, state)
        elif message["message_type"] == "negotiate":
            return await self._handle_negotiation(message, state)
        else:
            logger.warning(f"Unknown message type: {message['message_type']}")
            return create_agent_message(
                from_agent=self.agent_id,
                to_agent=message["from_agent"],
                message_type="error",
                content={"error": f"Unknown message type: {message['message_type']}"},
                correlation_id=message["id"]
            )
    
    async def can_handle_task(self, task: Dict[str, Any]) -> float:
        """Assess capability to handle voice call tasks"""
        request = task.get("request", "").lower()
        
        # High confidence patterns
        high_confidence_patterns = [
            r"\b(call|phone|speak to|contact)\b.*\b(person|customer|client|support|service)\b",
            r"\b(make.*call|give.*call)\b",
            r"\b(call|phone).*\b(restaurant|hotel|business)\b",
            r"\b(call|phone).*\b(book|reserve|make)\b.*\b(table|room|reservation)\b"
        ]
        
        # Medium confidence patterns
        medium_confidence_patterns = [
            r"\b(follow up|check in|confirm)\b",
            r"\b(customer service|support|help desk)\b"
        ]
        
        for pattern in high_confidence_patterns:
            if re.search(pattern, request):
                logger.info(f"High confidence match for pattern: {pattern}")
                return 0.9
                
        for pattern in medium_confidence_patterns:
            if re.search(pattern, request):
                logger.info(f"Medium confidence match for pattern: {pattern}")
                return 0.7
                
        logger.info("Low confidence for non-voice task")
        return 0.2
    
    async def _handle_voice_call_request(self, message: AgentMessage, state: ReactiveState) -> AgentMessage:
        """Process voice call request"""
        try:
            logger.info("Processing voice call request")
            
            # Extract call details and task ID
            request = message["content"].get("query", state["original_request"])
            task_id = message["content"].get("task_id") or state.get("task_id") or state.get("todo_id")
            
            if not task_id:
                raise Exception("Task ID is required for call tracking")
            
            # Convert task_id to UUID if it's a string
            if isinstance(task_id, str):
                task_id = UUID(task_id)
            
            call_details = self._extract_call_details(request)
            
            logger.info(f"Extracted call details: {call_details} for task: {task_id}")
            
            # Validate phone number
            if not call_details.get("phone_number"):
                raise Exception("Phone number is required for voice calls. Please provide a phone number in the task description.")
            
            # Create outbound call using VAPI SDK
            call_result = await self._initiate_call(call_details)
            call_id = call_result["call_id"]
            
            logger.info(f"Call initiated successfully: {call_id}")
            
            # Store call_id -> task_id mapping
            await self.call_service.create_call_mapping(call_id, task_id)
            
            return create_agent_message(
                from_agent=self.agent_id,
                to_agent="supervisor",
                message_type="response",
                content={
                    "call_id": call_id,
                    "task_id": str(task_id),
                    "status": "call_initiated",
                    "phone_number": call_details.get("phone_number"),
                    "assistant_id": self.assistant_id,
                    "call_purpose": call_details.get("purpose", "General inquiry"),
                    "timestamp": datetime.now().isoformat()
                },
                correlation_id=message["id"]
            )
            
        except Exception as e:
            logger.error(f"Error handling voice call request: {e}")
            return create_agent_message(
                from_agent=self.agent_id,
                to_agent="supervisor",
                message_type="error",
                content={"error": str(e), "request": request},
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
                "current_load": 0,
                "estimated_time": self._estimate_completion_time(task)
            },
            correlation_id=message["id"]
        )
    
    def _extract_call_details(self, request: str) -> Dict[str, Any]:
        """Extract call details from natural language request"""
        logger.info(f"Extracting call details from: {request}")
        
        details = {
            "purpose": "General inquiry",
            "phone_number": self._extract_phone_number(request),
            "recipient_name": self._extract_name(request)
        }
        
        # Pattern matching for common purposes
        request_lower = request.lower()
        if "appointment" in request_lower:
            details["purpose"] = "Appointment scheduling"
        elif "booking" in request_lower or "reservation" in request_lower:
            details["purpose"] = "Reservation booking"
        elif "customer service" in request_lower or "support" in request_lower:
            details["purpose"] = "Customer service inquiry"
        elif "follow up" in request_lower:
            details["purpose"] = "Follow-up call"
        
        logger.info(f"Call details extracted: {details}")
        return details
    
    async def _initiate_call(self, call_details: Dict[str, Any]) -> Dict[str, Any]:
        """Initiate outbound call via VAPI SDK"""
        logger.info(f"Initiating call with assistant {self.assistant_id}")
        
        try:
            # Create outbound call using VAPI SDK
            call = self.vapi.calls.create(
                phone_number_id=self.phone_number_id,
                customer={"number": call_details["phone_number"]},
                assistant_id=self.assistant_id
            )
            
            logger.info(f"Call created successfully: {call.id}")
            
            return {
                "call_id": call.id,
                "status": "initiated"
            }
            
        except Exception as e:
            logger.error(f"VAPI call creation failed: {e}")
            raise Exception(f"Failed to initiate call: {str(e)}")
    
    def _extract_phone_number(self, text: str) -> Optional[str]:
        """Extract phone number from text"""
        patterns = [
            r'\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})',
            r'\b\d{10}\b',
            r'\b\d{3}-\d{3}-\d{4}\b',
            r'\(\d{3}\)\s?\d{3}-\d{4}'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                phone_number = match.group(0).strip()
                logger.info(f"Extracted phone number: {phone_number}")
                return phone_number
        
        logger.warning("No phone number found in text")
        return None
    
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract recipient name from text (optional)"""
        patterns = [
            r'\bcall\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+at\b',
            r'\bcontact\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+at\b'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1)
                logger.info(f"Extracted recipient name: {name}")
                return name
        
        return None
    
    def _estimate_completion_time(self, task: Dict[str, Any]) -> int:
        """Estimate completion time in seconds"""
        request = task.get("request", "")
        if len(request) < 50:
            return 300  # 5 minutes for simple calls
        elif len(request) < 150:
            return 600  # 10 minutes for medium calls
        else:
            return 1200  # 20 minutes for complex calls
    
    def _get_vapi_token(self) -> str:
        """Get VAPI authentication token from environment"""
        token = os.getenv("VAPI_TOKEN")
        if not token:
            raise Exception("VAPI_TOKEN environment variable is required")
        return token
    
    def _get_phone_number_id(self) -> str:
        """Get phone number ID for outbound calls"""
        phone_id = os.getenv("VAPI_PHONE_NUMBER_ID")
        if not phone_id:
            raise Exception("VAPI_PHONE_NUMBER_ID environment variable is required")
        return phone_id