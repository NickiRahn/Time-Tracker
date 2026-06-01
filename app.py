import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import os
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="NR Calendar Audit Dashboard", page_icon="📅", layout="wide", initial_sidebar_state="expanded")

TASK_COLORS = {
    "GTD":"#888780","LMA":"#D4537E","MAPCO":"#3266ad","MAGNUM":"#639922","MCP":"#0C7C59",
    "MCC":"#1D9E75","M-COMPANIES":"#1D9E75","MTI":"#0C447C","MFE":"#4B1528","TLM/NR 1:1":"#7F77DD",
    "OFFICE CLOSED":"#cccccc","PTO/SICK TIME":"#F4A261","PROFESSIONAL DEVLOPMENT":"#D85A30",
    "PROFESSIONAL DEVELOPMENT":"#D85A30","COMMUTING/TRAVEL":"#BA7517","Commuting/Travel":"#BA7517",
    "NETWORKING/PEER GROUPS":"#A32D2D","CORP DEV":"#2B2D42",
}
GOALS_2026 = {
    "GTD":0.10,"LMA":0.025,"MAPCO":0.25,"MAGNUM":0.01,"MCP":0.04,"MCC":0.10,"MTI":0.25,"MFE":0.02,
    "TLM/NR 1:1":0.02,"OFFICE CLOSED":0.03,"PTO/SICK TIME":0.10,"PROFESSIONAL DEVELOPMENT":0.015,
    "COMMUTING/TRAVEL":0.025,"NETWORKING/PEER GROUPS":0.015,
}
COMPANY_TASKS = {"MAPCO","MAGNUM","MCP","MCC","M-COMPANIES","MTI","MFE","CORP DEV"}
# Excluded from the "Company Support vs All Other DUTIES" comparison (non-duty buckets).
# To count commuting as a duty, remove "COMMUTING/TRAVEL" from this set.
NON_DUTY = {"PTO/SICK TIME","OFFICE CLOSED","COMMUTING/TRAVEL"}
DATA_FILE = "saved_data.json"
MONTH_ORDER = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
MONTH_FULL = {"JANUARY":"JAN","FEBRUARY":"FEB","MARCH":"MAR","APRIL":"APR","MAY":"MAY","JUNE":"JUN","JULY":"JUL","AUGUST":"AUG","SEPTEMBER":"SEP","OCTOBER":"OCT","NOVEMBER":"NOV","DECEMBER":"DEC"}
MONTH_LONG = {v:k.title() for k,v in MONTH_FULL.items()}

# ── Theme bundling — applied WITHIN each task only, never across tasks. ───────
# First match wins. Add/edit lines as your projects change.
# Each line: ("Theme Name", ["keyword", "keyword", ...])
THEME_RULES = [
    ("Project Lily",            ["lily"]),
    ("EOS Facilitation",        ["eos", "level 10", "leve l10", "level l10", "l10"]),
    ("Strategy & Training",     ["strateg"]),
    ("Insurance",               ["insurance", "lockton", "broker", "flood and peterson", "ima meeting", " ima "]),
    ("Corp Dev / M&A",          ["corp dev", "corp -", "corp  -", "m&a", "qofe", "diligence", "data room"]),
    ("Marketing",               ["marketing", "huebner", "ashton"]),
    ("Budget Review",           ["budget"]),
    ("Award Event",             ["award"]),
    ("Board / BOD",             ["bod", "board meeting", "board", "advisory board"]),
    ("Event Planning",          ["centerpiece", "party", "75 year", "celebration", "event", "watches", "gift"]),
    ("Performance Review Prep", ["annual review", "feedback", "paf", "performance", "review template", "recap with taylor", "prep for 1:1"]),
    ("HR / Legal",              ["legal", "claim", "amanda", "amy", " hr", "re: hr"]),
    ("1:1s",                    ["1:1"]),
    ("Paycom Admin",            ["paycom"]),
    ("Bonus Calculations",      ["bonus"]),
    ("Syspro",                  ["syspro"]),
    ("401k",                    ["401k"]),
    ("CFO Search",              ["cfo"]),
    ("AI / Tooling",            ["gem", "trello", "app review", "review app", "karmak"]),
    ("Email & Admin",           ["email", "expenses", "docking", "calendar audit"]),
    ("IT Support",              ["it and", "it check", "it assistance", "it assist"]),
    ("Commuting",               ["to mapco", "commute", "drive", "to home", "to boulder", "to store", "picking up", "drop "]),
    ("Holiday / PTO",           ["memorial", "holiday", "pto", "sick"]),
    ("Networking",              ["vistage", "peer group"]),
]
THEME_MIN_HOURS = 1.0   # themes below this (within a task) are dropped from summaries
THEME_TOP_N = 4         # max themes shown per task

def theme_for(desc):
    d = str(desc).lower()
    for theme, kws in THEME_RULES:
        for kw in kws:
            if kw in d:
                return theme
    return re.sub(r"\s+", " ", str(desc)).strip().title()

