"""
Модуль: Ingest (AI-парковщик данных)

Кидаешь папку или файл → AI разбирает, извлекает знания, индексирует.
Ядро чистое, знания в отдельном хранилище.

Поддерживает: .txt, .md, .json, .csv, .py, .js, .html, .log, .pdf (text), .yaml
Всё что текст — разберёт.

Использование:
  ingest.scan path=/data/docs           — сканировать папку
  ingest.add path=/data/report.txt      — добавить файл
  ingest.process                        — обработать очередь через AI
  ingest.search query=kubernetes        — поиск по базе
  ingest.stats                          — статистика
  ingest.clear domain=project_x         — удалить домен знаний
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from core.module_base import SystemModule

INGEST_DIR = Path(__file__).parent.parent / "knowledge" / "ingested"
INGEST_INDEX = Path(__file__).parent.parent / "knowledge" / "ingest_index.json"
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"


class IngestModule(SystemModule):
    def __init__(self, bus=None, brain=None):
        super().__init__("ingest", "AI-парковщик данных — загрузка и индексация знаний")
        self.bus = bus
        self.brain = brain
        self.queue = []          # очередь файлов на обработку
        self.index = {}          # hash -> metadata
        self.domains = {}        # domain -> [entries]
        self._load_index()

        self.register_command("scan", self.cmd_scan, "Сканировать папку и добавить файлы")
        self.register_command("add", self.cmd_add, "Добавить один файл")
        self.register_command("process", self.cmd_process, "Обработать очередь — AI извлечёт знания")
        self.register_command("ingest_file", self.cmd_ingest_file, "Загрузить и сразу обработать файл")
        self.register_command("search", self.cmd_search, "Поиск по загруженным знаниям")
        self.register_command("stats", self.cmd_stats, "Статистика базы знаний")
        self.register_command("domains", self.cmd_domains, "Список доменов знаний")
        self.register_command("clear", self.cmd_clear, "Удалить домен знаний")
        self.register_command("list_queue", self.cmd_list_queue, "Файлы в очереди")

        # Поддерживаемые форматы
        self.text_exts = {
            '.txt', '.md', '.json', '.csv', '.py', '.js', '.ts',
            '.html', '.css', '.xml', '.yaml', '.yml', '.log',
            '.sh', '.bash', '.conf', '.ini', '.toml', '.env',
            '.sql', '.r', '.go', '.rs', '.java', '.c', '.cpp', '.h',
            '.rb', '.php', '.swift', '.kt', '.scala', '.dockerfile',
        }

    def _load_index(self):
        INGEST_DIR.mkdir(parents=True, exist_ok=True)
        if INGEST_INDEX.exists():
            try:
                data = json.loads(INGEST_INDEX.read_text(encoding="utf-8"))
                self.index = data.get("index", {})
                self.domains = data.get("domains", {})
            except:
                pass

    def _save_index(self):
        INGEST_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "index": self.index,
            "domains": self.domains,
            "updated": datetime.now().isoformat(),
            "total_files": len(self.index),
            "total_domains": len(self.domains),
        }
        INGEST_INDEX.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _file_hash(self, content):
        return hashlib.md5(content.encode("utf-8", errors="replace")).hexdigest()[:12]

    def _read_file(self, path):
        """Прочитать файл и вернуть текст"""
        p = Path(path)
        if not p.exists():
            return None, f"Файл не найден: {path}"
        if p.stat().st_size > 5 * 1024 * 1024:  # 5MB limit
            return None, f"Файл слишком большой: {p.stat().st_size / 1024 / 1024:.1f} MB (макс 5 MB)"
        ext = p.suffix.lower()
        if ext not in self.text_exts:
            return None, f"Формат {ext} не поддерживается"
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            return text, None
        except Exception as e:
            return None, str(e)

    # === COMMANDS ===

    async def cmd_scan(self, path, domain="general"):
        """Сканировать папку, добавить все файлы в очередь"""
        p = Path(path)
        if not p.exists():
            return f"Путь не найден: {path}"
        if not p.is_dir():
            return await self.cmd_add(path=path, domain=domain)

        added = 0
        skipped = 0
        errors = []

        for fp in sorted(p.rglob("*")):
            if fp.is_file() and fp.suffix.lower() in self.text_exts:
                text, err = self._read_file(str(fp))
                if err:
                    errors.append(f"{fp.name}: {err}")
                    continue
                h = self._file_hash(text)
                if h in self.index:
                    skipped += 1
                    continue
                self.queue.append({
                    "path": str(fp),
                    "name": fp.name,
                    "domain": domain,
                    "size": len(text),
                    "hash": h,
                })
                added += 1

        return {
            "scanned": str(p),
            "added_to_queue": added,
            "skipped_duplicates": skipped,
            "errors": errors[:5] if errors else [],
            "message": f"Добавлено {added} файлов в очередь. Запусти ingest.process для обработки.",
        }

    async def cmd_add(self, path, domain="general"):
        """Добавить один файл в очередь"""
        text, err = self._read_file(path)
        if err:
            return {"error": err}
        h = self._file_hash(text)
        if h in self.index:
            return "Файл уже в базе (дубликат)"
        self.queue.append({
            "path": path,
            "name": Path(path).name,
            "domain": domain,
            "size": len(text),
            "hash": h,
        })
        return f"Добавлен в очередь: {Path(path).name} → домен '{domain}'"

    async def cmd_process(self, max_files=10):
        """Обработать очередь — извлечь знания из каждого файла"""
        if not self.queue:
            return "Очередь пуста. Сначала ingest.scan или ingest.add"

        processed = 0
        results = []
        batch = self.queue[:int(max_files)]

        for item in batch:
            text, err = self._read_file(item["path"])
            if err:
                results.append({"file": item["name"], "error": err})
                continue

            # Извлекаем знания
            chunks = self._extract_chunks(text, item["name"])
            domain = item["domain"]

            # Сохраняем
            if domain not in self.domains:
                self.domains[domain] = []

            for chunk in chunks:
                entry = {
                    "id": f"{item['hash']}_{len(self.domains[domain])}",
                    "source": item["name"],
                    "title": chunk["title"],
                    "content": chunk["content"],
                    "tags": chunk.get("tags", []),
                    "added": datetime.now().isoformat(),
                }
                self.domains[domain].append(entry)

            # Сохраняем полный текст
            dest = INGEST_DIR / domain
            dest.mkdir(parents=True, exist_ok=True)
            (dest / f"{item['hash']}_{item['name']}.txt").write_text(
                text[:50000], encoding="utf-8"
            )

            self.index[item["hash"]] = {
                "name": item["name"],
                "domain": domain,
                "chunks": len(chunks),
                "size": item["size"],
                "processed": datetime.now().isoformat(),
            }
            processed += 1
            results.append({"file": item["name"], "chunks": len(chunks), "domain": domain})

        # Убираем обработанные из очереди
        self.queue = self.queue[len(batch):]
        self._save_index()

        return {
            "processed": processed,
            "remaining_in_queue": len(self.queue),
            "results": results,
        }

    async def cmd_ingest_file(self, path, domain="general"):
        """Одной командой: добавить + обработать"""
        await self.cmd_add(path=path, domain=domain)
        return await self.cmd_process(max_files=1)

    def _extract_chunks(self, text, filename):
        """Разбить текст на смысловые куски (chunks)"""
        chunks = []
        ext = Path(filename).suffix.lower()

        # JSON — каждый ключ верхнего уровня
        if ext == '.json':
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    for key, val in data.items():
                        chunks.append({
                            "title": f"{filename} → {key}",
                            "content": json.dumps(val, ensure_ascii=False, indent=1)[:2000],
                            "tags": [key, filename.replace(ext, "")],
                        })
                elif isinstance(data, list):
                    chunks.append({
                        "title": f"{filename} (list, {len(data)} items)",
                        "content": json.dumps(data[:20], ensure_ascii=False, indent=1)[:2000],
                        "tags": [filename.replace(ext, "")],
                    })
                return chunks if chunks else [{"title": filename, "content": text[:2000], "tags": []}]
            except:
                pass

        # CSV — заголовки + первые строки
        if ext == '.csv':
            lines = text.strip().split('\n')
            if lines:
                chunks.append({
                    "title": f"{filename} ({len(lines)} rows)",
                    "content": '\n'.join(lines[:30]),
                    "tags": [filename.replace(ext, ""), "data", "csv"],
                })
            return chunks

        # Markdown / текст — разбить по заголовкам
        if ext in ('.md', '.txt'):
            sections = []
            current_title = filename
            current_lines = []

            for line in text.split('\n'):
                if line.startswith('#') and current_lines:
                    sections.append((current_title, '\n'.join(current_lines)))
                    current_title = line.lstrip('#').strip()
                    current_lines = []
                else:
                    current_lines.append(line)

            if current_lines:
                sections.append((current_title, '\n'.join(current_lines)))

            for title, content in sections:
                if content.strip():
                    chunks.append({
                        "title": title,
                        "content": content[:2000],
                        "tags": [w for w in title.lower().split() if len(w) > 3][:5],
                    })
            return chunks if chunks else [{"title": filename, "content": text[:2000], "tags": []}]

        # Код — весь файл как один чанк с тегами
        if ext in ('.py', '.js', '.ts', '.go', '.rs', '.java', '.sh'):
            # Извлекаем имена функций/классов
            tags = []
            for line in text.split('\n'):
                line = line.strip()
                if line.startswith('def ') or line.startswith('class '):
                    name = line.split('(')[0].split(':')[0].replace('def ', '').replace('class ', '')
                    tags.append(name)
                elif line.startswith('function ') or line.startswith('const '):
                    name = line.split('(')[0].split('=')[0].replace('function ', '').replace('const ', '').strip()
                    if name:
                        tags.append(name)
            chunks.append({
                "title": f"{filename} ({len(text.split(chr(10)))} lines)",
                "content": text[:3000],
                "tags": tags[:10] + [ext.replace('.', '')],
            })
            return chunks

        # Дефолт — разбить по 1500 символов
        for i in range(0, len(text), 1500):
            chunk_text = text[i:i+1500]
            if chunk_text.strip():
                chunks.append({
                    "title": f"{filename} (part {i//1500 + 1})",
                    "content": chunk_text,
                    "tags": [filename.replace(Path(filename).suffix, "")],
                })
        return chunks if chunks else [{"title": filename, "content": text[:2000], "tags": []}]

    async def cmd_search(self, query, domain="", limit=10):
        """Поиск по всем загруженным знаниям"""
        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]
        results = []

        search_domains = [domain] if domain and domain in self.domains else self.domains.keys()

        for d in search_domains:
            for entry in self.domains.get(d, []):
                score = 0
                text = f"{entry['title']} {entry['content']} {' '.join(entry.get('tags', []))}".lower()

                if query_lower in text:
                    score += 10
                for w in query_words:
                    if w in text:
                        score += 2
                    if w in entry.get("title", "").lower():
                        score += 3

                if score > 0:
                    results.append({
                        "domain": d,
                        "title": entry["title"],
                        "content": entry["content"][:300] + "..." if len(entry["content"]) > 300 else entry["content"],
                        "tags": entry.get("tags", []),
                        "source": entry.get("source", ""),
                        "score": score,
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:int(limit)]

    async def cmd_stats(self):
        total_entries = sum(len(v) for v in self.domains.values())
        total_size = sum(info.get("size", 0) for info in self.index.values())
        return {
            "total_files": len(self.index),
            "total_entries": total_entries,
            "total_domains": len(self.domains),
            "domains": {k: len(v) for k, v in self.domains.items()},
            "queue_size": len(self.queue),
            "total_size_kb": round(total_size / 1024, 1),
        }

    async def cmd_domains(self):
        return {k: {"entries": len(v), "files": len(set(e.get("source", "") for e in v))} for k, v in self.domains.items()}

    async def cmd_clear(self, domain):
        """Удалить домен знаний"""
        if domain not in self.domains:
            return f"Домен '{domain}' не найден"
        count = len(self.domains[domain])
        del self.domains[domain]
        # Удалить из index
        self.index = {k: v for k, v in self.index.items() if v.get("domain") != domain}
        # Удалить файлы
        d = INGEST_DIR / domain
        if d.exists():
            import shutil
            shutil.rmtree(d)
        self._save_index()
        return f"Домен '{domain}' удалён ({count} записей)"

    async def cmd_list_queue(self):
        if not self.queue:
            return "Очередь пуста"
        return [{"name": q["name"], "domain": q["domain"], "size_kb": round(q["size"]/1024, 1)} for q in self.queue]
