"""
Модуль: Watchdog (Сторож)
Кроссплатформенный через psutil.
"""

import asyncio
import json
import psutil
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
            "memory_percent_warn": 80,
            "memory_percent_crit": 95,
            "disk_percent_warn": 85,
            "disk_percent_crit": 95,
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
        self.alerts = []
        report = {"timestamp": datetime.now().isoformat(), "checks": {}}

        mem = await self._check_memory()
        report["checks"]["memory"] = mem

        disk = await self._check_disks()
        report["checks"]["disks"] = disk

        if self.bus:
            modules = await self._check_modules()
            report["checks"]["modules"] = modules

        if self.alerts:
            report["status"] = "CRITICAL" if any(a["level"] == "CRITICAL" for a in self.alerts) else "WARNING"
        else:
            report["status"] = "OK"

        report["alerts"] = self.alerts
        self.health_history.append(report)
        self._save_history()
        return report

    async def _check_memory(self):
        try:
            mem = psutil.virtual_memory()
            used_pct = mem.percent
            result = {
                "status": "ok",
                "used_percent": used_pct,
                "TotalMB": round(mem.total / (1024**2)),
                "FreeMB": round(mem.available / (1024**2)),
                "UsedPercent": used_pct,
            }

            if used_pct >= self.thresholds["memory_percent_crit"]:
                self.alerts.append({"level": "CRITICAL", "source": "memory", "message": f"Критически мало RAM: {used_pct}% занято"})
            elif used_pct >= self.thresholds["memory_percent_warn"]:
                self.alerts.append({"level": "WARNING", "source": "memory", "message": f"RAM загружена: {used_pct}%"})

            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _check_disks(self):
        results = []
        seen = set()
        for p in psutil.disk_partitions():
            # Skip Docker internal mounts
            if p.mountpoint in ('/etc/resolv.conf', '/etc/hostname', '/etc/hosts'):
                continue
            try:
                usage = psutil.disk_usage(p.mountpoint)
                pct = usage.percent
                free_gb = round(usage.free / (1024**3), 1)

                status = "ok"
                if pct >= self.thresholds["disk_percent_crit"]:
                    status = "critical"
                    self.alerts.append({"level": "CRITICAL", "source": f"disk_{p.mountpoint}", "message": f"Диск {p.mountpoint} почти полон: {pct}% ({free_gb} GB свободно)"})
                elif pct >= self.thresholds["disk_percent_warn"]:
                    status = "warning"
                    self.alerts.append({"level": "WARNING", "source": f"disk_{p.mountpoint}", "message": f"Диск {p.mountpoint} заполняется: {pct}% ({free_gb} GB свободно)"})

                results.append({"drive": p.mountpoint, "mountpoint": p.mountpoint, "used_percent": pct, "free_gb": free_gb, "percent": pct, "status": status})
            except (PermissionError, OSError):
                pass
        return results

    async def _check_modules(self):
        results = {}
        for name, module in self.bus.modules.items():
            if name == "watchdog":
                continue
            info = module.get_info()
            if info["status"] != "running":
                self.alerts.append({"level": "WARNING", "source": f"module_{name}", "message": f"Модуль '{name}' не запущен"})
                results[name] = "NOT RUNNING"
            else:
                results[name] = "OK"
        return results

    async def cmd_alerts(self):
        if not self.alerts:
            await self.cmd_check()
        if not self.alerts:
            return "Всё в порядке. Предупреждений нет."
        return self.alerts

    async def cmd_history(self, count=10):
        return self.health_history[-int(count):]

    async def cmd_thresholds(self):
        return self.thresholds

    async def cmd_set_threshold(self, name, value):
        if name in self.thresholds:
            old = self.thresholds[name]
            self.thresholds[name] = float(value)
            self._save_history()
            return f"Порог '{name}': {old} -> {value}"
        return f"Неизвестный порог: {name}. Доступные: {list(self.thresholds.keys())}"

    async def cmd_heal(self):
        if not self.alerts:
            await self.cmd_check()
        actions_taken = []
        for alert in self.alerts:
            if alert["source"].startswith("module_"):
                module_name = alert["source"].replace("module_", "")
                if module_name in self.bus.modules:
                    await self.bus.modules[module_name].restart()
                    actions_taken.append(f"Перезапущен модуль '{module_name}'")
            if alert["source"] == "memory" and alert["level"] == "CRITICAL":
                actions_taken.append("Критически мало RAM. Рекомендация: processes.list top=10")
            if alert["source"].startswith("disk_") and alert["level"] == "CRITICAL":
                actions_taken.append(f"Диск почти полон. Рекомендация: найти большие файлы")
        if not actions_taken:
            return "Нет проблем, требующих вмешательства"
        return {"actions": actions_taken}
