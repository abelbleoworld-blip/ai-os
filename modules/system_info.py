"""
Модуль: Системная информация
Кроссплатформенный (Linux/macOS/Windows) через psutil.
"""

import platform
import psutil
from datetime import datetime, timedelta
from core.module_base import SystemModule


class SystemInfoModule(SystemModule):
    def __init__(self):
        super().__init__("system", "Информация о системе и железе")
        self.register_command("overview", self.cmd_overview, "Общая информация о системе")
        self.register_command("memory", self.cmd_memory, "Состояние оперативной памяти")
        self.register_command("cpu", self.cmd_cpu, "Информация о процессоре и нагрузке")
        self.register_command("disk", self.cmd_disk, "Использование дисков")
        self.register_command("network", self.cmd_network, "Сетевые интерфейсы и IP")
        self.register_command("uptime", self.cmd_uptime, "Время работы системы")

    async def cmd_overview(self):
        mem = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=0.5)
        disk = psutil.disk_usage('/')
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor() or platform.machine(),
            "hostname": platform.node(),
            "python": platform.python_version(),
            "cpu_percent": cpu_pct,
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "memory_total_gb": round(mem.total / (1024**3), 1),
            "memory_used_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "disk_used_percent": disk.percent,
        }

    async def cmd_memory(self):
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "TotalGB": round(mem.total / (1024**3), 1),
            "UsedGB": round(mem.used / (1024**3), 1),
            "FreeGB": round(mem.available / (1024**3), 1),
            "UsedPercent": mem.percent,
            "SwapTotalGB": round(swap.total / (1024**3), 1),
            "SwapUsedPercent": swap.percent,
        }

    async def cmd_cpu(self):
        cpu_pct = psutil.cpu_percent(interval=1, percpu=True)
        freq = psutil.cpu_freq()
        return {
            "Name": platform.processor() or platform.machine(),
            "NumberOfCores": psutil.cpu_count(logical=False),
            "NumberOfLogicalProcessors": psutil.cpu_count(logical=True),
            "LoadPercentage": round(sum(cpu_pct) / len(cpu_pct), 1) if cpu_pct else 0,
            "PerCoreLoad": cpu_pct,
            "FrequencyMHz": round(freq.current, 0) if freq else None,
            "FrequencyMaxMHz": round(freq.max, 0) if freq and freq.max else None,
        }

    async def cmd_disk(self):
        partitions = psutil.disk_partitions()
        result = []
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                result.append({
                    "drive": p.mountpoint,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": round(usage.total / (1024**3), 1),
                    "used_gb": round(usage.used / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent": usage.percent,
                })
            except (PermissionError, OSError):
                pass
        return result

    async def cmd_network(self):
        addrs = psutil.net_if_addrs()
        result = []
        for iface, addr_list in addrs.items():
            for addr in addr_list:
                if addr.family.name == 'AF_INET' and addr.address != '127.0.0.1':
                    result.append({
                        "interface": iface,
                        "ip": addr.address,
                        "netmask": addr.netmask,
                    })
        return result

    async def cmd_uptime(self):
        boot = datetime.fromtimestamp(psutil.boot_time())
        delta = datetime.now() - boot
        return {
            "boot_time": boot.isoformat(),
            "uptime_days": delta.days,
            "uptime_hours": delta.seconds // 3600,
            "uptime_minutes": (delta.seconds % 3600) // 60,
            "uptime_str": f"{delta.days}d {delta.seconds // 3600}h {(delta.seconds % 3600) // 60}m",
        }
