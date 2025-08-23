import os
import re
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
# Browser-Use SDK
try:
    from browser_use_sdk import AsyncBrowserUse
except Exception:
    AsyncBrowserUse = None
from ..schemas import LogCreate
from ..services.logs_service import LogsService
from ..convex_client import ConvexService
from ..repositories.items_repository import ItemsRepository # optional Supabase status sync
from ..config import (
    BROWSER_DEFAULT_VIEWPORT_WIDTH,
    BROWSER_DEFAULT_VIEWPORT_HEIGHT,
    BROWSER_DEFAULT_DEVICE_SCALE_FACTOR,
    BROWSER_MOBILE_BY_DEFAULT
)
SYNC_SUPABASE_STATUS = os.getenv("SYNC_SUPABASE_STATUS", "true").lower() == "true"
BROWSER_USE_API_KEY = os.getenv("BROWSER_USE_API_KEY") or ""
# -------------------- Pydantic IO models --------------------
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
    viewport_settings: Optional[Dict[str, Any]] = Field(None, description="Custom viewport settings for browser (width, height, device_scale_factor, etc.)")
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
# -------------------- Service --------------------
class BrowserService:
    """
    Uses Browser-Use Cloud SDK for all operations.
    Provides session management, task execution, and real-time streaming.
    """
    def __init__(self):
        if not BROWSER_USE_API_KEY:
            raise HTTPException(status_code=500, detail="Missing BROWSER_USE_API_KEY")
        if not AsyncBrowserUse:
            raise HTTPException(status_code=500, detail="Browser-Use SDK not available. Install with: pip install browser-use-sdk")
        self.sdk = AsyncBrowserUse(api_key=BROWSER_USE_API_KEY)
        self.logs = LogsService()
        self.convex = ConvexService()
        self.items_repo = ItemsRepository() if SYNC_SUPABASE_STATUS else None
    def _extract_session_id(self, obj: Any) -> Optional[str]:
        """Extract session ID from SDK response objects"""
        if not obj:
            return None
        # Try direct attributes first
        for attr in ["session_id", "sessionId", "sessionID"]:
            if hasattr(obj, attr):
                value = getattr(obj, attr)
                if value and isinstance(value, str):
                    return value.strip()
        # Try dict-like access
        if hasattr(obj, '__dict__'):
            obj_dict = obj.__dict__
        elif isinstance(obj, dict):
            obj_dict = obj
        else:
            return None
        for field in ["session_id", "sessionId", "sessionID"]:
            if field in obj_dict and obj_dict[field]:
                value = obj_dict[field]
                if isinstance(value, str):
                    return value.strip()
        # Try nested session object
        session = obj_dict.get("session")
        if session:
            if hasattr(session, 'id'):
                return str(session.id)
            elif isinstance(session, dict) and 'id' in session:
                return str(session['id'])
        return None
    def _extract_live_url(self, obj: Any) -> Optional[str]:
        """Extract live URL from SDK response objects"""
        if not obj:
            return None
        # Try direct attributes
        for attr in ["live_url", "liveUrl", "debugUrl", "debug_url"]:
            if hasattr(obj, attr):
                value = getattr(obj, attr)
                if value and isinstance(value, str):
                    return value.strip()
        # Try dict-like access
        if hasattr(obj, '__dict__'):
            obj_dict = obj.__dict__
        elif isinstance(obj, dict):
            obj_dict = obj
        else:
            return None
        for field in ["live_url", "liveUrl", "debugUrl", "debug_url"]:
            if field in obj_dict and obj_dict[field]:
                value = obj_dict[field]
                if isinstance(value, str):
                    return value.strip()
        # Try nested session object
        session = obj_dict.get("session")
        if session:
            for field in ["live_url", "liveUrl", "debugUrl", "debug_url"]:
                if hasattr(session, field):
                    value = getattr(session, field)
                    if value and isinstance(value, str):
                        return value.strip()
                elif isinstance(session, dict) and field in session:
                    value = session[field]
                    if value and isinstance(value, str):
                        return value.strip()
        return None
    def _build_task_config(self, payload: BrowserTaskRequest) -> Dict[str, Any]:
        """Build task configuration for SDK"""
        config = {
            "task": payload.task,
        }
        # Agent settings
        agent_settings: Dict[str, Any] = {}
        if payload.model:
            agent_settings["llm"] = payload.model
        if agent_settings:
            config["agent_settings"] = agent_settings
        # Browser settings
        browser_settings: Dict[str, Any] = {}
        if payload.session_id:
            browser_settings["session_id"] = payload.session_id
        if payload.allowed_domains:
            browser_settings["allowed_domains"] = payload.allowed_domains
        if payload.save_browser_data is not None:
            browser_settings["keep_alive"] = payload.save_browser_data
        # Add mobile-compatible viewport settings for better live video experience
        # Use Browser Use API parameters as documented at:
        # https://docs.browser-use.com/api-reference/browser-profiles/create-browser-profile
        # Set default mobile viewport for better live video experience (hardcoded for mobile portrait)
        default_viewport_width = 375  # Mobile width (portrait)
        default_viewport_height = 812  # Mobile height (portrait)
        default_is_mobile = True  # Enable mobile emulation
        # Use custom viewport settings if provided, otherwise use mobile defaults
        if payload.viewport_settings:
            browser_viewport_width = payload.viewport_settings.get("width", default_viewport_width)
            browser_viewport_height = payload.viewport_settings.get("height", default_viewport_height)
            is_mobile = payload.viewport_settings.get("is_mobile", default_is_mobile)
        else:
            browser_viewport_width = default_viewport_width
            browser_viewport_height = default_viewport_height
            is_mobile = default_is_mobile
        # Set Browser Use API compatible viewport parameters
        browser_settings["browserViewportWidth"] = browser_viewport_width
        browser_settings["browserViewportHeight"] = browser_viewport_height
        browser_settings["isMobile"] = is_mobile
        if browser_settings:
            config["browser_settings"] = browser_settings
        # Output format
        if payload.structured_output_json:
            config["structured_output"] = payload.structured_output_json
        # Metadata
        if payload.metadata:
            meta = dict(payload.metadata)
            if payload.item_id:
                meta["item_id"] = payload.item_id
            config["metadata"] = meta
        elif payload.item_id:
            config["metadata"] = {"item_id": payload.item_id}
        # Files
        if payload.included_file_names:
            config["files"] = payload.included_file_names
        # Secrets
        merged_secrets = self._resolve_secrets_from_task(payload.task)
        if payload.secrets:
            merged_secrets.update(payload.secrets)
        if merged_secrets:
            config["secrets"] = merged_secrets
        return config
    async def run_task(self, payload: BrowserTaskRequest) -> Union[BrowserTaskCreated, BrowserTaskResult]:
        """
        Start a Browser-Use task using the SDK.
        """
        try:
            # Mark as processing if item_id provided
            if payload.item_id:
                await self._set_status(payload.item_id, "processing")
            # Build task configuration
            task_config = self._build_task_config(payload)
            if payload.wait:
                # Synchronous execution
                print("[DEBUG] Running task synchronously...")
                result = await self.sdk.tasks.run(**task_config)
                print(f"[DEBUG] Sync task result: {result}")
                browser_result = self._sdk_result_to_browser_result(result)
                # Update live URL if available
                if payload.item_id and browser_result.live_url:
                    await self.convex.set_item_live_url(payload.item_id, browser_result.live_url)
                # Log results and update status
                if payload.item_id:
                    await self._emit_full_view_to_logs(payload.item_id, browser_result)
                    if browser_result.is_success:
                        await self._set_status(payload.item_id, "completed", context=None, done_output=browser_result.done_output)
                    else:
                        await self._set_status(
                            payload.item_id,
                            "pending",
                            context={"status": browser_result.status},
                            done_output=browser_result.done_output,
                        )
                return browser_result
            else:
                # Asynchronous execution
                print("[DEBUG] Creating task asynchronously...")
                task = await self.sdk.tasks.create(**task_config)
                print(f"[DEBUG] Created task: {task}")
                # Extract IDs and URLs
                task_id = str(task.id) if hasattr(task, 'id') else str(task)
                session_id = self._extract_session_id(task)
                live_url = self._extract_live_url(task)
                print(f"[DEBUG] Task ID: {task_id}")
                print(f"[DEBUG] Session ID: {session_id}")
                print(f"[DEBUG] Live URL: {live_url}")
                # If no session_id found, try getting it from the task details
                if not session_id and task_id:
                    try:
                        task_details = await self.sdk.tasks.get(task_id)
                        session_id = self._extract_session_id(task_details)
                        if not live_url:
                            live_url = self._extract_live_url(task_details)
                        print(f"[DEBUG] Session ID from task details: {session_id}")
                        print(f"[DEBUG] Live URL from task details: {live_url}")
                    except Exception as e:
                        print(f"[DEBUG] Failed to get task details: {e}")
                # If still no session_id, try listing active sessions
                if not session_id:
                    try:
                        sessions = await self.sdk.sessions.list(status="active", limit=10)
                        print(f"[DEBUG] Active sessions: {sessions}")
                        if sessions and len(sessions) > 0:
                            # Get the most recent session
                            latest_session = sessions[0] # Assuming sessions are ordered by creation time
                            session_id = str(latest_session.id) if hasattr(latest_session, 'id') else str(latest_session)
                            if not live_url:
                                live_url = self._extract_live_url(latest_session)
                            print(f"[DEBUG] Using latest session ID: {session_id}")
                            print(f"[DEBUG] Live URL from session: {live_url}")
                    except Exception as e:
                        print(f"[DEBUG] Failed to list sessions: {e}")
                # Fall back to using task_id as session_id if still not found
                if not session_id:
                    session_id = task_id
                    print(f"[DEBUG] Using task_id as session_id: {session_id}")
                # Update live URL in Convex
                if payload.item_id and live_url:
                    await self.convex.set_item_live_url(payload.item_id, live_url)
                # Start streaming in background
                if payload.item_id:
                    asyncio.create_task(self.stream_task_to_logs(task_id, payload.item_id))
                return BrowserTaskCreated(
                    task_id=task_id,
                    session_id=session_id or "",
                    live_url=live_url
                )
        except Exception as e:
            print(f"[DEBUG] Run task failed: {e}")
            if payload.item_id:
                await self._set_status(payload.item_id, "pending", context={"error": str(e)})
            raise HTTPException(status_code=500, detail=f"Failed to run browser task: {str(e)}")
    async def get_task(self, task_id: str) -> BrowserTaskResult:
        """Get task details by ID"""
        try:
            task = await self.sdk.tasks.get(task_id)
            return self._sdk_result_to_browser_result(task)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")
    async def get_task_logs(self, task_id: str) -> BrowserLogsUrl:
        """Get task logs download URL"""
        try:
            logs = await self.sdk.tasks.logs(task_id)
            # The SDK should return logs with a download URL
            if hasattr(logs, 'download_url'):
                return BrowserLogsUrl(download_url=logs.download_url)
            elif hasattr(logs, 'url'):
                return BrowserLogsUrl(download_url=logs.url)
            elif isinstance(logs, dict):
                url = logs.get('download_url') or logs.get('url')
                if url:
                    return BrowserLogsUrl(download_url=url)
            raise RuntimeError("No download URL found in logs response")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get task logs: {str(e)}")
    async def stream_task_to_logs(self, task_id: str, item_id: str) -> None:
        """
        Stream task updates to logs using SDK streaming
        """
        last_step_no = 0
        live_url_set = False
        async def emit(msg: str, level: str = "info", meta: Optional[Dict[str, Any]] = None):
            try:
                await self.logs.add_log(
                    LogCreate(item_id=item_id, message=msg, level=level, metadata=meta or {})
                )
            except Exception as e:
                print(f"[BrowserService] Failed to add log: {e}")
        try:
            await emit(f"[browser] stream started for task {task_id}", "debug", {"task_id": task_id})
            # Use SDK streaming
            async for update in self.sdk.tasks.stream(task_id):
                raw_json = self._to_jsonable(update)
                await emit("[browser] raw_update", "debug", {"task_id": task_id, "raw": raw_json})
                # Set live URL once
                if not live_url_set:
                    live_url = self._extract_live_url(update)
                    if live_url:
                        await self.convex.set_item_live_url(item_id, live_url)
                        live_url_set = True
                    await emit(f"[browser] live_url set: {live_url}", "debug", {"task_id": task_id})
                # Get status
                status = getattr(update, 'status', None) or (update.get('status') if isinstance(update, dict) else None)
                if status:
                    await emit(f"[browser] status: {status}", "info", {"task_id": task_id})
                # Process steps
                steps = getattr(update, 'steps', []) or (update.get('steps', []) if isinstance(update, dict) else [])
                for step in steps:
                    step_num = getattr(step, 'number', 0) or (step.get('number', 0) if isinstance(step, dict) else 0)
                    if step_num <= last_step_no:
                        continue
                    await emit(self._fmt_step(step), "info", {"task_id": task_id, "step": self._to_jsonable(step)})
                    last_step_no = max(last_step_no, step_num)
                # Check if task is finished
                if status in {"finished", "stopped", "failed", "error", "completed"}:
                    done_output = getattr(update, 'done_output', None) or (update.get('done_output') if isinstance(update, dict) else None)
                    is_success = getattr(update, 'is_success', None) or (update.get('is_success') if isinstance(update, dict) else None)
                    await emit(
                        "[browser] task finished",
                        "info",
                        {"task_id": task_id, "is_success": is_success, "done_output": self._to_jsonable(done_output)},
                    )
                    if is_success:
                        await self._set_status(item_id, "completed", context=None, done_output=done_output)
                    else:
                        await self._set_status(item_id, "pending", context={"status": status}, done_output=done_output)
                    break
        except Exception as e:
            await emit(f"[browser] stream error: {str(e)}", "error", {"task_id": task_id})
            await self._set_status(item_id, "pending", context={"error": str(e)}, done_output=None)
    def _sdk_result_to_browser_result(self, sdk_result: Any) -> BrowserTaskResult:
        """Convert SDK result to BrowserTaskResult"""
        # Helper to get attribute or dict value
        def get_value(obj, attr, default=None):
            if hasattr(obj, attr):
                return getattr(obj, attr, default)
            elif isinstance(obj, dict):
                return obj.get(attr, default)
            return default
        # Extract timestamps
        started_at = get_value(sdk_result, 'started_at') or get_value(sdk_result, 'startedAt')
        if hasattr(started_at, 'isoformat'):
            started_at = started_at.isoformat()
        elif started_at:
            started_at = str(started_at)
        finished_at = get_value(sdk_result, 'finished_at') or get_value(sdk_result, 'finishedAt')
        if hasattr(finished_at, 'isoformat'):
            finished_at = finished_at.isoformat()
        elif finished_at:
            finished_at = str(finished_at)
        # Extract steps
        steps_raw = get_value(sdk_result, 'steps', [])
        steps = [self._to_jsonable(s) for s in steps_raw] if steps_raw else []
        return BrowserTaskResult(
            id=str(get_value(sdk_result, 'id', '')),
            session_id=self._extract_session_id(sdk_result),
            status=get_value(sdk_result, 'status'),
            is_success=get_value(sdk_result, 'is_success') or get_value(sdk_result, 'isSuccess'),
            done_output=get_value(sdk_result, 'done_output') or get_value(sdk_result, 'doneOutput') or get_value(sdk_result, 'output'),
            live_url=self._extract_live_url(sdk_result),
            started_at=started_at,
            finished_at=finished_at,
            metadata=get_value(sdk_result, 'metadata', {}),
            steps=steps,
        )
    # ---------- Helper methods ----------
    async def _set_status(
        self,
        item_id: str,
        state: str,
        context: Optional[Dict[str, Any]] = None,
        done_output: Optional[Any] = None,
    ) -> None:
        """Set status in both Convex and optionally Supabase"""
        await self.convex.set_item_status(
            item_id=item_id,
            state=state,
            context=context,
            done_output=done_output,
        )
        if SYNC_SUPABASE_STATUS and self.items_repo is not None:
            try:
                await asyncio.to_thread(self.items_repo.update_item_state, item_id, state)
            except Exception:
                pass
    async def _emit_full_view_to_logs(self, item_id: str, result: BrowserTaskResult) -> None:
        """Emit all steps to logs"""
        steps = result.steps or []
        for s in steps:
            await self.logs.add_log(
                LogCreate(item_id=item_id, message=self._fmt_step(s), level="info", metadata={"step": s})
            )
    def _resolve_secrets_from_task(self, task_text: str) -> Dict[str, str]:
        """Extract secrets from task text using <secret> tags"""
        keys = set(re.findall(r"<secret>([^<]+)</secret>", task_text or ""))
        out: Dict[str, str] = {}
        for key in keys:
            norm = re.sub(r"[^A-Za-z0-9]", "_", key).upper()
            for candidate in (norm, f"SECRET__{norm}", f"BROWSER_USE_SECRET__{norm}"):
                val = os.getenv(candidate)
                if val:
                    out[key] = val
                    break
        return out
    def _to_jsonable(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format"""
        try:
            if hasattr(obj, "model_dump"):
                return obj.model_dump(mode="json")
            elif hasattr(obj, "__dict__"):
                return obj.__dict__
            elif isinstance(obj, dict):
                return obj
            else:
                return json.loads(json.dumps(obj, default=lambda o: getattr(o, "__dict__", str(o))))
        except Exception:
            try:
                return str(obj)
            except Exception:
                return None
    def _fmt_step(self, step: Any) -> str:
        """Format step for logging"""
        if isinstance(step, dict):
            num = step.get('number', 0)
            url = step.get('url', 'unknown')
            actions = step.get('actions', [])
        else:
            num = getattr(step, 'number', 0)
            url = getattr(step, 'url', 'unknown')
            actions = getattr(step, 'actions', [])
        if not isinstance(actions, list):
            actions = [actions]
        actions_str = ", ".join([str(a) for a in actions])
        return f"[browser] step #{num} on {url}; actions: {actions_str}"