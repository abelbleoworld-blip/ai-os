# AI-OS — Design Specification

> Техническое задание на дизайн интерфейса.
> Целевая платформа: Web (desktop + mobile). Тёмная тема. Glassmorphism.

---

## 1. Общая концепция

**AI-OS** — операционная система с AI-ядром. Пользователь управляет компьютером через чат на естественном языке. Система состоит из 15 модулей, объединённых шиной сообщений и AI-мозгом (Claude).

**Ключевая метафора:** один экран, один чат, всё через диалог. Панели мониторинга и утилит — вспомогательные, чат — главный.

**Целевая аудитория:** разработчики и администраторы, управляющие сервером/ПК без терминала.

---

## 2. Архитектура интерфейса

### 2.1 Слои

```
┌─────────────────────────────────────────────────┐
│                  Web Interface                   │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ Status   │  │   Chat       │  │  Panels   │  │
│  │ Bar      │  │   (primary)  │  │  (cards)  │  │
│  └──────────┘  └──────────────┘  └───────────┘  │
├─────────────────────────────────────────────────┤
│              FastAPI + WebSocket                  │
├─────────────────────────────────────────────────┤
│  ┌─────┐ ┌─────────┐ ┌───────┐ ┌────────────┐  │
│  │Brain│ │Trainer   │ │Learner│ │Knowledge   │  │
│  │     │ │(auto)    │ │       │ │Base        │  │
│  └──┬──┘ └────┬────┘ └───┬───┘ └─────┬──────┘  │
│     └─────────┴──────────┴────────────┘          │
│                  System Bus                      │
│  ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐    │
│  │file││proc││sys ││net ││scan││soft││mesh│... │
│  └────┘└────┘└────┘└────┘└────┘└────┘└────┘    │
└─────────────────────────────────────────────────┘
```

### 2.2 Связь компонентов

| Компонент | Источник данных | Обновление |
|-----------|----------------|------------|
| Status Bar | `GET /api/health` | polling 10s |
| Chat | `WS /ws` | real-time |
| System Cards | `GET /api/system/*` | polling 5s |
| Process List | `GET /api/processes` | polling 5s |
| Disk Chart | `GET /api/disks` | polling 30s |
| Network | `GET /api/network/connections` | polling 10s |
| Module Grid | `GET /api/status` | on load |
| Utils Panel | `POST /api/command` | on action |
| File Upload | `POST /api/upload` | on drop |
| Mesh Nodes | `GET /mesh/nodes` | polling 15s |
| Skills List | `GET /api/skills` | on load |
| Knowledge | `GET /api/knowledge` | on load |

---

## 3. Layout — Каркас экранов

### 3.1 Desktop (≥1024px)

```
┌──────────────────────────────────────────────────────┐
│ [●] AI-OS        [status pill]     [cpu] [ram] [disk]│  ← Status Bar (48px)
├──────────────────────────────────────────────────────┤
│                                          │           │
│                                          │  System   │
│                                          │  Cards    │
│              CHAT AREA                   │  ───────  │
│              (messages scroll)            │  CPU %    │
│                                          │  RAM %    │
│                                          │  Disk %   │
│                                          │  Net      │
│                                          │  Procs    │
│                                          │           │
├──────────────────────────────────────────┤  Modules  │
│ [🎙] [  type message...          ] [▶]  │  Grid     │
│      [drag file here]                    │           │
└──────────────────────────────────────────┴───────────┘
         70% width                          30% width
```

**Поведение:**
- Правая панель сворачивается кнопкой → чат занимает 100%
- Cards внутри панели — scrollable, каждая карточка независимая
- Module Grid — сетка иконок 4×4, клик → команда в чат

### 3.2 Mobile (< 768px)

```
┌────────────────────────┐
│ [●] AI-OS    [≡] [●●●]│  ← Header (compact)
├────────────────────────┤
│                        │
│     CHAT AREA          │
│     (full width)       │
│                        │
│                        │
├────────────────────────┤
│ [🎙] [ message ] [▶]  │  ← Fixed bottom
└────────────────────────┘

[≡] → slide-out drawer:
  - System Cards (stacked)
  - Module Grid (2 columns)
  - Utils
```

### 3.3 Tablet (768–1023px)

Как desktop, но правая панель — overlay (slide-in), а не постоянная колонка.

