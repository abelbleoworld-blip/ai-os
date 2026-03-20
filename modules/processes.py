"""
Модуль: Процессы
Кроссплатформенный через psutil.
"""

import subprocess
import asyncio
import psutil
from core.module_base import SystemModule


class ProcessesModule(SystemModule):
    def __init__(self):
        super().__init__("processes", "Управление процессами и программами")
        self.register_command("list", self.cmd_list, "Список запущенных процессов")
        self.register_command("run", self.cmd_run, "Запустить программу")
        self.register_command("shell", self.cmd_shell, "Выполнить команду в терминале")
        self.register_command("kill", self.cmd_kill, "Завершить процесс по имени")

    async def cmd_list(self, top=20):
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_times']):
            try:
                info = p.info
                mem_mb = round(info['memory_info'].rss / (1024 * 1024), 1) if info['memory_info'] else 0
                cpu_s = round(sum(info['cpu_times'][:2]), 1) if info['cpu_times'] else 0
                procs.append({
                    "Name": info['name'],
                    "Id": info['pid'],
                    "MemMB": mem_mb,
                    "CPU_s": cpu_s,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x['MemMB'], reverse=True)
        return procs[:int(top)]

    async def cmd_run(self, program, args=""):
        try:
            proc = subprocess.Popen(
                f"{program} {args}", shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            return f"Запущен: {program} (PID: {proc.pid})"
        except Exception as e:
            return f"Ошибка запуска: {e}"

    async def cmd_shell(self, command, timeout=30):
        try:
            result = subprocess.run(
                command, shell=True,
                capture_output=True, text=True, timeout=timeout
            )
            return {
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:2000],
                "code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Команда не завершилась за {timeout} секунд"}

    async def cmd_kill(self, name):
        killed = 0
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name'] and name.lower() in p.info['name'].lower():
                    p.kill()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed:
            return f"Завершено {killed} процессов '{name}'"
        return f"Процесс '{name}' не найден"
