"""RAG-based chatbot for documentation queries."""

import logging
from pathlib import Path
from typing import Any, Optional

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.models.doc_models import ChatMessage, ChatResponse
from app.services.llm import LLMService, get_llm_service

logger = logging.getLogger(__name__)

# Headers for ngrok tunnel (skip browser warning)
NGROK_HEADERS = {
    "ngrok-skip-browser-warning": "true",
}


class DocumentationChatbot:
    """RAG-based chatbot for querying documentation."""
    
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
        
        self._embeddings: Optional[OllamaEmbeddings] = None
        self._vectorstore: Optional[Chroma] = None
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
        )
        
        # Check if using ngrok URL
        self._is_ngrok = "ngrok" in settings.llm.ollama_base_url.lower()
    
    def _get_headers(self) -> dict[str, str]:
        """Get headers for Ollama requests (includes ngrok headers if needed)."""
        if self._is_ngrok:
            return NGROK_HEADERS.copy()
        return {}
    
    def _get_embeddings(self) -> OllamaEmbeddings:
        """Get or create embeddings model."""
        if self._embeddings is None:
            self._embeddings = OllamaEmbeddings(
                model=settings.vector_db.embedding_model,
                base_url=settings.llm.ollama_base_url,
                headers=self._get_headers(),
            )
        return self._embeddings
    
    def _get_vectorstore(self) -> Chroma:
        """Get or create vector store."""
        if self._vectorstore is None:
            persist_dir = str(self.docs_dir.parent / "chroma_db")
            
            self._vectorstore = Chroma(
                collection_name=settings.vector_db.collection_name,
                embedding_function=self._get_embeddings(),
                persist_directory=persist_dir,
            )
        return self._vectorstore
    
    async def index_documentation(self, file_key: Optional[str] = None) -> int:
        """Index documentation files into the vector store.
        
        Args:
            file_key: Optional specific file key to index. If None, indexes all.
            
        Returns:
            Number of chunks indexed.
        """
        vectorstore = self._get_vectorstore()
        documents = []
        
        # Find markdown files
        if file_key:
            # Find file by key
            for meta_file in self.docs_dir.glob("*_meta.json"):
                import json
                with open(meta_file) as f:
                    meta = json.load(f)
                if meta.get("figma_file_key") == file_key:
                    md_file = meta_file.with_name(meta_file.stem.replace("_meta", "") + ".md")
                    if md_file.exists():
                        documents.append((md_file, meta))
                    break
        else:
            # Index all files
            for md_file in self.docs_dir.glob("*.md"):
                meta_file = md_file.with_name(md_file.stem + "_meta.json")
                meta = {}
                if meta_file.exists():
                    import json
                    with open(meta_file) as f:
                        meta = json.load(f)
                documents.append((md_file, meta))
        
        total_chunks = 0
        
        for md_file, meta in documents:
            content = md_file.read_text()
            chunks = self._text_splitter.split_text(content)
            
            # Create documents with metadata
            texts = []
            metadatas = []
            
            for i, chunk in enumerate(chunks):
                texts.append(chunk)
                metadatas.append({
                    "source": str(md_file),
                    "file_key": meta.get("figma_file_key", ""),
                    "file_name": meta.get("figma_file_name", ""),
                    "chunk_index": i,
                })
            
            if texts:
                vectorstore.add_texts(texts=texts, metadatas=metadatas)
                total_chunks += len(texts)
                logger.info(f"Indexed {len(texts)} chunks from {md_file.name}")
        
        return total_chunks
    
    async def chat(
        self,
        message: str,
        file_key: Optional[str] = None,
        history: list[ChatMessage] = None,
    ) -> ChatResponse:
        """Process a chat message and return a response.
        
        Args:
            message: User's question.
            file_key: Optional file key to limit search scope.
            history: Optional conversation history.
            
        Returns:
            ChatResponse with answer and sources.
        """
        # Retrieve relevant context
        context, sources = await self._retrieve_context(message, file_key)
        
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
    
    async def _retrieve_context(
        self,
        query: str,
        file_key: Optional[str] = None,
        k: int = 4,
    ) -> tuple[str, list[str]]:
        """Retrieve relevant context from vector store.
        
        Args:
            query: Search query.
            file_key: Optional file key filter.
            k: Number of results to retrieve.
            
        Returns:
            Tuple of (context string, source list).
        """
        vectorstore = self._get_vectorstore()
        
        # Build filter
        filter_dict = None
        if file_key:
            filter_dict = {"file_key": file_key}
        
        # Search
        try:
            results = vectorstore.similarity_search(
                query,
                k=k,
                filter=filter_dict,
            )
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return "", []
        
        if not results:
            return "", []
        
        # Build context
        context_parts = []
        sources = set()
        
        for doc in results:
            context_parts.append(doc.page_content)
            if doc.metadata.get("file_name"):
                sources.add(doc.metadata["file_name"])
        
        context = "\n\n---\n\n".join(context_parts)
        
        return context, list(sources)
    
    async def clear_index(self) -> None:
        """Clear all indexed documents."""
        vectorstore = self._get_vectorstore()
        
        # Delete collection and recreate
        try:
            vectorstore.delete_collection()
            self._vectorstore = None
            logger.info("Cleared vector store index")
        except Exception as e:
            logger.error(f"Error clearing index: {e}")


# Global chatbot instance
_chatbot: Optional[DocumentationChatbot] = None


def get_chatbot() -> DocumentationChatbot:
    """Get or create the global chatbot instance."""
    global _chatbot
    if _chatbot is None:
        _chatbot = DocumentationChatbot()
    return _chatbot

