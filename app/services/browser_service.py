# app/services/browser_service.py
import os
import re
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

# SDK (pip install browser-use-sdk)
try:
    from browser_use_sdk import AsyncBrowserUse
except Exception as e:
    raise RuntimeError("browser-use-sdk is required. pip install browser-use-sdk") from e

from ..schemas import LogCreate
from ..services.logs_service import LogsService
from ..convex_client import ConvexService
from ..repositories.items_repository import ItemsRepository  # optional Supabase status sync


SYNC_SUPABASE_STATUS = os.getenv("SYNC_SUPABASE_STATUS", "true").lower() == "true"


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
    Runs Browser-Use Cloud tasks, streams updates into Convex logs,
    and mirrors item live_url/status in Convex (and optionally Supabase).
    """

    def __init__(self):
        api_key = os.getenv("BROWSER_USE_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Missing BROWSER_USE_API_KEY")
        self.client = AsyncBrowserUse(api_key=api_key)
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
            kwargs: Dict[str, Any] = {"task": payload.task}

            if payload.session_id:
                kwargs["session_id"] = payload.session_id
            if payload.model:
                kwargs["agent_settings"] = {"model": payload.model}

            browser_settings: Dict[str, Any] = {}
            if payload.allowed_domains:
                browser_settings["allowed_domains"] = payload.allowed_domains
            if payload.save_browser_data is not None:
                browser_settings["keep_alive"] = payload.save_browser_data
            if browser_settings:
                kwargs["browser_settings"] = browser_settings

            if payload.structured_output_json:
                kwargs["structured_output_json"] = payload.structured_output_json

            # carry item_id in metadata for traceability
            if payload.metadata:
                meta = dict(payload.metadata)
                if payload.item_id:
                    meta.setdefault("item_id", payload.item_id)
                kwargs["metadata"] = meta
            elif payload.item_id:
                kwargs["metadata"] = {"item_id": payload.item_id}

            if payload.included_file_names:
                kwargs["included_file_names"] = payload.included_file_names

            # Secrets: explicit > env-derived from <secret>... placeholders
            merged = self._resolve_secrets_from_task(payload.task)
            if payload.secrets:
                merged.update(payload.secrets)
            if merged:
                kwargs["secrets"] = merged

            # mark processing up front
            if payload.item_id:
                await self._set_status(payload.item_id, "processing")

            if payload.wait:
                view = await self.client.tasks.run(**kwargs)
                result = self._to_result(view)

                # live_url mirror
                if payload.item_id and result.live_url:
                    await self.convex.set_item_live_url(payload.item_id, result.live_url)

                # emit steps and finalize
                if payload.item_id:
                    await self._emit_full_view_to_logs(payload.item_id, result)
                    if result.is_success:
                        await self._set_status(
                            payload.item_id, "completed", context=None, done_output=result.done_output
                        )
                    else:
                        await self._set_status(
                            payload.item_id,
                            "pending",
                            context={"status": result.status},
                            done_output=result.done_output,
                        )
                return result

            # async create + background stream
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
                lu = self._session_live_url(view)
                if payload.item_id and lu:
                    await self.convex.set_item_live_url(payload.item_id, lu)
                live_url = lu
            except Exception:
                pass

            if payload.item_id:
                asyncio.create_task(self.stream_task_to_logs(task_id, payload.item_id))

            return BrowserTaskCreated(task_id=task_id, session_id=session_id, live_url=live_url)

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
            url = getattr(resp, "download_url", None) or getattr(resp, "downloadUrl", None) \
                or (resp.get("download_url") if isinstance(resp, dict) else None) \
                or (resp.get("downloadUrl") if isinstance(resp, dict) else None)
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
                # never crash the background task on log errors
                pass

        try:
            await emit(f"[browser] stream started for task {task_id}", "debug", {"task_id": task_id})

            async for update in self.client.tasks.stream(task_id):
                # raw payload
                raw_json = self._to_jsonable(update)
                await emit("[browser] raw_update", "debug", {"task_id": task_id, "raw": raw_json})

                # live_url (once)
                if not live_url_set:
                    lu = self._session_live_url(update) or None
                    print("live_url", lu)
                    if lu:
                        await self.convex.set_item_live_url(item_id, lu)
                        live_url_set = True

                # status
                status = self._get(update, "status")
                if status:
                    await emit(f"[browser] status: {status}", "debug", {"task_id": task_id})

                # new steps
                steps = self._get(update, "steps", default=[]) or []
                for s in steps:
                    num = self._get(s, "number", default=0)
                    if num <= last_step_no:
                        continue
                    await emit(self._fmt_step(s), "info", {"task_id": task_id, "step": self._to_jsonable(s)})
                    last_step_no = max(last_step_no, num)

                # completion
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

        except Exception as e:
            await emit(f"[browser] stream error: {str(e)}", "error", {"task_id": task_id})
            await self._set_status(item_id, "pending", context={"error": str(e)}, done_output=None)

    # ---------- Helpers ----------

    async def _set_status(
        self,
        item_id: str,
        state: str,
        context: Optional[Dict[str, Any]] = None,
        done_output: Optional[Any] = None,
    ) -> None:
        """
        Mirror status to Convex (and best-effort to Supabase if enabled).
        Accepts optional done_output so completion can atomically attach results.
        """
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
                # Best-effort mirror; never fail the stream on Supabase error
                pass

    async def _emit_full_view_to_logs(self, item_id: str, result: BrowserTaskResult) -> None:
        steps = result.steps or []
        for s in steps:
            await self.logs.add_log(
                LogCreate(
                    item_id=item_id,
                    message=self._fmt_step(s),
                    level="info",
                    metadata={"step": s},
                )
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
        """
        Extract <secret>keys</secret> from task and map to env without hardcoding domains:
          KEY -> $KEY | $SECRET__KEY | $BROWSER_USE_SECRET__KEY
        """
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
        """
        Convert SDK update objects (Pydantic models) into JSON-safe dicts.
        - Uses .model_dump(mode="json") when available (Pydantic v2).
        - Falls back to plain dict / __dict__ / string as last resort.
        """
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