def normalize_task(name):
    if not isinstance(name, str): return None
    upper = name.strip().upper()
    alias = {"M-COMPANIES":"MCC","M COMPANIES":"MCC","CORP DEV":"MAPCO","PROF DEV":"PROFESSIONAL DEVELOPMENT",
             "PROFESSIONAL DEVLOPMENT":"PROFESSIONAL DEVELOPMENT","PTO":"PTO/SICK TIME","OFFICE CLOSED/HOLIDAY":"OFFICE CLOSED"}
    return alias.get(upper, upper)

def task_color(task):
    return TASK_COLORS.get(task, TASK_COLORS.get(task.upper(), "#999999"))

def parse_duration_to_mins(d):
    if pd.isna(d): return 0
    d = str(d).strip(); total = 0
    h = re.search(r"(\d+)\s*h", d); m = re.search(r"(\d+)\s*m", d)
    if h: total += int(h.group(1))*60
    if m: total += int(m.group(1))
    if not h and not m:
        try: total = float(d)*60
        except ValueError: total = 0
    return total

def parse_filename_period(filename):
    name = os.path.splitext(filename)[0].upper()
    ym = re.search(r"(20\d\d)", name)
    year = int(ym.group(1)) if ym else None
    month = None
    for full, abbr in MONTH_FULL.items():
        if full in name: month = abbr; break
    if not month:
        for abbr in MONTH_ORDER:
            if re.search(rf"\b{abbr}\b", name): month = abbr; break
    return year, month

def load_saved_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except (json.JSONDecodeError, IOError): return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)

def parse_workinghours_file(uploaded_file, filename):
    try:
        df = pd.read_excel(uploaded_file)
    except Exception as e:
        return None, None, None, f"Could not open file: {e}"
    if not {"Day","Task","Duration"}.issubset(set(df.columns)):
        return None, None, None, f"Missing expected columns. Found: {list(df.columns)}. Need: Day, Task, Duration."
    df = df.dropna(subset=["Task"])
    df = df[df["Task"].astype(str).str.strip().str.upper() != "TOTAL"]
    df = df[df["Task"].astype(str).str.strip() != ""]
    df["mins"] = df["Duration"].apply(parse_duration_to_mins)
    year, month = parse_filename_period(filename)
    if (year is None or month is None) and "Day" in df.columns:
        try:
            fd = pd.to_datetime(df["Day"].dropna().iloc[0])
            year = year or fd.year; month = month or MONTH_ORDER[fd.month-1]
        except Exception: pass
    if year is None or month is None:
        return None, None, None, "Couldn't determine month/year. Name the file like 'WorkingHours_May_2026.xlsx'."

    df["canon"] = df["Task"].apply(normalize_task)
    df["desc"] = df["Work unit description"].fillna("") if "Work unit description" in df.columns else ""
    df["day_str"] = pd.to_datetime(df["Day"]).dt.strftime("%b %d")
    df["theme"] = df["desc"].apply(lambda d: theme_for(d) if str(d).strip() else None)

    summary = df.groupby("canon")["mins"].sum().apply(lambda m: m/60.0).to_dict()

    # Themes computed WITHIN each task separately. {task: [[theme, hours], ...]}
    themes = {}
    for task, g in df.groupby("canon"):
        themed = g.dropna(subset=["theme"])
        s = themed.groupby("theme")["mins"].sum().sort_values(ascending=False)
        themes[task] = [[t, round(mins/60.0, 2)] for t, mins in s.items()]

    df["iso"] = pd.to_datetime(df["Day"]).dt.strftime("%Y-%m-%d")
    daily_series = df.groupby("iso")["mins"].sum()
    daily = {iso: round(daily_series[iso]/60.0, 2) for iso in sorted(daily_series.index)}

    detail = []
    if "Start" in df.columns and "End" in df.columns:
        d2 = df.dropna(subset=["Start","End"]).copy()
        d2["Start_str"] = pd.to_datetime(d2["Start"]).dt.strftime("%H:%M")
        d2["End_str"] = pd.to_datetime(d2["End"]).dt.strftime("%H:%M")
        for _, r in d2.iterrows():
            detail.append({"day":r["day_str"],"task":str(r["Task"]).strip(),
                "desc":"" if pd.isna(r.get("Work unit description")) else str(r["Work unit description"]),
                "start":r["Start_str"],"end":r["End_str"],"mins":r["mins"]})

    record = {"summary":summary, "themes":themes, "daily":daily, "detail":detail}
    return year, month, record, None

def top_themes(theme_list, min_h=THEME_MIN_HOURS, n=THEME_TOP_N):
    out = [(name, h) for name, h in theme_list if h >= min_h]
    return out[:n]

def traffic_light(actual_pct, goal_pct):
    if goal_pct == 0: return "green"
    ratio = actual_pct/goal_pct
    if 0.8 <= ratio <= 1.3: return "green"
    if 0.5 <= ratio < 0.8 or 1.3 < ratio <= 1.7: return "yellow"
    return "red"

