"""Code analysis agent for generating documentation from source code."""

import fnmatch
import logging
import os
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.services.llm import LLMService, get_llm_service

logger = logging.getLogger(__name__)


class CodeAgent:
    """Agent for analyzing source code and generating documentation."""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Initialize the code agent.
        
        Args:
            llm_service: LLMService instance.
        """
        self.llm_service = llm_service or get_llm_service()
        self.config = settings.code_agent
    
    def _should_include_file(self, file_path: Path, base_path: Path) -> bool:
        """Check if a file should be included in analysis.
        
        Args:
            file_path: Path to the file.
            base_path: Base project path.
            
        Returns:
            True if file should be included.
        """
        relative_path = str(file_path.relative_to(base_path))
        
        # Check exclude patterns
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(relative_path, pattern):
                return False
            if fnmatch.fnmatch(str(file_path), pattern):
                return False
        
        # Check include patterns
        for pattern in self.config.include_patterns:
            if fnmatch.fnmatch(relative_path, pattern):
                return True
            if fnmatch.fnmatch(file_path.name, pattern.split("/")[-1]):
                return True
        
        return False
    
    def _get_file_type(self, file_path: Path) -> str:
        """Get the type/language of a file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            File type string.
        """
        suffix = file_path.suffix.lower()
        type_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript React",
            ".jsx": "JavaScript React",
            ".vue": "Vue",
            ".css": "CSS",
            ".scss": "SCSS",
            ".html": "HTML",
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
            ".md": "Markdown",
            ".sql": "SQL",
            ".sh": "Shell",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".kt": "Kotlin",
            ".swift": "Swift",
            ".rb": "Ruby",
            ".php": "PHP",
            ".c": "C",
            ".cpp": "C++",
            ".h": "C Header",
            ".hpp": "C++ Header",
        }
        return type_map.get(suffix, "Unknown")
    
    def _collect_files(self, project_path: Path) -> list[dict[str, Any]]:
        """Collect all relevant files from the project.
        
        Args:
            project_path: Path to the project directory.
            
        Returns:
            List of file info dictionaries.
        """
        files = []
        max_size = self.config.max_file_size_kb * 1024
        
        for root, dirs, filenames in os.walk(project_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            
            for filename in filenames:
                file_path = Path(root) / filename
                
                if not self._should_include_file(file_path, project_path):
                    continue
                
                # Check file size
                try:
                    size = file_path.stat().st_size
                    if size > max_size:
                        logger.debug(f"Skipping large file: {file_path}")
                        continue
                except OSError:
                    continue
                
                files.append({
                    "path": file_path,
                    "relative_path": str(file_path.relative_to(project_path)),
                    "type": self._get_file_type(file_path),
                    "size": size,
                })
        
        return files
    
    def _read_file_content(self, file_path: Path) -> Optional[str]:
        """Read file content safely.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            File content or None if error.
        """
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return None
    
    async def analyze_file(self, file_path: Path) -> dict[str, Any]:
        """Analyze a single file.
        
        Args:
            file_path: Path to the file.
            
        Returns:
            Analysis result dictionary.
        """
        content = self._read_file_content(file_path)
        if not content:
            return {"error": "Could not read file"}
        
        file_type = self._get_file_type(file_path)
        
        # Generate analysis using LLM
        analysis = await self.llm_service.analyze_code(content, str(file_path))
        
        return {
            "path": str(file_path),
            "type": file_type,
            "analysis": analysis,
        }
    
    async def analyze_project(
        self,
        project_path: str,
        include_patterns: list[str] = None,
        exclude_patterns: list[str] = None,
    ) -> dict[str, Any]:
        """Analyze an entire project.
        
        Args:
            project_path: Path to the project directory.
            include_patterns: Override include patterns.
            exclude_patterns: Override exclude patterns.
            
        Returns:
            Project analysis result.
        """
        path = Path(project_path)
        
        if not path.exists():
            return {"error": f"Project path does not exist: {project_path}"}
        
        if not path.is_dir():
            return {"error": f"Project path is not a directory: {project_path}"}
        
        # Override patterns if provided
        original_include = self.config.include_patterns
        original_exclude = self.config.exclude_patterns
        
        if include_patterns:
            self.config.include_patterns = include_patterns
        if exclude_patterns:
            self.config.exclude_patterns = exclude_patterns
        
        try:
            # Collect files
            files = self._collect_files(path)
            logger.info(f"Found {len(files)} files to analyze in {project_path}")
            
            if not files:
                return {
                    "project_path": project_path,
                    "error": "No files found matching the patterns",
                }
            
            # Group files by type
            files_by_type: dict[str, list[dict]] = {}
            for f in files:
                ftype = f["type"]
                if ftype not in files_by_type:
                    files_by_type[ftype] = []
                files_by_type[ftype].append(f)
            
            # Generate project overview
            overview = await self._generate_project_overview(path, files, files_by_type)
            
            # Analyze key files (limit to prevent token overflow)
            key_files = self._identify_key_files(files)
            file_analyses = []
            
            for file_info in key_files[:10]:  # Limit to 10 key files
                analysis = await self.analyze_file(file_info["path"])
                file_analyses.append(analysis)
            
            return {
                "project_path": project_path,
                "total_files": len(files),
                "files_by_type": {k: len(v) for k, v in files_by_type.items()},
                "overview": overview,
                "key_files": file_analyses,
            }
            
        finally:
            # Restore original patterns
            self.config.include_patterns = original_include
            self.config.exclude_patterns = original_exclude
    
    def _identify_key_files(self, files: list[dict]) -> list[dict]:
        """Identify key files for detailed analysis.
        
        Args:
            files: List of file info dictionaries.
            
        Returns:
            List of key files to analyze.
        """
        key_files = []
        
        # Priority patterns for key files
        priority_names = [
            "main.py", "app.py", "index.ts", "index.js", "main.ts", "main.js",
            "App.vue", "App.tsx", "App.jsx",
            "routes.py", "router.ts", "router.js",
            "models.py", "schema.py", "types.ts",
            "config.py", "settings.py", "config.ts",
            "README.md", "package.json", "pyproject.toml",
        ]
        
        for f in files:
            filename = Path(f["path"]).name
            if filename in priority_names:
                key_files.append(f)
        
        # Add remaining files sorted by size (smaller first, likely more focused)
        remaining = [f for f in files if f not in key_files]
        remaining.sort(key=lambda x: x["size"])
        
        key_files.extend(remaining)
        
        return key_files
    
    async def _generate_project_overview(
        self,
        project_path: Path,
        files: list[dict],
        files_by_type: dict[str, list[dict]],
    ) -> str:
        """Generate a high-level project overview.
        
        Args:
            project_path: Path to the project.
            files: List of all files.
            files_by_type: Files grouped by type.
            
        Returns:
            Project overview text.
        """
        # Build project structure summary
        structure_lines = []
        
        # Get unique directories
        dirs = set()
        for f in files:
            rel_path = Path(f["relative_path"])
            for parent in rel_path.parents:
                if str(parent) != ".":
                    dirs.add(str(parent))
        
        structure_lines.append(f"Project: {project_path.name}")
        structure_lines.append(f"Total files: {len(files)}")
        structure_lines.append(f"Directories: {len(dirs)}")
        structure_lines.append("")
        structure_lines.append("File types:")
        for ftype, flist in sorted(files_by_type.items(), key=lambda x: -len(x[1])):
            structure_lines.append(f"  - {ftype}: {len(flist)} files")
        
        structure_lines.append("")
        structure_lines.append("Key directories:")
        for d in sorted(dirs)[:10]:
            structure_lines.append(f"  - {d}/")
        
        structure_summary = "\n".join(structure_lines)
        
        # Generate overview using LLM
        template = """Based on the following project structure, provide a brief overview of what this project does and its architecture.

{structure}

Provide:
1. A one-paragraph summary of the project's purpose
2. The main technologies/frameworks used
3. The project architecture pattern (if identifiable)
4. Key components or modules

Be concise and factual."""

        overview = await self.llm_service.generate_with_template(
            template,
            {"structure": structure_summary},
            model=settings.get_model_for_task("code_analysis"),
        )
        
        return overview

