"""
Модуль логирования.
Настраивает систему логирования для всего приложения.
"""

import logging
import logging.config
import yaml
from pathlib import Path
from typing import Optional
from rich.logging import RichHandler
from rich.console import Console


# Создание директории для логов
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

console = Console()


def setup_logging(config_path: Optional[Path] = None, log_level: str = "INFO") -> None:
    """
    Настроить систему логирования.
    
    Args:
        config_path: Путь к YAML конфигурации логирования
        log_level: Уровень логирования по умолчанию
    """
    if config_path and config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logging.config.dictConfig(config)
            return
        except Exception as e:
            print(f"Ошибка загрузки конфигурации логирования: {e}")
    
    # Базовая конфигурация с Rich
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                tracebacks_show_locals=True,
            )
        ]
    )


def get_logger(name: str) -> logging.Logger:
    """
    Получить logger с заданным именем.
    
    Args:
        name: Имя logger'а (обычно __name__)
        
    Returns:
        Экземпляр Logger
    """
    return logging.getLogger(name)


class AgentLogger:
    """
    Специализированный logger для агента с дополнительной функциональностью.
    """
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
        self._task_id: Optional[str] = None
    
    def set_task_id(self, task_id: str) -> None:
        """Установить ID текущей задачи для логирования."""
        self._task_id = task_id
    
    def _format_message(self, message: str) -> str:
        """Форматировать сообщение с добавлением task_id."""
        if self._task_id:
            return f"[Task: {self._task_id}] {message}"
        return message
    
    def debug(self, message: str, **kwargs) -> None:
        """Debug level log."""
        self.logger.debug(self._format_message(message), **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Info level log."""
        self.logger.info(self._format_message(message), **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Warning level log."""
        self.logger.warning(self._format_message(message), **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Error level log."""
        self.logger.error(self._format_message(message), **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Critical level log."""
        self.logger.critical(self._format_message(message), **kwargs)
    
    def action(self, action_type: str, details: str) -> None:
        """Логировать действие агента."""
        self.debug(f"ACTION: {action_type} - {details}")
    
    def thought(self, thought: str) -> None:
        """Логировать размышление агента (ReAct pattern)."""
        self.debug(f"THOUGHT: {thought}")
    
    def observation(self, observation: str) -> None:
        """Логировать наблюдение агента (ReAct pattern)."""
        self.debug(f"OBSERVATION: {observation}")
    
    def step(self, step_number: int, total_steps: int, description: str) -> None:
        """Логировать шаг выполнения задачи."""
        self.debug(f"STEP {step_number}/{total_steps}: {description}")
    
    def token_usage(self, tokens: int, cost: float = 0.0) -> None:
        """Логировать использование токенов."""
        self.debug(f"TOKENS: {tokens} (cost: ${cost:.4f})")
    
    def page_transition(self, from_url: str, to_url: str) -> None:
        """Логировать переход между страницами."""
        self.debug(f"PAGE TRANSITION: {from_url} -> {to_url}")
    
    def security_alert(self, action: str, requires_confirmation: bool = True) -> None:
        """Логировать security alert."""
        prefix = "[!]" if requires_confirmation else "[*]"
        self.warning(f"{prefix} SECURITY: {action} {'(requires confirmation)' if requires_confirmation else ''}")


# Инициализация логирования при импорте модуля
try:
    config_path = Path(__file__).parent.parent.parent / "config" / "logging.yaml"
    if config_path.exists():
        setup_logging(config_path)
    else:
        setup_logging(log_level="INFO")
except Exception as e:
    setup_logging(log_level="INFO")
    print(f"Предупреждение: не удалось загрузить конфигурацию логирования: {e}")
