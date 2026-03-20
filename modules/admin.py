"""
Модуль: Admin (Самоуправление)
AI-OS обновляет и управляет собой без SSH.

Команды из чата:
  "обновись" → git pull + docker compose restart
  "admin.logs" → последние логи
  "admin.status" → git, docker, system
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from core.module_base import SystemModule

APP_DIR = Path("/app")


class AdminModule(SystemModule):
    def __init__(self, bus=None):
        super().__init__("admin", "Самоуправление — обновление, логи, деплой")
        self.bus = bus
        self.deploy_log = []

        self.register_command("update", self.cmd_update, "Git pull + перезапуск")
        self.register_command("status", self.cmd_status, "Статус git, docker, системы")
        self.register_command("logs", self.cmd_logs, "Последние логи AI-OS")
        self.register_command("restart", self.cmd_restart, "Перезапустить контейнер")
        self.register_command("version", self.cmd_version, "Текущая версия (git)")
        self.register_command("deploy_log", self.cmd_deploy_log, "История деплоев")
        self.register_command("shell", self.cmd_shell, "Выполнить команду на сервере")
        self.register_command("env", self.cmd_env, "Показать переменные окружения")

    def _run(self, cmd, timeout=30):
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=str(APP_DIR))
            return {"stdout": r.stdout.strip()[-2000:], "stderr": r.stderr.strip()[-500:], "code": r.returncode}
        except subprocess.TimeoutExpired:
            return {"error": f"Timeout {timeout}s", "code": -1}
        except Exception as e:
            return {"error": str(e), "code": -1}

    async def cmd_update(self):
        """Git pull + rebuild. AI-OS обновляет себя."""
        ts = datetime.now().isoformat()
        steps = []

        # 1. Git pull
        pull = self._run("git pull origin master", timeout=30)
        steps.append({"step": "git pull", **pull})

        if pull.get("code") != 0:
            self.deploy_log.append({"time": ts, "status": "failed", "step": "git pull", "error": pull.get("stderr", "")})
            return {"status": "failed", "step": "git pull", "error": pull.get("stderr", ""), "details": steps}

        # 2. Check if anything changed
        if "Already up to date" in pull.get("stdout", ""):
            return {"status": "already_up_to_date", "message": "Уже последняя версия.", "details": steps}

        # 3. Restart (docker compose will pick up new code via volume or rebuild)
        # Since we're INSIDE the container, we can't rebuild ourselves
        # But we can signal that a restart is needed
        self.deploy_log.append({
            "time": ts,
            "status": "updated",
            "changes": pull.get("stdout", ""),
        })

        return {
            "status": "updated",
            "message": "Код обновлён. Для применения нужен перезапуск контейнера.",
            "changes": pull.get("stdout", "")[:500],
            "hint": "Выполни на хосте: docker compose up --build -d",
            "details": steps,
        }

    async def cmd_status(self):
        """Полный статус системы"""
        git_log = self._run("git log --oneline -5")
        git_branch = self._run("git branch --show-current")
        git_status = self._run("git status --short")
        uptime = self._run("cat /proc/uptime")

        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        uptime_s = float(uptime.get("stdout", "0").split()[0]) if uptime.get("stdout") else 0
        uptime_h = int(uptime_s // 3600)
        uptime_m = int((uptime_s % 3600) // 60)

        return {
            "git": {
                "branch": git_branch.get("stdout", "?"),
                "changes": git_status.get("stdout", "clean") or "clean",
                "recent_commits": git_log.get("stdout", "").split("\n")[:5],
            },
            "system": {
                "uptime": f"{uptime_h}h {uptime_m}m",
                "memory_percent": mem.percent,
                "disk_percent": disk.percent,
                "python": self._run("python --version").get("stdout", ""),
            },
            "deploy_count": len(self.deploy_log),
        }

    async def cmd_logs(self, lines=30):
        """Последние логи"""
        log_file = APP_DIR / "logs" / "aios.log"
        if log_file.exists():
            text = log_file.read_text(encoding="utf-8", errors="replace")
            return "\n".join(text.split("\n")[-int(lines):])
        return "Log file not found"

    async def cmd_restart(self):
        """Перезапуск — изнутри контейнера можно только убить процесс"""
        return {
            "message": "Для перезапуска выполни на хосте:",
            "command": "cd /opt/ai-os && docker compose restart",
            "hint": "Или через admin.shell если есть docker socket",
        }

    async def cmd_version(self):
        """Текущая версия"""
        commit = self._run("git log --oneline -1")
        branch = self._run("git branch --show-current")
        tag = self._run("git describe --tags --always")
        remote = self._run("git remote get-url origin")
        behind = self._run("git rev-list HEAD..origin/master --count 2>/dev/null")

        return {
            "commit": commit.get("stdout", "?"),
            "branch": branch.get("stdout", "?"),
            "tag": tag.get("stdout", "?"),
            "remote": remote.get("stdout", "?"),
            "behind_remote": behind.get("stdout", "0") + " commits",
        }

    async def cmd_deploy_log(self):
        """История деплоев"""
        if not self.deploy_log:
            return "Деплоев ещё не было"
        return self.deploy_log[-10:]

    async def cmd_shell(self, command, timeout=15):
        """Выполнить произвольную команду"""
        # Safety: block dangerous commands
        dangerous = ["rm -rf /", "mkfs", "dd if=", ":(){", "fork bomb"]
        for d in dangerous:
            if d in command:
                return {"error": f"Blocked dangerous command: {d}"}
        return self._run(command, timeout=int(timeout))

    async def cmd_env(self):
        """Показать переменные окружения (без секретов)"""
        safe = {}
        for k, v in os.environ.items():
            if any(s in k.upper() for s in ["KEY", "TOKEN", "SECRET", "PASSWORD"]):
                safe[k] = v[:4] + "***" + v[-4:] if len(v) > 8 else "***"
            else:
                safe[k] = v
        return safe
