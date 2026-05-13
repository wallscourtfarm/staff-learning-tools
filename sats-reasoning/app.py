import streamlit as st
import anthropic
import json
import re
import math
from pathlib import Path

LOGO_PATH = Path("assets/wfa_logo.jpg")

def _b64_img(path):
    import base64
    return base64.b64encode(Path(path).read_bytes()).decode()

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="WFA KS2 SATs Reasoning",
    page_icon="✏️",
    layout="wide",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Sidebar */
    [data-testid="stSidebar"] { background: #f4f6f8; }
    [data-testid="stSidebar"] > div:first-child { padding-top: 12px; }

    /* Tighten expander padding in sidebar */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        border: 1px solid #dde2e8;
        border-radius: 5px;
        margin-bottom: 4px;
        background: white;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        font-size: 13px;
        font-weight: 600;
        color: #1a2a3a;
        padding: 8px 12px;
    }
    [data-testid="stSidebar"] .stCheckbox label { font-size: 13px; }
    [data-testid="stSidebar"] .stCheckbox { margin-bottom: 2px; }

    /* Primary button */
    .stButton > button[kind="primary"] {
        background-color: #1798d3 !important;
        border-color: #1798d3 !important;
        color: white !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #1280b8 !important;
        border-color: #1280b8 !important;
    }
    .stButton > button { border-radius: 5px !important; }

    /* Print styles */
    @media print {
        [data-testid="stSidebar"],
        [data-testid="stToolbar"],
        [data-testid="stHeader"],
        #MainMenu,
        .stButton,
        footer { display: none !important; }
        .main .block-container { padding: 0 !important; max-width: 100% !important; }
        body { background: white; }
    }
</style>
""", unsafe_allow_html=True)

# ─── Topic definitions ────────────────────────────────────────────────────────

TOPICS = {
    "Number & Place Value": [
        "Place value (integers to 10 million)",
        "Rounding to any power of 10",
        "Negative numbers",
        "Roman numerals",
    ],
    "Addition & Subtraction": [
        "Mental strategies",
        "Multi-step addition and subtraction",
    ],
    "Multiplication & Division": [
        "Long multiplication (up to 4-digit × 2-digit)",
        "Long division (up to 4-digit ÷ 2-digit)",
        "Order of operations (BODMAS)",
        "Factors, multiples, primes, squares and cubes",
    ],
    "Fractions, Decimals & Percentages": [
        "Comparing and ordering fractions",
        "Adding and subtracting fractions (different denominators)",
        "Multiplying fractions",
        "Fractions of amounts",
        "Decimals",
        "Percentages of amounts",
        "Percentage — finding the whole",
        "Converting between fractions, decimals and percentages",
    ],
    "Ratio & Proportion": [
        "Ratio",
        "Scale problems",
        "Proportion problems",
    ],
    "Algebra": [
        "Missing numbers and unknowns",
        "Number sequences",
        "Two unknowns",
        "Substitution",
    ],
    "Measurement": [
        "Unit conversion",
        "Perimeter",
        "Area of rectangles and compound shapes",
        "Area of triangles (½ × b × h)",
        "Volume of cuboids",
    ],
    "Geometry": [
        "Properties of 2D shapes",
        "Angles on a straight line (180°)",
        "Angles around a point (360°)",
        "Missing angles in triangles and quadrilaterals",
        "Coordinates — all four quadrants",
        "Translation and reflection",
    ],
    "Statistics": [
        "Bar charts and line graphs",
        "Pie charts",
        "Mean average",
        "Two-way tables",
    ],
}

# ─── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert KS2 mathematics question writer. Generate SATs-style reasoning questions that look and feel exactly like genuine KS2 SATs papers (Papers 2 and 3).

Return ONLY a valid JSON array — no markdown fences, no explanation, nothing else.

Each element has this shape:
{
  "id": 1,
  "marks": 1,
  "type": "write-answer",
  "questionText": "Question text here.",
  "answerLabel": "",
  "showMethod": false,
  "hasGrid": false,
  "gridType": null,
  "gridConfig": null,
  "options": null,
  "table": null,
  "chart": null,
  "parts": null,
  "answer": "correct answer",
  "markScheme": "Brief mark scheme note"
}

TYPES (use exact string):
- "write-answer"    — pupil writes in answer box
- "tick-options"    — tick one or more; options = ["opt1","opt2","opt3","opt4"]
- "circle-options"  — circle one from a horizontal list; options = ["a","b","c","d","e"]
- "match"           — draw lines; options = {"left":["A","B","C"],"right":["X","Y","Z"]}
- "order"           — arrange in order; options = ["3.2","0.7","1.05","2.8"]
- "explain"         — write an explanation (no answer box needed)
- "complete-table"  — table with blanks; table = {"headers":["col1","col2"],"rows":[[1,null],[null,4]]}
- "sequence"        — fill missing terms; options = [100,null,300,null,500]  (null = blank)
- "draw-on-grid"    — coordinate grid; hasGrid:true, gridType:"coordinate", gridConfig:{...}
- "number-line"     — number line; hasGrid:true, gridType:"number-line", gridConfig:{...}
- "multi-part"      — two sub-questions; parts = [{letter:"a",questionText:"...",answerLabel:"",marks:1,showMethod:false,answer:""},{letter:"b",...}]
- "bar-chart"       — rendered bar chart; chart = {"title":"Favourite sports","xLabel":"Sport","yLabel":"Number of children","yMax":30,"yStep":5,"data":[{"label":"Football","value":14},{"label":"Swimming","value":8},...]}
- "pie-chart"       — rendered pie chart; chart = {"title":"How children travel to school","total":60,"segments":[{"label":"Walk","value":24},{"label":"Car","value":18},{"label":"Bus","value":12},{"label":"Cycle","value":6}]}
- "line-graph"      — rendered line graph; chart = {"title":"Daily temperature","xLabel":"Day","yLabel":"Temperature (°C)","yMin":0,"yMax":25,"yStep":5,"points":[{"label":"Mon","value":12},{"label":"Tue","value":16},...]}

CHART RULES:
- For bar-chart: make yMax a round number comfortably above the highest bar. Use 4–6 bars. Values must be readable from the y-axis scale (multiples of yStep or clearly between gridlines).
- For pie-chart: segment values must sum to the stated total. Use 3–5 segments with realistic, non-trivial values. The question should require calculating an amount or fraction from the chart, not just reading a label.
- For line-graph: use 5–7 points with a clear trend or pattern. yMin is usually 0. Make values fall exactly on or between gridlines.
- Always write a question that requires interpreting or calculating from the chart — not just reading one value off directly.
- Use bar-chart and line-graph for Statistics topics. Use pie-chart for Statistics topics involving fractions or percentages.

gridConfig for coordinate:
{"xMin":-5,"xMax":5,"yMin":-5,"yMax":5,"points":[{"label":"A","x":3,"y":2}],"mirrorLine":null}
mirrorLine: "vertical" | "horizontal" | null

gridConfig for number-line:
{"min":0,"max":1,"marked":[0,0.5,1],"labels":["0","0.5","1"]}

Set showMethod:true when marks >= 2.
Vary question types across the set — do not make all questions "write-answer".
When the topic includes statistics, bar charts, pie charts or line graphs, USE those chart types rather than write-answer.
- "angle-diagram"   — rendered angle(s); angleConfig = {"subtype":"standalone|on-line|at-point|triangle","angles":[{"value":65,"label":""},{"value":null,"label":"x"}]}
- "labelled-shape"  — 2D shape with labelled sides; shapeConfig = {"shape":"rectangle|right-triangle|isosceles-triangle|l-shape|trapezium|parallelogram","sides":["8 cm","5 cm","8 cm","5 cm"]}
- "clock"           — analogue clock face; clockConfig = {"hours":8,"minutes":20}
- "measuring-scale" — measuring jug / scale; scaleConfig = {"unit":"ml","min":0,"max":500,"step":100,"labelStep":100,"pointer":350}
- "timetable"       — train/bus timetable; timetableConfig = {"title":"Train timetable","headers":["Station","Train A","Train B","Train C"],"rows":[["Bristol","07:15","08:30","09:45"],["Bath","07:28","08:43","09:58"],["London","09:05","10:20","11:35"]]}

GEOMETRY & MEASUREMENT RULES:
- angle-diagram subtypes: standalone=one angle two rays; on-line=angles on a straight line summing to 180°; at-point=angles around a point summing to 360°; triangle=three angles summing to 180°. Unknown angle shown as null with a letter label (e.g. "x"). Unknown angles rendered in pink — pupils calculate and write them in.
- labelled-shape sides count: rectangle=4, right-triangle=3, isosceles-triangle=3, l-shape=6, trapezium=4, parallelogram=4. Use "?" for unknown sides. Question must require a calculation (perimeter, area, or missing length).
- clock: ask to read time shown, calculate elapsed time, or state time after/before given duration.
- measuring-scale: pointer is always a specific value (the thing being read). step sets tick spacing, labelStep sets label spacing (can be larger for readability, e.g. step=50 labelStep=100). Units: ml, l, g, kg, °C.
- timetable: 3–5 rows (stops), 3–4 time columns. Ask about journey times, how long to wait, or earliest departure. Use 24-hour clock for train/bus timetables.
- Use angle-diagram for angles questions. Use labelled-shape for perimeter/area. Use clock for time reading/elapsed time. Use measuring-scale for weight/capacity/temperature reading. Use timetable for timetable problems.
Generate exactly the count requested."""

