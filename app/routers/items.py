from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Query, Depends
from ..services.items_service import ItemsService
from ..dependencies import get_items_service
from ..schemas import ItemCreate, Item, ItemUpdateState, ItemWithAttachments, Attachment

router = APIRouter(prefix="/items", tags=["items"])

@router.post("", response_model=Item)
def create_item(
    payload: ItemCreate,
    items_service: ItemsService = Depends(get_items_service)
):
    return items_service.create_item(payload)

@router.get("", response_model=List[Item])
def list_items(
    state: Optional[str] = Query(default=None, pattern="^(pending|processing|completed)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    items_service: ItemsService = Depends(get_items_service)
):
    return items_service.get_items(state=state, limit=limit, offset=offset)

@router.get("/{item_id}", response_model=ItemWithAttachments)
def get_item(
    item_id: str,
    items_service: ItemsService = Depends(get_items_service)
):
    return items_service.get_item_with_attachments(item_id)

@router.patch("/{item_id}/state", response_model=Item)
def update_state(
    item_id: str,
    payload: ItemUpdateState,
    items_service: ItemsService = Depends(get_items_service)
):
    return items_service.update_item_state(item_id, payload)

@router.post("/{item_id}/attachments", response_model=Attachment)
async def add_attachment(
    item_id: str,
    file: UploadFile = File(...),
    items_service: ItemsService = Depends(get_items_service)
):
    return await items_service.add_attachment(item_id, file)
