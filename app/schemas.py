from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

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
    task: str = Field(..., description="Natural-language instruction")
    item_id: Optional[str] = Field(None, description="If set, logs + status updates tie to this item")
    session_id: Optional[str] = None
    wait: bool = False
    allowed_domains: Optional[List[str]] = None
    model: Optional[str] = None
    structured_output_json: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    included_file_names: Optional[List[str]] = None
    secrets: Optional[Dict[str, str]] = None
    save_browser_data: Optional[bool] = None

class BrowserTaskCreated(BaseModel):
    task_id: str
    session_id: str
    live_url: Optional[str] = None

class BrowserTaskResult(BaseModel):
    id: str
    session_id: Optional[str] = None
    status: Optional[str] = None
    is_success: Optional[bool] = None
    done_output: Optional[Any] = None
    live_url: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    steps: Optional[List[Dict[str, Any]]] = None

    @field_validator("started_at", "finished_at", mode="before")
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

class BrowserLogsUrl(BaseModel):
    download_url: str

class BrowserTaskResponse(BaseModel):
    task_id: str
    item_id: str
    status: Literal["started", "in_progress", "completed", "failed"]
    message: str
    result: Optional[Dict[str, Any]] = None

# Orchestrator schemas
class TaskAnalysisResponse(BaseModel):
    """Response from task analysis"""
    item_id: str
    suitable: bool
    confidence: float
    task_type: str
    reasoning: str
    orchestration_started: bool = False

class OrchestrationResponse(BaseModel):
    """Response from orchestration trigger"""
    message: str
    item_id: str
    orchestration_started: bool