Y6_CURRICULUM = """Year 6 maths curriculum scope — pitch all questions here (this is SATs year):
- Number & Place Value: numbers to 10 million; round to any power of 10; order/compare integers and decimals
- Addition & Subtraction: equivalence and compensation strategies; multi-step calculations
- Multiplication & Division: long multiplication (up to 4-digit × 2-digit); long division (up to 4-digit ÷ 2-digit)
- Fractions, Decimals & Percentages: add/subtract fractions with different denominators; multiply and divide fractions; convert fluently between fractions, decimals and percentages; find percentage of a value; find the whole given a percentage
- Ratio & Proportion: describe ratio relationships; scale; solve proportion problems
- Algebra: balancing equations; two unknowns; substitution; order of operations (BODMAS)
- Measurement: area of triangles (½bh); perimeter and area consolidation; volume of cuboids; unit conversion
- Coordinates: all four quadrants — plot, read, translate, reflect
- Statistics: construct and interpret pie charts; line graphs; mean average; two-way tables
IMPORTANT: Coordinates must use all four quadrants. Include BODMAS, ratio, algebra, percentages where relevant. Use multi-step problems. Full SATs style and difficulty throughout."""

# ─── SVG helpers ─────────────────────────────────────────────────────────────

def coord_grid_svg(cfg: dict) -> str:
    x_min = cfg.get("xMin", 0)
    x_max = cfg.get("xMax", 10)
    y_min = cfg.get("yMin", 0)
    y_max = cfg.get("yMax", 10)
    points = cfg.get("points", []) or []
    mirror = cfg.get("mirrorLine", None)

    cell, pad = 30, 34
    W = (x_max - x_min) * cell + pad * 2
    H = (y_max - y_min) * cell + pad * 2

    def tx(x): return pad + (x - x_min) * cell
    def ty(y): return H - pad - (y - y_min) * cell

    els = []
    for x in range(x_min, x_max + 1):
        els.append(f'<line x1="{tx(x)}" y1="{pad}" x2="{tx(x)}" y2="{H-pad}" stroke="#ccc" stroke-width="0.5"/>')
    for y in range(y_min, y_max + 1):
        els.append(f'<line x1="{pad}" y1="{ty(y)}" x2="{W-pad}" y2="{ty(y)}" stroke="#ccc" stroke-width="0.5"/>')

    bx = tx(max(x_min, 0))
    by_ = ty(max(y_min, 0))

    if x_min <= 0 <= x_max:
        els.append(f'<line x1="{tx(0)}" y1="{pad}" x2="{tx(0)}" y2="{H-pad}" stroke="#333" stroke-width="1.5"/>')
    if y_min <= 0 <= y_max:
        els.append(f'<line x1="{pad}" y1="{ty(0)}" x2="{W-pad}" y2="{ty(0)}" stroke="#333" stroke-width="1.5"/>')

    for x in range(x_min, x_max + 1):
        els.append(f'<text x="{tx(x)}" y="{by_+16}" text-anchor="middle" font-size="10" fill="#333" font-family="Arial">{x}</text>')
    for y in range(y_min, y_max + 1):
        els.append(f'<text x="{bx-14}" y="{ty(y)+4}" text-anchor="middle" font-size="10" fill="#333" font-family="Arial">{y}</text>')

    els.append(f'<text x="{W-pad+8}" y="{by_+4}" font-size="12" font-style="italic" fill="#333" font-family="Arial">x</text>')
    els.append(f'<text x="{bx}" y="{pad-8}" text-anchor="middle" font-size="12" font-style="italic" fill="#333" font-family="Arial">y</text>')

    if mirror == "vertical":
        mx = (x_min + x_max) // 2
        els.append(f'<line x1="{tx(mx)}" y1="{pad}" x2="{tx(mx)}" y2="{H-pad}" stroke="#888" stroke-width="1.5" stroke-dasharray="6,3"/>')
        els.append(f'<text x="{tx(mx)}" y="{pad-6}" text-anchor="middle" font-size="10" fill="#888" font-family="Arial">mirror line</text>')
    elif mirror == "horizontal":
        my = (y_min + y_max) // 2
        els.append(f'<line x1="{pad}" y1="{ty(my)}" x2="{W-pad}" y2="{ty(my)}" stroke="#888" stroke-width="1.5" stroke-dasharray="6,3"/>')
        els.append(f'<text x="{pad}" y="{ty(my)-6}" font-size="10" fill="#888" font-family="Arial">mirror line</text>')

    for p in points:
        els.append(f'<circle cx="{tx(p["x"])}" cy="{ty(p["y"])}" r="4" fill="#1a1a8c"/>')
        lbl = p.get("label", "")
        els.append(f'<text x="{tx(p["x"])+8}" y="{ty(p["y"])-6}" font-size="11" font-weight="bold" fill="#1a1a8c" font-family="Arial">{lbl}</text>')

    return f'<svg width="{W}" height="{H}" style="display:block;margin:10px 0">{"".join(els)}</svg>'


def number_line_svg(cfg: dict) -> str:
    mn = cfg.get("min", 0)
    mx = cfg.get("max", 10)
    marked = cfg.get("marked", []) or []
    labels = cfg.get("labels", [str(v) for v in marked]) or []

    W, H, pad, lY = 420, 60, 28, 36

    def to_x(v):
        return pad + ((v - mn) / (mx - mn)) * (W - pad * 2) if mx != mn else pad

    els = [
        f'<line x1="{pad}" y1="{lY}" x2="{W-pad}" y2="{lY}" stroke="#333" stroke-width="2"/>',
        f'<polygon points="{W-pad},{lY} {W-pad-8},{lY-4} {W-pad-8},{lY+4}" fill="#333"/>',
    ]
    for i, v in enumerate(marked):
        x = to_x(v)
        lab = labels[i] if i < len(labels) else str(v)
        els.append(f'<line x1="{x:.1f}" y1="{lY-8}" x2="{x:.1f}" y2="{lY+8}" stroke="#333" stroke-width="1.5"/>')
        els.append(f'<text x="{x:.1f}" y="{lY+20}" text-anchor="middle" font-size="11" font-family="Arial" fill="#333">{lab}</text>')

    return f'<svg width="{W}" height="{H}" style="display:block;margin:10px 0">{"".join(els)}</svg>'


# ─── Chart SVG renderers ──────────────────────────────────────────────────────

_CHART_COLOURS = ["#1798d3", "#e57d24", "#2bae62", "#c0157b", "#9b59b6", "#e74c3c", "#f39c12"]


def bar_chart_svg(chart: dict) -> str:
    data    = chart.get("data", [])
    title   = chart.get("title", "")
    x_label = chart.get("xLabel", "")
    y_label = chart.get("yLabel", "")
    y_step  = chart.get("yStep", 5)
    y_max   = chart.get("yMax") or (max(d["value"] for d in data) * 1.25 if data else 10)

    W, H = 500, 300
    pl, pr, pt, pb = 58, 16, 38, 56   # pad left/right/top/bottom
    cw = W - pl - pr
    ch = H - pt - pb

    n       = len(data)
    slot_w  = cw / n
    bar_w   = slot_w * 0.55

    def bx(i):  return pl + i * slot_w + slot_w / 2
    def by_(v): return pt + ch - (v / y_max) * ch

    els = []

    # Title
    if title:
        els.append(f'<text x="{W//2}" y="22" text-anchor="middle" font-size="13" font-weight="bold" font-family="Arial" fill="#1a1a1a">{title}</text>')

    # Horizontal grid lines + y-axis labels
    steps = round(y_max / y_step)
    for i in range(steps + 1):
        v  = i * y_step
        yp = by_(v)
        els.append(f'<line x1="{pl}" y1="{yp:.1f}" x2="{W-pr}" y2="{yp:.1f}" stroke="#e0e0e0" stroke-width="1"/>')
        els.append(f'<text x="{pl-5}" y="{yp+4:.1f}" text-anchor="end" font-size="10" font-family="Arial" fill="#444">{v}</text>')

    # Axes
    els.append(f'<line x1="{pl}" y1="{pt}" x2="{pl}" y2="{pt+ch}" stroke="#333" stroke-width="1.5"/>')
    els.append(f'<line x1="{pl}" y1="{pt+ch}" x2="{W-pr}" y2="{pt+ch}" stroke="#333" stroke-width="1.5"/>')

    # Bars
    for i, d in enumerate(data):
        x   = bx(i)
        bh  = (d["value"] / y_max) * ch
        yp  = by_(d["value"])
        els.append(
            f'<rect x="{x - bar_w/2:.1f}" y="{yp:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="#1798d3"/>'
        )
        # value label above bar
        els.append(f'<text x="{x:.1f}" y="{yp-4:.1f}" text-anchor="middle" font-size="10" font-family="Arial" fill="#1798d3">{d["value"]}</text>')
        # category label below axis — wrap long labels at ~10 chars
        label = d.get("label", "")
        if len(label) > 10:
            words = label.split()
            lines, cur = [], ""
            for w in words:
                if len(cur) + len(w) + 1 <= 10:
                    cur = (cur + " " + w).strip()
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            for li, ln in enumerate(lines):
                els.append(f'<text x="{x:.1f}" y="{pt+ch+14+li*12:.1f}" text-anchor="middle" font-size="10" font-family="Arial" fill="#333">{ln}</text>')
        else:
            els.append(f'<text x="{x:.1f}" y="{pt+ch+14:.1f}" text-anchor="middle" font-size="10" font-family="Arial" fill="#333">{label}</text>')

    # Y-axis label (rotated)
    if y_label:
        mid_y = pt + ch / 2
        els.append(f'<text x="12" y="{mid_y:.1f}" text-anchor="middle" font-size="10" font-family="Arial" fill="#555" transform="rotate(-90,12,{mid_y:.1f})">{y_label}</text>')

    # X-axis label
    if x_label:
        els.append(f'<text x="{pl + cw/2:.1f}" y="{H-2}" text-anchor="middle" font-size="10" font-family="Arial" fill="#555">{x_label}</text>')

    return f'<svg width="{W}" height="{H}" style="display:block;margin:12px 0">{"".join(els)}</svg>'


