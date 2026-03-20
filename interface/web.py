"""
AI-OS Web Interface.
Chat-first glassmorphism design. No tabs, no menus. Just conversation.
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
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
from modules.mesh import MeshModule
from ai.brain import Brain
from ai.claude_brain import ClaudeBrain
from ai.trainer import AutoTrainer
from modules.learner import LearnerModule
from modules.ingest import IngestModule
from modules.utils import UtilsModule

bus = SystemBus()
modules = [FilesModule(), ProcessesModule(), SystemInfoModule(), NetworkModule(), DesignerModule(), PlatformModule(), VersionsModule(), ScannerModule(), SoftwareModule()]
for m in modules:
    bus.register(m)
watchdog = WatchdogModule(bus=bus)
bus.register(watchdog)
scheduler = SchedulerModule(bus=bus)
bus.register(scheduler)
mesh = MeshModule(bus=bus)
bus.register(mesh)
base_brain = Brain(bus)
trainer = AutoTrainer(base_brain)
base_brain.trainer = trainer
try:
    brain = ClaudeBrain(bus, base_brain)
except:
    brain = base_brain
learner = LearnerModule(bus=bus, brain=brain, trainer=trainer)
bus.register(learner)
ingest = IngestModule(bus=bus, brain=brain)
bus.register(ingest)
utils = UtilsModule(bus=bus)
bus.register(utils)

# Hook learner into brain processing
_orig_process = brain.process
async def _hooked_process(user_input):
    result = await _orig_process(user_input)
    learner.observe(user_input, result)
    return result
brain.process = _hooked_process

@asynccontextmanager
async def lifespan(app):
    await bus.start_all()
    await watchdog.start()
    await watchdog.cmd_check()
    yield
    trainer.save()
    learner._save()
    brain.save_memory()

app = FastAPI(title="AI-OS", lifespan=lifespan)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
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
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, file.filename)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    size = len(content)
    ext = os.path.splitext(file.filename)[1].lower()
    analysis = f"Файл '{file.filename}' загружен ({size} байт)"
    if ext in ('.txt', '.py', '.js', '.json', '.md', '.csv', '.log', '.xml', '.html', '.css'):
        try:
            text = content.decode('utf-8', errors='replace')[:3000]
            analysis += f"\n{text}"
        except:
            pass
    result = await brain.process(f"Загружен файл: {file.filename}, размер: {size} байт, путь: {save_path}")
    return {"filename": file.filename, "size": size, "path": save_path, "analysis": analysis, "ai_response": result}

# --- Mesh API (связь между нодами) ---

@app.get("/mesh/nodes")
async def mesh_nodes():
    return await mesh.cmd_nodes()

@app.get("/mesh/status")
async def mesh_status():
    return await mesh.cmd_status()

@app.post("/mesh/register")
async def mesh_register(data: dict):
    if data.get("secret") != mesh.secret:
        return {"error": "wrong secret"}
    return mesh.hub_register(data)

@app.post("/mesh/heartbeat")
async def mesh_heartbeat(data: dict):
    if data.get("secret") != mesh.secret:
        return {"error": "wrong secret"}
    return mesh.hub_heartbeat(data)

@app.post("/mesh/command")
async def mesh_command(data: dict):
    """Отправить команду на конкретную ноду"""
    node = data.get("node", "")
    module = data.get("module", "")
    command = data.get("command", "")
    args = data.get("args", {})
    if not node or not module or not command:
        return {"error": "need node, module, command"}
    return await mesh.hub_send_to_node(node, module, command, **args)

@app.post("/mesh/execute")
async def mesh_execute(data: dict):
    """Агент выполняет команду от хаба"""
    if data.get("secret") != mesh.secret:
        return {"error": "wrong secret"}
    module = data.get("module", "")
    command = data.get("command", "")
    args = data.get("args", {})
    return await bus.send(module, command, **args)

# --- Skills & Knowledge ---

@app.get("/api/skills")
async def api_skills():
    skills = {}
    for name, s in brain.skills.items():
        skills[name] = {
            "description": s.get("description", ""),
            "steps": len(s.get("steps", [])),
            "times_used": s.get("times_used", 0),
            "success_rate": s.get("success_rate", 1.0)
        }
    return {"skills": skills, "total": len(skills)}

@app.get("/api/knowledge")
async def api_knowledge():
    from ai.knowledge import KnowledgeBase
    result = {}
    for name in ["files", "processes", "system", "network", "watchdog", "designer", "platform"]:
        try:
            kb = KnowledgeBase(name)
            result[name] = {"entries": len(kb.entries), "solutions": len(kb.solutions), "sources": len(kb.sources)}
        except:
            pass
    return result

@app.get("/api/models")
async def api_models():
    config_path = Path(__file__).parent.parent / "config" / "api.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    return {
        "provider": config.get("provider", "unknown"),
        "default_model": config.get("default_model", ""),
        "smart_model": config.get("smart_model", ""),
        "openrouter_models": config.get("openrouter_models", {}),
        "max_tokens": config.get("max_tokens", 1024),
        "conversation_length": len(brain.conversation) if hasattr(brain, 'conversation') else 0
    }

@app.get("/api/stats")
async def api_stats():
    modules_info = bus.list_modules()
    from ai.knowledge import KnowledgeBase
    total_knowledge = 0
    total_solutions = 0
    for name in ["files", "processes", "system", "network", "watchdog", "designer", "platform"]:
        try:
            kb = KnowledgeBase(name)
            total_knowledge += len(kb.entries)
            total_solutions += len(kb.solutions)
        except:
            pass
    return {
        "modules": {"total": len(modules_info), "running": sum(1 for m in modules_info.values() if m["status"] == "running")},
        "brain": {"skills": len(brain.skills), "patterns": len(brain.patterns) if hasattr(brain, 'patterns') else 0, "history": len(brain.history), "conversation": len(brain.conversation) if hasattr(brain, 'conversation') else 0},
        "knowledge": {"entries": total_knowledge, "solutions": total_solutions},
        "trainer": {"commands_observed": sum(trainer.command_counts.values()), "unique_commands": len(trainer.command_counts)}
    }

@app.post("/api/knowledge/seed")
async def api_seed_knowledge():
    import subprocess
    result = subprocess.run(["python", "knowledge/seed.py"], capture_output=True, text=True, cwd=str(Path(__file__).parent.parent))
    return {"status": "ok", "output": result.stdout, "errors": result.stderr}


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>AI-OS</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
--bg:#0A0A0A;--bg-w:#0F0E0A;--bg-c:#1A0F0F;
--glass:rgba(255,255,255,0.06);--glass2:rgba(255,255,255,0.04);--glass-b:rgba(255,255,255,0.1);
--text:#F5F5F5;--t2:#9a9a9a;--t3:#555;
--accent:#6366F1;--accent2:#818CF8;
--green:#22C55E;--amber:#F59E0B;--red:#EF4444;--cyan:#06B6D4;--purple:#A855F7;
--r:20px;--rs:14px;
}
html,body{height:100%;font-family:'SF Pro Display','Inter',-apple-system,system-ui,sans-serif;background:var(--bg);color:var(--text);overflow:hidden;font-size:17px;transition:background 1.2s ease}

/* === TOP BAR === */
.top{position:fixed;top:0;left:0;right:0;z-index:100;display:flex;align-items:center;justify-content:space-between;padding:10px 24px;height:40px;background:rgba(10,10,10,0.7);backdrop-filter:blur(30px);-webkit-backdrop-filter:blur(30px);border-bottom:1px solid rgba(255,255,255,0.04)}
.top-l{display:flex;align-items:center;gap:10px}
.sdot{width:9px;height:9px;border-radius:50%;background:var(--green);transition:all 1s}
.sdot.w{background:var(--amber)}.sdot.c{background:var(--red);animation:glow 3s ease infinite}
@keyframes glow{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.4)}50%{box-shadow:0 0 8px 3px rgba(239,68,68,0.2)}}
.top-time{font-size:13px;color:var(--t2);font-weight:400;letter-spacing:.3px}
.top-ctx{font-size:13px;color:var(--t3);font-weight:500}

/* === MAIN CHAT === */
.wrap{position:fixed;top:40px;left:0;right:0;bottom:0;display:flex;flex-direction:column;max-width:740px;margin:0 auto}
.scroll{flex:1;overflow-y:auto;padding:24px 20px 12px;display:flex;flex-direction:column;gap:8px;scroll-behavior:smooth}
.scroll::-webkit-scrollbar{width:0}

/* Messages */
.m{max-width:80%;animation:mIn .18s ease}
@keyframes mIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.m-u{align-self:flex-end}.m-a{align-self:flex-start}
.b{padding:14px 20px;border-radius:var(--r);font-size:17px;line-height:1.6;backdrop-filter:blur(40px);-webkit-backdrop-filter:blur(40px)}
.m-u .b{background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);border-bottom-right-radius:6px}
.m-a .b{background:var(--glass2);border:1px solid rgba(255,255,255,0.06);border-bottom-left-radius:6px}
.m-lbl{font-size:10px;color:var(--t3);margin-bottom:3px;font-weight:600;letter-spacing:.5px;text-transform:uppercase}

/* Typing */
.typ-wrap{display:flex;align-items:center;gap:6px;padding:16px 20px}
.typ-dots{display:flex;gap:5px}
.td{width:8px;height:8px;background:var(--t3);border-radius:50%;animation:tb 1.4s ease infinite}
.td:nth-child(2){animation-delay:.15s}.td:nth-child(3){animation-delay:.3s}
@keyframes tb{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-6px)}}
.typ-txt{font-size:13px;color:var(--t3);margin-left:4px}

/* === GLASS CARDS (smart cards in chat) === */
.gc{background:rgba(255,255,255,0.05);backdrop-filter:blur(40px);-webkit-backdrop-filter:blur(40px);border:1px solid rgba(255,255,255,0.08);border-radius:var(--rs);padding:16px;margin-top:8px}
.gc-title{font-size:12px;color:var(--t3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px;font-weight:600;display:flex;align-items:center;gap:8px}
.gc-icon{font-size:16px}

/* Key-value */
.kv{display:flex;justify-content:space-between;align-items:center;padding:7px 0}
.kv+.kv{border-top:1px solid rgba(255,255,255,0.04)}
.kv-k{font-size:14px;color:var(--t2)}.kv-v{font-size:15px;font-weight:600}

/* Progress bar */
.pb{height:5px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden;margin-top:6px}
.pb-f{height:100%;border-radius:3px;transition:width .6s cubic-bezier(.4,0,.2,1)}

/* Stats strip */
.stats{display:flex;gap:1px;margin-top:10px;border-radius:var(--rs);overflow:hidden}
.st{flex:1;background:rgba(255,255,255,0.04);padding:14px 10px;text-align:center;backdrop-filter:blur(20px)}
.st-n{font-size:24px;font-weight:700;line-height:1}.st-l{font-size:10px;color:var(--t3);margin-top:5px;text-transform:uppercase;letter-spacing:.4px}
.cg{color:var(--green)}.ca{color:var(--accent2)}.cc{color:var(--cyan)}.cp{color:var(--purple)}.cw{color:var(--amber)}.cr{color:var(--red)}

/* Gauge */
.gauges{display:flex;gap:10px;margin-top:10px}
.ga{flex:1;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.06);border-radius:var(--rs);padding:16px;text-align:center;backdrop-filter:blur(20px)}
.ga svg{width:80px;height:80px;display:block;margin:0 auto 6px}
.ga-l{font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:.3px;margin-bottom:6px;font-weight:600}
.ga-s{font-size:11px;color:var(--t3);margin-top:2px}

/* Alerts */
.al{display:flex;align-items:center;gap:10px;padding:14px 16px;border-radius:var(--rs);font-size:14px;font-weight:500;margin-top:8px;backdrop-filter:blur(20px)}
.al-ok{background:rgba(34,197,94,0.08);color:var(--green);border:1px solid rgba(34,197,94,0.12)}
.al-w{background:rgba(245,158,11,0.08);color:var(--amber);border:1px solid rgba(245,158,11,0.12)}
.al-c{background:rgba(239,68,68,0.08);color:var(--red);border:1px solid rgba(239,68,68,0.12)}
.al-dot{width:8px;height:8px;border-radius:50%;background:currentColor;flex-shrink:0}
.al-txt{flex:1}

/* Action buttons on cards */
.acts{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.abtn{padding:9px 18px;border-radius:10px;border:none;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .15s}
.abtn-p{background:var(--accent);color:white}.abtn-p:hover{background:#5558e6;transform:translateY(-1px)}
.abtn-d{background:var(--red);color:white}.abtn-d:hover{background:#dc2626}
.abtn-s{background:rgba(255,255,255,0.06);color:var(--t2);border:1px solid rgba(255,255,255,0.08)}.abtn-s:hover{border-color:var(--accent);color:var(--accent2)}

/* Module grid (appears briefly) */
.modgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}
.modtile{background:rgba(255,255,255,0.05);backdrop-filter:blur(30px);-webkit-backdrop-filter:blur(30px);border:1px solid rgba(255,255,255,0.08);border-radius:var(--rs);padding:16px 10px;text-align:center;cursor:pointer;transition:all .15s}
.modtile:hover{background:rgba(255,255,255,0.09);transform:translateY(-2px)}
.modtile:active{transform:scale(.95)}
.modtile-i{font-size:24px;margin-bottom:6px;display:block}
.modtile-n{font-size:11px;color:var(--t2);font-weight:500}

/* File card */
.fcard{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:var(--rs);padding:16px;margin-top:8px;display:flex;align-items:center;gap:14px}
.fcard-icon{font-size:28px;width:48px;height:48px;background:rgba(255,255,255,0.06);border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.fcard-info{flex:1;min-width:0}
.fcard-name{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fcard-size{font-size:12px;color:var(--t3);margin-top:2px}

/* Process table */
.ptbl{width:100%;font-size:13px;border-collapse:collapse;margin-top:8px}
.ptbl th{color:var(--t3);font-weight:500;text-align:left;padding:8px;font-size:10px;text-transform:uppercase;letter-spacing:.3px;border-bottom:1px solid rgba(255,255,255,0.06)}
.ptbl td{padding:7px 8px;color:var(--t2);border-bottom:1px solid rgba(255,255,255,0.03)}
.ptbl td:first-child{color:var(--text);font-weight:500}

/* Code block */
.cblk{background:rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:14px;font-family:'SF Mono','Cascadia Code','Fira Code',monospace;font-size:13px;color:var(--t2);white-space:pre-wrap;max-height:200px;overflow-y:auto;line-height:1.5;margin-top:8px}

/* Model badge */
.mbadge{display:inline-flex;align-items:center;gap:6px;padding:5px 14px;border-radius:20px;font-size:11px;font-weight:600;background:rgba(99,102,241,0.1);color:var(--accent2);border:1px solid rgba(99,102,241,0.15);margin-top:10px}

/* Chips */
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.chip{padding:9px 18px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);border-radius:24px;color:var(--t2);font-size:14px;cursor:pointer;transition:all .15s;font-family:inherit;backdrop-filter:blur(10px)}
.chip:hover{background:rgba(99,102,241,0.1);border-color:rgba(99,102,241,0.25);color:var(--accent2)}

/* === INPUT === */
.inp-area{padding:10px 20px 24px;flex-shrink:0}
.inp-row{display:flex;align-items:center;gap:10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);border-radius:var(--r);padding:6px 8px 6px 20px;backdrop-filter:blur(30px);-webkit-backdrop-filter:blur(30px);transition:all .2s}
.inp-row:focus-within{border-color:rgba(99,102,241,0.3);box-shadow:0 0 0 3px rgba(99,102,241,0.07)}
.inp-f{flex:1;background:transparent;border:none;color:var(--text);font-size:17px;font-family:inherit;outline:none;padding:10px 0}
.inp-f::placeholder{color:var(--t3)}

/* Buttons */
.ib{width:44px;height:44px;border-radius:14px;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s;flex-shrink:0;font-size:17px}
.ib-send{background:var(--accent);color:white}.ib-send:hover{background:#5558e6;transform:scale(1.05)}
.ib-g{background:transparent;border:1px solid rgba(255,255,255,0.07);color:var(--t3)}.ib-g:hover{border-color:var(--accent);color:var(--accent2)}
.ib-mic{background:linear-gradient(135deg,var(--red),var(--amber));color:white;border:none}
.ib-mic:hover{transform:scale(1.05);box-shadow:0 0 16px rgba(239,68,68,0.25)}
.ib-mic.rec{animation:mpulse 1.5s ease infinite}
@keyframes mpulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.3)}50%{box-shadow:0 0 0 12px rgba(239,68,68,0)}}

/* Toast */
.toasts{position:fixed;top:48px;right:16px;z-index:200;display:flex;flex-direction:column;gap:8px;pointer-events:none}
.toast{padding:14px 18px;border-radius:var(--rs);font-size:14px;font-weight:500;pointer-events:auto;cursor:pointer;animation:tIn .18s ease;backdrop-filter:blur(30px);max-width:340px;display:flex;align-items:center;gap:10px;box-shadow:0 8px 32px rgba(0,0,0,0.5)}
.toast-ok{background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.2);color:var(--green)}
.toast-w{background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.2);color:var(--amber)}
.toast-c{background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.2);color:var(--red)}
@keyframes tIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}

/* Responsive: phone = only chat + floating mic */
@media(max-width:600px){
  .wrap{max-width:100%}
  .m{max-width:90%}
  .gauges{flex-direction:column}
  .modgrid{grid-template-columns:repeat(2,1fr)}
  .stats{flex-wrap:wrap}.st{min-width:45%}
  .b{font-size:16px;padding:12px 16px}
  .inp-area{padding:6px 12px 16px}
  .top{padding:8px 16px}
}
</style></head>
<body>

<div class="top">
  <div class="top-l"><div class="sdot" id="sd"></div><span class="top-time" id="sT"></span></div>
  <span class="top-ctx" id="sCtx">AI-OS</span>
</div>
<div class="toasts" id="toasts"></div>

<div class="wrap">
  <div class="scroll" id="chat"></div>
  <div class="inp-area">
    <div class="inp-row">
      <input type="text" class="inp-f" id="inp" placeholder="Скажи что-нибудь..." autocomplete="off" onkeydown="if(event.key==='Enter'){event.preventDefault();send()}">
      <button class="ib ib-g" onclick="document.getElementById('fI').click()" title="File">&#128206;</button>
      <input type="file" id="fI" style="display:none" onchange="upFile(this)">
      <button class="ib ib-mic" id="mic" onclick="togMic()" title="Voice">&#127908;</button>
      <button class="ib ib-send" onclick="send()">&#8593;</button>
    </div>
  </div>
</div>

<script>
const C=document.getElementById('chat'),I=document.getElementById('inp');

/* Time */
function uT(){const n=new Date(),h=String(n.getHours()).padStart(2,'0'),m=String(n.getMinutes()).padStart(2,'0'),d=String(n.getDate()).padStart(2,'0'),mo=String(n.getMonth()+1).padStart(2,'0');document.getElementById('sT').textContent=h+':'+m+' | '+d+'.'+mo+'.'+n.getFullYear()}
uT();setInterval(uT,30000);

/* Messages */
function add(c,t='a'){
  const m=document.createElement('div');m.className='m m-'+t;
  const b=document.createElement('div');b.className='b';
  if(t==='a'){const l=document.createElement('div');l.className='m-lbl';l.textContent='AI-OS';m.appendChild(l)}
  if(typeof c==='string')b.innerHTML=c;else b.appendChild(c);
  m.appendChild(b);C.appendChild(m);C.scrollTop=C.scrollHeight;return b;
}
function showTyp(){const m=document.createElement('div');m.className='m m-a';m.id='typ';m.innerHTML='<div class="m-lbl">AI-OS</div><div class="b"><div class="typ-wrap"><div class="typ-dots"><div class="td"></div><div class="td"></div><div class="td"></div></div><span class="typ-txt">Ищу решение...</span></div></div>';C.appendChild(m);C.scrollTop=C.scrollHeight}
function hideTyp(){const t=document.getElementById('typ');if(t)t.remove()}

/* === SMART CARD BUILDERS === */

function gauge(pct,color,label,sub){
  const c=2*Math.PI*38,off=c*(1-pct/100),col=pct>90?'var(--red)':pct>75?'var(--amber)':color;
  return '<div class="ga"><div class="ga-l">'+label+'</div><svg viewBox="0 0 90 90"><circle cx="45" cy="45" r="38" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="7"/><circle cx="45" cy="45" r="38" fill="none" stroke="'+col+'" stroke-width="7" stroke-dasharray="'+c+'" stroke-dashoffset="'+off+'" stroke-linecap="round" transform="rotate(-90 45 45)" style="transition:stroke-dashoffset .8s ease"/><text x="45" y="45" text-anchor="middle" dy=".35em" fill="var(--text)" font-size="18" font-weight="700">'+pct+'%</text></svg><div class="ga-s">'+(sub||'')+'</div></div>';
}

function statsStrip(items){
  let h='<div class="stats">';
  items.forEach(i=>{h+='<div class="st"><div class="st-n '+i.c+'">'+i.v+'</div><div class="st-l">'+i.l+'</div></div>'});
  return h+'</div>';
}

function alert_(lv,msg,fixable){
  const cls=lv==='CRITICAL'?'al-c':lv==='WARNING'?'al-w':'al-ok';
  let btns='';
  if(fixable) btns='<div class="acts"><button class="abtn abtn-d" onclick="quick(\'watchdog.heal\')">Починить одной кнопкой</button><button class="abtn abtn-s" onclick="quick(\'watchdog.check\')">Подробнее</button></div>';
  return '<div class="al '+cls+'"><div class="al-dot"></div><div class="al-txt">'+msg+btns+'</div></div>';
}

function modGrid(){
  const mods=[
    {i:'\u{1F4C2}',n:'Файлы',c:'files.list'},
    {i:'\u2699',n:'Процессы',c:'processes.list top=5'},
    {i:'\u{1F310}',n:'Сеть',c:'network.ping host=google.com'},
    {i:'\u2764',n:'Здоровье',c:'watchdog.check'},
    {i:'\u{1F4BB}',n:'CPU',c:'system.cpu'},
    {i:'\u{1F4BF}',n:'Диски',c:'files.disk_usage'},
    {i:'\u{1F6E1}',n:'Безопасность',c:'scanner.scan'},
    {i:'\u{1F916}',n:'ИИ',c:'report'}
  ];
  let h='<div class="modgrid">';
  mods.forEach(m=>{h+='<div class="modtile" onclick="quick(\''+m.c+'\')"><span class="modtile-i">'+m.i+'</span><span class="modtile-n">'+m.n+'</span></div>'});
  return h+'</div>';
}

/* === DATA RENDERERS === */
function dig(o){if(!o)return o;if(o.result&&typeof o.result==='object'){if(o.result.result!==undefined)return o.result.result;return o.result}return o}

function rOverview(d){
  const cp=d.cpu_percent||0,mp=d.memory_used_percent||0,dp=d.disk_used_percent||0;
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F5A5}</span>System Overview</div>';
  h+='<div class="kv"><span class="kv-k">OS</span><span class="kv-v">'+d.os+' '+d.machine+'</span></div>';
  h+='<div class="kv"><span class="kv-k">Host</span><span class="kv-v">'+d.hostname+'</span></div>';
  h+='<div class="kv"><span class="kv-k">CPU</span><span class="kv-v">'+(d.processor||d.machine)+' ('+d.cpu_cores+' cores)</span></div>';
  h+='<div class="kv"><span class="kv-k">RAM</span><span class="kv-v '+(mp>90?'cr':mp>75?'cw':'cg')+'">'+mp+'% of '+d.memory_total_gb+' GB</span></div>';
  h+='<div class="pb"><div class="pb-f" style="width:'+mp+'%;background:'+(mp>90?'var(--red)':mp>75?'var(--amber)':'var(--green)')+'"></div></div>';
  h+='<div class="kv"><span class="kv-k">Disk</span><span class="kv-v '+(dp>90?'cr':dp>75?'cw':'cc')+'">'+dp+'% of '+d.disk_total_gb+' GB</span></div>';
  h+='<div class="pb"><div class="pb-f" style="width:'+dp+'%;background:'+(dp>90?'var(--red)':dp>75?'var(--amber)':'var(--cyan)')+'"></div></div>';
  h+='</div>';
  // Gauges
  h+='<div class="gauges" style="margin-top:10px">';
  h+=gauge(cp,'var(--green)','CPU',d.cpu_cores+' cores');
  h+=gauge(mp,'var(--accent2)','RAM',d.memory_total_gb+' GB');
  h+=gauge(dp,'var(--cyan)','Disk',d.disk_total_gb+' GB');
  h+='</div>';
  return h;
}

function rCPU(d){
  const load=d.LoadPercentage||0;
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F4BB}</span>CPU</div>';
  h+='<div class="kv"><span class="kv-k">Processor</span><span class="kv-v">'+(d.Name||'Unknown')+'</span></div>';
  h+='<div class="kv"><span class="kv-k">Cores / Threads</span><span class="kv-v">'+(d.NumberOfCores||'?')+' / '+(d.NumberOfLogicalProcessors||'?')+'</span></div>';
  h+='<div class="kv"><span class="kv-k">Load</span><span class="kv-v '+(load>90?'cr':load>60?'cw':'cg')+'">'+load+'%</span></div>';
  h+='<div class="pb"><div class="pb-f" style="width:'+load+'%;background:'+(load>90?'var(--red)':load>60?'var(--amber)':'var(--green)')+'"></div></div>';
  if(d.PerCoreLoad&&d.PerCoreLoad.length){
    h+='<div style="display:flex;gap:4px;margin-top:10px;align-items:flex-end;height:40px">';
    const mx=Math.max(...d.PerCoreLoad,1);
    d.PerCoreLoad.forEach((v,i)=>{
      const pct=Math.max(v,2);
      const col=v>80?'var(--red)':v>50?'var(--amber)':'var(--green)';
      h+='<div style="flex:1;background:'+col+';height:'+pct+'%;border-radius:2px 2px 0 0;min-height:2px" title="Core '+i+': '+v+'%"></div>';
    });
    h+='</div><div style="font-size:10px;color:var(--t3);margin-top:4px">Per-core load</div>';
  }
  h+='</div>';
  return h;
}

function rMem(d){
  const p=d.UsedPercent||0,tot=d.TotalGB?d.TotalGB+' GB':(d.TotalMB||'?')+' MB',fr=d.FreeGB?d.FreeGB+' GB':(d.FreeMB||'?')+' MB';
  const col=p>90?'var(--red)':p>75?'var(--amber)':'var(--accent2)';
  return '<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F4CA}</span>Memory</div><div class="kv"><span class="kv-k">Used</span><span class="kv-v '+(p>90?'cr':p>75?'cw':'ca')+'">'+p+'%</span></div><div class="pb"><div class="pb-f" style="width:'+p+'%;background:'+col+'"></div></div><div class="kv"><span class="kv-k">Total</span><span class="kv-v">'+tot+'</span></div><div class="kv"><span class="kv-k">Free</span><span class="kv-v">'+fr+'</span></div>'+(d.SwapTotalGB?'<div class="kv"><span class="kv-k">Swap</span><span class="kv-v">'+d.SwapUsedPercent+'% of '+d.SwapTotalGB+' GB</span></div>':'')+'</div>';
}

function rDisk(items){
  // Filter out Docker internal mounts
  const real=items.filter(d=>{
    const m=d.drive||d.mountpoint||'';
    return m==='/'||m.startsWith('/home')||m.startsWith('/mnt')||m.startsWith('/media')||/^[A-Z]:/.test(m);
  });
  const show=real.length?real:items.slice(0,2);
  let h='';
  show.forEach(d=>{
    const p=d.percent||d.used_percent||0,col=p>90?'var(--red)':p>75?'var(--amber)':'var(--cyan)';
    h+='<div class="gc" style="margin-top:6px"><div class="gc-title"><span class="gc-icon">\u{1F4BF}</span>'+(d.drive||d.mountpoint||'Disk')+'</div><div class="kv"><span class="kv-k">Used</span><span class="kv-v '+(p>90?'cr':p>75?'cw':'cc')+'">'+p+'%</span></div><div class="pb"><div class="pb-f" style="width:'+p+'%;background:'+col+'"></div></div><div class="kv"><span class="kv-k">Free</span><span class="kv-v">'+(d.free_gb||'?')+' GB</span></div></div>';
  });
  return h;
}

function rHealth(d){
  const alerts=d.alerts||[];
  // Update background
  const s=d.status||'OK';
  updateBg(s);
  if(!alerts.length) return alert_('OK','System OK');
  let h='';alerts.forEach(a=>{h+=alert_(a.level,a.message,a.level==='CRITICAL')});
  return h;
}

function rProc(items){
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u2699</span>Processes</div><table class="ptbl"><tr><th>Name</th><th>PID</th><th>RAM</th><th>CPU</th></tr>';
  (Array.isArray(items)?items:[]).slice(0,8).forEach(p=>{h+='<tr><td>'+p.Name+'</td><td>'+p.Id+'</td><td>'+p.MemMB+' MB</td><td>'+(p.CPU_s||'-')+'s</td></tr>'});
  return h+'</table></div>';
}

function tryCard(d){
  if(!d) return null;
  // System overview (has os + cpu_cores + memory_total_gb)
  if(d.os&&d.cpu_cores&&d.memory_total_gb) return rOverview(d);
  // CPU info (has NumberOfCores + LoadPercentage)
  if(d.NumberOfCores&&d.LoadPercentage!==undefined) return rCPU(d);
  // Memory (has UsedPercent + TotalGB/TotalMB)
  if(d.UsedPercent!==undefined&&(d.TotalGB||d.TotalMB)) return rMem(d);
  // Disk array
  if(Array.isArray(d)&&d[0]&&(d[0].drive||d[0].percent!==undefined||d[0].mountpoint)) return rDisk(d);
  // Health check
  if(d.checks&&d.alerts!==undefined) return rHealth(d);
  // Process list
  if(Array.isArray(d)&&d[0]&&d[0].Name&&d[0].Id) return rProc(d);
  // Network interfaces
  if(Array.isArray(d)&&d[0]&&d[0].interface) return rNet(d);
  // Platform detect
  if(d.current_stack&&d.available_commands) return rPlatform(d);
  return null;
}

function rNet(items){
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F310}</span>Network</div>';
  items.forEach(i=>{h+='<div class="kv"><span class="kv-k">'+(i.interface||i.name)+'</span><span class="kv-v">'+(i.ip||'—')+'</span></div>'});
  return h+'</div>';
}

function rPlatform(d){
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F5A5}</span>Platform</div>';
  h+='<div class="kv"><span class="kv-k">OS</span><span class="kv-v">'+d.os+' '+d.release+'</span></div>';
  h+='<div class="kv"><span class="kv-k">Arch</span><span class="kv-v">'+d.machine+'</span></div>';
  h+='<div class="kv"><span class="kv-k">Stack</span><span class="kv-v">'+d.current_stack+'</span></div>';
  h+='<div class="kv"><span class="kv-k">Python</span><span class="kv-v">'+d.python+'</span></div>';
  if(d.installed_tools){const t=Object.entries(d.installed_tools);if(t.length){h+='<div style="margin-top:8px;font-size:11px;color:var(--t3)">Tools: '+t.map(x=>x[0]).join(', ')+'</div>'}}
  return h+'</div>';
}

function fmtResult(data){
  const el=document.createElement('div');
  if(data.result&&data.result.comment){
    el.innerHTML='<div style="margin-bottom:8px">'+data.result.comment+'</div>';
    if(data.result.results){data.result.results.forEach(r=>{
      const inner=dig(r.result);const card=tryCard(inner);
      if(card) el.innerHTML+=card;
      else if(inner){const c=document.createElement('div');c.className='cblk';c.textContent=typeof inner==='string'?inner:JSON.stringify(inner,null,2);el.appendChild(c)}
    })}
    return el;
  }
  if(data.result&&typeof data.result==='string') return data.result;
  if(data.result){
    const inner=dig(data.result);const card=tryCard(inner);
    if(card){el.innerHTML=card;return el}
    const c=document.createElement('div');c.className='cblk';c.textContent=typeof inner==='string'?inner:JSON.stringify(inner,null,2);el.appendChild(c);return el;
  }
  return JSON.stringify(data,null,2);
}

/* === STATUS === */
let lastSt='OK';
function updateBg(s){
  document.body.style.background=s==='CRITICAL'?'var(--bg-c)':s==='WARNING'?'var(--bg-w)':'var(--bg)';
  const d=document.getElementById('sd');d.className='sdot'+(s==='CRITICAL'?' c':s==='WARNING'?' w':'');
  document.getElementById('sCtx').textContent=s==='OK'?'AI-OS':s==='CRITICAL'?'AI-OS \u2022 CRITICAL':'AI-OS \u2022 Warning';
}

/* === INIT === */
async function init(){
  try{
    const [health,stats,models,kb]=await Promise.all([
      fetch('/api/health').then(r=>r.json()),
      fetch('/api/stats').then(r=>r.json()),
      fetch('/api/models').then(r=>r.json()),
      fetch('/api/knowledge').then(r=>r.json())
    ]);
    const s=health.status||'OK';updateBg(s);lastSt=s;

    const w=document.createElement('div');
    let h='<div style="margin-bottom:14px"><span style="font-size:20px;font-weight:700">AI-OS</span><br><span style="color:var(--t2);font-size:15px">Intelligent Operating System</span></div>';

    // Stats strip
    h+=statsStrip([
      {v:stats.modules.running+'/'+stats.modules.total,l:'Modules',c:'cg'},
      {v:stats.brain.skills,l:'Skills',c:'ca'},
      {v:stats.knowledge.entries,l:'Knowledge',c:'cc'},
      {v:stats.trainer.commands_observed,l:'Commands',c:'cp'}
    ]);

    // Model
    const prov=models.provider==='openrouter'?'OpenRouter':'Anthropic';
    const mod=(models.openrouter_models&&models.openrouter_models.fast)||models.default_model||'—';
    h+='<div class="mbadge">'+prov+' \u2022 '+mod+'</div>';

    // Knowledge summary
    const kbk=Object.keys(kb);
    if(kbk.length){let te=0,ts=0;kbk.forEach(k=>{te+=kb[k].entries||0;ts+=kb[k].solutions||0});
    h+='<div style="margin-top:8px;font-size:13px;color:var(--t3)">'+kbk.length+' knowledge domains \u2022 '+te+' entries \u2022 '+ts+' solutions</div>'}

    // Health
    if(health.alerts&&health.alerts.length){health.alerts.forEach(a=>{h+=alert_(a.level,a.message,a.level==='CRITICAL')})}
    else{h+=alert_('OK','System healthy')}

    // Module grid
    h+=modGrid();

    // Quick chips
    h+='<div class="chips"><span class="chip" onclick="quick(\'как дела у системы?\')">Status</span><span class="chip" onclick="quick(\'покажи процессы\')">Processes</span><span class="chip" onclick="quick(\'что с памятью?\')">Memory</span><span class="chip" onclick="quick(\'сколько места?\')">Disks</span><span class="chip" onclick="quick(\'проверь сеть\')">Network</span></div>';

    w.innerHTML=h;add(w,'a');
  }catch(e){add('Starting up...','a')}
  I.focus();
}

/* === SEND === */
async function send(){
  const t=I.value.trim();if(!t)return;I.value='';add(t,'u');showTyp();
  try{
    const r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:t})});
    const d=await r.json();hideTyp();add(fmtResult(d),'a');
  }catch(e){hideTyp();add('<span style="color:var(--red)">Error: '+e.message+'</span>','a')}
}
function quick(t){I.value=t;send()}

/* === UPLOAD === */
async function upFile(inp){
  if(!inp.files||!inp.files[0])return;const f=inp.files[0];
  add('\u{1F4CE} '+f.name+' ('+Math.round(f.size/1024)+' KB)','u');showTyp();
  const fd=new FormData();fd.append('file',f);
  try{
    const r=await fetch('/api/upload',{method:'POST',body:fd});const d=await r.json();hideTyp();
    let h='<div class="fcard"><div class="fcard-icon">\u{1F4C4}</div><div class="fcard-info"><div class="fcard-name">'+d.filename+'</div><div class="fcard-size">'+Math.round(d.size/1024)+' KB</div></div></div>';
    if(d.ai_response&&typeof d.ai_response==='string') h+='<div style="margin-top:10px">'+d.ai_response+'</div>';
    add(h,'a');
  }catch(e){hideTyp();add('Upload error: '+e.message,'a')}
  inp.value='';
}

/* === HEALTH POLLING === */
setInterval(async()=>{try{
  const h=await fetch('/api/health').then(r=>r.json());const s=h.status||'OK';updateBg(s);
  if(s!==lastSt){
    if(s==='CRITICAL'){toast(h.alerts[0].message,'c',10000);const el=document.createElement('div');el.innerHTML=alert_('CRITICAL',h.alerts[0].message,true);add(el,'a')}
    else if(s==='WARNING'){toast(h.alerts[0].message,'w',8000)}
    else if(lastSt!=='OK'){toast('System recovered','ok',4000)}
    lastSt=s;
  }
}catch(e){}},30000);

/* === TOAST === */
function toast(msg,lv='ok',dur=5000){
  const tc=document.getElementById('toasts'),t=document.createElement('div');
  t.className='toast toast-'+lv;t.innerHTML=msg+'<span style="margin-left:auto;opacity:.5;cursor:pointer" onclick="this.parentElement.remove()">\u2715</span>';
  tc.appendChild(t);setTimeout(()=>{if(t.parentElement){t.style.opacity='0';setTimeout(()=>t.remove(),300)}},dur);
  if('Notification' in window&&Notification.permission==='granted'&&lv!=='ok'){new Notification('AI-OS',{body:msg})}
}
if('Notification' in window&&Notification.permission==='default'){Notification.requestPermission()}

/* === VOICE === */
let rec=null,isR=false;
function togMic(){
  if(!('webkitSpeechRecognition' in window)&&!('SpeechRecognition' in window)){toast('Voice requires Chrome','w');return}
  if(isR){if(rec)rec.stop();document.getElementById('mic').classList.remove('rec');isR=false;return}
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;rec=new SR();rec.lang='ru-RU';rec.interimResults=true;rec.continuous=false;
  document.getElementById('mic').classList.add('rec');isR=true;let fin='';
  rec.onresult=e=>{let tmp='';for(let i=e.resultIndex;i<e.results.length;i++){if(e.results[i].isFinal)fin+=e.results[i][0].transcript;else tmp+=e.results[i][0].transcript}I.value=fin+tmp};
  rec.onend=()=>{document.getElementById('mic').classList.remove('rec');isR=false;if(fin.trim()){I.value=fin.trim();send()}};
  rec.onerror=e=>{document.getElementById('mic').classList.remove('rec');isR=false;if(e.error!=='no-speech')toast('Mic: '+e.error,'w')};
  rec.start();toast('Слушаю...','ok',3000);
}

init();
</script>
</body></html>"""

