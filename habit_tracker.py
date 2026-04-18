#!/usr/bin/env python3
"""
Daily Habit Tracker — logs habits, updates README.md, auto-commits to Git.
Usage:
    python habit_tracker.py           → interactive check-off
    python habit_tracker.py --auto    → mark all habits done (for cron)
    python habit_tracker.py --status  → show today's status
    python habit_tracker.py --add "Habit Name"   → add a new habit
    python habit_tracker.py --remove "Habit Name" → remove a habit
"""

import json
import os
import sys
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
DATA_FILE   = BASE_DIR / "habits.json"
README_FILE = BASE_DIR / "README.md"

DEFAULT_HABITS = [
    "💧 Drink 8 glasses of water",
    "🏃 Exercise / walk",
    "📚 Read for 20 minutes",
    "🧘 Meditate / breathe",
    "💻 Code something",
]

STREAK_EMOJIS = {
    0:  "⬜",
    1:  "🟩",
}


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"habits": DEFAULT_HABITS, "log": {}}


def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def today_str() -> str:
    return date.today().isoformat()


# ── Streak calculation ────────────────────────────────────────────────────────

def get_streak(data: dict, habit: str) -> int:
    """Count consecutive days ending today where the habit was done."""
    streak = 0
    check_date = date.today()
    while True:
        ds = check_date.isoformat()
        day_log = data["log"].get(ds, {})
        if day_log.get(habit):
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    return streak


def get_longest_streak(data: dict, habit: str) -> int:
    """All-time longest streak for a habit."""
    if not data["log"]:
        return 0
    sorted_dates = sorted(data["log"].keys())
    best = cur = 0
    prev = None
    for ds in sorted_dates:
        done = data["log"][ds].get(habit, False)
        if done:
            if prev is not None:
                delta = (date.fromisoformat(ds) - date.fromisoformat(prev)).days
                cur = cur + 1 if delta == 1 else 1
            else:
                cur = 1
            best = max(best, cur)
            prev = ds
        else:
            cur = 0
            prev = None
    return best


# ── README generator ─────────────────────────────────────────────────────────

def last_n_days(n=21) -> list[str]:
    today = date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def build_readme(data: dict):
    habits  = data["habits"]
    log     = data["log"]
    days    = last_n_days(21)
    today   = today_str()

    total_possible = sum(
        len([d for d in days if d in log]) for _ in habits
    )
    total_done = sum(
        log.get(d, {}).get(h, False)
        for h in habits
        for d in days
    )
    overall_pct = round(total_done / total_possible * 100) if total_possible else 0

    lines = [
        "# 🏆 Daily Habit Tracker",
        "",
        f"> Last updated: **{datetime.now().strftime('%Y-%m-%d %H:%M')}**",
        "",
        f"## 📊 Last 21 Days Overview — {overall_pct}% completion",
        "",
    ]

    # Compact date header (show day-of-month only)
    date_labels = " | ".join(
        f"`{d[8:]}`" for d in days
    )
    lines += [
        f"| Habit | {date_labels} | 🔥 Streak | 🏅 Best |",
        f"|-------|{'|'.join(['---']*21)}|-----------|---------|",
    ]

    for habit in habits:
        cells = []
        for d in days:
            done = log.get(d, {}).get(habit, False)
            cells.append(STREAK_EMOJIS[1] if done else STREAK_EMOJIS[0])
        streak  = get_streak(data, habit)
        longest = get_longest_streak(data, habit)
        row = f"| {habit} | {' | '.join(cells)} | {streak} days | {longest} days |"
        lines.append(row)

    lines += [
        "",
        "## 📅 Today's Checklist",
        "",
    ]

    today_log = log.get(today, {})
    for habit in habits:
        done = today_log.get(habit, False)
        mark = "✅" if done else "⬜"
        lines.append(f"- {mark} {habit}")

    lines += [
        "",
        "---",
        "",
        "🟩 = Done &nbsp;&nbsp; ⬜ = Missed",
        "",
        "_Tracked with [habit_tracker.py](habit_tracker.py) — auto-committed daily via Git_",
    ]

    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("✅ README.md updated.")


