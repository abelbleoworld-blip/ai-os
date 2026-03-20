# AI-OS Vision v1.0 — Claude as OS Kernel (2026)

## Core Philosophy
Claude = shell + window manager + file manager + notification center + decision engine.
No "Claude app" — the entire OS IS Claude.
User never leaves chat/voice (except games, video editors, 3D).

## Zero UI + Ambient Context
- Screen is almost empty by default (just chat or voice wave)
- Everything appears contextually and disappears in 3-12 seconds
- No permanent panels, docks, launchers
- Context (current task) always visible as thin top bar

## Modules (2026 naming)

| Module | Claude calls it | What it does |
|--------|----------------|-------------|
| files | "My stuff" | Files, search, tags, cloud, sync |
| processes | "What's running" | Launch, close, priority, energy |
| system | "Machine health" | Temp, battery, updates, diagnostics, backup |
| network | "Connection" | Wi-Fi, VPN, speed, blockers, tunnels |
| scanner | "Storage scan" | Disk scan, duplicates, cleanup, big files |
| apps | "Programs" | Install, update, web apps, PWA |
| knowledge | "My memory" | Personal KB, notes, vector search, RAG |
| privacy | "My shield" | Permissions, trackers, encryption, audit |
| automation | "My rules" | Triggers, scenarios, IFTTT in natural language |

## Three Screen Modes (auto-switch)

| Mode | When | What user sees |
|------|------|---------------|
| Clean chat | Default, after boot, idle | Just chat + thin top bar |
| Ambient overlay | Task/notification/card response | Chat + 1-2 large cards + voice wave, rest blurred. Disappears 6-12s |
| Full immersion | Video, game, presentation | Full screen content + translucent voice panel + micro-chat |

## 2026 Features
- Context chain: Claude remembers 7-14 days of conversations
- Wake-word free: always listening locally, activates on pause + keyword
- Multi-endpoint: one Claude controls laptop + phone + tablet + server
- Offline-first: 80-90% commands work without internet (~70-120B local model)
- Visual grounding: Claude sees screen, can say "close that window"

## Visual Style
- Background: charcoal-black (#0A0A0E → #111114 gradient)
- Accents: soft electric violet / cyan / warm amber (not neon)
- Cards: glassmorphism 2.0 + subtle edge glow
- Text: SF Pro Display / Inter, 18-22px, letter-spacing +0.5-1px
- Animations: max 220ms, easing cubic-bezier(0.16, 1, 0.3, 1)

## Example Conversations (2026 style)
- "Claude, turn off Wi-Fi every night at 23:00 and enable sleep mode"
- "Show where I'm spending the most battery this week"
- "Collect all my screenshots with flight prices from the last 3 months into one folder"
- "Backup phone photos to external drive and encrypt with my password"
- "I'm on a plane — disable all notifications except messages from my wife"

## Current State (v0.2.0) vs Vision (v1.0)

| Feature | v0.2.0 (now) | v1.0 (target) |
|---------|-------------|---------------|
| Modules | 18 | 9 (consolidated, smarter) |
| UI | Chat + folders + cards | Zero UI + Ambient |
| Voice | Alice webhook | Always-on local |
| Memory | 7 skills, 85 KB entries | 14-day context chain |
| Devices | 3 mesh nodes | Multi-endpoint seamless |
| Offline | 0% | 80-90% |
| Screen awareness | None | Visual grounding |