---

## 4. Компоненты

### 4.1 Status Bar

```
┌──────────────────────────────────────────────────┐
│ [●] AI-OS v1.0    [OK ●]    CPU 23%  RAM 54%  ▼ │
└──────────────────────────────────────────────────┘
```

- Индикатор здоровья: зелёный (OK), жёлтый (warning), красный (critical)
- Mini-метрики: CPU, RAM — текстом + цвет
- При клике на метрику → раскрывается карточка с деталями
- На мобильном: только индикатор [●] + hamburger

### 4.2 Chat Area

**Сообщения пользователя:**
```
┌─────────────────────────────────┐
│                    ┌───────────┐│
│                    │ покажи    ││
│                    │ процессы  ││
│                    └───────────┘│
│                        12:34   │
└─────────────────────────────────┘
```

**Ответы AI-OS:**
```
┌─────────────────────────────────┐
│ ┌─────────────────────────┐     │
│ │ 🤖 AI-OS                │     │
│ │                         │     │
│ │ Вот топ-5 процессов:   │     │
│ │ ┌─────────────────────┐ │     │
│ │ │ PID  NAME     CPU%  │ │     │
│ │ │ 123  chrome   34.2  │ │     │
│ │ │ 456  node     12.1  │ │     │
│ │ │ ...                 │ │     │
│ │ └─────────────────────┘ │     │
│ │                         │     │
│ │ Хочешь убить процесс?  │     │
│ └─────────────────────────┘     │
│    12:34                         │
└─────────────────────────────────┘
```

**Типы контента в ответах (Smart Cards):**
- Текст — обычный markdown
- Таблицы — процессы, файлы, пакеты → форматированная таблица
- Графики — CPU, RAM, disk → gauge / progress bar inline
- Палитра — дизайнер → цветные блоки
- Код — команды → monospace блок с кнопкой копирования
- Ошибка — красная рамка + suggestion

**Поведение чата:**
- Scroll snap to bottom при новом сообщении
- Typing indicator (три точки) пока AI думает
- Клик на предложение в ответе → вставка в поле ввода
- History: загружается из `brain.history` при открытии

### 4.3 Input Bar

```
┌─────────────────────────────────────────────┐
│ [🎙] [  Напиши команду...           ] [▶]  │
│ ─── quick commands ───                       │
│ [статус] [процессы] [диск] [сеть] [help]    │
└─────────────────────────────────────────────┘
```

- **Textarea** с auto-resize (1–4 строки)
- **Enter** = отправить, **Shift+Enter** = новая строка
- **Микрофон** [🎙]: Web Speech API, язык `ru-RU`. При записи — пульсация кнопки. Interim-результат отображается в поле ввода в реальном времени
- **Quick commands** — горизонтальный scroll, chips. Контекстные: меняются в зависимости от последнего ответа
- **Drag & drop** файлов → upload + анализ

### 4.4 System Cards (правая панель)

Каждая карточка — glassmorphic контейнер.

**CPU Card:**
```
┌─────────────────────┐
│ CPU         23% ◉   │  ← gauge circle
│ ██████░░░░░░░░░     │  ← per-core bars
│ Core 0: 45%         │
│ Core 1: 12%         │
│ ...                 │
└─────────────────────┘
```

**Memory Card:**
```
┌─────────────────────┐
│ RAM       54.4%     │
│ ████████████░░░░░░  │
│ 17.8 GB / 32 GB    │
│ Free: 14.9 GB      │
└─────────────────────┘
```

**Disk Card:**
```
┌─────────────────────┐
│ Disk                │
│   /     ██░░  14%   │
│   /Data ████  66%   │
│ Free: 72.9 GB      │
└─────────────────────┘
```

**Process Card:**
```
┌─────────────────────┐
│ Top Processes    [↻]│
│ chrome      34.2%   │
│ node        12.1%   │
│ python       8.4%   │
│ [kill]  [details]   │
└─────────────────────┘
```

**Network Card:**
```
┌─────────────────────┐
│ Network             │
│ IP: 192.168.1.x     │
│ Connections: 42     │
│ [ping] [interfaces] │
└─────────────────────┘
```

### 4.5 Module Grid

Сетка доступных модулей. Клик → быстрая команда в чат.

