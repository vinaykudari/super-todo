"""Orchestrator API endpoints"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends

from ..orchestrator import OrchestratorSupervisor
from ..services.items_service import ItemsService
from ..dependencies import get_items_service
from ..schemas import ItemUpdateState, TaskAnalysisResponse, OrchestrationResponse
from ..config import AI_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])




# Global supervisor instance (in production, use dependency injection)
_supervisor = None


def get_supervisor() -> OrchestratorSupervisor:
    """Get orchestrator supervisor instance"""
    global _supervisor
    if _supervisor is None:
        _supervisor = OrchestratorSupervisor()
    return _supervisor


@router.post("/analyze/{item_id}", response_model=TaskAnalysisResponse)
async def analyze_task(
    item_id: str,
    background_tasks: BackgroundTasks,
    items_service: ItemsService = Depends(get_items_service)
) -> TaskAnalysisResponse:
    """
    Analyze a pending task to determine if it should be processed by AI agents.
    If suitable, automatically starts orchestration and updates status to 'processing'.
    """
    
    try:
        # Get the item
        item = items_service.get_item_with_attachments(item_id)
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Only analyze pending items
        if item.state != "pending":
            raise HTTPException(
                status_code=400, 
                detail=f"Item is not in pending state. Current state: {item.state}"
            )
        
        # Get supervisor and analyze task
        supervisor = get_supervisor()
        task_request = f"{item.title} - {item.description or ''}"
        
        # Use task analyzer directly for analysis
        analysis = supervisor.task_analyzer.should_process_with_ai(
            item.title, 
            item.description
        )
        
        orchestration_started = False
        
        # If suitable for AI processing, start orchestration
        if analysis['suitable'] and analysis['confidence'] > AI_CONFIDENCE_THRESHOLD:
            # Update item status to processing
            items_service.update_item_state(item_id, ItemUpdateState(state="processing"))
            
            # Start orchestration in background
            background_tasks.add_task(
                run_orchestration,
                supervisor,
                item_id,
                task_request,
                item.title,
                item.description,
                items_service
            )
            
            orchestration_started = True
            logger.info(f"Started orchestration for item {item_id} (confidence: {analysis['confidence']})")
        else:
            logger.info(f"Item {item_id} not suitable for AI processing: {analysis['reasoning']}")
        
        return TaskAnalysisResponse(
            item_id=item_id,
            suitable=analysis['suitable'],
            confidence=analysis['confidence'],
            task_type=analysis['task_type'],
            reasoning=analysis['reasoning'],
            orchestration_started=orchestration_started
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze task: {str(e)}")


@router.post("/batch-analyze", response_model=List[TaskAnalysisResponse])
async def batch_analyze_pending_tasks(
    background_tasks: BackgroundTasks,
    items_service: ItemsService = Depends(get_items_service)
) -> List[TaskAnalysisResponse]:
    """
    Analyze all pending tasks and start orchestration for suitable ones.
    This can be called periodically to process new tasks automatically.
    """
    
    try:
        # Get all pending items
        pending_items = items_service.list_items(state="pending", limit=50)
        
        if not pending_items:
            return []
        
        supervisor = get_supervisor()
        results = []
        
        for item in pending_items:
            try:
                # Analyze each item
                task_request = f"{item.title} - {item.description or ''}"
                analysis = supervisor.task_analyzer.should_process_with_ai(
                    item.title, 
                    item.description
                )
                
                orchestration_started = False
                
                # Start orchestration if suitable
                if analysis['suitable'] and analysis['confidence'] > AI_CONFIDENCE_THRESHOLD:
                    # Update to processing
                    items_service.update_item_state(item.id, ItemUpdateState(state="processing"))
                    
                    # Start orchestration
                    background_tasks.add_task(
                        run_orchestration,
                        supervisor,
                        item.id,
                        task_request,
                        item.title,
                        item.description,
                        items_service
                    )
                    
                    orchestration_started = True
                    logger.info(f"Batch: Started orchestration for item {item.id}")
                
                results.append(TaskAnalysisResponse(
                    item_id=item.id,
                    suitable=analysis['suitable'],
                    confidence=analysis['confidence'],
                    task_type=analysis['task_type'],
                    reasoning=analysis['reasoning'],
                    orchestration_started=orchestration_started
                ))
                
            except Exception as e:
                logger.error(f"Error analyzing item {item.id}: {e}")
                results.append(TaskAnalysisResponse(
                    item_id=item.id,
                    suitable=False,
                    confidence=0.0,
                    task_type="error",
                    reasoning=f"Analysis failed: {str(e)}",
                    orchestration_started=False
                ))
        
        logger.info(f"Batch analysis completed: {len(results)} items processed")
        return results
        
    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")


@router.get("/items/{item_id}/status")
async def get_orchestration_status(
    item_id: str,
    items_service: ItemsService = Depends(get_items_service)
) -> Dict[str, Any]:
    """Get orchestration status for an item"""
    
    try:
        item = items_service.get_item_with_attachments(item_id)
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Return comprehensive status
        return {
            "item_id": item_id,
            "status": item.state,
            "orchestration_status": getattr(item, "orchestration_status", "pending"),
            "orchestration_result": getattr(item, "orchestration_result", None),
            "ai_request": getattr(item, "ai_request", None),
            "last_updated": item.updated_at,
            "is_ai_processable": item.state == "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting orchestration status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


async def run_orchestration(
    supervisor: OrchestratorSupervisor,
    item_id: str,
    request: str,
    title: str,
    description: str,
    items_service: ItemsService
) -> None:
    """Background task to run orchestration"""
    
    try:
        logger.info(f"Starting background orchestration for item {item_id}")
        
        # Run orchestration with enhanced parameters
        result = await supervisor.execute_task(item_id, request, title, description)
        
        # Update item based on result
        if result["execution_status"] == "completed":
            # Extract results
            search_results = result["results"].get("search_agent", {})
            aggregated = result["results"].get("aggregated", {})
            task_analysis = result.get("task_analysis", {})
            
            # Create summary
            summary = create_result_summary(search_results, aggregated, task_analysis)
            
            # Update item status to completed
            items_service.update_item_state(item_id, ItemUpdateState(state="completed"))
            
            # Store orchestration result in item description
            current_item = items_service.get_item_with_attachments(item_id)
            updated_description = f"{current_item.description or ''}\n\n**AI Task Result:**\n{summary}"
            
            logger.info(f"Orchestration completed successfully for item {item_id}")
            
        else:
            # Handle failure
            error_summary = create_error_summary(result["errors"])
            logger.error(f"Orchestration failed for item {item_id}: {error_summary}")
            
            # Reset item status to pending (so it can be retried)
            items_service.update_item_state(item_id, ItemUpdateState(state="pending"))
            
    except Exception as e:
        logger.error(f"Background orchestration failed: {e}")
        
        # Reset item status
        try:
            items_service.update_item_state(item_id, ItemUpdateState(state="pending"))
        except:
            pass  # Don't fail on cleanup


def create_result_summary(
    search_results: Dict[str, Any], 
    aggregated: Dict[str, Any],
    task_analysis: Dict[str, Any]
) -> str:
    """Create human-readable summary of orchestration results"""
    
    summary = f"**Task Analysis:** {task_analysis.get('task_type', 'unknown')} task (confidence: {task_analysis.get('confidence', 0):.0%})\n\n"
    
    if not search_results:
        return summary + "Task completed but no detailed results available."
    
    results = search_results.get("results", {}).get("results", [])
    
    if not results:
        return summary + "Search completed but no results found."
    
    # Create summary from first result
    first_result = results[0]
    summary += f"**Search Results:**\n"
    summary += f"- {first_result.get('title', 'Result')}\n"
    summary += f"- {first_result.get('summary', 'No summary available')}\n"
    
    if first_result.get('url'):
        summary += f"- Source: {first_result['url']}\n"
    
    summary += f"\nCompleted at: {aggregated.get('completed_at', 'Unknown time')}"
    
    return summary


def create_error_summary(errors: list) -> str:
    """Create human-readable error summary"""
    if not errors:
        return "Unknown error occurred"
    
    return f"Orchestration failed: {errors[0].get('error', 'Unknown error')}"