from supabase import create_client, Client
from .config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_BUCKET

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
