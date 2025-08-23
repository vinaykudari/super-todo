import os
import asyncio
from typing import Dict, Any, Optional
from convex import ConvexClient
from dotenv import load_dotenv

load_dotenv()

CONVEX_URL = os.getenv("CONVEX_URL")
if not CONVEX_URL:
    raise RuntimeError("Missing CONVEX_URL in environment")


class ConvexService:
    """
    Async wrapper around the synchronous Convex Python client.
    """

    def __init__(self):
        self.client = ConvexClient(CONVEX_URL)

    async def _call_function(self, function_name: str, args: Dict[str, Any], function_type: str = "mutation"):
        loop = asyncio.get_running_loop()
        if function_type == "mutation":
            return await loop.run_in_executor(None, self.client.mutation, function_name, args)
        return await loop.run_in_executor(None, self.client.query, function_name, args)

    # -------- Logs API (you already use these) --------

    async def add_log(self, item_id: str, message: str, level: str = "info",
                      metadata: Optional[Dict[str, Any]] = None):
        return await self._call_function(
            "logs:addLog",
            {"item_id": item_id, "message": message, "level": level, "metadata": metadata},
            "mutation",
        )

    async def get_logs_by_item_id(
        self,
        item_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        direction: str = "desc",
    ):
        """
        Query Convex logs:getLogsByItemId with explicit ordering.
        direction: "desc" (default) or "asc"
        """
        args: Dict[str, Any] = {"item_id": item_id, "limit": limit, "direction": direction}
        if cursor is not None:
            args["cursor"] = cursor
        return await self._call_function("logs:getLogsByItemId", args, "query")

    async def get_recent_logs(self, limit: int = 100):
        return await self._call_function("logs:getRecentLogs", {"limit": limit}, "query")

    async def stream_logs_by_item_id(self, item_id: str, since: Optional[int] = None):
        args = {"item_id": item_id}
        if since is not None:
            args["since"] = since
        return await self._call_function("logs:streamLogsByItemId", args, "query")

    async def upsert_item(self, item: Dict[str, Any]):
        """
        Convex items:upsertItem
        Accepts: { item_id, title, state, description?, live_url?, done_output?, context? }
        Only include optional keys when not None.
        """
        args: Dict[str, Any] = {
            "item_id": item["item_id"],
            "title": item["title"],
            "state": item["state"],
        }
        if item.get("description") is not None:
            args["description"] = item["description"]
        if item.get("live_url") is not None:
            args["live_url"] = item["live_url"]
        if item.get("done_output") is not None:
            args["done_output"] = item["done_output"]
        if item.get("context") is not None:
            args["context"] = item["context"]
        return await self._call_function("items:upsertItem", args, "mutation")

    async def set_item_live_url(self, item_id: str, live_url: Optional[str]):
        """
        Convex items:setLiveUrl — omit live_url when None.
        """
        args: Dict[str, Any] = {"item_id": item_id}
        if live_url is not None:
            args["live_url"] = live_url
        return await self._call_function("items:setLiveUrl", args, "mutation")

    async def set_item_status(
        self,
        item_id: str,
        state: str,
        context: Optional[Dict[str, Any]] = None,
        done_output: Optional[Any] = None,
    ):
        """
        Convex mutation: items:setStatus
        Only include optional keys when not None to satisfy Convex validators.
        """
        args: Dict[str, Any] = {"item_id": item_id, "state": state}
        if context is not None:
            args["context"] = context
        if done_output is not None:
            args["done_output"] = done_output
        return await self._call_function("items:setStatus", args, "mutation")

    async def list_items(
        self,
        *,
        state: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ):
        """
        Call Convex items:listItems query.
        Args:
        state: optional 'pending' | 'processing' | 'completed'
        limit: page size (default 50)
        cursor: stringified milliseconds since epoch (from previous response)
        Returns:
        Dict with keys: {"items": [...], "nextCursor": "ms" | None}
        """
        args: Dict[str, Any] = {"limit": limit}
        if state is not None:
            args["state"] = state
        if cursor is not None:
            args["cursor"] = cursor
        return await self._call_function("items:listItems", args, "query")
