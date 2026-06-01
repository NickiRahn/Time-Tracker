import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import os
import re
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NR Calendar Audit Dashboard",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
TASK_COLORS = {
    "GTD":                    "#888780",
    "LMA":                    "#D4537E",
    "MAPCO":                  "#3266ad",
    "MAGNUM":                 "#639922",
    "MCP":                    "#0C7C59",
    "MCC":                    "#1D9E75",
    "MTI":                    "#0C447C",
    "MFE":                    "#4B1528",
    "TLM/NR 1:1":             "#7F77DD",
    "OFFICE CLOSED":          "#cccccc",
    "PTO/SICK TIME":          "#F4A261",
    "PROFESSIONAL DEVELOPMENT": "#D85A30",
    "COMMUTING/TRAVEL":       "#BA7517",
    "NETWORKING/PEER GROUPS": "#A32D2D",
    "CORP DEV":               "#2B2D42",
    "M-COMPANIES":            "#1D9E75",
    "M COMPANIES":            "#1D9E75",
}

GOALS_2026 = {
    "GTD":                    0.10,
    "LMA":                    0.025,
    "MAPCO":                  0.25,
    "MAGNUM":                 0.01,
    "MCP":                    0.04,
    "MCC":                    0.10,
    "MTI":                    0.25,
    "MFE":                    0.02,
    "TLM/NR 1:1":             0.02,
    "OFFICE CLOSED":          0.03,
    "PTO/SICK TIME":          0.10,
    "PROFESSIONAL DEVELOPMENT": 0.015,
    "COMMUTING/TRAVEL":       0.025,
    "NETWORKING/PEER GROUPS": 0.015,
}

COMPANY_TASKS = ["MAPCO", "MAGNUM", "MCP", "MCC", "MTI", "MFE", "M-COMPANIES", "M COMPANIES", "CORP DEV"]

