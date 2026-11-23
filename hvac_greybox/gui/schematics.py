"""SVG schematics of the zone, AHU and VAV for the Streamlit app.

Each function takes the current input values (dict) and returns an SVG string
whose labels show those values. `show` renders one in the app.
"""
import base64
import math

import streamlit as st

# colours
INK    = "#1f2328"   # main text and outlines
MUTED  = "#57606a"   # secondary text
WALL   = "#8c959f"   # walls, ducts
COOL   = "#1f77b4"   # air flows
WARM   = "#d62728"   # heat (coils, gains)
SUN    = "#e8a200"   # solar
FILL   = "#f6f8fa"   # light fill inside boxes

WIDTH = 900  # viewBox width of every schematic

_DEFS = f"""
<defs>
  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="{COOL}"/>
  </marker>
  <marker id="arrow-sun" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
    <path d="M0,0 L10,5 L0,10 z" fill="{SUN}"/>
  </marker>
  <marker id="arrow-warm" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
    <path d="M0,0 L10,5 L0,10 z" fill="{WARM}"/>
  </marker>
  <pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <rect width="8" height="8" fill="#d0d7de"/>
    <line x1="0" y1="0" x2="0" y2="8" stroke="{WALL}" stroke-width="2"/>
  </pattern>
</defs>
"""


def _svg(height, body):
    return f"""
<svg viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}" xmlns="http://www.w3.org/2000/svg"
     font-family="-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif">
  {_DEFS}
  <rect x="1" y="1" width="{WIDTH - 2}" height="{height - 2}" rx="10" fill="#ffffff" stroke="#d0d7de"/>
  {body}
</svg>"""


def _text(x, y, s, size=14, color=INK, anchor="middle", weight="normal"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{s}</text>')


def _coil(x, y, w, h):
    """Coil: box with a zigzag of tubes."""
    n = 6
    pts = " ".join(f"{x + w * (i % 2):.0f},{y + h * i / n:.0f}" for i in range(n + 1))
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff" stroke="{WARM}" stroke-width="2"/>'
            f'<polyline points="{pts}" fill="none" stroke="{WARM}" stroke-width="1.5"/>')


def _damper(cx, cy, length=34, angle=40):
    """Damper blade: a line through a pivot."""
    dx = length / 2 * math.cos(math.radians(angle))
    dy = length / 2 * math.sin(math.radians(angle))
    return (f'<line x1="{cx - dx:.1f}" y1="{cy - dy:.1f}" x2="{cx + dx:.1f}" y2="{cy + dy:.1f}" '
            f'stroke="{INK}" stroke-width="3" stroke-linecap="round"/>'
            f'<circle cx="{cx}" cy="{cy}" r="3.5" fill="{INK}"/>')