```
┌─────────────────────────┐
│  📁 Files    ⚙ System   │
│  📊 Procs    🌐 Network  │
│  🎨 Design   💻 Platform │
│  📦 Software 🔍 Scanner  │
│  📅 Schedule 🌐 Mesh     │
│  🧠 Learner  📚 Ingest   │
│  🔧 Utils    🐕 Watchdog │
└─────────────────────────┘
```

При hover — tooltip с описанием модуля и числом команд.
При клике — раскрывается список команд модуля (dropdown).

### 4.6 Utils Panel

Панель утилит — группированные кнопки быстрых действий.

**Группы:**
| Группа | Утилиты |
|--------|---------|
| Files | ls, tree, find, preview, size, recent |
| Terminal | exec, which, env, grep |
| Text | wc, head, tail, diff |
| Encode | b64encode, b64decode, hash |
| System | ip, ports, df, top, uptime |
| Data | json2yaml |
| Notes | note, notes, note_get, note_del |

Каждая кнопка → вставляет команду в чат с плейсхолдерами аргументов.

### 4.7 Mesh Panel (если mesh активен)

```
┌───────────────────────────┐
│ Mesh Network        [hub] │
│                           │
│ ● imac (this)    — hub    │
│ ● vps-huawei     — agent  │
│ ○ macbook        — offline│
│                           │
│ [send command to node...] │
└───────────────────────────┘
```

---

## 5. Визуальный стиль

### 5.1 Тема

| Токен | Значение | Назначение |
|-------|----------|------------|
| `--bg-primary` | `#0a0a0f` | Фон приложения |
| `--bg-card` | `rgba(255,255,255,0.04)` | Фон карточек |
| `--bg-card-hover` | `rgba(255,255,255,0.08)` | Hover карточек |
| `--glass-border` | `rgba(255,255,255,0.08)` | Граница стекла |
| `--glass-blur` | `20px` | Размытие backdrop |
| `--text-primary` | `#e8e8ed` | Основной текст |
| `--text-secondary` | `#8888aa` | Вторичный текст |
| `--text-dim` | `#555570` | Приглушённый текст |
| `--accent` | `#6c5ce7` | Акцент (кнопки, ссылки) |
| `--ok` | `#00e676` | Статус OK |
| `--warn` | `#ffa726` | Предупреждение |
| `--critical` | `#ef5350` | Критично / ошибка |
| `--info` | `#42a5f5` | Информация |

### 5.2 Glassmorphism

Все карточки и панели:
```css
background: var(--bg-card);
backdrop-filter: blur(var(--glass-blur));
-webkit-backdrop-filter: blur(var(--glass-blur));
border: 1px solid var(--glass-border);
border-radius: 16px;
```

### 5.3 Типографика

| Элемент | Font | Size | Weight |
|---------|------|------|--------|
| Body | `Inter, system-ui, sans-serif` | 14px | 400 |
| Heading | `Inter` | 18px | 600 |
| Code/mono | `JetBrains Mono, monospace` | 13px | 400 |
| Status pill | `Inter` | 12px | 500 |
| Chat message | `Inter` | 15px | 400 |
| Chat input | `Inter` | 15px | 400 |

### 5.4 Анимации

| Элемент | Анимация | Длительность |
|---------|----------|--------------|
| Новое сообщение | fadeIn + slideUp | 300ms ease |
| Typing indicator | pulse (3 точки) | 1.2s infinite |
| Card appear | fadeIn + scale(0.95→1) | 200ms ease |
| Status change | color transition | 500ms ease |
| Gauge fill | width transition | 800ms ease |
| Mic recording | pulse glow (красный) | 1s infinite |
| Toast | slideIn → delay 3s → fadeOut | 300ms + 300ms |
| Panel slide | translateX | 300ms ease |

---

## 6. Состояния и поведение

### 6.1 Статус системы

Три состояния (определяется `/api/health`):

| Состояние | Цвет | Условие |
|-----------|------|---------|
| OK | `--ok` зелёный | Все модули работают, ресурсы < 80% |
| Warning | `--warn` жёлтый | RAM > 80% или диск > 85% или модуль недоступен |
| Critical | `--critical` красный | RAM > 95% или диск > 95% или brain offline |

### 6.2 AI Brain состояния

