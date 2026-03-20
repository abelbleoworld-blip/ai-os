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
from modules.alice import AliceModule
from modules.yadisk import YaDiskModule

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
alice = AliceModule(bus=bus, brain=brain)
bus.register(alice)
yadisk = YaDiskModule(bus=bus)
bus.register(yadisk)

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

@app.post("/alice/webhook")
async def alice_webhook(data: dict):
    return await alice.handle_webhook(data)

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

/* Module grid */
.modgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}
.modtile{background:rgba(255,255,255,0.05);backdrop-filter:blur(30px);-webkit-backdrop-filter:blur(30px);border:1px solid rgba(255,255,255,0.08);border-radius:var(--rs);padding:16px 10px;text-align:center;cursor:pointer;transition:all .15s}
.modtile:hover{background:rgba(255,255,255,0.09);transform:translateY(-2px)}
.modtile:active{transform:scale(.95)}
.modtile-i{font-size:24px;margin-bottom:6px;display:block}
.modtile-n{font-size:11px;color:var(--t2);font-weight:500}

/* Toolbar button */
.tb-btn{width:40px;height:40px;border-radius:12px;border:1px solid rgba(255,255,255,0.07);background:transparent;color:var(--t3);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:18px;transition:all .15s;flex-shrink:0}
.tb-btn:hover{border-color:var(--accent);color:var(--accent2);background:rgba(99,102,241,0.08)}
.tb-btn.active{border-color:var(--accent);color:var(--accent2);background:rgba(99,102,241,0.12)}

/* Utils panel (bottom drawer) */
.upanel{display:none;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:var(--r);padding:16px;margin-bottom:8px;backdrop-filter:blur(30px);max-height:60vh;overflow-y:auto}
.upanel.open{display:block;animation:mIn .18s ease}
.upanel::-webkit-scrollbar{width:3px}.upanel::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.08);border-radius:3px}

/* Android-style folders */
.ucat{margin-bottom:6px}
.ucat-header{display:flex;align-items:center;gap:8px;padding:10px 12px;cursor:pointer;border-radius:12px;transition:all .15s;user-select:none}
.ucat-header:hover{background:rgba(255,255,255,0.04)}
.ucat-header:active{transform:scale(.98)}
.ucat-icon{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}
.ucat-info{flex:1}
.ucat-name{font-size:13px;font-weight:600}
.ucat-count{font-size:10px;color:var(--t3)}
.ucat-arrow{font-size:12px;color:var(--t3);transition:transform .2s}
.ucat-arrow.open{transform:rotate(90deg)}
.ucat-grid{display:none;grid-template-columns:repeat(4,1fr);gap:6px;padding:8px 4px 12px;animation:mIn .15s ease}
.ucat-grid.open{display:grid}
.utile{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:12px 6px;cursor:pointer;transition:all .15s;text-align:center}
.utile:hover{background:rgba(255,255,255,0.08);border-color:rgba(255,255,255,0.1);transform:translateY(-1px)}
.utile:active{transform:scale(.94)}
.utile-i{font-size:22px;display:block;margin-bottom:4px}
.utile-n{font-size:10px;color:var(--t2);font-weight:500}
.utile-d{display:none}

/* Folder colors */
.folder-files{background:rgba(99,102,241,0.12)}
.folder-terminal{background:rgba(34,197,94,0.12)}
.folder-text{background:rgba(245,158,11,0.12)}
.folder-system{background:rgba(239,68,68,0.12)}
.folder-ai{background:rgba(168,85,247,0.12)}
.folder-design{background:rgba(236,72,153,0.12)}
.folder-tools{background:rgba(6,182,212,0.12)}

/* File browser overlay */
.fbrowser{display:none;position:fixed;top:40px;left:0;right:0;bottom:0;z-index:50;background:var(--bg);flex-direction:column;max-width:740px;margin:0 auto}
.fbrowser.open{display:flex}
.fb-bar{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid rgba(255,255,255,0.06);flex-shrink:0}
.fb-back{width:36px;height:36px;border-radius:10px;border:1px solid rgba(255,255,255,0.07);background:transparent;color:var(--t2);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:16px}
.fb-back:hover{border-color:var(--accent);color:var(--accent2)}
.fb-path{flex:1;font-size:13px;color:var(--t2);font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fb-list{flex:1;overflow-y:auto;padding:8px 16px}
.fb-list::-webkit-scrollbar{width:3px}.fb-list::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.08);border-radius:3px}
.fb-item{display:flex;align-items:center;gap:12px;padding:12px;border-radius:12px;cursor:pointer;transition:all .12s}
.fb-item:hover{background:rgba(255,255,255,0.04)}
.fb-item:active{background:rgba(255,255,255,0.06);transform:scale(.99)}
.fb-icon{font-size:24px;width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;background:rgba(255,255,255,0.04)}
.fb-name{font-size:14px;font-weight:500;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fb-meta{font-size:11px;color:var(--t3);text-align:right;flex-shrink:0}

@media(max-width:600px){.ucat-grid.open{grid-template-columns:repeat(3,1fr)}}

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

/* DaisyDisk-style disk map */
.dmap{background:var(--card);border:1px solid rgba(255,255,255,0.06);border-radius:var(--rs);padding:20px;margin-top:10px}
.dmap-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.dmap-title{font-size:15px;font-weight:700}
.dmap-sub{font-size:12px;color:var(--t3)}
.dmap-ring{width:140px;height:140px;margin:0 auto 16px;position:relative}
.dmap-ring svg{width:100%;height:100%;transform:rotate(-90deg)}
.dmap-ring-center{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center}
.dmap-ring-pct{font-size:28px;font-weight:800;line-height:1}
.dmap-ring-lbl{font-size:10px;color:var(--t3);margin-top:2px}
.dmap-bar{display:flex;height:28px;border-radius:8px;overflow:hidden;margin-bottom:16px;gap:2px}
.dmap-seg{height:100%;min-width:3px;transition:all .3s;position:relative;cursor:pointer;border-radius:4px}
.dmap-seg:hover{opacity:.8;transform:scaleY(1.15)}
.dmap-list{display:grid;gap:6px}
.dmap-item{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;transition:background .15s;cursor:default}
.dmap-item:hover{background:rgba(255,255,255,0.04)}
.dmap-dot{width:10px;height:10px;border-radius:3px;flex-shrink:0}
.dmap-name{flex:1;font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dmap-sz{font-size:12px;color:var(--t2);font-weight:600;flex-shrink:0;min-width:60px;text-align:right}
.dmap-pct{font-size:11px;color:var(--t3);flex-shrink:0;min-width:40px;text-align:right}
.dmap-detail{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);border-radius:10px;padding:12px;margin-top:12px}
.dmap-detail-title{font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;font-weight:600}
.dmap-minibar{height:4px;background:rgba(255,255,255,0.06);border-radius:2px;overflow:hidden;margin-top:4px;margin-bottom:6px}
.dmap-minibar-f{height:100%;border-radius:2px}
.dmap-free{display:flex;align-items:center;justify-content:space-between;padding:10px 0;margin-top:8px;border-top:1px solid rgba(255,255,255,0.05)}
.dmap-free-bar{flex:1;margin:0 14px}

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
.ib-mic{background:linear-gradient(135deg,#6366F1,#06B6D4);color:white;border:none}
.ib-mic:hover{transform:scale(1.05);box-shadow:0 0 16px rgba(99,102,241,0.3)}
.ib-mic.rec{animation:mpulse 1.5s ease infinite;background:linear-gradient(135deg,var(--red),var(--amber))}
@keyframes mpulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.3)}50%{box-shadow:0 0 0 12px rgba(239,68,68,0)}}

