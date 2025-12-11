"""
Browser Agent - агент для выполнения действий в браузере.
Предоставляет инструменты для LLM.
"""

from typing import Dict, Any, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from ..browser.automation import BrowserAutomation
from ..browser.page_analyzer import PageAnalyzer
from ..utils.logger import AgentLogger


logger = AgentLogger(__name__)


class BrowserAgent:
    """
    Агент для выполнения действий в браузере.
    Реализует все инструменты из tools.py.
    """
    
    def __init__(self, browser: BrowserAutomation):
        self.browser = browser
        self.page: Page = browser.page
        self.page_analyzer: Optional[PageAnalyzer] = None
        
        if self.page:
            self.page_analyzer = PageAnalyzer(self.page)
    
    def _convert_to_selector(self, ai_id_or_selector: str) -> str:
        """
        Конвертировать AI ID в реальный селектор.
        Если передан селектор - вернуть как есть.
        """
        # Если это AI ID (простой формат: type-number)
        if '-' in ai_id_or_selector and not any(char in ai_id_or_selector for char in ['[', '#', '.', ':']):
            # Конвертируем в селектор с data-ai-id
            selector = f'[data-ai-id="{ai_id_or_selector}"]'
            logger.debug(f"AI ID '{ai_id_or_selector}' -> Selector '{selector}'")
            return selector
        
        # Иначе это уже селектор
        return ai_id_or_selector
    
    async def click(self, selector: str, reason: str = "") -> Dict[str, Any]:
        """
        Кликнуть по элементу (поддержка AI ID).
        
        Args:
            selector: AI ID (например, "btn-1") или CSS селектор элемента
            reason: Объяснение действия
            
        Returns:
            Результат действия
        """
        try:
            # Конвертируем AI ID в селектор если нужно
            real_selector = self._convert_to_selector(selector)
            logger.action("CLICK", f"{real_selector} - {reason}")
            
            # Поиск элемента
            element = self.page.locator(real_selector).first
            
            # Ожидание видимости
            await element.wait_for(state="visible", timeout=5000)
            
            # Клик
            await element.click()
            
            # Увеличенное ожидание после клика для модальных окон и динамического контента
            await self.page.wait_for_timeout(1500)  # Было wait_for_load_state
            
            # Дополнительное ожидание для SPA (модальные окна, меню)
            try:
                await self.page.wait_for_load_state("networkidle", timeout=2000)
            except:
                pass  # Если не дождались networkidle - не критично
            
            logger.info(f"Клик выполнен: {selector}")
            
            return {
                "success": True,
                "message": f"Кликнул по элементу {selector}",
                "new_url": self.page.url
            }
        
        except PlaywrightTimeout:
            error_msg = f"Элемент не найден или не видим: {selector}"
            logger.error(f"{error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        
        except Exception as e:
            error_msg = f"Ошибка клика: {str(e)}"
            logger.error(f"{error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def type_text(self, selector: str, text: str, reason: str = "") -> Dict[str, Any]:
        """
        Ввести текст в поле (поддержка AI ID).
        
        Args:
            selector: AI ID (например, "input-1") или CSS селектор input элемента
            text: Текст для ввода
            reason: Объяснение действия
            
        Returns:
            Результат действия
        """
        try:
            # Конвертируем AI ID в селектор если нужно
            real_selector = self._convert_to_selector(selector)
            logger.action("TYPE", f"{real_selector} = '{text}' - {reason}")
            
            element = self.page.locator(real_selector).first
            await element.wait_for(state="visible", timeout=5000)
            
            # Очистка поля
            await element.clear()
            
            # Ввод текста
            await element.fill(text)
            
            logger.info(f"Текст введен в {selector}")
            
            return {
                "success": True,
                "message": f"Ввел текст в {selector}"
            }
        
        except Exception as e:
            error_msg = f"Ошибка ввода текста: {str(e)}"
            logger.error(f"{error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def navigate(self, url: str, reason: str = "") -> Dict[str, Any]:
        """
        Перейти по URL.
        
        Args:
            url: URL для перехода
            reason: Объяснение действия
            
        Returns:
            Результат действия
        """
        try:
            logger.action("NAVIGATE", f"{url} - {reason}")
            
            await self.browser.navigate(url)
            
            logger.info(f"Переход выполнен: {url}")
            
            return {
                "success": True,
                "message": f"Перешел на {url}",
                "current_url": self.page.url
            }
        
        except Exception as e:
            error_msg = f"Ошибка навигации: {str(e)}"
            logger.error(f"{error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def scroll(self, direction: str = "down", amount: str = "medium") -> Dict[str, Any]:
        """
        Прокрутить страницу.
        
        Args:
            direction: Направление ('up', 'down')
            amount: Количество ('small', 'medium', 'large', 'page')
            
        Returns:
            Результат действия
        """
        try:
            logger.action("SCROLL", f"{direction} {amount}")
            
            # Определение расстояния
            distances = {
                "small": 200,
                "medium": 500,
                "large": 1000,
                "page": 0  # viewport height
            }
            
            distance = distances.get(amount, 500)
            
            if amount == "page":
                # Прокрутка на высоту viewport
                viewport = self.page.viewport_size
                distance = viewport["height"] if viewport else 800
            
            # Отрицательное значение для прокрутки вверх
            if direction == "up":
                distance = -distance
            
            await self.page.evaluate(f"window.scrollBy(0, {distance})")
            await self.page.wait_for_timeout(1000)  # Даем время на загрузку контента
            
            logger.info(f"Прокрутка выполнена: {direction} {amount}")
            
            return {
                "success": True,
                "message": f"Прокрутил страницу {direction} на {amount}"
            }
        
        except Exception as e:
            error_msg = f"Ошибка прокрутки: {str(e)}"
            logger.error(f"{error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def go_back(self) -> Dict[str, Any]:
        """Вернуться на предыдущую страницу."""
        try:
            logger.action("GO_BACK", "Возврат назад")
            
            await self.browser.go_back()
            
            logger.info("✅ Возврат на предыдущую страницу")
            
            return {
                "success": True,
                "message": "Вернулся на предыдущую страницу",
                "current_url": self.page.url
            }
        
        except Exception as e:
            error_msg = f"Ошибка возврата: {str(e)}"
            logger.error(f"{error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def extract_text(self, selector: str) -> Dict[str, Any]:
        """
        Извлечь текст из элемента (поддержка AI ID).
        
        Args:
            selector: AI ID (например, "link-1") или CSS селектор элемента
            
        Returns:
            Результат с текстом
        """
        try:
            # Конвертируем AI ID в селектор если нужно
            real_selector = self._convert_to_selector(selector)
            logger.action("EXTRACT_TEXT", real_selector)
            
            element = self.page.locator(real_selector).first
            text = await element.inner_text()
            
            logger.info(f"Текст извлечен из {selector}")
            
            return {
                "success": True,
                "text": text,
                "message": f"Извлек текст из {selector}"
            }
        
        except Exception as e:
            error_msg = f"Ошибка извлечения текста: {str(e)}"
            logger.error(f"{error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def wait(self, seconds: int, reason: str = "") -> Dict[str, Any]:
        """
        Подождать указанное время.
        
        Args:
            seconds: Секунды ожидания
            reason: Объяснение ожидания
            
        Returns:
            Результат
        """
        try:
            logger.action("WAIT", f"{seconds}s - {reason}")
            
            await self.page.wait_for_timeout(seconds * 1000)
            
            logger.info(f"Ожидание {seconds}s завершено")
            
            return {
                "success": True,
                "message": f"Подождал {seconds} секунд"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def press_key(self, key: str, reason: str = "") -> Dict[str, Any]:
        """
        Нажать клавишу.
        
        Args:
            key: Название клавиши
            reason: Объяснение
            
        Returns:
            Результат
        """
        try:
            logger.action("PRESS_KEY", f"{key} - {reason}")
            
            await self.page.keyboard.press(key)
            
            logger.info(f"Клавиша нажата: {key}")
            
            return {
                "success": True,
                "message": f"Нажал клавишу {key}"
            }
        
        except Exception as e:
            error_msg = f"Ошибка нажатия клавиши: {str(e)}"
            logger.error(f"{error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def get_page_info(self) -> Dict[str, Any]:
        """Получить информацию о текущей странице."""
        if not self.page_analyzer:
            self.page_analyzer = PageAnalyzer(self.page)
        
        # Используем новую систему Smart Selectors по умолчанию
        page_info = await self.page_analyzer.analyze_page(use_smart_selectors=True, max_elements=100)
        return page_info.to_dict()
