"""Design checker agent for comparing Figma designs with running applications."""

import asyncio
import base64
import io
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.services.figma import FigmaService
from app.services.llm import LLMService, get_llm_service

logger = logging.getLogger(__name__)


class DesignChecker:
    """Agent for comparing Figma designs with actual application implementations.
    
    Performs:
    - Visual comparison (screenshot diff)
    - Specification comparison (colors, fonts, dimensions)
    - Element existence check
    """
    
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        figma_service: Optional[FigmaService] = None,
    ):
        """Initialize the design checker.
        
        Args:
            llm_service: LLMService instance.
            figma_service: FigmaService instance.
        """
        self.llm_service = llm_service or get_llm_service()
        self.figma_service = figma_service or FigmaService()
        
        self._output_dir = Path(settings.app_agent.screenshot_dir) / "design_checks"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        
        self._browser = None
        self._playwright = None
    
    async def _ensure_browser(self):
        """Ensure Playwright browser is initialized."""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
                logger.info("Playwright browser initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Playwright: {e}")
                raise RuntimeError(
                    "Playwright not available. Run 'playwright install chromium' to install browser."
                ) from e
    
    async def close(self):
        """Close browser and cleanup."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        if self.figma_service:
            await self.figma_service.close()
    
    async def check_design(
        self,
        figma_file_key: str,
        app_url: str,
        frame_mappings: Optional[list[dict[str, str]]] = None,
        check_types: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Compare Figma design with running application.
        
        Args:
            figma_file_key: Figma file key.
            app_url: Base URL of the application.
            frame_mappings: Optional list of {figma_frame_id: app_page_url} mappings.
            check_types: Types of checks to perform: visual, specs, elements.
            
        Returns:
            Comparison result with mismatches.
        """
        check_types = check_types or ["visual", "specs", "elements"]
        
        logger.info(f"Starting design check: Figma {figma_file_key} vs {app_url}")
        
        result = {
            "figma_file_key": figma_file_key,
            "app_url": app_url,
            "timestamp": datetime.now().isoformat(),
            "checks_performed": check_types,
            "comparisons": [],
            "summary": {
                "total_checks": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
            },
            "overall_score": 0,
        }
        
        try:
            # Get Figma file data
            figma_file = await self.figma_service.get_file(figma_file_key)
            design_info = self.figma_service.extract_design_info(figma_file)
            
            # Extract frames to compare
            frames_to_check = []
            if frame_mappings:
                frames_to_check = frame_mappings
            else:
                # Auto-discover frames from Figma
                frames_to_check = await self._auto_discover_frames(design_info, app_url)
            
            if not frames_to_check:
                result["error"] = "No frames to compare. Provide frame_mappings or ensure Figma file has frames."
                return result
            
            # Perform comparisons
            for mapping in frames_to_check:
                comparison = await self._compare_frame(
                    figma_file_key=figma_file_key,
                    frame_id=mapping.get("figma_frame_id"),
                    frame_name=mapping.get("figma_frame_name", ""),
                    app_page_url=mapping.get("app_url", app_url),
                    check_types=check_types,
                    design_info=design_info,
                )
                result["comparisons"].append(comparison)
                
                # Update summary
                result["summary"]["total_checks"] += comparison.get("total_checks", 0)
                result["summary"]["passed"] += comparison.get("passed", 0)
                result["summary"]["failed"] += comparison.get("failed", 0)
                result["summary"]["warnings"] += comparison.get("warnings", 0)
            
            # Calculate overall score
            total = result["summary"]["total_checks"]
            if total > 0:
                result["overall_score"] = round(
                    (result["summary"]["passed"] / total) * 100, 1
                )
            
            # Generate LLM analysis
            result["analysis"] = await self._generate_analysis(result)
            
        except Exception as e:
            logger.error(f"Design check failed: {e}")
            result["error"] = str(e)
        
        return result
    
    async def _auto_discover_frames(
        self,
        design_info: dict[str, Any],
        app_url: str,
    ) -> list[dict[str, str]]:
        """Auto-discover frames from Figma and map to app pages.
        
        Args:
            design_info: Extracted Figma design info.
            app_url: Base app URL.
            
        Returns:
            List of frame mappings.
        """
        mappings = []
        
        for page in design_info.get("pages", []):
            for frame in page.get("frames", [])[:5]:  # Limit frames
                frame_name = frame.get("name", "").lower()
                
                # Try to guess URL from frame name
                guessed_url = app_url
                if "home" in frame_name or "landing" in frame_name:
                    guessed_url = app_url
                elif "login" in frame_name or "signin" in frame_name:
                    guessed_url = f"{app_url.rstrip('/')}/login"
                elif "signup" in frame_name or "register" in frame_name:
                    guessed_url = f"{app_url.rstrip('/')}/signup"
                elif "dashboard" in frame_name:
                    guessed_url = f"{app_url.rstrip('/')}/dashboard"
                elif "settings" in frame_name:
                    guessed_url = f"{app_url.rstrip('/')}/settings"
                elif "profile" in frame_name:
                    guessed_url = f"{app_url.rstrip('/')}/profile"
                
                mappings.append({
                    "figma_frame_id": frame.get("id"),
                    "figma_frame_name": frame.get("name"),
                    "app_url": guessed_url,
                })
        
        return mappings
    
    async def _compare_frame(
        self,
        figma_file_key: str,
        frame_id: str,
        frame_name: str,
        app_page_url: str,
        check_types: list[str],
        design_info: dict[str, Any],
    ) -> dict[str, Any]:
        """Compare a single Figma frame with an app page.
        
        Args:
            figma_file_key: Figma file key.
            frame_id: Figma frame node ID.
            frame_name: Frame name for display.
            app_page_url: URL of the app page.
            check_types: Types of checks to perform.
            design_info: Full design info for specs.
            
        Returns:
            Comparison result for this frame.
        """
        comparison = {
            "figma_frame": frame_name,
            "figma_frame_id": frame_id,
            "app_url": app_page_url,
            "checks": [],
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0,
        }
        
        try:
            # Get Figma screenshot
            figma_screenshot = None
            if "visual" in check_types and frame_id:
                figma_screenshot = await self._get_figma_screenshot(
                    figma_file_key, frame_id
                )
            
            # Get app screenshot and styles
            app_screenshot = None
            app_styles = None
            app_elements = None
            
            if any(t in check_types for t in ["visual", "specs", "elements"]):
                await self._ensure_browser()
                app_data = await self._capture_app_page(app_page_url)
                app_screenshot = app_data.get("screenshot")
                app_styles = app_data.get("styles")
                app_elements = app_data.get("elements")
            
            # Perform visual comparison
            if "visual" in check_types and figma_screenshot and app_screenshot:
                visual_result = await self._compare_visuals(
                    figma_screenshot, app_screenshot, frame_name
                )
                comparison["checks"].append(visual_result)
                self._update_counts(comparison, visual_result)
            
            # Perform specs comparison
            if "specs" in check_types and app_styles:
                specs_results = await self._compare_specs(
                    design_info, app_styles, frame_name
                )
                comparison["checks"].extend(specs_results)
                for r in specs_results:
                    self._update_counts(comparison, r)
            
            # Perform element existence check
            if "elements" in check_types and app_elements:
                element_results = await self._check_elements(
                    design_info, app_elements, frame_name
                )
                comparison["checks"].extend(element_results)
                for r in element_results:
                    self._update_counts(comparison, r)
            
        except Exception as e:
            logger.error(f"Error comparing frame {frame_name}: {e}")
            comparison["error"] = str(e)
        
        return comparison
    
    def _update_counts(self, comparison: dict, check_result: dict):
        """Update pass/fail/warning counts."""
        comparison["total_checks"] += 1
        status = check_result.get("status", "warning")
        if status == "pass":
            comparison["passed"] += 1
        elif status == "fail":
            comparison["failed"] += 1
        else:
            comparison["warnings"] += 1
    
    async def _get_figma_screenshot(
        self,
        file_key: str,
        node_id: str,
    ) -> Optional[bytes]:
        """Get screenshot of a Figma frame.
        
        Args:
            file_key: Figma file key.
            node_id: Node ID to screenshot.
            
        Returns:
            Screenshot bytes or None.
        """
        try:
            images = await self.figma_service.get_images(
                file_key,
                [node_id],
                format="png",
                scale=2.0,
            )
            
            image_url = images.get(node_id)
            if not image_url:
                return None
            
            # Download the image
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()
                return response.content
                
        except Exception as e:
            logger.error(f"Failed to get Figma screenshot: {e}")
            return None
    
    async def _capture_app_page(self, url: str) -> dict[str, Any]:
        """Capture screenshot and extract styles from app page.
        
        Args:
            url: Page URL.
            
        Returns:
            Dict with screenshot, styles, and elements.
        """
        result = {
            "screenshot": None,
            "styles": {},
            "elements": [],
        }
        
        try:
            page = await self._browser.new_page()
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Take screenshot
            result["screenshot"] = await page.screenshot(full_page=False)
            
            # Extract computed styles
            result["styles"] = await page.evaluate("""() => {
                const styles = {
                    colors: new Set(),
                    fonts: new Set(),
                    fontSizes: new Set(),
                };
                
                const elements = document.querySelectorAll('*');
                elements.forEach(el => {
                    const computed = window.getComputedStyle(el);
                    
                    // Colors
                    if (computed.color && computed.color !== 'rgba(0, 0, 0, 0)') {
                        styles.colors.add(computed.color);
                    }
                    if (computed.backgroundColor && computed.backgroundColor !== 'rgba(0, 0, 0, 0)') {
                        styles.colors.add(computed.backgroundColor);
                    }
                    
                    // Fonts
                    if (computed.fontFamily) {
                        styles.fonts.add(computed.fontFamily.split(',')[0].trim().replace(/['"]/g, ''));
                    }
                    
                    // Font sizes
                    if (computed.fontSize) {
                        styles.fontSizes.add(computed.fontSize);
                    }
                });
                
                return {
                    colors: [...styles.colors].slice(0, 20),
                    fonts: [...styles.fonts].slice(0, 10),
                    fontSizes: [...styles.fontSizes].slice(0, 10),
                };
            }""")
            
            # Extract elements
            result["elements"] = await page.evaluate("""() => {
                const elements = [];
                
                // Buttons
                document.querySelectorAll('button, [role="button"], input[type="submit"]').forEach(el => {
                    elements.push({
                        type: 'button',
                        text: el.textContent?.trim() || el.value || '',
                        visible: el.offsetParent !== null,
                    });
                });
                
                // Links
                document.querySelectorAll('a').forEach(el => {
                    elements.push({
                        type: 'link',
                        text: el.textContent?.trim() || '',
                        href: el.href,
                        visible: el.offsetParent !== null,
                    });
                });
                
                // Inputs
                document.querySelectorAll('input, textarea, select').forEach(el => {
                    elements.push({
                        type: 'input',
                        inputType: el.type || 'text',
                        placeholder: el.placeholder || '',
                        name: el.name || '',
                        visible: el.offsetParent !== null,
                    });
                });
                
                // Images
                document.querySelectorAll('img').forEach(el => {
                    elements.push({
                        type: 'image',
                        alt: el.alt || '',
                        visible: el.offsetParent !== null,
                    });
                });
                
                // Headings
                document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(el => {
                    elements.push({
                        type: 'heading',
                        level: el.tagName.toLowerCase(),
                        text: el.textContent?.trim() || '',
                        visible: el.offsetParent !== null,
                    });
                });
                
                return elements;
            }""")
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Failed to capture app page {url}: {e}")
        
        return result
    
    async def _compare_visuals(
        self,
        figma_screenshot: bytes,
        app_screenshot: bytes,
        frame_name: str,
    ) -> dict[str, Any]:
        """Compare two screenshots visually.
        
        Args:
            figma_screenshot: Figma screenshot bytes.
            app_screenshot: App screenshot bytes.
            frame_name: Frame name for reporting.
            
        Returns:
            Visual comparison result.
        """
        try:
            from PIL import Image
            
            # Load images
            figma_img = Image.open(io.BytesIO(figma_screenshot))
            app_img = Image.open(io.BytesIO(app_screenshot))
            
            # Resize to same dimensions for comparison
            target_size = (min(figma_img.width, app_img.width), 
                          min(figma_img.height, app_img.height))
            figma_img = figma_img.resize(target_size, Image.Resampling.LANCZOS)
            app_img = app_img.resize(target_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB
            figma_img = figma_img.convert("RGB")
            app_img = app_img.convert("RGB")
            
            # Calculate simple pixel difference
            diff_pixels = 0
            total_pixels = target_size[0] * target_size[1]
            
            figma_data = figma_img.load()
            app_data = app_img.load()
            
            # Create diff image
            diff_img = Image.new("RGB", target_size)
            diff_data = diff_img.load()
            
            threshold = 30  # Color difference threshold
            
            for x in range(target_size[0]):
                for y in range(target_size[1]):
                    fp = figma_data[x, y]
                    ap = app_data[x, y]
                    
                    # Calculate color distance
                    dist = math.sqrt(
                        (fp[0] - ap[0]) ** 2 +
                        (fp[1] - ap[1]) ** 2 +
                        (fp[2] - ap[2]) ** 2
                    )
                    
                    if dist > threshold:
                        diff_pixels += 1
                        diff_data[x, y] = (255, 0, 0)  # Red for difference
                    else:
                        diff_data[x, y] = app_data[x, y]
            
            similarity = ((total_pixels - diff_pixels) / total_pixels) * 100
            
            # Save images for reference
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c if c.isalnum() else "_" for c in frame_name)
            
            figma_path = self._output_dir / f"{safe_name}_{timestamp}_figma.png"
            app_path = self._output_dir / f"{safe_name}_{timestamp}_app.png"
            diff_path = self._output_dir / f"{safe_name}_{timestamp}_diff.png"
            
            figma_img.save(figma_path)
            app_img.save(app_path)
            diff_img.save(diff_path)
            
            # Determine status
            if similarity >= 95:
                status = "pass"
                message = f"Visual match: {similarity:.1f}% similar"
            elif similarity >= 80:
                status = "warning"
                message = f"Minor visual differences: {similarity:.1f}% similar"
            else:
                status = "fail"
                message = f"Significant visual differences: {similarity:.1f}% similar"
            
            return {
                "check_type": "visual",
                "frame": frame_name,
                "status": status,
                "message": message,
                "similarity_percent": round(similarity, 1),
                "diff_pixels": diff_pixels,
                "total_pixels": total_pixels,
                "figma_screenshot": str(figma_path),
                "app_screenshot": str(app_path),
                "diff_image": str(diff_path),
            }
            
        except Exception as e:
            logger.error(f"Visual comparison failed: {e}")
            return {
                "check_type": "visual",
                "frame": frame_name,
                "status": "error",
                "message": f"Visual comparison failed: {e}",
            }
    
    async def _compare_specs(
        self,
        design_info: dict[str, Any],
        app_styles: dict[str, Any],
        frame_name: str,
    ) -> list[dict[str, Any]]:
        """Compare design specifications with app styles.
        
        Args:
            design_info: Figma design info.
            app_styles: Extracted app styles.
            frame_name: Frame name for reporting.
            
        Returns:
            List of spec comparison results.
        """
        results = []
        
        # Extract design colors
        design_colors = set()
        for color in design_info.get("colors", []):
            color_name = color.get("name", "")
            design_colors.add(color_name.lower())
        
        # Check fonts
        design_fonts = set()
        for typo in design_info.get("typography", []):
            font_name = typo.get("name", "")
            design_fonts.add(font_name.lower())
        
        app_fonts = set(f.lower() for f in app_styles.get("fonts", []))
        
        # Font check
        if design_fonts and app_fonts:
            # Simple check: at least one design font should be in app
            font_match = any(
                any(df in af for af in app_fonts)
                for df in design_fonts
            )
            
            results.append({
                "check_type": "specs",
                "category": "fonts",
                "frame": frame_name,
                "status": "pass" if font_match else "warning",
                "message": f"Fonts in app: {', '.join(list(app_fonts)[:5])}",
                "design_fonts": list(design_fonts)[:5],
                "app_fonts": list(app_fonts)[:5],
            })
        
        # Color count check (basic)
        app_colors = app_styles.get("colors", [])
        if app_colors:
            results.append({
                "check_type": "specs",
                "category": "colors",
                "frame": frame_name,
                "status": "pass",
                "message": f"Found {len(app_colors)} colors in app",
                "app_colors": app_colors[:10],
            })
        
        return results
    
    async def _check_elements(
        self,
        design_info: dict[str, Any],
        app_elements: list[dict[str, Any]],
        frame_name: str,
    ) -> list[dict[str, Any]]:
        """Check if design elements exist in the app.
        
        Args:
            design_info: Figma design info.
            app_elements: Extracted app elements.
            frame_name: Frame name for reporting.
            
        Returns:
            List of element check results.
        """
        results = []
        
        # Count element types
        app_buttons = [e for e in app_elements if e.get("type") == "button" and e.get("visible")]
        app_inputs = [e for e in app_elements if e.get("type") == "input" and e.get("visible")]
        app_images = [e for e in app_elements if e.get("type") == "image" and e.get("visible")]
        app_headings = [e for e in app_elements if e.get("type") == "heading" and e.get("visible")]
        
        results.append({
            "check_type": "elements",
            "category": "buttons",
            "frame": frame_name,
            "status": "pass" if app_buttons else "warning",
            "message": f"Found {len(app_buttons)} buttons",
            "count": len(app_buttons),
            "examples": [b.get("text", "")[:30] for b in app_buttons[:5]],
        })
        
        results.append({
            "check_type": "elements",
            "category": "inputs",
            "frame": frame_name,
            "status": "pass" if app_inputs else "pass",  # Inputs optional
            "message": f"Found {len(app_inputs)} input fields",
            "count": len(app_inputs),
        })
        
        results.append({
            "check_type": "elements",
            "category": "images",
            "frame": frame_name,
            "status": "pass",
            "message": f"Found {len(app_images)} images",
            "count": len(app_images),
        })
        
        results.append({
            "check_type": "elements",
            "category": "headings",
            "frame": frame_name,
            "status": "pass" if app_headings else "warning",
            "message": f"Found {len(app_headings)} headings",
            "count": len(app_headings),
            "examples": [h.get("text", "")[:50] for h in app_headings[:5]],
        })
        
        return results
    
    async def _generate_analysis(self, result: dict[str, Any]) -> str:
        """Generate LLM-powered analysis of the comparison results.
        
        Args:
            result: Full comparison result.
            
        Returns:
            Analysis text.
        """
        # Build summary for LLM
        checks_summary = []
        for comp in result.get("comparisons", []):
            frame = comp.get("figma_frame", "Unknown")
            for check in comp.get("checks", []):
                status = check.get("status", "unknown")
                message = check.get("message", "")
                check_type = check.get("check_type", "")
                checks_summary.append(f"- [{status.upper()}] {frame} - {check_type}: {message}")
        
        template = """Analyze the following design-to-implementation comparison results and provide actionable feedback.

Overall Score: {score}%
Total Checks: {total}
Passed: {passed}
Failed: {failed}
Warnings: {warnings}

Detailed Results:
{checks_summary}

Provide:
1. Executive Summary (2-3 sentences)
2. Critical Issues (if any failed checks)
3. Recommendations for fixing mismatches
4. Priority order for fixes

Be concise and actionable."""

        variables = {
            "score": result.get("overall_score", 0),
            "total": result["summary"]["total_checks"],
            "passed": result["summary"]["passed"],
            "failed": result["summary"]["failed"],
            "warnings": result["summary"]["warnings"],
            "checks_summary": "\n".join(checks_summary) if checks_summary else "No checks performed",
        }
        
        try:
            return await self.llm_service.generate_with_template(
                template,
                variables,
                model=settings.get_model_for_task("app_analysis"),
            )
        except Exception as e:
            logger.error(f"Failed to generate analysis: {e}")
            return f"Analysis generation failed: {e}"


# Global instance
_design_checker: Optional[DesignChecker] = None


def get_design_checker() -> DesignChecker:
    """Get or create the global DesignChecker instance."""
    global _design_checker
    if _design_checker is None:
        _design_checker = DesignChecker()
    return _design_checker

