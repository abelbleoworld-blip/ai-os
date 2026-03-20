"""
Модуль: Learner (Самообучение)
Активное обучение ядра AI-OS.

Что делает:
1. Учится на каждом диалоге — запоминает что сработало
2. Автоматически создаёт навыки из повторяющихся действий
3. Пополняет knowledge base из результатов команд
4. Запоминает ошибки и как они были решены
5. Оценивает качество своих ответов (feedback loop)
6. Экспортирует опыт между нодами (mesh learning)
"""

import json
import time
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict
from core.module_base import SystemModule
from ai.knowledge import KnowledgeBase

MEMORY_DIR = Path(__file__).parent.parent / "memory"


class LearnerModule(SystemModule):
    def __init__(self, bus=None, brain=None, trainer=None):
        super().__init__("learner", "Самообучение — ядро учится на каждом действии")
        self.bus = bus
        self.brain = brain
        self.trainer = trainer

        # Память обучения
        self.lessons = []           # извлечённые уроки
        self.error_fixes = {}       # ошибка -> как починили
        self.context_memory = []    # последние N взаимодействий для контекста
        self.feedback_scores = []   # оценки качества ответов
        self.learned_mappings = {}  # "фраза пользователя" -> "лучшая команда"

        self._load()

        self.register_command("status", self.cmd_status, "Статус обучения")
        self.register_command("lessons", self.cmd_lessons, "Извлечённые уроки")
        self.register_command("learn_from", self.cmd_learn_from, "Обучиться на конкретном примере")
        self.register_command("feedback", self.cmd_feedback, "Оценить последний ответ (good/bad)")
        self.register_command("auto_skills", self.cmd_auto_skills, "Авто-создание навыков из паттернов")
        self.register_command("forget", self.cmd_forget, "Забыть неудачный паттерн")
        self.register_command("export", self.cmd_export, "Экспорт опыта для других нод")
        self.register_command("import_exp", self.cmd_import, "Импорт опыта от другой ноды")
        self.register_command("train_knowledge", self.cmd_train_knowledge, "Обучить knowledge base из результатов")

    def _file(self):
        return MEMORY_DIR / "learner.json"

    def _load(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        f = self._file()
        if f.exists():
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                self.lessons = d.get("lessons", [])
                self.error_fixes = d.get("error_fixes", {})
                self.learned_mappings = d.get("learned_mappings", {})
                self.feedback_scores = d.get("feedback_scores", [])
            except:
                pass

    def _save(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "lessons": self.lessons[-500:],
            "error_fixes": self.error_fixes,
            "learned_mappings": self.learned_mappings,
            "feedback_scores": self.feedback_scores[-200:],
            "updated": datetime.now().isoformat(),
        }
        self._file().write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # === НАБЛЮДЕНИЕ (вызывается после каждого действия) ===

    def observe(self, user_input: str, result, method="claude"):
        """Наблюдать за каждым взаимодействием и учиться"""
        ts = datetime.now().isoformat()

        # 1. Сохраняем контекст
        entry = {
            "time": ts,
            "input": user_input,
            "method": method,
            "success": self._is_success(result),
        }

        # Если Claude вернул actions — запоминаем маппинг
        if isinstance(result, dict) and "actions" in str(result):
            actions = None
            if hasattr(result, 'get'):
                actions = result.get("results") or result.get("actions")
            if actions:
                entry["actions"] = self._extract_actions(actions)

        self.context_memory.append(entry)
        self.context_memory = self.context_memory[-50:]  # keep last 50

        # 2. Автоматические уроки
        self._auto_learn(user_input, result, entry)

        # 3. Детекция ошибок
        if not entry["success"]:
            self._learn_from_error(user_input, result)

        # 4. Автосохранение
        if len(self.context_memory) % 5 == 0:
            self._save()

    def _is_success(self, result):
        if isinstance(result, str):
            return "ошибка" not in result.lower() and "error" not in result.lower()
        if isinstance(result, dict):
            if result.get("status") == "error":
                return False
            if "error" in str(result.get("result", "")):
                return False
        return True

    def _extract_actions(self, actions):
        """Извлечь модуль.команда из результата"""
        extracted = []
        if isinstance(actions, list):
            for a in actions:
                if isinstance(a, dict):
                    m = a.get("module", "")
                    c = a.get("command", "")
                    if m and c:
                        extracted.append(f"{m}.{c}")
        return extracted

    def _auto_learn(self, user_input, result, entry):
        """Автоматическое извлечение уроков"""
        inp = user_input.strip().lower()

        # Если успешно и есть actions — запомнить маппинг
        if entry["success"] and entry.get("actions"):
            key = self._normalize_input(inp)
            if key and len(key) > 3:
                self.learned_mappings[key] = {
                    "actions": entry["actions"],
                    "count": self.learned_mappings.get(key, {}).get("count", 0) + 1,
                    "last": entry["time"],
                }

        # Детекция паттернов: если 2 последних запроса часто идут вместе
        if len(self.context_memory) >= 2:
            prev = self.context_memory[-2]
            curr = self.context_memory[-1]
            if prev["success"] and curr["success"]:
                pair = f"{self._normalize_input(prev['input'])} -> {self._normalize_input(curr['input'])}"
                existing = [l for l in self.lessons if l.get("pattern") == pair]
                if existing:
                    existing[0]["count"] += 1
                    existing[0]["last"] = entry["time"]
                    # Авто-навык при 3+ повторениях
                    if existing[0]["count"] >= 3 and not existing[0].get("skill_created"):
                        self._try_create_skill(existing[0])
                else:
                    self.lessons.append({
                        "type": "sequence",
                        "pattern": pair,
                        "count": 1,
                        "first": entry["time"],
                        "last": entry["time"],
                    })

    def _normalize_input(self, inp):
        """Нормализовать ввод для маппинга"""
        # Убираем лишние слова, оставляем суть
        stop = {"что", "как", "где", "мне", "покажи", "скажи", "пожалуйста", "ну", "а", "и", "в", "на", "с", "у"}
        words = [w for w in inp.lower().split() if w not in stop and len(w) > 2]
        return " ".join(words[:5])

    def _learn_from_error(self, user_input, result):
        """Запомнить ошибку для будущего"""
        error_key = self._normalize_input(user_input)
        error_msg = str(result)[:200]
        self.error_fixes[error_key] = {
            "error": error_msg,
            "time": datetime.now().isoformat(),
            "fixed": False,
        }

    def _try_create_skill(self, lesson):
        """Попробовать создать навык из повторяющегося паттерна"""
        if not self.brain:
            return
        parts = lesson["pattern"].split(" -> ")
        if len(parts) < 2:
            return

        # Собираем actions из маппингов
        steps = []
        for part in parts:
            mapping = self.learned_mappings.get(part, {})
            if mapping.get("actions"):
                for action_str in mapping["actions"]:
                    if "." in action_str:
                        m, c = action_str.split(".", 1)
                        steps.append({"module": m, "command": c})

        if steps:
            name = f"auto_{len(self.brain.skills) + 1}"
            desc = f"Авто: {lesson['pattern']} ({lesson['count']}x)"
            self.brain.learn_skill(name, steps, desc)
            lesson["skill_created"] = True
            self._save()

    # === COMMANDS ===

    async def cmd_status(self):
        total_obs = len(self.context_memory)
        success_rate = 0
        if total_obs:
            success_rate = round(sum(1 for c in self.context_memory if c["success"]) / total_obs * 100, 1)

        good = sum(1 for f in self.feedback_scores if f["score"] == "good")
        bad = sum(1 for f in self.feedback_scores if f["score"] == "bad")

        return {
            "observations": total_obs,
            "lessons_learned": len(self.lessons),
            "mappings": len(self.learned_mappings),
            "error_fixes": len(self.error_fixes),
            "success_rate": f"{success_rate}%",
            "feedback": {"good": good, "bad": bad, "total": len(self.feedback_scores)},
            "auto_skills_created": len([l for l in self.lessons if l.get("skill_created")]),
            "top_patterns": sorted(
                [l for l in self.lessons if l["count"] >= 2],
                key=lambda x: x["count"], reverse=True
            )[:5],
        }

    async def cmd_lessons(self, count=10):
        return sorted(self.lessons, key=lambda x: x.get("count", 0), reverse=True)[:int(count)]

    async def cmd_learn_from(self, phrase, module, command, **args):
        """Обучить: 'эта фраза' → module.command"""
        key = self._normalize_input(phrase)
        action = f"{module}.{command}"
        self.learned_mappings[key] = {
            "actions": [action],
            "count": 1,
            "last": datetime.now().isoformat(),
            "manual": True,
        }
        self._save()
        return f"Запомнил: '{phrase}' → {action}"

    async def cmd_feedback(self, score="good"):
        """Оценить последний ответ"""
        if not self.context_memory:
            return "Нет взаимодействий для оценки"
        last = self.context_memory[-1]
        self.feedback_scores.append({
            "input": last["input"],
            "score": score,
            "time": datetime.now().isoformat(),
        })

        # Если bad — пометить маппинг как плохой
        if score == "bad":
            key = self._normalize_input(last["input"])
            if key in self.learned_mappings:
                self.learned_mappings[key]["bad_count"] = self.learned_mappings[key].get("bad_count", 0) + 1
                # Удалить маппинг если 3+ bad
                if self.learned_mappings[key].get("bad_count", 0) >= 3:
                    del self.learned_mappings[key]
                    self._save()
                    return "Плохой паттерн удалён. Спасибо за обратную связь!"

        self._save()
        return f"Спасибо! Оценка '{score}' записана."

    async def cmd_auto_skills(self):
        """Показать и создать автонавыки из паттернов"""
        candidates = [l for l in self.lessons if l.get("count", 0) >= 2 and not l.get("skill_created")]
        if not candidates:
            return "Пока недостаточно повторяющихся паттернов. Продолжай пользоваться — я учусь."

        created = []
        for lesson in candidates:
            if lesson["count"] >= 3:
                self._try_create_skill(lesson)
                if lesson.get("skill_created"):
                    created.append(lesson["pattern"])

        if created:
            self._save()
            return {"created": created, "message": f"Создано {len(created)} навыков из паттернов"}
        return {"candidates": [{"pattern": l["pattern"], "count": l["count"]} for l in candidates[:5]], "message": "Паттерны найдены, но ещё мало повторений (нужно 3+)"}

    async def cmd_forget(self, pattern):
        """Забыть неудачный паттерн"""
        self.lessons = [l for l in self.lessons if l.get("pattern") != pattern]
        if pattern in self.learned_mappings:
            del self.learned_mappings[pattern]
        self._save()
        return f"Забыл паттерн: {pattern}"

    async def cmd_export(self):
        """Экспорт всего опыта для трансфера на другую ноду"""
        return {
            "lessons": self.lessons,
            "mappings": self.learned_mappings,
            "error_fixes": self.error_fixes,
            "exported_at": datetime.now().isoformat(),
        }

    async def cmd_import(self, data):
        """Импорт опыта от другой ноды"""
        if isinstance(data, str):
            data = json.loads(data)
        imported = 0
        for lesson in data.get("lessons", []):
            existing = [l for l in self.lessons if l.get("pattern") == lesson.get("pattern")]
            if not existing:
                self.lessons.append(lesson)
                imported += 1
        for key, val in data.get("mappings", {}).items():
            if key not in self.learned_mappings:
                self.learned_mappings[key] = val
                imported += 1
        for key, val in data.get("error_fixes", {}).items():
            if key not in self.error_fixes:
                self.error_fixes[key] = val
                imported += 1
        self._save()
        return f"Импортировано {imported} записей"

    async def cmd_train_knowledge(self, module_name="system"):
        """Обучить knowledge base из накопленного опыта"""
        kb = KnowledgeBase(module_name)
        added = 0
        # Добавляем решённые ошибки как solutions
        for key, fix in self.error_fixes.items():
            if fix.get("fixed") and fix.get("solution"):
                existing = kb.find_solution(key)
                if not existing:
                    kb.add_solution(key, fix["solution"])
                    added += 1
        # Добавляем частые маппинги как знания
        for key, mapping in self.learned_mappings.items():
            if mapping.get("count", 0) >= 3:
                existing = kb.search(key, limit=1)
                if not existing:
                    kb.add(
                        f"Частый запрос: {key}",
                        f"Решение: {', '.join(mapping.get('actions', []))}",
                        tags=key.split(),
                    )
                    added += 1
        kb.save()
        return f"Добавлено {added} записей в knowledge base '{module_name}'"

    # === HELPER: подсказка для Claude brain ===

    def get_suggestion_for(self, user_input):
        """Claude brain может спросить learner: что делать с этим запросом?"""
        key = self._normalize_input(user_input)

        # Проверить маппинги
        if key in self.learned_mappings:
            m = self.learned_mappings[key]
            if m.get("bad_count", 0) < 2:
                return {"source": "learned_mapping", "actions": m["actions"], "confidence": min(m.get("count", 1) / 5, 1.0)}

        # Проверить похожие маппинги
        for mkey, mval in self.learned_mappings.items():
            if any(w in mkey for w in key.split() if len(w) > 3):
                return {"source": "similar_mapping", "actions": mval["actions"], "confidence": 0.5}

        return None
