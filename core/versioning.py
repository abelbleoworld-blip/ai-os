"""
Система версий и отката (Versioning).

Принцип: любое изменение можно откатить.
Перед каждым изменением — сохраняем состояние.
Если результат плохой — откат в один клик.

Работает для:
- Файлов (перед изменением — бэкап)
- Конфигов системы
- Дизайн-темы и макеты
- Знаний модулей

Как git, но для всей системы. Каждое изменение = коммит.
Плохое изменение = откат на предыдущую стабильную версию.
"""

import json
import shutil
import hashlib
from datetime import datetime
from pathlib import Path


VERSIONS_DIR = Path(__file__).parent.parent / "versions"


class VersionManager:
    def __init__(self):
        VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.history_file = VERSIONS_DIR / "history.json"
        self.history = self._load_history()
        self.stable_tag = self._get_stable_tag()

    def _load_history(self):
        if self.history_file.exists():
            return json.loads(self.history_file.read_text(encoding="utf-8"))
        return []

    def _save_history(self):
        self.history_file.write_text(
            json.dumps(self.history[-500:], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _get_stable_tag(self):
        """Найти последнюю стабильную версию"""
        for entry in reversed(self.history):
            if entry.get("stable"):
                return entry["id"]
        return None

    def _make_id(self):
        """Уникальный ID версии"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"v_{ts}"

    def snapshot(self, path: str, reason: str, author: str = "system"):
        """
        Сохранить снимок файла/папки перед изменением.
        Возвращает ID версии для возможного отката.
        """
        src = Path(path)
        if not src.exists():
            return None

        version_id = self._make_id()
        backup_dir = VERSIONS_DIR / version_id
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Копируем файл или папку
        if src.is_file():
            shutil.copy2(src, backup_dir / src.name)
            size = src.stat().st_size
        else:
            shutil.copytree(src, backup_dir / src.name, dirs_exist_ok=True)
            size = sum(f.stat().st_size for f in src.rglob("*") if f.is_file())

        # Записываем в историю
        entry = {
            "id": version_id,
            "path": str(src.absolute()),
            "reason": reason,
            "author": author,
            "timestamp": datetime.now().isoformat(),
            "backup_location": str(backup_dir),
            "size_bytes": size,
            "stable": False
        }
        self.history.append(entry)
        self._save_history()

        return version_id

    def rollback(self, version_id: str = None):
        """
        Откатить к версии.
        Без аргумента — откат к последней стабильной.
        """
        if version_id is None:
            version_id = self.stable_tag

        if version_id is None:
            return "Нет стабильной версии для отката"

        # Найти запись
        entry = None
        for e in self.history:
            if e["id"] == version_id:
                entry = e
                break

        if not entry:
            return f"Версия '{version_id}' не найдена"

        backup_dir = Path(entry["backup_location"])
        target = Path(entry["path"])

        if not backup_dir.exists():
            return f"Бэкап '{version_id}' не найден на диске"

        # Сначала сохраняем текущее состояние (чтобы можно было откатить откат)
        self.snapshot(str(target), f"Перед откатом к {version_id}", "rollback")

        # Восстанавливаем
        if target.is_file() or not target.exists():
            backup_files = list(backup_dir.iterdir())
            if backup_files:
                if target.exists():
                    target.unlink()
                shutil.copy2(backup_files[0], target)
        else:
            # Папка
            backup_contents = list(backup_dir.iterdir())
            if backup_contents:
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(backup_contents[0], target)

        return {
            "rolled_back_to": version_id,
            "path": str(target),
            "reason": entry["reason"],
            "original_date": entry["timestamp"]
        }

    def mark_stable(self, version_id: str = None):
        """Пометить версию как стабильную"""
        if version_id is None and self.history:
            version_id = self.history[-1]["id"]

        for entry in self.history:
            if entry["id"] == version_id:
                entry["stable"] = True
                self.stable_tag = version_id
                self._save_history()
                return f"Версия '{version_id}' помечена как стабильная"

        return f"Версия '{version_id}' не найдена"

    def list_versions(self, count: int = 20):
        """Показать историю версий"""
        return self.history[-count:]

    def get_stable(self):
        """Текущая стабильная версия"""
        if self.stable_tag:
            for entry in self.history:
                if entry["id"] == self.stable_tag:
                    return entry
        return "Стабильная версия не установлена"

    def cleanup(self, keep_last: int = 50):
        """Очистить старые версии (оставить последние N)"""
        if len(self.history) <= keep_last:
            return "Нечего чистить"

        to_remove = self.history[:-keep_last]
        removed = 0
        for entry in to_remove:
            backup = Path(entry["backup_location"])
            if backup.exists():
                shutil.rmtree(backup)
                removed += 1

        self.history = self.history[-keep_last:]
        self._save_history()
        return f"Удалено {removed} старых версий, оставлено {keep_last}"
