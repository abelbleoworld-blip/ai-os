"""
База знаний (Knowledge Base).

Каждый модуль получает свою базу знаний — как справочник специалиста.
Электрик знает про провода, сантехник — про трубы.

База умеет:
1. Хранить факты, решения, ссылки на документацию
2. Искать по ключевым словам
3. Пополняться — модуль нашёл решение, сохранил на будущее
4. Ранжировать — часто используемые знания поднимаются выше

Знания сохраняются между сессиями в ai-os/knowledge/
"""

import json
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict


KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


class KnowledgeBase:
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.entries = []          # все записи знаний
        self.sources = []          # источники (ссылки на документацию)
        self.solutions = {}        # проблема -> решение (кэш решений)
        self._load()

    def _file_path(self):
        return KNOWLEDGE_DIR / f"{self.module_name}.json"

    def _load(self):
        """Загрузить знания из файла"""
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        fp = self._file_path()
        if fp.exists():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                self.entries = data.get("entries", [])
                self.sources = data.get("sources", [])
                self.solutions = data.get("solutions", {})
            except:
                pass

    def save(self):
        """Сохранить знания"""
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "module": self.module_name,
            "entries": self.entries,
            "sources": self.sources,
            "solutions": self.solutions,
            "updated_at": datetime.now().isoformat()
        }
        self._file_path().write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def add(self, title: str, content: str, tags: list = None, source: str = ""):
        """
        Добавить знание.
        Пример: kb.add("Очистка DNS кэша", "ipconfig /flushdns", ["dns", "сеть"], "Microsoft Docs")
        """
        entry = {
            "id": len(self.entries) + 1,
            "title": title,
            "content": content,
            "tags": tags or [],
            "source": source,
            "created": datetime.now().isoformat(),
            "used_count": 0,
            "rating": 0        # повышается при успешном использовании
        }
        self.entries.append(entry)
        self.save()
        return entry["id"]

    def add_source(self, name: str, url: str, description: str = ""):
        """Добавить источник документации"""
        self.sources.append({
            "name": name,
            "url": url,
            "description": description,
            "added": datetime.now().isoformat()
        })
        self.save()

    def add_solution(self, problem: str, solution: str, success: bool = True):
        """
        Запомнить решение проблемы.
        Модуль столкнулся с ошибкой, нашёл решение — сохранил.
        В следующий раз сразу знает что делать.
        """
        self.solutions[problem] = {
            "solution": solution,
            "success": success,
            "times_used": 0,
            "saved_at": datetime.now().isoformat()
        }
        self.save()

    def search(self, query: str, limit: int = 10):
        """
        Поиск по базе знаний.
        Ищет по заголовкам, содержимому и тегам.
        Результаты ранжируются по рейтингу и частоте использования.
        """
        query_lower = query.lower()
        query_words = query_lower.split()
        results = []

        for entry in self.entries:
            score = 0
            text = f"{entry['title']} {entry['content']} {' '.join(entry.get('tags', []))}".lower()

            # Точное совпадение фразы — высший приоритет
            if query_lower in text:
                score += 10

            # Совпадение отдельных слов
            for word in query_words:
                if word in text:
                    score += 2
                if word in entry.get("title", "").lower():
                    score += 3  # в заголовке важнее

            # Бонус за рейтинг и частоту
            score += entry.get("rating", 0) * 0.5
            score += entry.get("used_count", 0) * 0.3

            if score > 0:
                results.append({**entry, "_score": score})

        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:limit]

    def find_solution(self, problem: str):
        """Найти решение для проблемы"""
        problem_lower = problem.lower()
        # Точное совпадение
        if problem in self.solutions:
            sol = self.solutions[problem]
            sol["times_used"] += 1
            self.save()
            return sol

        # Поиск по ключевым словам
        for key, sol in self.solutions.items():
            if any(word in key.lower() for word in problem_lower.split() if len(word) > 3):
                sol["times_used"] += 1
                self.save()
                return {**sol, "matched_problem": key}

        return None

    def mark_used(self, entry_id: int, success: bool = True):
        """Отметить знание как использованное — повышает рейтинг"""
        for entry in self.entries:
            if entry["id"] == entry_id:
                entry["used_count"] += 1
                entry["rating"] += 1 if success else -1
                self.save()
                return True
        return False

    def get_stats(self):
        """Статистика базы знаний"""
        return {
            "module": self.module_name,
            "total_entries": len(self.entries),
            "total_sources": len(self.sources),
            "total_solutions": len(self.solutions),
            "top_rated": sorted(self.entries, key=lambda x: x.get("rating", 0), reverse=True)[:5],
            "most_used": sorted(self.entries, key=lambda x: x.get("used_count", 0), reverse=True)[:5],
        }

    def export_all(self):
        """Экспорт всех знаний"""
        return {
            "entries": self.entries,
            "sources": self.sources,
            "solutions": self.solutions,
        }
