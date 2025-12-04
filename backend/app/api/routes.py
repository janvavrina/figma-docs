"""API routes for Figma Documentation Generator."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.core.config import settings
from app.models.doc_models import (
    ChatRequest,
    ChatResponse,
    CodeAnalysisRequest,
    DocFormat,
    DocType,
    GenerateDocsRequest,
)
from app.models.figma_models import WatchedFile
from app.services.docs import get_doc_generator
from app.services.figma import FigmaService, get_change_detector
from app.services.llm import get_llm_service

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Health & Status ---

@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Get system status."""
    detector = get_change_detector()
    return {
        "status": "running",
        "change_detection": {
            "running": detector.is_running,
            "polling_interval_minutes": detector.polling_interval,
            "watched_files_count": len(detector.get_watched_files()),
        },
        "config": {
            "ollama_url": settings.llm.ollama_base_url,
            "default_model": settings.llm.default_model,
        },
    }


# --- Figma Team/Project Browser ---

@router.get("/figma/me")
async def get_figma_user() -> dict[str, Any]:
    """Get current Figma user info (to verify API token)."""
    figma = FigmaService()
    try:
        user = await figma.get_me()
        return user
    except Exception as e:
        logger.error(f"Error fetching Figma user: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid Figma API token or connection error: {e}")
    finally:
        await figma.close()


@router.get("/figma/teams/{team_id}/projects")
async def get_team_projects(team_id: str) -> list[dict[str, Any]]:
    """Get all projects in a Figma team."""
    figma = FigmaService()
    try:
        projects = await figma.get_team_projects(team_id)
        return projects
    except Exception as e:
        logger.error(f"Error fetching team projects for team {team_id}: {e}")
        error_msg = str(e)
        if "403" in error_msg:
            raise HTTPException(status_code=403, detail="Access denied. Make sure your API token has access to this team.")
        elif "404" in error_msg:
            raise HTTPException(status_code=404, detail=f"Team not found. Check if team ID '{team_id}' is correct.")
        elif "401" in error_msg:
            raise HTTPException(status_code=401, detail="Invalid API token. Check your FIGMA_API_TOKEN.")
        raise HTTPException(status_code=400, detail=f"Could not fetch team projects: {e}")
    finally:
        await figma.close()


@router.get("/figma/projects/{project_id}/files")
async def get_project_files(project_id: str) -> list[dict[str, Any]]:
    """Get all files in a Figma project."""
    figma = FigmaService()
    try:
        files = await figma.get_project_files(project_id)
        return files
    except Exception as e:
        logger.error(f"Error fetching project files: {e}")
        raise HTTPException(status_code=400, detail=f"Could not fetch project files: {e}")
    finally:
        await figma.close()


# --- Figma Files ---

class AddWatchedFileRequest(BaseModel):
    file_key: str
    name: str = ""


@router.get("/figma/files")
async def list_watched_files() -> list[dict[str, Any]]:
    """List all watched Figma files."""
    detector = get_change_detector()
    files = detector.get_watched_files()
    return [
        {
            "file_key": f.file_key,
            "name": f.name,
            "last_version": f.last_version,
            "last_modified": f.last_modified.isoformat() if f.last_modified else None,
            "last_checked": f.last_checked.isoformat() if f.last_checked else None,
            "doc_generated": f.doc_generated,
        }
        for f in files
    ]


