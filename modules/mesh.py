"""
Модуль: Mesh (Сеть нод)
Связывает все устройства в единую систему.

Huawei (Windows) + MacBook (macOS) + VPS (Linux) = одна AI-OS.

Архитектура:
- VPS = хаб (всегда онлайн, координирует)
- Huawei/MacBook = агенты (подключаются когда включены)
- Каждый агент регистрируется на хабе, шлёт heartbeat
- Через хаб можно отправить команду на любой агент

API:
  POST /mesh/register     — агент регистрируется
  POST /mesh/heartbeat    — агент жив
  POST /mesh/command      — отправить команду на агент
  GET  /mesh/nodes        — список всех нод
  GET  /mesh/node/{name}  — инфо о ноде
"""

import os
import time
import json
import asyncio
import urllib.request
import urllib.error
import platform
from datetime import datetime
from core.module_base import SystemModule


class MeshModule(SystemModule):
    def __init__(self, bus=None):
        super().__init__("mesh", "Сеть нод — связь между устройствами")
        self.bus = bus
        self.role = os.environ.get("MESH_ROLE", "hub")  # hub или agent
        self.node_name = os.environ.get("MESH_NODE_NAME", platform.node())
        self.hub_url = os.environ.get("MESH_HUB_URL", "")  # для агентов
        self.secret = os.environ.get("MESH_SECRET", "aios-mesh-2026")

        # Хаб хранит список нод
        self.nodes = {}

        # Команды
        self.register_command("nodes", self.cmd_nodes, "Список всех подключённых нод")
        self.register_command("node_info", self.cmd_node_info, "Информация о ноде")
        self.register_command("send", self.cmd_send, "Отправить команду на другую ноду")
        self.register_command("status", self.cmd_status, "Статус mesh-сети")
        self.register_command("ping_nodes", self.cmd_ping_nodes, "Проверить доступность всех нод")

        self._heartbeat_task = None

    async def start(self):
        await super().start()
        # Регистрируем себя
        self.nodes[self.node_name] = {
            "name": self.node_name,
            "role": self.role,
            "os": platform.system(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "status": "online",
            "last_seen": datetime.now().isoformat(),
            "registered_at": datetime.now().isoformat(),
            "url": "",  # заполняется при регистрации агентов
        }

        # Агент: зарегистрироваться на хабе и слать heartbeat
        if self.role == "agent" and self.hub_url:
            self._heartbeat_task = asyncio.create_task(self._agent_loop())

    async def stop(self):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        await super().stop()

    # --- Hub API (вызывается из web.py) ---

    def hub_register(self, data: dict):
        """Агент регистрируется на хабе"""
        name = data.get("name", "unknown")
        self.nodes[name] = {
            "name": name,
            "role": "agent",
            "os": data.get("os", "?"),
            "arch": data.get("arch", "?"),
            "python": data.get("python", "?"),
            "status": "online",
            "url": data.get("url", ""),
            "last_seen": datetime.now().isoformat(),
            "registered_at": datetime.now().isoformat(),
            "modules": data.get("modules", []),
        }
        self.logger.info(f"Нода '{name}' зарегистрирована ({data.get('os')})")
        return {"ok": True, "message": f"Нода '{name}' зарегистрирована"}

    def hub_heartbeat(self, data: dict):
        """Агент шлёт heartbeat"""
        name = data.get("name", "")
        if name in self.nodes:
            self.nodes[name]["last_seen"] = datetime.now().isoformat()
            self.nodes[name]["status"] = "online"
            return {"ok": True}
        return {"error": f"Нода '{name}' не зарегистрирована"}

    async def hub_send_to_node(self, node_name: str, module: str, command: str, **args):
        """Хаб отправляет команду на агент"""
        if node_name == self.node_name:
            # Локальная команда
            if self.bus:
                return await self.bus.send(module, command, **args)
            return {"error": "Bus not available"}

        node = self.nodes.get(node_name)
        if not node:
            return {"error": f"Нода '{node_name}' не найдена"}
        if node["status"] != "online":
            return {"error": f"Нода '{node_name}' офлайн"}
        if not node.get("url"):
            return {"error": f"Нода '{node_name}' не имеет URL"}

        # Отправить HTTP-запрос на агент
        try:
            payload = json.dumps({
                "secret": self.secret,
                "module": module,
                "command": command,
                "args": args,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{node['url']}/mesh/execute",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            self.nodes[node_name]["status"] = "error"
            return {"error": f"Не удалось связаться с '{node_name}': {e}"}

    # --- Agent loop ---

    async def _agent_loop(self):
        """Агент: регистрация + heartbeat каждые 30 сек"""
        # Регистрация
        agent_port = int(os.environ.get("AIOS_PORT", "8080"))
        agent_url = os.environ.get("MESH_AGENT_URL", f"http://{self._get_local_ip()}:{agent_port}")

        reg_data = {
            "name": self.node_name,
            "secret": self.secret,
            "os": platform.system(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "url": agent_url,
            "modules": list(self.bus.modules.keys()) if self.bus else [],
        }

        # Попытки регистрации
        for attempt in range(5):
            try:
                self._http_post(f"{self.hub_url}/mesh/register", reg_data)
                self.logger.info(f"Зарегистрирован на хабе: {self.hub_url}")
                break
            except Exception as e:
                self.logger.warning(f"Регистрация не удалась (попытка {attempt+1}): {e}")
                await asyncio.sleep(10)

        # Heartbeat loop
        while True:
            try:
                await asyncio.sleep(30)
                self._http_post(f"{self.hub_url}/mesh/heartbeat", {
                    "name": self.node_name,
                    "secret": self.secret,
                })
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning(f"Heartbeat ошибка: {e}")

    def _http_post(self, url, data):
        """Простой HTTP POST"""
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get_local_ip(self):
        """Определить свой IP"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    # --- Команды модуля ---

    async def cmd_nodes(self):
        """Список нод"""
        # Проверить таймауты (если нет heartbeat > 90 сек — офлайн)
        now = datetime.now()
        for name, node in self.nodes.items():
            if name == self.node_name:
                node["status"] = "online"
                node["last_seen"] = now.isoformat()
                continue
            try:
                last = datetime.fromisoformat(node["last_seen"])
                if (now - last).total_seconds() > 90:
                    node["status"] = "offline"
            except:
                pass

        return {
            name: {
                "os": n["os"],
                "role": n["role"],
                "status": n["status"],
                "last_seen": n["last_seen"],
            }
            for name, n in self.nodes.items()
        }

    async def cmd_node_info(self, name=""):
        """Детали ноды"""
        if not name:
            name = self.node_name
        node = self.nodes.get(name)
        if not node:
            return f"Нода '{name}' не найдена. Доступные: {list(self.nodes.keys())}"
        return node

    async def cmd_send(self, node="", module="", command="", **args):
        """Отправить команду на другую ноду"""
        if not node or not module or not command:
            return "Формат: mesh.send node=имя module=модуль command=команда"
        return await self.hub_send_to_node(node, module, command, **args)

    async def cmd_status(self):
        """Статус mesh-сети"""
        online = sum(1 for n in self.nodes.values() if n["status"] == "online")
        total = len(self.nodes)
        return {
            "role": self.role,
            "node_name": self.node_name,
            "total_nodes": total,
            "online": online,
            "offline": total - online,
            "nodes": list(self.nodes.keys()),
        }

    async def cmd_ping_nodes(self):
        """Пинг всех нод"""
        results = {}
        for name, node in self.nodes.items():
            if name == self.node_name:
                results[name] = "local (online)"
                continue
            if not node.get("url"):
                results[name] = "no url"
                continue
            try:
                req = urllib.request.Request(f"{node['url']}/api/health")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    results[name] = "online" if resp.status == 200 else f"status {resp.status}"
                    node["status"] = "online"
                    node["last_seen"] = datetime.now().isoformat()
            except Exception as e:
                results[name] = f"offline ({e})"
                node["status"] = "offline"
        return results
