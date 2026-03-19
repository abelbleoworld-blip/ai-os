"""
Модуль: Scheduler (Планировщик)
Автоматические задачи по расписанию.

"каждые 5 минут проверяй здоровье"
"каждый час сканируй память"
"через 30 минут напомни"

Задачи сохраняются между сессиями.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from core.module_base import SystemModule


SCHEDULE_FILE = Path(__file__).parent.parent / "memory" / "schedule.json"


class SchedulerModule(SystemModule):
    def __init__(self, bus=None):
        super().__init__("scheduler", "Планировщик автоматических задач")
        self.bus = bus
        self.tasks = {}
        self.task_id = 0
        self.running_tasks = {}
        self._load()
        self.register_command("add", self.cmd_add, "Добавить задачу (interval_sec, module, command)")
        self.register_command("list", self.cmd_list, "Показать все задачи")
        self.register_command("remove", self.cmd_remove, "Удалить задачу по ID")
        self.register_command("pause", self.cmd_pause, "Приостановить задачу")
        self.register_command("resume", self.cmd_resume, "Возобновить задачу")
        self.register_command("history", self.cmd_history, "История выполнения")
        self.register_command("presets", self.cmd_presets, "Готовые наборы задач")
        self.register_command("apply_preset", self.cmd_apply_preset, "Применить готовый набор")

    def _load(self):
        if SCHEDULE_FILE.exists():
            try:
                data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
                self.tasks = data.get("tasks", {})
                self.task_id = data.get("next_id", 0)
            except:
                pass

    def _save(self):
        SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {"tasks": self.tasks, "next_id": self.task_id}
        SCHEDULE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def start(self):
        await super().start()
        # Запускаем все активные задачи
        for tid, task in self.tasks.items():
            if task.get("active", True):
                self._start_task(tid)

    async def stop(self):
        # Останавливаем все задачи
        for tid in list(self.running_tasks.keys()):
            self.running_tasks[tid].cancel()
        self.running_tasks.clear()
        await super().stop()

    def _start_task(self, tid):
        if tid in self.running_tasks:
            return
        task = self.tasks.get(tid)
        if not task or not self.bus:
            return

        async def runner():
            while True:
                await asyncio.sleep(task["interval_sec"])
                try:
                    result = await self.bus.send(task["module"], task["command"], **task.get("args", {}))
                    # Записать в историю
                    if "history" not in task:
                        task["history"] = []
                    task["history"].append({
                        "time": datetime.now().isoformat(),
                        "status": "ok" if result.get("status") == "ok" else "error"
                    })
                    # Держим только последние 20
                    task["history"] = task["history"][-20:]
                    task["last_run"] = datetime.now().isoformat()
                    task["run_count"] = task.get("run_count", 0) + 1
                    self._save()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    if "history" not in task:
                        task["history"] = []
                    task["history"].append({
                        "time": datetime.now().isoformat(),
                        "status": "error",
                        "error": str(e)
                    })

        self.running_tasks[tid] = asyncio.create_task(runner())

    async def cmd_add(self, interval_sec=300, module="watchdog", command="check", name="", **kwargs):
        """Добавить задачу"""
        interval_sec = int(interval_sec)
        self.task_id += 1
        tid = str(self.task_id)

        if not name:
            name = f"{module}.{command} каждые {interval_sec}с"

        self.tasks[tid] = {
            "name": name,
            "module": module,
            "command": command,
            "args": {k: v for k, v in kwargs.items() if k not in ("interval_sec", "module", "command", "name")},
            "interval_sec": interval_sec,
            "active": True,
            "created": datetime.now().isoformat(),
            "run_count": 0,
            "last_run": None,
            "history": []
        }
        self._save()
        self._start_task(tid)

        return {
            "id": tid,
            "name": name,
            "interval": f"{interval_sec} сек ({interval_sec//60} мин)" if interval_sec >= 60 else f"{interval_sec} сек",
            "action": f"{module}.{command}",
            "status": "active"
        }

    async def cmd_list(self):
        """Показать задачи"""
        if not self.tasks:
            return "Задач нет. Добавь: scheduler.add interval_sec=300 module=watchdog command=check"

        result = []
        for tid, t in self.tasks.items():
            mins = t["interval_sec"] // 60
            result.append({
                "id": tid,
                "name": t["name"],
                "action": f"{t['module']}.{t['command']}",
                "interval": f"{mins} мин" if mins > 0 else f"{t['interval_sec']} сек",
                "active": t["active"],
                "runs": t.get("run_count", 0),
                "last_run": t.get("last_run"),
            })
        return result

    async def cmd_remove(self, id=""):
        """Удалить задачу"""
        if id in self.running_tasks:
            self.running_tasks[id].cancel()
            del self.running_tasks[id]
        if id in self.tasks:
            name = self.tasks[id]["name"]
            del self.tasks[id]
            self._save()
            return f"Задача #{id} '{name}' удалена"
        return f"Задача #{id} не найдена"

    async def cmd_pause(self, id=""):
        """Приостановить"""
        if id in self.tasks:
            self.tasks[id]["active"] = False
            if id in self.running_tasks:
                self.running_tasks[id].cancel()
                del self.running_tasks[id]
            self._save()
            return f"Задача #{id} приостановлена"
        return f"Задача #{id} не найдена"

    async def cmd_resume(self, id=""):
        """Возобновить"""
        if id in self.tasks:
            self.tasks[id]["active"] = True
            self._start_task(id)
            self._save()
            return f"Задача #{id} возобновлена"
        return f"Задача #{id} не найдена"

    async def cmd_history(self, id=""):
        """История выполнения"""
        if id and id in self.tasks:
            return self.tasks[id].get("history", [])
        # Общая история
        all_history = []
        for tid, t in self.tasks.items():
            for h in t.get("history", [])[-5:]:
                all_history.append({"task": t["name"], "id": tid, **h})
        all_history.sort(key=lambda x: x.get("time", ""), reverse=True)
        return all_history[:20]

    async def cmd_presets(self):
        """Готовые наборы"""
        return {
            "basic_monitoring": {
                "name": "Базовый мониторинг",
                "tasks": [
                    {"name": "Проверка здоровья", "module": "watchdog", "command": "check", "interval_sec": 300},
                    {"name": "Мониторинг памяти", "module": "system", "command": "memory", "interval_sec": 600},
                ]
            },
            "full_monitoring": {
                "name": "Полный мониторинг",
                "tasks": [
                    {"name": "Здоровье", "module": "watchdog", "command": "check", "interval_sec": 180},
                    {"name": "Память", "module": "system", "command": "memory", "interval_sec": 300},
                    {"name": "Диски", "module": "files", "command": "disk_usage", "interval_sec": 600},
                    {"name": "Процессы", "module": "processes", "command": "list", "interval_sec": 300},
                ]
            },
            "night_watch": {
                "name": "Ночной дозор",
                "tasks": [
                    {"name": "Здоровье", "module": "watchdog", "command": "check", "interval_sec": 900},
                    {"name": "Диски", "module": "files", "command": "disk_usage", "interval_sec": 1800},
                ]
            }
        }

    async def cmd_apply_preset(self, preset="basic_monitoring"):
        """Применить пресет"""
        presets = await self.cmd_presets()
        if preset not in presets:
            return f"Пресет '{preset}' не найден. Доступные: {list(presets.keys())}"

        added = []
        for t in presets[preset]["tasks"]:
            result = await self.cmd_add(
                interval_sec=t["interval_sec"],
                module=t["module"],
                command=t["command"],
                name=t["name"]
            )
            added.append(result)

        return {
            "preset": preset,
            "name": presets[preset]["name"],
            "tasks_added": len(added),
            "tasks": added
        }
