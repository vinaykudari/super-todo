import asyncio
from typing import Union

from fastapi import APIRouter, Depends, Query
from ..services.browser_service import (
    BrowserService,
    BrowserTaskRequest,
    BrowserTaskCreated,
    BrowserTaskResult,
    BrowserLogsUrl,
)
from ..services.logs_service import LogsService

# DI providers (fallbacks if you don't have a dependencies module)
try:
    from ..dependencies import get_browser_service, get_logs_service  # type: ignore
except Exception:

    def get_browser_service() -> BrowserService:
        return BrowserService()

    def get_logs_service() -> LogsService:
        return LogsService()


router = APIRouter(prefix="/browser", tags=["browser"])


@router.post(
    "/tasks",
    response_model=Union[BrowserTaskCreated, BrowserTaskResult],
    summary="Start a Browser-Use task and (optionally) monitor to item logs",
)
async def run_browser_task(
    payload: BrowserTaskRequest,
    browser_service: BrowserService = Depends(get_browser_service),
    logs_service: LogsService = Depends(get_logs_service),
):
    """
    Kick off a natural-language browser task.

    - Use `<secret>key</secret>` placeholders in `task`. Env vars resolve automatically:
        KEY -> $KEY, $SECRET__KEY, or $BROWSER_USE_SECRET__KEY
      You can also pass `secrets` directly.
    - Provide `item_id` to stream step/status logs into your existing item log feed.
    - Use `allowed_domains` for sandboxing.

    Returns either:
      - {task_id, session_id, live_url} when wait=false (and starts a background log monitor if item_id provided)
      - Full task result when wait=true (and emits a one-shot backfill of steps to logs if item_id provided)
    """
    result = await browser_service.run_task(payload)
    # If a monitor is running, it's already spawned inside service when item_id is present.
    # (Nothing else to do here.)
    return result


@router.get(
    "/tasks/{task_id}",
    response_model=BrowserTaskResult,
    summary="Get task status/details (includes steps, done_output, live_url)",
)
async def get_browser_task(
    task_id: str,
    browser_service: BrowserService = Depends(get_browser_service),
):
    return await browser_service.get_task(task_id)


@router.get(
    "/tasks/{task_id}/logs",
    response_model=BrowserLogsUrl,
    summary="Get a presigned download URL for the agent's execution logs",
)
async def get_browser_task_logs(
    task_id: str,
    browser_service: BrowserService = Depends(get_browser_service),
):
    return await browser_service.get_task_logs(task_id)
