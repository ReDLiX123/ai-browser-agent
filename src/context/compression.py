"""
Сжатие контекста и извлечение ключевой информации.
"""

from typing import Dict, Any, List
from bs4 import BeautifulSoup

from ..utils.logger import AgentLogger


logger = AgentLogger(__name__)


class ContentCompressor:
    """
    Класс для сжатия контента веб-страниц.
    Удаляет ненужную информацию и оставляет только суть.
    """
    
    @staticmethod
    def simplify_html(html: str) -> str:
        """
        Упростить HTML, оставив только важные элементы.
        
        Args:
            html: Исходный HTML
            
        Returns:
            Упрощенный HTML
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Удаляем ненужные теги
            for tag in soup(['script', 'style', 'meta', 'link', 'noscript', 'svg', 'path']):
                tag.decompose()
            
            # Удаляем комментарии
            for comment in soup.find_all(text=lambda text: isinstance(text, str) and text.startswith('<!--')):
                comment.extract()
            
            # Получаем упрощенный HTML
            simplified = str(soup)
            
            logger.debug(f"HTML упрощен: {len(html)} -> {len(simplified)} символов")
            return simplified
        
        except Exception as e:
            logger.error(f"Ошибка упрощения HTML: {e}")
            return html
    
    @staticmethod
    def extract_essential_info(page_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлечь только ключевую информацию для LLM (агрессивная компрессия).
        
        Args:
            page_info: Полная информация о странице
            
        Returns:
            Сжатая информация
        """
        essential = {
            "url": page_info.get("url", ""),
            "title": page_info.get("title", ""),
            # Максимум 100 элементов - увеличенный лимит для сложных страниц
            "interactive_elements": page_info.get("interactive_elements", [])[:100],
        }
        
        # Убрали text_summary и forms - они почти не используются агентом
        # Новая структура элементов уже минимальная: {id, type, label}
        
        logger.debug(f"Информация сжата: {len(page_info.get('interactive_elements', []))} -> {len(essential['interactive_elements'])} элементов")
        return essential
    
    @staticmethod
    def summarize_elements(elements: List[Dict[str, Any]], max_elements: int = 20) -> List[Dict[str, Any]]:
        """
        Сократить список элементов, оставив наиболее важные.
        
        Приоритет:
        1. Кнопки и ссылки с текстом
        2. Input поля
        3. Остальные интерактивные элементы
        """
        if len(elements) <= max_elements:
            return elements
        
        # Сортировка по важности
        prioritized = []
        
        # 1. Кнопки и ссылки с текстом
        for elem in elements:
            if elem.get("type") in ["button", "link", "submit_button"] and elem.get("text"):
                prioritized.append(elem)
        
        # 2. Input поля
        for elem in elements:
            if "input" in elem.get("type", "") and elem not in prioritized:
                prioritized.append(elem)
        
        # 3. Остальное
        for elem in elements:
            if elem not in prioritized:
                prioritized.append(elem)
            
            if len(prioritized) >= max_elements:
                break
        
        logger.debug(f"Элементы сокращены: {len(elements)} -> {len(prioritized)}")
        return prioritized[:max_elements]
