from typing import List, Dict, Any
from uuid import uuid4
from ..supabase_client import supabase, SUPABASE_BUCKET


class AttachmentsRepository:
    def __init__(self):
        self.supabase = supabase

    def get_attachments_by_item_id(self, item_id: str) -> List[Dict[str, Any]]:
        """Get all attachments for a specific item."""
        res = self.supabase.table("attachments").select("*").eq("item_id", item_id).order("created_at", desc=True).execute()
        return res.data or []

    def create_attachment(self, item_id: str, name: str, path: str, url: str, 
                         mime_type: str = None, size_bytes: int = None) -> Dict[str, Any]:
        """Create a new attachment record in the database."""
        res = self.supabase.table("attachments").insert({
            "item_id": item_id,
            "name": name,
            "path": path,
            "url": url,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
        }).execute()
        
        if not res.data:
            raise Exception("Failed to record attachment")
        return res.data[0]

    def upload_file(self, file_data: bytes, path: str, content_type: str) -> Dict[str, Any]:
        """Upload file to Supabase Storage."""
        up_res = self.supabase.storage.from_(SUPABASE_BUCKET).upload(
            file=file_data,
            path=path,
            file_options={"content-type": content_type, "upsert": False},
        )
        
        if up_res.get("error"):
            raise Exception(f"Upload failed: {up_res['error']}")
        return up_res

    def get_public_url(self, path: str) -> str:
        """Get public URL for a file in storage."""
        pub = self.supabase.storage.from_(SUPABASE_BUCKET).get_public_url(path)
        public_url = (pub.get("data") or {}).get("publicUrl")
        
        if not public_url:
            raise Exception("Could not get public URL")
        return public_url
