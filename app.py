# NR Calendar Audit Dashboard

A polished, shareable web dashboard for monthly, quarterly, and annual calendar audits — plus context switching analysis. One file upload powers everything.

---

## 📛 File naming (IMPORTANT)

Name each monthly export like this so the app knows which month it is:

- `WorkingHours_January_2026.xlsx`
- `WorkingHours_February_2026.xlsx`
- `WorkingHours_May_2026.xlsx`

The file must have these columns: **Day, Start, End, Work unit description, Duration, Task**
(The Start/End columns are what power the Context Switching timeline — keep them in!)

---

## 🚀 Deploy in 4 steps (no code needed)

### Step 1 — GitHub account
Go to **github.com** → Sign up.

### Step 2 — New repository
+ icon (top right) → New repository → name it → **Private** → Create.

### Step 3 — Upload files
On the repo page, click **"uploading an existing file"**, then drag in all 3 files
(`app.py`, `requirements.txt`, `README.md`) → Commit changes.

### Step 4 — Deploy on Streamlit
1. Go to **share.streamlit.io** → Sign in with GitHub
2. Click **Deploy a public app from GitHub** (the app is shareable by link; your code stays private)
3. Repository: your repo · Branch: `main` · Main file path: `app.py`
4. Click **Deploy** — live in ~2 minutes!

---

## 📊 How to use it

1. Sidebar → upload your `WorkingHours_<Month>_<Year>.xlsx`
2. The app reads it, stores it, and fills in Monthly / Quarterly / Annual / Context Switching automatically
3. Upload more months anytime — quarterly & annual views build themselves
4. Share the URL with your boss

### The 4 views
- **📊 Monthly** — breakdown donut, actual vs goal bars, traffic-light goal status, auto commentary
- **📈 Quarterly** — auto-rolls up 3 months, trend lines, goal table
- **🗓 Annual** — YTD totals, full-year pace projection, annual tracker
- **⚡ Context Switching** — daily task progression on a real time axis, hover for work details

---

## 🔄 Updating your 2026 goals
Open `app.py`, find the `GOALS_2026` block near the top, and edit the percentages. Commit the change on GitHub and the app redeploys automatically.
