"""
Системная шина (System Bus).
Центральная магистраль, через которую ИИ-ядро общается с модулями.
Как почтовая система города — все сообщения идут через неё.

Принцип: модули не знают друг о друге напрямую.
Они регистрируются на шине, и шина маршрутизирует команды.
Это даёт изоляцию — падение одного модуля не роняет другие.
"""

import asyncio
import logging
from datetime import datetime


class SystemBus:
    def __init__(self):
        self.modules = {}           # зарегистрированные модули
        self.event_log = []         # лог всех событий
        self.listeners = {}         # подписчики на события
        self.logger = logging.getLogger("aios.bus")

    def register(self, module):
        """Модуль регистрируется на шине — как новое здание получает адрес"""
        self.modules[module.name] = module
        self.logger.info(f"Модуль '{module.name}' зарегистрирован на шине")

    def unregister(self, module_name: str):
        """Модуль снимается с шины"""
        if module_name in self.modules:
            del self.modules[module_name]
            self.logger.info(f"Модуль '{module_name}' снят с шины")

    async def send(self, target_module: str, cmd_name: str, **kwargs):
        """
        Отправить команду модулю через шину.
        ИИ говорит: 'модуль files, выполни команду list, папка такая-то'
        Шина находит модуль и передаёт команду.
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "target": target_module,
            "command": cmd_name,
            "args": kwargs,
            "status": "pending"
        }

        if target_module not in self.modules:
            event["status"] = "error"
            event["result"] = f"Модуль '{target_module}' не найден"
            self.event_log.append(event)
            return event

        module = self.modules[target_module]

        if module.status != "running":
            # Модуль не работает — попробуем запустить
            self.logger.warning(f"Модуль '{target_module}' не запущен, запускаю...")
            await module.start()

        result = await module.execute(cmd_name, **kwargs)
        event["status"] = "ok" if result.get("ok") else "error"
        event["result"] = result
        self.event_log.append(event)

        # Уведомить подписчиков
        await self._notify(target_module, cmd_name, result)

        return event

    async def _notify(self, module_name: str, command: str, result):
        """Уведомить подписчиков о событии"""
        key = f"{module_name}.{command}"
        if key in self.listeners:
            for callback in self.listeners[key]:
                try:
                    await callback(result)
                except Exception as e:
                    self.logger.error(f"Ошибка в listener для {key}: {e}")

    def subscribe(self, event_key: str, callback):
        """Подписаться на событие — модуль может слушать другие модули"""
        if event_key not in self.listeners:
            self.listeners[event_key] = []
        self.listeners[event_key].append(callback)

    async def start_all(self):
        """Запустить все модули"""
        for name, module in self.modules.items():
            try:
                await module.start()
            except Exception as e:
                self.logger.error(f"Не удалось запустить '{name}': {e}")

    def list_modules(self):
        """Список всех модулей и их возможностей — ИИ видит что доступно"""
        return {
            name: module.get_info()
            for name, module in self.modules.items()
        }

    def get_recent_events(self, count=20):
        """Последние события — для отладки и мониторинга"""
        return self.event_log[-count:]
