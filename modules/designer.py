"""
Модуль: Дизайнер
Генерация UI-элементов, цветовых схем, макетов, иконок.
Как штатный дизайнер системы — умеет создавать интерфейсы.

Возможности:
- Генерация цветовых палитр
- Создание HTML/CSS макетов
- Генерация SVG иконок
- Адаптивные сетки
- Темы оформления
"""

import json
import math
import hashlib
from pathlib import Path
from core.module_base import SystemModule


class DesignerModule(SystemModule):
    def __init__(self):
        super().__init__("designer", "Дизайн интерфейсов, палитры, макеты")
        self.register_command("palette", self.cmd_palette, "Сгенерировать цветовую палитру")
        self.register_command("theme", self.cmd_theme, "Создать тему оформления (dark/light/custom)")
        self.register_command("layout", self.cmd_layout, "Сгенерировать HTML макет")
        self.register_command("icon", self.cmd_icon, "Создать SVG иконку")
        self.register_command("component", self.cmd_component, "Сгенерировать UI-компонент")
        self.register_command("page", self.cmd_page, "Сгенерировать полную HTML страницу")
        self.register_command("colors", self.cmd_colors, "Показать доступные цветовые схемы")
        self.register_command("export", self.cmd_export, "Экспортировать дизайн в файл")

    def _hsl_to_hex(self, h, s, l):
        """HSL → HEX"""
        s /= 100
        l /= 100
        c = (1 - abs(2 * l - 1)) * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = l - c / 2
        if h < 60: r, g, b = c, x, 0
        elif h < 120: r, g, b = x, c, 0
        elif h < 180: r, g, b = 0, c, x
        elif h < 240: r, g, b = 0, x, c
        elif h < 300: r, g, b = x, 0, c
        else: r, g, b = c, 0, x
        r, g, b = int((r+m)*255), int((g+m)*255), int((b+m)*255)
        return f"#{r:02x}{g:02x}{b:02x}"

    async def cmd_palette(self, base="#3b82f6", mode="complementary", count=6):
        """Генерация палитры из базового цвета"""
        # Парсим HEX
        base = base.lstrip("#")
        r, g, b = int(base[0:2],16), int(base[2:4],16), int(base[4:6],16)

        # RGB → HSL
        r1, g1, b1 = r/255, g/255, b/255
        mx, mn = max(r1,g1,b1), min(r1,g1,b1)
        l = (mx+mn)/2
        if mx == mn:
            h = s = 0
        else:
            d = mx - mn
            s = d/(2-mx-mn) if l > 0.5 else d/(mx+mn)
            if mx == r1: h = ((g1-b1)/d + (6 if g1<b1 else 0)) * 60
            elif mx == g1: h = ((b1-r1)/d + 2) * 60
            else: h = ((r1-g1)/d + 4) * 60

        count = int(count)
        colors = []

        if mode == "complementary":
            for i in range(count):
                hue = (h + (360/count) * i) % 360
                colors.append({
                    "hex": self._hsl_to_hex(hue, s*100, l*100),
                    "role": ["primary", "secondary", "accent", "info", "success", "warning"][i % 6]
                })
        elif mode == "monochrome":
            for i in range(count):
                lightness = 20 + (60 / max(count-1, 1)) * i
                colors.append({
                    "hex": self._hsl_to_hex(h, s*100, lightness),
                    "role": f"shade-{i+1}"
                })
        elif mode == "analogous":
            for i in range(count):
                hue = (h - 30 + (60 / max(count-1, 1)) * i) % 360
                colors.append({
                    "hex": self._hsl_to_hex(hue, s*100, l*100),
                    "role": f"analog-{i+1}"
                })

        return {
            "base": f"#{base}",
            "mode": mode,
            "colors": colors
        }

    async def cmd_theme(self, style="dark"):
        """Готовая тема оформления"""
        themes = {
            "dark": {
                "name": "Dark",
                "bg": "#0a0e17", "bg_secondary": "#111827", "bg_card": "#1e293b",
                "text": "#e0e6f0", "text_secondary": "#94a3b8", "text_muted": "#475569",
                "primary": "#3b82f6", "primary_hover": "#2563eb",
                "success": "#22c55e", "warning": "#eab308", "danger": "#ef4444",
                "border": "#2a3555", "border_hover": "#3b82f6",
                "shadow": "0 4px 24px rgba(0,0,0,0.4)"
            },
            "light": {
                "name": "Light",
                "bg": "#f8fafc", "bg_secondary": "#ffffff", "bg_card": "#ffffff",
                "text": "#1e293b", "text_secondary": "#64748b", "text_muted": "#94a3b8",
                "primary": "#2563eb", "primary_hover": "#1d4ed8",
                "success": "#16a34a", "warning": "#ca8a04", "danger": "#dc2626",
                "border": "#e2e8f0", "border_hover": "#2563eb",
                "shadow": "0 4px 24px rgba(0,0,0,0.08)"
            },
            "cyberpunk": {
                "name": "Cyberpunk",
                "bg": "#0d0221", "bg_secondary": "#150535", "bg_card": "#1a0a3e",
                "text": "#f0e6ff", "text_secondary": "#c4b5fd", "text_muted": "#7c3aed",
                "primary": "#f472b6", "primary_hover": "#ec4899",
                "success": "#34d399", "warning": "#fbbf24", "danger": "#f87171",
                "border": "#4c1d95", "border_hover": "#f472b6",
                "shadow": "0 4px 24px rgba(244,114,182,0.2)"
            },
            "ocean": {
                "name": "Ocean",
                "bg": "#0c1929", "bg_secondary": "#122340", "bg_card": "#1a3050",
                "text": "#e0f2fe", "text_secondary": "#7dd3fc", "text_muted": "#38bdf8",
                "primary": "#0ea5e9", "primary_hover": "#0284c7",
                "success": "#2dd4bf", "warning": "#fbbf24", "danger": "#f43f5e",
                "border": "#1e4976", "border_hover": "#0ea5e9",
                "shadow": "0 4px 24px rgba(14,165,233,0.15)"
            }
        }

        theme = themes.get(style, themes["dark"])

        # Генерируем CSS переменные
        css = ":root {\n"
        for key, value in theme.items():
            if key != "name":
                css += f"  --{key.replace('_', '-')}: {value};\n"
        css += "}\n"

        return {
            "theme": theme,
            "css_variables": css,
            "available_themes": list(themes.keys())
        }

    async def cmd_icon(self, name="circle", size=24, color="#3b82f6"):
        """Генерация SVG иконок"""
        size = int(size)
        icons = {
            "circle": f'<circle cx="{size//2}" cy="{size//2}" r="{size//2-2}" fill="none" stroke="{color}" stroke-width="2"/>',
            "check": f'<polyline points="{size*0.2},{size*0.5} {size*0.45},{size*0.75} {size*0.8},{size*0.25}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>',
            "x": f'<line x1="{size*0.2}" y1="{size*0.2}" x2="{size*0.8}" y2="{size*0.8}" stroke="{color}" stroke-width="2" stroke-linecap="round"/><line x1="{size*0.8}" y1="{size*0.2}" x2="{size*0.2}" y2="{size*0.8}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>',
            "arrow": f'<line x1="{size*0.2}" y1="{size*0.5}" x2="{size*0.8}" y2="{size*0.5}" stroke="{color}" stroke-width="2" stroke-linecap="round"/><polyline points="{size*0.6},{size*0.3} {size*0.8},{size*0.5} {size*0.6},{size*0.7}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>',
            "star": f'<polygon points="{size//2},{size*0.1} {size*0.62},{size*0.38} {size*0.95},{size*0.38} {size*0.68},{size*0.58} {size*0.79},{size*0.9} {size//2},{size*0.7} {size*0.21},{size*0.9} {size*0.32},{size*0.58} {size*0.05},{size*0.38} {size*0.38},{size*0.38}" fill="{color}"/>',
            "heart": f'<path d="M{size//2} {size*0.85} C{size*0.1} {size*0.55} {size*0.05} {size*0.2} {size*0.3} {size*0.15} C{size*0.42} {size*0.12} {size//2} {size*0.25} {size//2} {size*0.25} C{size//2} {size*0.25} {size*0.58} {size*0.12} {size*0.7} {size*0.15} C{size*0.95} {size*0.2} {size*0.9} {size*0.55} {size//2} {size*0.85}Z" fill="{color}"/>',
            "gear": f'<circle cx="{size//2}" cy="{size//2}" r="{size*0.2}" fill="none" stroke="{color}" stroke-width="2"/><circle cx="{size//2}" cy="{size//2}" r="{size*0.38}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="4 3"/>',
            "home": f'<path d="M{size*0.15} {size*0.5} L{size//2} {size*0.15} L{size*0.85} {size*0.5}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/><rect x="{size*0.25}" y="{size*0.45}" width="{size*0.5}" height="{size*0.4}" fill="none" stroke="{color}" stroke-width="2"/>',
            "module": f'<rect x="{size*0.1}" y="{size*0.1}" width="{size*0.35}" height="{size*0.35}" rx="2" fill="{color}" opacity="0.8"/><rect x="{size*0.55}" y="{size*0.1}" width="{size*0.35}" height="{size*0.35}" rx="2" fill="{color}" opacity="0.6"/><rect x="{size*0.1}" y="{size*0.55}" width="{size*0.35}" height="{size*0.35}" rx="2" fill="{color}" opacity="0.6"/><rect x="{size*0.55}" y="{size*0.55}" width="{size*0.35}" height="{size*0.35}" rx="2" fill="{color}" opacity="0.4"/>',
        }

        icon_inner = icons.get(name, icons["circle"])
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">{icon_inner}</svg>'

        return {
            "name": name,
            "svg": svg,
            "available_icons": list(icons.keys())
        }

    async def cmd_component(self, type="button", variant="primary"):
        """Генерация HTML/CSS компонента"""
        components = {
            "button": {
                "html": f'<button class="btn btn-{variant}">Click me</button>',
                "css": f""".btn {{
    padding: 10px 24px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
}}
.btn-primary {{ background: #3b82f6; color: white; }}
.btn-primary:hover {{ background: #2563eb; transform: translateY(-1px); }}
.btn-secondary {{ background: #1e293b; color: #e0e6f0; border: 1px solid #2a3555; }}
.btn-danger {{ background: #ef4444; color: white; }}"""
            },
            "card": {
                "html": """<div class="card">
    <h3 class="card-title">Title</h3>
    <p class="card-text">Content goes here</p>
    <div class="card-actions">
        <button class="btn btn-primary">Action</button>
    </div>
</div>""",
                "css": """.card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 20px;
    transition: border-color 0.2s;
}
.card:hover { border-color: #3b82f6; }
.card-title { font-size: 18px; margin-bottom: 12px; }
.card-text { color: #94a3b8; margin-bottom: 16px; }"""
            },
            "input": {
                "html": """<div class="input-group">
    <label class="input-label">Label</label>
    <input type="text" class="input" placeholder="Enter value...">
</div>""",
                "css": """.input-group { margin-bottom: 16px; }
.input-label { display: block; margin-bottom: 6px; color: #94a3b8; font-size: 14px; }
.input {
    width: 100%;
    padding: 10px 14px;
    background: #0f172a;
    border: 1px solid #2a3555;
    border-radius: 8px;
    color: #e0e6f0;
    font-size: 14px;
    outline: none;
}
.input:focus { border-color: #3b82f6; }"""
            },
            "alert": {
                "html": f'<div class="alert alert-{variant}">Alert message here</div>',
                "css": """.alert {
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    margin-bottom: 12px;
}
.alert-success { background: #052e16; border: 1px solid #065f46; color: #6ee7b7; }
.alert-warning { background: #422006; border: 1px solid #78350f; color: #fcd34d; }
.alert-danger { background: #450a0a; border: 1px solid #7f1d1d; color: #fca5a5; }
.alert-info { background: #0c1929; border: 1px solid #1e4976; color: #7dd3fc; }"""
            },
            "navbar": {
                "html": """<nav class="navbar">
    <div class="nav-brand">AI-OS</div>
    <div class="nav-links">
        <a href="#" class="nav-link active">Dashboard</a>
        <a href="#" class="nav-link">Modules</a>
        <a href="#" class="nav-link">Settings</a>
    </div>
</nav>""",
                "css": """.navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    background: #111827;
    border-bottom: 1px solid #1e293b;
}
.nav-brand { font-size: 20px; font-weight: 600; color: #3b82f6; }
.nav-links { display: flex; gap: 20px; }
.nav-link { color: #94a3b8; text-decoration: none; }
.nav-link.active { color: #3b82f6; }
.nav-link:hover { color: #e0e6f0; }"""
            }
        }

        comp = components.get(type, components["button"])
        return {
            "type": type,
            "variant": variant,
            **comp,
            "available_types": list(components.keys())
        }

    async def cmd_layout(self, columns=3, rows=2):
        """Генерация CSS Grid макета"""
        columns = int(columns)
        rows = int(rows)
        cells = columns * rows

        html = f'<div class="grid-layout">\n'
        for i in range(cells):
            html += f'    <div class="grid-cell">Block {i+1}</div>\n'
        html += '</div>'

        css = f""".grid-layout {{
    display: grid;
    grid-template-columns: repeat({columns}, 1fr);
    gap: 16px;
    padding: 20px;
}}
.grid-cell {{
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 20px;
    min-height: 120px;
}}
/* Адаптивность — на мобильных в 1 колонку */
@media (max-width: 768px) {{
    .grid-layout {{ grid-template-columns: 1fr; }}
}}"""

        return {
            "columns": columns,
            "rows": rows,
            "html": html,
            "css": css
        }

    async def cmd_page(self, title="AI-OS Page", theme="dark"):
        """Полная HTML страница"""
        theme_data = await self.cmd_theme(style=theme)
        css_vars = theme_data["css_variables"]

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css_vars}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
</style>
</head>
<body>
<div class="container">
    <h1>{title}</h1>
</div>
</body>
</html>"""

        return {
            "title": title,
            "theme": theme,
            "html": html,
            "size_bytes": len(html.encode())
        }

    async def cmd_colors(self):
        """Доступные цветовые схемы"""
        return {
            "schemes": {
                "complementary": "Противоположные цвета на цветовом круге (контраст)",
                "monochrome": "Оттенки одного цвета (спокойствие)",
                "analogous": "Соседние цвета (гармония)"
            },
            "presets": {
                "ocean": "#0ea5e9",
                "forest": "#22c55e",
                "sunset": "#f97316",
                "lavender": "#a78bfa",
                "rose": "#f43f5e",
                "gold": "#eab308",
                "cyber": "#f472b6"
            },
            "themes": ["dark", "light", "cyberpunk", "ocean"]
        }

    async def cmd_export(self, content="", path="", format="html"):
        """Экспорт дизайна в файл"""
        if not path:
            export_dir = Path(__file__).parent.parent / "exports"
            export_dir.mkdir(exist_ok=True)
            path = str(export_dir / f"design.{format}")

        Path(path).write_text(content, encoding="utf-8")
        return f"Экспортировано в {path} ({len(content)} байт)"
