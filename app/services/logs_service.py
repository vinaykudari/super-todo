from typing import Optional, Dict, Any
from fastapi import HTTPException

from ..repositories.logs_repository import LogsRepository
from ..schemas import LogCreate, Log, LogsResponse


class LogsService:
    def __init__(self):
        self.logs_repo = LogsRepository()

    async def add_log(self, payload: LogCreate) -> str:
        """Add a new log entry for an item."""
        try:
            log_id = await self.logs_repo.add_log(
                item_id=payload.item_id,
                message=payload.message,
                level=payload.level,
                metadata=payload.metadata
            )
            return log_id
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add log: {str(e)}")

    async def get_logs_by_item_id(self, item_id: str, limit: int = 50, cursor: Optional[str] = None) -> LogsResponse:
        """Get logs for a specific item with pagination."""
        try:
            result = await self.logs_repo.get_logs_by_item_id(item_id, limit, cursor)
            logs = [Log(**log) for log in result.get("logs", [])]
            return LogsResponse(
                logs=logs,
                nextCursor=result.get("nextCursor")
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")

    async def get_recent_logs(self, limit: int = 100) -> list[Log]:
        """Get recent logs across all items."""
        try:
            logs_data = await self.logs_repo.get_recent_logs(limit)
            return [Log(**log) for log in logs_data]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve recent logs: {str(e)}")

    async def stream_logs_by_item_id(self, item_id: str, since: Optional[int] = None) -> list[Log]:
        """Stream logs for a specific item (for real-time updates)."""
        try:
            logs_data = await self.logs_repo.stream_logs_by_item_id(item_id, since)
            return [Log(**log) for log in logs_data]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to stream logs: {str(e)}")
