"""
Модуль: Software (Управление программами)
Установка, удаление, обновление через winget.

"поставь VLC"
"обнови всё"
"что установлено?"
"удали Skype"
"""

import subprocess
import json
from core.module_base import SystemModule


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

    def _run_winget(self, args, timeout=60):
        """Запустить winget"""
        try:
            result = subprocess.run(
                ["winget"] + args,
                capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace"
            )
            return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
        except subprocess.TimeoutExpired:
            return {"error": f"Таймаут {timeout} сек"}
        except FileNotFoundError:
            return {"error": "winget не найден"}

    def _parse_table(self, text):
        """Парсинг табличного вывода winget"""
        lines = text.strip().split("\n")
        # Найти строку-разделитель (----)
        sep_idx = -1
        for i, line in enumerate(lines):
            if "---" in line:
                sep_idx = i
                break

        if sep_idx < 1:
            return text

        header = lines[sep_idx - 1]
        # Определяем позиции колонок по разделителю
        sep = lines[sep_idx]
        cols = []
        start = 0
        for part in sep.split():
            end = start + len(part)
            cols.append((start, end))
            start = end + 1

        results = []
        for line in lines[sep_idx + 1:]:
            if not line.strip():
                continue
            row = {}
            for j, (s, e) in enumerate(cols):
                val = line[s:e].strip() if s < len(line) else ""
                # Имена колонок
                hdr_val = header[s:e].strip() if s < len(header) else f"col{j}"
                row[hdr_val] = val
            if any(row.values()):
                results.append(row)

        return results

    async def cmd_search(self, query=""):
        """Поиск программы"""
        if not query:
            return "Укажи что искать: software.search query=vlc"

        r = self._run_winget(["search", query, "--accept-source-agreements"])
        if "error" in r:
            return r

        parsed = self._parse_table(r["stdout"])
        if isinstance(parsed, str):
            return parsed

        return {"query": query, "results": parsed[:15]}

    async def cmd_install(self, package=""):
        """Установить программу"""
        if not package:
            return "Укажи пакет: software.install package=VideoLAN.VLC"

        r = self._run_winget([
            "install", package,
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--silent"
        ], timeout=300)

        if "error" in r:
            return r

        if r["code"] == 0:
            return {"status": "ok", "message": f"'{package}' установлен", "output": r["stdout"][-500:]}
        return {"status": "error", "message": f"Ошибка установки '{package}'", "output": r["stdout"][-500:], "stderr": r["stderr"][-300:]}

    async def cmd_uninstall(self, package=""):
        """Удалить программу"""
        if not package:
            return "Укажи пакет: software.uninstall package=VideoLAN.VLC"

        r = self._run_winget(["uninstall", package, "--silent"], timeout=120)
        if "error" in r:
            return r

        if r["code"] == 0:
            return {"status": "ok", "message": f"'{package}' удалён"}
        return {"status": "error", "message": f"Не удалось удалить '{package}'", "output": r["stdout"][-300:]}

    async def cmd_list(self, filter=""):
        """Список установленных программ"""
        args = ["list", "--accept-source-agreements"]
        if filter:
            args.extend(["--name", filter])

        r = self._run_winget(args)
        if "error" in r:
            return r

        parsed = self._parse_table(r["stdout"])
        if isinstance(parsed, list):
            return {"total": len(parsed), "programs": parsed[:30]}
        return parsed

    async def cmd_upgradable(self):
        """Программы с обновлениями"""
        r = self._run_winget(["upgrade", "--accept-source-agreements"])
        if "error" in r:
            return r

        parsed = self._parse_table(r["stdout"])
        if isinstance(parsed, list):
            return {"upgradable": len(parsed), "programs": parsed}
        return parsed

    async def cmd_upgrade(self, package=""):
        """Обновить одну программу"""
        if not package:
            return "Укажи пакет: software.upgrade package=Google.Chrome"

        r = self._run_winget([
            "upgrade", package,
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--silent"
        ], timeout=300)

        if "error" in r:
            return r

        if r["code"] == 0:
            return {"status": "ok", "message": f"'{package}' обновлён"}
        return {"status": "error", "output": r["stdout"][-500:]}

    async def cmd_upgrade_all(self):
        """Обновить все программы"""
        r = self._run_winget([
            "upgrade", "--all",
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--silent"
        ], timeout=600)

        if "error" in r:
            return r

        return {"status": "ok" if r["code"] == 0 else "partial", "output": r["stdout"][-1000:]}

    async def cmd_info(self, package=""):
        """Информация о пакете"""
        if not package:
            return "Укажи пакет: software.info package=VideoLAN.VLC"

        r = self._run_winget(["show", package, "--accept-source-agreements"])
        if "error" in r:
            return r
        return r["stdout"]
