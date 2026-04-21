#!/usr/bin/env python3
"""
Habit Tracker Telegram Bot
Control your habit tracker directly from Telegram.

Commands:
    /start     → welcome message + all commands
    /status    → today's habit status
    /done      → mark ALL habits done for today
    /check     → check off habits one by one (interactive)
    /streak    → show current streaks
    /summary   → last 7 days overview
    /add <name>    → add a new habit
    /remove <name> → remove a habit
    /push      → commit & push to GitHub now
    /help      → show all commands

Setup:
    python habit_bot.py --setup   → configure bot token & chat ID
    python habit_bot.py           → start the bot
"""

import json
import os
import sys
import subprocess
import time
import requests
from datetime import date, datetime, timedelta
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
DATA_FILE   = BASE_DIR / "habits.json"
README_FILE = BASE_DIR / "README.md"
BOT_CONFIG  = BASE_DIR / "bot_config.json"

# ── Load bot config ───────────────────────────────────────────────────────────

def load_bot_config() -> dict:
    token   = os.environ.get("BOT_TOKEN", "")
    chat_id = os.environ.get("CHAT_ID", "")
    if token and chat_id:
        return {"token": token, "chat_id": chat_id}
    if BOT_CONFIG.exists():
        with open(BOT_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    return {"token": "", "chat_id": ""}

def save_bot_config(cfg: dict):
    with open(BOT_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

# ── Habit data helpers ────────────────────────────────────────────────────────

def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"habits": [], "log": {}}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def today_str() -> str:
    return date.today().isoformat()

def get_streak(data: dict, habit: str) -> int:
    streak = 0
    check_date = date.today()
    while True:
        ds = check_date.isoformat()
        if data["log"].get(ds, {}).get(habit):
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    return streak

# ── README + Git ──────────────────────────────────────────────────────────────

def update_readme(data: dict):
    """Regenerate README.md from habits data."""
    habits = data["habits"]
    log    = data["log"]
    today  = today_str()

    def last_n(n=21):
        return [(date.today() - timedelta(days=i)).isoformat() for i in range(n-1, -1, -1)]

    days = last_n(21)
    lines = [
        "# 🏆 Daily Habit Tracker",
        "",
        f"> Last updated: **{datetime.now().strftime('%Y-%m-%d %H:%M')}**",
        "",
        "## 📊 Last 21 Days\n",
        "| Habit | " + " | ".join(f"`{d[8:]}`" for d in days) + " | 🔥 Streak | 🏅 Best |",
        "|-------|" + "|".join(["---"]*21) + "|-----------|---------|",
    ]
    for habit in habits:
        cells = ["🟩" if log.get(d, {}).get(habit) else "⬜" for d in days]
        streak  = get_streak(data, habit)
        longest = max(
            (get_streak({**data, "log": {k: v for k, v in log.items() if k <= d}}, habit)
             for d in sorted(log.keys())), default=0
        )
        lines.append(f"| {habit} | {' | '.join(cells)} | {streak} days | {longest} days |")

    lines += ["", "## 📅 Today\n"]
    today_log = log.get(today, {})
    for habit in habits:
        mark = "✅" if today_log.get(habit) else "⬜"
        lines.append(f"- {mark} {habit}")

    lines += ["", "---", "🟩 = Done   ⬜ = Missed",
              "_Tracked with habit_bot.py — Telegram controlled_"]

    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def github_push(message: str) -> str:
    """Push habits.json and README.md to GitHub using the API — works on Railway."""
    import base64

    token = os.environ.get("GITHUB_TOKEN", "")
    repo  = os.environ.get("GITHUB_REPO", "")   # e.g. Rasel2510/daily-habits
    branch= os.environ.get("GITHUB_BRANCH", "main")

    if not token or not repo:
        return "❌ GitHub not configured. Add GITHUB_TOKEN and GITHUB_REPO to Railway variables."

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    base_url = f"https://api.github.com/repos/{repo}/contents"
    results  = []

    files_to_push = {
        "habits.json": DATA_FILE,
        "README.md":   README_FILE,
    }

    for filename, filepath in files_to_push.items():
        if not filepath.exists():
            continue
        try:
            with open(filepath, "rb") as f:
                content     = f.read()
            encoded_content = base64.b64encode(content).decode("utf-8")

            # Get current SHA (needed for update)
            get_resp = requests.get(f"{base_url}/{filename}",
                headers={**headers, "ref": branch}, timeout=10)
            sha = get_resp.json().get("sha", "") if get_resp.status_code == 200 else ""

            payload = {
                "message": message,
                "content": encoded_content,
                "branch":  branch,
            }
            if sha:
                payload["sha"] = sha

            put_resp = requests.put(f"{base_url}/{filename}",
                headers=headers, json=payload, timeout=15)

            if put_resp.status_code in (200, 201):
                results.append(f"✅ {filename} pushed")
            else:
                results.append(f"❌ {filename} failed: {put_resp.json().get('message','unknown error')}")
        except Exception as e:
            results.append(f"❌ {filename} error: {e}")

    return "\n".join(results) if results else "❌ Nothing to push."


def git_push(message: str) -> str:
    """Try GitHub API first (Railway), fall back to local git."""
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if github_token:
        return github_push(message)
    # Local git fallback
    try:
        if not (BASE_DIR / ".git").exists():
            return "❌ Git repo not found. Add GITHUB_TOKEN to Railway variables."
        subprocess.run(["git", "add", "habits.json", "README.md"], cwd=BASE_DIR, check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=BASE_DIR)
        if result.returncode == 0:
            return "ℹ️ Nothing new to commit."
        subprocess.run(["git", "commit", "-m", message], cwd=BASE_DIR, check=True)
        remotes = subprocess.run(["git", "remote"], cwd=BASE_DIR, capture_output=True, text=True)
        if remotes.stdout.strip():
            subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
            return "✅ Committed and pushed to GitHub!"
        return "✅ Committed locally."
    except Exception as e:
        return f"❌ Git error: {e}"

# ── Telegram API ──────────────────────────────────────────────────────────────

class TelegramBot:
    def __init__(self, token: str):
        self.token   = token
        self.base    = f"https://api.telegram.org/bot{token}"
        self.offset  = 0
        # pending interactive sessions: chat_id → {"habits": [...], "index": 0, "done": {}}
        self.sessions = {}

    def send(self, chat_id: str, text: str, keyboard=None):
        payload = {
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": "HTML",
        }
        if keyboard:
            payload["reply_markup"] = json.dumps({
                "inline_keyboard": keyboard
            })
        try:
            requests.post(f"{self.base}/sendMessage", json=payload, timeout=10)
        except Exception as e:
            print(f"Send error: {e}")

    def answer_callback(self, callback_id: str, text: str = ""):
        try:
            requests.post(f"{self.base}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text}, timeout=5)
        except:
            pass

    def get_updates(self) -> list:
        try:
            resp = requests.get(
                f"{self.base}/getUpdates",
                params={"offset": self.offset, "timeout": 30, "limit": 10},
                timeout=35
            )
            if resp.status_code == 200:
                updates = resp.json().get("result", [])
                if updates:
                    self.offset = updates[-1]["update_id"] + 1
                return updates
        except Exception as e:
            print(f"Poll error: {e}")
            time.sleep(3)
        return []

    # ── Command handlers ──────────────────────────────────────────────────────

    def cmd_start(self, chat_id: str):
        self.send(chat_id,
            "👋 <b>Hey Rasel! Habit Bot is running.</b>\n\n"
            "Here's what I can do:\n\n"
            "✅ /done — mark all habits done today\n"
            "☑️ /check — check off one by one\n"
            "📊 /status — today's progress\n"
            "🔥 /streak — your current streaks\n"
            "📅 /summary — last 7 days\n"
            "➕ /add &lt;habit&gt; — add new habit\n"
            "➖ /remove &lt;habit&gt; — remove habit\n"
            "🚀 /push — commit &amp; push to GitHub\n"
            "❓ /help — show this message"
        )

    def cmd_status(self, chat_id: str):
        data    = load_data()
        today   = today_str()
        log     = data["log"].get(today, {})
        habits  = data["habits"]
        done    = sum(1 for h in habits if log.get(h))
        total   = len(habits)
        pct     = round(done / total * 100) if total else 0

        bar = "█" * done + "░" * (total - done)
        lines = [
            f"📅 <b>Today — {today}</b>",
            f"Progress: [{bar}] {done}/{total} ({pct}%)\n",
        ]
        for habit in habits:
            mark = "✅" if log.get(habit) else "⬜"
            streak = get_streak(data, habit)
            fire   = f" 🔥{streak}" if streak > 1 else ""
            lines.append(f"{mark} {habit}{fire}")
        self.send(chat_id, "\n".join(lines))

    def cmd_done(self, chat_id: str):
        data  = load_data()
        today = today_str()
        data["log"].setdefault(today, {})
        for habit in data["habits"]:
            data["log"][today][habit] = True
        save_data(data)
        update_readme(data)
        msg = git_push(f"✅ all habits done on {today}")
        total = len(data["habits"])
        self.send(chat_id,
            f"🎉 <b>All {total} habits marked done!</b>\n"
            f"📅 {today}\n\n{msg}"
        )

    def cmd_streak(self, chat_id: str):
        data   = load_data()
        habits = data["habits"]
        lines  = ["🔥 <b>Current Streaks</b>\n"]
        for habit in habits:
            streak = get_streak(data, habit)
            bar    = "🟩" * min(streak, 7)
            if streak == 0:
                bar = "⬜ no streak yet"
            lines.append(f"{habit}\n  {bar} <b>{streak} days</b>\n")
        self.send(chat_id, "\n".join(lines))

    def cmd_summary(self, chat_id: str):
        data   = load_data()
        habits = data["habits"]
        log    = data["log"]
        days   = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        lines  = ["📅 <b>Last 7 Days</b>\n"]
        for habit in habits:
            cells = "".join("🟩" if log.get(d, {}).get(habit) else "⬜" for d in days)
            done  = sum(1 for d in days if log.get(d, {}).get(habit))
            lines.append(f"{habit}\n  {cells} {done}/7\n")
        self.send(chat_id, "\n".join(lines))

    def cmd_check(self, chat_id: str):
        """Start interactive one-by-one check-off with inline buttons."""
        data   = load_data()
        habits = data["habits"]
        if not habits:
            self.send(chat_id, "No habits found. Add one with /add")
            return
        today = today_str()
        log   = data["log"].get(today, {})
        self.sessions[chat_id] = {
            "habits": habits,
            "index":  0,
            "done":   {h: log.get(h, False) for h in habits}
        }
        self._ask_habit(chat_id)

    def _ask_habit(self, chat_id: str):
        session = self.sessions.get(chat_id)
        if not session:
            return
        idx    = session["index"]
        habits = session["habits"]
        if idx >= len(habits):
            self._finish_check(chat_id)
            return
        habit  = habits[idx]
        done   = session["done"].get(habit, False)
        status = "✅ already done" if done else "⬜ not done yet"
        self.send(chat_id,
            f"<b>Habit {idx+1}/{len(habits)}</b>\n\n"
            f"{habit}\n<i>{status}</i>\n\nDid you do this today?",
            keyboard=[
                [
                    {"text": "✅ Done",   "callback_data": f"check_yes_{idx}"},
                    {"text": "⬜ Skip",   "callback_data": f"check_no_{idx}"},
                ],
                [{"text": "🏁 Finish early", "callback_data": "check_finish"}]
            ]
        )

    def _finish_check(self, chat_id: str):
        session = self.sessions.pop(chat_id, None)
        if not session:
            return
        data  = load_data()
        today = today_str()
        data["log"].setdefault(today, {})
        done_count = 0
        for habit, val in session["done"].items():
            data["log"][today][habit] = val
            if val:
                done_count += 1
        save_data(data)
        update_readme(data)
        total = len(session["habits"])
        msg   = git_push(f"📊 habits: {done_count}/{total} done on {today}")
        self.send(chat_id,
            f"🎯 <b>Check-in complete!</b>\n"
            f"✅ {done_count}/{total} habits done today\n\n{msg}"
        )

    def cmd_add(self, chat_id: str, text: str):
        name = text.replace("/add", "").strip()
        if not name:
            self.send(chat_id, "Usage: /add 🏋️ Workout")
            return
        data = load_data()
        if name in data["habits"]:
            self.send(chat_id, f"⚠️ <b>{name}</b> already exists.")
            return
        data["habits"].append(name)
        save_data(data)
        update_readme(data)
        git_push(f"➕ added habit: {name}")
        self.send(chat_id, f"✅ Added: <b>{name}</b>")

    def cmd_remove(self, chat_id: str, text: str):
        name = text.replace("/remove", "").strip()
        if not name:
            self.send(chat_id, "Usage: /remove 🏋️ Workout")
            return
        data = load_data()
        if name not in data["habits"]:
            self.send(chat_id,
                f"❌ <b>{name}</b> not found.\n\n"
                f"Your habits:\n" + "\n".join(f"• {h}" for h in data["habits"])
            )
            return
        data["habits"].remove(name)
        save_data(data)
        update_readme(data)
        git_push(f"➖ removed habit: {name}")
        self.send(chat_id, f"✅ Removed: <b>{name}</b>")

    def cmd_push(self, chat_id: str):
        data = load_data()
        update_readme(data)
        today = today_str()
        msg   = git_push(f"🚀 manual push on {today}")
        self.send(chat_id, msg)

    def cmd_help(self, chat_id: str):
        self.cmd_start(chat_id)

    # ── Update router ─────────────────────────────────────────────────────────

    def handle_update(self, update: dict):
        # Inline button callbacks
        if "callback_query" in update:
            cb      = update["callback_query"]
            chat_id = str(cb["message"]["chat"]["id"])
            data_cb = cb.get("data", "")
            self.answer_callback(cb["id"])

            if data_cb.startswith("check_yes_"):
                idx     = int(data_cb.split("_")[2])
                session = self.sessions.get(chat_id)
                if session:
                    habit = session["habits"][idx]
                    session["done"][habit] = True
                    session["index"] = idx + 1
                    self._ask_habit(chat_id)

            elif data_cb.startswith("check_no_"):
                idx     = int(data_cb.split("_")[2])
                session = self.sessions.get(chat_id)
                if session:
                    session["index"] = idx + 1
                    self._ask_habit(chat_id)

            elif data_cb == "check_finish":
                self._finish_check(chat_id)
            return

        # Text messages
        if "message" not in update:
            return
        msg     = update["message"]
        chat_id = str(msg["chat"]["id"])
        text    = msg.get("text", "").strip()

        if not text:
            return

        cmd = text.split()[0].split("@")[0].lower()

        if cmd == "/start":         self.cmd_start(chat_id)
        elif cmd == "/status":      self.cmd_status(chat_id)
        elif cmd == "/done":        self.cmd_done(chat_id)
        elif cmd == "/streak":      self.cmd_streak(chat_id)
        elif cmd == "/summary":     self.cmd_summary(chat_id)
        elif cmd == "/check":       self.cmd_check(chat_id)
        elif cmd == "/add":         self.cmd_add(chat_id, text)
        elif cmd == "/remove":      self.cmd_remove(chat_id, text)
        elif cmd == "/push":        self.cmd_push(chat_id)
        elif cmd == "/help":        self.cmd_help(chat_id)
        else:
            self.send(chat_id, "❓ Unknown command. Send /help to see all commands.")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        cfg     = load_bot_config()
        chat_id = cfg.get("chat_id", "")
        print(f"Bot started! Send a message to your bot on Telegram.")
        print(f"Press Ctrl+C to stop.\n")
        if chat_id:
            self.send(chat_id, "🤖 <b>Habit Bot started!</b>\nSend /help to see all commands.")
        while True:
            try:
                updates = self.get_updates()
                for update in updates:
                    self.handle_update(update)
            except KeyboardInterrupt:
                print("\nBot stopped.")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)


# ── Setup wizard ──────────────────────────────────────────────────────────────

def setup_wizard():
    print("\n=== Habit Bot Setup ===\n")
    cfg = load_bot_config()

    print("Step 1: Get your bot token")
    print("  → Open Telegram → search @BotFather → /newbot → copy token\n")
    token = input(f"Bot token [{cfg.get('token', 'not set')}]: ").strip()
    if token:
        cfg["token"] = token

    print("\nStep 2: Get your chat ID")
    print("  → Search @userinfobot on Telegram → /start → copy your id\n")
    chat_id = input(f"Your chat ID [{cfg.get('chat_id', 'not set')}]: ").strip()
    if chat_id:
        cfg["chat_id"] = chat_id

    save_bot_config(cfg)
    print("\nConfig saved to bot_config.json")

    # Test message
    if cfg.get("token") and cfg.get("chat_id"):
        print("Sending test message...")
        bot = TelegramBot(cfg["token"])
        bot.send(cfg["chat_id"],
            "✅ <b>Bot connected successfully!</b>\n"
            "Run <code>py habit_bot.py</code> to start.\n"
            "Then send /help to see all commands."
        )
        print("Check your Telegram — you should have a message!")
    print("\nRun:  py habit_bot.py")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if args and args[0] == "--setup":
        setup_wizard()
        return

    cfg = load_bot_config()
    if not cfg.get("token"):
        print("Bot not configured. Run: py habit_bot.py --setup")
        return

    bot = TelegramBot(cfg["token"])
    bot.run()


if __name__ == "__main__":
    main()
