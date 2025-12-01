"""Pydantic models for documentation structures."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DocType(str, Enum):
    """Type of documentation."""
    USER = "user"
    DEVELOPER = "dev"
    BOTH = "both"


class DocFormat(str, Enum):
    """Output format for documentation."""
    MARKDOWN = "markdown"
    HTML = "html"


class DocSection(BaseModel):
    """A section within documentation."""
    id: str
    title: str
    content: str
    order: int = 0
    parent_id: Optional[str] = None
    figma_node_id: Optional[str] = None
    doc_type: DocType = DocType.BOTH


class Documentation(BaseModel):
    """Complete documentation for a Figma file."""
    id: str
    figma_file_key: str
    figma_file_name: str
    title: str
    description: Optional[str] = None
    sections: list[DocSection] = Field(default_factory=list)
    doc_type: DocType = DocType.BOTH
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"
    figma_version: Optional[str] = None


class ChatMessage(BaseModel):
    """Chat message for the documentation chatbot."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatResponse(BaseModel):
    """Response from the chatbot."""
    message: str
    sources: list[str] = Field(default_factory=list)
    figma_references: list[str] = Field(default_factory=list)


class GenerateDocsRequest(BaseModel):
    """Request to generate documentation."""
    file_key: str
    doc_type: DocType = DocType.BOTH
    formats: list[DocFormat] = Field(default_factory=lambda: [DocFormat.MARKDOWN, DocFormat.HTML])
    include_components: bool = True
    include_styles: bool = True
    include_interactions: bool = True


class ChatRequest(BaseModel):
    """Request for chatbot interaction."""
    message: str
    file_key: Optional[str] = None
    conversation_history: list[ChatMessage] = Field(default_factory=list)


class CodeAnalysisRequest(BaseModel):
    """Request for code analysis."""
    project_path: str
    include_patterns: list[str] = Field(default_factory=lambda: ["**/*.py", "**/*.js", "**/*.ts", "**/*.vue"])
    exclude_patterns: list[str] = Field(default_factory=lambda: ["**/node_modules/**", "**/__pycache__/**", "**/.git/**"])


class AppAnalysisRequest(BaseModel):
    """Request for application analysis."""
    app_url: str
    pages_to_analyze: list[str] = Field(default_factory=list)
    max_depth: int = 3
    take_screenshots: bool = True

