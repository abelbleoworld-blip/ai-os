"""
Модуль: Software (Управление программами)
Кроссплатформенная установка: brew (macOS), apt (Linux), winget (Windows).

"поставь VLC"
"обнови всё"
"что установлено?"
"удали Skype"
"""

import subprocess
import platform
import shutil
from core.module_base import SystemModule

# Маппинг популярных имён пакетов между менеджерами
PACKAGE_MAP = {
    # winget ID → brew cask/formula
    "VideoLAN.VLC": "vlc",
    "Google.Chrome": "google-chrome",
    "Mozilla.Firefox": "firefox",
    "Microsoft.VisualStudioCode": "visual-studio-code",
    "Telegram.TelegramDesktop": "telegram",
    "Spotify.Spotify": "spotify",
    "7zip.7zip": "p7zip",
    "GIMP.GIMP": "gimp",
    "Inkscape.Inkscape": "inkscape",
    "OBSProject.OBSStudio": "obs",
    "Transmission.Transmission": "transmission",
    "WireGuard.WireGuard": "wireguard-tools",
}


class SoftwareModule(SystemModule):
    def __init__(self):
        super().__init__("software", "Установка и управление программами")
        self.register_command("search", self.cmd_search, "Найти программу")
        self.register_command("install", self.cmd_install, "Установить программу")
        self.register_command("uninstall", self.cmd_uninstall, "Удалить программу")
        self.register_command("list", self.cmd_list, "Список установленных")
        self.register_command("upgradable", self.cmd_upgradable, "Программы с доступными обновлениями")
        self.register_command("upgrade", self.cmd_upgrade, "Обновить программу")
        self.register_command("upgrade_all", self.cmd_upgrade_all, "Обновить всё")
        self.register_command("info", self.cmd_info, "Информация о программе")

        # Определяем пакетный менеджер
        self.os_type = platform.system().lower()  # linux, darwin, windows
        self.pkg_manager = self._detect_manager()

    def _detect_manager(self):
        """Определить доступный пакетный менеджер"""
        managers = [
            ("brew", ["brew", "--version"]),
            ("apt", ["apt", "--version"]),
            ("dnf", ["dnf", "--version"]),
            ("winget", ["winget", "--version"]),
        ]
        for name, cmd in managers:
            if shutil.which(cmd[0]):
                return name
        return None

    def _resolve_package(self, package):
        """Преобразовать winget ID в имя для текущего менеджера"""
        if self.pkg_manager in ("brew", "apt", "dnf"):
            return PACKAGE_MAP.get(package, package.lower().split(".")[-1])
        return package

    def _run_pkg(self, args, timeout=60):
        """Запустить команду пакетного менеджера"""
        if not self.pkg_manager:
            return {"error": f"Пакетный менеджер не найден (ОС: {self.os_type}). Установи brew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""}
        try:
            cmd = [self.pkg_manager] + args
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace"
            )
            return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
        except subprocess.TimeoutExpired:
            return {"error": f"Таймаут {timeout} сек"}
        except FileNotFoundError:
            return {"error": f"{self.pkg_manager} не найден"}

    async def cmd_search(self, query=""):
        """Поиск программы"""
        if not query:
            return "Укажи что искать: software.search query=vlc"

        if self.pkg_manager == "brew":
            r = self._run_pkg(["search", query])
        elif self.pkg_manager == "apt":
            r = self._run_pkg(["search", query], timeout=30)
        elif self.pkg_manager == "winget":
            r = self._run_pkg(["search", query, "--accept-source-agreements"])
        else:
            return {"error": "Пакетный менеджер не найден"}

        if "error" in r:
            return r

        lines = [l.strip() for l in r["stdout"].split("\n") if l.strip()]
        return {"query": query, "manager": self.pkg_manager, "results": lines[:20]}

    async def cmd_install(self, package=""):
        """Установить программу"""
        if not package:
            return "Укажи пакет: software.install package=vlc"

        pkg = self._resolve_package(package)

        if self.pkg_manager == "brew":
            # Сначала пробуем cask (GUI-приложения), потом formula
            r = self._run_pkg(["install", "--cask", pkg], timeout=300)
            if r.get("code", 1) != 0 and "no cask" in r.get("stderr", "").lower():
                r = self._run_pkg(["install", pkg], timeout=300)
        elif self.pkg_manager == "apt":
            r = self._run_pkg(["install", "-y", pkg], timeout=300)
        elif self.pkg_manager == "winget":
            r = self._run_pkg(["install", package, "--accept-package-agreements", "--accept-source-agreements", "--silent"], timeout=300)
        else:
            return {"error": "Пакетный менеджер не найден"}

        if "error" in r:
            return r

        if r["code"] == 0:
            return {"status": "ok", "message": f"'{pkg}' установлен через {self.pkg_manager}", "output": r["stdout"][-500:]}
        return {"status": "error", "message": f"Ошибка установки '{pkg}'", "output": r["stdout"][-500:], "stderr": r["stderr"][-300:]}

    async def cmd_uninstall(self, package=""):
        """Удалить программу"""
        if not package:
            return "Укажи пакет: software.uninstall package=vlc"

        pkg = self._resolve_package(package)

        if self.pkg_manager == "brew":
            r = self._run_pkg(["uninstall", "--cask", pkg], timeout=120)
            if r.get("code", 1) != 0:
                r = self._run_pkg(["uninstall", pkg], timeout=120)
        elif self.pkg_manager == "apt":
            r = self._run_pkg(["remove", "-y", pkg], timeout=120)
        elif self.pkg_manager == "winget":
            r = self._run_pkg(["uninstall", package, "--silent"], timeout=120)
        else:
            return {"error": "Пакетный менеджер не найден"}

        if "error" in r:
            return r
        if r["code"] == 0:
            return {"status": "ok", "message": f"'{pkg}' удалён"}
        return {"status": "error", "message": f"Не удалось удалить '{pkg}'", "output": r["stdout"][-300:]}

    async def cmd_list(self, filter=""):
        """Список установленных программ"""
        if self.pkg_manager == "brew":
            r = self._run_pkg(["list", "--cask"])
            r2 = self._run_pkg(["list", "--formula"])
            if "error" not in r and "error" not in r2:
                casks = [l for l in r["stdout"].split("\n") if l.strip()]
                formulas = [l for l in r2["stdout"].split("\n") if l.strip()]
                all_pkgs = [{"name": c, "type": "cask"} for c in casks] + [{"name": f, "type": "formula"} for f in formulas]
                if filter:
                    all_pkgs = [p for p in all_pkgs if filter.lower() in p["name"].lower()]
                return {"total": len(all_pkgs), "manager": "brew", "programs": all_pkgs[:40]}
            return r if "error" in r else r2
        elif self.pkg_manager == "apt":
            r = self._run_pkg(["list", "--installed"])
        elif self.pkg_manager == "winget":
            r = self._run_pkg(["list", "--accept-source-agreements"])
        else:
            return {"error": "Пакетный менеджер не найден"}

        if "error" in r:
            return r
        lines = [l for l in r["stdout"].split("\n") if l.strip()]
        if filter:
            lines = [l for l in lines if filter.lower() in l.lower()]
        return {"total": len(lines), "manager": self.pkg_manager, "programs": lines[:30]}

    async def cmd_upgradable(self):
        """Программы с обновлениями"""
        if self.pkg_manager == "brew":
            r = self._run_pkg(["outdated"])
        elif self.pkg_manager == "apt":
            self._run_pkg(["update"], timeout=60)
            r = self._run_pkg(["list", "--upgradable"])
        elif self.pkg_manager == "winget":
            r = self._run_pkg(["upgrade", "--accept-source-agreements"])
        else:
            return {"error": "Пакетный менеджер не найден"}

        if "error" in r:
            return r
        lines = [l for l in r["stdout"].split("\n") if l.strip()]
        return {"upgradable": len(lines), "manager": self.pkg_manager, "programs": lines}

    async def cmd_upgrade(self, package=""):
        """Обновить одну программу"""
        if not package:
            return "Укажи пакет: software.upgrade package=vlc"

        pkg = self._resolve_package(package)

        if self.pkg_manager == "brew":
            r = self._run_pkg(["upgrade", pkg], timeout=300)
        elif self.pkg_manager == "apt":
            r = self._run_pkg(["install", "--only-upgrade", "-y", pkg], timeout=300)
        elif self.pkg_manager == "winget":
            r = self._run_pkg(["upgrade", package, "--accept-package-agreements", "--silent"], timeout=300)
        else:
            return {"error": "Пакетный менеджер не найден"}

        if "error" in r:
            return r
        if r["code"] == 0:
            return {"status": "ok", "message": f"'{pkg}' обновлён через {self.pkg_manager}"}
        return {"status": "error", "output": r["stdout"][-500:]}

    async def cmd_upgrade_all(self):
        """Обновить все программы"""
        if self.pkg_manager == "brew":
            r = self._run_pkg(["upgrade"], timeout=600)
        elif self.pkg_manager == "apt":
            self._run_pkg(["update"], timeout=60)
            r = self._run_pkg(["upgrade", "-y"], timeout=600)
        elif self.pkg_manager == "winget":
            r = self._run_pkg(["upgrade", "--all", "--accept-package-agreements", "--silent"], timeout=600)
        else:
            return {"error": "Пакетный менеджер не найден"}

        if "error" in r:
            return r
        return {"status": "ok" if r["code"] == 0 else "partial", "manager": self.pkg_manager, "output": r["stdout"][-1000:]}

    async def cmd_info(self, package=""):
        """Информация о пакете"""
        if not package:
            return "Укажи пакет: software.info package=vlc"

        pkg = self._resolve_package(package)

        if self.pkg_manager == "brew":
            r = self._run_pkg(["info", pkg])
        elif self.pkg_manager == "apt":
            r = self._run_pkg(["show", pkg])
        elif self.pkg_manager == "winget":
            r = self._run_pkg(["show", package, "--accept-source-agreements"])
        else:
            return {"error": "Пакетный менеджер не найден"}

        if "error" in r:
            return r
        return r["stdout"]
