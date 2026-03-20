"""
Модуль: Сеть
Кроссплатформенный через psutil + urllib.
"""

import subprocess
import urllib.request
import urllib.error
import json
import psutil
from core.module_base import SystemModule


class NetworkModule(SystemModule):
    def __init__(self):
        super().__init__("network", "Сетевые операции и интернет")
        self.register_command("ping", self.cmd_ping, "Проверить доступность хоста")
        self.register_command("download", self.cmd_download, "Скачать файл по URL")
        self.register_command("http_get", self.cmd_http_get, "HTTP GET запрос")
        self.register_command("connections", self.cmd_connections, "Активные соединения")
        self.register_command("interfaces", self.cmd_interfaces, "Сетевые интерфейсы")
        self.register_command("dns", self.cmd_dns, "DNS-запрос для домена")

    async def cmd_ping(self, host="google.com", count=4):
        try:
            result = subprocess.run(
                ["ping", "-c", str(count), host],
                capture_output=True, text=True, timeout=15
            )
            return result.stdout if result.returncode == 0 else f"Host {host} unreachable"
        except FileNotFoundError:
            # Fallback: try HTTP
            try:
                urllib.request.urlopen(f"https://{host}", timeout=5)
                return f"{host} is reachable (HTTP OK)"
            except:
                return f"{host} is unreachable"

    async def cmd_download(self, url, save_path):
        try:
            urllib.request.urlretrieve(url, save_path)
            return f"Downloaded: {save_path}"
        except Exception as e:
            return f"Error: {e}"

    async def cmd_http_get(self, url, timeout=10):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AI-OS/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(10000).decode("utf-8", errors="replace")
                return {"status": resp.status, "body_preview": body[:2000]}
        except Exception as e:
            return f"Error: {e}"

    async def cmd_connections(self):
        conns = []
        for c in psutil.net_connections(kind='inet'):
            if c.status == 'ESTABLISHED':
                conns.append({
                    "local": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
                    "remote": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
                    "pid": c.pid,
                    "status": c.status,
                })
        return conns[:20]

    async def cmd_interfaces(self):
        result = []
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for name, addr_list in addrs.items():
            iface = {"name": name, "up": stats.get(name, {}).isup if hasattr(stats.get(name), 'isup') else False}
            for addr in addr_list:
                if addr.family.name == 'AF_INET':
                    iface["ip"] = addr.address
                    iface["netmask"] = addr.netmask
            if "ip" in iface:
                result.append(iface)
        return result

    async def cmd_dns(self, domain):
        try:
            result = subprocess.run(["nslookup", domain], capture_output=True, text=True, timeout=10)
            return result.stdout
        except FileNotFoundError:
            import socket
            try:
                ip = socket.gethostbyname(domain)
                return f"{domain} -> {ip}"
            except:
                return f"DNS lookup failed for {domain}"