def pie_chart_svg(chart: dict) -> str:
    segments = chart.get("segments", [])
    title    = chart.get("title", "")
    total    = chart.get("total") or (sum(s["value"] for s in segments) or 1)

    if not segments:
        return ""

    W, H  = 460, 280
    cx, cy, r = 145, 148, 115

    els = []

    if title:
        els.append(f'<text x="{W//2}" y="20" text-anchor="middle" font-size="13" font-weight="bold" font-family="Arial" fill="#1a1a1a">{title}</text>')

    start = -math.pi / 2   # start at 12 o'clock
    for i, seg in enumerate(segments):
        sweep     = 2 * math.pi * seg["value"] / total
        end       = start + sweep
        x1, y1    = cx + r * math.cos(start), cy + r * math.sin(start)
        x2, y2    = cx + r * math.cos(end),   cy + r * math.sin(end)
        large_arc = 1 if sweep > math.pi else 0
        colour    = _CHART_COLOURS[i % len(_CHART_COLOURS)]

        els.append(
            f'<path d="M {cx} {cy} L {x1:.2f} {y1:.2f} '
            f'A {r} {r} 0 {large_arc} 1 {x2:.2f} {y2:.2f} Z" '
            f'fill="{colour}" stroke="white" stroke-width="2"/>'
        )

        # Percentage label inside segment (only if segment >= 8%)
        pct = seg["value"] / total * 100
        if pct >= 8:
            mid   = start + sweep / 2
            lr    = r * 0.62
            lx, ly = cx + lr * math.cos(mid), cy + lr * math.sin(mid)
            els.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle" font-size="11" font-weight="bold" '
                f'font-family="Arial" fill="white">{pct:.0f}%</text>'
            )

        start = end

    # Legend — right of pie
    leg_x = cx + r + 22
    for i, seg in enumerate(segments):
        colour = _CHART_COLOURS[i % len(_CHART_COLOURS)]
        ly     = 50 + i * 26
        els.append(f'<rect x="{leg_x}" y="{ly}" width="13" height="13" fill="{colour}" rx="2"/>')
        els.append(
            f'<text x="{leg_x+18}" y="{ly+10}" font-size="11" font-family="Arial" fill="#222">'
            f'{seg["label"]} ({seg["value"]})</text>'
        )

    return f'<svg width="{W}" height="{H}" style="display:block;margin:12px 0">{"".join(els)}</svg>'


def line_graph_svg(chart: dict) -> str:
    points  = chart.get("points", [])
    title   = chart.get("title", "")
    x_label = chart.get("xLabel", "")
    y_label = chart.get("yLabel", "")
    y_step  = chart.get("yStep", 5)
    y_min   = chart.get("yMin", 0)
    y_max   = chart.get("yMax") or (max(p["value"] for p in points) * 1.25 if points else 10)

    W, H = 500, 300
    pl, pr, pt, pb = 58, 16, 38, 56
    cw = W - pl - pr
    ch = H - pt - pb

    n = len(points)

    def lx(i): return pl + (i / (n - 1)) * cw if n > 1 else pl + cw / 2
    def ly_(v): return pt + ch - ((v - y_min) / (y_max - y_min)) * ch

    els = []

    if title:
        els.append(f'<text x="{W//2}" y="22" text-anchor="middle" font-size="13" font-weight="bold" font-family="Arial" fill="#1a1a1a">{title}</text>')

    # Grid lines + y labels
    steps = round((y_max - y_min) / y_step)
    for i in range(steps + 1):
        v  = y_min + i * y_step
        yp = ly_(v)
        els.append(f'<line x1="{pl}" y1="{yp:.1f}" x2="{W-pr}" y2="{yp:.1f}" stroke="#e0e0e0" stroke-width="1"/>')
        els.append(f'<text x="{pl-5}" y="{yp+4:.1f}" text-anchor="end" font-size="10" font-family="Arial" fill="#444">{v}</text>')

    # Axes
    els.append(f'<line x1="{pl}" y1="{pt}" x2="{pl}" y2="{pt+ch}" stroke="#333" stroke-width="1.5"/>')
    els.append(f'<line x1="{pl}" y1="{pt+ch}" x2="{W-pr}" y2="{pt+ch}" stroke="#333" stroke-width="1.5"/>')

    # Line path
    if n >= 2:
        coords = " ".join(f"{lx(i):.1f},{ly_(p['value']):.1f}" for i, p in enumerate(points))
        els.append(f'<polyline points="{coords}" fill="none" stroke="#1798d3" stroke-width="2.5"/>')

    # Points + x labels
    for i, p in enumerate(points):
        x = lx(i)
        y = ly_(p["value"])
        els.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#1798d3" stroke="white" stroke-width="1.5"/>')
        els.append(f'<text x="{x:.1f}" y="{pt+ch+14:.1f}" text-anchor="middle" font-size="10" font-family="Arial" fill="#333">{p["label"]}</text>')

    if y_label:
        mid_y = pt + ch / 2
        els.append(f'<text x="12" y="{mid_y:.1f}" text-anchor="middle" font-size="10" font-family="Arial" fill="#555" transform="rotate(-90,12,{mid_y:.1f})">{y_label}</text>')

    if x_label:
        els.append(f'<text x="{pl + cw/2:.1f}" y="{H-2}" text-anchor="middle" font-size="10" font-family="Arial" fill="#555">{x_label}</text>')

    return f'<svg width="{W}" height="{H}" style="display:block;margin:12px 0">{"".join(els)}</svg>'



# ─── Geometry & Measurement renderers ────────────────────────────────────────

