"""FastAPI backend for Ears language learning app.

Clean modular structure:
- api/models/      - Pydantic request/response models
- api/routers/     - API route handlers (thin layer)
- api/services/    - Business logic
- api/dependencies - Shared dependencies (db, settings)
"""

import sys
import asyncio
import warnings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Suppress Windows asyncio warnings (known harmless bug on Windows)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    warnings.filterwarnings('ignore', category=RuntimeWarning, module='asyncio')
    # Suppress ConnectionResetError from proactor event loop
    import logging
    logging.getLogger('asyncio').setLevel(logging.CRITICAL)

# Import routers
from api.routers import (
    health,
    vocabulary,
    transcripts,
    tts,
    learning,
    recordings,
    settings,
    backups,
)

# Import services for startup
from api.services.backup_service import BackupService

# Create FastAPI app
app = FastAPI(
    title="Ears",
    description="Language learning from real Swedish content",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(vocabulary.router, prefix="/api")
app.include_router(transcripts.router, prefix="/api")
app.include_router(tts.router, prefix="/api")
app.include_router(learning.router, prefix="/api")
app.include_router(recordings.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(backups.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print("\n🚀 Starting Ears backend...")
    print("✓ Ready!\n")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
