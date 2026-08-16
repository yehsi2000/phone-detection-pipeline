import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from server.database import init_db, DATABASE_DIR
from server.api.telemetry import router as telemetry_router
from server.api.triage import router as triage_router
from server.api.training import router as training_router
from server.api.model_dist import router as model_dist_router

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(SERVER_DIR, "static")
TEMPLATES_DIR = os.path.join(SERVER_DIR, "templates")
UPLOADS_DIR = os.path.join(DATABASE_DIR, "uploads")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[Central Server] Initializing database and storage...")
    init_db()
    print("[Central Server] Startup complete. Dashboard running on http://localhost:8000")
    yield
    # Shutdown
    print("[Central Server] Shutting down...")


app = FastAPI(
    title="Phone Detection Central Server & MLOps Dashboard",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for distributed clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(telemetry_router)
app.include_router(triage_router)
app.include_router(training_router)
app.include_router(model_dist_router)

# Mount Static Assets & Upload Storage
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/storage/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serves the central Web Admin Dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "phone-detection-central-server"}
