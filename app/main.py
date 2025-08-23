from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import items, logs, browser

app = FastAPI(title="Super Todo API (Hackathon)")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(items.router)
app.include_router(logs.router)
app.include_router(browser.router)