"""
Модуль: Watchdog (Сторож)
Автономный модуль здоровья системы.

Работает сам, без команд человека:
- Следит за памятью — если мало, предупреждает
- Следит за диском — если заканчивается место, сообщает
- Следит за модулями — если упал, перезапускает
- Ведёт журнал здоровья

Принцип: "не трогай то, что работает" — Watchdog вмешивается
ТОЛЬКО когда что-то идёт не так. Тихий, пока всё в порядке.
"""

import asyncio
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from core.module_base import SystemModule


HEALTH_LOG = Path(__file__).parent.parent / "memory" / "health_log.json"


class WatchdogModule(SystemModule):
    def __init__(self, bus=None):
        super().__init__("watchdog", "Мониторинг здоровья системы")
        self.bus = bus
        self.health_history = []
        self.alerts = []
        self.thresholds = {
            "memory_percent_warn": 80,     # предупредить если > 80% RAM
            "memory_percent_crit": 95,     # критично если > 95%
            "disk_percent_warn": 85,       # диск > 85%
            "disk_percent_crit": 95,       # диск > 95%
        }
        self._load_history()
        self.register_command("check", self.cmd_check, "Полная проверка здоровья")
        self.register_command("alerts", self.cmd_alerts, "Текущие предупреждения")
        self.register_command("history", self.cmd_history, "История здоровья")
        self.register_command("thresholds", self.cmd_thresholds, "Пороги срабатывания")
        self.register_command("set_threshold", self.cmd_set_threshold, "Изменить порог")
        self.register_command("heal", self.cmd_heal, "Попробовать исправить проблемы")

    def _load_history(self):
        if HEALTH_LOG.exists():
            try:
                data = json.loads(HEALTH_LOG.read_text(encoding="utf-8"))
                self.health_history = data.get("history", [])[-100:]
                self.thresholds.update(data.get("thresholds", {}))
            except:
                pass

    def _save_history(self):
        HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "history": self.health_history[-100:],
            "thresholds": self.thresholds,
            "last_check": datetime.now().isoformat()
        }
        HEALTH_LOG.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    async def cmd_check(self):
        """Полная проверка — как врачебный осмотр"""
        self.alerts = []
        report = {
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }

        # 1. Проверка памяти
        mem = await self._check_memory()
        report["checks"]["memory"] = mem

        # 2. Проверка дисков
        disk = await self._check_disks()
        report["checks"]["disks"] = disk

        # 3. Проверка модулей
        if self.bus:
            modules = await self._check_modules()
            report["checks"]["modules"] = modules

        # 4. Общий статус
        if self.alerts:
            report["status"] = "WARNING" if not any(a["level"] == "CRITICAL" for a in self.alerts) else "CRITICAL"
        else:
            report["status"] = "OK"

        report["alerts"] = self.alerts
        self.health_history.append(report)
        self._save_history()

        return report

    async def _check_memory(self):
        """Проверка RAM"""
        try:
            result = subprocess.run(
                ["powershell.exe", "-Command",
                 "Get-CimInstance Win32_OperatingSystem | "
                 "Select-Object @{N='TotalMB';E={[math]::Round($_.TotalVisibleMemorySize/1KB)}}, "
                 "@{N='FreeMB';E={[math]::Round($_.FreePhysicalMemory/1KB)}}, "
                 "@{N='UsedPercent';E={[math]::Round(($_.TotalVisibleMemorySize-$_.FreePhysicalMemory)/$_.TotalVisibleMemorySize*100,1)}} | "
                 "ConvertTo-Json"],
                capture_output=True, text=True, timeout=10
            )
            mem = json.loads(result.stdout)
            used_pct = mem["UsedPercent"]

            if used_pct >= self.thresholds["memory_percent_crit"]:
                self.alerts.append({
                    "level": "CRITICAL",
                    "source": "memory",
                    "message": f"Критически мало RAM: {used_pct}% занято"
                })
            elif used_pct >= self.thresholds["memory_percent_warn"]:
                self.alerts.append({
                    "level": "WARNING",
                    "source": "memory",
                    "message": f"RAM загружена: {used_pct}%"
                })

            return {"status": "ok", "used_percent": used_pct, **mem}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _check_disks(self):
        """Проверка дисков"""
        import os
        import string
        results = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                try:
                    usage = shutil.disk_usage(drive)
                    pct = round(usage.used / usage.total * 100, 1)
                    free_gb = round(usage.free / (1024**3), 1)

                    status = "ok"
                    if pct >= self.thresholds["disk_percent_crit"]:
                        status = "critical"
                        self.alerts.append({
                            "level": "CRITICAL",
                            "source": f"disk_{letter}",
                            "message": f"Диск {drive} почти полон: {pct}% ({free_gb} GB свободно)"
                        })
                    elif pct >= self.thresholds["disk_percent_warn"]:
                        status = "warning"
                        self.alerts.append({
                            "level": "WARNING",
                            "source": f"disk_{letter}",
                            "message": f"Диск {drive} заполняется: {pct}% ({free_gb} GB свободно)"
                        })

                    results.append({
                        "drive": drive,
                        "used_percent": pct,
                        "free_gb": free_gb,
                        "status": status
                    })
                except PermissionError:
                    pass
        return results

    async def _check_modules(self):
        """Проверка модулей системы"""
        results = {}
        for name, module in self.bus.modules.items():
            if name == "watchdog":
                continue
            info = module.get_info()
            if info["status"] != "running":
                self.alerts.append({
                    "level": "WARNING",
                    "source": f"module_{name}",
                    "message": f"Модуль '{name}' не запущен (статус: {info['status']})"
                })
                results[name] = "NOT RUNNING"
            else:
                results[name] = "OK"
        return results

    async def cmd_alerts(self):
        """Показать текущие предупреждения"""
        if not self.alerts:
            # Запустить проверку если ещё не было
            await self.cmd_check()
        if not self.alerts:
            return "Всё в порядке. Предупреждений нет."
        return self.alerts

    async def cmd_history(self, count=10):
        """История проверок"""
        return self.health_history[-int(count):]

    async def cmd_thresholds(self):
        """Текущие пороги"""
        return self.thresholds

    async def cmd_set_threshold(self, name, value):
        """Изменить порог — самонастройка"""
        if name in self.thresholds:
            old = self.thresholds[name]
            self.thresholds[name] = float(value)
            self._save_history()
            return f"Порог '{name}': {old} -> {value}"
        return f"Неизвестный порог: {name}. Доступные: {list(self.thresholds.keys())}"

    async def cmd_heal(self):
        """Попытка автоматически исправить проблемы"""
        if not self.alerts:
            await self.cmd_check()

        actions_taken = []

        for alert in self.alerts:
            # Модуль упал — перезапускаем
            if alert["source"].startswith("module_"):
                module_name = alert["source"].replace("module_", "")
                if module_name in self.bus.modules:
                    await self.bus.modules[module_name].restart()
                    actions_taken.append(f"Перезапущен модуль '{module_name}'")

            # Критически мало памяти — найти тяжёлые процессы
            if alert["source"] == "memory" and alert["level"] == "CRITICAL":
                actions_taken.append(
                    "Критически мало RAM. Рекомендация: processes.list top=10 — посмотреть что ест память"
                )

            # Диск полон
            if alert["source"].startswith("disk_") and alert["level"] == "CRITICAL":
                drive = alert["source"].replace("disk_", "") + ":\\"
                actions_taken.append(
                    f"Диск {drive} почти полон. Рекомендация: files.find pattern=*.tmp path={drive}"
                )

        if not actions_taken:
            return "Нет проблем, требующих вмешательства"

        return {"actions": actions_taken}