/* Floating mic (Alisa-style) */
.fmic{position:fixed;bottom:90px;right:24px;z-index:50;width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#6366F1,#06B6D4);color:white;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:24px;box-shadow:0 4px 24px rgba(99,102,241,0.35);transition:all .2s}
.fmic:hover{transform:scale(1.1);box-shadow:0 6px 32px rgba(99,102,241,0.45)}
.fmic:active{transform:scale(.95)}
.fmic.rec{background:linear-gradient(135deg,var(--red),var(--amber));animation:fmicPulse 1.5s ease infinite}
@keyframes fmicPulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0.4);transform:scale(1)}50%{box-shadow:0 0 0 16px rgba(239,68,68,0);transform:scale(1.05)}}
.fmic-label{position:fixed;bottom:76px;right:88px;z-index:50;background:rgba(0,0,0,0.7);color:var(--text);padding:6px 14px;border-radius:8px;font-size:12px;pointer-events:none;opacity:0;transition:opacity .2s}
.fmic-label.show{opacity:1}

/* Philosophy quote */
.philo{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:var(--rs);padding:16px;margin-top:14px}
.philo-title{font-size:11px;color:var(--t3);margin-bottom:6px}
.philo-text{font-size:14px;color:var(--t2);line-height:1.6;font-style:italic}

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

<!-- FLOATING MIC (Alisa-style) -->
<button class="fmic" id="fmic" onclick="togMic()">&#127908;</button>
<div class="fmic-label" id="fmicLabel">&#127908; Voice</div>

<!-- FILE BROWSER -->
<div class="fbrowser" id="fbrowser">
  <div class="fb-bar">
    <button class="fb-back" onclick="fbBack()">\u2190</button>
    <div class="fb-path" id="fbPath">/</div>
    <button class="fb-back" onclick="fbClose()">\u2715</button>
  </div>
  <div class="fb-list" id="fbList"></div>
</div>

<div class="wrap">
  <div class="scroll" id="chat"></div>
  <div class="inp-area">
    <div class="upanel" id="upanel"></div>
    <div class="inp-row">
      <button class="tb-btn" id="ubtn" onclick="toggleUtils()" title="Utils">&#9776;</button>
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