def zone_svg(v):
    """Room with R through the wall, C to ground, solar through a window, internal gains and thermostat."""
    h = 300
    sp_c = v["T_set"] + v["deadband"] / 2
    sp_h = v["T_set"] - v["deadband"] / 2
    # resistor zigzag from x0 to x1 at height y
    x0, x1, y = 175, 300, 205
    zz = [f"{x0},{y}"] + [f"{x0 + 15 + i * 12},{y + (-10 if i % 2 == 0 else 10)}" for i in range(8)] + [f"{x1},{y}"]
    body = f"""
  {_text(110, 40, "Outdoor", 16, MUTED, weight="bold")}
  {_text(565, 40, "Zone", 16, MUTED, weight="bold")}

  <!-- room: wall on the left with a window, outline elsewhere -->
  <rect x="250" y="55" width="630" height="215" fill="{FILL}" stroke="{WALL}" stroke-width="2"/>
  <rect x="222" y="55" width="28" height="215" fill="url(#hatch)" stroke="{WALL}"/>
  <rect x="222" y="90" width="28" height="55" fill="#cfe8ff" stroke="{WALL}"/>
  {_text(236, 85, "window", 11, MUTED)}

  <!-- sun and solar gain through the window -->
  <circle cx="60" cy="80" r="17" fill="{SUN}"/>
  {"".join(f'<line x1="{60 + 22 * c:.1f}" y1="{80 + 22 * s:.1f}" x2="{60 + 30 * c:.1f}" y2="{80 + 30 * s:.1f}" stroke="{SUN}" stroke-width="2.5"/>'
           for c, s in [(1, 0), (0.707, 0.707), (0, 1), (-0.707, 0.707), (-1, 0), (-0.707, -0.707), (0, -1), (0.707, -0.707)])}
  <line x1="88" y1="92" x2="335" y2="135" stroke="{SUN}" stroke-width="3" marker-end="url(#arrow-sun)"/>
  {_text(350, 120, "Solar gain = A_eff × GHI", 13, INK, "start")}
  {_text(350, 138, f"A_eff = {v['A_eff']:.1f} m²", 13, SUN, "start", "bold")}

  <!-- outdoor node, resistor, indoor node -->
  <circle cx="110" cy="{y}" r="6" fill="{INK}"/>
  {_text(110, y + 28, "T_out", 13, INK)}
  {_text(110, y + 45, "(weather file)", 11, MUTED)}
  <line x1="116" y1="{y}" x2="{x0}" y2="{y}" stroke="{INK}" stroke-width="2"/>
  <polyline points="{' '.join(zz)}" fill="none" stroke="{INK}" stroke-width="2.5"/>
  {_text((x0 + x1) / 2, y - 22, f"R = {v['R']:.4f} K/W", 13, INK, weight="bold")}
  <line x1="{x1}" y1="{y}" x2="414" y2="{y}" stroke="{INK}" stroke-width="2"/>
  <circle cx="420" cy="{y}" r="6" fill="{INK}"/>
  {_text(420, y - 18, f"T_in(0) = {v['T_in0']:.1f} °C", 13, INK, weight="bold")}

  <!-- capacitor to ground -->
  <line x1="420" y1="{y + 6}" x2="420" y2="{y + 22}" stroke="{INK}" stroke-width="2"/>
  <line x1="400" y1="{y + 22}" x2="440" y2="{y + 22}" stroke="{INK}" stroke-width="3"/>
  <line x1="400" y1="{y + 31}" x2="440" y2="{y + 31}" stroke="{INK}" stroke-width="3"/>
  <line x1="420" y1="{y + 31}" x2="420" y2="{y + 45}" stroke="{INK}" stroke-width="2"/>
  <line x1="406" y1="{y + 45}" x2="434" y2="{y + 45}" stroke="{INK}" stroke-width="2"/>
  <line x1="411" y1="{y + 50}" x2="429" y2="{y + 50}" stroke="{INK}" stroke-width="2"/>
  <line x1="416" y1="{y + 55}" x2="424" y2="{y + 55}" stroke="{INK}" stroke-width="2"/>
  {_text(450, y + 31, f"C = {v['C_MJ']:.1f} MJ/K", 13, INK, "start", "bold")}

  <!-- internal gains: person and computer with rising heat -->
  <circle cx="575" cy="170" r="11" fill="none" stroke="{INK}" stroke-width="2"/>
  <path d="M557,215 Q575,182 593,215" fill="none" stroke="{INK}" stroke-width="2"/>
  <rect x="612" y="185" width="38" height="26" rx="3" fill="#fff" stroke="{INK}" stroke-width="2"/>
  <line x1="606" y1="215" x2="656" y2="215" stroke="{INK}" stroke-width="2"/>
  {"".join(f'<path d="M{x},150 q-7,-10 0,-20 q7,-10 0,-20" fill="none" stroke="{WARM}" stroke-width="2.5" marker-end="url(#arrow-warm)"/>'
           for x in (570, 605, 640))}
  {_text(605, 240, "Internal gains", 13, INK)}
  {_text(605, 258, f"{v['Q_gains']:.0f} W", 13, WARM, weight="bold")}

  <!-- thermostat: setpoint, deadband and controller gains -->
  <line x1="705" y1="70" x2="705" y2="255" stroke="#d0d7de" stroke-width="1.5"/>
  {_text(792, 78, "Thermostat", 12, MUTED, weight="bold")}
  <rect x="774" y="88" width="36" height="36" rx="6" fill="#fff" stroke="{INK}" stroke-width="2"/>
  {_text(792, 112, "T", 14, INK, weight="bold")}
  {_text(792, 148, f"T_set = {v['T_set']:.1f} °C", 13, INK, weight="bold")}
  {_text(792, 166, f"deadband = {v['deadband']:.1f} K", 13, INK, weight="bold")}
  {_text(792, 184, f"heat &lt; {sp_h:.1f} · cool &gt; {sp_c:.1f} °C", 11, MUTED)}
  {_text(792, 210, f"Kp_cool = {v['Kp_cool']:.2f} 1/K", 13, COOL, weight="bold")}
  {_text(792, 228, f"Kp_heat = {v['Kp_heat']:.2f} 1/K", 13, WARM, weight="bold")}
"""
    return _svg(h, body), h