def angle_diagram_svg(config: dict) -> str:
    subtype     = config.get("subtype", "standalone")
    angles_data = config.get("angles", [])
    W, H = 340, 230
    els  = []

    def _pt(cx, cy, deg, r):
        return (cx + r * math.cos(math.radians(deg)),
                cy - r * math.sin(math.radians(deg)))

    def _ray(cx, cy, deg, L, sw=1.5):
        ex, ey = _pt(cx, cy, deg, L)
        return (f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
                f'stroke="#333" stroke-width="{sw}" stroke-linecap="round"/>')

    def _arc(cx, cy, r, a0, a1):
        x1, y1 = _pt(cx, cy, a0, r)
        x2, y2 = _pt(cx, cy, a1, r)
        lg = 1 if (a1 - a0) > 180 else 0
        return (f'<path d="M {x1:.1f},{y1:.1f} A {r},{r} 0 {lg},0 {x2:.1f},{y2:.1f}" '
                f'fill="none" stroke="#555" stroke-width="1"/>')

    def _lbl(cx, cy, mid_deg, r, text, unk=False):
        lx, ly = _pt(cx, cy, mid_deg, r)
        col = "#c0157b" if unk else "#333"
        fw  = "bold"   if unk else "normal"
        return (f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle" font-size="13" font-weight="{fw}" '
                f'font-family="Arial" fill="{col}">{text}</text>')

    def _dot(cx, cy):
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.5" fill="#333"/>'

    def _fmt(a):
        if a.get("value") is not None:
            return f'{a["value"]}\u00b0', False
        return f'{a.get("label","x")}\u00b0', True

    if subtype == "standalone":
        cx, cy, L = 85, 185, 135
        a0 = angles_data[0] if angles_data else {"value": 65}
        draw_deg = a0.get("value") if a0.get("value") is not None else 65
        txt, unk = _fmt(a0)
        els += [_ray(cx, cy, 0, L), _ray(cx, cy, draw_deg, L),
                _arc(cx, cy, 40, 0, draw_deg),
                _lbl(cx, cy, draw_deg / 2, 65, txt, unk), _dot(cx, cy)]

    elif subtype == "on-line":
        cy, cx, L = 155, W // 2, 115
        els.append(f'<line x1="20" y1="{cy}" x2="{W-20}" y2="{cy}" stroke="#333" stroke-width="1.5"/>')
        if len(angles_data) >= 2:
            v0 = angles_data[0].get("value")
            v1 = angles_data[1].get("value")
            ray_deg = (180 - v0) if (v0 is not None and v1 is None) else (v1 if v1 is not None else 65)
            t0, u0 = _fmt(angles_data[0])
            t1, u1 = _fmt(angles_data[1])
            els += [_ray(cx, cy, ray_deg, L),
                    _arc(cx, cy, 38, ray_deg, 180), _lbl(cx, cy, (ray_deg + 180) / 2, 60, t0, u0),
                    _arc(cx, cy, 38, 0, ray_deg),   _lbl(cx, cy, ray_deg / 2, 60, t1, u1),
                    _dot(cx, cy)]
        elif len(angles_data) == 1:
            a0 = angles_data[0]
            draw_deg = a0.get("value") if a0.get("value") is not None else 65
            txt, unk = _fmt(a0)
            els += [_ray(cx, cy, draw_deg, L),
                    _arc(cx, cy, 38, 0, draw_deg),
                    _lbl(cx, cy, draw_deg / 2, 60, txt, unk), _dot(cx, cy)]

    elif subtype == "at-point":
        cx, cy, L = W // 2, H // 2 + 10, 100
        known_sum = sum(a.get("value", 0) for a in angles_data if a.get("value") is not None)
        n_unk     = sum(1 for a in angles_data if a.get("value") is None)
        unk_val   = (360 - known_sum) / max(n_unk, 1)
        boundaries = [0.0]
        for a in angles_data:
            v = a.get("value") if a.get("value") is not None else unk_val
            boundaries.append(boundaries[-1] + v)
        for d in boundaries[:-1]:
            els.append(_ray(cx, cy, d % 360, L))
        prev = 0.0
        for a in angles_data:
            v   = a.get("value") if a.get("value") is not None else unk_val
            nxt = prev + v
            txt, unk = _fmt(a)
            els += [_arc(cx, cy, 36, prev, nxt), _lbl(cx, cy, (prev + nxt) / 2, 58, txt, unk)]
            prev = nxt
        els.append(_dot(cx, cy))

    elif subtype == "triangle":
        if len(angles_data) >= 3:
            has_right = any(a.get("value") == 90 for a in angles_data)
            if has_right:
                v = [(55, 175), (270, 175), (55, 50)]
                sq_idx = next(i for i, a in enumerate(angles_data) if a.get("value") == 90)
                sq_d1, sq_d2 = (1, 0), (0, -1)
            else:
                v = [(50, 180), (290, 180), (170, 42)]
                sq_idx = None; sq_d1 = sq_d2 = None
            pts = " ".join(f"{int(p[0])},{int(p[1])}" for p in v)
            els.append(f'<polygon points="{pts}" fill="none" stroke="#333" stroke-width="1.5"/>')
            if sq_idx is not None:
                vx, vy = v[sq_idx]; s = 13
                p1 = (vx+sq_d1[0]*s, vy+sq_d1[1]*s)
                p2 = (vx+(sq_d1[0]+sq_d2[0])*s, vy+(sq_d1[1]+sq_d2[1])*s)
                p3 = (vx+sq_d2[0]*s, vy+sq_d2[1]*s)
                els.append(f'<polyline points="{p1[0]},{p1[1]} {p2[0]},{p2[1]} {p3[0]},{p3[1]}" '
                            f'fill="none" stroke="#333" stroke-width="1.5"/>')
            cx_c = sum(p[0] for p in v) / 3
            cy_c = sum(p[1] for p in v) / 3
            for i, (a, (vx, vy)) in enumerate(zip(angles_data, v)):
                if sq_idx == i and a.get("value") == 90 and not a.get("label"): continue
                dx, dy = cx_c - vx, cy_c - vy
                dist = math.sqrt(dx*dx + dy*dy)
                lx, ly = vx + dx/dist*30, vy + dy/dist*30
                txt, unk = _fmt(a)
                col = "#c0157b" if unk else "#333"
                fw  = "bold" if unk else "normal"
                els.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                            f'dominant-baseline="middle" font-size="13" font-weight="{fw}" '
                            f'font-family="Arial" fill="{col}">{txt}</text>')

    return f'<svg width="{W}" height="{H}" style="display:block;margin:12px 0">{"".join(els)}</svg>'


def labelled_shape_svg(config: dict) -> str:
    shape = config.get("shape", "rectangle")
    sides = config.get("sides", [])
    W, H  = 340, 230
    els   = []

    def _sl(x, y, text, anchor="middle"):
        return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
                f'dominant-baseline="middle" font-size="12" font-family="Arial" fill="#333">{text}</text>')

    def _ra(vx, vy, d1, d2, s=11):
        p1 = (vx+d1[0]*s, vy+d1[1]*s)
        p2 = (vx+(d1[0]+d2[0])*s, vy+(d1[1]+d2[1])*s)
        p3 = (vx+d2[0]*s, vy+d2[1]*s)
        return (f'<polyline points="{p1[0]:.0f},{p1[1]:.0f} {p2[0]:.0f},{p2[1]:.0f} '
                f'{p3[0]:.0f},{p3[1]:.0f}" fill="none" stroke="#333" stroke-width="1"/>')

    if shape == "rectangle":
        x0, y0, x1, y1 = 55, 55, 285, 175
        els.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" '
                   f'fill="none" stroke="#333" stroke-width="1.5"/>')
        for vx, vy, d1, d2 in [(x0,y0,(1,0),(0,1)),(x1,y0,(-1,0),(0,1)),
                                (x1,y1,(-1,0),(0,-1)),(x0,y1,(1,0),(0,-1))]:
            els.append(_ra(vx, vy, d1, d2))
        lps = [((x0+x1)/2, y0-14, "middle"), (x1+15, (y0+y1)/2, "start"),
               ((x0+x1)/2, y1+15, "middle"), (x0-15, (y0+y1)/2, "end")]
        for i, (lx, ly, anc) in enumerate(lps):
            if i < len(sides): els.append(_sl(lx, ly, sides[i], anc))

    elif shape == "right-triangle":
        v = [(55,185),(285,185),(55,45)]
        pts = " ".join(f"{p[0]},{p[1]}" for p in v)
        els.append(f'<polygon points="{pts}" fill="none" stroke="#333" stroke-width="1.5"/>')
        els.append(_ra(v[0][0], v[0][1], (1,0), (0,-1)))
        lps = [((v[0][0]+v[1][0])/2, v[0][1]+15, "middle"),
               ((v[1][0]+v[2][0])/2+14, (v[1][1]+v[2][1])/2, "start"),
               (v[0][0]-14, (v[0][1]+v[2][1])/2, "end")]
        for i, (lx, ly, anc) in enumerate(lps):
            if i < len(sides): els.append(_sl(lx, ly, sides[i], anc))

    elif shape == "isosceles-triangle":
        v = [(170,40),(55,195),(285,195)]
        pts = " ".join(f"{p[0]},{p[1]}" for p in v)
        els.append(f'<polygon points="{pts}" fill="none" stroke="#333" stroke-width="1.5"/>')
        for pair in [(0,1),(0,2)]:
            mx=(v[pair[0]][0]+v[pair[1]][0])/2; my=(v[pair[0]][1]+v[pair[1]][1])/2
            dx=v[pair[1]][0]-v[pair[0]][0]; dy=v[pair[1]][1]-v[pair[0]][1]
            dist=math.sqrt(dx*dx+dy*dy); px,py=-dy/dist*6,dx/dist*6
            els.append(f'<line x1="{mx-px:.1f}" y1="{my-py:.1f}" x2="{mx+px:.1f}" y2="{my+py:.1f}" '
                       f'stroke="#333" stroke-width="1.5"/>')
        lps = [(v[0][0]-16, (v[0][1]+v[1][1])/2, "end"),
               ((v[1][0]+v[2][0])/2, v[1][1]+15, "middle"),
               (v[0][0]+16, (v[0][1]+v[2][1])/2, "start")]
        for i, (lx, ly, anc) in enumerate(lps):
            if i < len(sides): els.append(_sl(lx, ly, sides[i], anc))

    elif shape == "l-shape":
        x0,y0=50,30; ow,oh,nw,nh=240,185,130,90
        v=[(x0,y0),(x0+ow,y0),(x0+ow,y0+nh),(x0+ow-nw,y0+nh),(x0+ow-nw,y0+oh),(x0,y0+oh)]
        pts = " ".join(f"{p[0]},{p[1]}" for p in v)
        els.append(f'<polygon points="{pts}" fill="none" stroke="#333" stroke-width="1.5"/>')
        for idx,d1,d2 in [(0,(1,0),(0,1)),(1,(-1,0),(0,1)),(2,(0,1),(-1,0)),
                           (3,(1,0),(0,1)),(4,(-1,0),(0,-1)),(5,(1,0),(0,-1))]:
            els.append(_ra(v[idx][0],v[idx][1],d1,d2))
        lps=[((v[0][0]+v[1][0])/2, v[0][1]-14, "middle"),
             (v[1][0]+14, (v[1][1]+v[2][1])/2, "start"),
             ((v[2][0]+v[3][0])/2, v[2][1]-12, "middle"),
             (v[3][0]-14, (v[3][1]+v[4][1])/2, "end"),
             ((v[4][0]+v[5][0])/2, v[4][1]+15, "middle"),
             (v[5][0]-14, (v[5][1]+v[0][1])/2, "end")]
        for i, (lx, ly, anc) in enumerate(lps):
            if i < len(sides): els.append(_sl(lx, ly, sides[i], anc))

    elif shape == "trapezium":
        v=[(105,55),(245,55),(295,180),(55,180)]
        pts = " ".join(f"{p[0]},{p[1]}" for p in v)
        els.append(f'<polygon points="{pts}" fill="none" stroke="#333" stroke-width="1.5"/>')
        for tx,ty in [((v[0][0]+v[1][0])/2,v[0][1]),((v[2][0]+v[3][0])/2,v[2][1])]:
            els.append(f'<line x1="{tx-6}" y1="{ty}" x2="{tx+6}" y2="{ty}" stroke="#333" stroke-width="2"/>')
        lps=[((v[0][0]+v[1][0])/2, v[0][1]-14, "middle"),
             ((v[1][0]+v[2][0])/2+14, (v[1][1]+v[2][1])/2, "start"),
             ((v[2][0]+v[3][0])/2, v[2][1]+15, "middle"),
             ((v[3][0]+v[0][0])/2-14, (v[3][1]+v[0][1])/2, "end")]
        for i, (lx, ly, anc) in enumerate(lps):
            if i < len(sides): els.append(_sl(lx, ly, sides[i], anc))

    elif shape == "parallelogram":
        v=[(90,175),(290,175),(250,48),(50,48)]
        pts = " ".join(f"{p[0]},{p[1]}" for p in v)
        els.append(f'<polygon points="{pts}" fill="none" stroke="#333" stroke-width="1.5"/>')
        lps=[((v[3][0]+v[2][0])/2, v[2][1]-14, "middle"),
             ((v[1][0]+v[2][0])/2+14, (v[1][1]+v[2][1])/2, "start"),
             ((v[0][0]+v[1][0])/2, v[0][1]+15, "middle"),
             ((v[3][0]+v[0][0])/2-14, (v[3][1]+v[0][1])/2, "end")]
        for i, (lx, ly, anc) in enumerate(lps):
            if i < len(sides): els.append(_sl(lx, ly, sides[i], anc))

    return f'<svg width="{W}" height="{H}" style="display:block;margin:12px 0">{"".join(els)}</svg>'


