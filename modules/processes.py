"""
Модуль: Процессы
Управляет запущенными программами. Как диспетчер задач — видит всё что работает,
может запустить или остановить программу.
"""

import subprocess
import asyncio
from core.module_base import SystemModule


class ProcessesModule(SystemModule):
    def __init__(self):
        super().__init__("processes", "Управление процессами и программами")
        self.register_command("list", self.cmd_list, "Список запущенных процессов")
        self.register_command("run", self.cmd_run, "Запустить программу")
        self.register_command("shell", self.cmd_shell, "Выполнить команду в терминале")
        self.register_command("kill", self.cmd_kill, "Завершить процесс по имени")

    async def cmd_list(self, top=20):
        """Список процессов — что сейчас работает"""
        result = subprocess.run(
            ["powershell.exe", "-Command",
             f"Get-Process | Sort-Object -Property WorkingSet64 -Descending | "
             f"Select-Object -First {top} Name, Id, "
             f"@{{N='MemMB';E={{[math]::Round($_.WorkingSet64/1MB,1)}}}}, "
             f"@{{N='CPU_s';E={{[math]::Round($_.CPU,1)}}}} | "
             f"ConvertTo-Json"],
            capture_output=True, text=True, timeout=15
        )
        import json
        try:
            return json.loads(result.stdout)
        except:
            return result.stdout

    async def cmd_run(self, program, args=""):
        """Запустить программу"""
        try:
            proc = subprocess.Popen(
                f"{program} {args}",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return f"Запущен: {program} (PID: {proc.pid})"
        except Exception as e:
            return f"Ошибка запуска: {e}"

    async def cmd_shell(self, command, timeout=30):
        """Выполнить команду и вернуть результат"""
        try:
            result = subprocess.run(
                command, shell=True,
                capture_output=True, text=True,
                timeout=timeout
            )
            return {
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:2000],
                "code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Команда не завершилась за {timeout} секунд"}

    async def cmd_kill(self, name):
        """Завершить процесс по имени"""
        result = subprocess.run(
            ["powershell.exe", "-Command", f"Stop-Process -Name '{name}' -Force -ErrorAction SilentlyContinue"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"Процесс '{name}' завершён"
        return f"Не удалось завершить '{name}': {result.stderr}"
