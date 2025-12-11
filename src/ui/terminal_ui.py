"""
Terminal UI - интерфейс командной строки для взаимодействия с агентом.
"""

import asyncio
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown


from ..browser.automation import BrowserAutomation
from ..agents.orchestrator import OrchestratorAgent, TaskResult



console = Console()


class TerminalUI:
    """
    CLI интерфейс для взаимодействия с AI агентом.
    """
    
    def __init__(self):
        self.browser: Optional[BrowserAutomation] = None
        self.orchestrator: Optional[OrchestratorAgent] = None
    
    async def start(self) -> None:
        """Запустить интерфейс."""
        self._print_welcome()
        
        # Инициализация браузера
        console.print("\n[yellow]Инициализация браузера...[/yellow]")
        self.browser = BrowserAutomation()
        await self.browser.initialize()
        
        # Создание оркестратора
        self.orchestrator = OrchestratorAgent(self.browser)
        
        console.print("[green]✓ Браузер запущен и готов к работе![/green]\n")
        
        # Главный цикл
        try:
            await self._main_loop()
        finally:
            await self._cleanup()
    
    def _print_welcome(self) -> None:
        """Вывести приветственное сообщение."""
        welcome_text = """
# 🤖 AI Browser Agent

Автономный агент для управления веб-браузером.

**Команды:**
- Введите задачу на русском языке
- `exit` или `quit` - выход
- `help` - справка

**Примеры задач:**
- "Открой Wikipedia и найди информацию о Python"
- "Перейди на yandex.ru и покажи сегодняшнюю погоду"
- "Найди на GitHub проекты по machine learning"
        """
        
        console.print(Panel(Markdown(welcome_text), title="Добро пожаловать", border_style="blue"))
    
    async def _main_loop(self) -> None:
        """Главный цикл взаимодействия."""
        while True:
            try:
                # Получение задачи от пользователя
                task = Prompt.ask("\n[bold cyan]Введите задачу[/bold cyan]")
                
                # Проверка на exit
                if task.lower() in ["exit", "quit", "выход"]:
                    console.print("[yellow]До свидания![/yellow]")
                    break
                
                if task.lower() == "help":
                    self._print_help()
                    continue
                
                if not task.strip():
                    continue
                
                # Выполнение задачи
                await self._execute_task(task)
            
            except KeyboardInterrupt:
                console.print("\n[yellow]Прервано пользователем[/yellow]")
                break
            
            except Exception as e:
                console.print(f"[red]Ошибка: {e}[/red]")
    
    async def _execute_task(self, task: str) -> None:
        """Выполнить задачу."""
        console.print(f"\n[green]🚀 Начинаю выполнение задачи...[/green]\n")
        
        try:
            # Выполнение через оркестратор
            result: TaskResult = await self.orchestrator.execute_task(task)
            
            # Вывод результата
            self._print_result(result)
        
        except Exception as e:
            console.print(f"\n[red]❌ Ошибка выполнения: {e}[/red]")
    
    def _print_result(self, result: TaskResult) -> None:
        """Вывести результат выполнения."""
        console.print("\n" + "="*50)
        
        if result.success:
            console.print(f"[bold green]✅ Задача выполнена успешно![/bold green]")
            console.print(f"\n[cyan]Результат:[/cyan]")
            console.print(Panel(result.result, border_style="green"))
        else:
            console.print(f"[bold red]❌ Задача не выполнена[/bold red]")
            if result.error:
                console.print(f"\n[red]Ошибка:[/red] {result.error}")
        
        console.print(f"\n[dim]Выполнено шагов: {result.steps_taken}[/dim]")
        console.print("="*50)
    
    def _print_help(self) -> None:
        """Вывести справку."""
        help_text = """
## Помощь

### Как использовать:
1. Введите задачу на естественном языке
2. Агент автоматически выполнит все необходимые действия
3. Вы увидите процесс выполнения в браузере

### Что может агент:
- Открывать веб-сайты
- Кликать по элементам
- Заполнять формы
- Извлекать информацию
- Переходить между страницами

### Деструктивные действия:
Агент попросит подтверждение перед:
- Удалением данных
- Покупками
- Оплатой

### Важно:
- Агент работает автономно
- Не используются заготовленные сценарии
- Агент сам определяет, как выполнить задачу
        """
        
        console.print(Panel(Markdown(help_text), title="Справка", border_style="cyan"))
    
    async def _cleanup(self) -> None:
        """Очистка ресурсов."""
        console.print("\n[yellow]Закрытие браузера...[/yellow]")
        
        if self.browser:
            await self.browser.cleanup()
        
        console.print("[green]✓ Готово[/green]")


async def main():
    """Точка входа для CLI."""
    ui = TerminalUI()
    await ui.start()


if __name__ == "__main__":
    asyncio.run(main())
