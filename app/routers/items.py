from uuid import uuid4
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from ..supabase_client import supabase, SUPABASE_BUCKET
from ..schemas import ItemCreate, Item, ItemUpdateState, ItemWithAttachments, Attachment

router = APIRouter(prefix="/items", tags=["items"])

@router.post("", response_model=Item)
def create_item(payload: ItemCreate):
    res = supabase.table("items").insert({
        "title": payload.title,
        "description": payload.description,
    }).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create item")
    return res.data[0]

@router.get("", response_model=List[Item])
def list_items(
    state: Optional[str] = Query(default=None, pattern="^(pending|processing|completed)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = supabase.table("items").select("*").order("created_at", desc=True)
    if state:
        q = q.eq("state", state)
    # Supabase uses an inclusive range
    start = offset
    end = offset + limit - 1
    res = q.range(start, end).execute()
    return res.data or []

@router.get("/{item_id}", response_model=ItemWithAttachments)
def get_item(item_id: str):
    item_res = supabase.table("items").select("*").eq("id", item_id).limit(1).execute()
    item_rows = item_res.data or []
    if not item_rows:
        raise HTTPException(status_code=404, detail="Item not found")

    att_res = supabase.table("attachments").select("*").eq("item_id", item_id).order("created_at", desc=True).execute()
    return {
        **item_rows[0],
        "attachments": att_res.data or []
    }

@router.patch("/{item_id}/state", response_model=Item)
def update_state(item_id: str, payload: ItemUpdateState):
    res = supabase.table("items").update({"state": payload.state}).eq("id", item_id).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Item not found")
    return rows[0]

@router.post("/{item_id}/attachments", response_model=Attachment)
async def add_attachment(item_id: str, file: UploadFile = File(...)):
    # Ensure item exists
    item_check = supabase.table("items").select("id").eq("id", item_id).limit(1).execute()
    if not (item_check.data or []):
        raise HTTPException(status_code=404, detail="Item not found")

    # Upload to Supabase Storage
    raw = await file.read()
    path = f"{item_id}/{uuid4()}_{file.filename}"
    up_res = supabase.storage.from_(SUPABASE_BUCKET).upload(
        file=raw,
        path=path,
        file_options={"content-type": file.content_type or "application/octet-stream", "upsert": False},
    )
    if up_res.get("error"):
        raise HTTPException(status_code=500, detail=f"Upload failed: {up_res['error']}")

    pub = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(path)
    public_url = (pub.get("data") or {}).get("publicUrl")
    if not public_url:
        raise HTTPException(status_code=500, detail="Could not get public URL")

    # Record in DB
    ins = supabase.table("attachments").insert({
        "item_id": item_id,
        "name": file.filename,
        "path": path,
        "url": public_url,
        "mime_type": file.content_type,
        "size_bytes": len(raw),
    }).execute()
    if not ins.data:
        # best-effort cleanup (optional): you could delete the storage object here
        raise HTTPException(status_code=500, detail="Failed to record attachment")

    return ins.data[0]
