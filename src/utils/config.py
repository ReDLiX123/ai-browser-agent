"""
Модуль конфигурации приложения.
Загружает настройки из YAML файлов и переменных окружения.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# Загрузка переменных окружения
load_dotenv()

# Базовая директория проекта
BASE_DIR = Path(__file__).parent.parent.parent


class BrowserConfig(BaseModel):
    """Конфигурация браузера."""
    type: str = "chromium"
    headless: bool = False
    viewport: Dict[str, int] = {"width": 1280, "height": 720}
    user_agent: str = ""
    timeout: int = 30000
    slow_mo: int = 0
    devtools: bool = False
    args: list[str] = []  # Дополнительные аргументы запуска браузера


class PersistentContextConfig(BaseModel):
    """Конфигурация persistent context."""
    enabled: bool = True
    data_dir: str = "./browser_data"


class PageWaitConfig(BaseModel):
    """Конфигурация ожидания загрузки страниц."""
    network_idle_timeout: int = 3000
    dom_content_loaded: bool = True


class ModelConfig(BaseModel):
    """Конфигурация AI модели."""
    provider: str
    model: str
    temperature: float = 0.1
    max_tokens: int = 4000


class ContextConfig(BaseModel):
    """Конфигурация управления контекстом."""
    max_tokens: int = 16000  # Увеличено с 6000 для поддержки 100 элементов
    sliding_window_size: int = 25  # Увеличено с 10 для сохранения больше истории
    compression_threshold: float = 0.7


class AgentConfig(BaseModel):
    """Конфигурация агента."""
    max_steps: int = 50
    timeout: int = 300
    retry_attempts: int = 3


class SecurityConfig(BaseModel):
    """Конфигурация security layer."""
    enabled: bool = True
    destructive_patterns: list[str] = []


class Settings(BaseSettings):
    """Главный класс настроек приложения."""
    
    # API Keys
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    
    # Model selection
    primary_model: str = Field(default="gpt-4o", alias="PRIMARY_MODEL")
    fallback_model: str = Field(default="claude-3-5-sonnet-20241022", alias="FALLBACK_MODEL")
    summarization_model: str = Field(default="gpt-4o-mini", alias="SUMMARIZATION_MODEL")
    
    # Browser
    browser_type: str = Field(default="chromium", alias="BROWSER_TYPE")
    headless: bool = Field(default=False, alias="HEADLESS")
    browser_data_dir: str = Field(default="./browser_data", alias="BROWSER_DATA_DIR")
    
    # Agent
    max_context_tokens: int = Field(default=6000, alias="MAX_CONTEXT_TOKENS")
    max_task_steps: int = Field(default=50, alias="MAX_TASK_STEPS")
    enable_security_layer: bool = Field(default=True, alias="ENABLE_SECURITY_LAYER")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="logs/agent.log", alias="LOG_FILE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def load_yaml_config(config_name: str) -> Dict[str, Any]:
    """
    Загрузить YAML конфигурацию.
    
    Args:
        config_name: Имя конфигурационного файла (без расширения)
        
    Returns:
        Словарь с конфигурацией
    """
    config_path = BASE_DIR / "config" / f"{config_name}.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Конфигурационный файл не найден: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# Глобальный экземпляр настроек
settings = Settings()

# Загрузка YAML конфигураций
try:
    browser_config_dict = load_yaml_config("browser")
    browser_config = BrowserConfig(**browser_config_dict.get("browser", {}))
    persistent_context_config = PersistentContextConfig(**browser_config_dict.get("persistent_context", {}))
    page_wait_config = PageWaitConfig(**browser_config_dict.get("page_wait", {}))
except FileNotFoundError:
    # Использовать значения по умолчанию
    browser_config = BrowserConfig()
    persistent_context_config = PersistentContextConfig()
    page_wait_config = PageWaitConfig()

try:
    ai_config_dict = load_yaml_config("ai_models")
    models_config = {
        "primary": ModelConfig(**ai_config_dict["models"]["primary"]),
        "fallback": ModelConfig(**ai_config_dict["models"]["fallback"]),
        "summarization": ModelConfig(**ai_config_dict["models"]["summarization"]),
    }
    context_config = ContextConfig(**ai_config_dict.get("context", {}))
    agent_config = AgentConfig(**ai_config_dict.get("agent", {}))
    security_config = SecurityConfig(**ai_config_dict.get("security", {}))
except (FileNotFoundError, KeyError):
    # Использовать значения по умолчанию
    models_config = {
        "primary": ModelConfig(provider="openai", model="gpt-4o"),
        "fallback": ModelConfig(provider="anthropic", model="claude-3-5-sonnet-20241022"),
        "summarization": ModelConfig(provider="openai", model="gpt-4o-mini"),
    }
    context_config = ContextConfig()
    agent_config = AgentConfig()
    security_config = SecurityConfig()


def get_model_config(model_type: str = "primary") -> ModelConfig:
    """Получить конфигурацию модели по типу."""
    return models_config.get(model_type, models_config["primary"])
