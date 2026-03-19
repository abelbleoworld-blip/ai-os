"""
Веб-интерфейс AI-OS.
Glassmorphism dark design.
Запускается на localhost:8080
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form
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
from modules.scanner import ScannerModule
from modules.scheduler import SchedulerModule
from modules.software import SoftwareModule
from ai.brain import Brain
from ai.claude_brain import ClaudeBrain
from ai.trainer import AutoTrainer

bus = SystemBus()
modules = [FilesModule(), ProcessesModule(), SystemInfoModule(), NetworkModule(), DesignerModule(), PlatformModule(), VersionsModule(), ScannerModule(), SoftwareModule()]
for m in modules:
    bus.register(m)
watchdog = WatchdogModule(bus=bus)
bus.register(watchdog)
scheduler = SchedulerModule(bus=bus)
bus.register(scheduler)
base_brain = Brain(bus)
trainer = AutoTrainer(base_brain)
base_brain.trainer = trainer
try:
    brain = ClaudeBrain(bus, base_brain)
except:
    brain = base_brain

@asynccontextmanager
async def lifespan(app):
    await bus.start_all()
    await watchdog.start()
    await watchdog.cmd_check()
    yield
    trainer.save()
    brain.save_memory()

app = FastAPI(title="AI-OS", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML

@app.get("/api/status")
async def api_status():
    return {"modules": bus.list_modules(), "brain": {"skills": len(brain.skills), "patterns": len(brain.patterns), "history_count": len(brain.history)}, "trainer": {"commands_observed": sum(trainer.command_counts.values()), "unique_commands": len(trainer.command_counts)}}

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

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """Загрузка файла — сохраняет в ai-os/uploads/"""
    import os
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, file.filename)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    size = len(content)
    # Анализируем файл через brain
    ext = os.path.splitext(file.filename)[1].lower()
    analysis = f"Файл '{file.filename}' загружен ({size} байт). Путь: {save_path}"
    if ext in ('.txt', '.py', '.js', '.json', '.md', '.csv', '.log', '.xml', '.html', '.css'):
        try:
            text = content.decode('utf-8', errors='replace')[:3000]
            analysis += f"\nСодержимое (первые 3000 символов):\n{text}"
        except:
            pass
    result = await brain.process(f"Загружен файл: {file.filename}, размер: {size} байт, путь: {save_path}")
    return {"filename": file.filename, "size": size, "path": save_path, "analysis": analysis, "ai_response": result}


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>AI-OS</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
--bg:#0A0A0A;--card:#151515;--card-hover:#1a1a1a;--card-border:rgba(255,255,255,0.06);
--glass:rgba(255,255,255,0.04);--glass-border:rgba(255,255,255,0.08);
--text:#F5F5F5;--text2:#9a9a9a;--text3:#555;
--accent:#6366F1;--accent-g:rgba(99,102,241,0.12);
--green:#22C55E;--green-g:rgba(34,197,94,0.12);
--amber:#F59E0B;--amber-g:rgba(245,158,11,0.12);
--red:#EF4444;--red-g:rgba(239,68,68,0.12);
--r:16px;--rs:10px;
}
html,body{height:100%;font-family:-apple-system,'SF Pro Display','Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);overflow:hidden}

/* Animated BG */
.bg-layer{position:fixed;top:0;left:0;right:0;bottom:0;z-index:0;overflow:hidden}
.bg-layer::before{content:'';position:absolute;width:140%;height:140%;top:-20%;left:-20%;
background:radial-gradient(ellipse at 30% 20%,rgba(99,102,241,0.08) 0%,transparent 50%),
radial-gradient(ellipse at 70% 80%,rgba(239,68,68,0.05) 0%,transparent 50%),
radial-gradient(ellipse at 50% 50%,rgba(34,197,94,0.04) 0%,transparent 60%);
animation:bgMove 20s ease-in-out infinite alternate}
@keyframes bgMove{0%{transform:translate(0,0) rotate(0deg)}100%{transform:translate(-3%,2%) rotate(2deg)}}

.app{display:flex;flex-direction:column;height:100vh;max-width:800px;margin:0 auto;position:relative;z-index:1}

/* HEADER */
.hdr{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;flex-shrink:0}
.hdr-left{display:flex;align-items:center;gap:14px}
.traffic{display:flex;gap:6px}
.traffic-dot{width:12px;height:12px;border-radius:50%}
.td-r{background:#EF4444}.td-y{background:#F59E0B}.td-g{background:#22C55E}
.hdr-time{color:var(--text2);font-size:13px;font-weight:400}
.hdr-right{color:var(--text2);font-size:13px}

/* STATUS BAR */
.status-bar{margin:0 20px 8px;padding:10px 16px;border-radius:var(--r);display:flex;align-items:center;gap:10px;transition:all 0.3s}
.sb-ok{background:var(--green-g);color:var(--green)}
.sb-warn{background:var(--amber-g);color:var(--amber)}
.sb-crit{background:var(--red-g);color:var(--red);animation:critPulse 2s ease infinite}
@keyframes critPulse{0%,100%{opacity:1}50%{opacity:0.7}}
.sb-dot{width:8px;height:8px;border-radius:50%;background:currentColor;flex-shrink:0}
.sb-text{font-size:13px;font-weight:500}
.sb-btn{margin-left:auto;padding:6px 14px;border-radius:20px;border:none;font-size:12px;font-weight:600;cursor:pointer;transition:all 0.15s;font-family:inherit}
.sb-btn-fix{background:var(--red);color:white}
.sb-btn-fix:hover{background:#dc2626}

/* CHAT */
.chat{flex:1;overflow-y:auto;padding:12px 20px;display:flex;flex-direction:column;gap:12px;scroll-behavior:smooth}
.chat::-webkit-scrollbar{width:3px}.chat::-webkit-scrollbar-thumb{background:var(--card-border);border-radius:3px}

.msg{max-width:82%;animation:msgIn 0.3s ease}
@keyframes msgIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.msg-user{align-self:flex-end}
.msg-ai{align-self:flex-start}

.bubble{padding:14px 18px;border-radius:var(--r);font-size:15px;line-height:1.55;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
.msg-user .bubble{background:rgba(255,255,255,0.08);border:1px solid var(--glass-border);border-bottom-right-radius:4px;color:var(--text)}
.msg-ai .bubble{background:rgba(255,255,255,0.04);border:1px solid var(--card-border);border-bottom-left-radius:4px}
.msg-ai .msg-name{font-size:11px;color:var(--text3);margin-bottom:4px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase}

/* Typing */
.typing{display:flex;gap:5px;padding:14px 18px}
.typing-d{width:8px;height:8px;background:var(--text3);border-radius:50%;animation:tBounce 1.4s ease infinite}
.typing-d:nth-child(2){animation-delay:.2s}.typing-d:nth-child(3){animation-delay:.4s}
@keyframes tBounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-8px)}}

/* MODULE GRID */
.mod-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}
.mod-tile{background:var(--card);border:1px solid var(--card-border);border-radius:var(--rs);padding:14px 12px;text-align:center;cursor:pointer;transition:all 0.2s}
.mod-tile:hover{background:var(--card-hover);border-color:rgba(255,255,255,0.12);transform:translateY(-2px)}
.mod-tile:active{transform:scale(0.97)}
.mod-icon{font-size:24px;margin-bottom:6px;display:block}
.mod-name{font-size:12px;color:var(--text2);font-weight:500}

/* SMART CARDS */
.scard{background:var(--card);border:1px solid var(--card-border);border-radius:var(--rs);padding:16px;margin-top:10px;backdrop-filter:blur(10px)}
.scard-title{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;font-weight:600}
.scard-row{display:flex;justify-content:space-between;align-items:center;padding:5px 0}
.scard-row+.scard-row{border-top:1px solid var(--card-border)}
.sc-l{color:var(--text2);font-size:13px}.sc-v{font-size:15px;font-weight:600}
.sc-ok{color:var(--green)}.sc-warn{color:var(--amber)}.sc-crit{color:var(--red)}

.bar-t{width:100%;height:5px;background:rgba(255,255,255,0.06);border-radius:3px;margin-top:6px;overflow:hidden}
.bar-f{height:100%;border-radius:3px;transition:width 0.6s cubic-bezier(.4,0,.2,1)}

/* Alert cards - 3 states */
.alert{display:flex;align-items:center;gap:10px;padding:12px 16px;border-radius:var(--rs);font-size:13px;font-weight:500;margin-top:6px}
.alert-ok{background:var(--green-g);color:var(--green)}
.alert-warn{background:var(--amber-g);color:var(--amber)}
.alert-crit{background:var(--red-g);color:var(--red);animation:critPulse 2s ease infinite}
.alert-dot{width:8px;height:8px;border-radius:50%;background:currentColor;flex-shrink:0}
.alert-btn{margin-left:auto;padding:6px 16px;border-radius:8px;border:none;background:var(--red);color:white;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit}
.alert-btn:hover{background:#dc2626}

/* Diag card */
.diag{background:var(--card);border:1px solid var(--card-border);border-radius:var(--rs);padding:16px;margin-top:10px}
.diag-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.diag-title{font-size:14px;font-weight:600}.diag-icon{font-size:20px}
.diag-status{font-size:13px;margin-bottom:8px}
.diag-actions{display:flex;gap:8px;margin-top:10px}
.diag-btn{padding:8px 16px;border-radius:8px;border:1px solid var(--card-border);background:var(--card);color:var(--text);font-size:12px;cursor:pointer;font-family:inherit;transition:all 0.15s}
.diag-btn:hover{background:var(--card-hover);border-color:var(--accent)}
.diag-btn-primary{background:var(--accent);border-color:var(--accent);color:white}
.diag-btn-primary:hover{background:#5558e6}

/* Process table */
.ptbl{width:100%;font-size:12px;border-collapse:collapse;margin-top:8px}
.ptbl th{color:var(--text3);font-weight:500;text-align:left;padding:4px 8px 8px;font-size:11px;text-transform:uppercase;letter-spacing:.3px}
.ptbl td{padding:5px 8px;color:var(--text2);border-top:1px solid var(--card-border)}
.ptbl td:first-child{color:var(--text);font-weight:500}

/* Code block */
.cblock{background:#0d0d0d;border:1px solid var(--card-border);border-radius:8px;padding:12px;margin-top:8px;font-family:'Cascadia Code','Fira Code',monospace;font-size:12px;color:var(--text2);white-space:pre-wrap;max-height:180px;overflow-y:auto;line-height:1.5}

/* INPUT */
.input-area{padding:10px 20px 20px;flex-shrink:0}
.input-row{display:flex;align-items:center;gap:10px;background:rgba(255,255,255,0.04);border:1px solid var(--glass-border);border-radius:28px;padding:6px 6px 6px 20px;backdrop-filter:blur(20px);transition:all 0.2s}
.input-row:focus-within{border-color:rgba(99,102,241,0.4);box-shadow:0 0 0 3px var(--accent-g)}
.input-f{flex:1;background:transparent;border:none;color:var(--text);font-size:15px;font-family:inherit;outline:none;padding:8px 0}
.input-f::placeholder{color:var(--text3)}
.btn-mic{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#ef4444,#f59e0b);border:none;color:white;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.15s;flex-shrink:0;font-size:16px}
.btn-mic:hover{transform:scale(1.05);box-shadow:0 0 16px rgba(239,68,68,0.3)}
.btn-send{width:42px;height:42px;border-radius:50%;background:var(--accent);border:none;color:white;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.15s;flex-shrink:0;font-size:18px}
.btn-send:hover{background:#5558e6;transform:scale(1.05)}
.mic-label{text-align:center;margin-top:6px;font-size:11px;color:var(--text3)}

/* Chips */
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.chip{padding:7px 14px;background:var(--glass);border:1px solid var(--glass-border);border-radius:20px;color:var(--text2);font-size:12px;cursor:pointer;transition:all 0.15s;font-family:inherit;backdrop-filter:blur(10px)}
.chip:hover{background:var(--accent-g);border-color:var(--accent);color:var(--accent)}

/* Notification toast */
.toast-container{position:fixed;top:20px;right:20px;z-index:1000;display:flex;flex-direction:column;gap:8px;pointer-events:none}
.toast{padding:14px 20px;border-radius:var(--rs);font-size:13px;font-weight:500;pointer-events:auto;cursor:pointer;animation:toastIn 0.3s ease;backdrop-filter:blur(20px);max-width:360px;display:flex;align-items:center;gap:10px;box-shadow:0 8px 32px rgba(0,0,0,0.4)}
.toast-ok{background:rgba(34,197,94,0.15);border:1px solid rgba(34,197,94,0.3);color:var(--green)}
.toast-warn{background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.3);color:var(--amber)}
.toast-crit{background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:var(--red);animation:toastIn 0.3s ease,critPulse 2s ease infinite}
@keyframes toastIn{from{opacity:0;transform:translateX(40px)}to{opacity:1;transform:translateX(0)}}
.toast .toast-close{margin-left:auto;opacity:0.5;font-size:16px}
.toast .toast-close:hover{opacity:1}

/* Mic button */
.btn-mic{width:42px;height:42px;border-radius:50%;background:var(--card);border:1px solid var(--card-border);color:var(--text2);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.2s;flex-shrink:0;font-size:16px}
.btn-mic:hover{border-color:var(--accent);color:var(--accent)}
.btn-mic.recording{background:var(--red);border-color:var(--red);color:white;animation:micPulse 1.5s ease infinite}
@keyframes micPulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.4)}50%{box-shadow:0 0 0 12px rgba(239,68,68,0)}}

.hidden{display:none!important}
@media(max-width:600px){.msg{max-width:92%}.mod-grid{grid-template-columns:repeat(2,1fr)}.hdr{padding:12px 16px}.chat{padding:10px 16px}.input-area{padding:8px 16px 16px}}
</style>
</head>
<body>
<div class="bg-layer"></div>
<div class="toast-container" id="toasts"></div>
<div class="app">
<div class="hdr">
<div class="hdr-left">
<div class="traffic"><div class="traffic-dot td-r"></div><div class="traffic-dot td-y"></div><div class="traffic-dot td-g"></div></div>
<div class="hdr-time" id="hTime"></div>
</div>
<div class="hdr-right">AI-OS</div>
</div>

<div id="statusBar" class="status-bar sb-ok"><div class="sb-dot"></div><span class="sb-text" id="sbText">System Online</span></div>

<div class="chat" id="chat"></div>

<div class="input-area">
<div class="input-row">
<button class="btn-mic" id="micBtn" onclick="toggleMic()" title="Голосовой ввод">&#127908;</button>
<button class="btn-mic" onclick="document.getElementById('fileInp').click()" title="Прикрепить файл">&#128206;</button>
<input type="file" id="fileInp" style="display:none" onchange="uploadFile(this)">
<input type="text" class="input-f" id="inp" placeholder="Напиши или скажи голосом..." autocomplete="off" onkeydown="if(event.key==='Enter'){event.preventDefault();send()}">
<button class="btn-send" onclick="send()" title="Отправить">&#8593;</button>
</div>
<div class="mic-label"></div>
</div>
</div>

<script>
const C=document.getElementById('chat'),I=document.getElementById('inp');
function uTime(){const n=new Date(),h=String(n.getHours()).padStart(2,'0'),m=String(n.getMinutes()).padStart(2,'0'),d=String(n.getDate()).padStart(2,'0'),mo=String(n.getMonth()+1).padStart(2,'0');document.getElementById('hTime').textContent=h+':'+m+' | '+d+'.'+mo+'.'+n.getFullYear()}
uTime();setInterval(uTime,30000);

function addMsg(c,t='ai'){
const m=document.createElement('div');m.className='msg msg-'+t;
const b=document.createElement('div');b.className='bubble';
if(t==='ai'){const n=document.createElement('div');n.className='msg-name';n.textContent='AI-OS';m.appendChild(n)}
if(typeof c==='string')b.innerHTML=c;else b.appendChild(c);
m.appendChild(b);C.appendChild(m);C.scrollTop=C.scrollHeight;return b}

function showTyping(){const m=document.createElement('div');m.className='msg msg-ai';m.id='typ';
m.innerHTML='<div class="msg-name">AI-OS</div><div class="bubble"><div class="typing"><div class="typing-d"></div><div class="typing-d"></div><div class="typing-d"></div></div><div style="color:var(--text3);font-size:13px;margin-top:4px">Ищу решение...</div></div>';
C.appendChild(m);C.scrollTop=C.scrollHeight}
function hideTyping(){const t=document.getElementById('typ');if(t)t.remove()}

function dig(o){if(!o)return o;if(o.result&&typeof o.result==='object'){if(o.result.result!==undefined)return o.result.result;return o.result}return o}

function memCard(d){
const p=d.UsedPercent||0,cls=p>90?'sc-crit':p>75?'sc-warn':'sc-ok',bc=p>90?'var(--red)':p>75?'var(--amber)':'var(--green)';
const e=document.createElement('div');e.className='scard';
e.innerHTML='<div class="scard-title">Память</div><div class="scard-row"><span class="sc-l">Занято</span><span class="sc-v '+cls+'">'+p+'%</span></div><div class="bar-t"><div class="bar-f" style="width:'+p+'%;background:'+bc+'"></div></div><div class="scard-row"><span class="sc-l">Всего</span><span class="sc-v">'+(d.TotalGB||d.TotalMB)+' '+(d.TotalGB?'GB':'MB')+'</span></div><div class="scard-row"><span class="sc-l">Свободно</span><span class="sc-v">'+(d.FreeGB||d.FreeMB)+' '+(d.FreeGB?'GB':'MB')+'</span></div>';
return e}

function diskCard(items){
const e=document.createElement('div');e.className='scard';let h='<div class="scard-title">Диски</div>';
items.forEach(d=>{const p=d.percent||d.used_percent||0,cls=p>90?'sc-crit':p>75?'sc-warn':'sc-ok',bc=p>90?'var(--red)':p>75?'var(--amber)':'var(--green)';
h+='<div class="scard-row"><span class="sc-l">'+d.drive+'</span><span class="sc-v '+cls+'">'+p+'%</span></div><div class="bar-t"><div class="bar-f" style="width:'+p+'%;background:'+bc+'"></div></div><div class="scard-row"><span class="sc-l">Свободно</span><span class="sc-v">'+d.free_gb+' GB</span></div>'});
e.innerHTML=h;return e}

function healthCard(d){
const e=document.createElement('div');let h='';const alerts=d.alerts||[];
const sb=document.getElementById('statusBar'),st=document.getElementById('sbText');
const status=d.status||'OK';
sb.className='status-bar '+(status==='OK'?'sb-ok':status==='CRITICAL'?'sb-crit':'sb-warn');
st.textContent=status==='OK'?'System Online':status==='CRITICAL'?'CRITICAL':'Warning';

if(alerts.length===0){
h+='<div class="alert alert-ok"><div class="alert-dot"></div>Всё в порядке</div>'}
else{alerts.forEach(a=>{
const c=a.level==='CRITICAL'?'alert-crit':'alert-warn';
const icon=a.level==='CRITICAL'?'&#9888;':'&#9888;';
h+='<div class="alert '+c+'"><div class="alert-dot"></div>'+a.message+(a.level==='CRITICAL'?'<button class="alert-btn" onclick="quick(&quot;watchdog.heal&quot;)">Починить</button>':'')+'</div>'})}
e.innerHTML=h;return e}

function procCard(items){
const e=document.createElement('div');e.className='scard';
let h='<div class="scard-title">Процессы</div><table class="ptbl"><tr><th>Имя</th><th>PID</th><th>RAM</th><th>CPU</th></tr>';
(Array.isArray(items)?items:[]).slice(0,8).forEach(p=>{h+='<tr><td>'+p.Name+'</td><td>'+p.Id+'</td><td>'+p.MemMB+' MB</td><td>'+(p.CPU_s||'-')+'s</td></tr>'});
h+='</table>';e.innerHTML=h;return e}

function modGrid(){
const mods=[
{icon:'&#128193;',name:'Файлы',cmd:'files.list'},
{icon:'&#9881;',name:'Процессы',cmd:'processes.list top=5'},
{icon:'&#127760;',name:'Сеть',cmd:'network.ping host=google.com'},
{icon:'&#10084;',name:'Здоровье',cmd:'watchdog.check'},
{icon:'&#128187;',name:'CPU',cmd:'system.cpu'},
{icon:'&#128191;',name:'Диски',cmd:'files.disk_usage'},
{icon:'&#128272;',name:'Версии',cmd:'versions.list'},
{icon:'&#127912;',name:'Дизайн',cmd:'designer.colors'},
{icon:'&#129302;',name:'ИИ',cmd:'report'}
];
const g=document.createElement('div');g.className='mod-grid';
mods.forEach(m=>{const d=document.createElement("div");d.className="mod-tile";d.onclick=()=>quick(m.cmd);d.innerHTML='<span class="mod-icon">'+m.icon+'</span><span class="mod-name">'+m.name+'</span>';g.appendChild(d)});
return g}

function tryCard(mod,cmd,d){
if(!d)return null;
if(d.UsedPercent!==undefined&&(d.TotalGB||d.TotalMB))return memCard(d);
if(Array.isArray(d)&&d[0]&&(d[0].drive||d[0].percent!==undefined))return diskCard(d);
if(d.checks&&d.alerts!==undefined)return healthCard(d);
if(Array.isArray(d)&&d[0]&&d[0].Name&&d[0].Id)return procCard(d);
return null}

function fmtResult(data){
if(data.result&&data.result.comment){
const f=document.createElement('div');f.innerHTML='<div style="margin-bottom:8px">'+data.result.comment+'</div>';
if(data.result.results){data.result.results.forEach(r=>{
const inner=dig(r.result);const card=tryCard(r.module,r.command,inner);
if(card)f.appendChild(card);
else if(inner){const c=document.createElement('div');c.className='cblock';c.textContent=typeof inner==='string'?inner:JSON.stringify(inner,null,2);f.appendChild(c)}})}
return f}
if(data.result&&typeof data.result==='string')return data.result;
if(data.result){const inner=dig(data.result);const card=tryCard('','',inner);
if(card){const f=document.createElement('div');f.appendChild(card);return f}
const f=document.createElement('div');const c=document.createElement('div');c.className='cblock';c.textContent=typeof inner==='string'?inner:JSON.stringify(inner,null,2);f.appendChild(c);return f}
return JSON.stringify(data,null,2)}

async function send(){
const t=I.value.trim();if(!t)return;I.value='';addMsg(t,'user');showTyping();
try{const r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:t})});
const d=await r.json();hideTyping();addMsg(fmtResult(d),'ai')}
catch(e){hideTyping();addMsg('<span style="color:var(--red)">Ошибка: '+e.message+'</span>','ai')}}

function quick(t){I.value=t;send()}

async function uploadFile(input){
if(!input.files||!input.files[0])return;
const file=input.files[0];
addMsg('&#128206; '+file.name+' ('+Math.round(file.size/1024)+' KB)','user');
showTyping();
const fd=new FormData();fd.append('file',file);
try{
const r=await fetch('/api/upload',{method:'POST',body:fd});
const d=await r.json();hideTyping();
const frag=document.createElement('div');
let html='<div style="margin-bottom:8px">&#9989; Файл <strong>'+d.filename+'</strong> загружен</div>';
html+='<div class="scard"><div class="scard-title">Файл</div>';
html+='<div class="scard-row"><span class="sc-l">Имя</span><span class="sc-v">'+d.filename+'</span></div>';
html+='<div class="scard-row"><span class="sc-l">Размер</span><span class="sc-v">'+Math.round(d.size/1024)+' KB</span></div>';
html+='<div class="scard-row"><span class="sc-l">Путь</span><span class="sc-v" style="font-size:11px;word-break:break-all">'+d.path+'</span></div>';
html+='</div>';
if(d.ai_response&&typeof d.ai_response==='string')html+='<div style="margin-top:8px">'+d.ai_response+'</div>';
frag.innerHTML=html;addMsg(frag,'ai');
}catch(e){hideTyping();addMsg('Ошибка загрузки: '+e.message,'ai')}
input.value='';}

async function init(){
try{
const[health,st]=await Promise.all([fetch('/api/health').then(r=>r.json()),fetch('/api/status').then(r=>r.json())]);
const sb=document.getElementById('statusBar'),stx=document.getElementById('sbText');
const s=health.status||'OK';
sb.className='status-bar '+(s==='OK'?'sb-ok':s==='CRITICAL'?'sb-crit':'sb-warn');
stx.textContent=s==='OK'?'System Online':s;
if(s!=='OK'&&health.alerts){
sb.innerHTML='<div class="sb-dot"></div><span class="sb-text">'+health.alerts[0].message+'</span>'+(s==='CRITICAL'?'<button class="sb-btn sb-btn-fix" onclick="quick(&quot;watchdog.heal&quot;)">Починить</button>':'')}

const mc=Object.keys(st.modules).length;
const rc=Object.values(st.modules).filter(m=>m.status==='running').length;
const w=document.createElement('div');
let h='Привет! Я <strong>AI-OS</strong>. '+rc+'/'+mc+' модулей активно.';

if(health.alerts&&health.alerts.length>0){
health.alerts.forEach(a=>{const c=a.level==='CRITICAL'?'alert-crit':'alert-warn';
h+='<div class="alert '+c+'" style="margin-top:8px"><div class="alert-dot"></div>'+a.message+(a.level==='CRITICAL'?'<button class="alert-btn" onclick="quick(&quot;watchdog.heal&quot;)">Починить</button>':'')+'</div>'})}
else{h+='<div class="alert alert-ok" style="margin-top:8px"><div class="alert-dot"></div>Система в порядке</div>'}

w.innerHTML=h;
const bubble=addMsg(w,'ai');
bubble.appendChild(modGrid());

const chips=document.createElement('div');chips.className='chips';
['Здоровье','Память','Процессы','Диски','Сеть'].forEach(n=>{
const cmds={'Здоровье':'проверь здоровье','Память':'что с памятью?','Процессы':'покажи процессы','Диски':'сколько места на дисках?','Сеть':'проверь сеть'};
const ch=document.createElement("span");ch.className="chip";ch.textContent=n;ch.onclick=()=>quick(cmds[n]);chips.appendChild(ch)});
bubble.appendChild(chips);
}catch(e){addMsg('Запускаюсь...','ai')}
I.focus()}

init();
// === NOTIFICATIONS ===
let lastHealthStatus='OK';
function showToast(msg,level='ok',duration=6000){
const tc=document.getElementById('toasts');
const t=document.createElement('div');
t.className='toast toast-'+level;
t.innerHTML='<span>'+msg+'</span><span class="toast-close" onclick="this.parentElement.remove()">&#10005;</span>';
tc.appendChild(t);
setTimeout(()=>{if(t.parentElement)t.style.opacity='0';setTimeout(()=>t.remove(),300)},duration);
// Browser notification
if(Notification.permission==='granted'&&level!=='ok'){new Notification('AI-OS',{body:msg,icon:'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🤖</text></svg>'})}
}

// Request notification permission
if('Notification' in window&&Notification.permission==='default'){Notification.requestPermission()}

// Health check with notifications
setInterval(async()=>{try{const h=await fetch('/api/health').then(r=>r.json());const s=h.status||'OK';
const sb=document.getElementById('statusBar');
sb.className='status-bar '+(s==='OK'?'sb-ok':s==='CRITICAL'?'sb-crit':'sb-warn');
if(s==='OK')sb.innerHTML='<div class="sb-dot"></div><span class="sb-text" id="sbText">System Online</span>';
else if(h.alerts&&h.alerts.length){sb.innerHTML='<div class="sb-dot"></div><span class="sb-text">'+h.alerts[0].message+'</span>'}
// Notify on status change
if(s!==lastHealthStatus){
if(s==='CRITICAL')showToast(h.alerts[0].message,'crit',10000);
else if(s==='WARNING')showToast(h.alerts[0].message,'warn',8000);
else if(lastHealthStatus!=='OK')showToast('Система восстановлена','ok',4000);
lastHealthStatus=s}
}catch(e){}},30000);

// === VOICE INPUT (Web Speech API) ===
let recognition=null;
let isRecording=false;

function toggleMic(){
if(!('webkitSpeechRecognition' in window)&&!('SpeechRecognition' in window)){
showToast('Голосовой ввод не поддерживается в этом браузере. Используй Chrome.','warn');return}
if(isRecording){stopMic();return}
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
recognition=new SR();
recognition.lang='ru-RU';
recognition.interimResults=true;
recognition.continuous=false;
recognition.maxAlternatives=1;
const btn=document.getElementById('micBtn');
btn.classList.add('recording');
isRecording=true;
let finalText='';
recognition.onresult=(e)=>{
let interim='';
for(let i=e.resultIndex;i<e.results.length;i++){
if(e.results[i].isFinal)finalText+=e.results[i][0].transcript;
else interim+=e.results[i][0].transcript}
I.value=finalText+interim};
recognition.onend=()=>{
btn.classList.remove('recording');isRecording=false;
if(finalText.trim()){I.value=finalText.trim();send()}};
recognition.onerror=(e)=>{
btn.classList.remove('recording');isRecording=false;
if(e.error!=='no-speech')showToast('Ошибка микрофона: '+e.error,'warn')};
recognition.start();
showToast('Слушаю... Говори команду','ok',3000)}

function stopMic(){
if(recognition){recognition.stop()}
document.getElementById('micBtn').classList.remove('recording');
isRecording=false}
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    print("  AI-OS | http://localhost:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning")