def clock_svg(config: dict) -> str:
    hours   = config.get("hours", 3) % 12
    minutes = config.get("minutes", 0) % 60
    cx, cy, r = 110, 110, 96
    els = []
    els.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="white" stroke="#333" stroke-width="2.5"/>')
    for i in range(60):
        ang = math.radians(i*6 - 90); major = i % 5 == 0
        inner = r-(11 if major else 5)
        x1=cx+inner*math.cos(ang); y1=cy+inner*math.sin(ang)
        x2=cx+(r-2)*math.cos(ang); y2=cy+(r-2)*math.sin(ang)
        els.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                   f'stroke="#333" stroke-width="{2 if major else 0.8}"/>')
    for i in range(1, 13):
        ang=math.radians(i*30-90); nr=r-22
        nx=cx+nr*math.cos(ang); ny=cy+nr*math.sin(ang)
        els.append(f'<text x="{nx:.1f}" y="{ny:.1f}" text-anchor="middle" dominant-baseline="middle" '
                   f'font-size="14" font-weight="bold" font-family="Arial" fill="#222">{i}</text>')
    ma=math.radians(minutes*6-90)
    mhx=cx+(r-14)*math.cos(ma); mhy=cy+(r-14)*math.sin(ma)
    els.append(f'<line x1="{cx}" y1="{cy}" x2="{mhx:.1f}" y2="{mhy:.1f}" '
               f'stroke="#333" stroke-width="2" stroke-linecap="round"/>')
    ha=math.radians((hours+minutes/60)*30-90)
    hhx=cx+(r-38)*math.cos(ha); hhy=cy+(r-38)*math.sin(ha)
    els.append(f'<line x1="{cx}" y1="{cy}" x2="{hhx:.1f}" y2="{hhy:.1f}" '
               f'stroke="#333" stroke-width="3.5" stroke-linecap="round"/>')
    els.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="#333"/>')
    return f'<svg width="220" height="220" style="display:block;margin:12px 0">{"".join(els)}</svg>'


def measuring_scale_svg(config: dict) -> str:
    unit       = config.get("unit", "ml")
    mn         = config.get("min", 0)
    mx_val     = config.get("max", 500)
    step       = config.get("step", 100)
    label_step = config.get("labelStep", step)
    pointer    = config.get("pointer", None)
    W, H = 210, 290
    jx,jw,jt,jb = 55,72,30,262
    jh = jb - jt

    def sy(v): return jb - ((v-mn)/(mx_val-mn))*jh if mx_val != mn else jb

    els = []
    if pointer is not None:
        py=sy(pointer); fill_h=jb-py
        els.append(f'<rect x="{jx}" y="{py:.1f}" width="{jw}" height="{fill_h:.1f}" fill="#d0eaff" stroke="none"/>')
        els.append(f'<line x1="{jx}" y1="{py:.1f}" x2="{jx+jw}" y2="{py:.1f}" stroke="#1798d3" stroke-width="2"/>')
    els.append(f'<line x1="{jx}" y1="{jt}" x2="{jx}" y2="{jb}" stroke="#888" stroke-width="1.5"/>')
    els.append(f'<line x1="{jx+jw}" y1="{jt}" x2="{jx+jw}" y2="{jb}" stroke="#888" stroke-width="1.5"/>')
    els.append(f'<line x1="{jx}" y1="{jb}" x2="{jx+jw}" y2="{jb}" stroke="#888" stroke-width="2"/>')
    els.append(f'<line x1="{jx}" y1="{jt}" x2="{jx+jw}" y2="{jt}" stroke="#888" stroke-width="1" stroke-dasharray="4,3"/>')
    n_steps=round((mx_val-mn)/step)
    for i in range(n_steps+1):
        v=mn+i*step; y=sy(v); tlen=14 if v%label_step==0 else 7
        els.append(f'<line x1="{jx+jw}" y1="{y:.1f}" x2="{jx+jw+tlen}" y2="{y:.1f}" stroke="#333" stroke-width="1.5"/>')
        if v % label_step == 0:
            els.append(f'<text x="{jx+jw+18}" y="{y:.1f}" dominant-baseline="middle" '
                       f'font-size="12" font-family="Arial" fill="#333">{v} {unit}</text>')
    return f'<svg width="{W}" height="{H}" style="display:block;margin:12px 0">{"".join(els)}</svg>'


def timetable_html(config: dict) -> str:
    title   = config.get("title", "")
    headers = config.get("headers", [])
    rows    = config.get("rows", [])
    title_html=(f'<div style="font-size:13px;font-family:Arial;font-weight:600;color:#333;'
                f'margin-bottom:8px">{title}</div>') if title else ""
    th_cells="".join(
        f'<th style="border:1.5px solid #999;padding:6px 12px;background:#f0f4f8;font-size:13px;'
        f'font-family:Arial;font-weight:600;text-align:center;white-space:nowrap">{h}</th>'
        for h in headers)
    rows_html=""
    for ri, row in enumerate(rows):
        bg="#fff" if ri%2==0 else "#f8f9fb"; cells=""
        for ci, cell in enumerate(row):
            bold="font-weight:600;" if ci==0 else ""; align="left" if ci==0 else "center"
            cells+=(f'<td style="border:1px solid #ccc;padding:5px 12px;font-size:13px;'
                    f'font-family:Arial;{bold}text-align:{align};white-space:nowrap">{cell}</td>')
        rows_html+=f'<tr style="background:{bg}">{cells}</tr>'
    return (f'{title_html}<table style="border-collapse:collapse;margin:10px 0 14px 0">'
            f'<thead><tr>{th_cells}</tr></thead><tbody>{rows_html}</tbody></table>')


def _qt(text: str) -> str:
    return f'<p style="font-size:15px;font-family:Arial;line-height:1.5;margin:0 0 4px 0">{text}</p>'


def _answer_line(label: str = "") -> str:
    w = "160px" if label and len(label) > 2 else "110px"
    lbl = f'<span style="font-size:15px;font-family:Arial">{label}</span>' if label else ""
    return (
        f'<div style="margin-top:14px;display:flex;align-items:baseline;gap:8px">'
        f'{lbl}<span style="display:inline-block;width:{w};border-bottom:2px solid #333;height:26px"></span>'
        f'</div>'
    )


def _method_box() -> str:
    return (
        '<div style="border:1.5px solid #aaa;background:#f8f8f8;padding:10px 12px;'
        'margin:14px 0 8px 0;min-height:72px;font-size:13px;color:#666;font-style:italic">'
        'Show your method</div>'
    )


