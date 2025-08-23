from typing import Dict, Any, Optional, List
from ..convex_client import ConvexService


class LogsRepository:
    def __init__(self):
        self.convex_service = ConvexService()

    async def add_log(self, item_id: str, message: str, level: str = "info", metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a log entry for an item."""
        return await self.convex_service.add_log(item_id, message, level, metadata)

    async def get_logs_by_item_id(self, item_id: str, limit: int = 50, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Get logs for a specific item with pagination."""
        return await self.convex_service.get_logs_by_item_id(item_id, limit, cursor)

    async def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent logs across all items."""
        return await self.convex_service.get_recent_logs(limit)

    async def stream_logs_by_item_id(self, item_id: str, since: Optional[int] = None) -> List[Dict[str, Any]]:
        """Stream logs for a specific item (for real-time updates)."""
        return await self.convex_service.stream_logs_by_item_id(item_id, since)
