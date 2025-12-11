"""
Orchestrator Agent - главный координирующий агент.
Управляет выполнением задач и координацией sub-агентов.
"""

import json
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..browser.automation import BrowserAutomation
from ..ai.llm_client import LLMClient
from ..ai.prompt_templates import PromptTemplates, ConversationFormatter
from ..ai.tools import BROWSER_TOOLS
from ..context.manager import ContextManager
from ..context.compression import ContentCompressor
from .browser_agent import BrowserAgent
from .security import SecurityAgent
from ..utils.logger import AgentLogger
from ..utils.config import agent_config


logger = AgentLogger(__name__)


@dataclass
class TaskResult:
    """Результат выполнения задачи."""
    success: bool
    result: str
    steps_taken: int
    error: Optional[str] = None


class OrchestratorAgent:
    """
    Главный агент-оркестратор.
    Координирует работу всех sub-агентов и выполняет задачи.
    """
    
    def __init__(self, browser: BrowserAutomation):
        self.task_id = str(uuid.uuid4())[:8]
        logger.set_task_id(self.task_id)
        
        # Компоненты
        self.browser = browser
        self.llm_client = LLMClient(model_type="primary")
        self.context_manager = ContextManager(self.llm_client)
        self.browser_agent = BrowserAgent(browser)
        self.security_agent = SecurityAgent()
        
        # Конфигурация
        self.max_steps = agent_config.max_steps
        self.current_step = 0
        
        # Флаг завершения задачи
        self.task_completed = False
        self.task_result: Optional[TaskResult] = None
        
        logger.info(f"Orchestrator инициализирован (Task ID: {self.task_id})")
    
    async def execute_task(self, task: str) -> TaskResult:
        """
        Выполнить задачу.
        
        Args:
            task: Текстовая задача от пользователя
            
        Returns:
            Результат выполнения
        """
        logger.info(f"Новая задача: {task}")
        
        # Сброс состояния для новой задачи
        self.task_completed = False
        self.task_result = None
        self.current_step = 0
        
        # Очистка истории контекста (но оставляем новый task ID)
        self.task_id = str(uuid.uuid4())[:8]
        logger.set_task_id(self.task_id)
        
        # Инициализация контекста
        system_prompt = PromptTemplates.system_prompt()
        self.context_manager.set_system_message(system_prompt)
        
        # Добавляем задачу пользователя
        user_message = PromptTemplates.user_prompt_template(task)
        self.context_manager.add_user_message(user_message)
        
        # Главный цикл выполнения
        while not self.task_completed and self.current_step < self.max_steps:
            self.current_step += 1
            logger.step(self.current_step, self.max_steps, "Выполнение шага")
            
            try:
                # Получаем информацию о текущей странице
                page_info = await self.browser_agent.get_page_info()
                
                # Сжимаем информацию
                compressed_page_info = ContentCompressor.extract_essential_info(page_info)
                
                # Формируем промпт для планирования
                planning_prompt = PromptTemplates.planning_prompt(task, compressed_page_info)
                self.context_manager.add_user_message(planning_prompt)
                
                # Получаем решение от LLM
                messages = self.context_manager.get_messages()
                response = await self.llm_client.chat_completion(
                    messages=messages,
                    tools=BROWSER_TOOLS
                )
                
                # Обрабатываем ответ
                await self._process_llm_response(response)
                
            except Exception as e:
                logger.error(f"Ошибка на шаге {self.current_step}: {e}")
                
                # Попытка восстановления
                recovery_result = await self._attempt_recovery(str(e))
                
                if not recovery_result:
                    # Не удалось восстановиться
                    return TaskResult(
                        success=False,
                        result="",
                        steps_taken=self.current_step,
                        error=str(e)
                    )
        
        # Проверка завершения
        if self.task_completed and self.task_result:
            return self.task_result
        elif self.current_step >= self.max_steps:
            logger.warning(f"Достигнут лимит шагов: {self.max_steps}")
            return TaskResult(
                success=False,
                result="",
                steps_taken=self.current_step,
                error="Превышен лимит шагов"
            )
        else:
            return TaskResult(
                success=False,
                result="",
                steps_taken=self.current_step,
                error="Неизвестная ошибка"
            )
    
    async def _process_llm_response(self, response: Dict[str, Any]) -> None:
        """Обработать ответ от LLM."""
        # Если есть текстовый контент - логируем как размышление
        if response.get("content"):
            logger.thought(response["content"])
            self.context_manager.add_assistant_message(response["content"])
        
        # Если есть tool calls - выполняем
        tool_calls = response.get("tool_calls", [])
        
        if not tool_calls:
            logger.warning("LLM не вызвал никаких инструментов")
            return
        
        for tool_call in tool_calls:
            await self._execute_tool_call(tool_call)
    
    async def _execute_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Выполнить вызов инструмента."""
        tool_name = tool_call["function"]["name"]
        tool_args = tool_call["function"]["arguments"]
        
        logger.action(tool_name.upper(), str(tool_args))
        
        # Проверка безопасности
        if self.security_agent.enabled:
            security_check = await self.security_agent.check_action(tool_name, tool_args)
            
            if not security_check["safe"]:
                if security_check["requires_confirmation"]:
                    # Требуется подтверждение пользователя
                    error_msg = f"Действие требует подтверждения: {security_check['reason']}"
                    logger.security_alert(error_msg)
                    result = {"success": False, "error": error_msg, "requires_user_confirmation": True}
                else:
                    result = {"success": False, "error": security_check["reason"]}
                
                self.context_manager.add_tool_result(tool_name, json.dumps(result))
                return
        
        # Выполнение инструмента
        result = await self._call_tool(tool_name, tool_args)
        
        # Добавляем результат в контекст
        logger.observation(str(result))
        self.context_manager.add_tool_result(tool_name, json.dumps(result))
    
    async def _call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Вызвать конкретный инструмент."""
        try:
            # Маппинг инструментов
            if tool_name == "click":
                return await self.browser_agent.click(args["selector"], args.get("reason", ""))
            
            elif tool_name == "type_text":
                return await self.browser_agent.type_text(
                    args["selector"], args["text"], args.get("reason", "")
                )
            
            elif tool_name == "navigate":
                return await self.browser_agent.navigate(args["url"], args.get("reason", ""))
            
            elif tool_name == "scroll":
                return await self.browser_agent.scroll(args["direction"], args.get("amount", "medium"))
            
            elif tool_name == "go_back":
                return await self.browser_agent.go_back()
            
            elif tool_name == "extract_text":
                return await self.browser_agent.extract_text(args["selector"])
            
            elif tool_name == "wait":
                return await self.browser_agent.wait(args["seconds"], args.get("reason", ""))
            
            elif tool_name == "press_key":
                return await self.browser_agent.press_key(args["key"], args.get("reason", ""))
            
            elif tool_name == "task_complete":
                # Задача завершена
                self.task_completed = True
                self.task_result = TaskResult(
                    success=args.get("success", True),
                    result=args.get("result", ""),
                    steps_taken=self.current_step
                )
                logger.info(f"Задача завершена: {args.get('result', '')}")
                return {"success": True, "message": "Задача завершена"}
            
            elif tool_name == "ask_user":
                # Запрос к пользователю
                question = args.get("question", "")
                logger.info(f"Вопрос пользователю: {question}")
                return {
                    "success": False,
                    "message": "Требуется ответ пользователя",
                    "question": question,
                    "user_input_required": True
                }
            
            else:
                logger.error(f"Неизвестный инструмент: {tool_name}")
                return {"success": False, "error": f"Неизвестный инструмент: {tool_name}"}
        
        except Exception as e:
            logger.error(f"Ошибка выполнения {tool_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _attempt_recovery(self, error: str) -> bool:
        """
        Попытка восстановления после ошибки.
        
        Returns:
            True если восстановление успешно
        """
        logger.warning(f"Попытка восстановления после ошибки: {error}")
        
        try:
            # Формируем промпт для восстановления
            recovery_prompt = PromptTemplates.error_recovery_prompt(
                error=error,
                previous_action=f"Шаг {self.current_step}"
            )
            
            self.context_manager.add_user_message(recovery_prompt)
            
            # Даем агенту шанс исправиться
            return True
        
        except Exception as e:
            logger.error(f"Ошибка восстановления: {e}")
            return False
