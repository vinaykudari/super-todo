from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field

ItemState = Literal["pending", "processing", "completed"]

class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None

class Item(BaseModel):
    id: str
    title: str
    description: Optional[str]
    state: ItemState
    created_at: datetime
    updated_at: datetime

class ItemUpdateState(BaseModel):
    state: ItemState

class Attachment(BaseModel):
    id: str
    item_id: str
    name: str
    url: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: datetime

class ItemWithAttachments(Item):
    attachments: List[Attachment] = []
