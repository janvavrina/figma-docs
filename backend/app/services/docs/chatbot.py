"""Simple chatbot for documentation queries."""

import logging
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.models.doc_models import ChatMessage, ChatResponse
from app.services.llm import LLMService, get_llm_service

logger = logging.getLogger(__name__)


class DocumentationChatbot:
    """Simple chatbot for querying documentation."""
    
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        docs_dir: Optional[str] = None,
    ):
        """Initialize the chatbot.
        
        Args:
            llm_service: LLMService instance.
            docs_dir: Directory containing documentation files.
        """
        self.llm_service = llm_service or get_llm_service()
        self.docs_dir = Path(docs_dir or settings.documentation.output_dir) / "markdown"
    
    async def chat(
        self,
        message: str,
        file_key: Optional[str] = None,
        history: list[ChatMessage] = None,
    ) -> ChatResponse:
        """Process a chat message and return a response.
        
        Args:
            message: User's question.
            file_key: Optional file key to limit context.
            history: Optional conversation history.
            
        Returns:
            ChatResponse with answer and sources.
        """
        # Load documentation as context
        context, sources = self._load_documentation(file_key)
        
        # Convert history to dict format
        history_dicts = []
        if history:
            history_dicts = [{"role": m.role, "content": m.content} for m in history]
        
        # Generate response
        response = await self.llm_service.chat(
            message=message,
            context=context,
            history=history_dicts,
        )
        
        return ChatResponse(
            message=response,
            sources=sources,
            figma_references=[],
        )
    
    def _load_documentation(
        self,
        file_key: Optional[str] = None,
    ) -> tuple[str, list[str]]:
        """Load documentation files as context.
        
        Args:
            file_key: Optional file key to filter.
            
        Returns:
            Tuple of (context string, source list).
        """
        context_parts = []
        sources = []
        
        try:
            for md_file in self.docs_dir.glob("*.md"):
                # Check file key filter
                if file_key:
                    meta_file = md_file.with_name(md_file.stem + "_meta.json")
                    if meta_file.exists():
                        import json
                        with open(meta_file) as f:
                            meta = json.load(f)
                        if meta.get("figma_file_key") != file_key:
                            continue
                
                content = md_file.read_text()
                # Truncate to avoid token limits
                if len(content) > 6000:
                    content = content[:6000] + "\n... (truncated)"
                
                context_parts.append(f"# {md_file.stem}\n\n{content}")
                sources.append(md_file.stem)
                
        except Exception as e:
            logger.error(f"Error loading documentation: {e}")
        
        return "\n\n---\n\n".join(context_parts), sources


# Global chatbot instance
_chatbot: Optional[DocumentationChatbot] = None


def get_chatbot() -> DocumentationChatbot:
    """Get or create the global chatbot instance."""
    global _chatbot
    if _chatbot is None:
        _chatbot = DocumentationChatbot()
    return _chatbot
