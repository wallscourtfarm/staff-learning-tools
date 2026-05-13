import streamlit as st
import anthropic
import json
import re

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="KS2 SATs Reasoning — Question Generator",
    page_icon="✏️",
    layout="wide",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Sidebar background */
    [data-testid="stSidebar"] { background: #f4f6f8; }
    [data-testid="stSidebar"] > div:first-child { padding-top: 0; }

    /* Primary button colour */
    .stButton > button[kind="primary"] {
        background-color: #1798d3 !important;
        border-color: #1798d3 !important;
        color: white !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #1280b8 !important;
        border-color: #1280b8 !important;
    }
    .stButton > button {
        border-radius: 5px !important;
    }

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
    [data-testid="stSidebar"] .stCheckbox label {
        font-size: 13px;
    }
    [data-testid="stSidebar"] .stCheckbox { margin-bottom: 2px; }

    /* Main area */
    .block-container { padding-top: 24px; padding-bottom: 48px; }

    /* Print styles */
    @media print {
        [data-testid="stSidebar"],
        [data-testid="stToolbar"],
        [data-testid="stHeader"],
        #MainMenu,
        .stButton,
        .no-print,
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
  "answerLabel": "km",
  "showMethod": false,
  "hasGrid": false,
  "gridType": null,
  "gridConfig": null,
  "options": null,
  "table": null,
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

gridConfig for coordinate:
{"xMin":-5,"xMax":5,"yMin":-5,"yMax":5,"points":[{"label":"A","x":3,"y":2}],"mirrorLine":null}
mirrorLine: "vertical" | "horizontal" | null

gridConfig for number-line:
{"min":0,"max":1,"marked":[0,0.5,1],"labels":["0","0.5","1"]}

Set showMethod:true when marks >= 2.
Vary question types across the set — do not make all questions "write-answer".
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


# ─── Question HTML renderers ──────────────────────────────────────────────────

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


# ─── Session state ────────────────────────────────────────────────────────────

for key, default in [
    ("questions", []),
    ("show_ms", False),
    ("topics_used", []),
    ("diff_used", "Mixed"),
    ("count_used", 4),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="background:#1798d3;color:white;padding:16px 18px;border-radius:8px;margin-bottom:18px">
        <div style="font-size:10px;letter-spacing:1.5px;text-transform:uppercase;opacity:0.75;font-family:Arial;font-weight:600">
            Wallscourt Farm Academy
        </div>
        <div style="font-size:18px;font-weight:700;margin-top:4px;font-family:Arial;line-height:1.2">
            KS2 SATs Reasoning
        </div>
        <div style="font-size:11px;opacity:0.8;margin-top:3px;font-family:Arial">
            Question Generator
        </div>
    </div>
    """, unsafe_allow_html=True)

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
        if st.button("🖨️  Print / Save PDF", use_container_width=True, key="print_btn"):
            st.markdown("<script>window.print()</script>", unsafe_allow_html=True)

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
            st.rerun()
        except Exception as e:
            st.error(f"Failed to generate questions — {e}")

# ─── Main area ────────────────────────────────────────────────────────────────

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