def make_donut(task_hours, title=""):
    items = sorted([(t,h) for t,h in task_hours.items() if h>0], key=lambda x:-x[1])
    tasks = [t for t,_ in items]; values = [h for _,h in items]
    fig = go.Figure(go.Pie(labels=tasks, values=values, marker_colors=[task_color(t) for t in tasks],
        hole=0.55, textinfo="none", hovertemplate="<b>%{label}</b><br>%{value:.1f}h (%{percent})<extra></extra>"))
    fig.update_layout(title=dict(text=title, font=dict(size=13), x=0.5, xanchor="center"),
        showlegend=True, legend=dict(font=dict(size=10)), margin=dict(t=50,b=20,l=10,r=10),
        height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

def _fmt_day(iso):
    try: return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %d")
    except Exception: return iso

def make_daily_bars(daily):
    isos = sorted(daily.keys())
    days = [_fmt_day(d) for d in isos]; hours = [daily[d] for d in isos]
    fig = go.Figure(go.Bar(x=days, y=hours, marker_color="#3266ad", hovertemplate="%{x}<br>%{y:.1f}h<extra></extra>"))
    fig.update_layout(height=300, margin=dict(t=10,b=70,l=0,r=10), yaxis=dict(title="Hours", gridcolor="#f0ede8"),
        xaxis=dict(tickangle=-60, tickfont=dict(size=9)), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", bargap=0.25)
    return fig

def make_company_distribution(task_hours):
    """Pie of only the direct-company tasks, each its own slice."""
    comp = {t: h for t, h in task_hours.items() if t in COMPANY_TASKS and h > 0}
    if not comp: return None
    return make_donut(comp, "Company Support Distribution")

def make_support_vs_other(task_hours):
    """Company Support vs All Other Duties (excludes NON_DUTY buckets)."""
    comp = sum(h for t, h in task_hours.items() if t in COMPANY_TASKS)
    other = sum(h for t, h in task_hours.items() if t not in COMPANY_TASKS and t not in NON_DUTY)
    if comp + other == 0: return None
    fig = go.Figure(go.Pie(labels=["Company Support", "All Other Duties"], values=[comp, other],
        marker_colors=["#3266ad", "#D85A30"], hole=0.55, textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value:.1f}h (%{percent})<extra></extra>"))
    fig.update_layout(title=dict(text="Company Support vs. All Other Duties", font=dict(size=13), x=0.5, xanchor="center"),
        showlegend=True, legend=dict(font=dict(size=10), orientation="h", y=-0.05),
        margin=dict(t=50,b=20,l=10,r=10), height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

def weekly_totals(daily):
    """Sunday–Saturday weekly buckets from ISO-dated daily hours."""
    weeks = {}
    for iso, hrs in daily.items():
        try: d = datetime.strptime(iso, "%Y-%m-%d")
        except Exception: continue
        start = d - timedelta(days=(d.weekday() + 1) % 7)  # back up to Sunday
        weeks[start] = weeks.get(start, 0) + hrs
    out = []
    for start in sorted(weeks):
        end = start + timedelta(days=6)
        out.append((f"{start.strftime('%b %d')} – {end.strftime('%b %d')}", round(weeks[start], 2)))
    return out

def make_weekly_bars(daily):
    wk = weekly_totals(daily)
    if not wk: return None
    labels = [w[0] for w in wk]; hours = [w[1] for w in wk]
    fig = go.Figure(go.Bar(x=labels, y=hours, marker_color="#1D9E75",
        text=[f"{h:.1f}h" for h in hours], textposition="outside",
        hovertemplate="%{x}<br>%{y:.1f}h<extra></extra>"))
    fig.update_layout(height=300, margin=dict(t=20,b=50,l=0,r=10),
        yaxis=dict(title="Hours", gridcolor="#f0ede8"),
        xaxis=dict(tickfont=dict(size=10)), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", bargap=0.3)
    return fig

# Direct-company entities, ordered for consistent chart coloring/legend
ENTITY_ORDER = ["MAPCO", "MCC", "MTI", "MFE", "MAGNUM", "MCP", "M-COMPANIES", "CORP DEV"]

def _entities_present(month_task_hours_list):
    totals = {}
    for th in month_task_hours_list:
        for t, h in th.items():
            if t in COMPANY_TASKS:
                totals[t] = totals.get(t, 0) + h
    present = [e for e in ENTITY_ORDER if totals.get(e, 0) > 0]
    # include any company task not in ENTITY_ORDER, by total desc
    extras = sorted([t for t in totals if t not in ENTITY_ORDER and totals[t] > 0], key=lambda t:-totals[t])
    return present + extras, totals

def make_entity_grouped_bars(labels, month_task_hours_list):
    entities, _ = _entities_present(month_task_hours_list)
    if not entities: return None
    fig = go.Figure()
    for e in entities:
        y = [th.get(e, 0) for th in month_task_hours_list]
        fig.add_trace(go.Bar(name=e, x=labels, y=y, marker_color=task_color(e),
            hovertemplate=f"<b>{e}</b><br>%{{x}}: %{{y:.1f}}h<extra></extra>"))
    fig.update_layout(barmode="group", height=340, margin=dict(t=10,b=40,l=0,r=10),
        yaxis=dict(title="Hours", gridcolor="#f0ede8"), xaxis=dict(tickfont=dict(size=11)),
        legend=dict(orientation="h", y=-0.2, font=dict(size=10)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", bargap=0.25, bargroupgap=0.05)
    return fig

def make_entity_distribution(month_task_hours_list, title="Entity Support — Totals"):
    entities, totals = _entities_present(month_task_hours_list)
    if not entities: return None
    comp = {e: totals[e] for e in entities}
    return make_donut(comp, title)

def make_entity_stacked_area(labels, month_task_hours_list):
    entities, _ = _entities_present(month_task_hours_list)
    if not entities or len(labels) < 2: return None
    fig = go.Figure()
    for e in entities:
        y = [th.get(e, 0) for th in month_task_hours_list]
        fig.add_trace(go.Scatter(name=e, x=labels, y=y, mode="lines", stackgroup="one",
            line=dict(color=task_color(e), width=0.5), fillcolor=task_color(e),
            hovertemplate=f"<b>{e}</b><br>%{{x}}: %{{y:.1f}}h<extra></extra>"))
    fig.update_layout(height=340, margin=dict(t=10,b=40,l=0,r=10),
        yaxis=dict(title="Hours", gridcolor="#f0ede8"), xaxis=dict(tickfont=dict(size=11)),
        legend=dict(orientation="h", y=-0.2, font=dict(size=10)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

def make_goal_bars(task_hours, total_hours):
    if total_hours == 0: return None
    rows = sorted([(t, task_hours.get(t,0)/total_hours*100, g*100, task_color(t)) for t,g in GOALS_2026.items()], key=lambda r:-r[1])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[r[0] for r in rows], y=[r[1] for r in rows], marker_color=[r[3] for r in rows],
        name="Actual %", hovertemplate="%{x}<br>Actual: %{y:.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=[r[0] for r in rows], y=[r[2] for r in rows], mode="markers", name="2026 Goal",
        marker=dict(symbol="line-ew", size=18, color="#1a1917", line=dict(color="#1a1917", width=3)),
        hovertemplate="%{x}<br>Goal: %{y:.1f}%<extra></extra>"))
    fig.update_layout(height=340, margin=dict(t=10,b=90,l=0,r=10), yaxis=dict(title="% of total hours", gridcolor="#f0ede8"),
        xaxis=dict(tickangle=-35, tickfont=dict(size=10)), legend=dict(orientation="h", y=1.1, font=dict(size=11)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", bargap=0.35)
    return fig

def make_trend(monthly_dict, tasks):
    sk = sorted(monthly_dict.keys(), key=lambda k:(k[0], MONTH_ORDER.index(k[1])))
    x = [f"{m} {y}" for y,m in sk]
    fig = go.Figure()
    for task in tasks:
        y = [monthly_dict[k].get(task,0) for k in sk]
        if sum(y)==0: continue
        fig.add_trace(go.Scatter(x=x, y=y, name=task, mode="lines+markers",
            line=dict(color=task_color(task), width=2), marker=dict(size=6),
            hovertemplate=f"<b>{task}</b><br>%{{x}}: %{{y:.1f}}h<extra></extra>"))
    fig.update_layout(height=340, margin=dict(t=20,b=60,l=0,r=10), legend=dict(font=dict(size=10), orientation="h", y=-0.3),
        yaxis=dict(title="Hours", gridcolor="#f0ede8"), xaxis=dict(gridcolor="#f0ede8"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified")
    return fig

def generate_commentary(task_hours, total_hours):
    if total_hours == 0: return []
    lines = []
    for task, goal_pct in GOALS_2026.items():
        if goal_pct == 0: continue
        ah = task_hours.get(task,0); ap = ah/total_hours; ratio = ap/goal_pct
        if ratio > 1.5: lines.append(f"🔴 **{task}** is at {ap*100:.1f}% — {ratio:.1f}× your {goal_pct*100:.0f}% goal. Consider rebalancing.")
        elif ratio > 1.25: lines.append(f"🟡 **{task}** is slightly above goal ({ap*100:.1f}% vs {goal_pct*100:.0f}%).")
        elif ratio < 0.5 and ah > 0: lines.append(f"🟡 **{task}** is well below goal ({ap*100:.1f}% vs {goal_pct*100:.0f}%).")
    if not lines: lines.append("✅ All tasks are tracking close to 2026 goals.")
    return lines

def build_email_text(task_hours, themes_by_task, total, month_label, task_min_pct=0.01):
    lines = [f"Here is my time audit for {month_label} and a breakdown of key areas of time usage:", ""]
    for task, hrs in sorted(task_hours.items(), key=lambda x:-x[1]):
        if hrs <= 0 or (total and hrs/total < task_min_pct): continue
        pct = hrs/total*100 if total else 0
        lines.append(f"{task}: {hrs:.1f} hrs ({pct:.0f}%)")
        for name, _ in top_themes(themes_by_task.get(task, [])):
            lines.append(f"   - {name}")
        lines.append("")
    return "\n".join(lines)

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.metric-card { background:white; border:1px solid #e8e5e0; border-radius:12px; padding:1.1rem 1.25rem; }
.metric-label { font-size:0.72rem; color:#7a7874; font-family:'DM Mono',monospace; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:4px; }
.metric-value { font-size:1.7rem; font-weight:600; color:#1a1917; letter-spacing:-0.02em; line-height:1.1; }
.metric-sub { font-size:0.78rem; color:#7a7874; margin-top:2px; }
.section-header { font-size:1.1rem; font-weight:600; color:#1a1917; margin:1.5rem 0 0.75rem 0; padding-bottom:6px; border-bottom:1.5px solid #e8e5e0; }
.commentary-box { background:#f8f6f2; border-left:3px solid #3266ad; border-radius:0 8px 8px 0; padding:0.85rem 1rem; margin:0.5rem 0; font-size:0.875rem; color:#1a1917; }
.upload-hint { background:#f0f4ff; border:1px dashed #3266ad; border-radius:10px; padding:1.5rem; text-align:center; color:#3266ad; font-size:0.9rem; }
.task-summary { background:white; border:1px solid #e8e5e0; border-left:4px solid #3266ad; border-radius:8px; padding:0.9rem 1.1rem; margin-bottom:0.75rem; }
.task-title { font-size:1.05rem; font-weight:600; color:#1a1917; }
.task-hours { font-family:'DM Mono',monospace; font-size:0.9rem; color:#3266ad; font-weight:500; }
.task-bullet { font-size:0.875rem; color:#444; margin:3px 0 3px 14px; }
.theme-h { color:#7a7874; font-family:'DM Mono',monospace; font-size:0.8rem; }
</style>""", unsafe_allow_html=True)

def get_summary(entry): return entry.get("summary", {}) if isinstance(entry, dict) else {}
def get_themes(entry): return entry.get("themes", {}) if isinstance(entry, dict) else {}
def get_daily(entry): return entry.get("daily", {}) if isinstance(entry, dict) else {}

def render_task_cards(task_hours, themes_by_task, total):
    for task, hrs in sorted(task_hours.items(), key=lambda x:-x[1]):
        if hrs <= 0: continue
        pct = hrs/total*100 if total else 0
        bullets = "".join(
            f'<div class="task-bullet">• {name} <span class="theme-h">({h:.1f}h)</span></div>'
            for name, h in top_themes(themes_by_task.get(task, []))
        )
        st.markdown(
            f'<div class="task-summary"><span class="task-title">{task}</span> '
            f'<span class="task-hours">{hrs:.1f} hrs ({pct:.0f}%)</span>{bullets}</div>',
            unsafe_allow_html=True)

def main():
    with st.sidebar:
        st.markdown("## 📅 NR Calendar Audit")
        st.markdown("---")
        st.markdown("### Upload Monthly Report")
        st.caption("Name files like **WorkingHours_May_2026.xlsx**")
        uploaded = st.file_uploader("Drop your monthly WorkingHours export", type=["xlsx","xls"], accept_multiple_files=True)
        st.markdown("---")
        view = st.radio("View", ["📊 Monthly","📈 Quarterly","🗓 Annual","⚡ Context Switching"], label_visibility="collapsed")
        st.markdown("---")
        saved = load_saved_data()
        if saved:
            st.markdown(f"**{len(saved)} month(s) stored**")
            for k in sorted(saved.keys(), key=lambda k:(int(k.split('_')[0]), MONTH_ORDER.index(k.split('_')[1]))):
                st.caption(f"• {k.split('_')[1]} {k.split('_')[0]}")
            if st.button("🗑 Clear all data", use_container_width=True):
                save_data({}); st.rerun()

    if uploaded:
        saved = load_saved_data(); msgs = []
        for uf in uploaded:
            year, month, record, err = parse_workinghours_file(uf, uf.name)
            if err: msgs.append(("error", f"{uf.name}: {err}")); continue
            saved[f"{year}_{month}"] = record
            msgs.append(("success", f"Loaded {month} {year} ({sum(record['summary'].values()):.0f}h)"))
        save_data(saved)
        for kind, msg in msgs:
            (st.sidebar.success if kind=="success" else st.sidebar.error)(("✅ " if kind=="success" else "⚠️ ")+msg)

    saved = load_saved_data()

    if view == "📊 Monthly":
        st.markdown("# Monthly Calendar Audit")
        if not saved:
            st.markdown('<div class="upload-hint">👆 Upload your monthly WorkingHours file in the sidebar to begin</div>', unsafe_allow_html=True); return
        keys = sorted(saved.keys(), key=lambda k:(int(k.split("_")[0]), MONTH_ORDER.index(k.split("_")[1])))
        labels = [f"{k.split('_')[1]} {k.split('_')[0]}" for k in keys]
        sel_label = st.selectbox("Select month", labels, index=len(labels)-1)
        entry = saved[keys[labels.index(sel_label)]]
        task_hours = get_summary(entry); themes = get_themes(entry); daily = get_daily(entry)
        total = sum(task_hours.values())
        company = sum(v for k,v in task_hours.items() if k in COMPANY_TASKS); other = total-company
        sel_mon_abbr, sel_year = sel_label.split()
        month_label = f"{MONTH_LONG.get(sel_mon_abbr, sel_mon_abbr)} {sel_year}"

        c1,c2,c3,c4 = st.columns(4)
        c1.markdown(f'<div class="metric-card"><div class="metric-label">Total Hours</div><div class="metric-value">{total:.1f}</div><div class="metric-sub">{sel_label}</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><div class="metric-label">Company Support</div><div class="metric-value">{company:.1f}h</div><div class="metric-sub">{company/total*100:.0f}% of total</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><div class="metric-label">Other Tasks</div><div class="metric-value">{other:.1f}h</div><div class="metric-sub">{other/total*100:.0f}% of total</div></div>', unsafe_allow_html=True)
        top = max(task_hours, key=task_hours.get)
        c4.markdown(f'<div class="metric-card"><div class="metric-label">Top Task</div><div class="metric-value" style="font-size:1.2rem">{top}</div><div class="metric-sub">{task_hours[top]:.1f}h</div></div>', unsafe_allow_html=True)

        st.markdown("")
        cl,cr = st.columns(2)
        with cl:
            st.markdown('<div class="section-header">Hours Breakdown</div>', unsafe_allow_html=True)
            st.plotly_chart(make_donut(task_hours, sel_label), use_container_width=True)
        with cr:
            st.markdown('<div class="section-header">Hours Worked Per Day</div>', unsafe_allow_html=True)
            if daily: st.plotly_chart(make_daily_bars(daily), use_container_width=True)
            else: st.info("No daily data available for this month.")

        # Company-focused charts (match the April tab)
        cl,cr = st.columns(2)
        with cl:
            st.markdown('<div class="section-header">Company Support Distribution</div>', unsafe_allow_html=True)
            f_cd = make_company_distribution(task_hours)
            if f_cd: st.plotly_chart(f_cd, use_container_width=True)
            else: st.info("No direct company-support hours this month.")
        with cr:
            st.markdown('<div class="section-header">Company Support vs. All Other Duties</div>', unsafe_allow_html=True)
            f_so = make_support_vs_other(task_hours)
            if f_so: st.plotly_chart(f_so, use_container_width=True)
            st.caption("All Other Duties excludes PTO/Sick, Office Closed, and Commuting/Travel.")

        st.markdown('<div class="section-header">Weekly Hours Worked (Sun–Sat)</div>', unsafe_allow_html=True)
        f_wk = make_weekly_bars(daily)
        if f_wk: st.plotly_chart(f_wk, use_container_width=True)
        else: st.info("No daily data available to compute weekly totals.")

        st.markdown('<div class="section-header">Key Areas of Time Usage</div>', unsafe_allow_html=True)
        render_task_cards(task_hours, themes, total)

        st.markdown('<div class="section-header">📋 Ready-to-Send Email Text</div>', unsafe_allow_html=True)
        st.caption("Copy this straight into your email to Taylor & Sarah:")
        st.code(build_email_text(task_hours, themes, total, month_label), language=None)

    elif view == "📈 Quarterly":
        st.markdown("# Quarterly Review")
        if not saved:
            st.markdown('<div class="upload-hint">👆 Upload your monthly files to build quarterly views</div>', unsafe_allow_html=True); return
        quarters = {"Q1":["JAN","FEB","MAR"],"Q2":["APR","MAY","JUN"],"Q3":["JUL","AUG","SEP"],"Q4":["OCT","NOV","DEC"]}
        years = sorted({int(k.split("_")[0]) for k in saved}, reverse=True)
        c1,c2 = st.columns(2)
        sel_year = c1.selectbox("Year", years)
        avail = [q for q,ms in quarters.items() if any(f"{sel_year}_{m}" in saved for m in ms)]
        sel_q = c2.selectbox("Quarter", avail or ["Q1"])
        q_hours, q_themes, monthly = {}, {}, {}
        for m in quarters[sel_q]:
            key = f"{sel_year}_{m}"
            if key in saved:
                s = get_summary(saved[key]); monthly[m] = s
                for t,h in s.items(): q_hours[t] = q_hours.get(t,0)+h
                for t, tlist in get_themes(saved[key]).items():
                    q_themes.setdefault(t, {})
                    for name, hh in tlist: q_themes[t][name] = q_themes[t].get(name,0)+hh
        if not q_hours: st.info(f"No data for {sel_q} {sel_year} yet."); return
        total_q = sum(q_hours.values()); loaded = len(monthly)
        c1,c2,c3 = st.columns(3)
        c1.markdown(f'<div class="metric-card"><div class="metric-label">Quarter Total</div><div class="metric-value">{total_q:.1f}h</div><div class="metric-sub">{loaded} of 3 months</div></div>', unsafe_allow_html=True)
        comp = sum(v for k,v in q_hours.items() if k in COMPANY_TASKS)
        c2.markdown(f'<div class="metric-card"><div class="metric-label">Company Support</div><div class="metric-value">{comp:.1f}h</div><div class="metric-sub">{comp/total_q*100:.0f}% of quarter</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><div class="metric-label">Avg Monthly</div><div class="metric-value">{total_q/loaded:.1f}h</div><div class="metric-sub">per month</div></div>', unsafe_allow_html=True)
        st.markdown("")
        cl,cr = st.columns(2)
        with cl:
            st.markdown('<div class="section-header">Quarter Breakdown</div>', unsafe_allow_html=True)
            st.plotly_chart(make_donut(q_hours, f"{sel_q} {sel_year}"), use_container_width=True)
        with cr:
            st.markdown('<div class="section-header">Month-by-Month Trend</div>', unsafe_allow_html=True)
            if loaded > 1:
                md = {(sel_year,m):monthly[m] for m in monthly}
                st.plotly_chart(make_trend(md, sorted(q_hours, key=q_hours.get, reverse=True)[:6]), use_container_width=True)
            else: st.info("Upload more months to see the trend.")
        # Entity support charts (match the Q1 tab)
        q_month_labels = [m for m in quarters[sel_q] if m in monthly]
        q_month_list = [monthly[m] for m in q_month_labels]
        st.markdown('<div class="section-header">Entity Support by Month</div>', unsafe_allow_html=True)
        f_eb = make_entity_grouped_bars(q_month_labels, q_month_list)
        if f_eb: st.plotly_chart(f_eb, use_container_width=True)
        else: st.info("No direct company-support hours in this quarter yet.")
        cl,cr = st.columns(2)
        with cl:
            st.markdown('<div class="section-header">Entity Support — Totals</div>', unsafe_allow_html=True)
            f_ed = make_entity_distribution(q_month_list, f"{sel_q} {sel_year} Entity Support")
            if f_ed: st.plotly_chart(f_ed, use_container_width=True)
        with cr:
            st.markdown('<div class="section-header">Entity Support — Stacked by Month</div>', unsafe_allow_html=True)
            f_es = make_entity_stacked_area(q_month_labels, q_month_list)
            if f_es: st.plotly_chart(f_es, use_container_width=True)
            else: st.info("Upload 2+ months to see the stacked trend.")

        st.markdown('<div class="section-header">Key Areas of Time Usage — Quarter</div>', unsafe_allow_html=True)
        q_themes_sorted = {t: sorted(d.items(), key=lambda x:-x[1]) for t,d in q_themes.items()}
        render_task_cards(q_hours, q_themes_sorted, total_q)

    elif view == "🗓 Annual":
        st.markdown("# Annual Review")
        if not saved:
            st.markdown('<div class="upload-hint">👆 Upload your monthly files to build the annual view</div>', unsafe_allow_html=True); return
        years = sorted({int(k.split("_")[0]) for k in saved}, reverse=True)
        sel_year = st.selectbox("Year", years)
        keys = [k for k in saved if int(k.split("_")[0])==sel_year]
        y_hours, monthly = {}, {}
        for k in keys:
            m = k.split("_")[1]; s = get_summary(saved[k]); monthly[(sel_year,m)] = s
            for t,h in s.items(): y_hours[t] = y_hours.get(t,0)+h
        if not y_hours: st.info("No data for this year."); return
        total_y = sum(y_hours.values()); done = len(keys); pace = 12/done
        c1,c2,c3,c4 = st.columns(4)
        c1.markdown(f'<div class="metric-card"><div class="metric-label">YTD Hours</div><div class="metric-value">{total_y:.0f}h</div><div class="metric-sub">{done} months</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><div class="metric-label">Full-Year Pace</div><div class="metric-value">{total_y*pace:.0f}h</div><div class="metric-sub">projected</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><div class="metric-label">Monthly Avg</div><div class="metric-value">{total_y/done:.1f}h</div><div class="metric-sub">per month</div></div>', unsafe_allow_html=True)
        comp = sum(v for k,v in y_hours.items() if k in COMPANY_TASKS)
        c4.markdown(f'<div class="metric-card"><div class="metric-label">Company Support</div><div class="metric-value">{comp/total_y*100:.0f}%</div><div class="metric-sub">{comp:.0f}h YTD</div></div>', unsafe_allow_html=True)
        st.markdown("")
        cl,cr = st.columns(2)
        with cl:
            st.markdown('<div class="section-header">YTD Breakdown</div>', unsafe_allow_html=True)
            st.plotly_chart(make_donut(y_hours, f"{sel_year} YTD"), use_container_width=True)
        with cr:
            st.markdown('<div class="section-header">Monthly Trend (Top 6)</div>', unsafe_allow_html=True)
            st.plotly_chart(make_trend(monthly, sorted(y_hours, key=y_hours.get, reverse=True)[:6]), use_container_width=True)
        # Entity support charts (annual)
        ann_months = sorted(monthly.keys(), key=lambda k: MONTH_ORDER.index(k[1]))
        ann_labels = [k[1] for k in ann_months]
        ann_list = [monthly[k] for k in ann_months]
        st.markdown('<div class="section-header">Entity Support by Month</div>', unsafe_allow_html=True)
        f_eb = make_entity_grouped_bars(ann_labels, ann_list)
        if f_eb: st.plotly_chart(f_eb, use_container_width=True)
        else: st.info("No direct company-support hours this year yet.")
        cl,cr = st.columns(2)
        with cl:
            st.markdown('<div class="section-header">Entity Support — Year Totals</div>', unsafe_allow_html=True)
            f_ed = make_entity_distribution(ann_list, f"{sel_year} Entity Support")
            if f_ed: st.plotly_chart(f_ed, use_container_width=True)
        with cr:
            st.markdown('<div class="section-header">Entity Support — Stacked by Month</div>', unsafe_allow_html=True)
            f_es = make_entity_stacked_area(ann_labels, ann_list)
            if f_es: st.plotly_chart(f_es, use_container_width=True)
            else: st.info("Upload 2+ months to see the stacked trend.")

        st.markdown('<div class="section-header">All Activities — Actual vs. 2026 Goals</div>', unsafe_allow_html=True)
        f = make_goal_bars(y_hours, total_y)
        if f: st.plotly_chart(f, use_container_width=True)
        st.markdown('<div class="section-header">Annual Pace Tracker</div>', unsafe_allow_html=True)
        rows = []
        for task, goal_pct in GOALS_2026.items():
            yh = y_hours.get(task,0); yp = yh/total_y if total_y else 0; c = traffic_light(yp, goal_pct)
            rows.append({"":"🟢" if c=="green" else ("🟡" if c=="yellow" else "🔴"),"Task":task,"YTD Hours":f"{yh:.1f}h","YTD %":f"{yp*100:.1f}%","Goal %":f"{goal_pct*100:.1f}%","Proj Year-End":f"{yh*pace:.0f}h","Δ":f"{(yp-goal_pct)*100:+.1f}pp"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown('<div class="section-header">Annual Commentary</div>', unsafe_allow_html=True)
        for line in generate_commentary(y_hours, total_y):
            st.markdown(f'<div class="commentary-box">{line}</div>', unsafe_allow_html=True)

    elif view == "⚡ Context Switching":
        st.markdown("# Context Switching")
        detail_months = {k:e["detail"] for k,e in saved.items() if isinstance(e, dict) and e.get("detail")}
        if not detail_months:
            st.markdown('<div class="upload-hint">👆 Upload a WorkingHours file that includes Start and End time columns to see your context switching timeline</div>', unsafe_allow_html=True); return
        mkeys = sorted(detail_months.keys(), key=lambda k:(int(k.split("_")[0]), MONTH_ORDER.index(k.split("_")[1])))
        mlabels = [f"{k.split('_')[1]} {k.split('_')[0]}" for k in mkeys]
        sel_mkey = mkeys[mlabels.index(st.selectbox("Month", mlabels, index=len(mlabels)-1))]
        detail = detail_months[sel_mkey]
        days = sorted({d["day"] for d in detail}, key=lambda s: datetime.strptime(s, "%b %d"))
        sel_day = st.selectbox("Day", days, index=min(2, len(days)-1))
        day_entries = sorted([d for d in detail if d["day"]==sel_day], key=lambda d:d["start"])
        def to_mins(t): h,m = map(int,t.split(":")); return h*60+m
        def fmt(mins): h,m = divmod(int(mins),60); return f"{h}:{m:02d}"
        total_mins = sum(d["mins"] for d in day_entries); switches = len(day_entries)-1
        start_t = day_entries[0]["start"]; end_t = day_entries[-1]["end"]
        c1,c2,c3 = st.columns(3)
        c1.markdown(f'<div class="metric-card"><div class="metric-label">Hours Worked</div><div class="metric-value">{int(total_mins//60)}h {int(total_mins%60)}m</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><div class="metric-label">Context Switches</div><div class="metric-value">{switches}</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><div class="metric-label">Work Window</div><div class="metric-value" style="font-size:1.2rem">{start_t} – {end_t}</div></div>', unsafe_allow_html=True)
        st.markdown("")
        st.markdown('<div class="section-header">Task Progression (real time axis)</div>', unsafe_allow_html=True)
        tasks_in_day = list(dict.fromkeys(d["task"] for d in day_entries))
        tidx = {t:i for i,t in enumerate(tasks_in_day)}
        plot = list(day_entries); last = plot[-1]; plot.append({**last, "start":last["end"], "_end":True})
        xs,ys,colors,sizes,hovers = [],[],[],[],[]
        for d in plot:
            xs.append(to_mins(d["start"])); ys.append(tidx.get(d["task"],0)); colors.append(task_color(d["task"]))
            is_end = d.get("_end", False); sizes.append(5 if is_end else 9)
            if is_end: hovers.append(f"{d['start']} — end of day<br>{d['task']}")
            else:
                desc = f"<br>{d['desc']}" if d["desc"] else ""
                hovers.append(f"{d['start']} – {d['end']}<br><b>{d['task']}</b>{desc}")
        fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines+markers", line=dict(color="#2255cc", width=2, shape="hv"),
            marker=dict(color=colors, size=sizes), hovertext=hovers, hovertemplate="%{hovertext}<extra></extra>"))
        ds,de = to_mins(start_t), to_mins(end_t); ticks = list(range((ds//30)*30, de+30, 30))
        fig.update_layout(height=380, xaxis=dict(range=[ds-5,de+5], tickvals=ticks, ticktext=[fmt(t) for t in ticks], tickangle=-30, gridcolor="#f0ede8"),
            yaxis=dict(tickvals=list(range(len(tasks_in_day))), ticktext=tasks_in_day, gridcolor="#f0ede8"),
            margin=dict(t=10,b=40,l=170,r=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hovermode="closest")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('<div class="section-header">Task Summary</div>', unsafe_allow_html=True)
        summ = {}
        for d in day_entries: summ[d["task"]] = summ.get(d["task"],0)+d["mins"]
        rows = [{"Task":t,"Time":f"{int(m//60)}h {int(m%60)}m","% of day":f"{m/total_mins*100:.1f}%"} for t,m in sorted(summ.items(), key=lambda x:-x[1])]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
