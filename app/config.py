"""Application configuration"""

import os
from dotenv import load_dotenv

load_dotenv()

# Server configuration
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
BASE_URL = os.getenv("BASE_URL", f"http://{SERVER_HOST}:{SERVER_PORT}")

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "attachments")

# Orchestrator configuration
ORCHESTRATOR_ENABLED = os.getenv("ORCHESTRATOR_ENABLED", "true").lower() == "true"
AI_CONFIDENCE_THRESHOLD = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.6"))

# VAPI Voice Agent configuration
VAPI_TOKEN = os.getenv("VAPI_TOKEN")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "ab2953ac-1a50-403a-af6e-710cfa8bec1f")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")
VAPI_WEBHOOK_URL = os.getenv("VAPI_WEBHOOK_URL")
VOICE_AGENT_ENABLED = os.getenv("VOICE_AGENT_ENABLED", "true").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")