"""
Консольный интерфейс AI-OS.
Точка входа для человека — вводишь команды, видишь результат.
В будущем это заменится на GUI или голосовой интерфейс,
но начинаем с консоли — просто и надёжно.
"""

import asyncio
import json


class Console:
    def __init__(self, brain):
        self.brain = brain
        self.running = False

    def _format_result(self, result):
        """Красиво показать результат"""
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            # Если есть вложенный результат от шины
            if "result" in result and isinstance(result["result"], dict):
                inner = result["result"]
                if "result" in inner:
                    return self._format_result(inner["result"])
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        if isinstance(result, list):
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)
        return str(result)

    async def run(self):
        """Главный цикл — читаем команды, выполняем, показываем результат"""
        self.running = True

        print()
        print("=" * 50)
        print("  AI-OS v0.1 — Модульная ИИ-система")
        print("=" * 50)
        print()
        print("  Система запущена. Модули загружены.")
        print("  Введи 'help' для справки.")
        print("  Введи 'modules' для списка модулей.")
        print()

        # Показать статус модулей при старте
        modules = self.brain.bus.list_modules()
        for name, info in modules.items():
            status_icon = "+" if info["status"] == "running" else "-"
            print(f"  [{status_icon}] {name}: {info['description']}")
        print()

        while self.running:
            try:
                user_input = input("ai-os> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ("exit", "quit", "q"):
                    print("\nСохраняю память...")
                    self.brain.save_memory()
                    print("AI-OS остановлена. До встречи.")
                    self.running = False
                    break

                # Обработать через мозг
                result = await self.brain.process(user_input)

                # Показать результат
                formatted = self._format_result(result)
                print(formatted)
                print()

            except KeyboardInterrupt:
                print("\n\nПрерывание. Сохраняю память...")
                self.brain.save_memory()
                print("AI-OS остановлена.")
                break
            except EOFError:
                break
            except Exception as e:
                print(f"Ошибка: {e}")
                print()
