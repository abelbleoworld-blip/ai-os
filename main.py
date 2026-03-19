"""
AI-OS — Точка входа.

Здесь всё собирается:
1. Создаём шину (почтовую систему)
2. Создаём модули (городские службы)
3. Регистрируем модули на шине
4. Запускаем всё
5. Подключаем мозг (ИИ) + автотренер
6. Watchdog следит за здоровьем
7. Открываем интерфейс (консоль или веб)

Всё в связке: модули <-> шина <-> мозг <-> тренер <-> watchdog

Запуск:
  python main.py          — консольный режим
  python main.py --web    — веб-сервер (для Docker)
"""

import asyncio
import logging
import sys
import os

# Фикс кодировки для Windows-консоли
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.system("chcp 65001 >nul 2>&1")

# Добавить корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.bus import SystemBus
from modules.files import FilesModule
from modules.processes import ProcessesModule
from modules.system_info import SystemInfoModule
from modules.network import NetworkModule
from modules.watchdog import WatchdogModule
from modules.designer import DesignerModule
from modules.platform import PlatformModule
from modules.versions import VersionsModule
from modules.scanner import ScannerModule
from modules.scheduler import SchedulerModule
from modules.software import SoftwareModule
from ai.brain import Brain
from ai.claude_brain import ClaudeBrain
from ai.trainer import AutoTrainer


# Настройка логирования
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "aios.log"), encoding="utf-8"),
    ]
)


def _apply_env_config():
    """Применить API-ключи из переменных окружения (для Docker)"""
    import json
    from pathlib import Path

    config_path = Path(__file__).parent / "config" / "api.json"
    example_path = Path(__file__).parent / "config" / "api.example.json"

    # Если api.json нет — создать из примера
    if not config_path.exists() and example_path.exists():
        config = json.loads(example_path.read_text(encoding="utf-8"))
    elif config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {}

    # Переменные окружения перезаписывают файл
    env_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    env_openrouter = os.environ.get("OPENROUTER_API_KEY")
    env_model = os.environ.get("AIOS_MODEL")

    if env_anthropic:
        config["anthropic_api_key"] = env_anthropic
    if env_openrouter:
        config["openrouter_api_key"] = env_openrouter
    if env_model:
        config["default_model"] = env_model

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


async def init_system():
    """Инициализация всех компонентов AI-OS. Возвращает (brain, trainer)."""
    print("Инициализация AI-OS...")
    print()

    # 1. Шина — центральная магистраль
    bus = SystemBus()
    print("[1/7] Шина создана")

    # 2. Модули — независимые блоки
    modules = [
        FilesModule(),
        ProcessesModule(),
        SystemInfoModule(),
        NetworkModule(),
        DesignerModule(),
        PlatformModule(),
        VersionsModule(),
        ScannerModule(),
        SoftwareModule(),
    ]
    print(f"[2/7] Создано {len(modules)} модулей")

    # 3. Регистрируем на шине
    for module in modules:
        bus.register(module)
    print("[3/7] Модули зарегистрированы на шине")

    # 3.5 Планировщик (нужен bus)
    scheduler = SchedulerModule(bus=bus)
    bus.register(scheduler)

    # 4. Запускаем все модули
    await bus.start_all()
    print("[4/7] Модули запущены")

    # 5. Подключаем мозг (базовый + Claude)
    base_brain = Brain(bus)
    trainer = AutoTrainer(base_brain)
    base_brain.trainer = trainer

    try:
        brain = ClaudeBrain(bus, base_brain)
        print("[5/7] ИИ-ядро: Claude подключён (естественный язык)")
    except Exception as e:
        brain = base_brain
        print(f"[5/7] ИИ-ядро: базовый режим (Claude недоступен: {e})")

    # 6. Автотренер
    print("[6/7] Автотренер подключён (наблюдение активно)")

    # 7. Watchdog — следит за здоровьем (знает про шину)
    watchdog = WatchdogModule(bus=bus)
    bus.register(watchdog)
    await watchdog.start()

    # Первая проверка здоровья при старте
    health = await watchdog.cmd_check()
    health_status = health.get("status", "?")
    alerts_count = len(health.get("alerts", []))
    print(f"[7/7] Watchdog запущен (здоровье: {health_status}, предупреждений: {alerts_count})")

    if alerts_count > 0:
        print()
        print("  Предупреждения:")
        for alert in health["alerts"]:
            print(f"    [{alert['level']}] {alert['message']}")

    return brain, trainer


async def run_console(brain, trainer):
    """Консольный режим — как было раньше"""
    from interface.console import Console
    console = Console(brain)
    await console.run()
    trainer.save()
    brain.save_memory()


def run_web():
    """Веб-режим — FastAPI + uvicorn (web.py сам создаёт bus/brain)"""
    import uvicorn
    from interface.web import app

    host = os.environ.get("AIOS_HOST", "0.0.0.0")
    port = int(os.environ.get("AIOS_PORT", "8080"))

    print()
    print(f"  Web UI: http://localhost:{port}")
    print(f"  API:    http://localhost:{port}/api/status")
    print()

    uvicorn.run(app, host=host, port=port, log_level="info")


async def main_console():
    _apply_env_config()
    brain, trainer = await init_system()
    await run_console(brain, trainer)


if __name__ == "__main__":
    _apply_env_config()

    if "--web" in sys.argv:
        run_web()
    else:
        asyncio.run(main_console())
