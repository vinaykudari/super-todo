import asyncio
from typing import Optional, List
from fastapi import HTTPException, UploadFile

from ..repositories.items_repository import ItemsRepository
from ..repositories.attachments_repository import AttachmentsRepository
from ..schemas import ItemCreate, Item, ItemUpdateState, ItemWithAttachments, Attachment
from ..convex_client import ConvexService


class ItemsService:
    """
    Fully async service layer:
      - Wraps sync Supabase repos with asyncio.to_thread
      - Mirrors items + state to Convex for realtime UI
    """

    def __init__(self):
        self.items_repo = ItemsRepository()
        self.attachments_repo = AttachmentsRepository()
        self.convex = ConvexService()

    # ---------- Helpers to wrap sync repos ----------

    async def _create_item_supabase(self, title: str, description: Optional[str]) -> Item:
        data = await asyncio.to_thread(self.items_repo.create_item, title, description)
        return Item(**data)

    async def _get_items_supabase(self, state: Optional[str], limit: int, offset: int) -> List[Item]:
        items_data = await asyncio.to_thread(self.items_repo.get_items, state, limit, offset)
        return [Item(**i) for i in items_data]

    async def _get_item_by_id_supabase(self, item_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self.items_repo.get_item_by_id, item_id)

    async def _update_item_state_supabase(self, item_id: str, new_state: str) -> Optional[dict]:
        return await asyncio.to_thread(self.items_repo.update_item_state, item_id, new_state)

    async def _item_exists_supabase(self, item_id: str) -> bool:
        return await asyncio.to_thread(self.items_repo.item_exists, item_id)

    async def _upload_file_supabase(self, *, file_data: bytes, path: str, content_type: str):
        return await asyncio.to_thread(self.attachments_repo.upload_file, file_data, path, content_type)

    async def _get_public_url_supabase(self, path: str) -> str:
        return await asyncio.to_thread(self.attachments_repo.get_public_url, path)

    async def _create_attachment_supabase(
        self, *, item_id: str, name: str, path: str, url: str, mime_type: Optional[str], size_bytes: int
    ) -> Attachment:
        data = await asyncio.to_thread(
            self.attachments_repo.create_attachment,
            item_id, name, path, url, mime_type, size_bytes
        )
        return Attachment(**data)

    async def _get_attachments_by_item_id_supabase(self, item_id: str) -> List[Attachment]:
        att_data = await asyncio.to_thread(self.attachments_repo.get_attachments_by_item_id, item_id)
        return [Attachment(**a) for a in att_data]

    # ---------- Public API ----------

    async def create_item(self, payload: ItemCreate) -> Item:
        """Create a new item in Supabase and mirror to Convex (no nulls)."""
        try:
            # Supabase write (sync repo wrapped in thread)
            item = await self._create_item_supabase(payload.title, payload.description)

            # Build args without None optionals
            upsert_args = {
                "item_id": item.id,
                "title": item.title,
                "state": item.state,           # likely 'pending'
            }
            if item.description is not None:
                upsert_args["description"] = item.description

            # Mirror into Convex for realtime
            await self.convex.upsert_item(upsert_args)
            return item
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to create item")

    async def get_items(
        self,
        state: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,                 # kept for compatibility; ignored
        cursor: Optional[str] = None,    # Convex pagination token (updated_at as string)
    ) -> List[Item]:
        """
        Fetch items from Convex instead of Supabase.
        - Orders by updated_at DESC.
        - Supports optional state filter and cursor pagination.
        - Maps Convex docs -> your Item Pydantic model.
        """
        try:
            resp = await self.convex.list_items(state=state, limit=limit, cursor=cursor)
            convex_items = resp.get("items", [])
            items: List[Item] = []
            for it in convex_items:
                # Map Convex shape to your Item model fields
                items.append(
                    Item(
                        id=it["item_id"],
                        title=it["title"],
                        description=it.get("description") or "",
                        state=it["state"],
                        live_url=it.get("live_url"),
                        done_output=it.get("done_output"),
                    )
                )
            return items
        except Exception as e:
            print(f"Failed to retrieve items {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve items")

    async def get_item_with_attachments(self, item_id: str) -> ItemWithAttachments:
        """Fetch item and its attachments."""
        try:
            item_data = await self._get_item_by_id_supabase(item_id)
            if not item_data:
                raise HTTPException(status_code=404, detail="Item not found")
            attachments = await self._get_attachments_by_item_id_supabase(item_id)
            return ItemWithAttachments(**item_data, attachments=attachments)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to retrieve item")

    async def update_item_state(self, item_id: str, payload: ItemUpdateState) -> Item:
        """Update item state in Supabase and mirror to Convex."""
        try:
            updated = await self._update_item_state_supabase(item_id, payload.state)
            if not updated:
                raise HTTPException(status_code=404, detail="Item not found")

            item = Item(**updated)
            await self.convex.set_item_status(item_id=item.id, state=item.state)
            return item
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to update item state")

    async def add_attachment(self, item_id: str, file: UploadFile) -> Attachment:
        """Add an attachment, store file in Supabase storage, and record it."""
        try:
            if not await self._item_exists_supabase(item_id):
                raise HTTPException(status_code=404, detail="Item not found")

            file_data = await file.read()
            from uuid import uuid4
            file_path = f"{item_id}/{uuid4()}_{file.filename}"

            await self._upload_file_supabase(file_data=file_data, path=file_path,
                                             content_type=file.content_type or "application/octet-stream")
            public_url = await self._get_public_url_supabase(file_path)
            return await self._create_attachment_supabase(
                item_id=item_id,
                name=file.filename,
                path=file_path,
                url=public_url,
                mime_type=file.content_type,
                size_bytes=len(file_data),
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add attachment: {str(e)}")
