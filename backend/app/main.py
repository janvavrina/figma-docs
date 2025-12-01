"""Main FastAPI application for Figma Documentation Generator."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.services.figma import get_change_detector
from app.services.docs import get_doc_generator

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.logging.level),
    format=settings.logging.format,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Figma Documentation Generator...")
    
    # Initialize change detector
    detector = get_change_detector()
    await detector.initialize()
    
    # Register callback to regenerate docs on changes
    async def on_file_change(event):
        logger.info(f"File changed: {event.file_name}, regenerating docs...")
        generator = get_doc_generator()
        try:
            await generator.update_documentation(event.file_key)
            logger.info(f"Documentation updated for {event.file_name}")
        except Exception as e:
            logger.error(f"Failed to update documentation: {e}")
    
    detector.on_change(on_file_change)
    
    # Start change detection if there are watched files
    if detector.get_watched_files():
        detector.start()
        logger.info("Change detection started")
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")
    detector.stop()


# Create FastAPI app
app = FastAPI(
    title="Figma Documentation Generator",
    description="Generate user and developer documentation from Figma designs",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

# Mount static files for serving generated documentation
try:
    app.mount(
        "/docs-static",
        StaticFiles(directory=settings.documentation.output_dir),
        name="docs-static",
    )
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Figma Documentation Generator",
        "version": "1.0.0",
        "docs": "/docs",
        "api": "/api",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
    )

