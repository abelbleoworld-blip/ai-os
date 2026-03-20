# AI-OS

Модульная ИИ-операционная система с Claude. Управляет компьютером через естественный язык.

## Модули

| Модуль | Описание |
|---|---|
| files | Файлы и папки |
| processes | Процессы и программы |
| system | Информация о системе |
| network | Сеть и интернет |
| scanner | Сканирование дисков |
| software | Установка программ (winget) |
| scheduler | Планировщик задач |
| watchdog | Мониторинг здоровья |
| designer | Генерация UI/палитр |
| platform | Кроссплатформенность |
| versions | Версии и бэкапы |

## Запуск через Docker

### Требования

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac / Windows / Linux)
- API-ключ [Anthropic](https://console.anthropic.com/) или [OpenRouter](https://openrouter.ai/)

### 1. Клонировать

```bash
git clone https://github.com/abelbleoworld-blip/ai-os.git
cd ai-os
```

### 2. Создать `.env`

```bash
echo "ANTHROPIC_API_KEY=sk-ant-ваш-ключ" > .env
```

Или для OpenRouter:

```bash
echo "OPENROUTER_API_KEY=sk-or-ваш-ключ" > .env
```

### 3. Запустить

```bash
docker compose up --build -d
```

### 4. Открыть

Браузер: **http://localhost:8080**

## Команды Docker

```bash
docker compose logs -f          # логи в реальном времени
docker compose down             # остановить
docker compose up -d            # запустить
docker compose up --build -d    # пересобрать после изменений
```

## API

```
GET  /api/status     — статус модулей
GET  /api/health     — здоровье системы
GET  /api/processes  — список процессов
GET  /api/disks      — использование дисков
POST /api/command    — отправить команду {"command": "текст"}
POST /api/upload     — загрузить файл
```

## Запуск без Docker (консоль)

```bash
pip install -r requirements.txt
cp config/api.example.json config/api.json
# отредактировать config/api.json — вставить API-ключ
python main.py
```

## Переменные окружения

| Переменная | Описание |
|---|---|
| `ANTHROPIC_API_KEY` | Ключ Anthropic API |
| `OPENROUTER_API_KEY` | Ключ OpenRouter API |
| `AIOS_MODEL` | Модель (по умолчанию `claude-haiku-4-5-20251001`) |
| `AIOS_HOST` | Хост сервера (по умолчанию `0.0.0.0`) |
| `AIOS_PORT` | Порт сервера (по умолчанию `8080`) |
