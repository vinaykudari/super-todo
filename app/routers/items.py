from typing import Optional, List
from fastapi import APIRouter, Depends, Query, UploadFile, File, BackgroundTasks
from ..services.items_service import ItemsService
from ..schemas import ItemCreate, Item, ItemUpdateState, ItemWithAttachments, Attachment
from ..config import BASE_URL, ORCHESTRATOR_ENABLED

# DI
try:
    from ..dependencies import get_items_service  # type: ignore
except Exception:
    def get_items_service() -> ItemsService:
        return ItemsService()

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=Item)
async def create_item(
    payload: ItemCreate,
    background_tasks: BackgroundTasks,
    items_service: ItemsService = Depends(get_items_service),
):
    # Create the item first
    item = await items_service.create_item(payload)
    
    # Trigger orchestrator analysis in background (if enabled)
    if ORCHESTRATOR_ENABLED:
        background_tasks.add_task(trigger_orchestrator_analysis, item.id)
    
    return item


@router.get("", response_model=List[Item])
async def get_items(
    state: Optional[str] = Query(default=None, description="Filter by state"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),  # preserved for compatibility; ignored
    cursor: Optional[str] = Query(default=None, description="Convex pagination cursor (updated_at as string)"),
    items_service: ItemsService = Depends(get_items_service),
):
    """
    Retrieve items from Convex (not Supabase).
    - Ordered by updated_at DESC.
    - Optional state filter.
    - Optional cursor-based pagination.
    """
    return await items_service.get_items(state=state, limit=limit, offset=offset, cursor=cursor)


@router.get("/{item_id}", response_model=ItemWithAttachments)
async def get_item_with_attachments(
    item_id: str,
    items_service: ItemsService = Depends(get_items_service),
):
    return await items_service.get_item_with_attachments(item_id)


@router.patch("/{item_id}/state", response_model=Item)
async def update_item_state(
    item_id: str,
    payload: ItemUpdateState,
    items_service: ItemsService = Depends(get_items_service),
):
    return await items_service.update_item_state(item_id, payload)


@router.post("/{item_id}/attachments", response_model=Attachment)
async def add_attachment(
    item_id: str,
    file: UploadFile = File(...),
    items_service: ItemsService = Depends(get_items_service),
):
    return await items_service.add_attachment(item_id, file)


# Background task functions
async def trigger_orchestrator_analysis(item_id: str):
    """Background task to analyze newly created items for AI suitability"""
    import asyncio
    import httpx
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Give the item creation transaction time to commit
        await asyncio.sleep(0.5)
        
        # Call our own orchestrator endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/orchestrator/analyze/{item_id}")
            
            if response.status_code == 200:
                result = response.json()
                if result['orchestration_started']:
                    logger.info(f"🤖 Orchestration started for new item {item_id} (task: {result['task_type']}, confidence: {result['confidence']:.0%})")
                else:
                    logger.debug(f"📝 New item {item_id} not suitable for AI processing: {result['reasoning']}")
            else:
                logger.warning(f"Failed to analyze new item {item_id}: {response.status_code}")
                
    except Exception as e:
        logger.error(f"Error analyzing new item {item_id}: {e}")
        # Don't raise - this shouldn't fail item creation
