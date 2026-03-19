"""
Модуль: Системная информация
Глаза и уши ИИ — показывает состояние железа, памяти, CPU, сети.
Как датчики в здании: температура, нагрузка, свободное место.
"""

import platform
import subprocess
import json
from core.module_base import SystemModule


class SystemInfoModule(SystemModule):
    def __init__(self):
        super().__init__("system", "Информация о системе и железе")
        self.register_command("overview", self.cmd_overview, "Общая информация о системе")
        self.register_command("memory", self.cmd_memory, "Состояние оперативной памяти")
        self.register_command("cpu", self.cmd_cpu, "Информация о процессоре и нагрузке")
        self.register_command("network", self.cmd_network, "Сетевые интерфейсы и IP")
        self.register_command("uptime", self.cmd_uptime, "Время работы системы")

    async def cmd_overview(self):
        """Общая картина — ИИ понимает где он работает"""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "python": platform.python_version(),
        }

    async def cmd_memory(self):
        """Сколько памяти свободно"""
        result = subprocess.run(
            ["powershell.exe", "-Command",
             "Get-CimInstance Win32_OperatingSystem | "
             "Select-Object @{N='TotalGB';E={[math]::Round($_.TotalVisibleMemorySize/1MB,1)}}, "
             "@{N='FreeGB';E={[math]::Round($_.FreePhysicalMemory/1MB,1)}}, "
             "@{N='UsedPercent';E={[math]::Round(($_.TotalVisibleMemorySize - $_.FreePhysicalMemory) / $_.TotalVisibleMemorySize * 100, 1)}} | "
             "ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        try:
            return json.loads(result.stdout)
        except:
            return result.stdout

    async def cmd_cpu(self):
        """Нагрузка на процессор"""
        result = subprocess.run(
            ["powershell.exe", "-Command",
             "Get-CimInstance Win32_Processor | "
             "Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, "
             "LoadPercentage, MaxClockSpeed | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        try:
            return json.loads(result.stdout)
        except:
            return result.stdout

    async def cmd_network(self):
        """Сетевые подключения"""
        result = subprocess.run(
            ["powershell.exe", "-Command",
             "Get-NetIPAddress -AddressFamily IPv4 | "
             "Where-Object {$_.IPAddress -ne '127.0.0.1'} | "
             "Select-Object InterfaceAlias, IPAddress | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        try:
            return json.loads(result.stdout)
        except:
            return result.stdout

    async def cmd_uptime(self):
        """Сколько работает система"""
        result = subprocess.run(
            ["powershell.exe", "-Command",
             "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | "
             "Select-Object Days, Hours, Minutes | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        try:
            return json.loads(result.stdout)
        except:
            return result.stdout