def render_body(q: dict) -> str:
    qtype = q.get("type", "write-answer")
    qt = _qt(q.get("questionText", ""))
    opts = q.get("options") or []

    if qtype == "tick-options":
        items = "".join([
            f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">'
            f'<div style="width:18px;height:18px;border:1.5px solid #333;flex-shrink:0"></div>'
            f'<span style="font-size:15px;font-family:Arial">{o}</span></div>'
            for o in opts
        ])
        return qt + f'<div style="margin:12px 0 6px">{items}</div>'

    if qtype == "circle-options":
        items = "".join([
            f'<span style="font-size:16px;font-family:Arial;border:1.5px solid #333;'
            f'border-radius:40px;padding:4px 14px">{o}</span>'
            for o in opts
        ])
        return qt + f'<div style="display:flex;gap:20px;flex-wrap:wrap;margin:12px 0 6px;align-items:center">{items}</div>'

    if qtype == "match":
        left = opts.get("left", []) if isinstance(opts, dict) else []
        right = opts.get("right", []) if isinstance(opts, dict) else []
        lh = "".join([
            f'<div style="border:1.5px solid #333;padding:6px 16px;font-size:15px;font-family:Arial;'
            f'min-width:110px;text-align:center;margin-bottom:10px">{l}</div>' for l in left
        ])
        rh = "".join([
            f'<div style="border:1.5px solid #333;padding:6px 16px;font-size:15px;font-family:Arial;'
            f'min-width:110px;text-align:center;margin-bottom:10px">{r}</div>' for r in right
        ])
        return (
            qt + f'<div style="display:flex;gap:50px;margin:14px 0;align-items:flex-start">'
            f'<div>{lh}</div>'
            f'<div style="padding-top:10px;font-size:12px;color:#999;font-family:Arial">draw lines to match</div>'
            f'<div>{rh}</div></div>'
        )

    if qtype == "order":
        vals = "".join([f'<span style="font-size:16px;font-family:Arial;font-weight:500">{o}</span>' for o in opts])
        boxes = "".join([f'<div style="width:72px;border-bottom:2px solid #333;height:24px"></div>' for _ in opts])
        return (
            qt + f'<div style="margin:14px 0">'
            f'<div style="display:flex;gap:18px;flex-wrap:wrap;margin-bottom:16px">{vals}</div>'
            f'<div style="display:flex;gap:14px;align-items:center">'
            f'<span style="font-size:13px;font-family:Arial;color:#555">smallest</span>'
            f'{boxes}'
            f'<span style="font-size:13px;font-family:Arial;color:#555">largest</span>'
            f'</div></div>'
        )

    if qtype == "sequence":
        items = []
        for i, v in enumerate(opts):
            blank = '<span style="display:inline-block;width:58px;border-bottom:2px solid #1a1a8c;height:24px"></span>'
            val = f'<span style="font-size:18px;font-weight:bold;font-family:Arial">{v}</span>'
            arrow = '<span style="color:#888;font-size:13px">→</span>' if i < len(opts) - 1 else ""
            items.append(
                f'<span style="display:flex;align-items:center;gap:4px">'
                f'{blank if v is None else val}{arrow}</span>'
            )
        return qt + f'<div style="display:flex;gap:6px;align-items:center;margin:14px 0;flex-wrap:wrap">{"".join(items)}</div>'

    if qtype == "explain":
        return qt + '<div style="border:1.5px solid #bbb;background:#fafafa;min-height:72px;margin:12px 0;padding:8px"></div>'

    if qtype == "complete-table":
        tbl = q.get("table") or {}
        headers = tbl.get("headers", [])
        rows = tbl.get("rows", [])
        th = "".join([f'<th style="border:1.5px solid #555;padding:6px 14px;background:#f4f4f4;font-weight:bold">{h}</th>' for h in headers])
        tr_html = ""
        for row in rows:
            tds = "".join([
                f'<td style="border:1.5px solid #555;padding:6px 14px;min-width:80px;text-align:center">'
                + (f'<span style="display:inline-block;width:52px;border-bottom:1.5px solid #1a1a8c"></span>'
                   if cell is None else str(cell))
                + '</td>'
                for cell in row
            ])
            tr_html += f'<tr>{tds}</tr>'
        return qt + f'<table style="border-collapse:collapse;margin:14px 0;font-size:14px;font-family:Arial"><thead><tr>{th}</tr></thead><tbody>{tr_html}</tbody></table>'

    if qtype == "draw-on-grid":
        cfg = q.get("gridConfig") or {}
        svg = coord_grid_svg(cfg)
        note = '<p style="font-size:13px;color:#555;font-style:italic;margin-top:4px">Use a ruler.</p>' if cfg.get("mirrorLine") else ""
        return qt + svg + note

    if qtype == "bar-chart":
        chart = q.get("chart") or {}
        svg = bar_chart_svg(chart)
        return qt + svg + (_method_box() if q.get("showMethod") else "") + _answer_line(q.get("answerLabel", ""))

    if qtype == "pie-chart":
        chart = q.get("chart") or {}
        svg = pie_chart_svg(chart)
        return qt + svg + (_method_box() if q.get("showMethod") else "") + _answer_line(q.get("answerLabel", ""))

    if qtype == "line-graph":
        chart = q.get("chart") or {}
        svg = line_graph_svg(chart)
        return qt + svg + (_method_box() if q.get("showMethod") else "") + _answer_line(q.get("answerLabel", ""))

    if qtype == "angle-diagram":
        cfg = q.get("angleConfig") or {}
        return qt + angle_diagram_svg(cfg) + (_method_box() if q.get("showMethod") else "") + _answer_line(q.get("answerLabel", ""))

    if qtype == "labelled-shape":
        cfg = q.get("shapeConfig") or {}
        return qt + labelled_shape_svg(cfg) + (_method_box() if q.get("showMethod") else "") + _answer_line(q.get("answerLabel", ""))

    if qtype == "clock":
        cfg = q.get("clockConfig") or {}
        return qt + clock_svg(cfg) + _answer_line(q.get("answerLabel", ""))

    if qtype == "measuring-scale":
        cfg = q.get("scaleConfig") or {}
        return qt + measuring_scale_svg(cfg) + _answer_line(q.get("answerLabel", ""))

    if qtype == "timetable":
        cfg = q.get("timetableConfig") or {}
        tbl = timetable_html(cfg)
        return qt + tbl + (_method_box() if q.get("showMethod") else "") + _answer_line(q.get("answerLabel", ""))

    if qtype == "number-line":
        cfg = q.get("gridConfig") or {}
        svg = number_line_svg(cfg)
        return qt + svg + _answer_line("")

    if qtype == "multi-part":
        parts_html = ""
        for p in (q.get("parts") or []):
            pm = p.get("marks", 1)
            parts_html += (
                f'<div style="margin-bottom:16px">'
                f'<p style="font-size:15px;font-family:Arial;margin:0 0 8px 0">'
                f'<strong>{p.get("letter","")}</strong>&nbsp;&nbsp;{p.get("questionText","")}</p>'
                + (_method_box() if p.get("showMethod") else "")
                + _answer_line(p.get("answerLabel", ""))
                + f'<div style="font-size:13px;font-family:Arial;color:#333;text-align:right;margin-top:6px">'
                f'<span style="border-bottom:1.5px solid #333;padding-bottom:2px">'
                f'{pm} {"mark" if pm == 1 else "marks"}</span></div>'
                + '</div>'
            )
        return qt + parts_html

    # default: write-answer
    grid_html = ""
    if q.get("hasGrid") and q.get("gridType") == "coordinate" and q.get("gridConfig"):
        grid_html = coord_grid_svg(q["gridConfig"])
    return qt + grid_html + (_method_box() if q.get("showMethod") else "") + _answer_line(q.get("answerLabel", ""))


def render_question_card(q: dict, num: int) -> str:
    qtype = q.get("type", "write-answer")
    marks = (
        sum(p.get("marks", 1) for p in (q.get("parts") or []))
        if qtype == "multi-part"
        else q.get("marks", 1)
    )
    mark_str = f'{marks} {"mark" if marks == 1 else "marks"}'
    mark_badge = (
        "" if qtype == "multi-part" else
        f'<div style="width:76px;flex-shrink:0;display:flex;align-items:flex-end;justify-content:flex-end">'
        f'<div style="font-size:13px;font-family:Arial;color:#222;border-bottom:1.5px solid #333;'
        f'padding-bottom:2px;padding-right:2px">{mark_str}</div></div>'
    )
    return (
        f'<div style="display:flex;gap:0;padding:22px 0;border-bottom:1px solid #ddd">'
        f'<div style="width:38px;flex-shrink:0;font-size:19px;font-weight:bold;padding-top:1px;font-family:Arial">{num}</div>'
        f'<div style="flex:1">{render_body(q)}</div>'
        f'{mark_badge}</div>'
    )


# ─── API call ────────────────────────────────────────────────────────────────

def generate_questions(topics: list, difficulty: str, count: int) -> list:
    diff_map = {
        "Easier (1 mark)": "Easier — 1-mark questions, straightforward, accessible for pupils who need more support.",
        "Mixed": "Mixed difficulty — a range of 1-mark and 2-mark questions.",
        "Harder (2–3 marks)": "Harder — 2 and 3-mark questions, multi-step, full SATs challenge.",
    }
    diff_note = diff_map.get(difficulty, diff_map["Mixed"])
    topics_str = ", ".join(topics)

    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        api_key = st.session_state.get("manual_api_key", "")

    if not api_key:
        raise ValueError("No API key found. Add ANTHROPIC_API_KEY to Streamlit secrets.")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f'Generate {count} KS2 SATs-style reasoning questions for Year 6 on these topics: "{topics_str}". '
                f'{diff_note}\n\n{Y6_CURRICULUM}\n\nReturn ONLY the JSON array.'
            ),
        }],
    )
    raw = response.content[0].text
    clean = re.sub(r"```json\n?", "", raw)
    clean = re.sub(r"```\n?", "", clean).strip()
    return json.loads(clean)



def _svg_to_drawing(svg_str: str, max_w_mm: float = 155.0):
    """Convert an SVG string to a reportlab Drawing, scaled to fit the page."""
    import tempfile, os
    from reportlab.lib.units import mm as _mm
    try:
        from svglib.svglib import svg2rlg
        with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", delete=False, encoding="utf-8") as f:
            f.write(svg_str); tmp = f.name
        try:
            drw = svg2rlg(tmp)
        finally:
            os.unlink(tmp)
        if drw and drw.width > 0:
            max_w = max_w_mm * _mm
            if drw.width > max_w:
                scale = max_w / drw.width
                drw.width  = max_w
                drw.height = drw.height * scale
                drw.transform = (scale, 0, 0, scale, 0, 0)
        return drw
    except Exception:
        return None


