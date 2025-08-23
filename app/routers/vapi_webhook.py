"""VAPI Webhook router for handling voice call events"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..services.call_metadata_service import CallMetadataService
from ..dependencies import get_call_metadata_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vapi", tags=["vapi"])


class VAPIMessage(BaseModel):
    """VAPI webhook message structure"""
    message: Dict[str, Any]


@router.post("/webhook")
async def vapi_webhook(
    payload: VAPIMessage,
    call_service: CallMetadataService = Depends(get_call_metadata_service)
):
    """Handle VAPI webhook events"""
    try:
        message = payload.message
        message_type = message.get("type")
        call_data = message.get("call", {})
        call_id = call_data.get("id")
        
        logger.info(f"Received VAPI webhook: type={message_type}, call_id={call_id}")
        logger.debug(f"Full webhook payload: {payload.model_dump()}")
        
        # Skip processing if no call_id
        if not call_id:
            logger.warning("No call_id in webhook payload, skipping")
            return {"status": "ignored", "reason": "no_call_id"}
        
        # Process different event types
        if message_type == "status-update":
            await _handle_status_update(message, call_service)
        elif message_type == "hang":
            await _handle_call_end(message, call_service)
        elif message_type == "end-of-call-report":
            await _handle_end_of_call_report(message, call_service)
        elif message_type == "transcript":
            await _handle_transcript(message, call_service)
        elif message_type == "function-call":
            await _handle_function_call(message, call_service)
        else:
            logger.info(f"Unhandled message type: {message_type}")
        
        return {"status": "processed", "message_type": message_type}
        
    except Exception as e:
        logger.error(f"Error processing VAPI webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")


async def _handle_status_update(message: Dict[str, Any], call_service: CallMetadataService):
    """Handle status update events"""
    call_data = message.get("call", {})
    call_id = call_data.get("id")
    status = call_data.get("status")
    
    logger.info(f"Call status update: call_id={call_id}, status={status}")
    
    if status:
        await call_service.update_call_status(call_id, status)


async def _handle_call_end(message: Dict[str, Any], call_service: CallMetadataService):
    """Handle call hang/end events"""
    call_data = message.get("call", {})
    call_id = call_data.get("id")
    
    logger.info(f"Call ended: call_id={call_id}")
    
    # Update call status
    await call_service.update_call_status(call_id, "completed")
    
    # Get associated task and mark as complete
    task_id = await call_service.get_task_id_by_call_id(call_id)
    if task_id:
        success = await call_service.complete_task(task_id)
        if success:
            logger.info(f"Task {task_id} completed after call {call_id} ended")
        else:
            logger.error(f"Failed to complete task {task_id} after call {call_id} ended")
    else:
        logger.warning(f"No task found for completed call {call_id}")


async def _handle_end_of_call_report(message: Dict[str, Any], call_service: CallMetadataService):
    """Handle end-of-call report events"""
    call_data = message.get("call", {})
    call_id = call_data.get("id")
    
    # Extract summary and other call details
    summary = message.get("summary")
    
    logger.info(f"End of call report: call_id={call_id}")
    logger.info(f"Call summary: {summary}")
    
    # Update call status to completed
    await call_service.update_call_status(call_id, "completed")
    
    # Complete the associated task
    task_id = await call_service.get_task_id_by_call_id(call_id)
    if task_id:
        success = await call_service.complete_task(task_id)
        if success:
            logger.info(f"Task {task_id} completed with call report for call {call_id}")
        else:
            logger.error(f"Failed to complete task {task_id} with call report for call {call_id}")


async def _handle_transcript(message: Dict[str, Any], call_service: CallMetadataService):
    """Handle transcript events (optional logging)"""
    call_data = message.get("call", {})
    call_id = call_data.get("id")
    transcript = message.get("transcript", {})
    
    role = transcript.get("role")
    content = transcript.get("content")
    
    logger.debug(f"Call transcript - call_id={call_id}, role={role}, content={content}")


async def _handle_function_call(message: Dict[str, Any], call_service: CallMetadataService):
    """Handle function call events"""
    call_data = message.get("call", {})
    call_id = call_data.get("id")
    function_call = message.get("functionCall", {})
    
    function_name = function_call.get("name")
    parameters = function_call.get("parameters")
    
    logger.info(f"Function call - call_id={call_id}, function={function_name}, params={parameters}")