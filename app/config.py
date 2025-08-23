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

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")