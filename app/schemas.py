from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

ItemState = Literal["pending", "processing", "completed"]
LogLevel = Literal["info", "warning", "error", "debug"]
OrchestrationStatus = Literal["pending", "running", "completed", "failed"]

class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None

class Item(BaseModel):
    id: str
    title: str
    description: Optional[str]
    state: ItemState
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ai_request: Optional[str] = None
    orchestration_status: OrchestrationStatus = "pending"
    orchestration_result: Optional[Dict[str, Any]] = None
    live_url: Optional[str] = None
    screenshot_url: Optional[str] = None
    done_output: Optional[str] = None

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

# Log schemas
class LogCreate(BaseModel):
    item_id: str
    message: str
    level: LogLevel = "info"
    metadata: Optional[Dict[str, Any]] = None

class Log(BaseModel):
    _id: str
    item_id: str
    message: str
    level: LogLevel
    timestamp: int
    metadata: Optional[Dict[str, Any]] = None
    _creationTime: int

class LogsResponse(BaseModel):
    logs: List[Log]
    nextCursor: Optional[str] = None

# Browser automation schemas
class BrowserTaskRequest(BaseModel):
    item_id: str
    task: str = Field(..., description="Natural language description of the task to perform")
    allowed_domains: Optional[List[str]] = Field(default=None, description="List of allowed domains for security")

class BrowserTaskResponse(BaseModel):
    task_id: str
    item_id: str
    status: Literal["started", "in_progress", "completed", "failed"]
    message: str
    result: Optional[Dict[str, Any]] = None
