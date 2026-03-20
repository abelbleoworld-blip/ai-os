"""
Модуль: Файловая система
Управляет файлами и папками. Как городской архив — хранит, ищет, выдаёт документы.
"""

import os
import shutil
import json
from pathlib import Path
from core.module_base import SystemModule


class FilesModule(SystemModule):
    def __init__(self):
        super().__init__("files", "Управление файлами и папками")
        self.register_command("list", self.cmd_list, "Список файлов в папке")
        self.register_command("read", self.cmd_read, "Прочитать файл")
        self.register_command("write", self.cmd_write, "Записать файл")
        self.register_command("find", self.cmd_find, "Найти файлы по имени")
        self.register_command("info", self.cmd_info, "Информация о файле/папке")
        self.register_command("mkdir", self.cmd_mkdir, "Создать папку")
        self.register_command("delete", self.cmd_delete, "Удалить файл/папку")
        self.register_command("disk_usage", self.cmd_disk_usage, "Использование диска")

    async def cmd_list(self, path="."):
        """Показать содержимое папки"""
        p = Path(path)
        if not p.exists():
            return f"Путь '{path}' не существует"
        items = []
        for item in sorted(p.iterdir()):
            items.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None
            })
        return items

    async def cmd_read(self, path, encoding="utf-8"):
        """Прочитать содержимое файла"""
        p = Path(path)
        if not p.exists():
            return f"Файл '{path}' не найден"
        if p.stat().st_size > 1_000_000:
            return f"Файл слишком большой ({p.stat().st_size} байт), читаю первые 1000 строк"
        return p.read_text(encoding=encoding, errors="replace")

    async def cmd_write(self, path, content, encoding="utf-8"):
        """Записать содержимое в файл"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return f"Записано {len(content)} символов в '{path}'"

    async def cmd_find(self, pattern, path="."):
        """Найти файлы по шаблону (например *.txt)"""
        p = Path(path)
        results = list(p.rglob(pattern))[:100]  # ограничение 100
        return [str(r) for r in results]

    async def cmd_info(self, path):
        """Информация о файле"""
        p = Path(path)
        if not p.exists():
            return f"'{path}' не существует"
        stat = p.stat()
        return {
            "path": str(p.absolute()),
            "type": "dir" if p.is_dir() else "file",
            "size": stat.st_size,
            "modified": str(stat.st_mtime),
        }

    async def cmd_mkdir(self, path):
        """Создать папку"""
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        return f"Папка '{path}' создана"

    async def cmd_delete(self, path):
        """Удалить файл или папку"""
        p = Path(path)
        if not p.exists():
            return f"'{path}' не существует"
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return f"'{path}' удалён"

    async def cmd_disk_usage(self):
        """Использование дисков"""
        import psutil
        result = []
        seen = set()
        for p in psutil.disk_partitions():
            if p.mountpoint in ('/etc/resolv.conf', '/etc/hostname', '/etc/hosts'):
                continue
            try:
                usage = psutil.disk_usage(p.mountpoint)
                key = (usage.total, usage.free)
                if key in seen:
                    continue
                seen.add(key)
                result.append({
                    "drive": p.mountpoint,
                    "mountpoint": p.mountpoint,
                    "total_gb": round(usage.total / (1024**3), 1),
                    "used_gb": round(usage.used / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent": usage.percent
                })
            except (PermissionError, OSError):
                    pass
        return result
