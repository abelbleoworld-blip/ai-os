"""
Claude Brain — ИИ-мозг на базе Claude API.

Вместо парсинга команд вручную — Claude понимает естественный язык
и сам решает какие модули вызвать.

"Что жрёт память?" → Claude: вызвать processes.list + system.memory
"Проверь сеть" → Claude: network.ping + watchdog.check
"Сделай тёмную тему" → Claude: designer.theme style=dark
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from anthropic import Anthropic


CONFIG_PATH = Path(__file__).parent.parent / "config" / "api.json"


class ClaudeBrain:
    def __init__(self, bus, old_brain):
        self.bus = bus
        self.old_brain = old_brain  # fallback на старый мозг
        self.trainer = old_brain.trainer if old_brain else None
        self.skills = old_brain.skills if old_brain else {}
        self.patterns = old_brain.patterns if old_brain else {}
        self.history = old_brain.history if old_brain else []
        self.conversation = []  # история диалога для контекста

        # Загрузить конфиг
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.provider = config.get("provider", "anthropic")
        self.max_tokens = config.get("max_tokens", 1024)

        # Anthropic напрямую
        self.anthropic_key = config.get("anthropic_api_key", "")
        self.client = None
        if self.anthropic_key:
            self.client = Anthropic(api_key=self.anthropic_key)

        # OpenRouter — доступ ко всем моделям через один API
        self.openrouter_key = config.get("openrouter_api_key", "")
        self.openrouter_models = config.get("openrouter_models", {})

        # Модели
        self.model = config.get("default_model", "claude-haiku-4-5-20251001")
        self.smart_model = config.get("smart_model", "claude-sonnet-4-5-20250514")

    def _build_system_prompt(self):
        """Системный промпт — объясняем Claude кто он и что умеет"""
        modules_info = self.bus.list_modules()
        modules_desc = []
        for name, info in modules_info.items():
            cmds = ", ".join(f"{cmd} ({desc})" for cmd, desc in info["commands"].items()
                           if not cmd.startswith("kb_"))
            kb_cmds = "kb_search, kb_solve, kb_sources"
            modules_desc.append(f"- {name}: {info['description']}\n  Команды: {cmds}\n  Знания: {kb_cmds}")

        modules_text = "\n".join(modules_desc)

        # Собираем знания всех модулей для контекста
        knowledge_summary = []
        for name, module in self.bus.modules.items():
            if hasattr(module, 'kb') and module.kb.solutions:
                for problem, sol in module.kb.solutions.items():
                    knowledge_summary.append(f"  [{name}] {problem}: {sol['solution'][:100]}...")

        knowledge_text = "\n".join(knowledge_summary[:20]) if knowledge_summary else "  Пока пусто"

        return f"""Ты — AI-OS, интеллектуальная операционная система. У тебя ЕСТЬ прямой доступ к компьютеру через модули. Ты НЕ чат-бот — ты операционная система. Когда пользователь просит что-то сделать, ты ДЕЛАЕШЬ это немедленно, без лишних вопросов и без запроса разрешения.

ВАЖНО:
- У тебя ЕСТЬ доступ к файлам, процессам, сети, дискам — через модули ниже.
- НЕ говори "я не могу", "у меня нет доступа", "нужно разрешение" — ты МОЖЕШЬ, просто вызови модуль.
- НЕ спрашивай "хочешь ли ты" — просто делай.
- НЕ описывай что ты МОЖЕШЬ сделать — ДЕЛАЙ.
- Отвечай КРАТКО. Никаких эмодзи, никаких длинных объяснений.

ДОСТУПНЫЕ МОДУЛИ:
{modules_text}

БАЗА РЕШЕНИЙ:
{knowledge_text}

ФОРМАТ ДЕЙСТВИЙ:
Когда нужно выполнить действие — верни ТОЛЬКО JSON:
{{"actions": [{{"module": "имя", "command": "команда", "args": {{...}}}}], "comment": "краткое пояснение"}}

Можешь вызывать несколько модулей за раз. Если задача не требует модуля — ответь текстом (кратко).

ПРИМЕРЫ:
Пользователь: "что жрёт память?"
{{"actions": [{{"module": "processes", "command": "list", "args": {{"top": 10}}}}, {{"module": "system", "command": "memory"}}], "comment": "Топ процессов + состояние RAM"}}

