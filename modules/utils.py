"""
Модуль: Utils (Утилиты)
Terminal + Finder + AI в одном. Быстрые инструменты для повседневной работы.

Группы утилит:
  files.*    — просмотр, поиск, превью, размеры (Finder)
  term.*     — выполнение команд, пайпы, скрипты (Terminal)
  text.*     — работа с текстом: grep, diff, count, replace
  sys.*      — быстрая системная инфа: ip, who, env, ports
  convert.*  — конвертация: json↔yaml, csv→json, base64
  clip.*     — буфер обмена, заметки, сниппеты
"""

import os
import json
import subprocess
import shutil
import hashlib
import base64
from datetime import datetime
from pathlib import Path
from core.module_base import SystemModule

NOTES_DIR = Path(__file__).parent.parent / "memory" / "notes"


class UtilsModule(SystemModule):
    def __init__(self, bus=None):
        super().__init__("utils", "Утилиты — terminal + finder + AI tools")
        self.bus = bus
        self.clipboard = []  # буфер
        self.notes = {}      # заметки
        self._load_notes()

        # === FILES (Finder) ===
        self.register_command("ls", self.cmd_ls, "Список файлов (tree-style)")
        self.register_command("tree", self.cmd_tree, "Дерево папки")
        self.register_command("find", self.cmd_find, "Поиск файлов по имени/паттерну")
        self.register_command("preview", self.cmd_preview, "Превью файла (первые N строк)")
        self.register_command("size", self.cmd_size, "Размер файла/папки")
        self.register_command("recent", self.cmd_recent, "Недавно изменённые файлы")
        self.register_command("duplicates", self.cmd_duplicates, "Найти дубликаты по хешу")

        # === TERMINAL ===
        self.register_command("exec", self.cmd_exec, "Выполнить shell команду")
        self.register_command("which", self.cmd_which, "Найти исполняемый файл")
        self.register_command("env", self.cmd_env, "Переменные окружения")

        # === TEXT ===
        self.register_command("grep", self.cmd_grep, "Поиск текста в файлах")
        self.register_command("wc", self.cmd_wc, "Подсчёт строк/слов/символов")
        self.register_command("head", self.cmd_head, "Первые N строк файла")
        self.register_command("tail", self.cmd_tail, "Последние N строк файла")
        self.register_command("diff", self.cmd_diff, "Сравнить два файла")

        # === SYSTEM ===
        self.register_command("ip", self.cmd_ip, "Текущий IP адрес")
        self.register_command("ports", self.cmd_ports, "Открытые порты")
        self.register_command("df", self.cmd_df, "Свободное место")
        self.register_command("top", self.cmd_top, "Топ процессов")
        self.register_command("uptime", self.cmd_uptime, "Аптайм системы")

        # === CONVERT ===
        self.register_command("json2yaml", self.cmd_json2yaml, "JSON → YAML")
        self.register_command("b64encode", self.cmd_b64encode, "Base64 encode")
        self.register_command("b64decode", self.cmd_b64decode, "Base64 decode")
        self.register_command("hash", self.cmd_hash, "MD5/SHA256 хеш файла")

        # === CLIPBOARD / NOTES ===
        self.register_command("note", self.cmd_note, "Сохранить заметку")
        self.register_command("notes", self.cmd_notes, "Список заметок")
        self.register_command("note_get", self.cmd_note_get, "Прочитать заметку")
        self.register_command("note_del", self.cmd_note_del, "Удалить заметку")

    # ==================== FILES ====================

    async def cmd_ls(self, path=".", sort="name", hidden=False):
        p = Path(path).resolve()
        if not p.exists():
            return f"Not found: {path}"
        items = []
        for f in sorted(p.iterdir()):
            if not hidden and f.name.startswith('.'):
                continue
            is_dir = f.is_dir()
            try:
                size = f.stat().st_size if not is_dir else sum(
                    x.stat().st_size for x in f.rglob('*') if x.is_file()
                ) if is_dir else 0
            except:
                size = 0
            items.append({
                "name": f.name + ("/" if is_dir else ""),
                "type": "dir" if is_dir else "file",
                "size": self._fmt_size(size),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
        if sort == "size":
            items.sort(key=lambda x: x["size"], reverse=True)
        elif sort == "date":
            items.sort(key=lambda x: x["modified"], reverse=True)
        return {"path": str(p), "count": len(items), "items": items}

    async def cmd_tree(self, path=".", depth=3, max_items=50):
        lines = []
        count = [0]
        def walk(p, prefix="", d=0):
            if d > int(depth) or count[0] > int(max_items):
                return
            try:
                entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except PermissionError:
                return
            for i, entry in enumerate(entries):
                if entry.name.startswith('.'):
                    continue
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
                count[0] += 1
                if count[0] > int(max_items):
                    lines.append(f"{prefix}    ... (truncated)")
                    return
                if entry.is_dir():
                    ext = "    " if is_last else "│   "
                    walk(entry, prefix + ext, d + 1)
        p = Path(path).resolve()
        lines.append(str(p))
        walk(p)
        return "\n".join(lines)

    async def cmd_find(self, pattern, path=".", max_results=20):
        p = Path(path).resolve()
        results = []
        for f in p.rglob(pattern):
            if len(results) >= int(max_results):
                break
            results.append({
                "path": str(f),
                "name": f.name,
                "size": self._fmt_size(f.stat().st_size) if f.is_file() else "dir",
            })
        return {"pattern": pattern, "found": len(results), "results": results}

    async def cmd_preview(self, path, lines=20):
        p = Path(path)
        if not p.exists():
            return f"Not found: {path}"
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            preview = "\n".join(text.split("\n")[:int(lines)])
            return {"file": p.name, "lines": min(int(lines), text.count("\n") + 1), "total_lines": text.count("\n") + 1, "content": preview}
        except:
            return f"Cannot read: {path}"

    async def cmd_size(self, path):
        p = Path(path).resolve()
        if not p.exists():
            return f"Not found: {path}"
        if p.is_file():
            return {"path": str(p), "size": self._fmt_size(p.stat().st_size), "bytes": p.stat().st_size}
        total = sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
        files = sum(1 for f in p.rglob('*') if f.is_file())
        dirs = sum(1 for f in p.rglob('*') if f.is_dir())
        return {"path": str(p), "size": self._fmt_size(total), "bytes": total, "files": files, "dirs": dirs}

    async def cmd_recent(self, path=".", count=10):
        p = Path(path).resolve()
        files = []
        for f in p.rglob('*'):
            if f.is_file() and not f.name.startswith('.'):
                try:
                    files.append((f, f.stat().st_mtime))
                except:
                    pass
        files.sort(key=lambda x: x[1], reverse=True)
        return [{"name": f.name, "path": str(f), "modified": datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M"), "size": self._fmt_size(f.stat().st_size)} for f, t in files[:int(count)]]

    async def cmd_duplicates(self, path=".", min_size=1024):
        p = Path(path).resolve()
        hashes = {}
        for f in p.rglob('*'):
            if f.is_file() and f.stat().st_size >= int(min_size):
                try:
                    h = hashlib.md5(f.read_bytes()[:8192]).hexdigest()
                    hashes.setdefault(h, []).append(str(f))
                except:
                    pass
        dupes = {h: paths for h, paths in hashes.items() if len(paths) > 1}
        return {"duplicates": len(dupes), "groups": list(dupes.values())[:10]}

    # ==================== TERMINAL ====================

    async def cmd_exec(self, command, timeout=30):
        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=int(timeout))
            return {"stdout": r.stdout[:5000], "stderr": r.stderr[:1000], "code": r.returncode}
        except subprocess.TimeoutExpired:
            return {"error": f"Timeout after {timeout}s"}

    async def cmd_which(self, program):
        r = shutil.which(program)
        return r if r else f"'{program}' not found in PATH"

    async def cmd_env(self, filter=""):
        envs = dict(os.environ)
        if filter:
            envs = {k: v for k, v in envs.items() if filter.lower() in k.lower()}
        return envs

    # ==================== TEXT ====================

    async def cmd_grep(self, pattern, path=".", ext="*"):
        p = Path(path).resolve()
        results = []
        glob = f"*.{ext}" if ext != "*" else "*"
        for f in p.rglob(glob):
            if not f.is_file():
                continue
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
                    if pattern.lower() in line.lower():
                        results.append({"file": str(f), "line": i, "text": line.strip()[:200]})
                        if len(results) >= 30:
                            return {"pattern": pattern, "found": len(results), "results": results, "truncated": True}
            except:
                pass
        return {"pattern": pattern, "found": len(results), "results": results}

    async def cmd_wc(self, path):
        p = Path(path)
        text = p.read_text(encoding="utf-8", errors="replace")
        return {"file": p.name, "lines": text.count("\n") + 1, "words": len(text.split()), "chars": len(text), "size": self._fmt_size(len(text.encode()))}

    async def cmd_head(self, path, n=10):
        return await self.cmd_preview(path, lines=n)

    async def cmd_tail(self, path, n=10):
        p = Path(path)
        lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
        return {"file": p.name, "content": "\n".join(lines[-int(n):])}

    async def cmd_diff(self, file1, file2):
        try:
            r = subprocess.run(["diff", "--unified=3", file1, file2], capture_output=True, text=True)
            return r.stdout[:5000] if r.stdout else "Files are identical"
        except:
            return "diff not available"

    # ==================== SYSTEM ====================

    async def cmd_ip(self):
        import psutil
        addrs = psutil.net_if_addrs()
        result = {}
        for name, addr_list in addrs.items():
            for addr in addr_list:
                if addr.family.name == 'AF_INET' and addr.address != '127.0.0.1':
                    result[name] = addr.address
        return result

    async def cmd_ports(self):
        import psutil
        conns = []
        for c in psutil.net_connections(kind='inet'):
            if c.status == 'LISTEN':
                conns.append({"port": c.laddr.port, "addr": c.laddr.ip, "pid": c.pid})
        conns.sort(key=lambda x: x["port"])
        return conns[:20]

    async def cmd_df(self):
        import psutil
        result = []
        seen = set()
        for p in psutil.disk_partitions():
            if p.mountpoint in ('/etc/resolv.conf', '/etc/hostname', '/etc/hosts'):
                continue
            try:
                u = psutil.disk_usage(p.mountpoint)
                key = (u.total, u.free)
                if key in seen:
                    continue
                seen.add(key)
                result.append({"mount": p.mountpoint, "total": self._fmt_size(u.total), "free": self._fmt_size(u.free), "used_pct": u.percent})
            except:
                pass
        return result

    async def cmd_top(self, n=10):
        import psutil
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
            try:
                info = p.info
                procs.append({"name": info['name'], "pid": info['pid'], "mem_mb": round(info['memory_info'].rss / 1048576, 1), "cpu": info['cpu_percent']})
            except:
                pass
        procs.sort(key=lambda x: x['mem_mb'], reverse=True)
        return procs[:int(n)]

    async def cmd_uptime(self):
        import psutil
        boot = datetime.fromtimestamp(psutil.boot_time())
        delta = datetime.now() - boot
        return f"{delta.days}d {delta.seconds // 3600}h {(delta.seconds % 3600) // 60}m"

    # ==================== CONVERT ====================

    async def cmd_json2yaml(self, path):
        import yaml
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return yaml.dump(data, allow_unicode=True, default_flow_style=False)

    async def cmd_b64encode(self, text):
        return base64.b64encode(text.encode()).decode()

    async def cmd_b64decode(self, text):
        return base64.b64decode(text).decode()

    async def cmd_hash(self, path):
        p = Path(path)
        data = p.read_bytes()
        return {"file": p.name, "md5": hashlib.md5(data).hexdigest(), "sha256": hashlib.sha256(data).hexdigest(), "size": self._fmt_size(len(data))}

    # ==================== NOTES ====================

    def _load_notes(self):
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        for f in NOTES_DIR.glob("*.json"):
            try:
                self.notes[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except:
                pass

    def _save_note(self, name):
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        (NOTES_DIR / f"{name}.json").write_text(
            json.dumps(self.notes[name], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def cmd_note(self, name, text):
        self.notes[name] = {"text": text, "created": datetime.now().isoformat()}
        self._save_note(name)
        return f"Note '{name}' saved"

    async def cmd_notes(self):
        return {k: {"preview": v["text"][:80], "created": v.get("created", "")} for k, v in self.notes.items()}

    async def cmd_note_get(self, name):
        return self.notes.get(name, f"Note '{name}' not found")

    async def cmd_note_del(self, name):
        if name in self.notes:
            del self.notes[name]
            f = NOTES_DIR / f"{name}.json"
            if f.exists():
                f.unlink()
            return f"Note '{name}' deleted"
        return f"Note '{name}' not found"

    # ==================== HELPERS ====================

    def _fmt_size(self, b):
        for u in ['B', 'KB', 'MB', 'GB', 'TB']:
            if b < 1024:
                return f"{b:.1f} {u}"
            b /= 1024
        return f"{b:.1f} PB"