function utilsPanel(){
  const cats=[
    {name:'Files',icon:'\u{1F4C1}',cls:'folder-files',tools:[
      {i:'\u{1F4C2}',n:'Browse',c:'_browse:/app'},
      {i:'\u{1F332}',n:'Tree',c:'utils.tree path=/app depth=2'},
      {i:'\u{1F50D}',n:'Find',c:'ask:Что ищем? (*.py)|utils.find pattern=$'},
      {i:'\u{1F4CB}',n:'Recent',c:'utils.recent'},
      {i:'\u{1F4CA}',n:'Size',c:'ask:Путь|utils.size path=$'},
      {i:'\u{1F503}',n:'Dupes',c:'utils.duplicates path=/app'},
    ]},
    {name:'Terminal',icon:'\u{1F4BB}',cls:'folder-terminal',tools:[
      {i:'\u2318',n:'Run',c:'ask:Команда|utils.exec command=$'},
      {i:'\u{1F50E}',n:'Which',c:'ask:Программа|utils.which program=$'},
      {i:'\u{1F4DD}',n:'Env',c:'utils.env'},
      {i:'\u{1F6AA}',n:'Ports',c:'utils.ports'},
      {i:'\u{1F310}',n:'IP',c:'utils.ip'},
      {i:'\u2B06',n:'Uptime',c:'utils.uptime'},
    ]},
    {name:'Text',icon:'\u{1F4DD}',cls:'folder-text',tools:[
      {i:'\u{1F50D}',n:'Grep',c:'ask:Текст|utils.grep pattern=$'},
      {i:'\u{1F4C4}',n:'Preview',c:'ask:Файл|utils.preview path=$'},
      {i:'\u{1F522}',n:'Count',c:'ask:Файл|utils.wc path=$'},
      {i:'\u2194',n:'Diff',c:'ask:Файл 1|ask:Файл 2|utils.diff file1=$ file2=$'},
    ]},
    {name:'System',icon:'\u2699',cls:'folder-system',tools:[
      {i:'\u{1F4CA}',n:'Top',c:'utils.top'},
      {i:'\u{1F4BE}',n:'Disk',c:'utils.df'},
      {i:'\u{1F4BF}',n:'DiskMap',c:'utils.diskmap path=/app'},
      {i:'\u{1F9E0}',n:'Overview',c:'system.overview'},
      {i:'\u2764',n:'Health',c:'watchdog.check'},
    ]},
    {name:'AI & Learn',icon:'\u{1F916}',cls:'folder-ai',tools:[
      {i:'\u{1F9E0}',n:'Learner',c:'learner.status'},
      {i:'\u{1F4DA}',n:'Knowledge',c:'ingest.stats'},
      {i:'\u{1F4E5}',n:'Ingest',c:'ask:Путь|ingest.scan path=$'},
      {i:'\u{1F517}',n:'Mesh',c:'mesh.nodes'},
      {i:'\u2B50',n:'Skills',c:'skills'},
      {i:'\u{1F44D}',n:'Good',c:'learner.feedback good'},
      {i:'\u{1F4A1}',n:'Auto',c:'learner.auto_skills'},
      {i:'\u{1F4CB}',n:'Lessons',c:'learner.lessons'},
    ]},
    {name:'Design',icon:'\u{1F3A8}',cls:'folder-design',tools:[
      {i:'\u{1F3A8}',n:'Palette',c:'designer.palette'},
      {i:'\u{1F308}',n:'Colors',c:'designer.colors'},
      {i:'\u{1F4D0}',n:'Layout',c:'ask:Описание|designer.layout description=$'},
      {i:'\u{1F5BC}',n:'Generate',c:'ask:Описание|designer.generate description=$'},
    ]},
    {name:'Tools',icon:'\u{1F504}',cls:'folder-tools',tools:[
      {i:'\u{1F510}',n:'Hash',c:'ask:Файл|utils.hash path=$'},
      {i:'\u{1F4E6}',n:'Base64',c:'ask:Текст|utils.b64encode text=$'},
      {i:'\u{1F4DD}',n:'Notes',c:'utils.notes'},
      {i:'\u270F',n:'New Note',c:'ask:Имя|ask:Текст|utils.note name=$ text=$'},
    ]},
  ];
  let h='';
  cats.forEach((cat,ci)=>{
    const fid='folder_'+ci;
    h+='<div class="ucat">';
    h+='<div class="ucat-header" onclick="togFolder(\''+fid+'\')">';
    h+='<div class="ucat-icon '+cat.cls+'">'+cat.icon+'</div>';
    h+='<div class="ucat-info"><div class="ucat-name">'+cat.name+'</div><div class="ucat-count">'+cat.tools.length+' tools</div></div>';
    h+='<span class="ucat-arrow" id="arr_'+fid+'">\u25B6</span>';
    h+='</div>';
    h+='<div class="ucat-grid" id="'+fid+'">';
    cat.tools.forEach(t=>{
      h+='<div class="utile" onclick="event.stopPropagation();runUtil(\''+t.c.replace(/'/g,"\\'")+'\')">';
      h+='<span class="utile-i">'+t.i+'</span><span class="utile-n">'+t.n+'</span></div>';
    });
    h+='</div></div>';
  });
  return h;
}

function appsPanel(){
  const apps=[
    {name:'Yandex Alice',icon:'\u{1F3A4}',cls:'folder-ai',tools:[
      {i:'\u{1F3A4}',n:'Status',c:'alice.status'},
      {i:'\u{1F4CA}',n:'Stats',c:'alice.stats'},
    ]},
    {name:'Yandex Disk',icon:'\u2601',cls:'folder-tools',tools:[
      {i:'\u2601',n:'Status',c:'yadisk.status'},
      {i:'\u{1F4C1}',n:'Files',c:'yadisk.ls'},
      {i:'\u2B06',n:'Sync KB',c:'yadisk.sync_knowledge'},
      {i:'\u{1F4BE}',n:'Backup',c:'yadisk.backup'},
      {i:'\u{1F504}',n:'Restore',c:'yadisk.restore'},
    ]},
    {name:'Mesh Network',icon:'\u{1F517}',cls:'folder-terminal',tools:[
      {i:'\u{1F5A5}',n:'Nodes',c:'mesh.nodes'},
      {i:'\u{1F4E1}',n:'Status',c:'mesh.status'},
      {i:'\u{1F3D3}',n:'Ping',c:'mesh.ping_nodes'},
    ]},
    {name:'Designer',icon:'\u{1F3A8}',cls:'folder-design',tools:[
      {i:'\u{1F3A8}',n:'Palette',c:'designer.palette'},
      {i:'\u{1F308}',n:'Colors',c:'designer.colors'},
      {i:'\u{1F4D0}',n:'Layout',c:'ask:Describe layout|designer.layout description=$'},
      {i:'\u{1F5BC}',n:'Generate',c:'ask:Describe page|designer.generate description=$'},
    ]},
    {name:'Knowledge',icon:'\u{1F4DA}',cls:'folder-ai',tools:[
      {i:'\u{1F4DA}',n:'Stats',c:'ingest.stats'},
      {i:'\u{1F4E5}',n:'Ingest',c:'ask:Path|ingest.scan path=$'},
      {i:'\u{1F50D}',n:'Search',c:'ask:Query|ingest.search query=$'},
      {i:'\u{1F5D1}',n:'Domains',c:'ingest.domains'},
    ]},
    {name:'Scheduler',icon:'\u23F0',cls:'folder-text',tools:[
      {i:'\u23F0',n:'Tasks',c:'scheduler.list'},
      {i:'\u2795',n:'Add',c:'ask:Task command|ask:Interval (min)|scheduler.add command=$ interval=$'},
    ]},
    {name:'Software',icon:'\u{1F4E6}',cls:'folder-system',tools:[
      {i:'\u{1F4E6}',n:'Installed',c:'software.list'},
      {i:'\u{1F50D}',n:'Search',c:'ask:Package name|software.search name=$'},
      {i:'\u2B07',n:'Install',c:'ask:Package|software.install name=$'},
    ]},
  ];
  let h='';
  apps.forEach((cat,ci)=>{
    const fid='app_'+ci;
    h+='<div class="ucat">';
    h+='<div class="ucat-header" onclick="togFolder(\''+fid+'\')">';
    h+='<div class="ucat-icon '+cat.cls+'">'+cat.icon+'</div>';
    h+='<div class="ucat-info"><div class="ucat-name">'+cat.name+'</div><div class="ucat-count">'+cat.tools.length+' tools</div></div>';
    h+='<span class="ucat-arrow" id="arr_'+fid+'">\u25B6</span>';
    h+='</div>';
    h+='<div class="ucat-grid" id="'+fid+'">';
    cat.tools.forEach(t=>{
      h+='<div class="utile" onclick="event.stopPropagation();runUtil(\''+t.c.replace(/'/g,"\\'")+'\')">';
      h+='<span class="utile-i">'+t.i+'</span><span class="utile-n">'+t.n+'</span></div>';
    });
    h+='</div></div>';
  });
  return h;
}

function togFolder(id){
  const g=document.getElementById(id);
  const a=document.getElementById('arr_'+id);
  g.classList.toggle('open');
  a.classList.toggle('open');
}

function toggleUtils(){
  const p=document.getElementById('upanel');
  const b=document.getElementById('ubtn');
  if(p.classList.contains('open')){p.classList.remove('open');b.classList.remove('active')}
  else{p.classList.add('open');b.classList.add('active')}
}

function runUtil(cmd){
  // Close panels
  document.getElementById('upanel').classList.remove('open');
  const ubtn=document.getElementById('ubtn');if(ubtn)ubtn.classList.remove('active');
  // File browser
  if(cmd.startsWith('_browse:')){fbOpen(cmd.replace('_browse:',''));return}
  // Handle ask: prompts
  if(cmd.startsWith('ask:')){
    const parts=cmd.split('|');
    let finalCmd=parts[parts.length-1];
    for(let i=0;i<parts.length-1;i++){
      const q=parts[i].replace('ask:','');
      const answer=prompt(q);
      if(!answer) return;
      finalCmd=finalCmd.replace('$',answer);
    }
    quick(finalCmd);
  } else {
    quick(cmd);
  }
}

/* === DATA RENDERERS === */
function dig(o){
  if(!o)return o;
  // Unwrap nested {result:{ok:true,result:{...}}} and {timestamp,target,result:{...}}
  let r=o;
  for(let i=0;i<4;i++){
    if(r&&typeof r==='object'&&r.result!==undefined&&typeof r.result==='object'){
      r=r.result;
    } else break;
  }
  return r;
}

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

function rDiskMap(d){
  const pct=d.used_percent||0;
  const circ=2*Math.PI*58;
  const off=circ*(1-pct/100);
  const pctCol=pct>90?'var(--red)':pct>75?'var(--amber)':'var(--accent2)';

  let h='<div class="dmap">';
  h+='<div class="dmap-head"><div><div class="dmap-title">\u{1F4BE} Disk Map</div><div class="dmap-sub">'+d.path+'</div></div><div style="text-align:right"><div style="font-size:13px;color:var(--t2)">'+d.used+' / '+d.total+'</div></div></div>';

  // Ring chart
  h+='<div class="dmap-ring"><svg viewBox="0 0 130 130">';
  h+='<circle cx="65" cy="65" r="58" fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="12"/>';
  // Segments on ring
  let ringOff=0;
  d.folders.forEach(f=>{
    const segLen=circ*(f.percent/100);
    if(segLen>1){
      h+='<circle cx="65" cy="65" r="58" fill="none" stroke="'+f.color+'" stroke-width="12" stroke-dasharray="'+segLen+' '+(circ-segLen)+'" stroke-dashoffset="'+(-(ringOff))+'" stroke-linecap="butt" style="transition:all .5s"/>';
    }
    ringOff+=segLen;
  });
  h+='</svg><div class="dmap-ring-center"><div class="dmap-ring-pct" style="color:'+pctCol+'">'+pct+'%</div><div class="dmap-ring-lbl">used</div></div></div>';

  // Horizontal bar
  h+='<div class="dmap-bar">';
  d.folders.forEach(f=>{
    if(f.percent>0.3) h+='<div class="dmap-seg" style="width:'+Math.max(f.percent,1)+'%;background:'+f.color+'" title="'+f.name+': '+f.size_fmt+' ('+f.percent+'%)"></div>';
  });
  const freeP=100-pct;
  if(freeP>0) h+='<div class="dmap-seg" style="width:'+freeP+'%;background:rgba(255,255,255,0.06)" title="Free: '+d.free+'"></div>';
  h+='</div>';

  // Item list
  h+='<div class="dmap-list">';
  d.folders.forEach(f=>{
    h+='<div class="dmap-item">';
    h+='<div class="dmap-dot" style="background:'+f.color+'"></div>';
    h+='<span class="dmap-name">'+(f.is_dir?'\u{1F4C1} ':'\u{1F4C4} ')+f.name+'</span>';
    h+='<span class="dmap-sz">'+f.size_fmt+'</span>';
    h+='<span class="dmap-pct">'+f.percent+'%</span>';
    h+='</div>';
  });
  h+='</div>';

  // Free space
  h+='<div class="dmap-free"><span style="font-size:12px;color:var(--t3)">\u2B1C Free</span><div class="dmap-free-bar"><div class="dmap-minibar"><div class="dmap-minibar-f" style="width:'+freeP+'%;background:rgba(255,255,255,0.15)"></div></div></div><span style="font-size:13px;font-weight:600;color:var(--green)">'+d.free+'</span></div>';

  // Top folder detail
  if(d.top_children&&d.top_children.length){
    h+='<div class="dmap-detail"><div class="dmap-detail-title">\u{1F4C1} '+d.folders[0].name+' breakdown</div>';
    d.top_children.forEach(c=>{
      const cPct=d.folders[0].size>0?Math.round(c.size/d.folders[0].size*100):0;
      h+='<div style="display:flex;align-items:center;gap:8px;padding:3px 0"><span style="flex:1;font-size:12px;color:var(--t2)">'+c.name+'</span><span style="font-size:12px;font-weight:600">'+c.size_fmt+'</span></div>';
      h+='<div class="dmap-minibar"><div class="dmap-minibar-f" style="width:'+cPct+'%;background:'+d.folders[0].color+'"></div></div>';
    });
    h+='</div>';
  }

  h+='</div>';
  return h;
}

function tryCard(d){
  if(!d) return null;
  // DaisyDisk-style disk map
  if(d._type==='diskmap') return rDiskMap(d);
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
  // File list (from files.list)
  if(Array.isArray(d)&&d[0]&&d[0].name&&d[0].type&&(d[0].type==='file'||d[0].type==='dir')) return rFileList(d);
  // Learner status
  if(d.observations!==undefined&&d.lessons_learned!==undefined) return rLearner(d);
  // Mesh nodes (object with role+status)
  if(!Array.isArray(d)&&Object.values(d)[0]&&Object.values(d)[0].role) return rMesh(d);
  // Ingest stats
  if(d.total_files!==undefined&&d.total_domains!==undefined) return rIngestStats(d);
  // Palette (has base + colors + mode)
  if(d.base&&d.colors&&d.mode) return rPalette(d);
  // Designer colors (has presets or schemes)
  if(d.presets&&d.schemes) return rDesignerColors(d);
  // Platform detect
  if(d.current_stack&&d.available_commands) return rPlatform(d);
  // Utils ls (has path + items array)
  if(d.path&&d.items&&Array.isArray(d.items)) return rFileList(d.items);
  return null;
}

function rNet(items){
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F310}</span>Network</div>';
  items.forEach(i=>{h+='<div class="kv"><span class="kv-k">'+(i.interface||i.name)+'</span><span class="kv-v">'+(i.ip||'—')+'</span></div>'});
  return h+'</div>';
}

function rLearner(d){
  const obs=d.observations||0,les=d.lessons_learned||0,maps=d.mappings||0;
  const fb=d.feedback||{};const sr=d.success_rate||'0%';
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F9E0}</span>Learner</div>';
  h+=statsStrip([{v:obs,l:'Observed',c:'ca'},{v:les,l:'Lessons',c:'cc'},{v:maps,l:'Mappings',c:'cg'},{v:sr,l:'Success',c:'cp'}]);
  if(fb.total){h+='<div style="margin-top:10px;font-size:12px;color:var(--t2)">Feedback: \u{1F44D} '+fb.good+' \u{1F44E} '+fb.bad+'</div>'}
  if(d.auto_skills_created){h+='<div style="font-size:12px;color:var(--green);margin-top:4px">\u2B50 '+d.auto_skills_created+' auto-skills created</div>'}
  if(d.top_patterns&&d.top_patterns.length){
    h+='<div style="margin-top:10px;font-size:11px;color:var(--t3);text-transform:uppercase;font-weight:600">Top patterns</div>';
    d.top_patterns.forEach(p=>{h+='<div class="kv"><span class="kv-k" style="font-size:12px">'+p.pattern+'</span><span class="kv-v" style="font-size:12px">'+p.count+'x</span></div>'});
  }
  return h+'</div>';
}

