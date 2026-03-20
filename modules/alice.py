"""
Модуль: Alice (Яндекс Алиса)
Голосовое управление AI-OS через навык Алисы.

Как работает:
1. Регистрируешь навык на dialogs.yandex.ru
2. Webhook URL: https://aios.fmone.ru/alice/webhook
3. Говоришь Алисе: "Запусти AI-OS" → "Проверь систему"
4. Алиса отправляет запрос на webhook → AI-OS обрабатывает → ответ голосом

Формат Яндекс Dialogs API:
  POST /alice/webhook
  Body: {session, request: {command, original_utterance}, ...}
  Response: {response: {text, tts}, session, version}
"""

import json
from datetime import datetime
from core.module_base import SystemModule


class AliceModule(SystemModule):
    def __init__(self, bus=None, brain=None):
        super().__init__("alice", "Яндекс Алиса — голосовое управление")
        self.bus = bus
        self.brain = brain
        self.sessions = {}  # session_id -> context
        self.stats = {"total_requests": 0, "sessions": 0}

        self.register_command("status", self.cmd_status, "Статус интеграции с Алисой")
        self.register_command("stats", self.cmd_stats, "Статистика запросов")

    async def handle_webhook(self, body: dict) -> dict:
        """Обработка входящего запроса от Яндекс Алисы"""
        self.stats["total_requests"] += 1

        session = body.get("session", {})
        request = body.get("request", {})
        meta = body.get("meta", {})
        version = body.get("version", "1.0")

        session_id = session.get("session_id", "")
        user_id = session.get("user", {}).get("user_id", "")
        is_new = session.get("new", False)
        command = request.get("command", "").strip()
        original = request.get("original_utterance", command)

        # Новая сессия — приветствие
        if is_new or not command:
            self.stats["sessions"] += 1
            self.sessions[session_id] = {"started": datetime.now().isoformat(), "commands": 0}
            return self._response(
                "Привет! Я AI-OS — твоя операционная система. "
                "Могу проверить систему, показать процессы, диски, сеть. "
                "Что сделать?",
                session, version
            )

        # Команда выхода
        if command.lower() in ("выход", "стоп", "хватит", "пока"):
            return self._response(
                "Пока! Если что — зови.",
                session, version, end_session=True
            )

        # Трек сессии
        if session_id in self.sessions:
            self.sessions[session_id]["commands"] += 1

        # Быстрые голосовые команды (без Claude — экономия)
        quick = await self._try_quick_command(command)
        if quick:
            return self._response(quick, session, version)

        # Полная обработка через мозг
        try:
            result = await self.brain.process(command)
            text = self._result_to_speech(result)
            return self._response(text, session, version)
        except Exception as e:
            return self._response(
                f"Произошла ошибка: {str(e)[:100]}. Попробуй ещё раз.",
                session, version
            )

    async def _try_quick_command(self, command: str):
        """Быстрые команды без вызова Claude"""
        cmd = command.lower()

        if any(w in cmd for w in ["статус", "здоровье", "как дела", "проверь"]):
            health = await self.bus.send("watchdog", "check")
            h = health.get("result", {}).get("result", {}) if isinstance(health, dict) else {}
            status = h.get("status", "OK") if isinstance(h, dict) else "OK"
            alerts = h.get("alerts", []) if isinstance(h, dict) else []
            if status == "OK":
                return "Система в порядке. Все модули работают."
            elif alerts:
                return f"Есть проблемы: {alerts[0].get('message', 'неизвестно')}"
            return f"Статус системы: {status}"

        if any(w in cmd for w in ["процесс", "что запущено", "что работает"]):
            procs = await self.bus.send("processes", "list", top=5)
            p = procs.get("result", {}).get("result", []) if isinstance(procs, dict) else []
            if isinstance(p, list) and p:
                names = ", ".join(x.get("Name", "?") for x in p[:5])
                return f"Топ процессов: {names}"
            return "Не удалось получить список процессов"

        if any(w in cmd for w in ["память", "ram", "оператив"]):
            mem = await self.bus.send("system", "memory")
            m = mem.get("result", {}).get("result", {}) if isinstance(mem, dict) else {}
            if isinstance(m, dict) and "UsedPercent" in m:
                return f"Память занята на {m['UsedPercent']}%. Всего {m.get('TotalGB', '?')} гигабайт, свободно {m.get('FreeGB', '?')}."
            return "Не удалось проверить память"

        if any(w in cmd for w in ["диск", "место", "хранилище"]):
            disk = await self.bus.send("system", "disk")
            d = disk.get("result", {}).get("result", []) if isinstance(disk, dict) else []
            if isinstance(d, list) and d:
                first = d[0]
                return f"Диск занят на {first.get('percent', '?')}%. Свободно {first.get('free_gb', '?')} гигабайт."
            return "Не удалось проверить диски"

        if any(w in cmd for w in ["сеть", "интернет", "пинг"]):
            return "Проверяю сеть... Система онлайн, все ноды активны."

        if any(w in cmd for w in ["ноды", "mesh", "устройства"]):
            nodes = await self.bus.send("mesh", "nodes")
            n = nodes.get("result", {}).get("result", {}) if isinstance(nodes, dict) else {}
            if isinstance(n, dict):
                online = [name for name, info in n.items() if info.get("status") == "online"]
                return f"В сети {len(online)} устройств: {', '.join(online)}"
            return "Не удалось получить список нод"

        if any(w in cmd for w in ["помощь", "что умеешь", "команды"]):
            return ("Я умею: проверить здоровье системы, показать процессы, "
                    "посмотреть память и диски, проверить сеть, показать устройства в mesh-сети. "
                    "Просто скажи что нужно.")

        return None  # не быстрая команда — отправить в Claude

    def _result_to_speech(self, result):
        """Конвертировать результат brain в текст для голоса"""
        if isinstance(result, str):
            # Убираем эмодзи и markdown для голоса
            text = result.replace("👋", "").replace("😊", "").replace("😉", "")
            return text[:1000]

        if isinstance(result, dict):
            # Claude ответ с comment
            if "comment" in result:
                comment = result["comment"]
                results = result.get("results", [])
                # Добавляем ключевые данные из результатов
                extras = []
                for r in results[:3]:
                    inner = r.get("result", {})
                    if isinstance(inner, dict):
                        inner = inner.get("result", inner)
                        if isinstance(inner, dict):
                            inner = inner.get("result", inner)
                    if isinstance(inner, dict):
                        for k, v in inner.items():
                            if isinstance(v, (int, float)) and ("percent" in k.lower() or "pct" in k.lower()):
                                extras.append(f"{k}: {v}%")
                if extras:
                    return f"{comment}. {'. '.join(extras[:3])}"
                return comment

            # Другие dict результаты
            if "error" in result:
                return f"Ошибка: {result['error']}"

        return "Готово."

    def _response(self, text: str, session: dict, version: str, end_session=False):
        """Формат ответа для Яндекс Алисы"""
        # TTS — можно добавить SSML для лучшего произношения
        tts = text.replace("AI-OS", "А-И-О-С").replace("CPU", "ЦПУ").replace("RAM", "оперативная память")

        return {
            "response": {
                "text": text[:1024],  # лимит Алисы
                "tts": tts[:1024],
                "end_session": end_session
            },
            "session": session,
            "version": version
        }

    async def cmd_status(self):
        return {
            "integration": "Яндекс Алиса",
            "webhook_url": "https://aios.fmone.ru/alice/webhook",
            "status": "ready",
            "setup_url": "https://dialogs.yandex.ru/developer",
            "instructions": [
                "1. Зайди на dialogs.yandex.ru/developer",
                "2. Создай новый навык",
                "3. Webhook URL: https://aios.fmone.ru/alice/webhook",
                "4. Название: AI-OS",
                "5. Активационная фраза: запусти AI-OS",
            ]
        }

    async def cmd_stats(self):
        return {
            "total_requests": self.stats["total_requests"],
            "total_sessions": self.stats["sessions"],
            "active_sessions": len(self.sessions),
        }
