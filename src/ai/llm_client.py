"""
Клиент для работы с LLM (OpenAI/Anthropic).
Унифицированный интерфейс для вызова AI моделей.
"""

from typing import List, Dict, Any, Optional, AsyncGenerator
import json

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import tiktoken

from ..utils.logger import AgentLogger
from ..utils.config import settings, get_model_config
from .tools import BROWSER_TOOLS


logger = AgentLogger(__name__)


class LLMClient:
    """
    Универсальный клиент для работы с LLM.
    Поддерживает OpenAI и Anthropic с единым интерфейсом.
    """
    
    def __init__(self, model_type: str = "primary"):
        self.model_config = get_model_config(model_type)
        self.provider = self.model_config.provider
        self.model = self.model_config.model
        
        # Инициализация клиентов
        if self.provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY не установлен в .env")
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        elif self.provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY не установлен в .env")
            self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            # Anthropic использует примерно те же токены
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        else:
            raise ValueError(f"Неподдерживаемый провайдер: {self.provider}")
        
        logger.info(f"🤖 LLM клиент инициализирован: {self.provider}/{self.model}")
    
    def count_tokens(self, text: str) -> int:
        """Подсчитать количество токенов в тексте."""
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.debug(f"Ошибка подсчета токенов: {e}")
            # Приблизительная оценка: 1 токен ≈ 4 символа
            return len(text) // 4
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Запрос к LLM с поддержкой function calling.
        
        Args:
            messages: История сообщений
            tools: Список доступных инструментов
            temperature: Температура генерации
            max_tokens: Максимум токенов в ответе
            
        Returns:
            Ответ от LLM
        """
        temp = temperature if temperature is not None else self.model_config.temperature
        max_tok = max_tokens if max_tokens is not None else self.model_config.max_tokens
        
        try:
            if self.provider == "openai":
                response = await self._openai_completion(messages, tools, temp, max_tok)
            elif self.provider == "anthropic":
                response = await self._anthropic_completion(messages, tools, temp, max_tok)
            else:
                raise ValueError(f"Неизвестный провайдер: {self.provider}")
            
            # Подсчет токенов
            if response:
                usage = response.get("usage", {})
                total_tokens = usage.get("total_tokens", 0)
                logger.token_usage(total_tokens)
            
            return response
        
        except Exception as e:
            logger.error(f"Ошибка вызова LLM: {e}")
            raise
    
    async def _openai_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Вызов OpenAI API."""
        params: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        
        response = await self.client.chat.completions.create(**params)
        
        # Преобразование в унифицированный формат
        message = response.choices[0].message
        
        result = {
            "content": message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
        
        # Если есть tool calls
        if hasattr(message, "tool_calls") and message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments)
                    }
                }
                for tc in message.tool_calls
            ]
        
        return result
    
    async def _anthropic_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Вызов Anthropic API."""
        # Anthropic требует отдельно system message
        system_msg = None
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append(msg)
        
        params: Dict[str, Any] = {
            "model": self.model,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if system_msg:
            params["system"] = system_msg
        
        if tools:
            # Конвертация OpenAI формата в Anthropic
            anthropic_tools = [
                {
                    "name": tool["function"]["name"],
                    "description": tool["function"]["description"],
                    "input_schema": tool["function"]["parameters"]
                }
                for tool in tools
            ]
            params["tools"] = anthropic_tools
        
        response = await self.client.messages.create(**params)
        
        # Преобразование в унифицированный формат
        content = ""
        tool_calls = []
        
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "function": {
                        "name": block.name,
                        "arguments": block.input
                    }
                })
        
        result = {
            "content": content,
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        }
        
        if tool_calls:
            result["tool_calls"] = tool_calls
        
        return result
    
    async def simple_completion(self, prompt: str) -> str:
        """
        Простой запрос без tools (для summarization и т.д.).
        
        Args:
            prompt: Промпт
            
        Returns:
            Текстовый ответ
        """
        messages = [{"role": "user", "content": prompt}]
        response = await self.chat_completion(messages, tools=None)
        return response.get("content", "")
