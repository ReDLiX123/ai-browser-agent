"""
Модуль анализа веб-страниц.
Извлекает информацию со страницы и подготавливает её для LLM.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from playwright.async_api import Page
from bs4 import BeautifulSoup

from ..utils.logger import AgentLogger
from .element_finder import ElementFinder, Element
from .smart_selector import SmartSelectorSystem, SmartElement


logger = AgentLogger(__name__)


@dataclass
class PageInfo:
    """Информация о странице (упрощенная версия)."""
    url: str
    title: str
    interactive_elements: List[Dict[str, Any]]  # Список SmartElement в виде dict
    # Убрали text_content, forms, metadata для экономии токенов
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь."""
        return asdict(self)


class PageAnalyzer:
    """
    Анализатор веб-страниц.
    Извлекает структурированную информацию для AI агента.
    """
    
    def __init__(self, page: Page):
        self.page = page
        self.element_finder = ElementFinder(page)
        self.smart_selector = SmartSelectorSystem(page)
    
    async def analyze_page(self, use_smart_selectors: bool = True, max_elements: int = 100) -> PageInfo:
        """
        Полный анализ текущей страницы с умными селекторами.
        
        Args:
            use_smart_selectors: Использовать новую систему AI ID (рекомендуется)
            max_elements: Максимальное количество элементов
            
        Returns:
            Объект PageInfo с информацией о странице
        """
        try:
            logger.info("🔍 Анализ страницы...")
            
            # Базовая информация
            url = self.page.url
            title = await self.page.title()
            
            # Интерактивные элементы - используем новую или старую систему
            if use_smart_selectors:
                # Новая система: инжектируем AI IDs и извлекаем только релевантные
                await self.smart_selector.inject_ai_ids()
                smart_elements = await self.smart_selector.extract_smart_elements(max_elements)
                elements_dict = [elem.to_dict() for elem in smart_elements]
                logger.info(f"📊 Используется SmartSelector: {len(elements_dict)} элементов")
            else:
                # Старая система (для обратной совместимости)
                elements = await self.element_finder.find_all_interactive_elements(max_elements)
                elements_dict = [elem.to_dict() for elem in elements]
                logger.info(f"📊 Используется ElementFinder: {len(elements_dict)} элементов")
            
            page_info = PageInfo(
                url=url,
                title=title,
                interactive_elements=elements_dict
            )
            
            logger.info(f"✅ Страница проанализирована: {len(elements_dict)} элементов")
            return page_info
        
        except Exception as e:
            logger.error(f"❌ Ошибка анализа страницы: {e}")
            raise
    
    async def _extract_text_content(self, max_length: int = 2000) -> str:
        """
        Извлечь основной текстовый контент страницы.
        
        Args:
            max_length: Максимальная длина текста
            
        Returns:
            Текстовый контент
        """
        try:
            # Получаем текст из body, убираем скрипты и стили
            text = await self.page.evaluate("""
                () => {
                    // Клонируем body
                    const body = document.body.cloneNode(true);
                    
                    // Удаляем скрипты, стили, навигацию
                    const unwanted = body.querySelectorAll('script, style, nav, footer, header');
                    unwanted.forEach(el => el.remove());
                    
                    // Получаем текст
                    return body.innerText;
                }
            """)
            
            # Очистка и ограничение
            text = " ".join(text.split())  # Убираем множественные пробелы
            
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            return text
        
        except Exception as e:
            logger.debug(f"Ошибка извлечения текста: {e}")
            return ""
    
    async def _extract_forms(self) -> List[Dict[str, Any]]:
        """Извлечь информацию о формах на странице."""
        try:
            forms_data = await self.page.evaluate("""
                () => {
                    const forms = Array.from(document.querySelectorAll('form'));
                    return forms.map((form, idx) => {
                        const inputs = Array.from(form.querySelectorAll('input, select, textarea'));
                        return {
                            id: form.id || `form-${idx}`,
                            action: form.action,
                            method: form.method,
                            fields: inputs.map(input => ({
                                name: input.name,
                                type: input.type || input.tagName.toLowerCase(),
                                placeholder: input.placeholder,
                                required: input.required
                            }))
                        };
                    });
                }
            """)
            
            return forms_data
        
        except Exception as e:
            logger.debug(f"Ошибка извлечения форм: {e}")
            return []
    
    async def _extract_metadata(self) -> Dict[str, Any]:
        """Извлечь метаданные страницы."""
        try:
            metadata = await self.page.evaluate("""
                () => {
                    const meta = {};
                    
                    // Meta tags
                    const metaTags = document.querySelectorAll('meta');
                    metaTags.forEach(tag => {
                        const name = tag.getAttribute('name') || tag.getAttribute('property');
                        const content = tag.getAttribute('content');
                        if (name && content) {
                            meta[name] = content;
                        }
                    });
                    
                    // Canonical URL
                    const canonical = document.querySelector('link[rel="canonical"]');
                    if (canonical) {
                        meta['canonical'] = canonical.href;
                    }
                    
                    return meta;
                }
            """)
            
            return metadata
        
        except Exception as e:
            logger.debug(f"Ошибка извлечения метаданных: {e}")
            return {}
    
    async def get_element_context(self, selector: str, context_radius: int = 2) -> Dict[str, Any]:
        """
        Получить контекст вокруг элемента (соседние элементы).
        Полезно для понимания местоположения элемента.
        
        Args:
            selector: CSS селектор элемента
            context_radius: Количество соседних элементов для включения
            
        Returns:
            Контекст элемента
        """
        try:
            context = await self.page.evaluate(f"""
                (selector, radius) => {{
                    const element = document.querySelector(selector);
                    if (!element) return null;
                    
                    const parent = element.parentElement;
                    if (!parent) return null;
                    
                    const siblings = Array.from(parent.children);
                    const index = siblings.indexOf(element);
                    
                    const start = Math.max(0, index - radius);
                    const end = Math.min(siblings.length, index + radius + 1);
                    
                    return {{
                        parent: parent.tagName,
                        siblings: siblings.slice(start, end).map(el => ({{
                            tag: el.tagName,
                            text: el.innerText?.substring(0, 50),
                            is_target: el === element
                        }}))
                    }};
                }}
            """, selector, context_radius)
            
            return context or {}
        
        except Exception as e:
            logger.debug(f"Ошибка получения контекста элемента: {e}")
            return {}
    
    async def is_spa(self) -> bool:
        """
        Определить, является ли страница Single Page Application.
        """
        try:
            # Проверяем наличие популярных SPA фреймворков
            is_spa = await self.page.evaluate("""
                () => {
                    return !!(
                        window.React ||
                        window.Angular ||
                        window.Vue ||
                        document.querySelector('[ng-app]') ||
                        document.querySelector('[data-reactroot]') ||
                        document.querySelector('[data-v-]')
                    );
                }
            """)
            
            if is_spa:
                logger.info("🎯 Обнаружен SPA фреймворк")
            
            return is_spa
        
        except Exception as e:
            logger.debug(f"Ошибка определения SPA: {e}")
            return False
