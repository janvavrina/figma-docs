"""App analysis agent for generating documentation from running applications."""

import asyncio
import base64
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import markdown as md_lib

from app.core.config import settings
from app.models.doc_models import DocFormat, DocSection, DocType, Documentation
from app.services.llm import LLMService, get_llm_service

logger = logging.getLogger(__name__)


class AppAgent:
    """Agent for analyzing running applications and generating user documentation.
    
    This agent can navigate through a web application, take screenshots,
    and generate documentation describing the UI and user flows.
    
    Note: For full computer use functionality, this would integrate with
    tools like Playwright, Selenium, or specialized computer use APIs.
    This implementation provides the framework and basic HTTP-based analysis.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Initialize the app agent.

        Args:
            llm_service: LLMService instance.
        """
        self.llm_service = llm_service or get_llm_service()
        self.config = settings.app_agent
        self._visited_urls: set[str] = set()
        self._screenshots_dir = Path(self.config.screenshot_dir)
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = Path(settings.documentation.output_dir)
        (self.output_dir / "markdown").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "html").mkdir(parents=True, exist_ok=True)
    
    async def analyze_app(
        self,
        app_url: str,
        pages: list[str] = None,
        max_depth: int = None,
    ) -> dict[str, Any]:
        """Analyze a web application.
        
        Args:
            app_url: Base URL of the application.
            pages: Optional list of specific pages to analyze.
            max_depth: Maximum crawl depth.
            
        Returns:
            Analysis result dictionary.
        """
        if not app_url:
            return {"error": "No URL provided"}
        
        # Validate URL
        parsed = urlparse(app_url)
        if not parsed.scheme or not parsed.netloc:
            return {"error": f"Invalid URL: {app_url}"}
        
        max_depth = max_depth or self.config.max_depth
        self._visited_urls.clear()
        
        logger.info(f"Starting app analysis for {app_url}")
        
        # Analyze pages
        if pages:
            # Analyze specific pages
            page_analyses = []
            for page in pages[:self.config.max_pages]:
                full_url = urljoin(app_url, page)
                analysis = await self._analyze_page(full_url)
                page_analyses.append(analysis)
        else:
            # Start from base URL and discover pages
            page_analyses = await self._crawl_and_analyze(app_url, max_depth)
        
        # Generate overall documentation
        markdown_content = await self._generate_app_documentation(
            app_url, page_analyses
        )

        # Extract app name from URL
        app_name = parsed.netloc.replace("www.", "").split(".")[0].title()

        # Create and save documentation object (same as Figma docs)
        doc = Documentation(
            id=str(uuid.uuid4()),
            figma_file_key=f"app:{parsed.netloc}",  # Use app: prefix for app analysis
            figma_file_name=app_name,
            title=f"{app_name} Documentation",
            description=f"Auto-generated documentation from app analysis",
            doc_type=DocType.USER,
            figma_version=datetime.now().strftime("%Y%m%d%H%M%S"),
        )

        # Parse markdown into sections
        doc.sections = self._parse_markdown_sections(markdown_content)

        # Collect screenshots from page analyses
        screenshots = []
        for page in page_analyses:
            if page.get("screenshot"):
                screenshot_path = Path(page["screenshot"])
                if screenshot_path.exists():
                    screenshots.append({
                        "filename": screenshot_path.name,
                        "url": page.get("url", ""),
                        "title": page.get("title", ""),
                    })

        # Attach screenshots to doc for saving
        doc._screenshots = screenshots

        # Save documentation to files
        await self._save_documentation(doc, markdown_content)

        logger.info(f"App documentation saved: {doc.id}")

        return {
            "id": doc.id,
            "app_url": app_url,
            "title": doc.title,
            "figma_file_key": doc.figma_file_key,
            "figma_file_name": doc.figma_file_name,
            "doc_type": doc.doc_type.value,
            "pages_analyzed": len(page_analyses),
            "created_at": doc.created_at.isoformat(),
        }
    
    async def _analyze_page(self, url: str) -> dict[str, Any]:
        """Analyze a single page using screenshot + VLM.

        Args:
            url: URL of the page.

        Returns:
            Page analysis dictionary.
        """
        logger.info(f"Analyzing page: {url}")

        page_info = {"title": "", "elements": {}, "links": [], "forms": []}
        screenshot_path = None
        description = ""
        http_success = False

        # Try to fetch page content for HTML parsing
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                html_content = response.text

            # Extract page info from HTML
            page_info = self._extract_page_info(html_content, url)
            http_success = True
        except Exception as e:
            logger.warning(f"HTTP fetch failed for {url}: {e}, will try screenshot")

        # Take screenshot if enabled (even if HTTP failed)
        if self.config.take_screenshots:
            screenshot_path = await self.take_screenshot(url)

            if screenshot_path:
                # Use VLM to analyze screenshot
                try:
                    with open(screenshot_path, "rb") as f:
                        screenshot_bytes = f.read()

                    vlm_prompt = f"""Analyze this screenshot of a web page.

Page Title: {page_info.get('title', 'Unknown')}
URL: {url}

Describe in detail:
1. What is the main purpose of this page?
2. What are the key UI elements visible (buttons, forms, navigation, content areas)?
3. What actions can a user take on this page?
4. What is the overall design style and layout?

Be concise but thorough. Focus on user-relevant information."""

                    description = await self.llm_service.generate_with_image(
                        prompt=vlm_prompt,
                        images=[screenshot_bytes],
                        model=settings.get_model_for_task("app_analysis"),
                    )
                    logger.info(f"VLM analysis complete for {url}")
                except Exception as e:
                    logger.warning(f"VLM analysis failed, falling back to text: {e}")
                    if http_success:
                        description = await self._describe_page(page_info)
                    else:
                        description = f"Page at {url} - screenshot captured but analysis failed."
            elif http_success:
                description = await self._describe_page(page_info)
            else:
                description = f"Could not analyze page at {url}"
        elif http_success:
            description = await self._describe_page(page_info)
        else:
            return {
                "url": url,
                "status": "error",
                "error": "Could not fetch page and screenshots disabled",
            }

        return {
            "url": url,
            "title": page_info.get("title", ""),
            "status": "success" if (http_success or screenshot_path) else "partial",
            "elements": page_info.get("elements", {}),
            "links": page_info.get("links", []),
            "forms": page_info.get("forms", []),
            "description": description,
            "screenshot": screenshot_path,
        }

    def _extract_page_info(self, html: str, url: str) -> dict[str, Any]:
        """Extract information from HTML content.
        
        Args:
            html: HTML content.
            url: Page URL.
            
        Returns:
            Extracted page information.
        """
        from html.parser import HTMLParser
        
        class PageInfoParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.title = ""
                self.in_title = False
                self.headings = []
                self.links = []
                self.buttons = []
                self.forms = []
                self.inputs = []
                self.images = []
                self.current_form = None
            
            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                
                if tag == "title":
                    self.in_title = True
                elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    pass  # Will capture in data
                elif tag == "a":
                    href = attrs_dict.get("href", "")
                    text = attrs_dict.get("title", "")
                    if href and not href.startswith("#") and not href.startswith("javascript:"):
                        self.links.append({"href": href, "text": text})
                elif tag == "button":
                    self.buttons.append({
                        "type": attrs_dict.get("type", "button"),
                        "text": "",
                    })
                elif tag == "form":
                    self.current_form = {
                        "action": attrs_dict.get("action", ""),
                        "method": attrs_dict.get("method", "get"),
                        "inputs": [],
                    }
                elif tag == "input" and self.current_form:
                    self.current_form["inputs"].append({
                        "type": attrs_dict.get("type", "text"),
                        "name": attrs_dict.get("name", ""),
                        "placeholder": attrs_dict.get("placeholder", ""),
                    })
                elif tag == "img":
                    self.images.append({
                        "src": attrs_dict.get("src", ""),
                        "alt": attrs_dict.get("alt", ""),
                    })
            
            def handle_endtag(self, tag):
                if tag == "title":
                    self.in_title = False
                elif tag == "form" and self.current_form:
                    self.forms.append(self.current_form)
                    self.current_form = None
            
            def handle_data(self, data):
                if self.in_title:
                    self.title += data.strip()
        
        parser = PageInfoParser()
        try:
            parser.feed(html)
        except Exception as e:
            logger.warning(f"HTML parsing error: {e}")
        
        return {
            "title": parser.title,
            "elements": {
                "headings": len(parser.headings),
                "buttons": len(parser.buttons),
                "images": len(parser.images),
                "inputs": len(parser.inputs),
            },
            "links": parser.links[:20],  # Limit links
            "forms": parser.forms,
        }
    
    async def _describe_page(self, page_info: dict[str, Any]) -> str:
        """Generate a description of the page using LLM.
        
        Args:
            page_info: Extracted page information.
            
        Returns:
            Page description.
        """
        template = """Based on the following page information, describe what this page does and how a user would interact with it.

Page Title: {title}

Elements found:
- Buttons: {buttons}
- Forms: {forms}
- Images: {images}
- Links: {links}

Forms on page:
{forms_detail}

Provide a brief, user-friendly description of:
1. What this page is for
2. What actions a user can take
3. Any important UI elements

Keep it concise and practical."""

        forms_detail = ""
        for i, form in enumerate(page_info.get("forms", [])[:3]):
            forms_detail += f"\nForm {i+1}: {form.get('method', 'GET').upper()} to {form.get('action', '/')}\n"
            for inp in form.get("inputs", [])[:5]:
                forms_detail += f"  - {inp.get('type', 'text')} input: {inp.get('name', 'unnamed')}\n"
        
        if not forms_detail:
            forms_detail = "No forms found"
        
        variables = {
            "title": page_info.get("title", "Unknown"),
            "buttons": page_info.get("elements", {}).get("buttons", 0),
            "forms": len(page_info.get("forms", [])),
            "images": page_info.get("elements", {}).get("images", 0),
            "links": len(page_info.get("links", [])),
            "forms_detail": forms_detail,
        }
        
        return await self.llm_service.generate_with_template(
            template,
            variables,
            model=settings.get_model_for_task("app_analysis"),
        )
    
    async def _crawl_and_analyze(
        self,
        start_url: str,
        max_depth: int,
        current_depth: int = 0,
    ) -> list[dict[str, Any]]:
        """Crawl the application and analyze discovered pages.
        
        Args:
            start_url: Starting URL.
            max_depth: Maximum depth to crawl.
            current_depth: Current crawl depth.
            
        Returns:
            List of page analyses.
        """
        if current_depth >= max_depth:
            return []
        
        if len(self._visited_urls) >= self.config.max_pages:
            return []
        
        if start_url in self._visited_urls:
            return []
        
        self._visited_urls.add(start_url)
        
        # Analyze current page
        analysis = await self._analyze_page(start_url)
        results = [analysis]
        
        if analysis.get("status") != "success":
            return results
        
        # Get links and crawl deeper
        base_parsed = urlparse(start_url)
        
        for link in analysis.get("links", []):
            href = link.get("href", "")
            if not href:
                continue
            
            # Build full URL
            full_url = urljoin(start_url, href)
            link_parsed = urlparse(full_url)
            
            # Only follow same-domain links
            if link_parsed.netloc != base_parsed.netloc:
                continue
            
            # Skip already visited
            if full_url in self._visited_urls:
                continue
            
            # Add delay between requests
            await asyncio.sleep(self.config.action_delay)
            
            # Recursively analyze
            sub_results = await self._crawl_and_analyze(
                full_url, max_depth, current_depth + 1
            )
            results.extend(sub_results)
            
            if len(self._visited_urls) >= self.config.max_pages:
                break
        
        return results
    
    async def _generate_app_documentation(
        self,
        app_url: str,
        page_analyses: list[dict[str, Any]],
    ) -> str:
        """Generate comprehensive app documentation.
        
        Args:
            app_url: Base application URL.
            page_analyses: List of page analysis results.
            
        Returns:
            Generated documentation.
        """
        # Build summary of pages
        pages_summary = []
        for page in page_analyses:
            if page.get("status") == "success":
                pages_summary.append(f"- **{page.get('title', 'Untitled')}** ({page.get('url', '')})")
                if page.get("description"):
                    # Take first sentence
                    desc = page.get("description", "").split(".")[0] + "."
                    pages_summary.append(f"  {desc}")
        
        template = """Generate user documentation for the following web application.

Application URL: {app_url}
Pages Analyzed: {page_count}

Pages discovered:
{pages_summary}

Generate a user guide that includes:
1. Application Overview - what the app does
2. Navigation Guide - how to move between pages
3. Key Features - main functionality available
4. Getting Started - basic workflow for new users

Format as Markdown with clear headings and bullet points.
Be practical and user-focused."""

        variables = {
            "app_url": app_url,
            "page_count": len(page_analyses),
            "pages_summary": "\n".join(pages_summary) if pages_summary else "No pages successfully analyzed",
        }
        
        return await self.llm_service.generate_with_template(
            template,
            variables,
            model=settings.get_model_for_task("app_analysis"),
        )
    
    async def take_screenshot(self, url: str, filename: Optional[str] = None) -> Optional[str]:
        """Take a screenshot of a page using Playwright.

        Args:
            url: URL to screenshot.
            filename: Optional filename.

        Returns:
            Path to screenshot or None.
        """
        try:
            from playwright.async_api import async_playwright

            if not filename:
                # Generate filename from URL
                parsed = urlparse(url)
                safe_path = parsed.path.replace("/", "_").strip("_") or "index"
                filename = f"{parsed.netloc}_{safe_path}.png"

            screenshot_path = self._screenshots_dir / filename

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1920, "height": 1080})

                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.screenshot(path=str(screenshot_path), full_page=True)
                await browser.close()

            logger.info(f"Screenshot saved: {screenshot_path}")
            return str(screenshot_path)

        except Exception as e:
            logger.error(f"Failed to take screenshot of {url}: {e}")
            return None

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
    ) -> None:
        """Save documentation to files.

        Args:
            doc: Documentation object.
            markdown_content: Raw markdown content.
        """
        # Create safe filename
        safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in doc.figma_file_name)
        safe_name = safe_name.replace(" ", "_").lower()

        # Save markdown
        md_path = self.output_dir / "markdown" / f"{safe_name}.md"
        md_path.write_text(markdown_content)
        logger.info(f"Saved markdown: {md_path}")

        # Save HTML
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
            "screenshots": getattr(doc, "_screenshots", []),
        }
        meta_path.write_text(json.dumps(meta_data, indent=2))

    def _convert_to_html(self, doc: Documentation, markdown_content: str) -> str:
        """Convert markdown to HTML.

        Args:
            doc: Documentation object.
            markdown_content: Raw markdown content.

        Returns:
            HTML string.
        """
        # Convert markdown to HTML
        html_content = md_lib.markdown(
            markdown_content,
            extensions=["fenced_code", "tables", "toc"],
        )

        # Simple HTML template
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{doc.title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; background: #0f0f0f; color: #e8e8e8; }}
        h1, h2, h3 {{ color: #e8e8e8; }}
        a {{ color: #6366f1; }}
        code {{ background: #1e1e1e; padding: 0.2rem 0.5rem; border-radius: 4px; }}
        pre {{ background: #1e1e1e; padding: 1rem; border-radius: 8px; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>{doc.title}</h1>
    <p><em>Generated: {doc.created_at.strftime("%Y-%m-%d %H:%M")}</em></p>
    {html_content}
</body>
</html>'''

