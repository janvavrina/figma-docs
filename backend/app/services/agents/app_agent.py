"""App analysis agent for generating documentation from running applications."""

import asyncio
import base64
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from app.core.config import settings
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
        documentation = await self._generate_app_documentation(
            app_url, page_analyses
        )
        
        return {
            "app_url": app_url,
            "pages_analyzed": len(page_analyses),
            "pages": page_analyses,
            "documentation": documentation,
            "screenshots_dir": str(self._screenshots_dir),
        }
    
    async def _analyze_page(self, url: str) -> dict[str, Any]:
        """Analyze a single page.
        
        Args:
            url: URL of the page.
            
        Returns:
            Page analysis dictionary.
        """
        logger.info(f"Analyzing page: {url}")
        
        try:
            # Fetch page content
            import httpx
            
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                html_content = response.text
            
            # Extract page info
            page_info = self._extract_page_info(html_content, url)
            
            # Generate description using LLM
            description = await self._describe_page(page_info)
            
            return {
                "url": url,
                "title": page_info.get("title", ""),
                "status": "success",
                "elements": page_info.get("elements", {}),
                "links": page_info.get("links", []),
                "forms": page_info.get("forms", []),
                "description": description,
            }
            
        except Exception as e:
            logger.error(f"Error analyzing {url}: {e}")
            return {
                "url": url,
                "status": "error",
                "error": str(e),
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
        """Take a screenshot of a page.
        
        Note: This is a placeholder. Full implementation would use
        Playwright, Puppeteer, or similar browser automation tool.
        
        Args:
            url: URL to screenshot.
            filename: Optional filename.
            
        Returns:
            Path to screenshot or None.
        """
        # This would require browser automation
        # For now, return None and log
        logger.info(f"Screenshot requested for {url} - requires browser automation")
        return None

