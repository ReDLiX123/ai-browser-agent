"""
Security Agent - проверка безопасности действий.
"""

from typing import Dict, Any, List

from ..utils.logger import AgentLogger
from ..utils.config import security_config


logger = AgentLogger(__name__)


class SecurityAgent:
    """
    Security layer для контроля деструктивных действий.
    """
    
    def __init__(self):
        self.enabled = security_config.enabled
        self.destructive_patterns = security_config.destructive_patterns
        self.user_confirmation_callback = None
    
    def set_confirmation_callback(self, callback):
        """Установить callback для запроса подтверждения у пользователя."""
        self.user_confirmation_callback = callback
    
    async def check_action(self, action_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Проверить безопасность действия.
        
        Args:
            action_name: Название действия
            parameters: Параметры действия
            
        Returns:
            Результат проверки {"safe": bool, "reason": str, "requires_confirmation": bool}
        """
        if not self.enabled:
            return {
                "safe": True,
                "reason": "Security layer отключен",
                "requires_confirmation": False
            }
        
        # Проверка на деструктивные паттерны
        is_destructive, reason = self._is_destructive_action(action_name, parameters)
        
        if is_destructive:
            logger.security_alert(f"{action_name} с параметрами {parameters}", requires_confirmation=True)
            
            # Если есть callback - запросим подтверждение
            if self.user_confirmation_callback:
                confirmed = await self.user_confirmation_callback(action_name, parameters, reason)
                
                if confirmed:
                    logger.info(f"Пользователь подтвердил действие: {action_name}")
                    return {
                        "safe": True,
                        "reason": "Подтверждено пользователем",
                        "requires_confirmation": False
                    }
                else:
                    logger.warning(f"Пользователь отклонил действие: {action_name}")
                    return {
                        "safe": False,
                        "reason": "Отклонено пользователем",
                        "requires_confirmation": False
                    }
            
            # Если нет callback - требуем подтверждение
            return {
                "safe": False,
                "reason": reason,
                "requires_confirmation": True
            }
        
        return {
            "safe": True,
            "reason": "Действие безопасно",
            "requires_confirmation": False
        }
    
    def _is_destructive_action(self, action_name: str, parameters: Dict[str, Any]) -> tuple[bool, str]:
        """
        Определить, является ли действие деструктивным.
        
        Returns:
            (is_destructive, reason)
        """
        # Проверка click действий
        if action_name == "click":
            selector = parameters.get("selector", "").lower()
            reason_text = parameters.get("reason", "").lower()
            
            for pattern in self.destructive_patterns:
                if pattern in selector or pattern in reason_text:
                    return True, f"Обнаружен деструктивный паттерн: '{pattern}'"
        
        # Проверка type_text (например, ввод данных карты)
        if action_name == "type_text":
            text = parameters.get("text", "").lower()
            selector = parameters.get("selector", "").lower()
            
            # Проверка на ввод финансовых данных
            if any(keyword in selector for keyword in ["card", "payment", "cvv", "credit"]):
                return True, "Попытка ввода платежных данных"
        
        return False, ""
    
    def add_destructive_pattern(self, pattern: str) -> None:
        """Добавить паттерн деструктивного действия."""
        if pattern not in self.destructive_patterns:
            self.destructive_patterns.append(pattern)
            logger.info(f"Добавлен деструктивный паттерн: {pattern}")