def ahu_svg(v):
    """AHU: exhaust/return duct on top, outdoor/supply duct below, mixing damper, coil, fan, SAT sensor."""
    h = 290
    top, bot, dh = 55, 165, 50   # duct tops and height
    body = f"""
  {_text(450, 32, "Air handling unit", 16, MUTED, weight="bold")}

  <!-- ducts -->
  <rect x="90" y="{top}" width="720" height="{dh}" fill="{FILL}" stroke="{WALL}" stroke-width="2"/>
  <rect x="90" y="{bot}" width="720" height="{dh}" fill="{FILL}" stroke="{WALL}" stroke-width="2"/>
  <rect x="250" y="{top + dh}" width="44" height="{bot - top - dh}" fill="{FILL}" stroke="{WALL}" stroke-width="2"/>
  <rect x="252" y="{top + dh - 2}" width="40" height="{bot - top - dh + 4}" fill="{FILL}"/>

  <!-- air streams -->
  <line x1="880" y1="{top + 25}" x2="820" y2="{top + 25}" stroke="{COOL}" stroke-width="3" marker-end="url(#arrow)"/>
  {_text(850, top + 15, "RA", 13, COOL, weight="bold")}
  {_text(850, top + 48, "from zone", 11, MUTED)}
  <line x1="85" y1="{top + 25}" x2="22" y2="{top + 25}" stroke="{COOL}" stroke-width="3" marker-end="url(#arrow)"/>
  {_text(50, top + 15, "EA", 13, COOL, weight="bold")}
  <line x1="20" y1="{bot + 25}" x2="85" y2="{bot + 25}" stroke="{COOL}" stroke-width="3" marker-end="url(#arrow)"/>
  {_text(50, bot + 15, "OA", 13, COOL, weight="bold")}
  <line x1="815" y1="{bot + 25}" x2="880" y2="{bot + 25}" stroke="{COOL}" stroke-width="3" marker-end="url(#arrow)"/>
  {_text(850, bot + 15, "SA", 13, COOL, weight="bold")}
  {_text(850, bot + 48, "to VAV", 11, MUTED)}

  <!-- economizer dampers -->
  {_damper(150, top + 25)}
  {_damper(150, bot + 25)}
  {_damper(272, (top + dh + bot) / 2, angle=-50)}
  {_text(305, (top + dh + bot) / 2 + 5, "economizer", 12, MUTED, "start")}

  <!-- mixed air sensor -->
  <circle cx="345" cy="{bot + 25}" r="11" fill="#fff" stroke="{INK}" stroke-width="1.5"/>
  {_text(345, bot + 29, "T", 11, INK)}
  {_text(345, bot + 70, "T_ma", 12, MUTED)}

  <!-- coil -->
  {_coil(420, bot, 34, dh)}
  {_text(437, bot - 8, "coil", 12, MUTED)}

  <!-- fan -->
  <circle cx="560" cy="{bot + 25}" r="20" fill="#fff" stroke="{INK}" stroke-width="2"/>
  <path d="M548,{bot + 13} L576,{bot + 25} L548,{bot + 37}" fill="none" stroke="{INK}" stroke-width="2"/>
  {_text(560, bot - 8, "fan", 12, MUTED)}

  <!-- supply air temperature sensor and P loop to the coil -->
  <circle cx="700" cy="{bot + 25}" r="11" fill="#fff" stroke="{INK}" stroke-width="1.5"/>
  {_text(700, bot + 29, "T", 11, INK)}
  <path d="M700,{bot + 14} V{bot - 25} H437 V{bot}" fill="none" stroke="{WARM}" stroke-width="1.5" stroke-dasharray="5,4"/>
  {_text(568, bot - 31, "P control on T_sa", 11, WARM)}

  <!-- input labels -->
  {_text(150, 262, f"foa_min = {v['foa_min']:.2f}  ·  foa(0) = {v['foa0']:.2f}", 13, INK, weight="bold")}
  {_text(437, 252, f"Q_rated = {v['Q_coil_rated']:.0f} W", 13, WARM, weight="bold")}
  {_text(437, 270, f"Kp = {v['Kp_coil']:.0f} W/K", 13, WARM, weight="bold")}
  {_text(700, 262, f"T_sa,sp = {v['T_sasp']:.1f} °C", 13, INK, weight="bold")}
"""
    return _svg(h, body), h


