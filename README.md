# NR Calendar Audit Dashboard

A polished, shareable web dashboard for monthly, quarterly, and annual calendar audits — plus context switching analysis.

---

## 🚀 Deploy in 4 steps (no code needed)

### Step 1 — Create a free GitHub account
Go to **github.com** → Sign up (just email + password).

### Step 2 — Create a new repository
1. Click the **+** in the top right → **New repository**
2. Name it `nr-dashboard` (or anything you like)
3. Set it to **Private**
4. Click **Create repository**

### Step 3 — Upload these files
1. On your new repo page, click **uploading an existing file**
2. Drag and drop **all 3 files** from this folder:
   - `app.py`
   - `requirements.txt`
   - `README.md`
3. Click **Commit changes**

### Step 4 — Deploy on Streamlit
1. Go to **share.streamlit.io** → Sign up with your GitHub account
2. Click **New app**
3. Choose your `nr-dashboard` repo
4. Set **Main file path** to `app.py`
5. Click **Deploy** — it'll be live in ~2 minutes!
6. You'll get a URL like `https://yourname-nr-dashboard.streamlit.app`

---

## 📊 How to use it

### Monthly Audit
1. Sidebar → **Upload Time Report** → drop in your monthly Excel
2. The app parses it automatically and stores the data
3. Select any month from the dropdown to review
4. Share the URL with your boss — they can view everything

### Context Switching
1. Sidebar → **⚡ Context Switching**
2. Upload your Toggl working hours export
3. Select any day to see the full timeline

### Data persists between sessions
Each time you upload a new month, it gets added to the database. Quarterly and annual views build automatically as you add months.

---

## 📁 File format

The app expects the same Excel format you already use:
- Monthly sheets named like `APR 2026`, `JAN 2026`, etc.
- Columns: Day, Task, Time/Duration
- A totals sheet named `2026 Totals` or similar

---

## 🆘 Help

If anything looks off after uploading, check that your sheet names include the month abbreviation (JAN, FEB, MAR, etc.) and the year.
