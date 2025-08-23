import os
import re
import asyncio
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator


from browser_use_sdk import AsyncBrowserUse

from ..schemas import LogCreate
from ..services.logs_service import LogsService


# -------------------- IO MODELS --------------------

class BrowserTaskRequest(BaseModel):
    """
    Natural-language Browser-Use task.

    Use <secret>placeholders</secret> in `task`; we'll fill from:
      1) `secrets` dict provided here (wins),
      2) environment variables derived from the placeholder (no hardcoding).

    Example:
      task="Return my sunscreen from Amazon. Login with <secret>amazon_email</secret> and <secret>amazon_password</secret>."
    """
    task: str = Field(..., description="Natural-language task for the agent")
    item_id: Optional[str] = Field(
        default=None, description="If provided, we stream step logs to this item via LogsService"
    )
    session_id: Optional[str] = Field(
        default=None, description="Continue in existing session"
    )
    wait: bool = Field(
        default=False, description="Wait until completion and return final output"
    )
    allowed_domains: Optional[List[str]] = Field(
        default=None, description="Domain sandboxing, e.g. ['https://*.amazon.com']"
    )
    model: Optional[str] = Field(
        default=None, description="LLM model override (Cloud default if omitted)"
    )
    structured_output_json: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON schema for structured output"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Arbitrary metadata; we pass through to Cloud"
    )
    included_file_names: Optional[List[str]] = Field(
        default=None, description="File names previously uploaded via presigned URL"
    )
    secrets: Optional[Dict[str, str]] = Field(
        default=None,
        description="Key/value secrets referenced in the task with <secret>key</secret>",
    )
    save_browser_data: Optional[bool] = Field(
        default=None,
        description="Hints to keep session/browser alive longer (Cloud heuristic)",
    )


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

    @field_validator('started_at', 'finished_at', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    @field_validator('steps', mode='before')
    @classmethod
    def convert_steps_to_dict(cls, v):
        if v is None:
            return v
        if isinstance(v, list):
            result = []
            for step in v:
                if hasattr(step, '__dict__'):
                    # Convert object to dict using __dict__ directly to avoid FieldInfo
                    step_dict = {}
                    obj_dict = step.__dict__
                    for attr_name, attr_value in obj_dict.items():
                        if not attr_name.startswith('_') and not callable(attr_value):
                            # Skip Pydantic FieldInfo objects and other non-serializable types
                            if not str(type(attr_value)).startswith("<class 'pydantic"):
                                step_dict[attr_name] = attr_value
                    result.append(step_dict)
                elif isinstance(step, dict):
                    result.append(step)
                else:
                    # Try to convert to dict if possible
                    try:
                        result.append(dict(step))
                    except Exception:
                        result.append({"raw": str(step)})
            return result
        return v


class BrowserLogsUrl(BaseModel):
    download_url: str


# -------------------- SERVICE --------------------

class BrowserService:
    def __init__(self):
        api_key = os.getenv("BROWSER_USE_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Missing BROWSER_USE_API_KEY")
        self.client = AsyncBrowserUse(api_key=api_key)

    # ---- Public API ----

    async def run_task(
        self,
        payload: BrowserTaskRequest,
    ) -> Union[BrowserTaskCreated, BrowserTaskResult]:
        """
        Create or run a Browser Use task. If `wait=True` returns final result,
        else returns task + session IDs immediately. Optionally starts a log
        monitor for `item_id`.
        """
        try:
            kwargs: Dict[str, Any] = {
                "task": payload.task,
            }

            if payload.session_id:
                kwargs["session_id"] = payload.session_id

            if payload.model:
                kwargs["agent_settings"] = {"model": payload.model}

            browser_settings: Dict[str, Any] = {}
            if payload.allowed_domains:
                browser_settings["allowed_domains"] = payload.allowed_domains
            if payload.save_browser_data is not None:
                # Cloud doesn't expose a perfect knob; this nudges persistence.
                browser_settings["keep_alive"] = payload.save_browser_data
            if browser_settings:
                kwargs["browser_settings"] = browser_settings

            if payload.structured_output_json:
                kwargs["structured_output_json"] = payload.structured_output_json
            if payload.metadata:
                kwargs["metadata"] = payload.metadata
            if payload.included_file_names:
                kwargs["included_file_names"] = payload.included_file_names

            # Merge secrets: explicit > derived from <secret>... placeholders
            merged_secrets = dict(self._resolve_secrets_from_task(payload.task))
            if payload.secrets:
                merged_secrets.update(payload.secrets)
            if merged_secrets:
                kwargs["secrets"] = merged_secrets

            if payload.wait:
                view = await self.client.tasks.run(**kwargs)
                result = self._to_result(view)
                # If item_id provided, backfill all steps to logs once:
                if payload.item_id:
                    await self._emit_full_view_to_logs(payload.item_id, result)
                return result

            created = await self.client.tasks.create(**kwargs)
            task_id = getattr(created, "id", None) or created["id"]
            session_id = (
                getattr(created, "session_id", None)
                or getattr(created, "sessionId", None)
                or created.get("sessionId")
            )

            live_url = None
            try:
                view = await self.client.tasks.retrieve(task_id)
                live_url = self._session_live_url(view)
            except Exception:
                pass

            # Start background monitor if item_id provided
            if payload.item_id:
                asyncio.create_task(
                    self.monitor_task_to_logs(
                        task_id=task_id,
                        item_id=payload.item_id,
                        poll_interval=1.2,
                    )
                )

            return BrowserTaskCreated(task_id=task_id, session_id=session_id, live_url=live_url)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to run browser task: {str(e)}")

    async def get_task(self, task_id: str) -> BrowserTaskResult:
        try:
            view = await self.client.tasks.retrieve(task_id)
            return self._to_result(view)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")

    async def get_task_logs(self, task_id: str) -> BrowserLogsUrl:
        try:
            resp = await self.client.tasks.get_logs(task_id)
            download_url = getattr(resp, "download_url", None) or getattr(resp, "downloadUrl", None) \
                or (resp.get("download_url") or resp.get("downloadUrl"))
            if not download_url:
                raise RuntimeError("No download URL returned from Browser Use.")
            return BrowserLogsUrl(download_url=download_url)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get task logs: {str(e)}")

    # ---- Log Streaming (polling monitor) ----

    async def monitor_task_to_logs(
        self,
        task_id: str,
        item_id: str,
        poll_interval: float = 1.0,
        timeout_seconds: int = 15 * 60,
        logs_service: Optional[LogsService] = None,
    ) -> None:
        """
        Polls `Get Task` and emits new steps / status transitions to LogsService under `item_id`.
        This pairs with your existing /logs/stream/{item_id} endpoint for real-time UI.
        """
        svc = logs_service or LogsService()
        last_step_count = 0
        last_status = None

        async def emit(message: str, level: str = "info", metadata: Optional[Dict[str, Any]] = None):
            await svc.add_log(LogCreate(item_id=item_id, message=message, level=level, metadata=metadata or {}))

        try:
            await emit(f"[browser] monitor started for task {task_id}", "debug", {"task_id": task_id})

            # First snapshot
            view = await self.client.tasks.retrieve(task_id)
            cur = self._to_result(view)
            last_status = cur.status
            if cur.status:
                await emit(f"[browser] status: {cur.status}", "debug")

            if cur.steps:
                last_step_count = len(cur.steps)
                # Emit already-available steps once
                for s in cur.steps:
                    await emit(self._fmt_step(s), "info", {"task_id": task_id, "step": s})

            # Loop
            deadline = asyncio.get_event_loop().time() + timeout_seconds
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(poll_interval)
                view = await self.client.tasks.retrieve(task_id)
                cur = self._to_result(view)

                # New status?
                if cur.status and cur.status != last_status:
                    await emit(f"[browser] status: {cur.status}", "debug", {"task_id": task_id})
                    last_status = cur.status

                # New steps?
                steps = cur.steps or []
                if len(steps) > last_step_count:
                    for s in steps[last_step_count:]:
                        await emit(self._fmt_step(s), "info", {"task_id": task_id, "step": s})
                    last_step_count = len(steps)

                # Done?
                if cur.status in {"finished", "stopped", "failed", "error", "completed"}:
                    await emit(
                        "[browser] task finished",
                        "info",
                        {"task_id": task_id, "is_success": cur.is_success, "done_output": cur.done_output},
                    )
                    break

            else:
                await emit("[browser] monitor timeout reached; stopping monitor", "warning", {"task_id": task_id})

        except Exception as e:
            # Best-effort error log, never crash server
            try:
                await emit(f"[browser] monitor error: {str(e)}", "error", {"task_id": task_id})
            except Exception:
                pass

    # ---- Helpers ----

    def _to_result(self, view: Any) -> BrowserTaskResult:
        def g(obj: Any, *names: str, default=None):
            for n in names:
                if hasattr(obj, n):
                    return getattr(obj, n)
                if isinstance(obj, dict) and n in obj:
                    return obj[n]
            return default

        session = g(view, "session", default=None) or {}
        live_url = self._session_live_url(view)

        return BrowserTaskResult(
            id=g(view, "id"),
            session_id=g(view, "session_id", "sessionId"),
            status=g(view, "status"),
            is_success=g(view, "is_success", "isSuccess"),
            done_output=g(view, "done_output", "doneOutput"),
            live_url=live_url,
            started_at=g(view, "started_at", "startedAt"),
            finished_at=g(view, "finished_at", "finishedAt"),
            metadata=g(view, "metadata", default={}),
            steps=g(view, "steps", default=[]),
        )

    def _session_live_url(self, view: Any) -> Optional[str]:
        try:
            session = getattr(view, "session", None) or (view.get("session") if isinstance(view, dict) else None)
            if not session:
                return None
            return getattr(session, "live_url", None) or getattr(session, "liveUrl", None) \
                or (session.get("live_url") or session.get("liveUrl"))
        except Exception:
            return None

    def _resolve_secrets_from_task(self, task_text: str) -> Dict[str, str]:
        """
        Find all <secret>key</secret> in the task and look up env vars for each key.
        No domain hardcoding. We try a few common patterns:
          - KEY (uppercased, non-alnum -> '_')
          - SECRET__KEY
          - BROWSER_USE_SECRET__KEY
        """
        keys = set(re.findall(r"<secret>([^<]+)</secret>", task_text or ""))
        out: Dict[str, str] = {}
        for key in keys:
            norm = re.sub(r"[^A-Za-z0-9]", "_", key).upper()
            candidates = [
                norm,
                f"SECRET__{norm}",
                f"BROWSER_USE_SECRET__{norm}",
            ]
            for env_key in candidates:
                val = os.getenv(env_key)
                if val:
                    out[key] = val
                    break
        return out

    def _fmt_step(self, step: Dict[str, Any]) -> str:
        num = step.get("number")
        url = step.get("url")
        acts = step.get("actions") or []
        acts_s = ", ".join(acts) if isinstance(acts, list) else str(acts)
        return f"[browser] step #{num} on {url or 'unknown'}; actions: {acts_s}"
