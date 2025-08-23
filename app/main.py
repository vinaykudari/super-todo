import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import items, logs, browser, orchestrator
from .config import LOG_LEVEL

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Super Todo API (Hackathon)")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info(f"Super Todo API starting up with log level: {LOG_LEVEL}")
    logger.info("Voice agent orchestration enabled")

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(items.router)
app.include_router(logs.router)
app.include_router(browser.router)
app.include_router(orchestrator.router)