function rMesh(d){
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F517}</span>Mesh Network</div>';
  const nodes=Object.entries(d);
  nodes.forEach(([name,info])=>{
    const online=info.status==='online';
    const dot=online?'\u{1F7E2}':'\u{1F534}';
    const role=info.role==='hub'?'\u{1F451}':'';
    h+='<div class="kv"><span class="kv-k">'+dot+' '+role+' '+name+'</span><span class="kv-v" style="color:'+(online?'var(--green)':'var(--red)')+'">'+info.status+'</span></div>';
  });
  h+='<div style="margin-top:8px;font-size:12px;color:var(--t3)">'+nodes.length+' nodes in network</div>';
  return h+'</div>';
}

function rFileList(items){
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F4C1}</span>Files</div>';
  items.forEach(f=>{
    const icon=f.type==='dir'?'\u{1F4C1}':'\u{1F4C4}';
    const size=f.size?(' \u2022 '+(f.size>1048576?(f.size/1048576).toFixed(1)+' MB':f.size>1024?(f.size/1024).toFixed(1)+' KB':f.size+' B')):'';
    h+='<div class="kv"><span class="kv-k" style="font-size:13px">'+icon+' '+f.name+'</span><span class="kv-v" style="font-size:12px;color:var(--t3)">'+size+'</span></div>';
  });
  return h+'</div>';
}

