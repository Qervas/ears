"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Ears API", "status": "running"}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
