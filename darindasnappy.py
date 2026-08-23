from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import threading
import os
import json
import time
import random
import sqlite3
import urllib.parse
import re
from datetime import datetime, timedelta
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, TwoFactorRequired, RateLimitError
import requests

app = Flask(__name__)
app.secret_key = "ULTRA_SPAM_PANEL_2024"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=6)

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect('ig_spam.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        session_id TEXT,
        password TEXT,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER,
        target_url TEXT,
        target_name TEXT,
        messages TEXT,
        nc_names TEXT,
        delay REAL,
        msg_count INTEGER DEFAULT 0,
        nc_count INTEGER DEFAULT 0,
        status TEXT,
        sent INTEGER DEFAULT 0,
        failed INTEGER DEFAULT 0,
        started_at TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account TEXT,
        message TEXT,
        level TEXT,
        created_at TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# ================= HELPERS =================
def get_db():
    return sqlite3.connect('ig_spam.db')

def log_event(account, msg, level="info"):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (account, message, level, created_at) VALUES (?, ?, ?, ?)",
              (account, msg, level, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    print(f"[{account}] [{level}] {msg}")

def login_with_session(session_id, username=""):
    cl = Client()
    cl.request_timeout = 15
    cl.set_user_agent("Instagram 269.0.0.18.96 Android (28/9; 420dpi; 1080x2232; samsung; SM-G973F; beyond1; qcom; en_US)")
    
    sid = session_id.strip()
    if '%3A' in sid:
        sid = urllib.parse.unquote(sid)
    
    try:
        cl.login_by_sessionid(sid)
        log_event(username, "✅ Login successful!", "success")
        return cl
    except LoginRequired:
        log_event(username, "❌ Session expired!", "error")
        raise Exception("Session expired! Please update session ID")
    except Exception as e:
        log_event(username, f"❌ Login failed: {e}", "error")
        raise e

def get_accounts():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, session_id, created_at FROM accounts ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_account_by_id(acc_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, session_id, password FROM accounts WHERE id = ?", (acc_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_campaigns():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM campaigns ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_logs(limit=50):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

# ================= SPAM WORKER WITH AUTO NC =================
running_campaigns = {}
active_spam = {}

NC_NAMES = [
    "🔒 LOCKED BY KING",
    "👑 ROYAL CLAN",
    "⚡ GOD MODE ON",
    "🔥 SPAM ZONE",
    "💀 DEAD ZONE",
    "🚀 SPEED RUN",
    "🎯 TARGET LOCKED",
    "🤖 BOT ACTIVE",
    "👾 GAME OVER",
    "🏆 VICTORY",
]

def spam_worker(campaign_id):
    global running_campaigns, active_spam
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
    camp = c.fetchone()
    conn.close()
    
    if not camp:
        return
    
    camp_id, acc_id, target_url, target_name, messages, nc_names, delay, msg_count, nc_count, status, sent, failed, started_at = camp
    
    acc = get_account_by_id(acc_id)
    if not acc:
        log_event("SYSTEM", f"❌ Account {acc_id} not found!", "error")
        return
    
    acc_id, username, session_id, password = acc
    
    # Parse NC names
    nc_list = [n.strip() for n in nc_names.split('\n') if n.strip()] if nc_names else NC_NAMES
    if not nc_list:
        nc_list = NC_NAMES
    
    # Parse messages
    msg_list = [m.strip() for m in messages.split('\n') if m.strip()]
    if not msg_list:
        msg_list = ["🔥 SPAM BY SNAPPY 🔥"]
    
    try:
        cl = login_with_session(session_id, username)
        log_event(username, f"🚀 Starting spam on {target_name}", "success")
        
        # Get thread ID
        thread_id = None
        if target_url:
            match = re.search(r'/t/(\d+)/', target_url)
            if match:
                thread_id = match.group(1)
            else:
                thread_id = target_url
        
        if not thread_id:
            log_event(username, "❌ Invalid thread URL!", "error")
            return
        
        msg_idx = 0
        nc_idx = 0
        sent_count = 0
        fail_count = 0
        msg_counter = 0
        
        # Update status
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE campaigns SET status = 'running', started_at = ? WHERE id = ?",
                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), campaign_id))
        conn.commit()
        conn.close()
        
        active_spam[campaign_id] = True
        
        while active_spam.get(campaign_id, False):
            try:
                # Get message
                msg = msg_list[msg_idx % len(msg_list)]
                msg_idx += 1
                msg = msg.replace("{target}", target_name or "TARGET")
                
                # SEND MESSAGE
                cl.direct_send(msg, thread_ids=[thread_id])
                sent_count += 1
                msg_counter += 1
                log_event(username, f"📨 Sent #{sent_count} to {target_name}", "success")
                
                # Update stats
                conn = get_db()
                c = conn.cursor()
                c.execute("UPDATE campaigns SET sent = ?, msg_count = ? WHERE id = ?", 
                         (sent_count, msg_counter, campaign_id))
                conn.commit()
                conn.close()
                
                # ========== AUTO NC NAME CHANGE ==========
                # Har 10 messages ke baad group name change
                if msg_counter >= 10:
                    msg_counter = 0
                    new_name = nc_list[nc_idx % len(nc_list)]
                    nc_idx += 1
                    
                    log_event(username, f"🔄 Changing group name to: {new_name}", "warning")
                    try:
                        cl.direct_thread_update_title(thread_id, new_name)
                        log_event(username, f"✅ Name changed to: {new_name}", "success")
                        
                        # Update nc_count
                        conn = get_db()
                        c = conn.cursor()
                        c.execute("UPDATE campaigns SET nc_count = nc_count + 1 WHERE id = ?", (campaign_id,))
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        log_event(username, f"❌ Name change failed: {e}", "error")
                
                # Delay
                time.sleep(float(delay or 2.0))
                
            except Exception as e:
                fail_count += 1
                log_event(username, f"❌ Send failed: {e}", "error")
                
                if "login" in str(e).lower() or "session" in str(e).lower():
                    log_event(username, "🔄 Re-logging...", "warning")
                    try:
                        cl = login_with_session(session_id, username)
                    except:
                        log_event(username, "❌ Re-login failed!", "error")
                        break
                
                time.sleep(5)
        
        # Mark stopped
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE campaigns SET status = 'stopped' WHERE id = ?", (campaign_id,))
        conn.commit()
        conn.close()
        
        log_event(username, f"⏹️ Stopped. Sent: {sent_count}, Failed: {fail_count}", "info")
        
    except Exception as e:
        log_event(username, f"❌ Campaign crashed: {e}", "error")
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE campaigns SET status = 'crashed' WHERE id = ?", (campaign_id,))
        conn.commit()
        conn.close()
    
    active_spam[campaign_id] = False
    running_campaigns.pop(campaign_id, None)

