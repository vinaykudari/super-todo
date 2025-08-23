from typing import Optional, List
from fastapi import HTTPException, UploadFile
from uuid import uuid4

from ..repositories.items_repository import ItemsRepository
from ..repositories.attachments_repository import AttachmentsRepository
from ..schemas import ItemCreate, Item, ItemUpdateState, ItemWithAttachments, Attachment


class ItemsService:
    def __init__(self):
        self.items_repo = ItemsRepository()
        self.attachments_repo = AttachmentsRepository()

    def create_item(self, payload: ItemCreate) -> Item:
        """Create a new todo item."""
        try:
            item_data = self.items_repo.create_item(
                title=payload.title,
                description=payload.description
            )
            return Item(**item_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to create item")

    def get_items(self, state: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Item]:
        """Get list of items with optional filtering."""
        try:
            items_data = self.items_repo.get_items(state=state, limit=limit, offset=offset)
            return [Item(**item) for item in items_data]
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to retrieve items")

    def get_item_with_attachments(self, item_id: str) -> ItemWithAttachments:
        """Get a single item with its attachments."""
        try:
            item_data = self.items_repo.get_item_by_id(item_id)
            if not item_data:
                raise HTTPException(status_code=404, detail="Item not found")

            attachments_data = self.attachments_repo.get_attachments_by_item_id(item_id)
            attachments = [Attachment(**att) for att in attachments_data]

            return ItemWithAttachments(**item_data, attachments=attachments)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to retrieve item")

    def update_item_state(self, item_id: str, payload: ItemUpdateState) -> Item:
        """Update the state of an item."""
        try:
            updated_item = self.items_repo.update_item_state(item_id, payload.state)
            if not updated_item:
                raise HTTPException(status_code=404, detail="Item not found")
            
            return Item(**updated_item)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to update item state")

    async def add_attachment(self, item_id: str, file: UploadFile) -> Attachment:
        """Add a file attachment to an item."""
        try:
            # Verify item exists
            if not self.items_repo.item_exists(item_id):
                raise HTTPException(status_code=404, detail="Item not found")

            # Read file data
            file_data = await file.read()
            
            # Generate storage path
            file_path = f"{item_id}/{uuid4()}_{file.filename}"
            
            # Upload to storage
            self.attachments_repo.upload_file(
                file_data=file_data,
                path=file_path,
                content_type=file.content_type or "application/octet-stream"
            )
            
            # Get public URL
            public_url = self.attachments_repo.get_public_url(file_path)
            
            # Save attachment record
            attachment_data = self.attachments_repo.create_attachment(
                item_id=item_id,
                name=file.filename,
                path=file_path,
                url=public_url,
                mime_type=file.content_type,
                size_bytes=len(file_data)
            )
            
            return Attachment(**attachment_data)
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add attachment: {str(e)}")
