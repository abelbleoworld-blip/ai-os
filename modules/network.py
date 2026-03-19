"""
Модуль: Сеть
Работа с интернетом — скачать, проверить, запросить.
Как городская почтовая служба для связи с внешним миром.
"""

import subprocess
import urllib.request
import urllib.error
import json
from core.module_base import SystemModule


class NetworkModule(SystemModule):
    def __init__(self):
        super().__init__("network", "Сетевые операции и интернет")
        self.register_command("ping", self.cmd_ping, "Проверить доступность хоста")
        self.register_command("download", self.cmd_download, "Скачать файл по URL")
        self.register_command("http_get", self.cmd_http_get, "HTTP GET запрос")
        self.register_command("connections", self.cmd_connections, "Активные соединения")
        self.register_command("dns", self.cmd_dns, "DNS-запрос для домена")

    async def cmd_ping(self, host, count=4):
        """Пинг — жив ли хост?"""
        result = subprocess.run(
            ["ping", "-n", str(count), host],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout

    async def cmd_download(self, url, save_path):
        """Скачать файл"""
        try:
            urllib.request.urlretrieve(url, save_path)
            return f"Скачано: {save_path}"
        except Exception as e:
            return f"Ошибка: {e}"

    async def cmd_http_get(self, url, timeout=10):
        """Простой HTTP GET"""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AI-OS/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(10000).decode("utf-8", errors="replace")
                return {
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body_preview": body[:2000]
                }
        except Exception as e:
            return f"Ошибка: {e}"

    async def cmd_connections(self):
        """Активные сетевые соединения"""
        result = subprocess.run(
            ["powershell.exe", "-Command",
             "Get-NetTCPConnection -State Established | "
             "Select-Object -First 20 LocalAddress, LocalPort, RemoteAddress, RemotePort, OwningProcess | "
             "ConvertTo-Json"],
            capture_output=True, text=True, timeout=10
        )
        try:
            return json.loads(result.stdout)
        except:
            return result.stdout

    async def cmd_dns(self, domain):
        """DNS lookup"""
        result = subprocess.run(
            ["nslookup", domain],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout
