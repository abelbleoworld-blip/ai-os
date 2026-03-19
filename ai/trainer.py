"""
AutoTrainer — автоматическое обучение системы.

Наблюдает за всем что происходит и учится:
1. Считает частоту команд — что используется часто
2. Находит последовательности — если после A всегда идёт B, предлагает объединить
3. Запоминает ошибки — если команда падает, запоминает контекст
4. Оптимизирует — предлагает ускорить частые операции

Как стажёр, который смотрит за мастером и записывает:
"каждое утро он первым делом проверяет почту, потом открывает отчёт"
→ можно автоматизировать.
"""

import json
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict


MEMORY_DIR = Path(__file__).parent.parent / "memory"


class AutoTrainer:
    def __init__(self, brain):
        self.brain = brain
        self.command_counts = Counter()       # сколько раз вызвана каждая команда
        self.sequences = []                   # последовательности команд
        self.error_log = []                   # ошибки и контексты
        self.suggestions = []                 # предложения по оптимизации
        self.sequence_buffer = []             # буфер текущей последовательности
        self.auto_skills_offered = set()      # уже предложенные навыки (не спамить)
        self._load()

    def _load(self):
        """Загрузить накопленную статистику"""
        stats_file = MEMORY_DIR / "trainer_stats.json"
        if stats_file.exists():
            data = json.loads(stats_file.read_text(encoding="utf-8"))
            self.command_counts = Counter(data.get("command_counts", {}))
            self.sequences = data.get("sequences", [])
            self.error_log = data.get("error_log", [])

    def save(self):
        """Сохранить статистику"""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "command_counts": dict(self.command_counts),
            "sequences": self.sequences[-500:],  # последние 500
            "error_log": self.error_log[-200:],
            "last_saved": datetime.now().isoformat()
        }
        (MEMORY_DIR / "trainer_stats.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def observe(self, user_input: str, result: dict):
        """
        Главная функция — наблюдать за каждым действием.
        Вызывается после каждой команды.
        """
        cmd_key = user_input.strip().split()[0] if user_input.strip() else ""

        # 1. Считаем частоту
        self.command_counts[cmd_key] += 1

        # 2. Добавляем в буфер последовательности
        self.sequence_buffer.append({
            "command": user_input.strip(),
            "time": datetime.now().isoformat(),
            "success": not (isinstance(result, dict) and "error" in result)
        })

        # Если буфер больше 2 — ищем паттерны
        if len(self.sequence_buffer) >= 2:
            self._detect_sequence()

        # 3. Если ошибка — запоминаем
        if isinstance(result, dict) and result.get("status") == "error":
            self.error_log.append({
                "command": user_input,
                "error": str(result.get("result", "")),
                "time": datetime.now().isoformat()
            })

        # 4. Автосохранение каждые 10 команд
        total = sum(self.command_counts.values())
        if total % 10 == 0:
            self.save()

    def _detect_sequence(self):
        """Найти повторяющиеся последовательности"""
        if len(self.sequence_buffer) < 2:
            return

        # Берём последние 2-5 команд как возможную последовательность
        for window in range(2, min(6, len(self.sequence_buffer) + 1)):
            recent = [s["command"] for s in self.sequence_buffer[-window:]]
            seq_key = " -> ".join(recent)

            # Проверяем, встречалась ли эта последовательность раньше
            found = False
            for seq in self.sequences:
                if seq["key"] == seq_key:
                    seq["count"] += 1
                    seq["last_seen"] = datetime.now().isoformat()
                    found = True
                    break

            if not found:
                self.sequences.append({
                    "key": seq_key,
                    "commands": recent,
                    "count": 1,
                    "first_seen": datetime.now().isoformat(),
                    "last_seen": datetime.now().isoformat()
                })

    def get_suggestions(self):
        """
        Анализ и рекомендации:
        - Частые команды → предложить горячие клавиши
        - Повторяющиеся последовательности → предложить сохранить как навык
        - Частые ошибки → предложить исправление
        """
        suggestions = []

        # Частые последовательности → навыки
        for seq in self.sequences:
            if seq["count"] >= 3 and seq["key"] not in self.auto_skills_offered:
                suggestions.append({
                    "type": "auto_skill",
                    "message": f"Вы часто выполняете: {seq['key']} ({seq['count']} раз). Сохранить как навык?",
                    "sequence": seq
                })

        # Топ команд
        top = self.command_counts.most_common(5)
        if top:
            suggestions.append({
                "type": "stats",
                "message": "Самые частые команды:",
                "top_commands": [{"command": cmd, "count": cnt} for cmd, cnt in top]
            })

        # Частые ошибки
        if self.error_log:
            error_cmds = Counter(e["command"].split()[0] for e in self.error_log)
            problem_cmds = [(cmd, cnt) for cmd, cnt in error_cmds.items() if cnt >= 2]
            if problem_cmds:
                suggestions.append({
                    "type": "errors",
                    "message": "Команды с частыми ошибками:",
                    "problems": problem_cmds
                })

        return suggestions

    def auto_create_skill(self, sequence_key: str):
        """Автоматически создать навык из найденной последовательности"""
        for seq in self.sequences:
            if seq["key"] == sequence_key:
                # Превращаем последовательность в навык
                steps = []
                for cmd in seq["commands"]:
                    parts = cmd.split()
                    if "." in parts[0]:
                        module, command = parts[0].split(".", 1)
                        args = {}
                        for p in parts[1:]:
                            if "=" in p:
                                k, v = p.split("=", 1)
                                args[k] = v
                        steps.append({"module": module, "command": command, "args": args})

                if steps:
                    skill_name = f"auto_{len(self.brain.skills) + 1}"
                    self.brain.learn_skill(
                        skill_name,
                        steps,
                        f"Автонавык из последовательности: {sequence_key}"
                    )
                    self.auto_skills_offered.add(sequence_key)
                    return f"Навык '{skill_name}' создан автоматически"

        return "Последовательность не найдена"

    def get_report(self):
        """Полный отчёт об обучении"""
        total_commands = sum(self.command_counts.values())
        return {
            "total_commands_observed": total_commands,
            "unique_commands": len(self.command_counts),
            "sequences_found": len([s for s in self.sequences if s["count"] >= 2]),
            "errors_logged": len(self.error_log),
            "skills_auto_created": len([s for s in self.brain.skills if s.startswith("auto_")]) if self.brain.skills else 0,
            "top_commands": dict(self.command_counts.most_common(10)),
            "suggestions": self.get_suggestions()
        }
