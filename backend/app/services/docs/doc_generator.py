"""Documentation generator service."""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.models.doc_models import DocFormat, DocSection, DocType, Documentation
from app.models.figma_models import FigmaFile
from app.services.figma import FigmaService
from app.services.llm import LLMService, get_llm_service

logger = logging.getLogger(__name__)


class DocGenerator:
    """Service for generating documentation from Figma designs."""
    
    def __init__(
        self,
        figma_service: Optional[FigmaService] = None,
        llm_service: Optional[LLMService] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize documentation generator.
        
        Args:
            figma_service: FigmaService instance.
            llm_service: LLMService instance.
            output_dir: Directory for generated documentation.
        """
        self.figma_service = figma_service or FigmaService()
        self.llm_service = llm_service or get_llm_service()
        self.output_dir = Path(output_dir or settings.documentation.output_dir)
        
        # Ensure output directories exist
        (self.output_dir / "markdown").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "html").mkdir(parents=True, exist_ok=True)
        
        # Initialize Jinja2 for HTML templates
        self._init_templates()
    
    def _init_templates(self) -> None:
        """Initialize Jinja2 template environment."""
        template_dir = Path(__file__).parent / "templates"
        template_dir.mkdir(exist_ok=True)
        
        # Create default HTML template if it doesn't exist
        default_template = template_dir / "doc_template.html"
        if not default_template.exists():
            self._create_default_template(default_template)
        
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
    
    def _create_default_template(self, path: Path) -> None:
        """Create the default HTML template."""
        template_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        :root {
            --bg-primary: #0f0f0f;
            --bg-secondary: #1a1a1a;
            --bg-tertiary: #252525;
            --text-primary: #e8e8e8;
            --text-secondary: #a0a0a0;
            --accent: #6366f1;
            --accent-hover: #818cf8;
            --border: #333;
            --code-bg: #1e1e1e;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.7;
            min-height: 100vh;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 3rem 2rem;
        }
        
        header {
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border);
        }
        
        h1 {
            font-size: 2.5rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, var(--text-primary), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .meta {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
        
        .content {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 2rem;
            border: 1px solid var(--border);
        }
        
        h2 {
            font-size: 1.5rem;
            font-weight: 600;
            margin: 2rem 0 1rem;
            color: var(--text-primary);
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--accent);
        }
        
        h3 {
            font-size: 1.2rem;
            font-weight: 500;
            margin: 1.5rem 0 0.75rem;
            color: var(--text-primary);
        }
        
        h4 {
            font-size: 1rem;
            font-weight: 500;
            margin: 1rem 0 0.5rem;
            color: var(--text-secondary);
        }
        
        p {
            margin-bottom: 1rem;
            color: var(--text-secondary);
        }
        
        ul, ol {
            margin: 1rem 0;
            padding-left: 1.5rem;
        }
        
        li {
            margin-bottom: 0.5rem;
            color: var(--text-secondary);
        }
        
        code {
            background: var(--code-bg);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 0.9em;
        }
        
        pre {
            background: var(--code-bg);
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
            margin: 1rem 0;
            border: 1px solid var(--border);
        }
        
        pre code {
            padding: 0;
            background: none;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }
        
        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        
        th {
            background: var(--bg-tertiary);
            font-weight: 500;
        }
        
        a {
            color: var(--accent);
            text-decoration: none;
        }
        
        a:hover {
            color: var(--accent-hover);
            text-decoration: underline;
        }
        
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            background: var(--accent);
            color: white;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        
        footer {
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{{ title }}</h1>
            <p class="meta">
                Generated: {{ generated_at }} | 
                Version: {{ version }} |
                <span class="badge">{{ doc_type }}</span>
            </p>
        </header>
        
        <main class="content">
            {{ content | safe }}
        </main>
        
        <footer>
            <p>Generated by Figma Documentation Generator</p>
        </footer>
    </div>
</body>
</html>
'''
        path.write_text(template_content)
    
    async def generate_from_figma(
        self,
        file_key: str,
        doc_type: DocType = DocType.BOTH,
        formats: list[DocFormat] = None,
    ) -> Documentation:
        """Generate documentation from a Figma file.
        
        Args:
            file_key: Figma file key.
            doc_type: Type of documentation to generate.
            formats: Output formats (markdown, html).
            
        Returns:
            Generated Documentation object.
        """
        formats = formats or [DocFormat.MARKDOWN, DocFormat.HTML]
        
        logger.info(f"Generating {doc_type.value} documentation for file {file_key}")
        
        # Fetch Figma file
        figma_file = await self.figma_service.get_file(file_key)
        
        # Extract design information
        design_info = self.figma_service.extract_design_info(figma_file)
        
        # Generate documentation using LLM
        markdown_content = await self.llm_service.generate_documentation(
            design_info, doc_type.value
        )
        
        # Create documentation object
        doc = Documentation(
            id=str(uuid.uuid4()),
            figma_file_key=file_key,
            figma_file_name=figma_file.name,
            title=f"{figma_file.name} Documentation",
            description=f"Auto-generated {doc_type.value} documentation",
            doc_type=doc_type,
            figma_version=figma_file.version,
        )
        
        # Parse markdown into sections
        doc.sections = self._parse_markdown_sections(markdown_content)
        
        # Save documentation
        await self._save_documentation(doc, markdown_content, formats)
        
        logger.info(f"Documentation generated successfully: {doc.id}")
        
        return doc
    
    def _parse_markdown_sections(self, markdown_content: str) -> list[DocSection]:
        """Parse markdown content into sections.
        
        Args:
            markdown_content: Raw markdown content.
            
        Returns:
            List of DocSection objects.
        """
        sections = []
        current_section = None
        current_content = []
        section_order = 0
        
        for line in markdown_content.split("\n"):
            # Check for headers
            if line.startswith("## "):
                # Save previous section
                if current_section:
                    current_section.content = "\n".join(current_content).strip()
                    sections.append(current_section)
                
                # Start new section
                title = line[3:].strip()
                current_section = DocSection(
                    id=str(uuid.uuid4()),
                    title=title,
                    content="",
                    order=section_order,
                )
                current_content = []
                section_order += 1
            elif current_section:
                current_content.append(line)
        
        # Save last section
        if current_section:
            current_section.content = "\n".join(current_content).strip()
            sections.append(current_section)
        
        return sections
    
    async def _save_documentation(
        self,
        doc: Documentation,
        markdown_content: str,
        formats: list[DocFormat],
    ) -> None:
        """Save documentation to files.
        
        Args:
            doc: Documentation object.
            markdown_content: Raw markdown content.
            formats: Formats to save.
        """
        # Create safe filename
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in doc.figma_file_name)
        safe_name = safe_name.replace(" ", "_").lower()
        
        # Save markdown
        if DocFormat.MARKDOWN in formats:
            md_path = self.output_dir / "markdown" / f"{safe_name}.md"
            md_path.write_text(markdown_content)
            logger.info(f"Saved markdown: {md_path}")
        
        # Save HTML
        if DocFormat.HTML in formats:
            html_content = self._convert_to_html(doc, markdown_content)
            html_path = self.output_dir / "html" / f"{safe_name}.html"
            html_path.write_text(html_content)
            logger.info(f"Saved HTML: {html_path}")
        
        # Save metadata JSON
        meta_path = self.output_dir / "markdown" / f"{safe_name}_meta.json"
        meta_data = {
            "id": doc.id,
            "figma_file_key": doc.figma_file_key,
            "figma_file_name": doc.figma_file_name,
            "title": doc.title,
            "doc_type": doc.doc_type.value,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
            "version": doc.version,
            "figma_version": doc.figma_version,
            "sections": [
                {"id": s.id, "title": s.title, "order": s.order}
                for s in doc.sections
            ],
        }
        meta_path.write_text(json.dumps(meta_data, indent=2))
    
    def _convert_to_html(self, doc: Documentation, markdown_content: str) -> str:
        """Convert markdown to HTML using template.
        
        Args:
            doc: Documentation object.
            markdown_content: Raw markdown content.
            
        Returns:
            HTML string.
        """
        # Convert markdown to HTML
        md = markdown.Markdown(
            extensions=["fenced_code", "tables", "toc", "codehilite"],
            extension_configs={
                "codehilite": {"css_class": "highlight"},
            },
        )
        html_content = md.convert(markdown_content)
        
        # Render with template
        template = self.jinja_env.get_template("doc_template.html")
        return template.render(
            title=doc.title,
            content=html_content,
            generated_at=doc.created_at.strftime("%Y-%m-%d %H:%M"),
            version=doc.version,
            doc_type=doc.doc_type.value.upper(),
        )
    
    async def update_documentation(
        self,
        file_key: str,
        doc_type: DocType = DocType.BOTH,
    ) -> Documentation:
        """Update existing documentation after Figma changes.
        
        Args:
            file_key: Figma file key.
            doc_type: Type of documentation.
            
        Returns:
            Updated Documentation object.
        """
        # For now, regenerate completely
        # Future: implement diff-based updates
        return await self.generate_from_figma(file_key, doc_type)
    
    def list_documentation(self) -> list[dict[str, Any]]:
        """List all generated documentation.
        
        Returns:
            List of documentation metadata.
        """
        docs = []
        meta_dir = self.output_dir / "markdown"
        
        for meta_file in meta_dir.glob("*_meta.json"):
            try:
                with open(meta_file) as f:
                    docs.append(json.load(f))
            except Exception as e:
                logger.error(f"Error reading {meta_file}: {e}")
        
        return sorted(docs, key=lambda d: d.get("created_at", ""), reverse=True)
    
    def get_documentation(self, doc_id: str) -> Optional[dict[str, Any]]:
        """Get documentation by ID.
        
        Args:
            doc_id: Documentation ID.
            
        Returns:
            Documentation data or None.
        """
        for doc in self.list_documentation():
            if doc.get("id") == doc_id:
                # Load full content
                safe_name = "".join(
                    c if c.isalnum() or c in "._- " else "_"
                    for c in doc.get("figma_file_name", "")
                )
                safe_name = safe_name.replace(" ", "_").lower()
                
                md_path = self.output_dir / "markdown" / f"{safe_name}.md"
                if md_path.exists():
                    doc["content"] = md_path.read_text()
                
                return doc
        
        return None
    
    def get_documentation_content(
        self,
        file_key: str,
        format: DocFormat = DocFormat.MARKDOWN,
    ) -> Optional[str]:
        """Get documentation content by Figma file key.
        
        Args:
            file_key: Figma file key.
            format: Desired format.
            
        Returns:
            Documentation content or None.
        """
        for doc in self.list_documentation():
            if doc.get("figma_file_key") == file_key:
                safe_name = "".join(
                    c if c.isalnum() or c in "._- " else "_"
                    for c in doc.get("figma_file_name", "")
                )
                safe_name = safe_name.replace(" ", "_").lower()
                
                if format == DocFormat.MARKDOWN:
                    path = self.output_dir / "markdown" / f"{safe_name}.md"
                else:
                    path = self.output_dir / "html" / f"{safe_name}.html"
                
                if path.exists():
                    return path.read_text()
        
        return None


# Global doc generator instance
_doc_generator: Optional[DocGenerator] = None


def get_doc_generator() -> DocGenerator:
    """Get or create the global doc generator instance."""
    global _doc_generator
    if _doc_generator is None:
        _doc_generator = DocGenerator()
    return _doc_generator

