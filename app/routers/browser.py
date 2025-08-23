from typing import Union
from fastapi import APIRouter, Depends
from ..services.browser_service import (
    BrowserService,
    BrowserTaskRequest,
    BrowserTaskCreated,
    BrowserTaskResult,
    BrowserLogsUrl,
)
from ..dependencies import get_browser_service  # type: ignore


router = APIRouter(prefix="/browser", tags=["browser"])


@router.post(
    "/tasks",
    response_model=Union[BrowserTaskCreated, BrowserTaskResult],
    summary="Start a Browser-Use task; stream logs and update Convex status"
)
async def run_browser_task(
    payload: BrowserTaskRequest,
    browser_service: BrowserService = Depends(get_browser_service),
):
    """
    Use `<secret>...key...</secret>` placeholders in `task` and provide values via env:
      KEY / SECRET__KEY / BROWSER_USE_SECRET__KEY

    If `item_id` is present:
      - state -> 'processing' immediately
      - live_url mirrored when available
      - streaming step/status logs to Convex
      - final state: 'completed' on success; 'pending' with context otherwise
    """
    return await browser_service.run_task(payload)


@router.get("/tasks/{task_id}", response_model=BrowserTaskResult)
async def get_browser_task(task_id: str, browser_service: BrowserService = Depends(get_browser_service)):
    return await browser_service.get_task(task_id)


@router.get("/tasks/{task_id}/logs", response_model=BrowserLogsUrl)
async def get_browser_task_logs(task_id: str, browser_service: BrowserService = Depends(get_browser_service)):
    return await browser_service.get_task_logs(task_id)
