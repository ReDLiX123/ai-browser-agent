"""
Модуль поиска элементов на странице.
Генерирует уникальные селекторы для элементов в runtime.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from playwright.async_api import Page, Locator, ElementHandle
from bs4 import BeautifulSoup

from ..utils.logger import AgentLogger


logger = AgentLogger(__name__)


@dataclass
class Element:
    """Представление элемента на странице."""
    selector: str
    tag: str
    text: str
    element_type: str  # button, link, input, etc.
    aria_label: Optional[str] = None
    placeholder: Optional[str] = None
    value: Optional[str] = None
    href: Optional[str] = None
    is_visible: bool = True
    bbox: Optional[Dict[str, float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для LLM."""
        return {
            "selector": self.selector,
            "type": self.element_type,
            "tag": self.tag,
            "text": self.text[:100] if self.text else "",  # Ограничение длины
            "aria_label": self.aria_label,
            "placeholder": self.placeholder,
            "visible": self.is_visible,
        }


class ElementFinder:
    """
    Класс для поиска и идентификации элементов на странице.
    Генерирует селекторы динамически, без хардкодинга.
    """
    
    INTERACTIVE_SELECTORS = [
        'a', 'button', 'input', 'select', 'textarea',
        '[role="button"]', '[role="link"]', '[role="tab"]',
        '[onclick]', '[ng-click]', '[data-testid]'
    ]
    
    def __init__(self, page: Page):
        self.page = page
    
    async def find_all_interactive_elements(self, max_elements: int = 50) -> List[Element]:
        """
        Найти все интерактивные элементы на странице.
        
        Args:
            max_elements: Максимальное количество элементов для возврата
        
        Returns:
            Список элементов Element
        """
        elements: List[Element] = []
        
        try:
            # Получение всех интерактивных элементов
            for selector in self.INTERACTIVE_SELECTORS:
                locators = self.page.locator(selector)
                count = await locators.count()
                
                logger.debug(f"Найдено {count} элементов для селектора '{selector}'")
                
                # Ограничиваем количество проверяемых элементов для одного селектора
                max_per_selector = min(count, 100)
                
                for i in range(max_per_selector):
                    # Проверяем лимит
                    if len(elements) >= max_elements:
                        logger.info(f"Достигнут лимит элементов: {max_elements}")
                        return elements
                    
                    try:
                        element = locators.nth(i)
                        
                        # Проверка видимости с timeout
                        is_visible = await element.is_visible(timeout=1000)
                        if not is_visible:
                            continue
                        
                        # Извлечение информации
                        elem_data = await self._extract_element_info(element, i)
                        if elem_data:
                            elements.append(elem_data)
                    
                    except Exception as e:
                        logger.debug(f"Ошибка обработки элемента {selector}[{i}]: {e}")
                        continue
            
            logger.info(f"Найдено {len(elements)} интерактивных элементов")
            return elements
        
        except Exception as e:
            logger.error(f"Ошибка поиска элементов: {e}")
            return []
    
    async def _extract_element_info(self, locator: Locator, index: int) -> Optional[Element]:
        """Извлечь информацию об элементе."""
        try:
            # Получение атрибутов
            tag_name = await locator.evaluate("el => el.tagName.toLowerCase()")
            text_content = await locator.inner_text() or ""
            text_content = text_content.strip()
            
            # Атрибуты
            element_id = await locator.get_attribute("id")
            element_class = await locator.get_attribute("class")
            aria_label = await locator.get_attribute("aria-label")
            placeholder = await locator.get_attribute("placeholder")
            element_type = await locator.get_attribute("type")
            value = await locator.get_attribute("value")
            href = await locator.get_attribute("href")
            data_testid = await locator.get_attribute("data-testid")
            
            # Bounding box
            bbox = await locator.bounding_box()
            
            # Генерация уникального селектора
            selector = await self._generate_selector(
                tag_name, element_id, element_class, text_content, 
                aria_label, data_testid, placeholder, index
            )
            
            # Определение типа элемента для LLM
            elem_type = self._determine_element_type(tag_name, element_type, href)
            
            return Element(
                selector=selector,
                tag=tag_name,
                text=text_content,
                element_type=elem_type,
                aria_label=aria_label,
                placeholder=placeholder,
                value=value,
                href=href,
                is_visible=True,
                bbox=bbox
            )
        
        except Exception as e:
            logger.debug(f"Не удалось извлечь информацию об элементе: {e}")
            return None
    
    async def _generate_selector(
        self,
        tag: str,
        elem_id: Optional[str],
        elem_class: Optional[str],
        text: str,
        aria_label: Optional[str],
        data_testid: Optional[str],
        placeholder: Optional[str],
        index: int
    ) -> str:
        """
        Генерировать уникальный селектор для элемента.
        
        Приоритет:
        1. data-testid (если есть)
        2. id (если уникальный)
        3. aria-label
        4. text content (для ссылок и кнопок)
        5. placeholder (для inputs)
        6. nth-child селектор
        """
        # 1. data-testid - самый надежный
        if data_testid:
            return f'[data-testid="{data_testid}"]'
        
        # 2. ID - если есть
        if elem_id:
            return f'#{elem_id}'
        
        # 3. Aria-label - хороший семантический селектор
        if aria_label:
            return f'{tag}[aria-label="{aria_label}"]'
        
        # 4. Text content - для кнопок и ссылок
        if text and len(text) > 0 and len(text) < 50:
            # Экранирование кавычек
            escaped_text = text.replace('"', '\\"')
            return f'{tag}:has-text("{escaped_text}")'
        
        # 5. Placeholder - для input полей
        if placeholder:
            return f'input[placeholder="{placeholder}"]'
        
        # 6. Class - если есть
        if elem_class:
            classes = elem_class.split()[0] if elem_class else ""
            if classes:
                return f'{tag}.{classes}'
        
        # 7. Fallback - nth селектор
        return f'{tag}:nth-of-type({index + 1})'
    
    def _determine_element_type(
        self, 
        tag: str, 
        input_type: Optional[str],
        href: Optional[str]
    ) -> str:
        """Определить тип элемента для понимания LLM."""
        if tag == "a" or href:
            return "link"
        elif tag == "button":
            return "button"
        elif tag == "input":
            if input_type == "submit":
                return "submit_button"
            elif input_type in ["text", "email", "password", "search"]:
                return "text_input"
            elif input_type == "checkbox":
                return "checkbox"
            elif input_type == "radio":
                return "radio"
            else:
                return "input"
        elif tag == "select":
            return "dropdown"
        elif tag == "textarea":
            return "textarea"
        else:
            return "interactive"
    
    async def find_element_by_description(self, description: str) -> Optional[Element]:
        """
        Найти элемент по текстовому описанию.
        Полезно когда LLM описывает элемент человеческим языком.
        
        Args:
            description: Описание элемента (например, "кнопка Submit")
            
        Returns:
            Найденный элемент или None
        """
        elements = await self.find_all_interactive_elements()
        
        description_lower = description.lower()
        
        # Поиск по тексту, aria-label, placeholder
        for elem in elements:
            if (elem.text and description_lower in elem.text.lower()) or \
               (elem.aria_label and description_lower in elem.aria_label.lower()) or \
               (elem.placeholder and description_lower in elem.placeholder.lower()):
                return elem
        
        return None
