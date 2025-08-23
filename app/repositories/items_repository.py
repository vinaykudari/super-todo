from typing import Optional, List, Dict, Any
from uuid import uuid4
from ..supabase_client import supabase


class ItemsRepository:
    def __init__(self):
        self.supabase = supabase

    def create_item(self, title: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Create a new item in the database."""
        res = self.supabase.table("items").insert({
            "title": title,
            "description": description,
        }).execute()
        
        if not res.data:
            raise Exception("Failed to create item")
        return res.data[0]

    def get_items(self, state: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get items with optional filtering and pagination."""
        q = self.supabase.table("items").select("*").order("created_at", desc=True)
        
        if state:
            q = q.eq("state", state)
        
        start = offset
        end = offset + limit - 1
        res = q.range(start, end).execute()
        return res.data or []

    def get_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get a single item by ID."""
        res = self.supabase.table("items").select("*").eq("id", item_id).limit(1).execute()
        rows = res.data or []
        return rows[0] if rows else None

    def update_item_state(self, item_id: str, state: str) -> Optional[Dict[str, Any]]:
        """Update item state."""
        res = self.supabase.table("items").update({"state": state}).eq("id", item_id).execute()
        rows = res.data or []
        return rows[0] if rows else None

    def item_exists(self, item_id: str) -> bool:
        """Check if an item exists."""
        res = self.supabase.table("items").select("id").eq("id", item_id).limit(1).execute()
        return bool(res.data)
