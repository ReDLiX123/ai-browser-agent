"""
Определения инструментов (tools) для LLM.
Функции, которые агент может вызывать для взаимодействия с браузером.
"""

from typing import List, Dict, Any


# Определения инструментов для OpenAI function calling
BROWSER_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Кликнуть по элементу на странице. Используй селектор из предоставленного списка элементов.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS селектор элемента. ВАЖНО: используй ТОЛЬКО селекторы из списка interactive_elements!"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Объяснение, зачем кликаешь по этому элементу"
                    }
                },
                "required": ["selector", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Ввести текст в поле ввода. Используй селектор input элемента из предоставленного списка.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS селектор input элемента из списка interactive_elements"
                    },
                    "text": {
                        "type": "string",
                        "description": "Текст для ввода"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Объяснение, что вводишь и зачем"
                    }
                },
                "required": ["selector", "text", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "Перейти по указанному URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL для перехода (должен начинаться с http:// или https://)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Объяснение, зачем переходишь по этому URL"
                    }
                },
                "required": ["url", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Прокрутить страницу вниз или вверх",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["down", "up"],
                        "description": "Направление прокрутки"
                    },
                    "amount": {
                        "type": "string",
                        "enum": ["small", "medium", "large", "page"],
                        "description": "Количество прокрутки"
                    }
                },
                "required": ["direction", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_back",
            "description": "Вернуться на предыдущую страницу",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_text",
            "description": "Извлечь текстовый контент с определенной части страницы",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS селектор элемента, из которого нужно извлечь текст"
                    }
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Подождать некоторое время (для загрузки контента, анимаций и т.д.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "integer",
                        "description": "Количество секунд ожидания (1-10)",
                        "minimum": 1,
                        "maximum": 10
                    },
                    "reason": {
                        "type": "string",
                        "description": "Объяснение, зачем ждешь"
                    }
                },
                "required": ["seconds", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Нажать клавишу (Enter, Escape, Tab и т.д.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "enum": ["Enter", "Escape", "Tab", "Backspace", "Delete", "ArrowUp", "ArrowDown"],
                        "description": "Название клавиши"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Объяснение, зачем нажимаешь эту клавишу"
                    }
                },
                "required": ["key", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_complete",
            "description": "Завершить задачу и вернуть результат пользователю",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "string",
                        "description": "Результат выполнения задачи (ответ на вопрос пользователя)"
                    },
                    "success": {
                        "type": "boolean",
                        "description": "Успешно ли выполнена задача"
                    }
                },
                "required": ["result", "success"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Задать вопрос пользователю, когда нужна дополнительная информация",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Вопрос для пользователя"
                    }
                },
                "required": ["question"]
            }
        }
    }
]


def get_tool_descriptions() -> str:
    """Получить текстовое описание всех доступных инструментов."""
    descriptions = []
    for tool in BROWSER_TOOLS:
        func = tool["function"]
        desc = f"- {func['name']}: {func['description']}"
        descriptions.append(desc)
    return "\n".join(descriptions)