function rIngestStats(d){
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F4DA}</span>Knowledge Store</div>';
  h+=statsStrip([{v:d.total_files||0,l:'Files',c:'ca'},{v:d.total_entries||0,l:'Entries',c:'cc'},{v:d.total_domains||0,l:'Domains',c:'cg'},{v:d.queue_size||0,l:'Queue',c:'cp'}]);
  if(d.domains&&Object.keys(d.domains).length){
    h+='<div style="margin-top:10px">';
    Object.entries(d.domains).forEach(([name,count])=>{
      h+='<div class="kv"><span class="kv-k" style="font-size:12px;text-transform:capitalize">'+name+'</span><span class="kv-v" style="font-size:12px">'+count+' entries</span></div>';
    });
    h+='</div>';
  }
  return h+'</div>';
}

function rPalette(d){
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F3A8}</span>Palette \u2014 '+d.mode+'</div>';
  h+='<div style="display:flex;gap:3px;margin:10px 0;height:48px;border-radius:8px;overflow:hidden">';
  (d.colors||[]).forEach(c=>{
    const hex=typeof c==='string'?c:c.hex||c.color||'#888';
    h+='<div style="flex:1;background:'+hex+';position:relative;cursor:pointer" title="'+(c.role||'')+' '+hex+'" onclick="navigator.clipboard.writeText(\''+hex+'\');toast(\'Copied '+hex+'\',\'ok\',2000)"><div style="position:absolute;bottom:2px;left:50%;transform:translateX(-50%);font-size:8px;color:rgba(0,0,0,0.5);font-weight:600;text-shadow:0 0 3px rgba(255,255,255,0.5)">'+hex.slice(0,7)+'</div></div>';
  });
  h+='</div>';
  h+='<div class="kv"><span class="kv-k">Base</span><span class="kv-v"><span style="display:inline-block;width:14px;height:14px;border-radius:4px;background:'+(d.base||'#888')+';vertical-align:middle;margin-right:6px"></span>'+(d.base||'')+'</span></div>';
  h+='<div class="kv"><span class="kv-k">Mode</span><span class="kv-v">'+d.mode+'</span></div>';
  (d.colors||[]).forEach(c=>{
    const hex=typeof c==='string'?c:c.hex||'#888';
    const role=typeof c==='object'?c.role||'':'';
    h+='<div class="kv" style="cursor:pointer" onclick="navigator.clipboard.writeText(\''+hex+'\');toast(\'Copied\',\'ok\',1500)"><span class="kv-k"><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:'+hex+';vertical-align:middle;margin-right:8px"></span>'+role+'</span><span class="kv-v" style="font-family:monospace;font-size:13px">'+hex+'</span></div>';
  });
  return h+'</div>';
}

