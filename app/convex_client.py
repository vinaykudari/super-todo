import os
import asyncio
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from convex import ConvexClient

load_dotenv()

CONVEX_URL = os.getenv("CONVEX_URL")

if not CONVEX_URL:
    raise RuntimeError("Missing CONVEX_URL in environment")


class ConvexService:
    def __init__(self):
        self.client = ConvexClient(CONVEX_URL)

    async def _call_function(self, function_name: str, args: Dict[str, Any], function_type: str = "mutation"):
        """Call a Convex function asynchronously."""
        loop = asyncio.get_event_loop()
        if function_type == "mutation":
            return await loop.run_in_executor(None, self.client.mutation, function_name, args)
        else:
            return await loop.run_in_executor(None, self.client.query, function_name, args)

    async def add_log(self, item_id: str, message: str, level: str = "info", metadata: Optional[Dict[str, Any]] = None):
        """Add a log entry for an item."""
        return await self._call_function("logs:addLog", {
            "item_id": item_id,
            "message": message,
            "level": level,
            "metadata": metadata
        }, "mutation")

    async def get_logs_by_item_id(self, item_id: str, limit: int = 50, cursor: Optional[str] = None):
        """Get logs for a specific item with pagination."""
        args = {
            "item_id": item_id,
            "limit": limit
        }
        if cursor is not None:
            args["cursor"] = cursor
        return await self._call_function("logs:getLogsByItemId", args, "query")

    async def get_recent_logs(self, limit: int = 100):
        """Get recent logs across all items."""
        return await self._call_function("logs:getRecentLogs", {
            "limit": limit
        }, "query")

    async def stream_logs_by_item_id(self, item_id: str, since: Optional[int] = None):
        """Stream logs for a specific item (for real-time updates)."""
        args = {
            "item_id": item_id
        }
        if since is not None:
            args["since"] = since
        return await self._call_function("logs:streamLogsByItemId", args, "query")
