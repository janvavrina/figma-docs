"""Pydantic models for Figma data structures."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class FigmaUser(BaseModel):
    """Figma user information."""
    id: str
    handle: str
    img_url: Optional[str] = None


class FigmaVersion(BaseModel):
    """Figma file version."""
    id: str
    created_at: datetime
    label: Optional[str] = None
    description: Optional[str] = None
    user: Optional[FigmaUser] = None


class FigmaNode(BaseModel):
    """Figma node (element) in the design tree."""
    id: str
    name: str
    type: str
    children: list["FigmaNode"] = Field(default_factory=list)
    visible: bool = True
    
    # Style properties (optional)
    background_color: Optional[dict[str, float]] = None
    fills: list[dict[str, Any]] = Field(default_factory=list)
    strokes: list[dict[str, Any]] = Field(default_factory=list)
    effects: list[dict[str, Any]] = Field(default_factory=list)
    
    # Layout properties (optional)
    absolute_bounding_box: Optional[dict[str, float]] = None
    constraints: Optional[dict[str, str]] = None
    layout_mode: Optional[str] = None
    
    # Text properties (optional)
    characters: Optional[str] = None
    style: Optional[dict[str, Any]] = None
    
    # Component properties (optional)
    component_id: Optional[str] = None


class FigmaComponent(BaseModel):
    """Figma component definition."""
    key: str
    name: str
    description: Optional[str] = None
    node_id: str
    containing_frame: Optional[dict[str, str]] = None


class FigmaFile(BaseModel):
    """Complete Figma file information."""
    key: str
    name: str
    last_modified: datetime
    version: str
    thumbnail_url: Optional[str] = None
    document: Optional[FigmaNode] = None
    components: dict[str, FigmaComponent] = Field(default_factory=dict)
    styles: dict[str, Any] = Field(default_factory=dict)


class WatchedFile(BaseModel):
    """Configuration for a watched Figma file."""
    file_key: str
    name: str
    last_version: Optional[str] = None
    last_modified: Optional[datetime] = None
    last_checked: Optional[datetime] = None
    doc_generated: bool = False


class FileChangeEvent(BaseModel):
    """Event triggered when a Figma file changes."""
    file_key: str
    file_name: str
    old_version: Optional[str] = None
    new_version: str
    changed_at: datetime
    changes_detected: list[str] = Field(default_factory=list)

