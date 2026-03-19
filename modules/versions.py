"""
Модуль: Версионирование
Управление версиями, бэкапами и откатами.
Любое изменение можно откатить. Стабильные версии помечаются.

Дизайнер изменил тему → не понравилось → откат.
Модуль обновил конфиг → сломалось → откат на стабильную.
"""

from core.module_base import SystemModule
from core.versioning import VersionManager


class VersionsModule(SystemModule):
    def __init__(self):
        super().__init__("versions", "Версии, бэкапы, откаты")
        self.vm = VersionManager()
        self.register_command("snapshot", self.cmd_snapshot, "Сохранить снимок файла/папки")
        self.register_command("rollback", self.cmd_rollback, "Откатить к версии")
        self.register_command("stable", self.cmd_stable, "Пометить версию как стабильную")
        self.register_command("list", self.cmd_list, "История версий")
        self.register_command("current", self.cmd_current, "Текущая стабильная версия")
        self.register_command("cleanup", self.cmd_cleanup, "Очистить старые версии")

    async def cmd_snapshot(self, path="", reason="Ручной снимок"):
        """Сохранить снимок"""
        if not path:
            return "Укажи путь: versions.snapshot path=C:/file reason=описание"
        vid = self.vm.snapshot(path, reason, author="user")
        if vid:
            return f"Снимок сохранён: {vid}"
        return "Файл/папка не существует"

    async def cmd_rollback(self, version_id=None):
        """Откатить"""
        return self.vm.rollback(version_id)

    async def cmd_stable(self, version_id=None):
        """Пометить стабильной"""
        return self.vm.mark_stable(version_id)

    async def cmd_list(self, count=20):
        """История"""
        return self.vm.list_versions(int(count))

    async def cmd_current(self):
        """Текущая стабильная"""
        return self.vm.get_stable()

    async def cmd_cleanup(self, keep=50):
        """Очистка"""
        return self.vm.cleanup(int(keep))