def build_pdf_bytes(questions: list, topics_display: str) -> bytes | None:
    """Build an A4 PDF of the question paper using reportlab + svglib."""
    try:
        from io import BytesIO
        import tempfile, os
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                         HRFlowable, Table, TableStyle)
        from reportlab.platypus.flowables import Flowable
    except ImportError:
        return None

    # ── Custom Flowables ─────────────────────────────────────────────────────

    class _AnswerLine(Flowable):
        def __init__(self, label="", width_mm=80):
            super().__init__()
            self._label = label; self._lw = width_mm * mm
            self.width = self._lw + 50 * mm; self.height = 12 * mm
        def draw(self):
            c = self.canv
            x = 0
            if self._label:
                c.setFont("Helvetica", 11)
                c.drawString(0, 3 * mm, self._label)
                x = c.stringWidth(self._label, "Helvetica", 11) + 5 * mm
            c.setLineWidth(1.2)
            c.line(x, 0, x + self._lw, 0)

    class _ShadedBox(Flowable):
        def __init__(self, label="Show your method", height_mm=28):
            super().__init__()
            self._label = label; self.width = 160 * mm; self.height = height_mm * mm
        def draw(self):
            c = self.canv
            c.setStrokeGray(0.7); c.setFillGray(0.97)
            c.rect(0, 0, self.width, self.height, fill=1, stroke=1)
            if self._label:
                c.setFillGray(0.5); c.setFont("Helvetica-Oblique", 10)
                c.drawString(4 * mm, self.height - 5 * mm, self._label)

    class _MarkBadge(Flowable):
        def __init__(self, text):
            super().__init__(); self._text = text
            self.width = 160 * mm; self.height = 7 * mm
        def draw(self):
            c = self.canv; c.setFont("Helvetica", 10)
            w = c.stringWidth(self._text, "Helvetica", 10)
            x = self.width - w
            c.setLineWidth(0.8); c.line(x, -1, self.width, -1)
            c.drawString(x, 1 * mm, self._text)

    # ── Styles ───────────────────────────────────────────────────────────────
    body   = ParagraphStyle("body",   fontName="Helvetica",        fontSize=11, leading=15, spaceAfter=3)
    meta_s = ParagraphStyle("meta",   fontName="Helvetica",        fontSize=9,  textColor=colors.HexColor("#444444"))
    title_s= ParagraphStyle("title",  fontName="Helvetica-Bold",   fontSize=17, textColor=colors.HexColor("#1a1a8c"), spaceAfter=4)
    ital   = ParagraphStyle("ital",   fontName="Helvetica-Oblique",fontSize=10, textColor=colors.HexColor("#666666"))
    end_s  = ParagraphStyle("end",    fontName="Helvetica",        fontSize=9,  textColor=colors.HexColor("#bbbbbb"), alignment=TA_CENTER)

    # ── SVG helper ───────────────────────────────────────────────────────────
    def _svg(q):
        qtype = q.get("type", "")
        fn_map = {
            "bar-chart":       lambda: bar_chart_svg(q.get("chart") or {}),
            "pie-chart":       lambda: pie_chart_svg(q.get("chart") or {}),
            "line-graph":      lambda: line_graph_svg(q.get("chart") or {}),
            "angle-diagram":   lambda: angle_diagram_svg(q.get("angleConfig") or {}),
            "labelled-shape":  lambda: labelled_shape_svg(q.get("shapeConfig") or {}),
            "clock":           lambda: clock_svg(q.get("clockConfig") or {}),
            "measuring-scale": lambda: measuring_scale_svg(q.get("scaleConfig") or {}),
            "draw-on-grid":    lambda: coord_grid_svg(q.get("gridConfig") or {}),
            "number-line":     lambda: number_line_svg(q.get("gridConfig") or {}),
        }
        fn = fn_map.get(qtype)
        return fn() if fn else None

    # ── Build story ──────────────────────────────────────────────────────────
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=18*mm, rightMargin=18*mm,
                             topMargin=18*mm,  bottomMargin=22*mm)
    story = []

    story += [
        Paragraph("Key Stage 2 Mathematics — Reasoning | Year 6", meta_s),
        Paragraph(f"{topics_display} Practice Questions", title_s),
        HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=5*mm),
    ]

    for qi, q in enumerate(questions, 1):
        qtype = q.get("type", "write-answer")
        marks = (sum(p.get("marks", 1) for p in (q.get("parts") or []))
                 if qtype == "multi-part" else q.get("marks", 1))
        mark_str = f'{marks} {"mark" if marks == 1 else "marks"}'

        # Question text
        story.append(Paragraph(f"<b>{qi}</b>  {q.get('questionText','')}", body))

        # SVG visual
        svg_str = _svg(q)
        if svg_str:
            drw = _svg_to_drawing(svg_str)
            if drw:
                story += [Spacer(1, 2*mm), drw]

        # Timetable
        if qtype == "timetable":
            cfg = q.get("timetableConfig") or {}
            hdrs, rows = cfg.get("headers",[]), cfg.get("rows",[])
            if hdrs and rows:
                tdata = [hdrs] + rows
                col_w = [50*mm] + [28*mm]*(len(hdrs)-1)
                t = Table(tdata, colWidths=col_w)
                t.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,0), colors.HexColor("#f0f4f8")),
                    ("FONTNAME",  (0,0),(-1,0), "Helvetica-Bold"),
                    ("FONTNAME",  (0,1),(0,-1), "Helvetica-Bold"),
                    ("FONTSIZE",  (0,0),(-1,-1), 10),
                    ("ALIGN",     (1,0),(-1,-1), "CENTER"),
                    ("GRID",      (0,0),(-1,-1), 0.8, colors.HexColor("#cccccc")),
                    ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#f8f9fb")]),
                ]))
                story += [Spacer(1,2*mm), t]

        # Complete table
        if qtype == "complete-table":
            td = q.get("table") or {}
            hdrs, rows = td.get("headers",[]), td.get("rows",[])
            if hdrs and rows:
                tdata = [hdrs] + [[("___" if c is None else str(c)) for c in r] for r in rows]
                col_w = [40*mm]*len(hdrs)
                t = Table(tdata, colWidths=col_w)
                t.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,0), colors.HexColor("#f4f4f4")),
                    ("FONTNAME",  (0,0),(-1,0), "Helvetica-Bold"),
                    ("FONTSIZE",  (0,0),(-1,-1), 11),
                    ("ALIGN",     (0,0),(-1,-1), "CENTER"),
                    ("GRID",      (0,0),(-1,-1), 1, colors.HexColor("#555555")),
                ]))
                story += [Spacer(1,2*mm), t]

        # Match
        if qtype == "match":
            opts = q.get("options") or {}
            left  = opts.get("left",[])  if isinstance(opts, dict) else []
            right = opts.get("right",[]) if isinstance(opts, dict) else []
            if left and right:
                tdata = [[l,"",r] for l,r in zip(left, right)]
                t = Table(tdata, colWidths=[55*mm, 50*mm, 55*mm])
                t.setStyle(TableStyle([
                    ("BOX",(0,0),(0,-1),0.8,colors.black),
                    ("BOX",(2,0),(2,-1),0.8,colors.black),
                    ("FONTSIZE",(0,0),(-1,-1),11),
                    ("ALIGN",(0,0),(0,-1),"CENTER"),
                    ("ALIGN",(2,0),(2,-1),"CENTER"),
                ]))
                story += [Spacer(1,2*mm), t]

        # Tick options
        if qtype == "tick-options":
            for o in (q.get("options") or []):
                story.append(Paragraph(f"☐ {o}", body))

        # Circle options
        if qtype == "circle-options":
            opts = q.get("options") or []
            story.append(Paragraph("     ".join(f"( {o} )" for o in opts), body))

        # Order
        if qtype == "order":
            opts = q.get("options") or []
            story.append(Paragraph("  ".join(str(o) for o in opts), body))
            story.append(Paragraph("Write in order, smallest to largest:", ital))
            story += [Spacer(1,2*mm), _AnswerLine(width_mm=60)]

        # Sequence
        if qtype == "sequence":
            opts = q.get("options") or []
            parts = ["―――――" if v is None else str(v) for v in opts]
            story.append(Paragraph("  →  ".join(parts), body))

        # Explain box
        if qtype == "explain":
            story += [Spacer(1,2*mm), _ShadedBox(label="", height_mm=32)]

        # Method box
        if q.get("showMethod") and qtype not in ("explain","multi-part","timetable"):
            story += [Spacer(1,2*mm), _ShadedBox()]

        # Multi-part sub-questions
        if qtype == "multi-part":
            for p in (q.get("parts") or []):
                pm = p.get("marks", 1)
                story.append(Paragraph(f"<b>{p.get('letter','')}</b>  {p.get('questionText','')}", body))
                if p.get("showMethod"):
                    story += [Spacer(1,2*mm), _ShadedBox()]
                story += [Spacer(1,2*mm), _AnswerLine(p.get("answerLabel",""))]
                story.append(Paragraph(f'{pm} {"mark" if pm==1 else "marks"}', ital))
                story.append(Spacer(1,3*mm))
            story.append(_MarkBadge(mark_str))

        else:
            # Answer line for most types
            if qtype not in ("explain","tick-options","circle-options","match","order","sequence",
                             "bar-chart","pie-chart","line-graph","angle-diagram","labelled-shape",
                             "clock","measuring-scale","draw-on-grid","number-line","timetable",
                             "complete-table"):
                story += [Spacer(1,2*mm), _AnswerLine(q.get("answerLabel",""))]
            elif qtype not in ("match","tick-options","circle-options","explain"):
                story += [Spacer(1,2*mm), _AnswerLine(q.get("answerLabel",""))]
            story.append(_MarkBadge(mark_str))

        story += [
            Spacer(1, 3*mm),
            HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd")),
            Spacer(1, 2*mm),
        ]

    story.append(Paragraph("[END OF QUESTIONS]", end_s))

    doc.build(story)
    return buf.getvalue()


