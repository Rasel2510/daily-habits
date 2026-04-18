#!/usr/bin/env python3
"""
One-time setup: initialises the Git repo, creates habits.json,
generates the first README.md, and prints cron instructions.
"""
import subprocess
import json
from pathlib import Path

BASE_DIR  = Path(__file__).parent
DATA_FILE = BASE_DIR / "habits.json"

def run(cmd, **kw):
    subprocess.run(cmd, cwd=BASE_DIR, check=True, **kw)

# 1. Write default habits.json
if not DATA_FILE.exists():
    data = {
        "habits": [
            "💧 Drink 8 glasses of water",
            "🏃 Exercise / walk",
            "📚 Read for 20 minutes",
            "🧘 Meditate / breathe",
            "💻 Code something",
        ],
        "log": {}
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print("✅ habits.json created.")
else:
    print("ℹ️  habits.json already exists — skipping.")

# 2. Init git repo
if not (BASE_DIR / ".git").exists():
    run(["git", "init"])
    run(["git", "add", "."])
    run(["git", "commit", "-m", "🚀 init: habit tracker"])
    print("✅ Git repo initialised with first commit.")
else:
    print("ℹ️  Git repo already exists — skipping.")

# 3. Print next steps
python = "python3"
tracker = BASE_DIR / "habit_tracker.py"

print(f"""
┌─────────────────────────────────────────────────────┐
│  ✅  Setup complete!                                 │
└─────────────────────────────────────────────────────┘

▶  Connect to GitHub:
   git remote add origin https://github.com/YOU/REPO.git
   git push -u origin main

▶  Daily manual check-in:
   {python} {tracker}

▶  Auto-run every night at 11 PM via cron:
   Run:  crontab -e
   Add:  0 23 * * * {python} {tracker} --auto >> ~/habit_cron.log 2>&1

▶  Add / remove habits anytime:
   {python} {tracker} --add   "🎨 Draw something"
   {python} {tracker} --remove "🧘 Meditate / breathe"

▶  Check today's status:
   {python} {tracker} --status
""")
