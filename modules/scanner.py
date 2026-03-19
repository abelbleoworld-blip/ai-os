"""
Модуль: Scanner (Сканер дисков)
Адаптировано из folder-ai/scanner.js — полный анализ дисков.

Возможности:
- Глубокое сканирование с прогрессом
- Анализ по типам, датам, размерам
- Поиск дублей по имени
- Пустые папки
- Крупнейшие файлы
- Старейшие файлы
- Отчёт для ИИ (структурированный)
- Быстрый отчёт в одну команду
"""

import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from core.module_base import SystemModule


# Системные файлы/папки — пропускаем
SYSTEM_SKIP = {
    'thumbs.db', 'desktop.ini', '.ds_store',
    '$recycle.bin', 'system volume information',
    '$winreagent', 'recovery', '.spotlight-v100',
    '.trashes', '.fseventsd', '.temporaryitems',
}


def human_size(b):
    if b < 1024: return f"{b} B"
    if b < 1024**2: return f"{b/1024:.1f} KB"
    if b < 1024**3: return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.2f} GB"


class ScannerModule(SystemModule):
    def __init__(self):
        super().__init__("scanner", "Сканирование и анализ дисков")
        self.register_command("scan", self.cmd_scan, "Полное сканирование папки/диска")
        self.register_command("biggest_files", self.cmd_biggest_files, "Топ самых больших файлов")
        self.register_command("biggest_folders", self.cmd_biggest_folders, "Топ самых тяжёлых папок")
        self.register_command("by_type", self.cmd_by_type, "Разбивка по типам файлов")
        self.register_command("duplicates", self.cmd_duplicates, "Найти дубликаты имён")
        self.register_command("empty_dirs", self.cmd_empty_dirs, "Найти пустые папки")
        self.register_command("old_files", self.cmd_old_files, "Файлы старше N дней")
        self.register_command("quick", self.cmd_quick, "Быстрый полный отчёт")
        self.register_command("report", self.cmd_report, "Текстовый отчёт для ИИ")

    def _scan(self, target_path, max_depth=20, max_files=50000):
        """Полное сканирование — порт из folder-ai/scanner.js"""
        result = {
            "root": target_path,
            "files": [],
            "dirs": [],
            "total_size": 0,
            "total_files": 0,
            "total_dirs": 0,
            "by_type": defaultdict(int),
            "by_date": defaultdict(int),
            "by_size": {"tiny": 0, "small": 0, "medium": 0, "large": 0, "huge": 0},
            "duplicate_names": [],
            "empty_dirs": [],
            "largest_files": [],
            "oldest_files": [],
            "deepest_path": 0,
        }

        name_count = defaultdict(int)
        file_count = 0

        def scan_dir(dir_path, depth):
            nonlocal file_count
            if depth > max_depth or file_count >= max_files:
                return

            try:
                entries = os.scandir(dir_path)
            except (PermissionError, OSError):
                return

            for entry in entries:
                if entry.name.lower() in SYSTEM_SKIP:
                    continue
                # Пропускаем тяжёлые папки
                if entry.name in ('node_modules', '.git', '__pycache__', 'Windows', 'ProgramData'):
                    continue

                try:
                    if entry.is_dir(follow_symlinks=False):
                        result["total_dirs"] += 1
                        child_count = 0
                        try:
                            child_count = len([e for e in os.scandir(entry.path)
                                             if e.name.lower() not in SYSTEM_SKIP])
                        except (PermissionError, OSError):
                            pass

                        stat = entry.stat(follow_symlinks=False)
                        result["dirs"].append({
                            "name": entry.name,
                            "path": os.path.relpath(entry.path, target_path),
                            "depth": depth,
                            "items": child_count,
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                        })

                        if child_count == 0:
                            result["empty_dirs"].append(os.path.relpath(entry.path, target_path))

                        if depth > result["deepest_path"]:
                            result["deepest_path"] = depth

                        scan_dir(entry.path, depth + 1)

                    elif entry.is_file(follow_symlinks=False):
                        if file_count >= max_files:
                            return
                        file_count += 1
                        result["total_files"] += 1

                        stat = entry.stat(follow_symlinks=False)
                        size = stat.st_size
                        ext = os.path.splitext(entry.name)[1].lower() or "(нет)"
                        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
                        date_month = modified[:7]

                        result["total_size"] += size
                        result["by_type"][ext] += 1
                        result["by_date"][date_month] += 1

                        # Категории размеров
                        if size < 1024: result["by_size"]["tiny"] += 1
                        elif size < 1024**2: result["by_size"]["small"] += 1
                        elif size < 100 * 1024**2: result["by_size"]["medium"] += 1
                        elif size < 1024**3: result["by_size"]["large"] += 1
                        else: result["by_size"]["huge"] += 1

                        name_count[entry.name.lower()] += 1

                        result["files"].append({
                            "name": entry.name,
                            "path": os.path.relpath(entry.path, target_path),
                            "dir": os.path.relpath(dir_path, target_path),
                            "ext": ext,
                            "size": size,
                            "size_human": human_size(size),
                            "modified": modified,
                            "depth": depth,
                        })

                except (PermissionError, OSError):
                    continue

        scan_dir(target_path, 0)

        # Post-process
        result["duplicate_names"] = sorted(
            [{"name": n, "count": c} for n, c in name_count.items() if c > 1],
            key=lambda x: x["count"], reverse=True
        )

        result["largest_files"] = sorted(
            result["files"], key=lambda x: x["size"], reverse=True
        )[:20]

        result["oldest_files"] = sorted(
            result["files"], key=lambda x: x["modified"]
        )[:10]

        result["total_size_human"] = human_size(result["total_size"])
        result["by_type"] = dict(result["by_type"])
        result["by_date"] = dict(result["by_date"])

        return result

    async def cmd_scan(self, path="D:/", max_depth=20):
        """Полное сканирование"""
        p = Path(path)
        if not p.exists():
            return f"Путь '{path}' не существует"
        max_depth = int(max_depth)
        scan = self._scan(path, max_depth=max_depth)

        return {
            "root": scan["root"],
            "total_files": scan["total_files"],
            "total_dirs": scan["total_dirs"],
            "total_size": scan["total_size_human"],
            "deepest_path": scan["deepest_path"],
            "top_types": sorted(scan["by_type"].items(), key=lambda x: x[1], reverse=True)[:15],
            "size_distribution": scan["by_size"],
            "largest_files": [
                {"name": f["name"], "size": f["size_human"], "path": f["path"]}
                for f in scan["largest_files"][:10]
            ],
            "duplicates_count": len(scan["duplicate_names"]),
            "empty_dirs_count": len(scan["empty_dirs"]),
        }

    async def cmd_biggest_files(self, path="D:/", top=20):
        """Топ самых больших файлов"""
        top = int(top)
        scan = self._scan(path)
        return [
            {"name": f["name"], "size": f["size_human"], "modified": f["modified"], "path": f["path"]}
            for f in scan["largest_files"][:top]
        ]

    async def cmd_biggest_folders(self, path="D:/", top=15):
        """Топ самых тяжёлых папок (первый уровень)"""
        top = int(top)
        scan = self._scan(path)

        # Суммировать размеры файлов по папкам верхнего уровня
        folder_sizes = defaultdict(lambda: {"size": 0, "count": 0})
        for f in scan["files"]:
            top_dir = f["dir"].split(os.sep)[0] if f["dir"] != "." else "(корень)"
            folder_sizes[top_dir]["size"] += f["size"]
            folder_sizes[top_dir]["count"] += 1

        result = sorted(
            [{"folder": k, "size": human_size(v["size"]), "size_bytes": v["size"], "files": v["count"]}
             for k, v in folder_sizes.items()],
            key=lambda x: x["size_bytes"], reverse=True
        )[:top]

        return result

    async def cmd_by_type(self, path="D:/"):
        """Разбивка по типам"""
        scan = self._scan(path)

        categories = {
            "Видео": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"},
            "Фото": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".raw", ".heic", ".tiff"},
            "Музыка": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
            "Документы": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"},
            "Архивы": {".zip", ".rar", ".7z", ".tar", ".gz"},
            "3D/CAD": {".sldprt", ".sldasm", ".slddrw", ".step", ".stl", ".dwg", ".dxf"},
            "Код": {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs"},
            "Исполняемые": {".exe", ".msi", ".dll"},
            "ISO/Образы": {".iso", ".img", ".vhd", ".vhdx", ".vmdk"},
            "Базы данных": {".db", ".sqlite", ".mdf", ".ldf", ".bak"},
        }

        result = {}
        for cat, exts in categories.items():
            cat_files = [f for f in scan["files"] if f["ext"] in exts]
            if cat_files:
                total = sum(f["size"] for f in cat_files)
                result[cat] = {
                    "count": len(cat_files),
                    "size": human_size(total),
                    "size_bytes": total,
                    "top3": [{"name": f["name"], "size": f["size_human"]} for f in sorted(cat_files, key=lambda x: x["size"], reverse=True)[:3]]
                }

        return dict(sorted(result.items(), key=lambda x: x[1]["size_bytes"], reverse=True))

    async def cmd_duplicates(self, path="D:/"):
        """Найти дубликаты имён файлов"""
        scan = self._scan(path)
        dups = scan["duplicate_names"][:30]

        # Добавить пути для каждого дубля
        for d in dups:
            d["locations"] = [
                f["dir"] for f in scan["files"]
                if f["name"].lower() == d["name"]
            ][:5]

        return {
            "total_duplicate_names": len(scan["duplicate_names"]),
            "duplicates": dups
        }

    async def cmd_empty_dirs(self, path="D:/"):
        """Пустые папки"""
        scan = self._scan(path)
        return {
            "total": len(scan["empty_dirs"]),
            "dirs": scan["empty_dirs"][:50]
        }

    async def cmd_old_files(self, path="D:/", days=365, min_size_mb=10):
        """Файлы старше N дней"""
        days = int(days)
        min_size = int(min_size_mb) * 1024 * 1024
        cutoff = datetime.now().strftime("%Y-%m-%d")
        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        scan = self._scan(path)
        old = [f for f in scan["files"] if f["modified"] < cutoff_date and f["size"] >= min_size]
        old.sort(key=lambda x: x["size"], reverse=True)

        total = sum(f["size"] for f in old)
        return {
            "criteria": f"Старше {days} дней, больше {min_size_mb} MB",
            "total_files": len(old),
            "total_size": human_size(total),
            "files": [{"name": f["name"], "size": f["size_human"], "modified": f["modified"], "path": f["path"]} for f in old[:25]]
        }

    async def cmd_quick(self, path="D:/"):
        """Быстрый полный отчёт"""
        scan = self._scan(path)

        # Топ папки
        folder_sizes = defaultdict(int)
        for f in scan["files"]:
            top_dir = f["dir"].split(os.sep)[0] if f["dir"] != "." else "(корень)"
            folder_sizes[top_dir] += f["size"]
        top_folders = sorted(folder_sizes.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "path": path,
            "summary": {
                "files": scan["total_files"],
                "dirs": scan["total_dirs"],
                "size": scan["total_size_human"],
                "depth": scan["deepest_path"],
            },
            "size_distribution": scan["by_size"],
            "top_folders": [{"folder": k, "size": human_size(v)} for k, v in top_folders],
            "top_files": [{"name": f["name"], "size": f["size_human"], "path": f["path"]} for f in scan["largest_files"][:10]],
            "top_types": sorted(scan["by_type"].items(), key=lambda x: x[1], reverse=True)[:10],
            "duplicates": len(scan["duplicate_names"]),
            "empty_dirs": len(scan["empty_dirs"]),
        }

    async def cmd_report(self, path="D:/"):
        """Текстовый отчёт — порт buildReport() из folder-ai"""
        scan = self._scan(path)
        lines = []
        lines.append(f"# Отчёт: {scan['root']}")
        lines.append(f"Файлов: {scan['total_files']} | Папок: {scan['total_dirs']} | Размер: {scan['total_size_human']}")
        lines.append(f"Глубина: {scan['deepest_path']} уровней")
        lines.append("")

        # Типы
        types = sorted(scan["by_type"].items(), key=lambda x: x[1], reverse=True)[:15]
        lines.append("## Типы файлов")
        for ext, c in types:
            lines.append(f"  {ext}: {c}")
        lines.append("")

        # Размеры
        s = scan["by_size"]
        lines.append("## По размеру")
        lines.append(f"  <1KB: {s['tiny']} | <1MB: {s['small']} | <100MB: {s['medium']} | <1GB: {s['large']} | >1GB: {s['huge']}")
        lines.append("")

        # Крупнейшие
        lines.append("## Крупнейшие файлы")
        for f in scan["largest_files"][:10]:
            lines.append(f"  {f['size_human']} — {f['path']}")
        lines.append("")

        # Дубли
        if scan["duplicate_names"]:
            lines.append(f"## Дубликаты имён ({len(scan['duplicate_names'])})")
            for d in scan["duplicate_names"][:15]:
                lines.append(f'  "{d["name"]}" x {d["count"]}')
            lines.append("")

        # Пустые папки
        if scan["empty_dirs"]:
            lines.append(f"## Пустые папки ({len(scan['empty_dirs'])})")
            for d in scan["empty_dirs"][:10]:
                lines.append(f"  {d}")
            lines.append("")

        # Старейшие
        lines.append("## Старейшие файлы")
        for f in scan["oldest_files"]:
            lines.append(f"  {f['modified']} — {f['path']}")

        return "\n".join(lines)
