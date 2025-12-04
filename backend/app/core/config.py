"""Configuration management for Figma Documentation Generator."""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class LLMGenerationConfig(BaseModel):
    """LLM generation parameters."""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9


class LLMModelsConfig(BaseModel):
    """Model assignments for different tasks."""
    documentation: str = "gemma3:27b"
    chatbot: str = "granite3.1-dense:8b"
    code_analysis: str = "Phi-4-mini-instruct:latest"
    app_analysis: str = "gemma3:27b"


class LLMConfig(BaseModel):
    """LLM configuration."""
    default_model: str = "gemma3:27b"
    models: LLMModelsConfig = Field(default_factory=LLMModelsConfig)
    ollama_base_url: str = "http://localhost:11434"
    generation: LLMGenerationConfig = Field(default_factory=LLMGenerationConfig)


class WatchedFileConfig(BaseModel):
    """Configuration for a watched Figma file."""
    file_key: str
    name: str


class FigmaConfig(BaseModel):
    """Figma API configuration."""
    api_token: str = ""
    api_base_url: str = "https://api.figma.com"
    polling_interval_minutes: int = 5
    watched_files: list[WatchedFileConfig] = Field(default_factory=list)


class DocumentationFormatsConfig(BaseModel):
    """Documentation format settings."""
    formats: list[str] = Field(default_factory=lambda: ["markdown", "html"])


class DocumentationTemplatesConfig(BaseModel):
    """Documentation template settings."""
    include_components: bool = True
    include_styles: bool = True
    include_interactions: bool = True
    include_tokens: bool = True


class DocumentationConfig(BaseModel):
    """Documentation generation configuration."""
    output_dir: str = "./docs"
    default_type: str = "both"
    formats: list[str] = Field(default_factory=lambda: ["markdown", "html"])
    templates: DocumentationTemplatesConfig = Field(default_factory=DocumentationTemplatesConfig)


class CodeAgentConfig(BaseModel):
    """Code agent configuration."""
    include_patterns: list[str] = Field(default_factory=lambda: [
        "**/*.py", "**/*.js", "**/*.ts", "**/*.tsx",
        "**/*.vue", "**/*.jsx", "**/*.css", "**/*.scss", "**/*.html"
    ])
    exclude_patterns: list[str] = Field(default_factory=lambda: [
        "**/node_modules/**", "**/__pycache__/**", "**/.git/**",
        "**/dist/**", "**/build/**", "**/*.min.js", "**/*.min.css"
    ])
    max_file_size_kb: int = 500


class AppAgentConfig(BaseModel):
    """App agent (computer use) configuration."""
    max_pages: int = 20
    max_depth: int = 3
    take_screenshots: bool = True
    screenshot_dir: str = "./docs/screenshots"
    action_delay: float = 1.0


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "./logs/figma_docs.log"


class ServerConfig(BaseModel):
    """Server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: [
        "http://localhost:3000", "http://127.0.0.1:3000"
    ])


class Settings(BaseSettings):
    """Main application settings."""
    
    # LLM settings
    llm: LLMConfig = Field(default_factory=LLMConfig)
    
    # Figma settings
    figma: FigmaConfig = Field(default_factory=FigmaConfig)
    
    # Documentation settings
    documentation: DocumentationConfig = Field(default_factory=DocumentationConfig)
    
    # Code agent settings
    code_agent: CodeAgentConfig = Field(default_factory=CodeAgentConfig)
    
    # App agent settings
    app_agent: AppAgentConfig = Field(default_factory=AppAgentConfig)
    
    # Logging settings
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    # Server settings
    server: ServerConfig = Field(default_factory=ServerConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "Settings":
        """Load settings from a YAML configuration file."""
        config_path = Path(config_path)
        
        if not config_path.exists():
            # Return default settings if config doesn't exist
            return cls()
        
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
        
        # Process environment variable substitutions
        config_data = cls._process_env_vars(config_data)
        
        return cls(**config_data)
    
    @classmethod
    def _process_env_vars(cls, data: Any) -> Any:
        """Recursively process environment variable substitutions in config."""
        if isinstance(data, dict):
            return {k: cls._process_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls._process_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Check for ${VAR_NAME} pattern with optional default ${VAR_NAME:-default}
            if data.startswith("${") and data.endswith("}"):
                inner = data[2:-1]
                if ":-" in inner:
                    var_name, default = inner.split(":-", 1)
                    return os.environ.get(var_name, default)
                else:
                    return os.environ.get(inner, "")
            return data
        return data
    
    def get_model_for_task(self, task: str) -> str:
        """Get the configured model for a specific task."""
        models = self.llm.models
        model_map = {
            "documentation": models.documentation,
            "chatbot": models.chatbot,
            "code_analysis": models.code_analysis,
            "app_analysis": models.app_analysis,
        }
        return model_map.get(task, self.llm.default_model)


def load_settings(config_path: Optional[str | Path] = None) -> Settings:
    """Load settings from config file or use defaults."""
    if config_path is None:
        # Try to find config.yaml in common locations
        possible_paths = [
            Path("config.yaml"),
            Path("../config.yaml"),
            Path(__file__).parent.parent.parent.parent / "config.yaml",
        ]
        for path in possible_paths:
            if path.exists():
                config_path = path
                break
    
    if config_path:
        settings_obj = Settings.from_yaml(config_path)
    else:
        settings_obj = Settings()
    
    # Override with environment variables if set
    if os.environ.get("OLLAMA_BASE_URL"):
        settings_obj.llm.ollama_base_url = os.environ["OLLAMA_BASE_URL"]
    
    if os.environ.get("FIGMA_API_TOKEN"):
        settings_obj.figma.api_token = os.environ["FIGMA_API_TOKEN"]
    
    return settings_obj


# Global settings instance
settings = load_settings()

