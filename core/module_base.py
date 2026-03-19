"""
Базовый класс модуля системы.
Каждый модуль (файлы, сеть, процессы) наследует от этого класса.
Модуль = независимый блок системы, который:
  - запускается сам
  - работает автономно
  - принимает команды через шину
  - может быть перезапущен без остановки всей системы
"""

import asyncio
import logging
from datetime import datetime
from ai.knowledge import KnowledgeBase


class SystemModule:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = "stopped"       # stopped / running / error
        self.started_at = None
        self.commands = {}             # команды, которые модуль умеет выполнять
        self.kb = KnowledgeBase(name)  # база знаний модуля
        self.logger = logging.getLogger(f"aios.{name}")

        # Каждый модуль умеет искать по своим знаниям
        self.register_command("kb_search", self._kb_search, "Поиск по базе знаний модуля")
        self.register_command("kb_solve", self._kb_solve, "Найти решение проблемы")
        self.register_command("kb_sources", self._kb_sources, "Показать источники документации")
        self.register_command("kb_stats", self._kb_stats, "Статистика базы знаний")

    async def _kb_search(self, query=""):
        return self.kb.search(query)

    async def _kb_solve(self, problem=""):
        sol = self.kb.find_solution(problem)
        return sol if sol else f"Решение для '{problem}' не найдено. База учится — добавьте через обучение."

    async def _kb_sources(self):
        return self.kb.sources if self.kb.sources else "Источники не добавлены"

    async def _kb_stats(self):
        return self.kb.get_stats()

    async def start(self):
        """Запуск модуля — как включение службы Windows"""
        self.status = "running"
        self.started_at = datetime.now()
        self.logger.info(f"[{self.name}] запущен")

    async def stop(self):
        """Остановка модуля"""
        self.status = "stopped"
        self.logger.info(f"[{self.name}] остановлен")

    async def restart(self):
        """Перезапуск — если модуль сломался, перезапускаем только его"""
        await self.stop()
        await self.start()

    def register_command(self, command_name: str, handler, description: str):
        """Регистрация команды — модуль говорит системе 'я умею делать вот это'"""
        self.commands[command_name] = {
            "handler": handler,
            "description": description
        }

    async def execute(self, cmd_name: str, **kwargs):
        """Выполнение команды — ИИ вызывает конкретную функцию модуля"""
        command = cmd_name
        if cmd_name not in self.commands:
            # Не знаем команду — ищем в базе знаний
            hint = self.kb.search(command, limit=3)
            if hint:
                return {"error": f"Команда '{command}' не найдена", "hints": hint}
            return {"error": f"Команда '{command}' не найдена в модуле '{self.name}'"}
        try:
            # Фильтруем аргументы — убираем те, что функция не принимает
            import inspect
            handler = self.commands[command]["handler"]
            sig = inspect.signature(handler)
            params = sig.parameters
            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
                # Функция принимает **kwargs — передаём всё
                filtered_kwargs = kwargs
            else:
                valid_params = set(params.keys()) - {"self"}
                filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
            result = await handler(**filtered_kwargs)
            return {"ok": True, "result": result}
        except Exception as e:
            self.logger.error(f"[{self.name}] ошибка в '{command}': {e}")
            # Ищем решение в базе знаний
            solution = self.kb.find_solution(str(e))
            error_result = {"error": str(e)}
            if solution:
                error_result["suggested_fix"] = solution
            return error_result

    def get_info(self):
        """Информация о модуле — ИИ спрашивает 'что ты умеешь?'"""
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "started_at": str(self.started_at) if self.started_at else None,
            "commands": {
                name: cmd["description"]
                for name, cmd in self.commands.items()
            }
        }