# ─── Session state ────────────────────────────────────────────────────────────

for key, default in [
    ("questions", []),
    ("show_ms", False),
    ("topics_used", []),
    ("diff_used", "Mixed"),
    ("count_used", 4),
    ("pdf_bytes", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        '<p style="font-size:13px;font-weight:700;color:#1798d3;margin:4px 0 12px 0">'
        'KS2 SATs Reasoning</p>',
        unsafe_allow_html=True,
    )

    # API key — only show if not in secrets
    has_secret_key = False
    try:
        _ = st.secrets["ANTHROPIC_API_KEY"]
        has_secret_key = True
    except Exception:
        pass

    if not has_secret_key:
        with st.expander("🔑 API key"):
            manual_key = st.text_input("Anthropic API key", type="password",
                                       placeholder="sk-ant-…", key="manual_api_key_input")
            if manual_key:
                st.session_state["manual_api_key"] = manual_key
                st.caption("Key saved for this session.")

    # ── Topic selection ───────────────────────────────────────────────────────
    st.markdown(
        '<p style="font-size:13px;font-weight:700;color:#1a2a3a;margin:0 0 6px 0">Select topics</p>',
        unsafe_allow_html=True
    )

    selected_topics = []
    for strand, topic_list in TOPICS.items():
        with st.expander(strand, expanded=False):
            # Select all toggle
            all_key = f"all_{strand}"
            select_all = st.checkbox("Select all", key=all_key)
            st.markdown('<div style="height:2px;background:#eee;margin:4px 0 6px 0"></div>', unsafe_allow_html=True)
            for topic in topic_list:
                cb_key = f"cb_{strand}_{topic}"
                checked = st.checkbox(topic, key=cb_key, value=select_all)
                if checked or select_all:
                    selected_topics.append(topic)

    # Deduplicate while preserving order
    seen = set()
    unique_topics = []
    for t in selected_topics:
        if t not in seen:
            seen.add(t)
            unique_topics.append(t)
    selected_topics = unique_topics

    st.divider()

    difficulty = st.radio(
        "Difficulty",
        ["Easier (1 mark)", "Mixed", "Harder (2–3 marks)"],
        index=1,
        key="difficulty_radio",
    )
    count = st.selectbox(
        "Number of questions",
        [2, 3, 4, 5, 6],
        index=2,
        key="count_select",
    )

    st.divider()

    can_generate = bool(selected_topics)
    generate_clicked = st.button(
        "Generate questions",
        type="primary",
        use_container_width=True,
        disabled=not can_generate,
        key="generate_btn",
    )

    if st.session_state.questions:
        regen_clicked = st.button(
            "↺  Regenerate",
            use_container_width=True,
            key="regen_btn",
        )
    else:
        regen_clicked = False

    if not can_generate:
        st.caption("Select at least one topic above.")

    if st.session_state.questions:
        st.divider()
        ms_label = "Hide mark scheme" if st.session_state.show_ms else "Show mark scheme"
        if st.button(ms_label, use_container_width=True, key="ms_btn"):
            st.session_state.show_ms = not st.session_state.show_ms
            st.rerun()
        pdf_bytes = st.session_state.get("pdf_bytes")
        if pdf_bytes:
            st.download_button(
                "⬇️  Download PDF",
                data=pdf_bytes,
                file_name="SATs_Reasoning_Questions.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="pdf_dl_btn",
            )
        else:
            st.caption("PDF unavailable — install weasyprint.")

# ─── Generation logic ─────────────────────────────────────────────────────────

do_generate = generate_clicked and can_generate
do_regen = regen_clicked and bool(st.session_state.topics_used)

if do_generate or do_regen:
    topics_to_use = selected_topics if do_generate else st.session_state.topics_used
    diff_to_use = difficulty
    count_to_use = count

    with st.spinner("Generating questions…"):
        try:
            qs = generate_questions(topics_to_use, diff_to_use, count_to_use)
            st.session_state.questions = qs
            st.session_state.show_ms = False
            st.session_state.topics_used = topics_to_use
            st.session_state.diff_used = diff_to_use
            st.session_state.count_used = count_to_use
            topics_disp = ", ".join(topics_to_use)
            with st.spinner("Building PDF…"):
                st.session_state.pdf_bytes = build_pdf_bytes(qs, topics_disp)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to generate questions — {e}")

# ─── Main area ────────────────────────────────────────────────────────────────

# Header — same pattern as all WFA Streamlit apps
if LOGO_PATH.exists():
    logo_b64 = _b64_img(LOGO_PATH)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:18px;margin-bottom:6px;">'
        f'<img src="data:image/jpeg;base64,{logo_b64}" style="height:60px;width:auto;">'
        f'<span style="font-size:1.75rem;font-weight:700;color:#1798d3;">'
        f'WFA KS2 SATs Reasoning</span></div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<span style="font-size:1.75rem;font-weight:700;color:#1798d3;">'
        'WFA KS2 SATs Reasoning</span>',
        unsafe_allow_html=True,
    )
st.divider()

questions = st.session_state.questions

if questions:
    topics_display = ", ".join(st.session_state.topics_used)

    # Question paper
    q_cards = "".join([render_question_card(q, i + 1) for i, q in enumerate(questions)])

    paper_html = f"""
<div style="background:white;box-shadow:0 2px 16px rgba(0,0,0,0.10);padding:40px 52px 52px 52px;
            max-width:820px;margin:0 auto;font-family:Arial">
    <div style="border-bottom:2.5px solid #222;padding-bottom:12px;margin-bottom:4px">
        <div style="font-size:13px;color:#555;margin-bottom:3px">
            Key Stage 2 Mathematics — Reasoning &nbsp;|&nbsp; Year 6
        </div>
        <div style="font-size:21px;font-weight:bold;color:#1a1a8c">{topics_display} Practice Questions</div>
    </div>
    {q_cards}
    <div style="text-align:center;margin-top:30px;padding-top:14px;border-top:1px solid #eee;
                font-size:12px;color:#bbb">[END OF QUESTIONS]</div>
</div>"""

    st.markdown(paper_html, unsafe_allow_html=True)

    # Mark scheme
    if st.session_state.show_ms:
        ms_rows = ""
        for i, q in enumerate(questions):
            mks = (
                sum(p.get("marks", 1) for p in (q.get("parts") or []))
                if q.get("type") == "multi-part"
                else q.get("marks", 1)
            )
            ms_rows += (
                f'<tr style="border-bottom:1px solid #ccd">'
                f'<td style="padding:8px 10px 8px 0;font-weight:bold;vertical-align:top">{i+1}</td>'
                f'<td style="padding:8px 10px;vertical-align:top">{q.get("answer","")}</td>'
                f'<td style="padding:8px 10px;vertical-align:top">{mks}m</td>'
                f'<td style="padding:8px 0 8px 10px;vertical-align:top;color:#444">{q.get("markScheme","")}</td>'
                f'</tr>'
            )

        st.markdown(f"""
<div style="background:#eef2ff;border:1.5px solid #aab;border-radius:6px;padding:20px 24px;
            margin-top:22px;max-width:820px;margin-left:auto;margin-right:auto">
    <h3 style="font-family:Arial;font-size:16px;color:#1a1a8c;margin:0 0 14px 0">Mark Scheme</h3>
    <table style="width:100%;border-collapse:collapse;font-family:Arial;font-size:14px">
        <thead>
            <tr style="border-bottom:1.5px solid #aab">
                <th style="text-align:left;padding:6px 10px 6px 0;color:#333">Qu.</th>
                <th style="text-align:left;padding:6px 10px;color:#333">Answer</th>
                <th style="text-align:left;padding:6px 10px;color:#333">Mark</th>
                <th style="text-align:left;padding:6px 10px;color:#333">Additional guidance</th>
            </tr>
        </thead>
        <tbody>{ms_rows}</tbody>
    </table>
</div>""", unsafe_allow_html=True)

else:
    # Empty state
    st.markdown("""
<div style="text-align:center;padding:80px 0;max-width:820px;margin:0 auto">
    <div style="font-size:52px;margin-bottom:14px">✏️</div>
    <div style="font-size:17px;color:#666;margin-bottom:8px;font-family:Arial;font-weight:600">
        Select topics in the sidebar, then click Generate
    </div>
    <div style="font-size:13px;color:#999;font-family:Arial">
        Number &nbsp;·&nbsp; Fractions &nbsp;·&nbsp; Algebra &nbsp;·&nbsp; Geometry &nbsp;·&nbsp; Statistics &nbsp;·&nbsp; Ratio and more
    </div>
</div>""", unsafe_allow_html=True)