DATA_FILE = "saved_data.json"
MONTH_ORDER = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.metric-card {
    background: white;
    border: 1px solid #e8e5e0;
    border-radius: 12px;
    padding: 1.1rem 1.25rem;
    margin-bottom: 0;
}
.metric-label {
    font-size: 0.72rem;
    color: #7a7874;
    font-family: 'DM Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}
.metric-value {
    font-size: 1.7rem;
    font-weight: 600;
    color: #1a1917;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
.metric-sub {
    font-size: 0.78rem;
    color: #7a7874;
    margin-top: 2px;
}
.section-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: #1a1917;
    margin: 1.5rem 0 0.75rem 0;
    padding-bottom: 6px;
    border-bottom: 1.5px solid #e8e5e0;
}
.traffic-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
    border-bottom: 1px solid #f0ede8;
    font-size: 0.85rem;
}
.dot-green  { width:10px;height:10px;border-radius:50%;background:#22c55e;flex-shrink:0; }
.dot-yellow { width:10px;height:10px;border-radius:50%;background:#eab308;flex-shrink:0; }
.dot-red    { width:10px;height:10px;border-radius:50%;background:#ef4444;flex-shrink:0; }
.commentary-box {
    background: #f8f6f2;
    border-left: 3px solid #3266ad;
    border-radius: 0 8px 8px 0;
    padding: 0.85rem 1rem;
    margin: 0.5rem 0;
    font-size: 0.875rem;
    color: #1a1917;
}
.upload-hint {
    background: #f0f4ff;
    border: 1px dashed #3266ad;
    border-radius: 10px;
    padding: 1.5rem;
    text-align: center;
    color: #3266ad;
    font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)

# ── Data persistence ──────────────────────────────────────────────────────────
def load_saved_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Parsing helpers ───────────────────────────────────────────────────────────
def normalize_task(name):
    if not isinstance(name, str):
        return str(name)
    n = name.strip().upper()
    aliases = {
        "M-COMPANIES": "MCC", "M COMPANIES": "MCC",
        "CORP DEV": "MAPCO",
        "PROF DEV": "PROFESSIONAL DEVELOPMENT",
        "PTO": "PTO/SICK TIME",
        "OFFICE CLOSED/HOLIDAY": "OFFICE CLOSED",
        "COMMUTING/TRAVEL": "COMMUTING/TRAVEL",
    }
    return aliases.get(n, n)

def parse_monthly_sheet(df_raw):
    """Parse a monthly detail sheet (Day / Task / Time columns)."""
    # Find the right columns
    cols = [str(c).strip() for c in df_raw.columns]
    df_raw.columns = cols

    # Try to identify task and time columns
    task_col = next((c for c in cols if "task" in c.lower()), None)
    time_col = next((c for c in cols if c.lower() in ["time", "time ", "hours", "duration"]), None)
    day_col  = next((c for c in cols if "day" in c.lower()), None)

    if not task_col or not time_col:
        return None

    df = df_raw[[day_col, task_col, time_col]].copy() if day_col else df_raw[[task_col, time_col]].copy()
    df.columns = (["day", "task", "hours"] if day_col else ["task", "hours"])
    df = df.dropna(subset=["task", "hours"])
    df = df[df["task"].astype(str).str.strip() != ""]
    df["task"]  = df["task"].apply(normalize_task)
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0)
    df = df[df["hours"] > 0]
    return df

def parse_totals_sheet(df_raw):
    """Parse the annual totals sheet."""
    cols = [str(c).strip() for c in df_raw.columns]
    df_raw.columns = cols
    task_col = next((c for c in cols if c.lower() == "task"), None)
    if not task_col:
        return None

    month_cols = [c for c in cols if c.upper() in MONTH_ORDER]
    if not month_cols:
        return None

    df = df_raw[[task_col] + month_cols].copy()
    df.columns = ["task"] + [c.upper() for c in month_cols]
    df = df.dropna(subset=["task"])
    df = df[df["task"].astype(str).str.strip().str.upper().isin(
        [k.upper() for k in GOALS_2026.keys()] + ["MAPCO","MCC","MTI","MFE","MAGNUM","MCP"]
    )]
    df["task"] = df["task"].apply(normalize_task)
    for col in [c.upper() for c in month_cols]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

def infer_year_month(sheet_name):
    """Try to extract year and month from sheet name like 'APR 2026'."""
    sn = sheet_name.upper()
    year_m = re.search(r"(20\d\d)", sn)
    month_m = next((m for m in MONTH_ORDER if m in sn), None)
    year = int(year_m.group(1)) if year_m else datetime.now().year
    return year, month_m

def parse_uploaded_file(uploaded_file):
    """Return dict of {(year, month): task_hours_series}."""
    xl = pd.ExcelFile(uploaded_file)
    results = {}
    totals_df = None

    for sheet in xl.sheet_names:
        df_raw = xl.parse(sheet, header=0)
        sn = sheet.upper()

        # Totals sheet
        if "TOTAL" in sn and "TOTAL" not in [s.upper() for s in xl.sheet_names if s != sheet]:
            totals_df = parse_totals_sheet(df_raw)
            continue
        if re.search(r"\d{4}\s*TOTAL", sn) or sn.endswith("TOTALS"):
            totals_df = parse_totals_sheet(df_raw)
            continue

        # Monthly detail sheet
        year, month = infer_year_month(sheet)
        if month:
            parsed = parse_monthly_sheet(df_raw)
            if parsed is not None and len(parsed) > 0:
                summary = parsed.groupby("task")["hours"].sum()
                results[(year, month)] = summary.to_dict()

    return results, totals_df

# ── Chart helpers ─────────────────────────────────────────────────────────────
def traffic_light(actual_pct, goal_pct):
    if goal_pct == 0:
        return "green"
    ratio = actual_pct / goal_pct
    if 0.8 <= ratio <= 1.3:
        return "green"
    elif 0.5 <= ratio < 0.8 or 1.3 < ratio <= 1.7:
        return "yellow"
    else:
        return "red"

def make_donut(task_hours, title=""):
    tasks  = list(task_hours.keys())
    values = list(task_hours.values())
    colors = [TASK_COLORS.get(t, "#aaa") for t in tasks]
    total  = sum(values)
    labels = [f"{t}<br>{v:.1f}h ({v/total*100:.1f}%)" if total > 0 else t for t, v in zip(tasks, values)]
    fig = go.Figure(go.Pie(
        labels=tasks, values=values, customdata=labels,
        hovertemplate="%{customdata}<extra></extra>",
        marker_colors=colors, hole=0.55,
        textinfo="none",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, family="DM Sans"), x=0.5, xanchor="center"),
        showlegend=True,
        legend=dict(font=dict(size=10, family="DM Mono"), orientation="v"),
        margin=dict(t=50, b=20, l=10, r=10),
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig

def make_trend(monthly_data, tasks=None):
    """Line chart of hours per task over months."""
    if not monthly_data:
        return None
    sorted_keys = sorted(monthly_data.keys(), key=lambda k: (k[0], MONTH_ORDER.index(k[1])))
    x_labels = [f"{m} {y}" for y, m in sorted_keys]

    all_tasks = tasks or sorted(set(t for d in monthly_data.values() for t in d.keys()))
    fig = go.Figure()
    for task in all_tasks:
        y = [monthly_data[k].get(task, 0) for k in sorted_keys]
        if sum(y) == 0:
            continue
        fig.add_trace(go.Scatter(
            x=x_labels, y=y, name=task, mode="lines+markers",
            line=dict(color=TASK_COLORS.get(task, "#888"), width=2),
            marker=dict(size=6),
            hovertemplate=f"<b>{task}</b><br>%{{x}}: %{{y:.1f}}h<extra></extra>",
        ))
    fig.update_layout(
        height=340, margin=dict(t=20, b=40, l=0, r=10),
        legend=dict(font=dict(size=10, family="DM Mono"), orientation="h", y=-0.25),
        yaxis=dict(title="Hours", gridcolor="#f0ede8"),
        xaxis=dict(gridcolor="#f0ede8"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
    )
    return fig

def make_goal_bars(task_hours, total_hours):
    if total_hours == 0:
        return None
    rows = []
    for task, goal_pct in GOALS_2026.items():
        actual_h = task_hours.get(task, 0)
        actual_pct = actual_h / total_hours if total_hours > 0 else 0
        rows.append(dict(task=task, actual=actual_pct*100, goal=goal_pct*100,
                         color=TASK_COLORS.get(task, "#888")))
    rows.sort(key=lambda r: -r["actual"])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[r["task"] for r in rows],
        y=[r["actual"] for r in rows],
        name="Actual %",
        marker_color=[r["color"] for r in rows],
        hovertemplate="%{x}<br>Actual: %{y:.1f}%<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[r["task"] for r in rows],
        y=[r["goal"] for r in rows],
        name="2026 Goal %",
        mode="markers",
        marker=dict(symbol="line-ew", size=16, color="#1a1917",
                    line=dict(color="#1a1917", width=2)),
        hovertemplate="%{x}<br>Goal: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        height=320, margin=dict(t=10, b=80, l=0, r=10),
        yaxis=dict(title="% of total hours", gridcolor="#f0ede8"),
        xaxis=dict(tickangle=-35, tickfont=dict(size=10, family="DM Mono")),
        legend=dict(orientation="h", y=1.08, font=dict(size=11)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.35,
    )
    return fig

def generate_commentary(task_hours, total_hours, period="this month"):
    lines = []
    if total_hours == 0:
        return []
    for task, goal_pct in GOALS_2026.items():
        if goal_pct == 0:
            continue
        actual_h = task_hours.get(task, 0)
        actual_pct = actual_h / total_hours
        ratio = actual_pct / goal_pct
        if ratio > 1.5:
            lines.append(f"🔴 **{task}** is running at {actual_pct*100:.1f}% — {ratio:.1f}× your {goal_pct*100:.0f}% goal. Consider rebalancing.")
        elif ratio > 1.25:
            lines.append(f"🟡 **{task}** is slightly above goal ({actual_pct*100:.1f}% vs {goal_pct*100:.0f}% target).")
        elif ratio < 0.5 and actual_h > 0:
            lines.append(f"🟡 **{task}** is well below goal ({actual_pct*100:.1f}% vs {goal_pct*100:.0f}% target).")
    if not lines:
        lines.append("✅ All tasks are tracking close to 2026 goals.")
    return lines

# ── Main app ──────────────────────────────────────────────────────────────────
def main():
    # Sidebar
    with st.sidebar:
        st.markdown("## 📅 NR Calendar Audit")
        st.markdown("---")
        st.markdown("### Upload Time Report")
        uploaded = st.file_uploader(
            "Drop your monthly Excel here",
            type=["xlsx", "xls"],
            help="Upload your Toggl/calendar export (same format as your existing audit spreadsheets)",
        )

        st.markdown("---")
        st.markdown("### View")
        view = st.radio("", ["📊 Monthly", "📈 Quarterly", "🗓 Annual", "⚡ Context Switching"], label_visibility="collapsed")

        st.markdown("---")
        saved = load_saved_data()
        if saved:
            st.markdown(f"**{len(saved)} month(s) stored**")
            if st.button("🗑 Clear all data", use_container_width=True):
                save_data({})
                st.rerun()

    # Process upload
    if uploaded:
        with st.spinner("Parsing your time report…"):
            new_data, totals_df = parse_uploaded_file(uploaded)
        if new_data:
            saved = load_saved_data()
            for (year, month), task_dict in new_data.items():
                key = f"{year}_{month}"
                saved[key] = task_dict
            save_data(saved)
            st.sidebar.success(f"✅ Loaded {len(new_data)} month(s)")
        else:
            st.sidebar.warning("Couldn't parse any monthly sheets. Make sure your file matches the standard format.")

    saved = load_saved_data()

    # ── MONTHLY VIEW ──────────────────────────────────────────────────────────
    if view == "📊 Monthly":
        st.markdown("# Monthly Calendar Audit")

        if not saved:
            st.markdown('<div class="upload-hint">👆 Upload your monthly time report in the sidebar to get started</div>', unsafe_allow_html=True)
            return

        # Month selector
        keys = sorted(saved.keys(), key=lambda k: (int(k.split("_")[0]), MONTH_ORDER.index(k.split("_")[1])))
        labels = [f"{k.split('_')[1]} {k.split('_')[0]}" for k in keys]
        sel_label = st.selectbox("Select month", labels, index=len(labels)-1)
        sel_key = keys[labels.index(sel_label)]
        task_hours = saved[sel_key]
        total_hours = sum(task_hours.values())
        company_hours = sum(v for k, v in task_hours.items() if k in COMPANY_TASKS)
        other_hours = total_hours - company_hours

        # KPI cards
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Total Hours</div><div class="metric-value">{total_hours:.1f}</div><div class="metric-sub">{sel_label}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Company Support</div><div class="metric-value">{company_hours:.1f}h</div><div class="metric-sub">{company_hours/total_hours*100:.0f}% of total</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Other Tasks</div><div class="metric-value">{other_hours:.1f}h</div><div class="metric-sub">{other_hours/total_hours*100:.0f}% of total</div></div>', unsafe_allow_html=True)
        with c4:
            top_task = max(task_hours, key=task_hours.get)
            st.markdown(f'<div class="metric-card"><div class="metric-label">Top Task</div><div class="metric-value" style="font-size:1.2rem">{top_task}</div><div class="metric-sub">{task_hours[top_task]:.1f}h</div></div>', unsafe_allow_html=True)

        st.markdown("")

        # Charts row
        col_left, col_right = st.columns([1, 1])
        with col_left:
            st.markdown('<div class="section-header">Hours Breakdown</div>', unsafe_allow_html=True)
            st.plotly_chart(make_donut(task_hours, sel_label), use_container_width=True)
        with col_right:
            st.markdown('<div class="section-header">Actual vs. 2026 Goals</div>', unsafe_allow_html=True)
            fig_goals = make_goal_bars(task_hours, total_hours)
            if fig_goals:
                st.plotly_chart(fig_goals, use_container_width=True)

        # Traffic lights + commentary
        col_tl, col_comm = st.columns([1, 1])
        with col_tl:
            st.markdown('<div class="section-header">Goal Status</div>', unsafe_allow_html=True)
            for task, goal_pct in GOALS_2026.items():
                if goal_pct == 0:
                    continue
                actual_h = task_hours.get(task, 0)
                actual_pct = actual_h / total_hours if total_hours > 0 else 0
                color = traffic_light(actual_pct, goal_pct)
                dot_class = f"dot-{color}"
                st.markdown(
                    f'<div class="traffic-row"><span class="{dot_class}"></span>'
                    f'<span style="flex:1;font-weight:500">{task}</span>'
                    f'<span style="font-family:DM Mono;font-size:0.8rem;color:#7a7874">'
                    f'{actual_pct*100:.1f}% / {goal_pct*100:.0f}% goal</span></div>',
                    unsafe_allow_html=True
                )

        with col_comm:
            st.markdown('<div class="section-header">Auto Commentary</div>', unsafe_allow_html=True)
            for line in generate_commentary(task_hours, total_hours, sel_label):
                st.markdown(f'<div class="commentary-box">{line}</div>', unsafe_allow_html=True)

    # ── QUARTERLY VIEW ────────────────────────────────────────────────────────
    elif view == "📈 Quarterly":
        st.markdown("# Quarterly Review")

        if not saved:
            st.markdown('<div class="upload-hint">👆 Upload your time reports in the sidebar to get started</div>', unsafe_allow_html=True)
            return

        quarters = {"Q1": ["JAN","FEB","MAR"], "Q2": ["APR","MAY","JUN"],
                    "Q3": ["JUL","AUG","SEP"], "Q4": ["OCT","NOV","DEC"]}
        years = sorted(set(int(k.split("_")[0]) for k in saved.keys()), reverse=True)

        c1, c2 = st.columns(2)
        with c1:
            sel_year = st.selectbox("Year", years)
        with c2:
            available_q = []
            for q, months in quarters.items():
                if any(f"{sel_year}_{m}" in saved for m in months):
                    available_q.append(q)
            sel_q = st.selectbox("Quarter", available_q if available_q else ["Q1"])

        q_months = quarters[sel_q]
        q_task_hours = {}
        monthly_breakdown = {}
        for month in q_months:
            key = f"{sel_year}_{month}"
            if key in saved:
                monthly_breakdown[month] = saved[key]
                for task, hours in saved[key].items():
                    q_task_hours[task] = q_task_hours.get(task, 0) + hours

        if not q_task_hours:
            st.info(f"No data yet for {sel_q} {sel_year}. Upload more months to see quarterly data.")
            return

        total_q = sum(q_task_hours.values())
        months_loaded = len(monthly_breakdown)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Quarter Total</div><div class="metric-value">{total_q:.1f}h</div><div class="metric-sub">{months_loaded} of 3 months loaded</div></div>', unsafe_allow_html=True)
        with c2:
            company_q = sum(v for k, v in q_task_hours.items() if k in COMPANY_TASKS)
            st.markdown(f'<div class="metric-card"><div class="metric-label">Company Support</div><div class="metric-value">{company_q:.1f}h</div><div class="metric-sub">{company_q/total_q*100:.0f}% of quarter</div></div>', unsafe_allow_html=True)
        with c3:
            avg_monthly = total_q / months_loaded if months_loaded else 0
            st.markdown(f'<div class="metric-card"><div class="metric-label">Avg Monthly Hours</div><div class="metric-value">{avg_monthly:.1f}h</div><div class="metric-sub">per month this quarter</div></div>', unsafe_allow_html=True)

        st.markdown("")
        cl, cr = st.columns(2)
        with cl:
            st.markdown('<div class="section-header">Quarter Breakdown</div>', unsafe_allow_html=True)
            st.plotly_chart(make_donut(q_task_hours, f"{sel_q} {sel_year}"), use_container_width=True)
        with cr:
            st.markdown('<div class="section-header">Month-by-Month Trend</div>', unsafe_allow_html=True)
            if len(monthly_breakdown) > 1:
                monthly_data = {(sel_year, m): monthly_breakdown[m] for m in monthly_breakdown}
                top_tasks = sorted(q_task_hours, key=q_task_hours.get, reverse=True)[:6]
                fig = make_trend(monthly_data, top_tasks)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Upload more months to see the trend chart.")

        # Quarter vs goals table
        st.markdown('<div class="section-header">Goal vs. Actual — ' + f"{sel_q} {sel_year}" + '</div>', unsafe_allow_html=True)
        rows = []
        for task, goal_pct in GOALS_2026.items():
            actual_h = q_task_hours.get(task, 0)
            actual_pct = actual_h / total_q if total_q > 0 else 0
            color = traffic_light(actual_pct, goal_pct)
            emoji = "🟢" if color=="green" else ("🟡" if color=="yellow" else "🔴")
            rows.append({
                "": emoji, "Task": task,
                "Actual Hours": f"{actual_h:.1f}h",
                "Actual %": f"{actual_pct*100:.1f}%",
                "2026 Goal %": f"{goal_pct*100:.1f}%",
                "Δ from Goal": f"{(actual_pct - goal_pct)*100:+.1f}pp",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Commentary
        st.markdown('<div class="section-header">Quarter Commentary</div>', unsafe_allow_html=True)
        for line in generate_commentary(q_task_hours, total_q, f"{sel_q} {sel_year}"):
            st.markdown(f'<div class="commentary-box">{line}</div>', unsafe_allow_html=True)

    # ── ANNUAL VIEW ───────────────────────────────────────────────────────────
    elif view == "🗓 Annual":
        st.markdown("# Annual Review")

        if not saved:
            st.markdown('<div class="upload-hint">👆 Upload your time reports in the sidebar to get started</div>', unsafe_allow_html=True)
            return

        years = sorted(set(int(k.split("_")[0]) for k in saved.keys()), reverse=True)
        sel_year = st.selectbox("Year", years)

        year_keys = [k for k in saved if int(k.split("_")[0]) == sel_year]
        year_task_hours = {}
        monthly_data = {}
        for key in year_keys:
            month = key.split("_")[1]
            monthly_data[(sel_year, month)] = saved[key]
            for task, h in saved[key].items():
                year_task_hours[task] = year_task_hours.get(task, 0) + h

        if not year_task_hours:
            st.info("No data for this year yet.")
            return

        total_y = sum(year_task_hours.values())
        months_done = len(year_keys)
        pace_factor = 12 / months_done if months_done else 1

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">YTD Hours</div><div class="metric-value">{total_y:.0f}h</div><div class="metric-sub">{months_done} months</div></div>', unsafe_allow_html=True)
        with c2:
            projected = total_y * pace_factor
            st.markdown(f'<div class="metric-card"><div class="metric-label">Full-Year Pace</div><div class="metric-value">{projected:.0f}h</div><div class="metric-sub">projected at current rate</div></div>', unsafe_allow_html=True)
        with c3:
            avg_m = total_y / months_done if months_done else 0
            st.markdown(f'<div class="metric-card"><div class="metric-label">Monthly Avg</div><div class="metric-value">{avg_m:.1f}h</div><div class="metric-sub">per month</div></div>', unsafe_allow_html=True)
        with c4:
            company_y = sum(v for k, v in year_task_hours.items() if k in COMPANY_TASKS)
            st.markdown(f'<div class="metric-card"><div class="metric-label">Company Support</div><div class="metric-value">{company_y/total_y*100:.0f}%</div><div class="metric-sub">{company_y:.0f}h YTD</div></div>', unsafe_allow_html=True)

        st.markdown("")

        cl, cr = st.columns(2)
        with cl:
            st.markdown('<div class="section-header">YTD Breakdown</div>', unsafe_allow_html=True)
            st.plotly_chart(make_donut(year_task_hours, f"{sel_year} YTD"), use_container_width=True)
        with cr:
            st.markdown('<div class="section-header">Monthly Trend (Top 6 Tasks)</div>', unsafe_allow_html=True)
            top_tasks = sorted(year_task_hours, key=year_task_hours.get, reverse=True)[:6]
            sorted_monthly = {k: v for k, v in sorted(monthly_data.items(), key=lambda x: MONTH_ORDER.index(x[0][1]))}
            fig = make_trend(sorted_monthly, top_tasks)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

        # Annual pace tracker
        st.markdown('<div class="section-header">Annual Pace Tracker</div>', unsafe_allow_html=True)
        rows = []
        for task, goal_pct in GOALS_2026.items():
            ytd_h = year_task_hours.get(task, 0)
            ytd_pct = ytd_h / total_y if total_y > 0 else 0
            proj_pct = ytd_pct  # proportion stays same on pace
            proj_h = ytd_h * pace_factor
            color = traffic_light(ytd_pct, goal_pct)
            emoji = "🟢" if color=="green" else ("🟡" if color=="yellow" else "🔴")
            rows.append({
                "": emoji, "Task": task,
                "YTD Hours": f"{ytd_h:.1f}h",
                "YTD %": f"{ytd_pct*100:.1f}%",
                "2026 Goal %": f"{goal_pct*100:.1f}%",
                "Projected Year-End": f"{proj_h:.0f}h",
                "Δ from Goal": f"{(ytd_pct - goal_pct)*100:+.1f}pp",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown('<div class="section-header">Annual Commentary</div>', unsafe_allow_html=True)
        for line in generate_commentary(year_task_hours, total_y, f"{sel_year} YTD"):
            st.markdown(f'<div class="commentary-box">{line}</div>', unsafe_allow_html=True)

    # ── CONTEXT SWITCHING ─────────────────────────────────────────────────────
    elif view == "⚡ Context Switching":
        st.markdown("# Context Switching")

        ctx_file = st.file_uploader(
            "Upload your working hours export (Toggl format with Start/End times)",
            type=["xlsx", "xls"],
            key="ctx_upload",
        )

        if not ctx_file:
            st.markdown('<div class="upload-hint">👆 Upload your Toggl working hours export to see your context switching timeline</div>', unsafe_allow_html=True)
            return

        with st.spinner("Parsing time entries…"):
            df = pd.read_excel(ctx_file)
            df = df.dropna(subset=["Task"])
            df = df[df["Task"] != "Total"]
            df["Day_str"] = pd.to_datetime(df["Day"]).dt.strftime("%b %d")
            df["Start_str"] = pd.to_datetime(df["Start"]).dt.strftime("%H:%M")
            df["End_str"]   = pd.to_datetime(df["End"]).dt.strftime("%H:%M")

            def to_mins(t):
                h, m = map(int, t.split(":"))
                return h * 60 + m

            def fmt_time(mins):
                h, m = divmod(int(mins), 60)
                return f"{h}:{m:02d}"

            def parse_dur(d):
                if pd.isna(d): return 0
                d = str(d)
                total = 0
                hm = re.search(r"(\d+)h", d)
                mm = re.search(r"(\d+)m", d)
                if hm: total += int(hm.group(1)) * 60
                if mm: total += int(mm.group(1))
                return total

            df["mins"] = df["Duration"].apply(parse_dur)

        days = df["Day_str"].unique().tolist()
        sel_day = st.selectbox("Select day", days, index=min(2, len(days)-1))
        day_df = df[df["Day_str"] == sel_day].reset_index(drop=True)

        total_mins = day_df["mins"].sum()
        switches = len(day_df) - 1
        start_t = day_df["Start_str"].iloc[0]
        end_t   = day_df["End_str"].iloc[-1]
        total_h = f"{int(total_mins//60)}h {int(total_mins%60)}m"

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Hours Worked</div><div class="metric-value">{total_h}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Context Switches</div><div class="metric-value">{switches}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Work Window</div><div class="metric-value" style="font-size:1.2rem">{start_t} – {end_t}</div></div>', unsafe_allow_html=True)

        st.markdown("")
        st.markdown('<div class="section-header">Task Progression (real time axis)</div>', unsafe_allow_html=True)

        tasks_in_day = day_df["Task"].unique().tolist()
        task_idx = {t: i for i, t in enumerate(tasks_in_day)}

        points_x, points_y, point_colors, point_sizes, hover_texts = [], [], [], [], []
        all_entries = day_df.to_dict("records")
        # add end sentinel
        last = all_entries[-1]
        all_entries.append({**last, "Start_str": last["End_str"], "_is_end": True})

        for i, row in enumerate(all_entries):
            x = to_mins(row["Start_str"])
            y = task_idx.get(row["Task"], 0)
            points_x.append(x)
            points_y.append(y)
            point_colors.append(TASK_COLORS.get(row["Task"], "#888"))
            is_end = row.get("_is_end", False)
            point_sizes.append(8 if not is_end else 5)
            desc = row.get("Work unit description", "")
            end_t_row = row.get("End_str", "")
            if is_end:
                hover_texts.append(f"{row['Start_str']} — end of day<br>{row['Task']}")
            else:
                hover_texts.append(f"{row['Start_str']} – {end_t_row}<br><b>{row['Task']}</b><br>{desc}")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=points_x, y=points_y,
            mode="lines+markers",
            line=dict(color="#2255cc", width=2, shape="hv"),
            marker=dict(color=point_colors, size=point_sizes),
            hovertext=hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
        ))
        day_start = to_mins(day_df["Start_str"].iloc[0])
        day_end   = to_mins(day_df["End_str"].iloc[-1])
        tick_vals = list(range((day_start//30)*30, day_end+30, 30))
        fig.update_layout(
            height=360,
            xaxis=dict(
                range=[day_start-5, day_end+5],
                tickvals=tick_vals,
                ticktext=[fmt_time(v) for v in tick_vals],
                tickangle=-30,
                gridcolor="#f0ede8",
            ),
            yaxis=dict(
                tickvals=list(range(len(tasks_in_day))),
                ticktext=tasks_in_day,
                gridcolor="#f0ede8",
            ),
            margin=dict(t=10, b=40, l=160, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            hovermode="closest",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Day summary table
        st.markdown('<div class="section-header">Task Summary</div>', unsafe_allow_html=True)
        summary = day_df.groupby("Task")["mins"].sum().reset_index()
        summary["Hours"] = summary["mins"].apply(lambda m: f"{int(m//60)}h {int(m%60)}m")
        summary["% of day"] = summary["mins"].apply(lambda m: f"{m/total_mins*100:.1f}%" if total_mins > 0 else "0%")
        summary = summary.drop(columns=["mins"]).rename(columns={"Task": "Task"})
        st.dataframe(summary.sort_values("% of day", ascending=False), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
