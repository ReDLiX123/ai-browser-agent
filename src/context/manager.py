"""
Управление контекстом для LLM.
Sliding window, подсчет токенов, сжатие истории.
"""

from typing import List, Dict, Any
from collections import deque

from ..utils.logger import AgentLogger
from ..utils.config import context_config
from ..ai.llm_client import LLMClient


logger = AgentLogger(__name__)


class ContextManager:
    """
    Менеджер контекста для управления историей диалога и токенами.
    """
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.max_tokens = context_config.max_tokens
        self.sliding_window_size = context_config.sliding_window_size
        
        # История сообщений (deque с ограничением размера)
        self.message_history: deque = deque(maxlen=self.sliding_window_size * 2)
        
        # Системный промпт (не считается в sliding window)
        self.system_message: Dict[str, str] = {"role": "system", "content": ""}
    
    def set_system_message(self, content: str) -> None:
        """Установить системное сообщение."""
        self.system_message = {"role": "system", "content": content}
    
    def add_user_message(self, content: str) -> None:
        """Добавить сообщение пользователя."""
        self.message_history.append({
            "role": "user",
            "content": content
        })
        logger.debug(f"Добавлено user message, история: {len(self.message_history)}")
    
    def add_assistant_message(self, content: str) -> None:
        """Добавить сообщение ассистента."""
        self.message_history.append({
            "role": "assistant",
            "content": content
        })
        logger.debug(f"Добавлено assistant message, история: {len(self.message_history)}")
    
    def add_tool_result(self, tool_name: str, result: str) -> None:
        """Добавить результат выполнения tool."""
        self.message_history.append({
            "role": "user",
            "content": f"TOOL RESULT [{tool_name}]: {result}"
        })
    
    def get_messages(self, include_system: bool = True) -> List[Dict[str, str]]:
        """
        Получить сообщения для отправки в LLM.
        
        Args:
            include_system: Включать ли системное сообщение
            
        Returns:
            Список сообщений
        """
        messages = []
        
        if include_system and self.system_message["content"]:
            messages.append(self.system_message)
        
        messages.extend(list(self.message_history))
        
        # Проверка токенов
        total_tokens = self._count_messages_tokens(messages)
        
        # Если превышен лимит, сжимаем
        if total_tokens > self.max_tokens:
            logger.warning(f"Превышен лимит токенов: {total_tokens}/{self.max_tokens}. Сжатие...")
            messages = self._compress_messages(messages)
        
        return messages
    
    def _count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Подсчитать общее количество токенов в сообщениях."""
        total = 0
        for msg in messages:
            total += self.llm_client.count_tokens(msg["content"])
        return total
    
    def _compress_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Сжать сообщения чтобы уложиться в лимит токенов.
        
        Стратегия:
        1. Оставляем system message
        2. Оставляем последние N сообщений (sliding window)
        3. Если все еще много - сокращаем text content
        """
        compressed = []
        
        # System message всегда остается
        system_msg = None
        other_msgs = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg
            else:
                other_msgs.append(msg)
        
        # Берем последние сообщения
        recent_msgs = other_msgs[-self.sliding_window_size:]
        
        if system_msg:
            compressed.append(system_msg)
        compressed.extend(recent_msgs)
        
        # Проверяем токены снова
        total_tokens = self._count_messages_tokens(compressed)
        
        # Если все еще много - сокращаем контент каждого сообщения (НО НЕ TOOL RESULT)
        if total_tokens > self.max_tokens:
            for msg in compressed:
                if msg["role"] != "system":
                    content = msg["content"]
                    # НЕ обрезаем TOOL RESULT - они содержат критически важную информацию
                    if not content.startswith("TOOL RESULT"):
                        # Сокращаем только очень длинные сообщения
                        if len(content) > 5000:
                            msg["content"] = content[:4500] + "... [truncated]"
        
        logger.info(f"Контекст сжат: {len(messages)} -> {len(compressed)} сообщений")
        return compressed
    
    def clear_history(self) -> None:
        """Очистить историю сообщений."""
        self.message_history.clear()
        logger.info("История сообщений очищена")
    
    def get_context_info(self) -> Dict[str, Any]:
        """Получить информацию о текущем контексте."""
        messages = self.get_messages()
        return {
            "total_messages": len(messages),
            "total_tokens": self._count_messages_tokens(messages),
            "max_tokens": self.max_tokens,
            "utilization": self._count_messages_tokens(messages) / self.max_tokens
        }