# ── Git commit ────────────────────────────────────────────────────────────────

def git_commit_and_push(message: str):
    try:
        # Init repo if needed
        if not (BASE_DIR / ".git").exists():
            subprocess.run(["git", "init"], cwd=BASE_DIR, check=True)
            print("✅ Git repo initialised.")

        subprocess.run(["git", "add", "habits.json", "README.md"], cwd=BASE_DIR, check=True)

        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=BASE_DIR
        )
        if result.returncode == 0:
            print("ℹ️  Nothing new to commit.")
            return

        subprocess.run(["git", "commit", "-m", message], cwd=BASE_DIR, check=True)
        print(f"✅ Committed: {message}")

        # Push only if remote exists
        remotes = subprocess.run(
            ["git", "remote"], cwd=BASE_DIR, capture_output=True, text=True
        )
        if remotes.stdout.strip():
            subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
            print("✅ Pushed to remote.")
        else:
            print("ℹ️  No remote configured — skipping push.")
            print("   Run: git remote add origin <your-repo-url>")

    except subprocess.CalledProcessError as e:
        print(f"❌ Git error: {e}")


# ── Interactive CLI ───────────────────────────────────────────────────────────

def interactive_check(data: dict):
    habits  = data["habits"]
    today   = today_str()
    log     = data["log"]

    if today not in log:
        log[today] = {}

    print(f"\n📅 Habit check-in for {today}\n")
    print("  Press ENTER = done ✅  |  Type 's' = skip ⬜\n")

    for habit in habits:
        already = log[today].get(habit, False)
        status  = " [already done ✅]" if already else ""
        ans = input(f"  {habit}{status}? ").strip().lower()
        if ans != "s":
            log[today][habit] = True
        else:
            log[today][habit] = log[today].get(habit, False)  # keep existing

    save_data(data)
    print()
    build_readme(data)

    done_count = sum(1 for v in log[today].values() if v)
    total      = len(habits)
    msg = f"habits: {done_count}/{total} done on {today}"
    git_commit_and_push(f"📊 {msg}")


def auto_check(data: dict):
    """Mark ALL habits as done — useful for cron testing."""
    today = today_str()
    data["log"].setdefault(today, {})
    for habit in data["habits"]:
        data["log"][today][habit] = True
    save_data(data)
    build_readme(data)
    git_commit_and_push(f"🤖 auto: all habits done on {today}")


def show_status(data: dict):
    today    = today_str()
    today_log = data["log"].get(today, {})
    print(f"\n📅 Status for {today}\n")
    for habit in data["habits"]:
        done   = today_log.get(habit, False)
        streak = get_streak(data, habit)
        mark   = "✅" if done else "⬜"
        print(f"  {mark}  {habit}  (🔥 {streak}-day streak)")
    print()


def add_habit(data: dict, name: str):
    if name in data["habits"]:
        print(f"ℹ️  '{name}' already exists.")
        return
    data["habits"].append(name)
    save_data(data)
    build_readme(data)
    git_commit_and_push(f"➕ added habit: {name}")
    print(f"✅ Added: {name}")


def remove_habit(data: dict, name: str):
    if name not in data["habits"]:
        print(f"❌ '{name}' not found.")
        return
    data["habits"].remove(name)
    save_data(data)
    build_readme(data)
    git_commit_and_push(f"➖ removed habit: {name}")
    print(f"✅ Removed: {name}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    data = load_data()

    if not args:
        interactive_check(data)
    elif args[0] == "--auto":
        auto_check(data)
    elif args[0] == "--status":
        show_status(data)
    elif args[0] == "--add" and len(args) > 1:
        add_habit(data, " ".join(args[1:]))
    elif args[0] == "--remove" and len(args) > 1:
        remove_habit(data, " ".join(args[1:]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