function rDesignerColors(d){
  let h='<div class="gc"><div class="gc-title"><span class="gc-icon">\u{1F308}</span>Colors & Themes</div>';
  if(d.presets){
    h+='<div style="display:flex;gap:3px;margin:10px 0;height:36px;border-radius:8px;overflow:hidden">';
    Object.entries(d.presets).forEach(([name,hex])=>{
      h+='<div style="flex:1;background:'+hex+';cursor:pointer" title="'+name+': '+hex+'" onclick="navigator.clipboard.writeText(\''+hex+'\');toast(\''+name+': '+hex+'\',\'ok\',2000)"></div>';
    });
    h+='</div>';
    Object.entries(d.presets).forEach(([name,hex])=>{
      h+='<div class="kv" style="cursor:pointer" onclick="navigator.clipboard.writeText(\''+hex+'\')"><span class="kv-k"><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:'+hex+';vertical-align:middle;margin-right:8px"></span>'+name+'</span><span class="kv-v" style="font-family:monospace;font-size:13px">'+hex+'</span></div>';
    });
  }
  if(d.schemes){
    h+='<div style="margin-top:10px;font-size:11px;color:var(--t3);text-transform:uppercase;font-weight:600">Schemes</div>';
    Object.entries(d.schemes).forEach(([name,desc])=>{
      h+='<div class="kv"><span class="kv-k">'+name+'</span><span class="kv-v" style="font-size:12px;color:var(--t2)">'+desc+'</span></div>';
    });
  }
  if(d.themes){
    h+='<div style="margin-top:10px;font-size:11px;color:var(--t3);text-transform:uppercase;font-weight:600">Themes</div>';
    h+='<div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap">';
    d.themes.forEach(t=>{h+='<span class="chip" onclick="quick(\'designer.theme style='+t+'\')">'+t+'</span>'});
    h+='</div>';
  }
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

/* === UNIVERSAL AUTO-RENDERER === */
function autoRender(d){
  // 1. null/undefined
  if(d===null||d===undefined) return '';
  // 2. String — render as text (check if contains useful info)
  if(typeof d==='string'){
    if(d.includes('reachable')||d.includes('OK')||d.includes('healthy')||d.includes('порядке'))
      return '<div class="al al-ok"><div class="al-dot"></div>'+d+'</div>';
    if(d.includes('error')||d.includes('Error')||d.includes('ошибка'))
      return '<div class="al al-c"><div class="al-dot"></div>'+d+'</div>';
    if(d.includes('warning')||d.includes('Warning'))
      return '<div class="al al-w"><div class="al-dot"></div>'+d+'</div>';
    return '<div style="padding:8px 0;line-height:1.6">'+d.replace(/\n/g,'<br>')+'</div>';
  }
  // 3. Number/boolean
  if(typeof d==='number'||typeof d==='boolean')
    return '<span style="font-weight:600;color:var(--accent2)">'+d+'</span>';
  // 4. Array
  if(Array.isArray(d)){
    if(!d.length) return '<div style="color:var(--t3);padding:8px">Empty</div>';
    // Array of objects → auto table
    if(typeof d[0]==='object'&&d[0]!==null){
      const keys=Object.keys(d[0]).filter(k=>!k.startsWith('_'));
      let h='<div class="gc"><table class="ptbl"><tr>';
      keys.slice(0,6).forEach(k=>{h+='<th>'+k+'</th>'});
      h+='</tr>';
      d.slice(0,15).forEach(row=>{
        h+='<tr>';
        keys.slice(0,6).forEach(k=>{
          let v=row[k];
          if(v===null||v===undefined) v='—';
          else if(typeof v==='object') v=JSON.stringify(v);
          else v=String(v);
          if(v.length>40) v=v.slice(0,40)+'...';
          h+='<td>'+v+'</td>';
        });
        h+='</tr>';
      });
      if(d.length>15) h+='<tr><td colspan="'+keys.length+'" style="color:var(--t3);text-align:center">...and '+(d.length-15)+' more</td></tr>';
      return h+'</table></div>';
    }
    // Array of strings/numbers → list
    let h='<div class="gc">';
    d.slice(0,20).forEach(item=>{h+='<div style="padding:4px 0;font-size:13px;color:var(--t2);border-bottom:1px solid rgba(255,255,255,0.03)">'+(typeof item==='object'?JSON.stringify(item):item)+'</div>'});
    return h+'</div>';
  }
  // 5. Object → smart card
  if(typeof d==='object'){
    const keys=Object.keys(d).filter(k=>!k.startsWith('_'));
    if(!keys.length) return '';
    // Detect patterns
    const colors=['var(--accent2)','var(--green)','var(--cyan)','var(--amber)','var(--purple)','var(--red)'];
    let h='<div class="gc">';
    let ci=0;
    keys.forEach(k=>{
      const v=d[k];
      if(v===null||v===undefined) return;
      // Nested object → sub-section
      if(typeof v==='object'&&!Array.isArray(v)){
        h+='<div style="margin-top:10px;font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:.4px;font-weight:600">'+k+'</div>';
        Object.entries(v).forEach(([sk,sv])=>{
          const val=typeof sv==='object'?JSON.stringify(sv):String(sv);
          h+='<div class="kv"><span class="kv-k">'+sk+'</span><span class="kv-v" style="font-size:13px">'+val.slice(0,80)+'</span></div>';
        });
      }
      // Array → compact list
      else if(Array.isArray(v)){
        h+='<div style="margin-top:10px;font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:.4px;font-weight:600">'+k+' ('+v.length+')</div>';
        v.slice(0,5).forEach(item=>{
          h+='<div style="padding:3px 0;font-size:12px;color:var(--t2)">\u2022 '+(typeof item==='object'?JSON.stringify(item):item)+'</div>';
        });
        if(v.length>5) h+='<div style="font-size:11px;color:var(--t3)">...and '+(v.length-5)+' more</div>';
      }
      // Number with % → progress bar
      else if(typeof v==='number'&&(k.toLowerCase().includes('percent')||k.toLowerCase().includes('pct')||k.toLowerCase().includes('rate'))){
        const col=v>90?'var(--red)':v>75?'var(--amber)':colors[ci%colors.length];
        h+='<div class="kv"><span class="kv-k">'+k+'</span><span class="kv-v" style="color:'+col+'">'+v+'%</span></div>';
        h+='<div class="pb"><div class="pb-f" style="width:'+Math.min(v,100)+'%;background:'+col+'"></div></div>';
      }
      // Number → colored value
      else if(typeof v==='number'){
        h+='<div class="kv"><span class="kv-k">'+k+'</span><span class="kv-v" style="color:'+colors[ci%colors.length]+'">'+v+'</span></div>';
      }
      // Boolean → green/red dot
      else if(typeof v==='boolean'){
        h+='<div class="kv"><span class="kv-k">'+k+'</span><span class="kv-v">'+(v?'\u{1F7E2} Yes':'\u{1F534} No')+'</span></div>';
      }
      // String → key-value
      else {
        const sv=String(v);
        if(sv.length>100){
          h+='<div style="margin-top:8px;font-size:11px;color:var(--t3);text-transform:uppercase;font-weight:600">'+k+'</div>';
          h+='<div style="font-size:13px;color:var(--t2);padding:4px 0;line-height:1.5">'+sv.slice(0,300)+(sv.length>300?'...':'')+'</div>';
        } else {
          h+='<div class="kv"><span class="kv-k">'+k+'</span><span class="kv-v" style="font-size:13px">'+sv+'</span></div>';
        }
      }
      ci++;
    });
    return h+'</div>';
  }
  return String(d);
}

function fmtResult(data){
  const el=document.createElement('div');
  if(data.result&&data.result.comment){
    el.innerHTML='<div style="margin-bottom:8px">'+data.result.comment+'</div>';
    if(data.result.results){data.result.results.forEach(r=>{
      const inner=dig(r.result);const card=tryCard(inner);
      if(card) el.innerHTML+=card;
      else el.innerHTML+=autoRender(inner);
    })}
    return el;
  }
  if(data.result&&typeof data.result==='string') return data.result;
  if(data.result){
    const inner=dig(data.result);const card=tryCard(inner);
    if(card){el.innerHTML=card;return el}
    el.innerHTML=autoRender(inner);return el;
  }
  el.innerHTML=autoRender(data);return el;
}

/* === STATUS === */
let lastSt='OK';
function updateBg(s){
  document.body.style.background=s==='CRITICAL'?'var(--bg-c)':s==='WARNING'?'var(--bg-w)':'var(--bg)';
  const d=document.getElementById('sd');d.className='sdot'+(s==='CRITICAL'?' c':s==='WARNING'?' w':'');
  document.getElementById('sCtx').textContent=s==='OK'?'AI-OS':s==='CRITICAL'?'AI-OS \u2022 CRITICAL':'AI-OS \u2022 Warning';
}

/* === FILE BROWSER === */
let fbHistory=['/app'];
const fileIcons={dir:'\u{1F4C1}',py:'\u{1F40D}',js:'\u2B50',ts:'\u{1F535}',json:'\u{1F4CB}',md:'\u{1F4D6}',txt:'\u{1F4C4}',log:'\u{1F4DC}',sh:'\u{1F4DF}',yml:'\u2699',yaml:'\u2699',html:'\u{1F310}',css:'\u{1F3A8}',csv:'\u{1F4CA}',default:'\u{1F4C4}'};
function getFileIcon(name,isDir){
  if(isDir) return fileIcons.dir;
  const ext=name.split('.').pop().toLowerCase();
  return fileIcons[ext]||fileIcons.default;
}
function fmtBytes(b){
  if(!b||b===null) return '';
  if(b>1048576) return (b/1048576).toFixed(1)+' MB';
  if(b>1024) return (b/1024).toFixed(1)+' KB';
  return b+' B';
}
async function fbOpen(path){
  document.getElementById('fbrowser').classList.add('open');
  fbHistory=[path];
  await fbLoad(path);
}
function fbClose(){document.getElementById('fbrowser').classList.remove('open')}
function fbBack(){
  if(fbHistory.length>1){fbHistory.pop();fbLoad(fbHistory[fbHistory.length-1])}
  else fbClose();
}
async function fbLoad(path){
  document.getElementById('fbPath').textContent=path;
  const list=document.getElementById('fbList');
  list.innerHTML='<div style="padding:20px;text-align:center;color:var(--t3)">Loading...</div>';
  try{
    const r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:'utils.ls path='+path+' hidden=false'})});
    const d=await r.json();
    let items=dig(d.result);
    if(items&&items.items) items=items.items;
    if(!Array.isArray(items)){list.innerHTML='<div style="padding:20px;color:var(--t3)">Empty</div>';return}
    // Sort: dirs first, then files
    items.sort((a,b)=>{if(a.type==='dir'&&b.type!=='dir')return -1;if(a.type!=='dir'&&b.type==='dir')return 1;return a.name.localeCompare(b.name)});
    let h='';
    items.forEach(f=>{
      const icon=getFileIcon(f.name,f.type==='dir');
      const sz=f.type==='dir'?'':f.size;
      const mod=f.modified||'';
      if(f.type==='dir'){
        h+='<div class="fb-item" onclick="fbNav(\''+path+'/'+f.name+'\')">';
      } else {
        h+='<div class="fb-item" onclick="fbPreview(\''+path+'/'+f.name+'\')">';
      }
      h+='<div class="fb-icon">'+icon+'</div>';
      h+='<div class="fb-name">'+f.name+'</div>';
      h+='<div class="fb-meta">'+(typeof sz==='string'?sz:fmtBytes(sz))+'<br>'+mod+'</div>';
      h+='</div>';
    });
    list.innerHTML=h||'<div style="padding:20px;color:var(--t3)">Empty folder</div>';
  }catch(e){list.innerHTML='<div style="padding:20px;color:var(--red)">Error: '+e.message+'</div>'}
}
function fbNav(path){
  path=path.replace(/\/\//g,'/');
  fbHistory.push(path);
  fbLoad(path);
}
function fbPreview(path){
  fbClose();
  quick('utils.preview path='+path+' lines=30');
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

    // Utilities + Apps folders
    h+='<div style="margin-top:14px;font-size:12px;color:var(--t3);text-transform:uppercase;letter-spacing:.5px;font-weight:600;margin-bottom:8px">\u{1F9F0} Utilities</div>';
    h+=utilsPanel();

    h+='<div style="margin-top:14px;font-size:12px;color:var(--t3);text-transform:uppercase;letter-spacing:.5px;font-weight:600;margin-bottom:8px">\u{1F4E6} Apps</div>';
    h+=appsPanel();

    // Quick chips
    h+='<div class="chips" style="margin-top:14px"><span class="chip" onclick="quick(\'проверь систему\')">System</span><span class="chip" onclick="quick(\'покажи процессы\')">Processes</span><span class="chip" onclick="quick(\'что с памятью?\')">Memory</span><span class="chip" onclick="quick(\'сколько места?\')">Disks</span><span class="chip" onclick="quick(\'mesh.nodes\')">Mesh</span></div>';

    // Philosophy
    h+='<div class="philo"><div class="philo-title">Philosophy</div><div class="philo-text">AI-OS \u2014 \u044d\u0442\u043e \u043d\u0435 \u0438\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441, \u044d\u0442\u043e \u043f\u0440\u043e\u0441\u0442\u043e \u0440\u0430\u0437\u0433\u043e\u0432\u043e\u0440. \u0422\u044b \u0433\u043e\u0432\u043e\u0440\u0438\u0448\u044c \u2014 \u0441\u0438\u0441\u0442\u0435\u043c\u0430 \u0434\u0435\u043b\u0430\u0435\u0442. \u0412\u0441\u0451 \u043e\u0441\u0442\u0430\u043b\u044c\u043d\u043e\u0435 \u043f\u0440\u043e\u0438\u0441\u0445\u043e\u0434\u0438\u0442 \u0441\u0430\u043c\u043e.</div></div>';

    w.innerHTML=h;add(w,'a');
    // Also populate the input-area panel
    document.getElementById('upanel').innerHTML=utilsPanel();
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
  const fm=document.getElementById('fmic'),mb=document.getElementById('mic'),fl=document.getElementById('fmicLabel');
  if(isR){if(rec)rec.stop();if(fm)fm.classList.remove('rec');if(mb)mb.classList.remove('rec');if(fl)fl.classList.remove('show');isR=false;return}
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;rec=new SR();rec.lang='ru-RU';rec.interimResults=true;rec.continuous=false;
  if(fm)fm.classList.add('rec');if(mb)mb.classList.add('rec');isR=true;let fin='';
  if(fl){fl.textContent='\u{1F3A4} Listening...';fl.classList.add('show')}
  rec.onresult=e=>{let tmp='';for(let i=e.resultIndex;i<e.results.length;i++){if(e.results[i].isFinal)fin+=e.results[i][0].transcript;else tmp+=e.results[i][0].transcript}I.value=fin+tmp;if(fl)fl.textContent='\u{1F3A4} '+(fin+tmp).slice(0,30)};
  rec.onend=()=>{if(fm)fm.classList.remove('rec');if(mb)mb.classList.remove('rec');if(fl)fl.classList.remove('show');isR=false;if(fin.trim()){I.value=fin.trim();send()}};
  rec.onerror=e=>{if(fm)fm.classList.remove('rec');if(mb)mb.classList.remove('rec');if(fl)fl.classList.remove('show');isR=false;if(e.error!=='no-speech')toast('Mic: '+e.error,'w')};
  rec.start();toast('\u{1F3A4} Listening...','ok',3000);
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