# ================= ROUTES =================
@app.route("/")
def index():
    return redirect("/panel")

@app.route("/panel")
def panel():
    accounts = get_accounts()
    campaigns = get_campaigns()
    logs = get_logs(50)
    return render_template_string(PANEL_HTML, accounts=accounts, campaigns=campaigns, logs=logs)

@app.route("/add_account", methods=["POST"])
def add_account():
    session_id = request.form.get("session_id", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    
    if not session_id:
        return jsonify({"status": "error", "message": "Session ID required!"})
    
    try:
        cl = login_with_session(session_id, username or "TEST")
        if not username:
            username = cl.username or f"user_{int(time.time())}"
    except Exception as e:
        return jsonify({"status": "error", "message": f"Invalid session: {e}"})
    
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO accounts (username, session_id, password, created_at) VALUES (?, ?, ?, ?)",
              (username, session_id, password, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    log_event(username, "✅ Account added!", "success")
    return jsonify({"status": "ok", "message": f"Account {username} added!"})

@app.route("/start_campaign", methods=["POST"])
def start_campaign():
    account_id = request.form.get("account_id", "").strip()
    target_url = request.form.get("target_url", "").strip()
    target_name = request.form.get("target_name", "").strip()
    messages = request.form.get("messages", "").strip()
    nc_names = request.form.get("nc_names", "").strip()
    delay = float(request.form.get("delay", 3.0))
    
    if not account_id or not target_url or not target_name:
        return jsonify({"status": "error", "message": "All fields required!"})
    
    if not messages:
        messages = "🔥 SPAM BY SNAPPY 🔥\n🚀 SYSTEM ONLINE\n💥 WAR MODE ACTIVE"
    
    if not nc_names:
        nc_names = "🔒 LOCKED BY KING\n👑 ROYAL CLAN\n⚡ GOD MODE\n🔥 SPAM ZONE"
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO campaigns (account_id, target_url, target_name, messages, nc_names, delay, status, started_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (account_id, target_url, target_name, messages, nc_names, delay, "starting", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    campaign_id = c.lastrowid
    conn.close()
    
    active_spam[campaign_id] = True
    thread = threading.Thread(target=spam_worker, args=(campaign_id,))
    thread.daemon = True
    thread.start()
    running_campaigns[campaign_id] = thread
    
    log_event("SYSTEM", f"🚀 Campaign {campaign_id} started on {target_name}", "success")
    return jsonify({"status": "ok", "message": f"Campaign started on {target_name}!"})

@app.route("/stop_campaign/<int:campaign_id>", methods=["POST"])
def stop_campaign(campaign_id):
    active_spam[campaign_id] = False
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE campaigns SET status = 'stopped' WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "message": "Campaign stopped!"})

@app.route("/delete_campaign/<int:campaign_id>", methods=["POST"])
def delete_campaign(campaign_id):
    active_spam.pop(campaign_id, None)
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "message": "Campaign deleted!"})

