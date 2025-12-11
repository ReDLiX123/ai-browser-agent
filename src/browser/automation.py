"""
Модуль автоматизации браузера.
Обертка над Playwright для управления браузером и контекстом.
"""

from typing import Optional, Dict, Any
from pathlib import Path
import asyncio

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Error as PlaywrightError
)

from ..utils.logger import AgentLogger
from ..utils.config import browser_config, persistent_context_config, page_wait_config


logger = AgentLogger(__name__)


class BrowserAutomation:
    """
    Класс для управления браузером через Playwright.
    Поддерживает persistent sessions и автоматическое управление контекстом.
    """
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._is_initialized = False
    
    async def initialize(self) -> None:
        """Инициализировать браузер и создать контекст."""
        if self._is_initialized:
            logger.warning("Browser уже инициализирован")
            return
        
        try:
            logger.info("Инициализация браузера...")
            
            # Запуск Playwright
            self.playwright = await async_playwright().start()
            
            # Выбор типа браузера
            browser_type = getattr(self.playwright, browser_config.type)
            
            # Запуск браузера
            launch_args = {
                "headless": browser_config.headless,
                "slow_mo": browser_config.slow_mo,
                "devtools": browser_config.devtools,
            }
            
            # Добавляем args если есть
            if browser_config.args:
                launch_args["args"] = browser_config.args
            
            self.browser = await browser_type.launch(**launch_args)
            
            logger.info(f"Браузер {browser_config.type} запущен")
            
            # Создание контекста
            await self._create_context()
            
            self._is_initialized = True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации браузера: {e}")
            await self.cleanup()
            raise
    
    async def _create_context(self) -> None:
        """Создать browser context (persistent или обычный)."""
        if not self.browser:
            raise RuntimeError("Browser не инициализирован")
        
        context_options: Dict[str, Any] = {
            "viewport": browser_config.viewport,
            "user_agent": browser_config.user_agent if browser_config.user_agent else None,
        }
        
        # Persistent context для сохранения сессий
        if persistent_context_config.enabled:
            data_dir = Path(persistent_context_config.data_dir)
            data_dir.mkdir(exist_ok=True, parents=True)
            
            # Для persistent context используем browser_type.launch_persistent_context
            logger.info(f"Использование persistent context: {data_dir}")
            
            # Закрываем обычный browser и создаем persistent
            await self.browser.close()
            
            browser_type = getattr(self.playwright, browser_config.type)
            
            persistent_args = {
                "headless": browser_config.headless,
                "slow_mo": browser_config.slow_mo,
                **context_options
            }
            
            # Добавляем args если есть
            if browser_config.args:
                persistent_args["args"] = browser_config.args
            
            self.context = await browser_type.launch_persistent_context(
                str(data_dir),
                **persistent_args
            )
            self.browser = None  # В persistent context browser недоступен отдельно
        else:
            self.context = await self.browser.new_context(**context_options)
        
        # Создание первой страницы
        if len(self.context.pages) > 0:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()
        
        # Установка timeout
        self.page.set_default_timeout(browser_config.timeout)
        
        logger.info("Браузер context создан")
    
    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """
        Перейти по URL.
        
        Args:
            url: URL для перехода
            wait_until: Условие ожидания ('load', 'domcontentloaded', 'networkidle')
        """
        if not self.page:
            raise RuntimeError("Page не инициализирована")
        
        try:
            logger.info(f"Переход на: {url}")
            await self.page.goto(url, wait_until=wait_until)
            await self._wait_for_page_ready()
            logger.info(f"Страница загружена: {self.page.url}")
        except PlaywrightError as e:
            logger.error(f"Ошибка навигации: {e}")
            raise
    
    async def _wait_for_page_ready(self) -> None:
        """Дождаться полной готовности страницы."""
        if not self.page:
            return
        
        try:
            # Ждем NetworkIdle для SPA
            await self.page.wait_for_load_state("networkidle", 
                                               timeout=page_wait_config.network_idle_timeout)
        except PlaywrightError:
            # Если NetworkIdle не достигнут, продолжаем
            logger.debug("NetworkIdle timeout, продолжаем работу")
    
    async def get_current_url(self) -> str:
        """Получить текущий URL."""
        if not self.page:
            raise RuntimeError("Page не инициализирована")
        return self.page.url
    
    async def get_page_title(self) -> str:
        """Получить заголовок страницы."""
        if not self.page:
            raise RuntimeError("Page не инициализирована")
        return await self.page.title()
    
    async def take_screenshot(self, path: Optional[str] = None) -> bytes:
        """
        Сделать скриншот страницы.
        
        Args:
            path: Путь для сохранения (опционально)
            
        Returns:
            Байты изображения
        """
        if not self.page:
            raise RuntimeError("Page не инициализирована")
        
        screenshot = await self.page.screenshot(
            path=path,
            full_page=False  # Только viewport
        )
        
        if path:
            logger.info(f"Скриншот сохранен: {path}")
        
        return screenshot
    
    async def execute_script(self, script: str) -> Any:
        """
        Выполнить JavaScript на странице.
        
        Args:
            script: JavaScript код
            
        Returns:
            Результат выполнения
        """
        if not self.page:
            raise RuntimeError("Page не инициализирована")
        
        return await self.page.evaluate(script)
    
    async def go_back(self) -> None:
        """Вернуться на предыдущую страницу."""
        if not self.page:
            raise RuntimeError("Page не инициализирована")
        
        await self.page.go_back()
        await self._wait_for_page_ready()
        logger.info("Возврат на предыдущую страницу")
    
    async def go_forward(self) -> None:
        """Перейти на следующую страницу."""
        if not self.page:
            raise RuntimeError("Page не инициализирована")
        
        await self.page.go_forward()
        await self._wait_for_page_ready()
        logger.info("Переход на следующую страницу")
    
    async def reload(self) -> None:
        """Перезагрузить текущую страницу."""
        if not self.page:
            raise RuntimeError("Page не инициализирована")
        
        await self.page.reload()
        await self._wait_for_page_ready()
        logger.info("Страница перезагружена")
    
    async def wait_for_timeout(self, timeout: int) -> None:
        """
        Ожидание заданное время.
        
        Args:
            timeout: Время ожидания в миллисекундах
        """
        await asyncio.sleep(timeout / 1000)
    
    async def cleanup(self) -> None:
        """Очистить ресурсы и закрыть браузер."""
        logger.info("Очистка ресурсов браузера...")
        
        try:
            if self.context:
                await self.context.close()
            
            if self.browser:
                await self.browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("Браузер закрыт")
            
        except Exception as e:
            logger.error(f"Ошибка при закрытии браузера: {e}")
        finally:
            self._is_initialized = False
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.cleanup()