| Состояние | Индикация |
|-----------|-----------|
| Claude подключён | Зелёная иконка 🤖 в чате |
| Claude недоступен (API) | Жёлтая иконка, текст "базовый режим" |
| Обработка запроса | Typing indicator + disable input |
| Ошибка | Красное сообщение с suggestion |

### 6.3 Голосовой ввод

```
Idle → [клик mic] → Recording → [клик mic] → Processing → Result in input
                      ↑ пульсация                          ↓ auto-focus
                      ↑ interim text в поле ввода           ↓
```

Технология: `SpeechRecognition` API (Chrome/Edge). Язык: `ru-RU`. `interimResults: true` — показ промежуточного текста.

### 6.4 File Upload

```
Drag file over chat → overlay "Отпусти для загрузки"
Drop → upload animation → POST /api/upload
→ AI-ответ с анализом файла
```

---

## 7. API Endpoints (полная карта)

### Чтение

```
GET  /                          → HTML интерфейс
GET  /api/status                → {modules, brain, trainer}
GET  /api/health                → {status, checks, alerts}
GET  /api/report                → {trainer report}
GET  /api/stats                 → {global stats}
GET  /api/models                → {available AI models}
GET  /api/skills                → {learned skills}
GET  /api/knowledge             → {knowledge base stats}
GET  /api/system/overview       → {cpu, ram, disk snapshot}
GET  /api/system/memory         → {memory details}
GET  /api/system/cpu            → {per-core CPU}
GET  /api/system/uptime         → {uptime}
GET  /api/processes             → {top processes}
GET  /api/disks                 → {disk usage}
GET  /api/network/connections   → {active connections}
GET  /mesh/nodes                → {mesh node list}
GET  /mesh/status               → {mesh status}
```

### Запись

```
POST /api/command               → {command: "text"} → AI response
POST /api/upload                → multipart file → analysis
POST /api/knowledge/seed        → seed knowledge bases
POST /mesh/register             → register mesh node
POST /mesh/heartbeat            → node heartbeat
POST /mesh/command              → send command to node
POST /mesh/execute              → execute from hub
```

### WebSocket

```
WS   /ws                        → JSON {input: "text"} ↔ {response: "text"}
```

---

## 8. Модульная архитектура (для дизайна)

15 модулей. Каждый имеет имя, иконку, набор команд.

| # | Модуль | Иконка | Команд | Назначение |
|---|--------|--------|--------|------------|
| 1 | files | 📁 | 8 | Файловые операции |
| 2 | processes | ⚙ | 4 | Управление процессами |
| 3 | system | 📊 | 6 | Информация о системе |
| 4 | network | 🌐 | 6 | Сеть и подключения |
| 5 | watchdog | 🐕 | 6 | Мониторинг здоровья |
| 6 | designer | 🎨 | 8 | Генерация палитр и макетов |
| 7 | platform | 💻 | 5 | Определение платформы |
| 8 | versions | 📌 | 5 | Версионирование |
| 9 | scanner | 🔍 | 9 | Анализ диска |
| 10 | scheduler | 📅 | 8 | Планировщик задач |
| 11 | software | 📦 | 8 | Пакетный менеджер |
| 12 | mesh | 🌐 | 5 | Mesh-сеть устройств |
| 13 | learner | 🧠 | 9 | Самообучение |
| 14 | ingest | 📚 | 5 | Загрузка знаний |
| 15 | utils | 🔧 | 27 | Утилиты терминала |

---

## 9. Технические требования

- **Single Page Application** — без перезагрузок
- **Vanilla JS** — без фреймворков (проект не использует React/Vue)
- **WebSocket** для чата (fallback на POST /api/command)
- **Web Speech API** для голосового ввода
- **CSS custom properties** для темизации
- **Responsive:** 320px → 2560px
- **Поддержка:** Chrome 90+, Safari 15+, Firefox 90+, Edge 90+
- **Шрифты:** Inter (Google Fonts), JetBrains Mono (Google Fonts)

---

## 10. Файловая структура интерфейса

```
interface/
├── static/
│   └── index.html       ← единый файл: HTML + CSS + JS
└── web.py               ← FastAPI backend + fallback HTML
```

Весь фронтенд — **один HTML-файл** с inline CSS и JS. Это сделано намеренно для простоты деплоя (Docker, copy, embed).
