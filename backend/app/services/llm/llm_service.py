"""LLM service for interacting with Ollama models via LangChain."""

import base64
import logging
from typing import Any, Optional

import httpx
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings

logger = logging.getLogger(__name__)

# Headers for ngrok tunnel (skip browser warning)
NGROK_HEADERS = {
    "ngrok-skip-browser-warning": "true",
}


class LLMService:
    """Service for interacting with Ollama LLM models."""
    
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize LLM service.
        
        Args:
            model: Model name to use. If not provided, uses default from config.
            base_url: Ollama server URL. If not provided, uses config.
        """
        self.base_url = base_url or settings.llm.ollama_base_url
        self.default_model = model or settings.llm.default_model
        self._models: dict[str, OllamaLLM] = {}
        
        # Check if using ngrok URL
        self._is_ngrok = "ngrok" in self.base_url.lower() if self.base_url else False
    
    def _get_headers(self) -> dict[str, str]:
        """Get headers for Ollama requests (includes ngrok headers if needed)."""
        if self._is_ngrok:
            return NGROK_HEADERS.copy()
        return {}
    
    def _get_model(self, model_name: Optional[str] = None) -> OllamaLLM:
        """Get or create an Ollama model instance.
        
        Args:
            model_name: Name of the model to get.
            
        Returns:
            OllamaLLM instance.
        """
        model = model_name or self.default_model
        
        if model not in self._models:
            self._models[model] = OllamaLLM(
                model=model,
                base_url=self.base_url,
                temperature=settings.llm.generation.temperature,
                num_predict=settings.llm.generation.max_tokens,
                top_p=settings.llm.generation.top_p,
                headers=self._get_headers(),
            )
            logger.info(f"Initialized Ollama model: {model} (ngrok: {self._is_ngrok})")
        
        return self._models[model]
    
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate text from a prompt.
        
        Args:
            prompt: The prompt to generate from.
            model: Optional model override.
            **kwargs: Additional generation parameters.
            
        Returns:
            Generated text.
        """
        llm = self._get_model(model)
        
        try:
            response = await llm.ainvoke(prompt)
            return response
        except Exception as e:
            logger.error(f"Error generating text: {e}")
            raise
    
    async def generate_with_image(
        self,
        prompt: str,
        images: list[bytes],
        model: Optional[str] = None,
        stream: bool = False,
    ) -> str:
        """Generate text from a prompt with images using Ollama vision API.
        
        Args:
            prompt: The prompt to generate from.
            images: List of image bytes (PNG/JPEG).
            model: Optional model override. Defaults to vision model from config.
            stream: Whether to stream the response.
            
        Returns:
            Generated text.
        """
        # Get vision model from config if available, otherwise use provided model or default
        if model:
            model_name = model
        else:
            # Try to get vision model from config
            try:
                if hasattr(settings.llm.models, "vision"):
                    model_name = settings.llm.models.vision
                else:
                    model_name = self.default_model
            except AttributeError:
                model_name = self.default_model
        
        # Convert images to base64
        image_b64_list = []
        for img_bytes in images:
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            image_b64_list.append(img_b64)
        
        # Prepare request payload
        payload = {
            "model": model_name,
            "prompt": prompt,
            "images": image_b64_list,
            "stream": stream,
            "options": {
                "temperature": settings.llm.generation.temperature,
                "num_predict": settings.llm.generation.max_tokens,
                "top_p": settings.llm.generation.top_p,
            },
        }
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                url = f"{self.base_url}/api/generate"
                headers = self._get_headers()
                
                if stream:
                    # Stream response
                    async with client.stream(
                        "POST",
                        url,
                        json=payload,
                        headers=headers,
                    ) as response:
                        response.raise_for_status()
                        full_response = ""
                        async for line in response.aiter_lines():
                            if line:
                                import json
                                try:
                                    chunk = json.loads(line)
                                    if "response" in chunk:
                                        full_response += chunk["response"]
                                    if chunk.get("done", False):
                                        break
                                except json.JSONDecodeError:
                                    continue
                        return full_response
                else:
                    # Non-streaming response
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    return data.get("response", "")
                    
        except Exception as e:
            logger.error(f"Error generating with image: {e}")
            raise
    
    async def generate_with_template(
        self,
        template: str,
        variables: dict[str, Any],
        model: Optional[str] = None,
    ) -> str:
        """Generate text using a prompt template.
        
        Args:
            template: Prompt template string with {variable} placeholders.
            variables: Dictionary of variables to fill in the template.
            model: Optional model override.
            
        Returns:
            Generated text.
        """
        llm = self._get_model(model)
        prompt = PromptTemplate.from_template(template)
        chain = prompt | llm | StrOutputParser()
        
        try:
            response = await chain.ainvoke(variables)
            return response
        except Exception as e:
            logger.error(f"Error generating with template: {e}")
            raise
    
    async def generate_documentation(
        self,
        design_info: dict[str, Any],
        doc_type: str = "both",
    ) -> str:
        """Generate documentation from Figma design information.
        
        Args:
            design_info: Extracted design information from Figma.
            doc_type: Type of documentation (user, dev, both).
            
        Returns:
            Generated documentation in markdown format.
        """
        model = settings.get_model_for_task("documentation")
        
        template = self._get_documentation_template(doc_type)
        
        variables = {
            "file_name": design_info.get("file_name", "Unknown"),
            "pages": self._format_pages(design_info.get("pages", [])),
            "components": self._format_components(design_info.get("components", [])),
            "styles": self._format_styles(design_info.get("styles", [])),
            "colors": self._format_colors(design_info.get("colors", [])),
            "typography": self._format_typography(design_info.get("typography", [])),
            "doc_type": doc_type,
        }
        
        return await self.generate_with_template(template, variables, model)
    
    def _get_documentation_template(self, doc_type: str) -> str:
        """Get the documentation generation template.

        Args:
            doc_type: Type of documentation to generate.

        Returns:
            Prompt template string.
        """
        base_template = """You are an expert technical documentation writer specializing in UI/UX design documentation.
Your task is to generate COMPREHENSIVE and DETAILED documentation for the following Figma design.

IMPORTANT: Generate extensive, thorough documentation. Do NOT be brief. Each section should be detailed and informative.

# Design: {file_name}

## Pages and Screens
{pages}

## Components
{components}

## Design Styles
{styles}

## Color Palette
{colors}

## Typography
{typography}

---

"""

        if doc_type == "user":
            base_template += """Generate COMPREHENSIVE USER documentation. Be DETAILED and THOROUGH in each section.

Required sections (write extensively about each):

## 1. Application Overview
- Detailed description of what this application does
- Target audience and use cases
- Key features and capabilities

## 2. Screen-by-Screen Guide
For EACH screen/page, provide:
- Screen name and purpose
- Detailed description of all visible elements
- Step-by-step instructions for using the screen
- What happens when user interacts with each element
- Common tasks that can be performed

## 3. Navigation Guide
- How to move between screens
- Navigation patterns used (tabs, menus, buttons)
- Breadcrumb structure if applicable
- Quick navigation tips

## 4. User Workflows
- Common task flows (e.g., "How to create a new item")
- Step-by-step guides for key actions
- Expected outcomes for each workflow

## 5. UI Elements Reference
- Description of all button types and their functions
- Form fields and input requirements
- Icons and their meanings
- Status indicators and notifications

## 6. Tips and Best Practices
- Keyboard shortcuts if applicable
- Time-saving features
- Common mistakes to avoid
- Helpful hints for new users

Write in a friendly, accessible tone. Use clear headings, numbered steps, and bullet points.
Be THOROUGH - aim for at least 1500-2000 words of documentation."""

        elif doc_type == "dev":
            base_template += """Generate COMPREHENSIVE DEVELOPER documentation. Be DETAILED and THOROUGH in each section.

Required sections (write extensively about each):

## 1. Design System Overview
- Architecture of the design system
- Design principles and patterns used
- Naming conventions

## 2. Component Library
For EACH component, provide:
- Component name and purpose
- Props/variants if applicable
- Visual states (default, hover, active, disabled, error)
- Sizing specifications
- Usage guidelines
- Code implementation hints

## 3. Design Tokens
### Colors
- Primary, secondary, accent colors with hex/RGB values
- Semantic color usage (success, error, warning, info)
- Background colors and their use cases
- Text colors and contrast ratios

### Typography
- Font families and fallbacks
- Font sizes scale (in px, rem, or design system units)
- Line heights
- Font weights
- Text styles for headings, body, captions

### Spacing
- Spacing scale (4px, 8px, 16px, etc.)
- Padding conventions
- Margin conventions
- Grid system if applicable

### Borders & Shadows
- Border radius values
- Border widths and styles
- Shadow definitions (box-shadow values)

## 4. Layout Specifications
- Grid system details
- Breakpoints for responsive design
- Container widths
- Flex/Grid layouts used

## 5. Component Specifications
For each major frame/component provide:
- Exact dimensions (width x height)
- Padding and margins
- Background colors
- Border specifications
- Typography used

## 6. Interaction States
- Hover states and transitions
- Focus states for accessibility
- Active/pressed states
- Loading states
- Error states

## 7. Accessibility Guidelines
- Color contrast requirements
- Focus indicators
- ARIA labels and roles
- Keyboard navigation requirements

## 8. Implementation Notes
- Suggested CSS/styling approach
- Component hierarchy recommendations
- Reusable patterns identified
- Performance considerations

Write in technical language suitable for developers.
Be THOROUGH - aim for at least 2000-2500 words of documentation."""

        else:  # both
            base_template += """Generate COMPREHENSIVE documentation for BOTH users and developers. Be DETAILED and THOROUGH.

IMPORTANT: For EACH major screen/frame, create a section with BOTH perspectives using this EXACT format:

### [Screen/Frame Name]

## User Perspective

[Detailed user documentation for this screen including:]
- What this screen does and its purpose
- All visible elements and their functions
- Step-by-step usage instructions
- How to navigate from/to this screen
- Tips for using this screen effectively

## Developer Perspective

[Detailed developer documentation for this screen including:]
- Component structure and hierarchy
- Design tokens used (colors with hex values, typography, spacing)
- Exact dimensions and specifications
- States (default, hover, active, disabled)
- Implementation notes and CSS guidelines
- Accessibility considerations

---

After all screen sections, include these summary sections:

### Design System Summary

## User Perspective

- Application overview
- Key features summary
- Navigation patterns
- Common workflows
- Tips and best practices

## Developer Perspective

- Complete color palette with hex values
- Typography scale
- Spacing system
- Component library overview
- Global accessibility guidelines
- Implementation best practices

Write clearly and be THOROUGH - aim for at least 2500-3000 words total documentation.
Each screen should have substantial content in BOTH perspectives."""

        base_template += """

FORMATTING REQUIREMENTS:
- Use Markdown format with proper headings (##, ###, ####)
- Use bullet points and numbered lists for clarity
- Include tables where appropriate for specifications
- Use code blocks for CSS values or technical specifications
- Add horizontal rules (---) between major sections

REMEMBER: Generate EXTENSIVE documentation. Do not summarize or abbreviate.
Each section should be detailed and comprehensive."""

        return base_template
    
    def _format_pages(self, pages: list[dict]) -> str:
        """Format pages information for the prompt."""
        if not pages:
            return "No pages found."
        
        lines = []
        for page in pages:
            lines.append(f"### {page.get('name', 'Unnamed Page')}")
            
            frames = page.get("frames", [])
            if frames:
                lines.append("Frames/Screens:")
                for frame in frames[:10]:  # Limit to prevent token overflow
                    frame_name = frame.get("name", "Unnamed")
                    dims = frame.get("dimensions", {})
                    size = f" ({dims.get('width', '?')}x{dims.get('height', '?')})" if dims else ""
                    lines.append(f"  - {frame_name}{size}")
                    
                    # Add children summary
                    children = frame.get("children", [])
                    if children:
                        child_types = {}
                        for child in children:
                            ctype = child.get("type", "Unknown")
                            child_types[ctype] = child_types.get(ctype, 0) + 1
                        types_str = ", ".join(f"{v} {k}" for k, v in child_types.items())
                        lines.append(f"    Contains: {types_str}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_components(self, components: list[dict]) -> str:
        """Format components information for the prompt."""
        if not components:
            return "No components defined."
        
        lines = []
        for comp in components[:20]:  # Limit components
            name = comp.get("name", "Unnamed")
            desc = comp.get("description", "")
            lines.append(f"- **{name}**" + (f": {desc}" if desc else ""))
        
        return "\n".join(lines)
    
    def _format_styles(self, styles: list[dict]) -> str:
        """Format styles information for the prompt."""
        if not styles:
            return "No styles defined."
        
        lines = []
        for style in styles[:20]:
            name = style.get("name", "Unnamed")
            stype = style.get("type", "")
            lines.append(f"- {name} ({stype})")
        
        return "\n".join(lines)
    
    def _format_colors(self, colors: list[dict]) -> str:
        """Format color information for the prompt."""
        if not colors:
            return "No color styles defined."
        
        lines = []
        for color in colors[:15]:
            name = color.get("name", "Unnamed")
            lines.append(f"- {name}")
        
        return "\n".join(lines)
    
    def _format_typography(self, typography: list[dict]) -> str:
        """Format typography information for the prompt."""
        if not typography:
            return "No typography styles defined."
        
        lines = []
        for typo in typography[:15]:
            name = typo.get("name", "Unnamed")
            lines.append(f"- {name}")
        
        return "\n".join(lines)
    
    async def chat(
        self,
        message: str,
        context: str = "",
        history: list[dict[str, str]] = None,
    ) -> str:
        """Generate a chat response with optional context.
        
        Args:
            message: User message.
            context: Optional context from RAG retrieval.
            history: Optional conversation history.
            
        Returns:
            Assistant response.
        """
        model = settings.get_model_for_task("chatbot")
        
        template = """You are a helpful assistant that answers questions about application design and documentation.

{context_section}

{history_section}

User: {message}

Provide a helpful, accurate response based on the available context. If you don't have enough information, say so."""

        context_section = f"Context from documentation:\n{context}" if context else ""
        
        history_section = ""
        if history:
            history_lines = []
            for msg in history[-5:]:  # Last 5 messages
                role = msg.get("role", "user").capitalize()
                content = msg.get("content", "")
                history_lines.append(f"{role}: {content}")
            history_section = "Previous conversation:\n" + "\n".join(history_lines)
        
        variables = {
            "context_section": context_section,
            "history_section": history_section,
            "message": message,
        }
        
        return await self.generate_with_template(template, variables, model)
    
    async def analyze_code(self, code_content: str, file_path: str) -> str:
        """Analyze code and generate documentation.
        
        Args:
            code_content: The code to analyze.
            file_path: Path to the code file.
            
        Returns:
            Generated code documentation.
        """
        model = settings.get_model_for_task("code_analysis")
        
        template = """Analyze the following code and generate documentation.

File: {file_path}

```
{code_content}
```

Generate documentation that includes:
1. Overview of what this code does
2. Main functions/classes and their purposes
3. Key dependencies and imports
4. Usage examples if applicable
5. Any important notes or considerations

Format the output as Markdown."""

        variables = {
            "file_path": file_path,
            "code_content": code_content[:8000],  # Limit code length
        }
        
        return await self.generate_with_template(template, variables, model)


    async def list_models(self) -> list[dict[str, Any]]:
        """List all available models on the Ollama server.
        
        Returns:
            List of model information dictionaries.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/tags",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
    
    async def pull_model(self, model_name: str) -> dict[str, Any]:
        """Pull (download) a model from Ollama registry.
        
        Args:
            model_name: Name of the model to pull (e.g., "gemma3:27b").
            
        Returns:
            Status information about the pull operation.
        """
        logger.info(f"Pulling model: {model_name}")
        
        async with httpx.AsyncClient(timeout=600.0) as client:  # 10 min timeout for large models
            response = await client.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": False},
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()
    
    async def pull_model_stream(self, model_name: str):
        """Pull a model with streaming progress updates.
        
        Args:
            model_name: Name of the model to pull.
            
        Yields:
            Progress updates as dictionaries.
        """
        logger.info(f"Pulling model (streaming): {model_name}")
        
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": True},
                headers=self._get_headers(),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        import json
                        yield json.loads(line)
    
    async def check_model_exists(self, model_name: str) -> bool:
        """Check if a model exists on the Ollama server.
        
        Args:
            model_name: Name of the model to check.
            
        Returns:
            True if model exists, False otherwise.
        """
        try:
            models = await self.list_models()
            model_names = [m.get("name", "") for m in models]
            # Check both exact match and without tag
            base_name = model_name.split(":")[0]
            return any(
                model_name == name or 
                model_name in name or 
                base_name in name 
                for name in model_names
            )
        except Exception as e:
            logger.error(f"Error checking model existence: {e}")
            return False
    
    async def ensure_models_available(self) -> dict[str, Any]:
        """Ensure all configured models are available, pulling if necessary.
        
        Returns:
            Status report of model availability and pull operations.
        """
        required_models = set([
            settings.llm.models.documentation,
            settings.llm.models.chatbot,
            settings.llm.models.code_analysis,
            settings.llm.models.app_analysis,
        ])
        
        results = {
            "checked": [],
            "already_available": [],
            "pulled": [],
            "failed": [],
        }
        
        for model in required_models:
            results["checked"].append(model)
            
            try:
                exists = await self.check_model_exists(model)
                
                if exists:
                    results["already_available"].append(model)
                    logger.info(f"Model already available: {model}")
                else:
                    logger.info(f"Model not found, pulling: {model}")
                    await self.pull_model(model)
                    results["pulled"].append(model)
                    logger.info(f"Successfully pulled: {model}")
                    
            except Exception as e:
                logger.error(f"Failed to ensure model {model}: {e}")
                results["failed"].append({"model": model, "error": str(e)})
        
        return results
    
    async def get_ollama_status(self) -> dict[str, Any]:
        """Get Ollama server status and information.
        
        Returns:
            Server status information.
        """
        logger.info(f"Checking Ollama status at: {self.base_url} (ngrok: {self._is_ngrok})")
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Check if server is reachable
                url = f"{self.base_url}/api/tags"
                headers = self._get_headers()
                logger.debug(f"Request URL: {url}, Headers: {headers}")
                
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                models = response.json().get("models", [])
                
                logger.info(f"Ollama online with {len(models)} models")
                
                return {
                    "status": "online",
                    "url": self.base_url,
                    "is_ngrok": self._is_ngrok,
                    "models_count": len(models),
                    "models": [m.get("name") for m in models],
                }
        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to Ollama at {self.base_url}: {e}")
            return {
                "status": "offline",
                "url": self.base_url,
                "is_ngrok": self._is_ngrok,
                "error": f"Cannot connect to Ollama server: {e}",
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from Ollama: {e.response.status_code} - {e.response.text}")
            return {
                "status": "error",
                "url": self.base_url,
                "is_ngrok": self._is_ngrok,
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
        except Exception as e:
            logger.error(f"Error checking Ollama status: {e}")
            return {
                "status": "error",
                "url": self.base_url,
                "is_ngrok": self._is_ngrok,
                "error": str(e),
            }


# Global LLM service instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the global LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

