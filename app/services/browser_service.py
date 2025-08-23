import os
import re
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

# Optional SDK only for streaming; REST for everything else
try:
    from browser_use_sdk import AsyncBrowserUse
except Exception:
    AsyncBrowserUse = None

from ..schemas import LogCreate
from ..services.logs_service import LogsService
from ..convex_client import ConvexService
from ..repositories.items_repository import ItemsRepository  # optional Supabase status sync


SYNC_SUPABASE_STATUS = os.getenv("SYNC_SUPABASE_STATUS", "true").lower() == "true"
BROWSER_USE_API_KEY = os.getenv("BROWSER_USE_API_KEY") or ""

API_BASES = [
    # Try canonical first; fall back variants handle version differences
    "https://api.browser-use.com/api/v1",
    "https://api.browser-use.com/v1",
    "https://api.browser-use.com",  # some deployments mount /tasks at the root
]



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
    Uses Browser-Use Cloud REST for create/run/retrieve (robust across SDK versions).
    Uses SDK stream (when available) for step-by-step updates.
    Mirrors live_url/status/done_output to Convex and emits raw update logs.
    """

    def __init__(self):
        if not BROWSER_USE_API_KEY:
            raise HTTPException(status_code=500, detail="Missing BROWSER_USE_API_KEY")
        self.http = httpx.AsyncClient(timeout=60)
        self.sdk = AsyncBrowserUse(api_key=BROWSER_USE_API_KEY) if AsyncBrowserUse else None
        self.logs = LogsService()
        self.convex = ConvexService()
        self.items_repo = ItemsRepository() if SYNC_SUPABASE_STATUS else None

    # ---------- Public API ----------

    async def run_task(self, payload: BrowserTaskRequest) -> Union[BrowserTaskCreated, BrowserTaskResult]:
        """
        Start a Browser-Use task. When item_id is provided:
          • set state=processing
          • mirror live_url when available
          • stream logs and finalize with done_output on completion
        """
        try:
            # Build REST body; include both snake_case and camelCase for forward-compat.
            request: Dict[str, Any] = {"task": payload.task}

            # Attach to an existing session
            if payload.session_id:
                request["sessionId"] = payload.session_id  # body expects camelCase in many deployments

            # Agent / Browser settings
            if payload.model:
                request["agent_settings"] = {"model": payload.model}
                request["agentSettings"] = {"model": payload.model}  # dual-form

            browser_settings: Dict[str, Any] = {}
            if payload.allowed_domains:
                browser_settings["allowed_domains"] = payload.allowed_domains
                browser_settings["allowedDomains"] = payload.allowed_domains
            if payload.save_browser_data is not None:
                # a few variants exist: keepAlive / saveBrowserData
                browser_settings["keep_alive"] = payload.save_browser_data
                browser_settings["keepAlive"] = payload.save_browser_data
                browser_settings["save_browser_data"] = payload.save_browser_data
                browser_settings["saveBrowserData"] = payload.save_browser_data
            if browser_settings:
                request["browser_settings"] = browser_settings
                request["browserSettings"] = browser_settings

            # Structured output
            if payload.structured_output_json:
                request["structured_output_json"] = payload.structured_output_json
                request["structuredOutputJson"] = payload.structured_output_json

            # Metadata (carry item_id for traceability)
            if payload.metadata:
                meta = dict(payload.metadata)
                if payload.item_id:
                    meta.setdefault("item_id", payload.item_id)
                request["metadata"] = meta
            elif payload.item_id:
                request["metadata"] = {"item_id": payload.item_id}

            # Include files
            if payload.included_file_names:
                request["included_file_names"] = payload.included_file_names
                request["includedFileNames"] = payload.included_file_names

            # If you’re not using secrets now, skip. (Leave resolver to keep compatibility.)
            merged = self._resolve_secrets_from_task(payload.task)
            if payload.secrets:
                merged.update(payload.secrets)
            if merged:
                request["secrets"] = merged

            # Mark processing up front
            if payload.item_id:
                await self._set_status(payload.item_id, "processing")

            headers = {"Authorization": f"Bearer {BROWSER_USE_API_KEY}"}

            if payload.wait:
                # Synchronous run
                view = await self._http_run_task(request, headers)
                result = self._to_result(view)

                if payload.item_id and result.live_url:
                    await self.convex.set_item_live_url(payload.item_id, result.live_url)

                if payload.item_id:
                    await self._emit_full_view_to_logs(payload.item_id, result)
                    if result.is_success:
                        await self._set_status(payload.item_id, "completed", context=None, done_output=result.done_output)
                    else:
                        await self._set_status(
                            payload.item_id,
                            "pending",
                            context={"status": result.status},
                            done_output=result.done_output,
                        )
                return result

            # Async create + background stream
            created = await self._http_create_task(request, headers)
            task_id = created.get("id") or created.get("taskId") or ""
            session_id = (
                created.get("sessionId")
                or created.get("session_id")
                or (created.get("session", {}) or {}).get("id")
                or ""
            )

            live_url = None
            try:
                view = await self._http_retrieve_task(task_id, headers)
                lu = self._session_live_url(view)
                if payload.item_id and lu:
                    await self.convex.set_item_live_url(payload.item_id, lu)
                live_url = lu
            except Exception as e:
                await self._debug_log(payload.item_id, f"[browser] retrieve after create failed: {e}")

            if payload.item_id:
                asyncio.create_task(self.stream_task_to_logs(task_id, payload.item_id))

            return BrowserTaskCreated(task_id=task_id, session_id=session_id, live_url=live_url)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to run browser task: {str(e)}")

    async def get_task(self, task_id: str) -> BrowserTaskResult:
        try:
            headers = {"Authorization": f"Bearer {BROWSER_USE_API_KEY}"}
            view = await self._http_retrieve_task(task_id, headers)
            return self._to_result(view)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")

    async def get_task_logs(self, task_id: str) -> BrowserLogsUrl:
        try:
            headers = {"Authorization": f"Bearer {BROWSER_USE_API_KEY}"}
            data = await self._http_get_task_logs(task_id, headers)
            url = (
                data.get("download_url")
                or data.get("downloadUrl")
                or (data.get("logs", {}) or {}).get("downloadUrl")
            )
            if not url:
                raise RuntimeError("No download URL returned from Browser Use.")
            return BrowserLogsUrl(download_url=url)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get task logs: {str(e)}")

    async def stream_task_to_logs(self, task_id: str, item_id: str) -> None:
        """
        Subscribe to Browser-Use updates -> emit raw + pretty logs,
        mirror live_url once, and finalize status with done_output.
        """
        last_step_no = 0
        live_url_set = False

        async def emit(msg: str, level: str = "info", meta: Optional[Dict[str, Any]] = None):
            try:
                await self.logs.add_log(
                    LogCreate(item_id=item_id, message=msg, level=level, metadata=meta or {})
                )
            except Exception:
                pass

        try:
            await emit(f"[browser] stream started for task {task_id}", "debug", {"task_id": task_id})

            # Prefer SDK stream if available; otherwise poll as a fallback
            if self.sdk and hasattr(self.sdk, "tasks") and hasattr(self.sdk.tasks, "stream"):
                async for update in self.sdk.tasks.stream(task_id):  # type: ignore[attr-defined]
                    raw_json = self._to_jsonable(update)
                    await emit("[browser] raw_update", "debug", {"task_id": task_id, "raw": raw_json})

                    if not live_url_set:
                        lu = self._session_live_url(update) or None
                        if lu:
                            await self.convex.set_item_live_url(item_id, lu)
                            live_url_set = True

                    status = self._get(update, "status")
                    if status:
                        await emit(f"[browser] status: {status}", "debug", {"task_id": task_id})

                    steps = self._get(update, "steps", default=[]) or []
                    for s in steps:
                        num = self._get(s, "number", default=0)
                        if num <= last_step_no:
                            continue
                        await emit(self._fmt_step(s), "info", {"task_id": task_id, "step": self._to_jsonable(s)})
                        last_step_no = max(last_step_no, num)

                    if status in {"finished", "stopped", "failed", "error", "completed"}:
                        done_output = self._get(update, "done_output") or self._get(update, "doneOutput")
                        is_success = self._get(update, "is_success") or self._get(update, "isSuccess")

                        await emit(
                            "[browser] task finished",
                            "info",
                            {"task_id": task_id, "is_success": is_success, "done_output": self._to_jsonable(done_output)},
                        )

                        if is_success:
                            await self._set_status(item_id, "completed", context=None, done_output=done_output)
                        else:
                            await self._set_status(
                                item_id,
                                "pending",
                                context={"status": status},
                                done_output=done_output,
                            )
                        break
            else:
                # Poll every 2s as a fallback (no SDK)
                headers = {"Authorization": f"Bearer {BROWSER_USE_API_KEY}"}
                while True:
                    update = await self._http_retrieve_task(task_id, headers)
                    raw_json = self._to_jsonable(update)
                    await emit("[browser] raw_update", "debug", {"task_id": task_id, "raw": raw_json})

                    if not live_url_set:
                        lu = self._session_live_url(update) or None
                        if lu:
                            await self.convex.set_item_live_url(item_id, lu)
                            live_url_set = True

                    status = self._get(update, "status")
                    if status:
                        await emit(f"[browser] status: {status}", "debug", {"task_id": task_id})

                    steps = self._get(update, "steps", default=[]) or []
                    for s in steps:
                        num = self._get(s, "number", default=0)
                        if num <= last_step_no:
                            continue
                        await emit(self._fmt_step(s), "info", {"task_id": task_id, "step": self._to_jsonable(s)})
                        last_step_no = max(last_step_no, num)

                    if status in {"finished", "stopped", "failed", "error", "completed"}:
                        done_output = self._get(update, "done_output") or self._get(update, "doneOutput")
                        is_success = self._get(update, "is_success") or self._get(update, "isSuccess")

                        await emit(
                            "[browser] task finished",
                            "info",
                            {"task_id": task_id, "is_success": is_success, "done_output": self._to_jsonable(done_output)},
                        )

                        if is_success:
                            await self._set_status(item_id, "completed", context=None, done_output=done_output)
                        else:
                            await self._set_status(
                                item_id,
                                "pending",
                                context={"status": status},
                                done_output=done_output,
                            )
                        break

                    await asyncio.sleep(2)

        except Exception as e:
            await emit(f"[browser] stream error: {str(e)}", "error", {"task_id": task_id})
            await self._set_status(item_id, "pending", context={"error": str(e)}, done_output=None)

    # ---------- HTTP helpers ----------

    async def _http_create_task(self, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        # Try common endpoints for "create task"
        paths = ["/run-task", "/tasks/run", "/tasks", "/task", "/create-task"]
        for base in API_BASES:
            for path in paths:
                url = f"{base}{path}"
                try:
                    r = await self.http.post(url, json=body, headers=headers)
                    if r.status_code in (200, 201):
                        return r.json()
                except Exception:
                    continue
        raise RuntimeError("All create-task endpoints failed")

    async def _http_run_task(self, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        # Try common endpoints for "run task synchronously"
        paths = ["/run-task", "/tasks/run"]
        for base in API_BASES:
            for path in paths:
                url = f"{base}{path}"
                try:
                    r = await self.http.post(url, json=body, headers=headers)
                    if r.status_code in (200, 201):
                        return r.json()
                except Exception:
                    continue
        raise RuntimeError("All run-task endpoints failed")

    async def _http_retrieve_task(self, task_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
        paths = [f"/tasks/{task_id}", f"/task/{task_id}"]
        for base in API_BASES:
            for path in paths:
                url = f"{base}{path}"
                try:
                    r = await self.http.get(url, headers=headers)
                    if r.status_code in (200, 201):
                        return r.json()
                except Exception:
                    continue
        raise RuntimeError("All retrieve-task endpoints failed")

    async def _http_get_task_logs(self, task_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
        paths = [f"/tasks/{task_id}/logs", f"/task/{task_id}/logs"]
        for base in API_BASES:
            for path in paths:
                url = f"{base}{path}"
                try:
                    r = await self.http.get(url, headers=headers)
                    if r.status_code in (200, 201):
                        return r.json()
                except Exception:
                    continue
        raise RuntimeError("All get-task-logs endpoints failed")

    async def _debug_log(self, item_id: Optional[str], message: str, meta: Optional[Dict[str, Any]] = None):
        try:
            await self.logs.add_log(
                LogCreate(item_id=item_id or "n/a", message=message, level="debug", metadata=meta or {})
            )
        except Exception:
            pass

    # ---------- Helpers ----------

    async def _set_status(
        self,
        item_id: str,
        state: str,
        context: Optional[Dict[str, Any]] = None,
        done_output: Optional[Any] = None,
    ) -> None:
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
        steps = result.steps or []
        for s in steps:
            await self.logs.add_log(
                LogCreate(item_id=item_id, message=self._fmt_step(s), level="info", metadata={"step": s})
            )

    def _to_result(self, view: Any) -> BrowserTaskResult:
        # timestamps
        started_at = self._get(view, "started_at") or self._get(view, "startedAt")
        if hasattr(started_at, "isoformat"):
            started_at = started_at.isoformat()
        elif started_at is not None:
            started_at = str(started_at)

        finished_at = self._get(view, "finished_at") or self._get(view, "finishedAt")
        if hasattr(finished_at, "isoformat"):
            finished_at = finished_at.isoformat()
        elif finished_at is not None:
            finished_at = str(finished_at)

        # steps -> JSONable dicts
        steps_raw = self._get(view, "steps", default=[]) or []
        steps: List[Dict[str, Any]] = [self._to_jsonable(s) for s in steps_raw]

        return BrowserTaskResult(
            id=self._get(view, "id"),
            session_id=self._get(view, "session_id") or self._get(view, "sessionId"),
            status=self._get(view, "status"),
            is_success=self._get(view, "is_success") or self._get(view, "isSuccess"),
            done_output=self._get(view, "done_output") or self._get(view, "doneOutput"),
            live_url=self._session_live_url(view),
            started_at=started_at,
            finished_at=finished_at,
            metadata=self._get(view, "metadata", default={}),
            steps=steps,
        )

    def _session_live_url(self, view: Any) -> Optional[str]:
        session = self._get(view, "session", default=None) or {}
        if not session:
            return None
        return self._get(session, "live_url") or self._get(session, "liveUrl")

    def _resolve_secrets_from_task(self, task_text: str) -> Dict[str, str]:
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
        try:
            if hasattr(obj, "model_dump"):
                return obj.model_dump(mode="json")  # type: ignore[attr-defined]
            if isinstance(obj, dict):
                return obj
            return json.loads(json.dumps(obj, default=lambda o: getattr(o, "__dict__", str(o))))
        except Exception:
            try:
                return str(obj)
            except Exception:
                return None

    def _get(self, obj: Any, name: str, default=None):
        if hasattr(obj, name):
            return getattr(obj, name)
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        return default

    def _fmt_step(self, step: Dict[str, Any]) -> str:
        num = self._get(step, "number", 0)
        url = self._get(step, "url", "unknown")
        acts = self._get(step, "actions", [])
        if not isinstance(acts, list):
            acts = [acts]
        acts_s = ", ".join([str(a) for a in acts])
        return f"[browser] step #{num} on {url}; actions: {acts_s}"