"""
Веб-интерфейс AI-OS.
Дашборд в браузере — кнопки, панели, статусы.
Запускается на localhost:8080
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from core.bus import SystemBus
from modules.files import FilesModule
from modules.processes import ProcessesModule
from modules.system_info import SystemInfoModule
from modules.network import NetworkModule
from modules.watchdog import WatchdogModule
from modules.designer import DesignerModule
from modules.platform import PlatformModule
from modules.versions import VersionsModule
from ai.brain import Brain
from ai.claude_brain import ClaudeBrain
from ai.trainer import AutoTrainer


# Инициализация системы
bus = SystemBus()
modules = [FilesModule(), ProcessesModule(), SystemInfoModule(), NetworkModule(), DesignerModule(), PlatformModule(), VersionsModule()]
for m in modules:
    bus.register(m)

watchdog = WatchdogModule(bus=bus)
bus.register(watchdog)

base_brain = Brain(bus)
trainer = AutoTrainer(base_brain)
base_brain.trainer = trainer

try:
    brain = ClaudeBrain(bus, base_brain)
except:
    brain = base_brain


@asynccontextmanager
async def lifespan(app):
    # Startup
    await bus.start_all()
    await watchdog.start()
    await watchdog.cmd_check()
    yield
    # Shutdown
    trainer.save()
    brain.save_memory()


app = FastAPI(title="AI-OS", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


@app.get("/api/status")
async def api_status():
    return {
        "modules": bus.list_modules(),
        "brain": {
            "skills": len(brain.skills),
            "patterns": len(brain.patterns),
            "history_count": len(brain.history),
        },
        "trainer": {
            "commands_observed": sum(trainer.command_counts.values()),
            "unique_commands": len(trainer.command_counts),
        }
    }


@app.get("/api/health")
async def api_health():
    return await watchdog.cmd_check()


@app.get("/api/system/overview")
async def api_overview():
    return await bus.send("system", "overview")


@app.get("/api/system/memory")
async def api_memory():
    return await bus.send("system", "memory")


@app.get("/api/system/cpu")
async def api_cpu():
    return await bus.send("system", "cpu")


@app.get("/api/system/uptime")
async def api_uptime():
    return await bus.send("system", "uptime")


@app.get("/api/processes")
async def api_processes():
    return await bus.send("processes", "list", top=15)


@app.get("/api/disks")
async def api_disks():
    return await bus.send("files", "disk_usage")


@app.get("/api/network/connections")
async def api_connections():
    return await bus.send("network", "connections")


@app.get("/api/report")
async def api_report():
    return trainer.get_report()


@app.post("/api/command")
async def api_command(data: dict):
    cmd = data.get("command", "")
    if not cmd:
        return {"error": "empty command"}
    result = await brain.process(cmd)
    return {"input": cmd, "result": result}


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-OS Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0a0e17;
    color: #e0e6f0;
    min-height: 100vh;
}
.header {
    background: linear-gradient(135deg, #1a1f35 0%, #0d1225 100%);
    border-bottom: 1px solid #2a3555;
    padding: 16px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.header h1 {
    font-size: 22px;
    font-weight: 600;
    background: linear-gradient(90deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.header .status-badge {
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
}
.status-ok { background: #065f46; color: #6ee7b7; }
.status-warn { background: #78350f; color: #fcd34d; }
.status-err { background: #7f1d1d; color: #fca5a5; }

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 16px;
    padding: 20px;
    max-width: 1400px;
    margin: 0 auto;
}
.card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 20px;
    transition: border-color 0.2s;
}
.card:hover { border-color: #3b82f6; }
.card h2 {
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #94a3b8;
    margin-bottom: 16px;
}
.card h2 .dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 8px;
}
.dot-green { background: #22c55e; box-shadow: 0 0 8px #22c55e55; }
.dot-yellow { background: #eab308; box-shadow: 0 0 8px #eab30855; }
.dot-red { background: #ef4444; box-shadow: 0 0 8px #ef444455; }
.dot-gray { background: #6b7280; }

.metric {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 8px 0;
    border-bottom: 1px solid #1e293b;
}
.metric:last-child { border-bottom: none; }
.metric .label { color: #94a3b8; font-size: 14px; }
.metric .value { font-size: 18px; font-weight: 600; }
.value-ok { color: #22c55e; }
.value-warn { color: #eab308; }
.value-crit { color: #ef4444; }

.bar-bg {
    width: 100%;
    height: 8px;
    background: #1e293b;
    border-radius: 4px;
    margin-top: 6px;
    overflow: hidden;
}
.bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
}

.module-list { list-style: none; }
.module-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    margin-bottom: 6px;
    background: #0f172a;
    border-radius: 8px;
    border: 1px solid #1e293b;
}
.module-item .name { font-weight: 500; }
.module-item .cmds { color: #64748b; font-size: 13px; }
.module-badge {
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}
.badge-running { background: #065f46; color: #6ee7b7; }
.badge-stopped { background: #7f1d1d; color: #fca5a5; }

.btn-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
}
.btn {
    padding: 8px 16px;
    border: 1px solid #2a3555;
    background: #1e293b;
    color: #e0e6f0;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s;
}
.btn:hover { background: #2a3555; border-color: #3b82f6; }
.btn:active { transform: scale(0.97); }
.btn-primary { background: #1d4ed8; border-color: #3b82f6; }
.btn-primary:hover { background: #2563eb; }
.btn-danger { border-color: #991b1b; }
.btn-danger:hover { background: #991b1b; }

.command-box {
    grid-column: 1 / -1;
}
.cmd-input-row {
    display: flex;
    gap: 10px;
    margin-bottom: 12px;
}
.cmd-input {
    flex: 1;
    padding: 12px 16px;
    background: #0f172a;
    border: 1px solid #2a3555;
    border-radius: 8px;
    color: #e0e6f0;
    font-size: 15px;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    outline: none;
}
.cmd-input:focus { border-color: #3b82f6; }
.cmd-input::placeholder { color: #475569; }
.cmd-output {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 16px;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: 13px;
    max-height: 350px;
    overflow-y: auto;
    white-space: pre-wrap;
    line-height: 1.6;
    color: #a5b4c8;
}
.cmd-output .cmd-line { color: #60a5fa; }
.cmd-output .cmd-result { color: #e0e6f0; }
.cmd-output .cmd-error { color: #fca5a5; }

.alerts-list { list-style: none; }
.alert-item {
    padding: 10px 14px;
    margin-bottom: 6px;
    border-radius: 8px;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.alert-warn { background: #422006; border: 1px solid #78350f; color: #fcd34d; }
.alert-crit { background: #450a0a; border: 1px solid #7f1d1d; color: #fca5a5; }
.alert-ok { background: #052e16; border: 1px solid #065f46; color: #6ee7b7; }

.process-table { width: 100%; font-size: 13px; }
.process-table th {
    text-align: left;
    color: #64748b;
    padding: 6px 8px;
    border-bottom: 1px solid #1e293b;
    font-weight: 500;
}
.process-table td {
    padding: 6px 8px;
    border-bottom: 1px solid #0f172a;
}

.loader {
    display: inline-block;
    width: 16px; height: 16px;
    border: 2px solid #2a3555;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    margin-right: 8px;
}
@keyframes spin { to { transform: rotate(360deg); } }

.quick-actions { margin-top: 16px; }
.footer {
    text-align: center;
    padding: 20px;
    color: #475569;
    font-size: 13px;
}
</style>
</head>
<body>

<div class="header">
    <h1>AI-OS</h1>
    <div id="healthBadge" class="status-badge status-ok">Loading...</div>
</div>

<div class="grid">

    <!-- Система -->
    <div class="card" id="sysCard">
        <h2><span class="dot dot-green"></span> Система</h2>
        <div id="sysInfo">
            <div class="metric"><span class="label">Загрузка...</span></div>
        </div>
        <div class="btn-row">
            <button class="btn" onclick="loadOverview()">Обновить</button>
            <button class="btn" onclick="quickCmd('system.uptime')">Аптайм</button>
            <button class="btn" onclick="quickCmd('system.cpu')">CPU</button>
        </div>
    </div>

    <!-- Память -->
    <div class="card" id="memCard">
        <h2><span class="dot dot-green" id="memDot"></span> Память</h2>
        <div id="memInfo">
            <div class="metric"><span class="label">Загрузка...</span></div>
        </div>
        <div class="btn-row">
            <button class="btn" onclick="loadMemory()">Обновить</button>
        </div>
    </div>

    <!-- Диски -->
    <div class="card" id="diskCard">
        <h2><span class="dot dot-green" id="diskDot"></span> Диски</h2>
        <div id="diskInfo">
            <div class="metric"><span class="label">Загрузка...</span></div>
        </div>
        <div class="btn-row">
            <button class="btn" onclick="loadDisks()">Обновить</button>
        </div>
    </div>

    <!-- Здоровье -->
    <div class="card" id="healthCard">
        <h2><span class="dot dot-green" id="healthDot"></span> Здоровье</h2>
        <div id="healthInfo">
            <div class="metric"><span class="label">Загрузка...</span></div>
        </div>
        <div class="btn-row">
            <button class="btn btn-primary" onclick="loadHealth()">Проверить</button>
            <button class="btn" onclick="quickCmd('watchdog.heal')">Лечить</button>
        </div>
    </div>

    <!-- Модули -->
    <div class="card">
        <h2><span class="dot dot-green"></span> Модули</h2>
        <ul class="module-list" id="moduleList">
            <li class="module-item"><span class="label">Загрузка...</span></li>
        </ul>
    </div>

    <!-- Процессы -->
    <div class="card">
        <h2><span class="dot dot-green"></span> Процессы</h2>
        <div id="procInfo">
            <div class="metric"><span class="label">Загрузка...</span></div>
        </div>
        <div class="btn-row">
            <button class="btn" onclick="loadProcesses()">Обновить</button>
        </div>
    </div>

    <!-- Обучение -->
    <div class="card">
        <h2><span class="dot dot-green"></span> Обучение ИИ</h2>
        <div id="trainInfo">
            <div class="metric"><span class="label">Загрузка...</span></div>
        </div>
        <div class="btn-row">
            <button class="btn" onclick="loadReport()">Отчёт</button>
            <button class="btn" onclick="quickCmd('skills')">Навыки</button>
            <button class="btn" onclick="quickCmd('save')">Сохранить</button>
        </div>
    </div>

    <!-- Быстрые действия -->
    <div class="card">
        <h2><span class="dot dot-green"></span> Быстрые действия</h2>
        <div class="btn-row">
            <button class="btn btn-primary" onclick="quickCmd('status')">Статус</button>
            <button class="btn" onclick="quickCmd('system.network')">Сеть</button>
            <button class="btn" onclick="quickCmd('network.ping host=google.com')">Пинг Google</button>
            <button class="btn" onclick="quickCmd('files.list path=C:/Users/alex')">Мои файлы</button>
            <button class="btn" onclick="quickCmd('processes.list top=10')">Топ процессов</button>
            <button class="btn" onclick="quickCmd('files.disk_usage')">Диски</button>
            <button class="btn" onclick="quickCmd('watchdog.check')">Проверка</button>
            <button class="btn btn-danger" onclick="quickCmd('watchdog.heal')">Лечить</button>
        </div>
    </div>

    <!-- Командная строка -->
    <div class="card command-box">
        <h2><span class="dot dot-green"></span> Командная строка</h2>
        <div class="cmd-input-row">
            <input type="text" class="cmd-input" id="cmdInput"
                   placeholder="модуль.команда аргумент=значение"
                   onkeydown="if(event.key==='Enter')runCmd()">
            <button class="btn btn-primary" onclick="runCmd()">Выполнить</button>
            <button class="btn" onclick="clearOutput()">Очистить</button>
        </div>
        <div class="cmd-output" id="cmdOutput">AI-OS готова к работе. Введите команду или нажмите кнопку выше.\n</div>
    </div>

</div>

<div class="footer">AI-OS v0.1 — Модульная ИИ-система</div>

<script>
const API = '';

async function api(path, opts) {
    try {
        const r = await fetch(API + path, opts);
        return await r.json();
    } catch(e) {
        return {error: e.message};
    }
}

function $(id) { return document.getElementById(id); }

function appendOutput(text, cls='cmd-result') {
    const out = $('cmdOutput');
    const line = document.createElement('div');
    line.className = cls;
    line.textContent = text;
    out.appendChild(line);
    out.scrollTop = out.scrollHeight;
}

function formatJSON(obj) {
    return JSON.stringify(obj, null, 2);
}

async function runCmd() {
    const input = $('cmdInput');
    const cmd = input.value.trim();
    if (!cmd) return;
    input.value = '';

    appendOutput('> ' + cmd, 'cmd-line');

    const data = await api('/api/command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({command: cmd})
    });

    if (data.result) {
        appendOutput(formatJSON(data.result));
    } else {
        appendOutput(formatJSON(data));
    }
    appendOutput('');
}

async function quickCmd(cmd) {
    $('cmdInput').value = cmd;
    await runCmd();
}

function clearOutput() {
    $('cmdOutput').innerHTML = '';
}

async function loadOverview() {
    const d = await api('/api/system/overview');
    const r = d.result?.result || d.result || d;
    if (r && !r.error) {
        $('sysInfo').innerHTML = `
            <div class="metric"><span class="label">ОС</span><span class="value">${r.os} ${r.os_version}</span></div>
            <div class="metric"><span class="label">Процессор</span><span class="value" style="font-size:13px">${r.processor}</span></div>
            <div class="metric"><span class="label">Имя</span><span class="value">${r.hostname}</span></div>
            <div class="metric"><span class="label">Архитектура</span><span class="value">${r.machine}</span></div>
        `;
    }
}

async function loadMemory() {
    const d = await api('/api/system/memory');
    const r = d.result?.result || d.result || d;
    if (r && !r.error) {
        const pct = r.UsedPercent || 0;
        const cls = pct > 90 ? 'value-crit' : pct > 75 ? 'value-warn' : 'value-ok';
        const barCls = pct > 90 ? '#ef4444' : pct > 75 ? '#eab308' : '#22c55e';
        $('memDot').className = 'dot ' + (pct > 90 ? 'dot-red' : pct > 75 ? 'dot-yellow' : 'dot-green');
        $('memInfo').innerHTML = `
            <div class="metric"><span class="label">Использовано</span><span class="value ${cls}">${pct}%</span></div>
            <div class="bar-bg"><div class="bar-fill" style="width:${pct}%;background:${barCls}"></div></div>
            <div class="metric"><span class="label">Всего</span><span class="value">${r.TotalGB || r.TotalMB} ${r.TotalGB ? 'GB' : 'MB'}</span></div>
            <div class="metric"><span class="label">Свободно</span><span class="value">${r.FreeGB || r.FreeMB} ${r.FreeGB ? 'GB' : 'MB'}</span></div>
        `;
    }
}

async function loadDisks() {
    const d = await api('/api/disks');
    const items = d.result?.result || d.result || d;
    if (Array.isArray(items)) {
        let html = '';
        let hasWarn = false;
        items.forEach(disk => {
            const pct = disk.percent || disk.used_percent || 0;
            const cls = pct > 90 ? 'value-crit' : pct > 75 ? 'value-warn' : 'value-ok';
            const barCls = pct > 90 ? '#ef4444' : pct > 75 ? '#eab308' : '#22c55e';
            if (pct > 85) hasWarn = true;
            html += `
                <div class="metric"><span class="label">${disk.drive}</span><span class="value ${cls}">${pct}%</span></div>
                <div class="bar-bg"><div class="bar-fill" style="width:${pct}%;background:${barCls}"></div></div>
                <div class="metric"><span class="label">Свободно</span><span class="value">${disk.free_gb} GB</span></div>
            `;
        });
        $('diskDot').className = 'dot ' + (hasWarn ? 'dot-yellow' : 'dot-green');
        $('diskInfo').innerHTML = html;
    }
}

async function loadHealth() {
    const d = await api('/api/health');
    const r = d || {};
    const status = r.status || 'OK';
    const badge = $('healthBadge');
    badge.textContent = status === 'OK' ? 'Здоров' : status;
    badge.className = 'status-badge ' + (status === 'OK' ? 'status-ok' : status === 'CRITICAL' ? 'status-err' : 'status-warn');
    $('healthDot').className = 'dot ' + (status === 'OK' ? 'dot-green' : status === 'CRITICAL' ? 'dot-red' : 'dot-yellow');

    const alerts = r.alerts || [];
    if (alerts.length === 0) {
        $('healthInfo').innerHTML = '<div class="alert-item alert-ok">Всё в порядке</div>';
    } else {
        let html = '';
        alerts.forEach(a => {
            const cls = a.level === 'CRITICAL' ? 'alert-crit' : 'alert-warn';
            html += `<div class="alert-item ${cls}">[${a.level}] ${a.message}</div>`;
        });
        $('healthInfo').innerHTML = html;
    }
}

async function loadModules() {
    const d = await api('/api/status');
    const mods = d.modules || {};
    let html = '';
    for (const [name, info] of Object.entries(mods)) {
        const badgeCls = info.status === 'running' ? 'badge-running' : 'badge-stopped';
        const cmdCount = Object.keys(info.commands || {}).length;
        html += `
            <li class="module-item">
                <div>
                    <div class="name">${name}</div>
                    <div class="cmds">${info.description} (${cmdCount} команд)</div>
                </div>
                <span class="module-badge ${badgeCls}">${info.status}</span>
            </li>
        `;
    }
    $('moduleList').innerHTML = html;

    // Обучение
    const tr = d.trainer || {};
    $('trainInfo').innerHTML = `
        <div class="metric"><span class="label">Команд отслежено</span><span class="value">${tr.commands_observed || 0}</span></div>
        <div class="metric"><span class="label">Уникальных</span><span class="value">${tr.unique_commands || 0}</span></div>
        <div class="metric"><span class="label">Навыков</span><span class="value">${d.brain?.skills || 0}</span></div>
    `;
}

async function loadProcesses() {
    const d = await api('/api/processes');
    const items = d.result?.result || d.result || d;
    if (Array.isArray(items)) {
        let html = '<table class="process-table"><tr><th>Процесс</th><th>PID</th><th>RAM (MB)</th><th>CPU (s)</th></tr>';
        items.slice(0, 10).forEach(p => {
            html += `<tr><td>${p.Name}</td><td>${p.Id}</td><td>${p.MemMB}</td><td>${p.CPU_s || '-'}</td></tr>`;
        });
        html += '</table>';
        $('procInfo').innerHTML = html;
    }
}

async function loadReport() {
    const d = await api('/api/report');
    appendOutput('=== Отчёт обучения ===', 'cmd-line');
    appendOutput(formatJSON(d));
    appendOutput('');
}

// Загрузить всё при старте
async function init() {
    await Promise.all([
        loadOverview(),
        loadMemory(),
        loadDisks(),
        loadHealth(),
        loadModules(),
        loadProcesses(),
    ]);
}

// Автообновление каждые 30 секунд
init();
setInterval(() => {
    loadMemory();
    loadHealth();
    loadModules();
}, 30000);

// Фокус на поле ввода
$('cmdInput').focus();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    print()
    print("=" * 50)
    print("  AI-OS Dashboard")
    print("  Открой в браузере: http://localhost:8080")
    print("=" * 50)
    print()
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning")