@router.post("/figma/files")
async def add_watched_file(request: AddWatchedFileRequest) -> dict[str, Any]:
    """Add a Figma file to watch."""
    detector = get_change_detector()
    
    # Verify file exists
    figma = FigmaService()
    try:
        file_info = await figma.get_file(request.file_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not access Figma file: {e}")
    finally:
        await figma.close()
    
    watched = detector.add_watched_file(request.file_key, request.name or file_info.name)
    
    return {
        "file_key": watched.file_key,
        "name": watched.name,
        "message": "File added to watch list",
    }


@router.delete("/figma/files/{file_key}")
async def remove_watched_file(file_key: str) -> dict[str, str]:
    """Remove a Figma file from watching."""
    detector = get_change_detector()
    
    if detector.remove_watched_file(file_key):
        return {"message": "File removed from watch list"}
    
    raise HTTPException(status_code=404, detail="File not found in watch list")


@router.get("/figma/files/{file_key}")
async def get_figma_file(file_key: str) -> dict[str, Any]:
    """Get Figma file information."""
    figma = FigmaService()
    try:
        file_info = await figma.get_file(file_key)
        design_info = figma.extract_design_info(file_info)
        return design_info
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch file: {e}")
    finally:
        await figma.close()


@router.post("/figma/files/{file_key}/check")
async def check_file_changes(file_key: str) -> dict[str, Any]:
    """Manually check a file for changes."""
    detector = get_change_detector()
    event = await detector.check_file(file_key)
    
    if event:
        return {
            "changed": True,
            "old_version": event.old_version,
            "new_version": event.new_version,
            "changed_at": event.changed_at.isoformat(),
        }
    
    return {"changed": False}


# --- Documentation ---

@router.get("/docs")
async def list_documentation() -> list[dict[str, Any]]:
    """List all generated documentation."""
    generator = get_doc_generator()
    return generator.list_documentation()


@router.post("/docs/generate")
async def generate_documentation(
    request: GenerateDocsRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Generate documentation for a Figma file."""
    generator = get_doc_generator()
    
    try:
        doc = await generator.generate_from_figma(
            request.file_key,
            request.doc_type,
            request.formats,
        )
        
        # Mark file as having docs generated
        detector = get_change_detector()
        for watched in detector.get_watched_files():
            if watched.file_key == request.file_key:
                watched.doc_generated = True
                break
        
        return {
            "id": doc.id,
            "title": doc.title,
            "figma_file_key": doc.figma_file_key,
            "doc_type": doc.doc_type.value,
            "created_at": doc.created_at.isoformat(),
            "sections_count": len(doc.sections),
        }
    except Exception as e:
        logger.error(f"Error generating documentation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/docs/{doc_id}")
async def get_documentation(doc_id: str) -> dict[str, Any]:
    """Get documentation by ID."""
    generator = get_doc_generator()
    doc = generator.get_documentation(doc_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Documentation not found")
    
    return doc


@router.get("/docs/file/{file_key}")
async def get_documentation_by_file(
    file_key: str,
    format: str = "markdown",
) -> dict[str, Any]:
    """Get documentation content by Figma file key."""
    generator = get_doc_generator()
    
    doc_format = DocFormat.MARKDOWN if format == "markdown" else DocFormat.HTML
    content = generator.get_documentation_content(file_key, doc_format)
    
    if not content:
        raise HTTPException(status_code=404, detail="Documentation not found for this file")
    
    return {
        "file_key": file_key,
        "format": format,
        "content": content,
    }


# --- Chat ---

@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat with the documentation assistant."""
    from app.services.docs.chatbot import get_chatbot
    
    chatbot = get_chatbot()
    
    try:
        response = await chatbot.chat(
            request.message,
            file_key=request.file_key,
            history=request.conversation_history,
        )
        return response
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Change Detection Control ---

@router.post("/detection/start")
async def start_change_detection() -> dict[str, str]:
    """Start the change detection polling."""
    detector = get_change_detector()
    
    if detector.is_running:
        return {"message": "Change detection is already running"}
    
    detector.start()
    return {"message": "Change detection started"}


@router.post("/detection/stop")
async def stop_change_detection() -> dict[str, str]:
    """Stop the change detection polling."""
    detector = get_change_detector()
    detector.stop()
    return {"message": "Change detection stopped"}


@router.post("/detection/check-all")
async def check_all_files() -> list[dict[str, Any]]:
    """Manually check all watched files for changes."""
    detector = get_change_detector()
    events = await detector.check_all_files()
    
    return [
        {
            "file_key": e.file_key,
            "file_name": e.file_name,
            "old_version": e.old_version,
            "new_version": e.new_version,
            "changed_at": e.changed_at.isoformat(),
        }
        for e in events
    ]


# --- Code Analysis ---

@router.post("/analyze/code")
async def analyze_code(request: CodeAnalysisRequest) -> dict[str, Any]:
    """Analyze code and generate documentation."""
    from app.services.agents import CodeAgent
    
    agent = CodeAgent()
    
    try:
        result = await agent.analyze_project(
            request.project_path,
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
        )
        return result
    except Exception as e:
        logger.error(f"Code analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- App Analysis ---

@router.post("/analyze/app")
async def analyze_app(request: dict[str, Any]) -> dict[str, Any]:
    """Analyze application UI and generate documentation."""
    from app.services.agents import AppAgent
    
    agent = AppAgent()
    
    try:
        result = await agent.analyze_app(
            request.get("app_url", ""),
            pages=request.get("pages_to_analyze", []),
            max_depth=request.get("max_depth", 3),
        )
        return result
    except Exception as e:
        logger.error(f"App analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Ollama Models ---

@router.get("/ollama/status")
async def get_ollama_status() -> dict[str, Any]:
    """Get Ollama server status and available models."""
    llm_service = get_llm_service()
    return await llm_service.get_ollama_status()


@router.get("/ollama/models")
async def list_ollama_models() -> dict[str, Any]:
    """List all models available on the Ollama server."""
    llm_service = get_llm_service()
    
    try:
        models = await llm_service.list_models()
        return {
            "models": models,
            "count": len(models),
        }
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PullModelRequest(BaseModel):
    model_name: str


@router.post("/ollama/models/pull")
async def pull_ollama_model(
    request: PullModelRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Pull (download) a model from Ollama registry."""
    llm_service = get_llm_service()
    
    try:
        # Check if model already exists
        exists = await llm_service.check_model_exists(request.model_name)
        if exists:
            return {
                "status": "already_available",
                "model": request.model_name,
                "message": f"Model {request.model_name} is already available",
            }
        
        # Pull model (this can take a while)
        logger.info(f"Starting model pull: {request.model_name}")
        result = await llm_service.pull_model(request.model_name)
        
        return {
            "status": "success",
            "model": request.model_name,
            "message": f"Successfully pulled {request.model_name}",
            "details": result,
        }
    except Exception as e:
        logger.error(f"Error pulling model {request.model_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ollama/models/ensure")
async def ensure_required_models() -> dict[str, Any]:
    """Ensure all required models are available, pulling if necessary."""
    llm_service = get_llm_service()
    
    try:
        result = await llm_service.ensure_models_available()
        return {
            "status": "complete",
            **result,
        }
    except Exception as e:
        logger.error(f"Error ensuring models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ollama/models/{model_name}/exists")
async def check_model_exists(model_name: str) -> dict[str, Any]:
    """Check if a specific model exists on the Ollama server."""
    llm_service = get_llm_service()
    
    try:
        exists = await llm_service.check_model_exists(model_name)
        return {
            "model": model_name,
            "exists": exists,
        }
    except Exception as e:
        logger.error(f"Error checking model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Configuration ---

@router.get("/config")
async def get_config() -> dict[str, Any]:
    """Get current configuration (safe values only)."""
    return {
        "llm": {
            "default_model": settings.llm.default_model,
            "models": {
                "documentation": settings.llm.models.documentation,
                "chatbot": settings.llm.models.chatbot,
                "code_analysis": settings.llm.models.code_analysis,
                "app_analysis": settings.llm.models.app_analysis,
            },
            "ollama_base_url": settings.llm.ollama_base_url,
        },
        "figma": {
            "polling_interval_minutes": settings.figma.polling_interval_minutes,
            "watched_files_count": len(settings.figma.watched_files),
        },
        "documentation": {
            "output_dir": settings.documentation.output_dir,
            "default_type": settings.documentation.default_type,
            "formats": settings.documentation.formats,
        },
    }

