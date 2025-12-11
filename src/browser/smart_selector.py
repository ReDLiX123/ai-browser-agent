"""
Модуль для умной работы с селекторами.
Генерирует уникальные AI ID для элементов и фильтрует только релевантные.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from playwright.async_api import Page

from ..utils.logger import AgentLogger


logger = AgentLogger(__name__)


@dataclass
class SmartElement:
    """Упрощенное представление элемента для LLM."""
    ai_id: str  # Уникальный ID: btn-1, input-2, link-3
    element_type: str  # button, link, input, etc.
    label: str  # Человекочитаемое описание
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в компактный словарь."""
        return {
            "id": self.ai_id,
            "type": self.element_type,
            "label": self.label[:80] if self.label else ""  # Ограничение длины
        }


class SmartSelectorSystem:
    """
    Система умных селекторов.
    Инжектирует уникальные ID в DOM и извлекает только релевантные элементы.
    """
    
    # Типы интерактивных элементов для поиска
    INTERACTIVE_TAGS = ['a', 'button', 'input', 'select', 'textarea']
    
    # Минимальный размер элемента для учета (в пикселях)
    MIN_ELEMENT_SIZE = 10
    
    def __init__(self, page: Page):
        self.page = page
        self.element_map: Dict[str, str] = {}  # ai_id -> real_selector
        self.id_counter = {
            'button': 0,
            'link': 0,
            'input': 0,
            'select': 0,
            'textarea': 0,
            'other': 0
        }
    
    async def inject_ai_ids(self) -> None:
        """
        Инжектировать уникальные data-ai-id атрибуты в интерактивные элементы.
        """
        try:
            logger.info("🔧 Инжектирование AI IDs в DOM...")
            
            # JavaScript для инжекции ID
            await self.page.evaluate("""
                () => {
                    // Удаляем старые AI IDs
                    document.querySelectorAll('[data-ai-id]').forEach(el => {
                        el.removeAttribute('data-ai-id');
                    });
                    
                    // Счетчики для каждого типа
                    const counters = {
                        button: 0,
                        link: 0,
                        input: 0,
                        select: 0,
                        textarea: 0,
                        other: 0
                    };
                    
                    // Функция определения типа
                    function getElementType(el) {
                        const tag = el.tagName.toLowerCase();
                        if (tag === 'a') return 'link';
                        if (tag === 'button') return 'button';
                        if (tag === 'input') return 'input';
                        if (tag === 'select') return 'select';
                        if (tag === 'textarea') return 'textarea';
                        if (el.hasAttribute('role')) {
                            const role = el.getAttribute('role');
                            if (role === 'button') return 'button';
                            if (role === 'link') return 'link';
                        }
                        return 'other';
                    }
                    
                    // Находим все интерактивные элементы
                    const selectors = [
                        'a', 'button', 'input', 'select', 'textarea',
                        '[role="button"]', '[role="link"]', '[role="tab"]',
                        '[onclick]'
                    ];
                    
                    const elements = new Set();
                    selectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => elements.add(el));
                    });
                    
                    // Инжектируем ID
                    elements.forEach(el => {
                        const type = getElementType(el);
                        const id = `${type}-${counters[type]++}`;
                        el.setAttribute('data-ai-id', id);
                    });
                    
                    return Array.from(elements).length;
                }
            """)
            
            logger.info("✅ AI IDs успешно инжектированы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инжекции AI IDs: {e}")
            raise
    
    async def extract_smart_elements(self, max_elements: int = 100) -> List[SmartElement]:
        """
        Извлечь только релевантные элементы с упрощенной информацией.
        
        Args:
            max_elements: Максимальное количество элементов
            
        Returns:
            Список SmartElement
        """
        try:
            logger.info("🔍 Извлечение релевантных элементов...")
            
            # JavaScript для извлечения элементов
            elements_data = await self.page.evaluate(f"""
                (maxElements) => {{
                    const elements = [];
                    
                    // Получаем размер viewport
                    const viewportHeight = window.innerHeight;
                    const viewportWidth = window.innerWidth;
                    
                    // Функция проверки релевантности
                    function isRelevant(el) {{
                        // Проверка видимости
                        const rect = el.getBoundingClientRect();
                        if (rect.width < {self.MIN_ELEMENT_SIZE} || rect.height < {self.MIN_ELEMENT_SIZE}) {{
                            return false;
                        }}
                        
                        // Вычисляем стили
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {{
                            return false;
                        }}
                        
                        // Проверяем, что элемент хотя бы частично в viewport
                        const inViewport = (
                            rect.top < viewportHeight &&
                            rect.bottom > 0 &&
                            rect.left < viewportWidth &&
                            rect.right > 0
                        );
                        
                        return inViewport;
                    }}
                    
                    // Функция получения label
                    function getLabel(el) {{
                        // Приоритет 1: aria-label
                        if (el.hasAttribute('aria-label')) {{
                            return el.getAttribute('aria-label');
                        }}
                        
                        // Приоритет 2: placeholder (для input)
                        if (el.hasAttribute('placeholder')) {{
                            return el.getAttribute('placeholder');
                        }}
                        
                        // Приоритет 3: title
                        if (el.hasAttribute('title')) {{
                            return el.getAttribute('title');
                        }}
                        
                        // Приоритет 4: текстовое содержимое
                        const text = el.innerText || el.textContent || '';
                        if (text.trim()) {{
                            return text.trim().substring(0, 80);
                        }}
                        
                        // Приоритет 5: значение для input
                        if (el.value) {{
                            return `Input: ${{el.value}}`;
                        }}
                        
                        // Приоритет 6: href для ссылок
                        if (el.href) {{
                            return `Link: ${{el.href}}`;
                        }}
                        
                        // Fallback
                        return el.tagName.toLowerCase();
                    }}
                    
                    // Функция определения типа
                    function getType(el) {{
                        const tag = el.tagName.toLowerCase();
                        if (tag === 'a') return 'link';
                        if (tag === 'button') return 'button';
                        if (tag === 'select') return 'dropdown';
                        if (tag === 'textarea') return 'textarea';
                        if (tag === 'input') {{
                            const type = el.type || 'text';
                            if (type === 'submit') return 'submit_button';
                            if (type === 'checkbox') return 'checkbox';
                            if (type === 'radio') return 'radio';
                            return 'text_input';
                        }}
                        return 'interactive';
                    }}
                    
                    // Получаем все элементы с AI ID
                    const allElements = Array.from(document.querySelectorAll('[data-ai-id]'));
                    
                    // Фильтруем релевантные
                    const relevantElements = allElements.filter(isRelevant);
                    
                    // Приоритизация: сначала в верхней части viewport
                    relevantElements.sort((a, b) => {{
                        const rectA = a.getBoundingClientRect();
                        const rectB = b.getBoundingClientRect();
                        
                        // Сортировка по позиции в viewport (сверху вниз)
                        return rectA.top - rectB.top;
                    }});
                    
                    // Берем только нужное количество
                    const limitedElements = relevantElements.slice(0, maxElements);
                    
                    // Формируем результат
                    return limitedElements.map(el => ({{
                        ai_id: el.getAttribute('data-ai-id'),
                        type: getType(el),
                        label: getLabel(el)
                    }}));
                }}
            """, max_elements)
            
            # Преобразуем в SmartElement
            smart_elements = [
                SmartElement(
                    ai_id=elem['ai_id'],
                    element_type=elem['type'],
                    label=elem['label']
                )
                for elem in elements_data
            ]
            
            # Обновляем карту селекторов
            self.element_map.clear()
            for elem in smart_elements:
                self.element_map[elem.ai_id] = f'[data-ai-id="{elem.ai_id}"]'
            
            logger.info(f"✅ Найдено {len(smart_elements)} релевантных элементов")
            return smart_elements
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения элементов: {e}")
            return []
    
    def get_selector_by_ai_id(self, ai_id: str) -> Optional[str]:
        """
        Получить реальный CSS селектор по AI ID.
        
        Args:
            ai_id: AI ID элемента (например, "btn-1")
            
        Returns:
            CSS селектор или None
        """
        return self.element_map.get(ai_id)
    
    def convert_ai_id_to_selector(self, ai_id_or_selector: str) -> str:
        """
        Конвертировать AI ID в селектор, если нужно.
        Если передан уже селектор - вернуть как есть.
        
        Args:
            ai_id_or_selector: AI ID или селектор
            
        Returns:
            CSS селектор
        """
        # Если это уже селектор (содержит [, #, ., :)
        if any(char in ai_id_or_selector for char in ['[', '#', '.', ':']):
            return ai_id_or_selector
        
        # Иначе это AI ID - конвертируем
        selector = self.get_selector_by_ai_id(ai_id_or_selector)
        if selector:
            return selector
        
        # Fallback - попробуем как есть
        logger.warning(f"AI ID '{ai_id_or_selector}' не найден в карте, использую как селектор")
        return ai_id_or_selector
    
    async def refresh_elements(self) -> List[SmartElement]:
        """
        Полное обновление: переинжектирование ID и повторное извлечение элементов.
        """
        await self.inject_ai_ids()
        return await self.extract_smart_elements()
    
    def clear(self) -> None:
        """Очистить карту элементов и счетчики."""
        self.element_map.clear()
        for key in self.id_counter:
            self.id_counter[key] = 0
        logger.debug("Карта элементов очищена")
