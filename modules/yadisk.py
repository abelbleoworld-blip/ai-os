"""
Модуль: YaDisk (Яндекс Диск)
Синхронизация данных и knowledge с Яндекс Диском.

Использует REST API Яндекс Диска (OAuth).
Хранение: knowledge, бэкапы, общие файлы между нодами.

Настройка:
  1. Получи OAuth токен: https://oauth.yandex.ru/authorize?response_type=token&client_id=YOUR_APP_ID
  2. Добавь в .env: YADISK_TOKEN=your_token
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from core.module_base import SystemModule

YADISK_API = "https://cloud-api.yandex.net/v1/disk"


class YaDiskModule(SystemModule):
    def __init__(self, bus=None):
        super().__init__("yadisk", "Яндекс Диск — облачное хранилище и синхронизация")
        self.bus = bus
        self.token = os.environ.get("YADISK_TOKEN", "")
        self.base_path = "/AI-OS"  # папка на Яндекс Диске

        self.register_command("status", self.cmd_status, "Статус подключения")
        self.register_command("info", self.cmd_info, "Информация о диске")
        self.register_command("ls", self.cmd_ls, "Список файлов на Яндекс Диске")
        self.register_command("upload", self.cmd_upload, "Загрузить файл на Яндекс Диск")
        self.register_command("download", self.cmd_download, "Скачать файл с Яндекс Диска")
        self.register_command("sync_knowledge", self.cmd_sync_knowledge, "Синхронизировать базу знаний")
        self.register_command("backup", self.cmd_backup, "Бэкап памяти и навыков")
        self.register_command("restore", self.cmd_restore, "Восстановить из бэкапа")

    def _headers(self):
        return {
            "Authorization": f"OAuth {self.token}",
            "Content-Type": "application/json",
        }

    def _api(self, endpoint, method="GET", data=None):
        """Запрос к API Яндекс Диска"""
        if not self.token:
            return {"error": "YADISK_TOKEN не задан. Добавь в .env"}

        url = f"{YADISK_API}{endpoint}"
        req = urllib.request.Request(url, headers=self._headers(), method=method)

        if data:
            req.data = json.dumps(data).encode("utf-8")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            return {"error": f"HTTP {e.code}: {body[:200]}"}
        except Exception as e:
            return {"error": str(e)}

    async def cmd_status(self):
        if not self.token:
            return {
                "connected": False,
                "message": "Нет токена. Добавь YADISK_TOKEN в .env",
                "setup": [
                    "1. Создай приложение: https://oauth.yandex.ru/client/new",
                    "2. Получи токен: https://oauth.yandex.ru/authorize?response_type=token&client_id=YOUR_ID",
                    "3. Добавь в .env: YADISK_TOKEN=полученный_токен",
                    "4. Перезапусти: docker compose up -d",
                ]
            }
        info = self._api("/")
        if "error" in info:
            return {"connected": False, "error": info["error"]}
        return {
            "connected": True,
            "total_gb": round(info.get("total_space", 0) / (1024**3), 1),
            "used_gb": round(info.get("used_space", 0) / (1024**3), 1),
            "free_gb": round((info.get("total_space", 0) - info.get("used_space", 0)) / (1024**3), 1),
            "user": info.get("user", {}).get("display_name", ""),
        }

    async def cmd_info(self):
        return self._api("/")

    async def cmd_ls(self, path=""):
        """Список файлов"""
        full_path = f"{self.base_path}/{path}".rstrip("/")
        result = self._api(f"/resources?path={full_path}&limit=50")
        if "error" in result:
            # Попробовать создать папку
            if "404" in str(result.get("error", "")):
                self._api(f"/resources?path={self.base_path}", method="PUT")
                return {"message": f"Папка {self.base_path} создана. Пока пусто."}
            return result
        items = result.get("_embedded", {}).get("items", [])
        return [{
            "name": i["name"],
            "type": i["type"],
            "size": i.get("size", 0),
            "modified": i.get("modified", ""),
        } for i in items]

    async def cmd_upload(self, local_path, remote_path=""):
        """Загрузить локальный файл на Яндекс Диск"""
        p = Path(local_path)
        if not p.exists():
            return {"error": f"File not found: {local_path}"}

        remote = f"{self.base_path}/{remote_path or p.name}"
        # Получить URL для загрузки
        result = self._api(f"/resources/upload?path={remote}&overwrite=true")
        if "error" in result:
            return result

        upload_url = result.get("href", "")
        if not upload_url:
            return {"error": "No upload URL received"}

        # Загрузить файл
        try:
            data = p.read_bytes()
            req = urllib.request.Request(upload_url, data=data, method="PUT")
            req.add_header("Content-Length", str(len(data)))
            with urllib.request.urlopen(req, timeout=60) as resp:
                return {"uploaded": remote, "size": len(data), "status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    async def cmd_download(self, remote_path, local_path=""):
        """Скачать файл с Яндекс Диска"""
        remote = f"{self.base_path}/{remote_path}"
        result = self._api(f"/resources/download?path={remote}")
        if "error" in result:
            return result

        download_url = result.get("href", "")
        if not download_url:
            return {"error": "No download URL"}

        local = local_path or f"/app/uploads/{Path(remote_path).name}"
        try:
            urllib.request.urlretrieve(download_url, local)
            return {"downloaded": local, "from": remote, "status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    async def cmd_sync_knowledge(self):
        """Синхронизировать knowledge base с Яндекс Диском"""
        knowledge_dir = Path("/app/knowledge")
        results = {"uploaded": [], "errors": []}

        # Создать папку на диске
        self._api(f"/resources?path={self.base_path}/knowledge", method="PUT")

        for f in knowledge_dir.glob("*.json"):
            r = await self.cmd_upload(str(f), f"knowledge/{f.name}")
            if "error" in r:
                results["errors"].append(f"{f.name}: {r['error']}")
            else:
                results["uploaded"].append(f.name)

        return {
            "synced": len(results["uploaded"]),
            "errors": len(results["errors"]),
            "files": results["uploaded"],
            "error_details": results["errors"][:5],
        }

    async def cmd_backup(self):
        """Бэкап всей памяти и навыков"""
        memory_dir = Path("/app/memory")
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        backup_path = f"backups/backup_{ts}"

        self._api(f"/resources?path={self.base_path}/backups", method="PUT")
        self._api(f"/resources?path={self.base_path}/{backup_path}", method="PUT")

        results = {"uploaded": [], "errors": []}

        for f in memory_dir.glob("*.json"):
            r = await self.cmd_upload(str(f), f"{backup_path}/{f.name}")
            if "error" in r:
                results["errors"].append(f.name)
            else:
                results["uploaded"].append(f.name)

        return {
            "backup": backup_path,
            "files": len(results["uploaded"]),
            "errors": len(results["errors"]),
            "timestamp": ts,
        }

    async def cmd_restore(self, backup_name="latest"):
        """Восстановить из бэкапа"""
        # Найти бэкапы
        backups = self._api(f"/resources?path={self.base_path}/backups&limit=20")
        if "error" in backups:
            return backups

        items = backups.get("_embedded", {}).get("items", [])
        if not items:
            return {"error": "Бэкапов нет"}

        # Последний бэкап
        items.sort(key=lambda x: x.get("modified", ""), reverse=True)
        target = items[0]["name"] if backup_name == "latest" else backup_name

        # Скачать файлы
        files = self._api(f"/resources?path={self.base_path}/backups/{target}&limit=50")
        if "error" in files:
            return files

        restored = []
        for f in files.get("_embedded", {}).get("items", []):
            r = await self.cmd_download(f"backups/{target}/{f['name']}", f"/app/memory/{f['name']}")
            if "error" not in r:
                restored.append(f["name"])

        return {"restored_from": target, "files": restored, "count": len(restored)}