@app.route("/delete_account/<int:acc_id>", methods=["POST"])
def delete_account(acc_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
    c.execute("DELETE FROM campaigns WHERE account_id = ?", (acc_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "message": "Account deleted!"})

@app.route("/logs")
def get_logs_json():
    logs = get_logs(50)
    return jsonify([{"account": l[1], "message": l[2], "level": l[3], "time": l[4]} for l in logs])

# ================= HTML =================
PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 ULTRA SPAM PANEL</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0a0a0a; color: #fff; font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; background: #141414; padding: 15px 20px; border-radius: 12px; border: 1px solid #ff0055; margin-bottom: 20px; }
        .header h1 { color: #ff3b8d; font-size: 24px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media(max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }
        .card { background: #141414; border-radius: 12px; border: 1px solid #333; padding: 20px; margin-bottom: 20px; }
        .card h2 { color: #00ffcc; font-size: 18px; margin-bottom: 15px; }
        input, select, textarea { width: 100%; padding: 10px 14px; background: #1a1a1a; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 14px; margin-bottom: 10px; }
        textarea { min-height: 80px; resize: vertical; }
        input:focus, select:focus, textarea:focus { border-color: #ff0055; outline: none; }
        .btn { padding: 10px 20px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.3s; font-size: 14px; }
        .btn-primary { background: #ff0055; color: #fff; }
        .btn-primary:hover { background: #e6004d; }
        .btn-success { background: #00ff88; color: #000; }
        .btn-success:hover { background: #00e677; }
        .btn-danger { background: #ff4444; color: #fff; }
        .btn-danger:hover { background: #e60000; }
        .btn-warning { background: #facc15; color: #000; }
        .btn-warning:hover { background: #e6b800; }
        .btn-small { padding: 4px 10px; font-size: 11px; }
        .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
        .badge-running { background: #00ff88; color: #000; }
        .badge-stopped { background: #ff4444; color: #fff; }
        .badge-starting { background: #facc15; color: #000; }
        .account-item, .campaign-item { background: #1a1a1a; padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
        .account-item .info, .campaign-item .info { flex: 1; }
        .campaign-item .info .name { font-size: 14px; font-weight: 600; color: #00ffcc; }
        .campaign-item .info .detail { font-size: 12px; color: #888; }
        .terminal { background: #000; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; border: 1px solid #333; color: #00ffcc; }
        .terminal .log-line { padding: 3px 0; border-bottom: 1px solid #0a0a0a; }
        .terminal .log-line .time { color: #666; margin-right: 10px; }
        .terminal .log-line .success { color: #00ff88; }
        .terminal .log-line .error { color: #ff4444; }
        .terminal .log-line .warning { color: #facc15; }
        .terminal .log-line .info { color: #38bdf8; }
        .flex { display: flex; gap: 10px; }
        .flex-1 { flex: 1; }
        .mt-10 { margin-top: 10px; }
        .text-muted { color: #888; font-size: 12px; }
        .highlight { color: #ff3b8d; font-weight: 700; }
    </style>
</head>
<body>
<div class="container">
    <div class="header"><h1>🔥 ULTRA SPAM PANEL</h1><span style="color:#00ff88;">● AUTO NC NAME CHANGE</span></div>
    <div class="grid-2">
        <div>
            <div class="card">
                <h2>➕ Add Account</h2>
                <form id="addForm">
                    <input type="text" name="session_id" placeholder="Session ID" required>
                    <input type="text" name="username" placeholder="Username (auto-detect)">
                    <button type="submit" class="btn btn-primary">Add Account</button>
                </form>
                <div id="addMsg" class="text-muted mt-10"></div>
            </div>
            
            <div class="card">
                <h2>🚀 Start Campaign</h2>
                <form id="startForm">
                    <select name="account_id" required>
                        <option value="">Select Account</option>
                        {% for acc in accounts %}
                        <option value="{{ acc[0] }}">@{{ acc[1] }}</option>
                        {% endfor %}
                    </select>
                    <input type="text" name="target_url" placeholder="Thread URL (https://www.instagram.com/direct/t/...)" required>
                    <input type="text" name="target_name" placeholder="Target Name" required>
                    <textarea name="messages" placeholder="Messages (one per line)">🔥 SPAM BY SNAPPY 🔥
🚀 SYSTEM ONLINE
💥 WAR MODE ACTIVE
👑 KING IS HERE</textarea>
                    <textarea name="nc_names" placeholder="NC Names (one per line)">🔒 LOCKED BY KING
👑 ROYAL CLAN
⚡ GOD MODE
🔥 SPAM ZONE
💀 DEAD ZONE</textarea>
                    <input type="number" name="delay" placeholder="Delay (sec)" value="3.0" step="0.5">
                    <button type="submit" class="btn btn-success">🚀 Start Campaign</button>
                </form>
                <div id="startMsg" class="text-muted mt-10"></div>
                <div class="text-muted mt-10" style="color:#ff3b8d;">⚡ AUTO NC: Name changes every 10 messages!</div>
            </div>
            
            <div class="card">
                <h2>📱 Accounts</h2>
                {% for acc in accounts %}
                <div class="account-item">
                    <div class="info"><div class="name">@{{ acc[1] }}</div><div class="detail">Added: {{ acc[3] }}</div></div>
                    <form method="POST" action="/delete_account/{{ acc[0] }}" style="display:inline;">
                        <button type="submit" class="btn btn-danger btn-small" onclick="return confirm('Delete?')">🗑</button>
                    </form>
                </div>
                {% else %}
                <div class="text-muted">No accounts.</div>
                {% endfor %}
            </div>
        </div>
        
        <div>
            <div class="card">
                <h2>📊 Campaigns</h2>
                {% for camp in campaigns %}
                <div class="campaign-item">
                    <div class="info">
                        <div class="name">{{ camp[3] }} <span class="badge badge-{{ camp[8] }}">{{ camp[8]|upper }}</span></div>
                        <div class="detail">Sent: {{ camp[10] }} | Failed: {{ camp[11] }} | NC Changes: {{ camp[6] }} | Account: {% for acc in accounts %}{% if acc[0] == camp[1] %}@{{ acc[1] }}{% endif %}{% endfor %}</div>
                    </div>
                    <div class="actions">
                        {% if camp[8] == 'running' or camp[8] == 'starting' %}
                        <form method="POST" action="/stop_campaign/{{ camp[0] }}" style="display:inline;">
                            <button type="submit" class="btn btn-warning btn-small">⏹ Stop</button>
                        </form>
                        {% endif %}
                        <form method="POST" action="/delete_campaign/{{ camp[0] }}" style="display:inline;">
                            <button type="submit" class="btn btn-danger btn-small" onclick="return confirm('Delete?')">🗑</button>
                        </form>
                    </div>
                </div>
                {% else %}
                <div class="text-muted">No campaigns.</div>
                {% endfor %}
            </div>
            
            <div class="card">
                <h2>🖥️ Live Logs</h2>
                <button class="btn btn-small" style="background:#333;color:#fff;" onclick="loadLogs()">🔄 Refresh</button>
                <div id="terminal" class="terminal">
                    {% for log in logs %}
                    <div class="log-line"><span class="time">[{{ log[4] }}]</span><span class="{{ log[3] }}">[{{ log[2] }}]</span> {{ log[1] }}</div>
                    {% else %}
                    <div class="log-line">[SYSTEM] Ready...</div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
</div>
<script>
document.getElementById('addForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const data = new FormData(this);
    const res = await fetch('/add_account', {method:'POST', body:new URLSearchParams(data)});
    const result = await res.json();
    document.getElementById('addMsg').textContent = result.message;
    if(result.status === 'ok') setTimeout(() => location.reload(), 1000);
});

document.getElementById('startForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const data = new FormData(this);
    const res = await fetch('/start_campaign', {method:'POST', body:new URLSearchParams(data)});
    const result = await res.json();
    document.getElementById('startMsg').textContent = result.message;
    if(result.status === 'ok') setTimeout(() => location.reload(), 1000);
});

async function loadLogs() {
    const res = await fetch('/logs');
    const logs = await res.json();
    const terminal = document.getElementById('terminal');
    terminal.innerHTML = logs.map(log => 
        `<div class="log-line"><span class="time">[${log.time}]</span><span class="${log.level}">[${log.level}]</span> ${log.message}</div>`
    ).join('');
}
setInterval(loadLogs, 3000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("🔥 ULTRA SPAM PANEL Running on http://0.0.0.0:" + str(port))
    app.run(host="0.0.0.0", port=port, debug=False)
