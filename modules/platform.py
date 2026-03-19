"""
Модуль: Platform (Кроссплатформенная интеграция)
Позволяет AI-OS работать на любой ОС.

Принцип: один и тот же запрос — разные команды под капотом.
  "покажи процессы" → Windows: Get-Process / Linux: ps aux / macOS: ps aux
  "свободная память" → Windows: WMI / Linux: /proc/meminfo / macOS: vm_stat

Модуль определяет текущую ОС и маршрутизирует команды
через правильный системный стек.
"""

import platform
import subprocess
import json
import sys
from core.module_base import SystemModule


class PlatformModule(SystemModule):
    def __init__(self):
        super().__init__("platform", "Кроссплатформенная интеграция (Windows/Linux/macOS)")
        self.current_os = platform.system().lower()  # windows / linux / darwin
        self.register_command("detect", self.cmd_detect, "Определить текущую ОС и возможности")
        self.register_command("exec", self.cmd_exec, "Выполнить команду для текущей ОС")
        self.register_command("translate", self.cmd_translate, "Перевести команду между ОС")
        self.register_command("compat", self.cmd_compat, "Проверить совместимость команды")
        self.register_command("stacks", self.cmd_stacks, "Показать системные стеки всех ОС")

        # Таблица эквивалентных команд
        self.command_map = {
            "list_processes": {
                "windows": {"cmd": ["powershell.exe", "-Command", "Get-Process | Select-Object -First 20 Name, Id, @{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | ConvertTo-Json"], "parse": "json"},
                "linux": {"cmd": ["ps", "aux", "--sort=-%mem"], "parse": "text"},
                "darwin": {"cmd": ["ps", "aux", "-m"], "parse": "text"},
            },
            "memory_info": {
                "windows": {"cmd": ["powershell.exe", "-Command", "Get-CimInstance Win32_OperatingSystem | Select-Object @{N='TotalGB';E={[math]::Round($_.TotalVisibleMemorySize/1MB,1)}}, @{N='FreeGB';E={[math]::Round($_.FreePhysicalMemory/1MB,1)}} | ConvertTo-Json"], "parse": "json"},
                "linux": {"cmd": ["free", "-h"], "parse": "text"},
                "darwin": {"cmd": ["vm_stat"], "parse": "text"},
            },
            "disk_usage": {
                "windows": {"cmd": ["powershell.exe", "-Command", "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}}, @{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}} | ConvertTo-Json"], "parse": "json"},
                "linux": {"cmd": ["df", "-h"], "parse": "text"},
                "darwin": {"cmd": ["df", "-h"], "parse": "text"},
            },
            "network_info": {
                "windows": {"cmd": ["powershell.exe", "-Command", "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress | ConvertTo-Json"], "parse": "json"},
                "linux": {"cmd": ["ip", "addr", "show"], "parse": "text"},
                "darwin": {"cmd": ["ifconfig"], "parse": "text"},
            },
            "system_info": {
                "windows": {"cmd": ["systeminfo"], "parse": "text"},
                "linux": {"cmd": ["uname", "-a"], "parse": "text"},
                "darwin": {"cmd": ["sw_vers"], "parse": "text"},
            },
            "list_services": {
                "windows": {"cmd": ["powershell.exe", "-Command", "Get-Service | Where-Object Status -eq Running | Select-Object -First 20 Name, DisplayName | ConvertTo-Json"], "parse": "json"},
                "linux": {"cmd": ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"], "parse": "text"},
                "darwin": {"cmd": ["launchctl", "list"], "parse": "text"},
            },
            "flush_dns": {
                "windows": {"cmd": ["ipconfig", "/flushdns"], "parse": "text"},
                "linux": {"cmd": ["systemd-resolve", "--flush-caches"], "parse": "text"},
                "darwin": {"cmd": ["dscacheutil", "-flushcache"], "parse": "text"},
            },
            "open_file": {
                "windows": {"cmd": ["start", ""], "parse": "text"},
                "linux": {"cmd": ["xdg-open"], "parse": "text"},
                "darwin": {"cmd": ["open"], "parse": "text"},
            },
            "find_files": {
                "windows": {"cmd": ["powershell.exe", "-Command", "Get-ChildItem -Recurse -Name"], "parse": "text"},
                "linux": {"cmd": ["find", ".", "-name"], "parse": "text"},
                "darwin": {"cmd": ["find", ".", "-name"], "parse": "text"},
            },
            "package_install": {
                "windows": {"cmd": ["winget", "install"], "parse": "text"},
                "linux_apt": {"cmd": ["apt", "install", "-y"], "parse": "text"},
                "linux_dnf": {"cmd": ["dnf", "install", "-y"], "parse": "text"},
                "linux_pacman": {"cmd": ["pacman", "-S", "--noconfirm"], "parse": "text"},
                "darwin": {"cmd": ["brew", "install"], "parse": "text"},
            },
            "package_list": {
                "windows": {"cmd": ["winget", "list"], "parse": "text"},
                "linux_apt": {"cmd": ["dpkg", "--list"], "parse": "text"},
                "linux_dnf": {"cmd": ["rpm", "-qa"], "parse": "text"},
                "darwin": {"cmd": ["brew", "list"], "parse": "text"},
            },
        }

    async def cmd_detect(self):
        """Определить ОС и возможности"""
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "current_stack": self.current_os,
            "available_commands": list(self.command_map.keys()),
            "stacks_supported": ["windows", "linux", "darwin (macOS)"],
        }

        # Определяем доступные инструменты
        tools = {}
        tool_checks = {
            "winget": "winget --version",
            "choco": "choco --version",
            "git": "git --version",
            "node": "node --version",
            "python": "python --version",
            "docker": "docker --version",
            "wsl": "wsl --status",
        }
        for name, cmd in tool_checks.items():
            try:
                r = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    tools[name] = r.stdout.strip().split('\n')[0]
            except:
                pass

        info["installed_tools"] = tools
        return info

    async def cmd_exec(self, action, **kwargs):
        """Выполнить кроссплатформенную команду"""
        if action not in self.command_map:
            return {
                "error": f"Неизвестное действие: {action}",
                "available": list(self.command_map.keys())
            }

        action_map = self.command_map[action]

        # Найти команду для текущей ОС
        os_key = self.current_os
        if os_key not in action_map:
            # Попробовать варианты (linux_apt, linux_dnf и т.д.)
            for key in action_map:
                if key.startswith(os_key):
                    os_key = key
                    break
            else:
                return {"error": f"Действие '{action}' не поддерживается на {self.current_os}"}

        cmd_info = action_map[os_key]
        cmd = cmd_info["cmd"]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            output = result.stdout

            if cmd_info["parse"] == "json":
                try:
                    output = json.loads(output)
                except:
                    pass

            return {
                "action": action,
                "os": self.current_os,
                "command_used": " ".join(cmd),
                "result": output
            }
        except Exception as e:
            return {"error": str(e)}

    async def cmd_translate(self, command, from_os="windows", to_os="linux"):
        """Показать эквивалент команды на другой ОС"""
        translations = {
            # Windows → Linux
            "dir": "ls -la",
            "cls": "clear",
            "copy": "cp",
            "move": "mv",
            "del": "rm",
            "rmdir": "rm -rf",
            "type": "cat",
            "find": "grep",
            "findstr": "grep",
            "tasklist": "ps aux",
            "taskkill": "kill / killall",
            "ipconfig": "ip addr / ifconfig",
            "netstat": "ss / netstat",
            "systeminfo": "uname -a / hostnamectl",
            "sc query": "systemctl status",
            "sc start": "systemctl start",
            "sc stop": "systemctl stop",
            "sfc /scannow": "fsck / apt --fix-broken install",
            "chkdsk": "fsck",
            "regedit": "нет аналога (Linux не использует реестр)",
            "msconfig": "systemctl / update-rc.d",
            "control panel": "настройки через файлы конфигурации",
            "msiexec": "dpkg -i / rpm -i",
            "winget install": "apt install / dnf install / pacman -S",
            "powershell": "bash / zsh",
            "notepad": "nano / vim / gedit",
            "explorer": "nautilus / dolphin / thunar",
        }

        result = {"from_os": from_os, "to_os": to_os}

        if command.lower() in translations:
            result["original"] = command
            result["translated"] = translations[command.lower()]
        else:
            # Поиск частичного совпадения
            matches = {k: v for k, v in translations.items() if command.lower() in k}
            if matches:
                result["matches"] = matches
            else:
                result["message"] = f"Перевод для '{command}' не найден"
                result["hint"] = "Попробуй одну из: " + ", ".join(list(translations.keys())[:10])

        return result

    async def cmd_compat(self, command):
        """Проверить на каких ОС работает команда"""
        compat = {}
        for action, platforms in self.command_map.items():
            if command.lower() in action.lower():
                compat[action] = {
                    os_name: " ".join(info["cmd"][:3])
                    for os_name, info in platforms.items()
                }

        if not compat:
            return f"Команда '{command}' не найдена в таблице совместимости"

        return compat

    async def cmd_stacks(self):
        """Системные стеки каждой ОС"""
        return {
            "windows": {
                "kernel": "NT Kernel",
                "shell": "PowerShell / CMD",
                "package_manager": "winget / choco / scoop",
                "services": "SCM (services.msc)",
                "init": "wininit.exe",
                "filesystem": "NTFS / ReFS",
                "api": "Win32 / WMI / COM / .NET",
                "display": "DWM (Desktop Window Manager)",
                "firewall": "Windows Defender Firewall",
                "registry": "Windows Registry (regedit)",
            },
            "linux": {
                "kernel": "Linux Kernel",
                "shell": "bash / zsh / fish",
                "package_manager": "apt / dnf / pacman / nix",
                "services": "systemd / openrc / runit",
                "init": "systemd (PID 1)",
                "filesystem": "ext4 / btrfs / xfs / zfs",
                "api": "POSIX / syscalls",
                "display": "X11 / Wayland",
                "firewall": "iptables / nftables / ufw",
                "config": "Текстовые файлы (/etc/)",
            },
            "darwin": {
                "kernel": "XNU (Mach + BSD)",
                "shell": "zsh (по умолчанию)",
                "package_manager": "brew (Homebrew)",
                "services": "launchd",
                "init": "launchd (PID 1)",
                "filesystem": "APFS / HFS+",
                "api": "Cocoa / POSIX / IOKit",
                "display": "Quartz / Metal",
                "firewall": "pf (Packet Filter)",
                "config": "plist файлы + defaults",
            },
            "common_layer": {
                "note": "AI-OS абстрагирует различия — одна команда, любая ОС",
                "supported_actions": list(self.command_map.keys())
            }
        }