Пользователь: "привет"
Привет. Я AI-OS. Что нужно?

Пользователь: "проверь здоровье"
{{"actions": [{{"module": "watchdog", "command": "check"}}], "comment": "Диагностика"}}

Пользователь: "покажи диски"
{{"actions": [{{"module": "files", "command": "disk_usage"}}], "comment": "Использование дисков"}}"""

    async def process(self, user_input: str):
        """Главная функция — человек говорит, Claude думает, модули делают"""
        from datetime import datetime
        timestamp = datetime.now().isoformat()

        # Прямые команды модулей — пропускаем без Claude (экономия)
        if "." in user_input.split()[0] if user_input.strip() else False:
            result = await self.old_brain.process(user_input)
            return result

        # Короткие системные команды
        short = user_input.strip().lower()
        if short in ("help", "modules", "status", "skills", "history", "save", "report", "suggest"):
            return await self.old_brain.process(user_input)

        # Отправляем в Claude
        try:
            response = await self._ask_claude(user_input)

            # Пробуем распарсить как JSON с действиями
            actions_result = self._try_parse_actions(response)

            if actions_result:
                # Claude хочет вызвать модули
                results = []
                for action in actions_result["actions"]:
                    module = action["module"]
                    command = action["command"]
                    args = action.get("args", {})
                    r = await self.bus.send(module, command, **args)
                    results.append({"module": module, "command": command, "result": r})

                comment = actions_result.get("comment", "")

                # Запоминаем
                self.history.append({
                    "time": timestamp,
                    "input": user_input,
                    "method": "claude",
                    "actions": actions_result["actions"],
                    "results": results
                })

                # Тренер наблюдает
                if self.trainer:
                    self.trainer.observe(user_input, {"actions": results})

                return {
                    "comment": comment,
                    "results": results
                }
            else:
                # Claude ответил текстом — просто возвращаем
                self.history.append({
                    "time": timestamp,
                    "input": user_input,
                    "method": "claude_text",
                    "response": response
                })
                return response

        except Exception as e:
            # Claude недоступен — fallback на старый мозг
            error_msg = str(e)
            if "rate_limit" in error_msg.lower() or "credit" in error_msg.lower():
                return f"API лимит: {error_msg}. Используй прямые команды (модуль.команда)"
            return f"Claude ошибка: {error_msg}. Fallback: используй модуль.команда"

    async def _ask_claude(self, user_input: str):
        """Отправить запрос — через Anthropic или OpenRouter"""
        self.conversation.append({"role": "user", "content": user_input})
        recent = self.conversation[-10:]

        if self.provider == "openrouter" and self.openrouter_key:
            assistant_text = self._call_openrouter(recent)
        elif self.client:
            assistant_text = self._call_anthropic(recent)
        else:
            raise Exception("Нет настроенного провайдера API")

        self.conversation.append({"role": "assistant", "content": assistant_text})
        return assistant_text

    def _call_anthropic(self, messages):
        """Вызов через Anthropic API напрямую"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._build_system_prompt(),
            messages=messages
        )
        return response.content[0].text

    def _call_openrouter(self, messages):
        """
        Вызов через OpenRouter — доступ к любой модели.
        OpenRouter поддерживает OpenAI-совместимый формат.
        """
        model = self.openrouter_models.get("fast", "anthropic/claude-haiku-4-5-20251001")

        # Формируем запрос в формате OpenAI (OpenRouter совместим)
        payload = json.dumps({
            "model": model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": self._build_system_prompt()},
                *messages
            ]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ai-os.local",
                "X-Title": "AI-OS"
            }
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    def _try_parse_actions(self, response: str):
        """Попробовать распарсить ответ Claude как JSON с действиями"""
        text = response.strip()

        # Ищем JSON в ответе
        start = text.find("{")
        end = text.rfind("}") + 1

        if start == -1 or end <= start:
            return None

        try:
            data = json.loads(text[start:end])
            if "actions" in data and isinstance(data["actions"], list):
                return data
        except json.JSONDecodeError:
            pass

        return None

    def save_memory(self):
        """Сохранить память"""
        if self.old_brain:
            self.old_brain.skills = self.skills
            self.old_brain.patterns = self.patterns
            self.old_brain.history = self.history
            self.old_brain.save_memory()
