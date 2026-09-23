"""Look & feel for the StatusForge dashboard: CSS, inline icons, and the hero backdrop."""
from __future__ import annotations

from urllib.parse import quote

DET, LLM, IO = "#2FBF9F", "#F0705A", "#7B93FF"
CORAL, GREEN, AMBER, RED, VIOLET = "#F0705A", "#2FBF9F", "#F5B942", "#F0524A", "#A78BFA"

# Feather-style icons (MIT) — stroke = currentColor, so a parent's color tints them.
_ICON_PATHS = {
    "logo": '<path d="M4 20l9-9"/><path d="M20 20l-9-9"/><path d="M10.5 3.5l4 4-3 3-4-4z"/><path d="M13.5 3.5l-4 4 3 3 4-4z"/>',
    "overview": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>'
                '<rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
    "workflow": '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>'
                '<line x1="8.6" y1="13.5" x2="15.4" y2="17.5"/><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"/>',
    "graph": '<line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>'
             '<path d="M18 9a9 9 0 0 1-9 9"/>',
    "data": '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/>'
            '<line x1="9" y1="21" x2="9" y2="9"/>',
    "inspect": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "docs": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "alert": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="12"/>'
             '<line x1="12" y1="16" x2="12.01" y2="16"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>'
                '<path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    "warning": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
               '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "ban": '<circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "mail": '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>'
            '<polyline points="22,6 12,13 2,6"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>'
            '<line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "external": '<path d="M7 17L17 7"/><polyline points="7 7 17 7 17 17"/>',
    "arch": '<polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/>'
            '<line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/>',
}


def icon(name: str, size: int = 20, stroke: float = 1.8) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{_ICON_PATHS[name]}</svg>')


SLACK_MARK = (
    '<svg width="18" height="18" viewBox="0 0 24 24">'
    '<rect x="9" y="2" width="4" height="9" rx="2" fill="#36C5F0"/><rect x="2" y="11" width="9" height="4" rx="2" fill="#2EB67D"/>'
    '<rect x="11" y="13" width="4" height="9" rx="2" fill="#ECB22E"/><rect x="13" y="9" width="9" height="4" rx="2" fill="#E01E5A"/>'
    '</svg>'
)

# Layered ridgelines at dusk — the hero's right-hand backdrop, drawn in SVG (no image assets).
_MOUNTAINS = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 460' preserveAspectRatio='xMaxYMid slice'>
<defs>
<linearGradient id='sky' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#3a2a4a'/><stop offset='.55' stop-color='#5b3a55'/><stop offset='1' stop-color='#0a0e15'/></linearGradient>
<linearGradient id='m1' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#6f5870'/><stop offset='1' stop-color='#1b1a26'/></linearGradient>
<linearGradient id='m2' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#3b3447'/><stop offset='1' stop-color='#11131b'/></linearGradient>
<linearGradient id='m3' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#1d1f2b'/><stop offset='1' stop-color='#0a0e15'/></linearGradient>
<radialGradient id='glow' cx='.7' cy='.35' r='.5'><stop offset='0' stop-color='#e98a8a' stop-opacity='.45'/><stop offset='1' stop-color='#e98a8a' stop-opacity='0'/></radialGradient>
</defs>
<rect width='800' height='460' fill='url(#sky)'/><rect width='800' height='460' fill='url(#glow)'/>
<path d='M0 300 L120 210 L200 250 L330 120 L420 200 L520 90 L600 170 L700 110 L800 180 L800 460 L0 460z' fill='url(#m1)'/>
<path d='M330 120 L360 160 L345 158 L372 190 L420 200z M520 90 L548 128 L535 126 L560 160 L600 170z' fill='#c9a7b8' opacity='.35'/>
<path d='M0 340 L90 290 L180 320 L300 240 L400 300 L500 230 L610 290 L720 240 L800 270 L800 460 L0 460z' fill='url(#m2)'/>
<path d='M0 390 L140 350 L260 380 L380 330 L520 370 L650 335 L800 360 L800 460 L0 460z' fill='url(#m3)'/>
</svg>"""
HERO_BG = "data:image/svg+xml;utf8," + quote(" ".join(_MOUNTAINS.split()))

_WAVE = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 120' preserveAspectRatio='none'>
<path d='M0 90 C60 60 110 110 170 70 S260 40 300 60' fill='none' stroke='#F0705A' stroke-opacity='.55' stroke-width='1.5'/>
<path d='M0 100 C70 70 120 115 180 82 S260 55 300 72' fill='none' stroke='#F0705A' stroke-opacity='.3' stroke-width='1.2'/>
<path d='M0 110 C80 85 130 118 190 95 S265 72 300 85' fill='none' stroke='#F0705A' stroke-opacity='.18' stroke-width='1'/>
</svg>"""
WAVE_BG = "data:image/svg+xml;utf8," + quote(" ".join(_WAVE.split()))

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Caveat:wght@500&display=swap');
:root {{
  --bg:#0a0e15; --card:#0f141d; --card2:#121826; --line:#1e2533; --line2:#2a3242;
  --text:#eef1f6; --muted:#98a2b3; --dim:#6b7488; --coral:{CORAL};
}}
.stApp {{ background:
  radial-gradient(1200px 500px at 85% -10%, rgba(233,138,138,.10), transparent 60%),
  var(--bg); }}
