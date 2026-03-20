# AI-OS — Инструкция для Huawei

## Твоя роль

Ты отвечаешь за **VPS-сервер**, на котором живёт AI-OS — интеллектуальная операционная система.
AI-OS — это чат-бот + системный администратор в одном: управляет сервером, мониторит здоровье,
отвечает на естественном языке, учится на паттернах использования.

---

## Инфраструктура

### Архитектура
```
[MacBook Alex] → git push → [GitHub] → git clone → [Timeweb VPS] → Docker → AI-OS
                                                         ↑
                                                    ты здесь (Huawei)
```

### Компоненты
| Что              | Где                                              |
|-------------------|--------------------------------------------------|
| Исходный код      | https://github.com/abelbleoworld-blip/ai-os.git |
| VPS (твой)        | 147.45.245.32 (Timeweb)                          |
| AI-мозг           | OpenRouter API → Claude 3.5 Haiku                |
| Контейнер         | Docker + docker-compose                          |
| Веб-интерфейс     | http://147.45.245.32 (после деплоя)              |

### Стек
- **Backend**: Python 3.12, FastAPI, Uvicorn
- **AI**: Anthropic Claude через OpenRouter
- **Deploy**: Docker, nginx reverse proxy
- **OS на VPS**: Ubuntu (Timeweb)

---

## Деплой (первый раз)

### 1. Зайди на сервер
```bash
ssh root@147.45.245.32
```

### 2. Установи Docker и nginx
```bash
apt update && apt upgrade -y
apt install -y docker.io docker-compose-v2 nginx git
systemctl enable docker && systemctl start docker
```

### 3. Клонируй проект
```bash
cd /opt
git clone https://github.com/abelbleoworld-blip/ai-os.git
cd ai-os
```

### 4. Создай .env с API ключом
```bash
nano .env
```
Вставь:
```
OPENROUTER_API_KEY=sk-or-v1-СЮДА_КЛЮЧ
```
(Ключ спроси у Alex)

### 5. Запусти
```bash
docker compose up --build -d
```

### 6. Настрой nginx (чтобы работало на порту 80)
```bash
cat > /etc/nginx/sites-available/ai-os << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
EOF

ln -sf /etc/nginx/sites-available/ai-os /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

### 7. Проверь
Открой в браузере: **http://147.45.245.32**

Должен быть тёмный чат-интерфейс AI-OS с приветствием.

---

## Обновление (когда Alex запушит новый код)

```bash
ssh root@147.45.245.32
cd /opt/ai-os
git pull
docker compose up --build -d
```
Всё. 4 команды.

---

## Полезные команды

```bash
# Статус контейнера
docker compose ps

# Логи (live)
docker compose logs -f

# Перезапуск
docker compose restart

# Полный ребилд
docker compose down && docker compose up --build -d

# Проверить что nginx работает
systemctl status nginx

# Проверить что AI-OS отвечает
curl http://localhost:8080/api/health
```

---

## Структура проекта

```
ai-os/
├── main.py              — точка входа
├── docker-compose.yml   — Docker конфиг
├── Dockerfile           — сборка образа
├── .env                 — API ключи (НЕ в git!)
├── interface/
│   └── web.py           — веб-интерфейс (фронт + API)
├── ai/
│   ├── claude_brain.py  — мозг (Claude API)
│   ├── brain.py         — базовый мозг (fallback)
│   ├── trainer.py       — автообучение
│   └── knowledge.py     — база знаний
├── modules/
│   ├── system_info.py   — CPU, RAM, диски
│   ├── processes.py     — процессы
│   ├── network.py       — сеть
│   ├── watchdog.py      — мониторинг здоровья
│   ├── files.py         — файловая система
│   ├── scanner.py       — безопасность
│   ├── scheduler.py     — планировщик задач
│   ├── designer.py      — генерация UI/палитр
│   ├── platform.py      — кроссплатформенность
│   └── software.py      — управление софтом
├── knowledge/           — базы знаний модулей
├── memory/              — навыки, паттерны, история
└── config/
    └── api.json         — конфиг моделей
```

---

## Если что-то сломалось

| Проблема | Решение |
|----------|---------|
| Сайт не открывается | `docker compose ps` — контейнер запущен? `systemctl status nginx` — nginx живой? |
| "Claude ошибка" в чате | Проверь .env — правильный ли API ключ. `docker compose logs` — детали ошибки |
| Порт 8080 занят | `docker compose down && docker compose up -d` |
| Нужно обновить | `cd /opt/ai-os && git pull && docker compose up --build -d` |
| Диск заполнен | `docker system prune -f` — очистить старые образы |

---

## Контакты

- **Alex** — разработчик, пишет код и пушит на GitHub
- **Huawei (ты)** — DevOps, управляешь VPS и деплоем
- **AI-OS** — сама система, работает на VPS

При вопросах — пиши Alex или спрашивай AI-OS прямо в чате (он знает свою архитектуру).