def vav_svg(v):
    """VAV box (damper and reheat coil) discharging into the zone, with the thermostat signals."""
    h = 290
    y0, dh = 120, 44   # duct top and height
    body = f"""
  <!-- inlet duct, box, discharge -->
  <rect x="40" y="{y0}" width="130" height="{dh}" fill="{FILL}" stroke="{WALL}" stroke-width="2"/>
  <rect x="170" y="{y0 - 18}" width="290" height="{dh + 36}" rx="6" fill="{FILL}" stroke="{INK}" stroke-width="2"/>
  {_text(315, y0 - 26, "VAV box", 13, MUTED, weight="bold")}
  {_text(235, y0 + dh + 36, "damper", 12, MUTED)}
  {_text(370, y0 + dh + 36, "reheat", 12, MUTED)}
  <rect x="460" y="{y0}" width="100" height="{dh}" fill="{FILL}" stroke="{WALL}" stroke-width="2"/>
  <line x1="20" y1="{y0 + 22}" x2="150" y2="{y0 + 22}" stroke="{COOL}" stroke-width="3" marker-end="url(#arrow)"/>
  {_text(85, y0 - 10, "SA from AHU", 12, COOL, weight="bold")}
  <line x1="470" y1="{y0 + 22}" x2="600" y2="{y0 + 22}" stroke="{COOL}" stroke-width="3" marker-end="url(#arrow)"/>

  <!-- damper and reheat coil -->
  {_damper(235, y0 + 22, length=38, angle=55)}
  {_coil(355, y0 - 8, 30, dh + 16)}

  <!-- zone with thermostat -->
  <rect x="560" y="45" width="320" height="215" fill="none" stroke="{WALL}" stroke-width="2"/>
  {_text(720, 70, "Zone", 16, MUTED, weight="bold")}
  <rect x="770" y="{y0 + 4}" width="36" height="36" rx="6" fill="#fff" stroke="{INK}" stroke-width="2"/>
  {_text(788, y0 + 28, "T", 14, INK, weight="bold")}
  {_text(788, y0 + 62, "thermostat", 12, MUTED)}
  {_text(720, 225, "setpoint, deadband and gains: see Zone", 12, MUTED)}

  <!-- control signals from the thermostat -->
  <path d="M788,{y0 + 4} V25 H235 V{y0 + 8}" fill="none" stroke="{COOL}" stroke-width="1.5" stroke-dasharray="5,4"/>
  <path d="M370,25 V{y0 - 8}" fill="none" stroke="{WARM}" stroke-width="1.5" stroke-dasharray="5,4"/>
  {_text(245, 45, "y_cool", 12, COOL, "start")}
  {_text(380, 45, "y_heat", 12, WARM, "start")}

  <!-- input labels -->
  {_text(235, 262, f"flow {v['msa_min']:.0f} – {v['msa_max']:.0f} L/s", 13, COOL, weight="bold")}
  {_text(390, 262, f"Q_rated = {v['Q_rad_rated']:.0f} W", 13, WARM, weight="bold")}
"""
    return _svg(h, body), h


def show(svg_and_height):
    """Render an SVG schematic in the app, scaled to the width of its container."""
    svg, _ = svg_and_height
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    st.markdown(f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%">',
                unsafe_allow_html=True)