.stApp :is(div, p, span, a, label, button, input, li, h1, h2, h3, h4, th, td):not([data-testid="stIconMaterial"]):not(pre *):not(code):not(code *) {{
  font-family:'Inter', system-ui, sans-serif; }}
[data-testid="stAppDeployButton"] {{ display:none; }}
header[data-testid="stHeader"] {{ background:transparent; }}
.block-container {{ padding:3.4rem 2rem 3rem; max-width:1560px; }}

/* sidebar */
section[data-testid="stSidebar"] {{ background:#0b0f16; border-right:1px solid var(--line); width:236px !important; }}
section[data-testid="stSidebar"] .block-container, section[data-testid="stSidebarContent"] {{ padding-top:0; }}
.sf-brand {{ display:flex; align-items:center; gap:10px; font-weight:700; font-size:20px; color:var(--text);
  margin:6px 4px 26px; }}
.sf-brand svg {{ color:var(--coral); }}
.sf-nav a {{ display:flex; align-items:center; gap:14px; padding:11px 14px; margin:3px 0; border-radius:10px;
  color:#c9cfdb !important; text-decoration:none !important; font-size:14.5px; font-weight:500; }}
.sf-nav a:hover {{ background:#141a26; color:#fff !important; }}
.sf-nav a.active {{ background:linear-gradient(90deg, rgba(240,112,90,.22), rgba(240,112,90,.08));
  color:#fff !important; box-shadow:inset 0 0 0 1px rgba(240,112,90,.18); }}
.sf-nav a svg {{ color:#aab2c3; }} .sf-nav a.active svg {{ color:var(--coral); }}
.sf-side-card {{ margin-top:40px; border:1px solid var(--line); border-radius:14px; padding:18px 16px 70px;
  background:url("{WAVE_BG}") bottom/100% 60% no-repeat, linear-gradient(180deg,#121826,#0e121b); }}
.sf-side-card b {{ display:block; font-size:17px; line-height:1.25; color:var(--text); margin-bottom:8px; }}
.sf-side-card span {{ color:var(--muted); font-size:13px; line-height:1.45; }}

/* top bar */
.sf-top {{ display:flex; justify-content:flex-end; align-items:center; gap:12px; margin:-6px 0 6px; }}
.sf-pill {{ display:inline-flex; align-items:center; gap:8px; padding:8px 14px; border-radius:999px;
  background:#121826; border:1px solid var(--line); color:#dfe4ec; font-size:13px; font-weight:500; }}
.sf-dot {{ width:8px; height:8px; border-radius:50%; background:{GREEN}; box-shadow:0 0 8px {GREEN}; }}
.sf-avatar {{ width:38px; height:38px; border-radius:50%; background:#1a2130; border:1px solid var(--line2);
  display:inline-flex; align-items:center; justify-content:center; font-weight:700; font-size:13px; color:#fff; }}

/* hero */
.st-key-hero {{ border-radius:18px; padding:26px 28px 30px; margin-bottom:8px;
  background:linear-gradient(90deg, var(--bg) 30%, rgba(10,14,21,.55) 58%, rgba(10,14,21,0) 80%),
             url("{HERO_BG}") right center / 62% 100% no-repeat; }}
.sf-eyebrow {{ color:#aab2c3; font-size:12px; letter-spacing:.16em; white-space:nowrap; font-weight:500; text-transform:uppercase; }}
.sf-title {{ font-size:78px; line-height:1.02; font-weight:800; letter-spacing:-.03em; margin:18px 0 10px;
  background:linear-gradient(92deg,#ffd9cc 0%,#f6a6a0 45%,#e690b8 100%); -webkit-background-clip:text;
  background-clip:text; color:transparent; }}
.sf-sub {{ font-size:22px; font-weight:500; color:#eef1f6; margin-bottom:22px; }}
.sf-desc {{ color:#b7bfcc; font-size:15.5px; line-height:1.6; max-width:470px; margin-bottom:26px; }}
.sf-quote, .sf-quote * {{ font-family:'Caveat', cursive !important; }}
.sf-quote {{ font-size:25px; line-height:1.15; color:#d7dbe6; transform:rotate(-9deg);
  margin-top:70px; text-align:center; }}
.sf-quote svg {{ display:block; margin:18px auto 0; color:#cfd4df; }}
.sf-words {{ color:#cfd4df; letter-spacing:.3em; font-size:12.5px; white-space:nowrap; line-height:1.9; margin-top:92px; opacity:.85; }}
.st-key-run button {{ background:linear-gradient(90deg,#f0705a,#e9605a) !important; border:none !important;
  color:#fff !important; padding:0 18px !important; border-radius:8px !important; font-weight:600 !important; white-space:nowrap;
  box-shadow:0 8px 24px rgba(240,112,90,.28); height:48px; }}
.st-key-run button:hover {{ filter:brightness(1.08); }}
a.sf-ghost {{ display:inline-flex; align-items:center; justify-content:center; gap:10px; height:48px; padding:0 22px;
  border:1px solid #c9cfdb; border-radius:8px; color:#fff !important; text-decoration:none !important;
  font-weight:600; font-size:15px; width:100%; white-space:nowrap; }}
a.sf-ghost:hover {{ border-color:var(--coral); color:var(--coral) !important; }}

/* slack preview */
.sf-slack {{ background:rgba(16,21,31,.88); backdrop-filter:blur(8px); border:1px solid var(--line2);
  border-radius:14px; padding:16px 16px 12px; box-shadow:0 20px 50px rgba(0,0,0,.45); margin-top:-6px; }}
.sf-slack .h {{ display:flex; align-items:center; gap:8px; color:#dfe4ec; font-size:13.5px; font-weight:500; }}
.sf-slack .h small {{ color:var(--dim); font-size:11.5px; font-weight:400; }}
.sf-here {{ display:inline-block; margin:10px 0 6px; padding:2px 8px; border-radius:5px; font-size:13px;
  color:#ffb4a8; background:rgba(240,112,90,.25); }}
.sf-slack .t {{ font-weight:700; font-size:16px; color:#fff; }}
.sf-slack .d {{ color:var(--muted); font-size:12.5px; margin:4px 0 2px; }}
.sf-slack .s {{ color:#e5e8ee; font-size:13.5px; padding-bottom:10px; border-bottom:1px solid var(--line); }}
.sf-item {{ display:flex; align-items:center; gap:12px; padding:8px 2px; }}
.sf-item i {{ width:11px; height:11px; border-radius:50%; flex:none; }}
.sf-item div {{ flex:1; min-width:0; }} .sf-item b {{ display:block; font-size:13.5px; color:#fff; font-weight:600;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.sf-item span {{ color:var(--muted); font-size:12px; }}
.sf-prio {{ font-size:12px; padding:3px 9px; border-radius:6px; color:#ffb4a8; background:rgba(240,82,74,.22); }}
.sf-more {{ color:#cfd4df; font-size:13px; padding:4px 2px 10px; }}
.sf-foot {{ border:1px solid var(--line2); border-radius:8px; text-align:center; padding:7px; color:var(--muted);
  font-size:12px; }}

/* stat cards */
.sf-stats {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin:6px 0 16px; }}
.sf-stat {{ display:flex; align-items:center; gap:16px; background:var(--card); border:1px solid var(--line);
  border-radius:12px; padding:18px 18px; }}
.sf-stat .ic {{ width:56px; height:56px; border-radius:50%; flex:none; display:flex; align-items:center;
  justify-content:center; }}
.sf-stat .n {{ font-size:27px; font-weight:700; color:#fff; line-height:1.1; }}
.sf-stat .l {{ font-size:14px; color:#e5e8ee; font-weight:500; margin-top:4px; }}
.sf-stat .x {{ font-size:13px; color:var(--muted); margin-top:4px; }}
.sf-stat.ok {{ background:linear-gradient(135deg, rgba(47,191,159,.12), rgba(47,191,159,.03)); border-color:rgba(47,191,159,.3); }}
.sf-stat.ok .k {{ color:{GREEN}; font-size:13px; }}
.sf-stat.ok a {{ color:{GREEN} !important; font-size:13px; text-decoration:none !important; display:inline-block; margin-top:4px; }}

/* cards */
[class*="st-key-card_"] {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:20px 22px 18px; }}
.sf-h {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
.sf-h h2 {{ font-size:22px !important; font-weight:700 !important; color:#fff; margin:0 !important; padding:0 !important; }}
.sf-h h3 {{ font-size:18px !important; font-weight:700 !important; color:#fff; margin:0 !important; padding:0 !important; }}
.sf-cap {{ color:#b7bfcc; font-size:14px; margin:6px 0 4px; }}
.sf-cap.sm {{ font-size:12.5px; color:var(--muted); line-height:1.5; }}
a.sf-btn {{ display:inline-flex; align-items:center; gap:10px; padding:9px 16px; border:1px solid var(--line2);
  border-radius:8px; color:#fff !important; text-decoration:none !important; font-size:14px; font-weight:500;
  background:#121826; white-space:nowrap; }}
a.sf-btn:hover {{ border-color:var(--coral); }}
.sf-row {{ display:flex; align-items:center; gap:14px; margin:9px 0; }}
.sf-chip {{ display:inline-block; font-size:12.5px; padding:3px 11px; border-radius:4px; border:1px solid;
  white-space:nowrap; }}
.sf-row span.r {{ color:var(--muted); font-size:13px; }}
.sf-rung {{ display:flex; align-items:center; gap:14px; margin:14px 0; }}
.sf-rung .num {{ width:26px; height:26px; border-radius:50%; border:1px solid #6b7488; color:#dfe4ec; flex:none;
  display:flex; align-items:center; justify-content:center; font-size:13px; }}
.sf-rung .tile {{ width:40px; height:40px; border-radius:9px; flex:none; display:flex; align-items:center;
  justify-content:center; }}
.sf-rung b {{ display:block; color:#fff; font-size:14px; font-weight:600; }}
.sf-rung span {{ color:#b7bfcc; font-size:13px; }}
.sf-note {{ display:flex; align-items:center; gap:14px; margin-top:12px; padding:12px 16px; border:1px solid var(--line);
  border-radius:10px; background:#0c1119; color:#b7bfcc; font-size:12.5px; }}
.sf-note svg {{ color:#aab2c3; flex:none; }}
.sf-type {{ font-size:12.5px; color:#dfe4ec; margin:6px 0 2px; }}
.sf-type code {{ color:{GREEN}; background:none; padding:0; font-size:12px; }}
.sf-anchor {{ position:relative; top:-16px; }}
div[data-testid="stGraphVizChart"] svg {{ max-width:100%; height:auto; }}

@media (max-width: 1100px) {{
  .sf-stats {{ grid-template-columns:repeat(2,1fr); }}
  .sf-title {{ font-size:56px; }}
  .st-key-hero {{ background:var(--bg); }}
}}
</style>
"""
