"""
ИИ-ядро (Brain).
Мозг системы — принимает запросы от человека, разбирает их,
вызывает нужные модули, учится на результатах.

Ключевой принцип: модули сами себя настраивают.
Brain запоминает что работало, что нет, и в следующий раз
выбирает лучший путь.
"""

import json
import os
import asyncio
from datetime import datetime
from pathlib import Path


# Путь к памяти ИИ — сюда сохраняется опыт
MEMORY_DIR = Path(__file__).parent.parent / "memory"


class Brain:
    def __init__(self, bus):
        self.bus = bus                    # шина для связи с модулями
        self.memory = {}                  # оперативная память (текущая сессия)
        self.skills = {}                  # выученные навыки
        self.history = []                 # история действий в сессии
        self.trainer = None               # автообучение (подключается позже)
        self._load_memory()               # загрузить опыт из прошлых сессий

    def _load_memory(self):
        """Загрузить сохранённый опыт при старте"""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        skills_file = MEMORY_DIR / "skills.json"
        patterns_file = MEMORY_DIR / "patterns.json"

        if skills_file.exists():
            self.skills = json.loads(skills_file.read_text(encoding="utf-8"))

        self.patterns = {}
        if patterns_file.exists():
            self.patterns = json.loads(patterns_file.read_text(encoding="utf-8"))

    def save_memory(self):
        """Сохранить опыт — модули тренируются и сохраняют результат"""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        (MEMORY_DIR / "skills.json").write_text(
            json.dumps(self.skills, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        (MEMORY_DIR / "patterns.json").write_text(
            json.dumps(self.patterns, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def learn_skill(self, name: str, steps: list, description: str = ""):
        """
        Обучение: запомнить последовательность действий как навык.
        Например: 'очистка_temp' = [files.find *.tmp, files.delete каждый]
        В следующий раз ИИ выполнит это автоматически.
        """
        self.skills[name] = {
            "steps": steps,
            "description": description,
            "learned_at": datetime.now().isoformat(),
            "times_used": 0,
            "success_rate": 1.0
        }
        self.save_memory()
        return f"Навык '{name}' сохранён ({len(steps)} шагов)"

    def learn_pattern(self, trigger: str, action: dict):
        """
        Запомнить паттерн: если видишь X — делай Y.
        Модули сами регистрируют паттерны по мере работы.
        """
        self.patterns[trigger] = {
            "action": action,
            "learned_at": datetime.now().isoformat(),
            "times_triggered": 0
        }
        self.save_memory()

    async def process(self, user_input: str):
        """
        Главная функция — человек говорит, ИИ делает.
        1. Разобрать что хочет человек
        2. Найти подходящий навык или составить план
        3. Выполнить через модули
        4. Запомнить результат
        """
        timestamp = datetime.now().isoformat()

        # Проверяем, есть ли выученный навык для этого запроса
        skill_match = self._find_skill(user_input)
        if skill_match:
            result = await self._execute_skill(skill_match)
            self.history.append({
                "time": timestamp,
                "input": user_input,
                "method": "skill",
                "skill": skill_match,
                "result": result
            })
            # Наблюдение автотренера
            if self.trainer:
                self.trainer.observe(user_input, result)
            return result

        # Разбираем команду вручную
        parsed = self._parse_input(user_input)
        if parsed:
            result = await self._execute_parsed(parsed)
            self.history.append({
                "time": timestamp,
                "input": user_input,
                "method": "parsed",
                "parsed": parsed,
                "result": result
            })
            # Наблюдение автотренера
            if self.trainer:
                self.trainer.observe(user_input, result)
                # Каждые 5 команд — проверяем есть ли подсказки
                if sum(self.trainer.command_counts.values()) % 5 == 0:
                    suggestions = self.trainer.get_suggestions()
                    if suggestions:
                        result["_suggestions"] = suggestions
            return result

        # Не понял — показываем что умеем
        return await self._show_capabilities(user_input)

    def _find_skill(self, user_input: str):
        """Поиск подходящего навыка по ключевым словам"""
        input_lower = user_input.lower()
        for name, skill in self.skills.items():
            if name.lower() in input_lower:
                return name
            # Проверяем описание
            if skill.get("description") and any(
                word in input_lower
                for word in skill["description"].lower().split()
                if len(word) > 3
            ):
                return name
        return None

    async def _execute_skill(self, skill_name: str):
        """Выполнить выученный навык"""
        skill = self.skills[skill_name]
        results = []
        for step in skill["steps"]:
            module = step["module"]
            command = step["command"]
            args = step.get("args", {})
            r = await self.bus.send(module, command, **args)
            results.append(r)
        skill["times_used"] += 1
        self.save_memory()
        return {
            "skill": skill_name,
            "steps_completed": len(results),
            "results": results
        }

    def _parse_input(self, user_input: str):
        """
        Разбор команды. Формат:
          модуль.команда аргумент=значение
        Примеры:
          files.list path=C:/Users
          system.memory
          processes.list top=10
          network.ping host=google.com
        """
        parts = user_input.strip().split()
        if not parts:
            return None

        # Прямая команда: module.command
        if "." in parts[0]:
            module, command = parts[0].split(".", 1)
            kwargs = {}
            for part in parts[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    # Попробовать преобразовать числа
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                    kwargs[key] = value
            return {"module": module, "command": command, "args": kwargs}

        # Короткие команды
        shortcuts = {
            "help": {"module": "_brain", "command": "help"},
            "modules": {"module": "_brain", "command": "modules"},
            "status": {"module": "_brain", "command": "status"},
            "skills": {"module": "_brain", "command": "skills"},
            "history": {"module": "_brain", "command": "history"},
            "train": {"module": "_brain", "command": "train"},
            "save": {"module": "_brain", "command": "save"},
            "report": {"module": "_brain", "command": "report"},
            "suggest": {"module": "_brain", "command": "suggest"},
        }

        if parts[0].lower() in shortcuts:
            return {**shortcuts[parts[0].lower()], "args": {"raw": parts[1:]}}

        return None

    async def _execute_parsed(self, parsed: dict):
        """Выполнить разобранную команду"""
        module = parsed["module"]
        command = parsed["command"]
        args = parsed.get("args", {})

        # Внутренние команды мозга
        if module == "_brain":
            return await self._brain_command(command, args)

        # Отправить на шину
        return await self.bus.send(module, command, **args)

    async def _brain_command(self, command: str, args: dict):
        """Команды самого мозга"""
        if command == "help":
            return self._help()
        elif command == "modules":
            return self.bus.list_modules()
        elif command == "status":
            return self._status()
        elif command == "skills":
            return {name: {
                "description": s["description"],
                "times_used": s["times_used"],
                "steps": len(s["steps"])
            } for name, s in self.skills.items()}
        elif command == "history":
            return self.history[-10:]
        elif command == "save":
            self.save_memory()
            return "Память сохранена"
        elif command == "train":
            return self._train_help()
        elif command == "report":
            if self.trainer:
                return self.trainer.get_report()
            return "Автотренер не подключён"
        elif command == "suggest":
            if self.trainer:
                return self.trainer.get_suggestions()
            return "Автотренер не подключён"
        return {"error": f"Неизвестная команда мозга: {command}"}

    def _help(self):
        """Справка"""
        modules = self.bus.list_modules()
        lines = ["=== AI-OS Справка ===", ""]
        lines.append("Формат команд: модуль.команда аргумент=значение")
        lines.append("")
        lines.append("Доступные модули:")
        for name, info in modules.items():
            lines.append(f"  {name}: {info['description']}")
            for cmd, desc in info['commands'].items():
                lines.append(f"    .{cmd} — {desc}")
            lines.append("")
        lines.append("Системные команды:")
        lines.append("  help     — эта справка")
        lines.append("  modules  — список модулей")
        lines.append("  status   — состояние системы")
        lines.append("  skills   — выученные навыки")
        lines.append("  history  — история действий")
        lines.append("  train    — как обучить систему")
        lines.append("  save     — сохранить память")
        lines.append("  exit     — выход")
        return "\n".join(lines)

    def _train_help(self):
        """Как обучить систему"""
        return """
=== Обучение AI-OS ===

Чтобы научить систему новому навыку, используй интерактивный режим:
  1. Выполни нужные команды по очереди
  2. Скажи 'train' и система предложит сохранить последовательность как навык

Или обучи напрямую через JSON:
  train name=очистка description=Очистка временных файлов steps=[...]

Модули также учатся сами:
  - Запоминают частые команды
  - Оптимизируют порядок выполнения
  - Сохраняют паттерны ошибок
"""

    def _status(self):
        """Статус системы"""
        modules = self.bus.list_modules()
        return {
            "modules_total": len(modules),
            "modules_running": sum(1 for m in modules.values() if m["status"] == "running"),
            "skills_learned": len(self.skills),
            "patterns_learned": len(self.patterns),
            "actions_this_session": len(self.history),
            "memory_saved": (MEMORY_DIR / "skills.json").exists()
        }

    async def _show_capabilities(self, user_input: str):
        """Не поняли команду — показываем что умеем"""
        return {
            "message": f"Не понял команду: '{user_input}'",
            "hint": "Введи 'help' для списка команд или 'modules' для списка модулей",
            "format": "модуль.команда аргумент=значение",
            "examples": [
                "files.list path=C:/Users",
                "system.memory",
                "processes.list top=5",
                "network.ping host=google.com"
            ]
        }
