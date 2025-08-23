from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from ..services.logs_service import LogsService
from ..dependencies import get_logs_service
from ..schemas import LogCreate, Log, LogsResponse

router = APIRouter(prefix="/logs", tags=["logs"])

@router.post("", response_model=str)
async def add_log(
    payload: LogCreate,
    logs_service: LogsService = Depends(get_logs_service)
):
    """Add a new log entry for an item."""
    return await logs_service.add_log(payload)

@router.get("/item/{item_id}", response_model=LogsResponse)
async def get_logs_by_item_id(
    item_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = Query(default=None),
    logs_service: LogsService = Depends(get_logs_service)
):
    """Get logs for a specific item with pagination."""
    return await logs_service.get_logs_by_item_id(item_id, limit, cursor)

@router.get("/recent", response_model=List[Log])
async def get_recent_logs(
    limit: int = Query(default=100, ge=1, le=500),
    logs_service: LogsService = Depends(get_logs_service)
):
    """Get recent logs across all items."""
    return await logs_service.get_recent_logs(limit)

@router.get("/stream/{item_id}", response_model=List[Log])
async def stream_logs_by_item_id(
    item_id: str,
    since: Optional[int] = Query(default=None, description="Timestamp to get logs since"),
    logs_service: LogsService = Depends(get_logs_service)
):
    """Stream logs for a specific item (for real-time updates)."""
    return await logs_service.stream_logs_by_item_id(item_id, since)
