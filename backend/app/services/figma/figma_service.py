"""Figma API service for interacting with Figma files."""

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.models.figma_models import (
    FigmaComponent,
    FigmaFile,
    FigmaNode,
    FigmaUser,
    FigmaVersion,
)

logger = logging.getLogger(__name__)


class FigmaService:
    """Service for interacting with Figma REST API."""
    
    def __init__(self, api_token: Optional[str] = None):
        """Initialize Figma service.
        
        Args:
            api_token: Figma API token. If not provided, uses config.
        """
        self.api_token = api_token or settings.figma.api_token
        self.base_url = settings.figma.api_base_url
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "X-Figma-Token": self.api_token,
            "Content-Type": "application/json",
        }
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=30.0,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def get_me(self) -> dict[str, Any]:
        """Get current user info to verify API token.
        
        Returns:
            User info dictionary with id, email, handle.
        """
        client = await self._get_client()
        
        response = await client.get("/v1/me")
        response.raise_for_status()
        
        return response.json()
    
    async def get_team_projects(self, team_id: str) -> list[dict[str, Any]]:
        """Get all projects in a team.
        
        Args:
            team_id: The team ID.
            
        Returns:
            List of project dictionaries with id and name.
        """
        client = await self._get_client()
        
        response = await client.get(f"/v1/teams/{team_id}/projects")
        response.raise_for_status()
        
        data = response.json()
        projects = []
        
        for project in data.get("projects", []):
            projects.append({
                "id": project.get("id"),
                "name": project.get("name", "Unnamed Project"),
            })
        
        return projects
    
    async def get_project_files(self, project_id: str) -> list[dict[str, Any]]:
        """Get all files in a project.
        
        Args:
            project_id: The project ID.
            
        Returns:
            List of file dictionaries with key, name, thumbnail_url, last_modified.
        """
        client = await self._get_client()
        
        response = await client.get(f"/v1/projects/{project_id}/files")
        response.raise_for_status()
        
        data = response.json()
        files = []
        
        for file_data in data.get("files", []):
            file_type = file_data.get("file_type", "design")  # 'design' or 'jam'
            files.append({
                "key": file_data.get("key"),
                "name": file_data.get("name", "Unnamed File"),
                "thumbnail_url": file_data.get("thumbnail_url"),
                "last_modified": file_data.get("last_modified"),
                "file_type": file_type,  # Add file type for filtering
            })
        
        return files
    
    async def get_file(self, file_key: str, version: Optional[str] = None) -> FigmaFile:
        """Get a Figma file by key.
        
        Args:
            file_key: The unique key of the Figma file.
            version: Optional specific version to retrieve.
            
        Returns:
            FigmaFile object with file data.
            
        Raises:
            httpx.HTTPStatusError: If the API request fails.
            ValueError: If file_key is invalid.
        """
        # Validate file key
        if not file_key or not isinstance(file_key, str):
            raise ValueError("File key must be a non-empty string")
        
        file_key = file_key.strip()
        if not file_key:
            raise ValueError("File key cannot be empty")
        
        # Check API token
        if not self.api_token:
            raise ValueError("Figma API token is not set. Set FIGMA_API_TOKEN environment variable.")
        
        client = await self._get_client()
        
        params = {}
        if version:
            params["version"] = version
        
        logger.info(f"Fetching Figma file: {file_key} (version: {version or 'latest'})")
        
        try:
            response = await client.get(f"/v1/files/{file_key}", params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Log detailed error information
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                error_detail = error_data.get("err", error_data.get("message", str(e.response.text)))
            except:
                error_detail = e.response.text[:500] if e.response.text else str(e)
            
            logger.error(
                f"Figma API error for file {file_key}: {e.response.status_code} - {error_detail}"
            )
            
            # Provide more helpful error messages
            if e.response.status_code == 400:
                # Check if it's a file type issue (e.g., FigJam)
                if "file type not supported" in error_detail.lower() or "not supported by this endpoint" in error_detail.lower():
                    raise httpx.HTTPStatusError(
                        f"File type not supported: The file '{file_key}' appears to be a FigJam file or another unsupported file type. "
                        f"This tool only supports Figma Design files. Please use a Figma Design file (.fig) instead of a FigJam file.",
                        request=e.request,
                        response=e.response,
                    ) from e
                else:
                    raise httpx.HTTPStatusError(
                        f"Could not access Figma file '{file_key}': {error_detail}. "
                        f"Check that the file key is correct and your API token has access to this file.",
                        request=e.request,
                        response=e.response,
                    ) from e
            elif e.response.status_code == 403:
                raise httpx.HTTPStatusError(
                    f"Access denied to Figma file '{file_key}': {error_detail}. "
                    f"Your API token may not have permission to access this file.",
                    request=e.request,
                    response=e.response,
                ) from e
            elif e.response.status_code == 404:
                raise httpx.HTTPStatusError(
                    f"Figma file '{file_key}' not found: {error_detail}. "
                    f"Check that the file key is correct.",
                    request=e.request,
                    response=e.response,
                ) from e
            else:
                raise
        
        data = response.json()
        
        # Parse document tree
        document = self._parse_node(data.get("document", {}))
        
        # Parse components
        components = {}
        for comp_id, comp_data in data.get("components", {}).items():
            components[comp_id] = FigmaComponent(
                key=comp_data.get("key", comp_id),
                name=comp_data.get("name", ""),
                description=comp_data.get("description"),
                node_id=comp_id,
                containing_frame=comp_data.get("containingFrame"),
            )
        
        return FigmaFile(
            key=file_key,
            name=data.get("name", ""),
            last_modified=datetime.fromisoformat(data["lastModified"].replace("Z", "+00:00")),
            version=data.get("version", ""),
            thumbnail_url=data.get("thumbnailUrl"),
            document=document,
            components=components,
            styles=data.get("styles", {}),
        )
    
    def _parse_node(self, node_data: dict[str, Any]) -> FigmaNode:
        """Recursively parse a Figma node.
        
        Args:
            node_data: Raw node data from API.
            
        Returns:
            Parsed FigmaNode object.
        """
        children = []
        for child_data in node_data.get("children", []):
            children.append(self._parse_node(child_data))
        
        return FigmaNode(
            id=node_data.get("id", ""),
            name=node_data.get("name", ""),
            type=node_data.get("type", ""),
            children=children,
            visible=node_data.get("visible", True),
            background_color=node_data.get("backgroundColor"),
            fills=node_data.get("fills", []),
            strokes=node_data.get("strokes", []),
            effects=node_data.get("effects", []),
            absolute_bounding_box=node_data.get("absoluteBoundingBox"),
            constraints=node_data.get("constraints"),
            layout_mode=node_data.get("layoutMode"),
            characters=node_data.get("characters"),
            style=node_data.get("style"),
            component_id=node_data.get("componentId"),
        )
    
    async def get_file_versions(
        self,
        file_key: str,
        limit: int = 30,
    ) -> list[FigmaVersion]:
        """Get version history of a Figma file.
        
        Args:
            file_key: The unique key of the Figma file.
            limit: Maximum number of versions to retrieve.
            
        Returns:
            List of FigmaVersion objects.
        """
        client = await self._get_client()
        
        response = await client.get(f"/v1/files/{file_key}/versions")
        response.raise_for_status()
        
        data = response.json()
        versions = []
        
        for version_data in data.get("versions", [])[:limit]:
            user = None
            if version_data.get("user"):
                user = FigmaUser(
                    id=version_data["user"].get("id", ""),
                    handle=version_data["user"].get("handle", ""),
                    img_url=version_data["user"].get("img_url"),
                )
            
            versions.append(FigmaVersion(
                id=version_data.get("id", ""),
                created_at=datetime.fromisoformat(
                    version_data["created_at"].replace("Z", "+00:00")
                ),
                label=version_data.get("label"),
                description=version_data.get("description"),
                user=user,
            ))
        
        return versions
    
    async def get_file_components(self, file_key: str) -> dict[str, FigmaComponent]:
        """Get all components in a Figma file.
        
        Args:
            file_key: The unique key of the Figma file.
            
        Returns:
            Dictionary of component ID to FigmaComponent.
        """
        client = await self._get_client()
        
        response = await client.get(f"/v1/files/{file_key}/components")
        response.raise_for_status()
        
        data = response.json()
        components = {}
        
        for comp_data in data.get("meta", {}).get("components", []):
            comp_id = comp_data.get("node_id", "")
            components[comp_id] = FigmaComponent(
                key=comp_data.get("key", ""),
                name=comp_data.get("name", ""),
                description=comp_data.get("description"),
                node_id=comp_id,
                containing_frame=comp_data.get("containing_frame"),
            )
        
        return components
    
    async def get_file_styles(self, file_key: str) -> dict[str, Any]:
        """Get all styles in a Figma file.
        
        Args:
            file_key: The unique key of the Figma file.
            
        Returns:
            Dictionary of style ID to style data.
        """
        client = await self._get_client()
        
        response = await client.get(f"/v1/files/{file_key}/styles")
        response.raise_for_status()
        
        data = response.json()
        return data.get("meta", {}).get("styles", {})
    
    async def get_images(
        self,
        file_key: str,
        node_ids: list[str],
        format: str = "png",
        scale: float = 1.0,
    ) -> dict[str, str]:
        """Get rendered images for specific nodes.
        
        Args:
            file_key: The unique key of the Figma file.
            node_ids: List of node IDs to render.
            format: Image format (png, jpg, svg, pdf).
            scale: Scale factor for the image.
            
        Returns:
            Dictionary of node ID to image URL.
        """
        client = await self._get_client()
        
        params = {
            "ids": ",".join(node_ids),
            "format": format,
            "scale": scale,
        }
        
        response = await client.get(f"/v1/images/{file_key}", params=params)
        response.raise_for_status()
        
        data = response.json()
        return data.get("images", {})
    
    async def download_images(
        self,
        file_key: str,
        node_ids: list[str],
        format: str = "png",
        scale: float = 2.0,
    ) -> dict[str, bytes]:
        """Download rendered images as bytes for specific nodes.
        
        Args:
            file_key: The unique key of the Figma file.
            node_ids: List of node IDs to render.
            format: Image format (png, jpg, svg, pdf).
            scale: Scale factor for the image (higher for better quality).
            
        Returns:
            Dictionary of node ID to image bytes.
        """
        # Get image URLs from Figma API
        image_urls = await self.get_images(file_key, node_ids, format, scale)
        
        # Download each image
        downloaded_images: dict[str, bytes] = {}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for node_id, image_url in image_urls.items():
                if not image_url:
                    logger.warning(f"No image URL returned for node {node_id}")
                    continue
                
                try:
                    # Download image from CDN (no auth needed for Figma CDN)
                    response = await client.get(image_url)
                    response.raise_for_status()
                    downloaded_images[node_id] = response.content
                    logger.debug(f"Downloaded image for node {node_id} ({len(response.content)} bytes)")
                except Exception as e:
                    logger.error(f"Error downloading image for node {node_id}: {e}")
                    # Continue with other images even if one fails
        
        return downloaded_images
    
    async def get_latest_version(self, file_key: str) -> Optional[FigmaVersion]:
        """Get the latest version of a Figma file.
        
        Args:
            file_key: The unique key of the Figma file.
            
        Returns:
            Latest FigmaVersion or None if no versions.
        """
        versions = await self.get_file_versions(file_key, limit=1)
        return versions[0] if versions else None
    
    async def check_file_changed(
        self,
        file_key: str,
        last_known_version: Optional[str] = None,
        last_known_modified: Optional[datetime] = None,
    ) -> tuple[bool, Optional[str], Optional[datetime]]:
        """Check if a Figma file has changed since last check.
        
        Args:
            file_key: The unique key of the Figma file.
            last_known_version: Last known version ID.
            last_known_modified: Last known modification timestamp.
            
        Returns:
            Tuple of (has_changed, new_version, new_modified_time).
        """
        try:
            # Get file metadata (lighter than full file)
            client = await self._get_client()
            response = await client.get(f"/v1/files/{file_key}", params={"depth": 1})
            response.raise_for_status()
            
            data = response.json()
            current_version = data.get("version", "")
            current_modified = datetime.fromisoformat(
                data["lastModified"].replace("Z", "+00:00")
            )
            
            has_changed = False
            
            if last_known_version and current_version != last_known_version:
                has_changed = True
            elif last_known_modified and current_modified > last_known_modified:
                has_changed = True
            elif not last_known_version and not last_known_modified:
                # First check, consider it changed
                has_changed = True
            
            return has_changed, current_version, current_modified
            
        except Exception as e:
            logger.error(f"Error checking file changes for {file_key}: {e}")
            return False, None, None
    
    def extract_design_info(self, file: FigmaFile) -> dict[str, Any]:
        """Extract structured design information from a Figma file.
        
        Args:
            file: FigmaFile object.
            
        Returns:
            Dictionary with extracted design information.
        """
        info = {
            "file_name": file.name,
            "file_key": file.key,
            "last_modified": file.last_modified.isoformat(),
            "version": file.version,
            "pages": [],
            "components": [],
            "styles": [],
            "colors": [],
            "typography": [],
        }
        
        if file.document:
            # Extract pages (top-level children of document)
            for page in file.document.children:
                page_info = self._extract_page_info(page)
                info["pages"].append(page_info)
        
        # Extract components
        for comp_id, comp in file.components.items():
            info["components"].append({
                "id": comp_id,
                "key": comp.key,
                "name": comp.name,
                "description": comp.description,
            })
        
        # Extract styles
        for style_id, style in file.styles.items():
            style_info = {
                "id": style_id,
                "name": style.get("name", ""),
                "type": style.get("styleType", ""),
                "description": style.get("description", ""),
            }
            info["styles"].append(style_info)
            
            # Categorize styles
            if style.get("styleType") == "FILL":
                info["colors"].append(style_info)
            elif style.get("styleType") == "TEXT":
                info["typography"].append(style_info)
        
        return info
    
    def _extract_page_info(self, page: FigmaNode) -> dict[str, Any]:
        """Extract information from a page node.
        
        Args:
            page: FigmaNode representing a page.
            
        Returns:
            Dictionary with page information.
        """
        page_info = {
            "id": page.id,
            "name": page.name,
            "type": page.type,
            "frames": [],
            "elements": [],
        }
        
        for child in page.children:
            if child.type == "FRAME":
                frame_info = self._extract_frame_info(child)
                page_info["frames"].append(frame_info)
            else:
                element_info = self._extract_element_info(child)
                page_info["elements"].append(element_info)
        
        return page_info
    
    def _extract_frame_info(self, frame: FigmaNode, depth: int = 0) -> dict[str, Any]:
        """Extract information from a frame node.
        
        Args:
            frame: FigmaNode representing a frame.
            depth: Current recursion depth.
            
        Returns:
            Dictionary with frame information.
        """
        frame_info = {
            "id": frame.id,
            "name": frame.name,
            "type": frame.type,
            "layout_mode": frame.layout_mode,
            "children": [],
        }
        
        if frame.absolute_bounding_box:
            frame_info["dimensions"] = {
                "width": frame.absolute_bounding_box.get("width"),
                "height": frame.absolute_bounding_box.get("height"),
            }
        
        # Limit recursion depth
        if depth < 5:
            for child in frame.children:
                if child.type == "FRAME" or child.type == "GROUP":
                    child_info = self._extract_frame_info(child, depth + 1)
                else:
                    child_info = self._extract_element_info(child)
                frame_info["children"].append(child_info)
        
        return frame_info
    
    def _extract_element_info(self, element: FigmaNode) -> dict[str, Any]:
        """Extract information from an element node.
        
        Args:
            element: FigmaNode representing an element.
            
        Returns:
            Dictionary with element information.
        """
        element_info = {
            "id": element.id,
            "name": element.name,
            "type": element.type,
            "visible": element.visible,
        }
        
        # Add text content if present
        if element.characters:
            element_info["text"] = element.characters
        
        # Add component reference if present
        if element.component_id:
            element_info["component_id"] = element.component_id
        
        # Add dimensions if present
        if element.absolute_bounding_box:
            element_info["dimensions"] = {
                "width": element.absolute_bounding_box.get("width"),
                "height": element.absolute_bounding_box.get("height"),
            }
        
        return element_info

