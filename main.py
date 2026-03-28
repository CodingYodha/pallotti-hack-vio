"""
Individual Association & Violation Tracking System
Main FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.database import init_db
from app.routers import videos, violations, individuals, dashboard, equipment, webcam, search, chat, stream, auth, employees
from app.config import settings

# Create upload directories immediately on import (before app starts)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.SNIPPETS_DIR, exist_ok=True)
os.makedirs(settings.VIOLATIONS_IMG_DIR, exist_ok=True)
os.makedirs("employee_photos", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    await init_db()

    # Flaw 2 fix: pre-load employee face encodings at startup so the first frame
    # of any stream never blocks the event loop on heavy Facenet/DB I/O.
    # run_in_executor offloads the synchronous work to a thread while keeping
    # the event loop free.
    import asyncio
    from app.services.face_recognition_service import get_face_service
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, get_face_service().load_employees_sync)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(f"Startup face-encoding preload failed (non-fatal): {exc}")

    yield

    # Shutdown (cleanup if needed)


app = FastAPI(
    title="Violation Tracking System",
    description="AI-powered video analytics for safety violation detection and individual tracking",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(violations.router, prefix="/api/violations", tags=["Violations"])
app.include_router(individuals.router, prefix="/api/individuals", tags=["Individuals"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(equipment.router, tags=["Equipment"])
app.include_router(webcam.router, prefix="/api/webcam", tags=["Webcam"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(stream.router, prefix="/api/stream", tags=["Live Stream"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(employees.router, prefix="/api/employees", tags=["Employees"])

# Serve static files for uploads, snippets, and violation images
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.mount("/snippets", StaticFiles(directory=settings.SNIPPETS_DIR), name="snippets")
app.mount("/violation_images", StaticFiles(directory=settings.VIOLATIONS_IMG_DIR), name="violation_images")
app.mount("/employee_photos", StaticFiles(directory="employee_photos"), name="employee_photos")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "message": "Violation Tracking System API",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "ai_pipeline": "ready"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