def _format_result(result):
    """Превратить результат модулей в человеко-читаемый текст"""
    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        # Ответ с comment + results (от ClaudeBrain)
        comment = result.get("comment", "")
        results = result.get("results", [])

        if comment or results:
            parts = []
            if comment:
                parts.append(comment)
            for r in results:
                if isinstance(r, dict):
                    module = r.get("module", r.get("target", ""))
                    command = r.get("command", "")
                    inner = r.get("result", r)

                    if module or command:
                        parts.append(f"\n--- {module}.{command} ---")

                    # Извлечь вложенный result
                    if isinstance(inner, dict):
                        ok = inner.get("ok")
                        data = inner.get("result", inner)
                        if isinstance(data, dict):
                            for k, v in data.items():
                                if k in ("ok", "_score"):
                                    continue
                                if isinstance(v, (dict, list)):
                                    parts.append(f"{k}: {json.dumps(v, ensure_ascii=False, default=str)}")
                                else:
                                    parts.append(f"{k}: {v}")
                        elif isinstance(data, list):
                            for item in data[:15]:
                                if isinstance(item, dict):
                                    line = " | ".join(f"{k}: {v}" for k, v in item.items() if k not in ("ok", "_score"))
                                    parts.append(f"  {line}")
                                else:
                                    parts.append(f"  {item}")
                        elif isinstance(data, str):
                            parts.append(data)
                        else:
                            parts.append(str(data))
                    elif isinstance(inner, str):
                        parts.append(inner)
                    else:
                        parts.append(str(inner))
                elif isinstance(r, str):
                    parts.append(r)

            return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False, indent=2, default=str)

        # Простой dict без comment/results
        parts = []
        for k, v in result.items():
            if isinstance(v, (dict, list)):
                parts.append(f"{k}: {json.dumps(v, ensure_ascii=False, default=str)}")
            else:
                parts.append(f"{k}: {v}")
        return "\n".join(parts)

    if isinstance(result, list):
        parts = []
        for item in result[:20]:
            if isinstance(item, dict):
                line = " | ".join(f"{k}: {v}" for k, v in item.items())
                parts.append(line)
            else:
                parts.append(str(item))
        return "\n".join(parts)

    return str(result)


# --- WebSocket endpoint ---

@app.websocket("/ws")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    # Send welcome + module status
    modules_info = bus.list_modules()
    module_list = []
    for name, info in modules_info.items():
        icon = "+" if info["status"] == "running" else "-"
        module_list.append(f"[{icon}] {name}: {info['description']}")
    await ws.send_json({
        "type": "system",
        "text": "AI-OS v0.1 — Модульная ИИ-система\n\n" + "\n".join(module_list) + "\n\nГотов к работе."
    })
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                user_input = msg.get("input", "").strip()
            except json.JSONDecodeError:
                user_input = data.strip()
            if not user_input:
                continue
            try:
                result = await brain.process(user_input)
                text = _format_result(result)
                await ws.send_json({"type": "response", "input": user_input, "text": text})
            except Exception as e:
                await ws.send_json({"type": "error", "text": f"Ошибка: {e}"})
    except WebSocketDisconnect:
        pass

# Static files
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
