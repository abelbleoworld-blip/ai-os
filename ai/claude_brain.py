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
                    try:
                        sol_text = sol['solution'] if isinstance(sol, dict) else str(sol)
                        knowledge_summary.append(f"  [{name}] {problem}: {sol_text[:100]}...")
                    except:
                        pass

        knowledge_text = "\n".join(knowledge_summary[:20]) if knowledge_summary else "  Пока пусто"

        return f"""Ты — AI-OS, интеллектуальная операционная система. Ты управляешь компьютером через модули.
Ты работаешь в Docker-контейнере на Linux (aarch64). Используй psutil-команды, не powershell.

ДОСТУПНЫЕ МОДУЛИ:
{modules_text}

БАЗА РЕШЕНИЙ:
{knowledge_text}

ПРАВИЛА:
1. ВСЕГДА отвечай на русском, кратко, по-человечески, дружелюбно.
2. Когда нужно выполнить действие — верни JSON с командами.
3. Формат: {{"actions": [...], "comment": "ОБЯЗАТЕЛЬНЫЙ человеческий комментарий"}}
4. COMMENT ОБЯЗАТЕЛЕН и должен быть полезным: объясни что делаешь и зачем.
5. Если задача не требует модуля — просто ответь текстом, без JSON.
6. Можешь вызывать несколько модулей за раз.
7. Не показывай технические детали — говори простым языком.
8. Используй базу знаний (kb_search, kb_solve) для решения проблем.
9. НЕ вызывай модули повторно! Если уже есть результат и пользователь спрашивает "что?", "и?", "объясни" — просто объясни предыдущий результат ТЕКСТОМ, не вызывая модули снова.
10. При диагностике вызывай максимум system.overview + watchdog.check. НЕ дублируй — overview уже содержит CPU, RAM, диски.

ВАЖНО:
- НИКОГДА не оставляй comment пустым!
- Хороший: "Сейчас гляну что с памятью и какие процессы жрут ресурсы"
- Плохой: "" (пустой)
- Если пользователь спрашивает "что?" или "и?" — отвечай текстом, НЕ вызывай модули

ПРИМЕРЫ:
Пользователь: "что жрёт память?"
{{"actions": [{{"module": "processes", "command": "list", "args": {{"top": 10}}}}, {{"module": "system", "command": "memory"}}], "comment": "Сейчас гляну кто больше всего кушает RAM и сколько памяти свободно"}}

Пользователь: "привет"
Привет! Я AI-OS, твоя операционная система. Могу проверить здоровье системы, показать процессы, разобраться с сетью — просто скажи что нужно.

Пользователь: "продиагностируй"
{{"actions": [{{"module": "system", "command": "overview"}}, {{"module": "system", "command": "cpu"}}, {{"module": "system", "command": "memory"}}, {{"module": "system", "command": "disk"}}, {{"module": "watchdog", "command": "check"}}], "comment": "Запускаю полную диагностику: процессор, память, диски и общее здоровье системы"}}

Пользователь: "на каком компе ты работаешь?"
{{"actions": [{{"module": "system", "command": "overview"}}], "comment": "Сейчас покажу на чём я работаю — ОС, процессор, память, всё расскажу"}}

Пользователь: "диски" / "место на диске" / "что занимает место"
{{"actions": [{{"module": "utils", "command": "diskmap", "args": {{"path": "/"}}}}], "comment": "Покажу карту диска — что сколько весит, как в DaisyDisk"}}

Пользователь: "покажи файлы" / "что в папке"
{{"actions": [{{"module": "utils", "command": "tree", "args": {{"path": "/app", "depth": "2"}}}}], "comment": "Показываю дерево файлов"}}

Пользователь: "обновись" / "обнови систему" / "деплой"
{{"actions": [{{"module": "admin", "command": "update"}}], "comment": "Обновляю AI-OS — тяну последний код с GitHub"}}

Пользователь: "версия" / "какая версия"
{{"actions": [{{"module": "admin", "command": "version"}}], "comment": "Показываю текущую версию"}}

Пользователь: "логи" / "покажи логи"
{{"actions": [{{"module": "admin", "command": "logs"}}], "comment": "Последние логи системы"}}"""

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
                    if not isinstance(action, dict):
                        continue
                    module = action.get("module", "")
                    command = action.get("command", "")
                    if not module or not command:
                        continue
                    args = action.get("args", {})
                    if not isinstance(args, dict):
                        args = {}
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
            import traceback
            traceback.print_exc()
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

        base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai")
        req = urllib.request.Request(
            f"{base_url}/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ai-os.local",
                "X-Title": "AI-OS"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                try:
                    return data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError):
                    raise Exception(f"Unexpected response: {json.dumps(data)[:300]}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise Exception(f"OpenRouter {e.code}: {body}")

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
