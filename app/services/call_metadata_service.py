"""Service for managing VAPI call metadata and task tracking"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from ..supabase_client import supabase
from ..schemas import ItemState

logger = logging.getLogger(__name__)


class CallMetadataService:
    """Service for managing call_id to task_id mappings and call status"""
    
    def __init__(self):
        self.supabase = supabase
    
    async def create_call_mapping(self, call_id: str, task_id: UUID) -> Dict[str, Any]:
        """Create a mapping between call_id and task_id"""
        try:
            result = self.supabase.table("call_metadata").insert({
                "call_id": call_id,
                "task_id": str(task_id),
                "status": "initiated"
            }).execute()
            
            logger.info(f"Created call mapping: call_id={call_id}, task_id={task_id}")
            return result.data[0] if result.data else {}
            
        except Exception as e:
            logger.error(f"Error creating call mapping: {e}")
            raise
    
    async def get_task_id_by_call_id(self, call_id: str) -> Optional[UUID]:
        """Get task_id from call_id"""
        try:
            result = self.supabase.table("call_metadata").select("task_id").eq("call_id", call_id).single().execute()
            
            if result.data:
                task_id = result.data["task_id"]
                logger.info(f"Found task_id {task_id} for call_id {call_id}")
                return UUID(task_id)
            
            logger.warning(f"No task found for call_id {call_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting task_id for call_id {call_id}: {e}")
            return None
    
    async def update_call_status(self, call_id: str, status: str) -> bool:
        """Update the status of a call"""
        try:
            result = self.supabase.table("call_metadata").update({"status": status}).eq("call_id", call_id).execute()
            
            if result.data:
                logger.info(f"Updated call {call_id} status to {status}")
                return True
            
            logger.warning(f"No call found to update: call_id={call_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error updating call status: {e}")
            return False
    
    async def complete_task(self, task_id: UUID) -> bool:
        """Mark a task as completed"""
        try:
            result = self.supabase.table("items").update({
                "state": ItemState.COMPLETED.value
            }).eq("id", str(task_id)).execute()
            
            if result.data:
                logger.info(f"Task {task_id} marked as completed")
                return True
            
            logger.warning(f"No task found to complete: task_id={task_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error completing task {task_id}: {e}")
            return False