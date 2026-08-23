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
from instagrapi.exceptions import LoginRequired, ChallengeRequired, RateLimitError

app = Flask(__name__)
app.secret_key = "F53D8A1C9E2B7F4A6D8E1F3C5B7A9D2E"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect('spam_engine.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        session_id TEXT,
        password TEXT,
        full_name TEXT,
        created_at TEXT
    )''')
    
    # Campaigns table
    c.execute('''CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        target_url TEXT,
        target_name TEXT,
        messages TEXT,
        delay REAL,
        status TEXT,
        sent_count INTEGER DEFAULT 0,
        fail_count INTEGER DEFAULT 0,
        started_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Logs table
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        level TEXT,
        created_at TEXT
    )''')
    
    conn.commit()
    conn.close()

init_db()

# ================= HELPERS =================
def get_db():
    return sqlite3.connect('spam_engine.db')

def log_event(user_id, msg, level="info"):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO logs (user_id, message, level, created_at) VALUES (?, ?, ?, ?)",
              (user_id, msg, level, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    print(f"[{user_id}] [{level}] {msg}")

def get_user_by_id(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, session_id, password, full_name, created_at FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "session_id": row[2], "password": row[3], 
                "full_name": row[4], "created_at": row[5]}
    return None

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, full_name, created_at FROM users ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_campaigns(user_id=None):
    conn = get_db()
    c = conn.cursor()
    if user_id:
        c.execute("SELECT * FROM campaigns WHERE user_id = ? ORDER BY id DESC", (user_id,))
    else:
        c.execute("SELECT * FROM campaigns ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_logs(user_id=None, limit=30):
    conn = get_db()
    c = conn.cursor()
    if user_id:
        c.execute("SELECT * FROM logs WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    else:
        c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def login_with_session(session_id, username=""):
    cl = Client()
    cl.request_timeout = 15
    cl.set_user_agent("Instagram 269.0.0.18.96 Android")
    
    sid = session_id.strip()
    if '%3A' in sid:
        sid = urllib.parse.unquote(sid)
    
    try:
        cl.login_by_sessionid(sid)
        return cl
    except Exception as e:
        raise Exception(f"Login failed: {e}")

# ================= SPAM ENGINE =================
running_campaigns = {}
active_campaigns = {}

def spam_engine(campaign_id, user_id, target_url, target_name, messages, delay):
    global running_campaigns, active_campaigns
    
    user = get_user_by_id(user_id)
    if not user:
        return
    
    try:
        cl = login_with_session(user["session_id"], user["username"])
        
        # Extract thread ID
        thread_id = None
        match = re.search(r'/t/(\d+)/', target_url)
        if match:
            thread_id = match.group(1)
        
        if not thread_id:
            log_event(user_id, f"❌ Invalid thread URL!", "error")
            return
        
        msg_list = [m.strip() for m in messages.split('\n') if m.strip()]
        if not msg_list:
            msg_list = ["🔥 SPAM ACTIVE"]
        
        msg_idx = 0
        sent = 0
        failed = 0
        
        # Update status
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE campaigns SET status = 'running', started_at = ? WHERE id = ?",
                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), campaign_id))
        conn.commit()
        conn.close()
        
        active_campaigns[campaign_id] = True
        
        while active_campaigns.get(campaign_id, False):
            try:
                msg = msg_list[msg_idx % len(msg_list)]
                msg_idx += 1
                msg = msg.replace("{target}", target_name or "TARGET")
                
                cl.direct_send(msg, thread_ids=[thread_id])
                sent += 1
                log_event(user_id, f"📨 Sent #{sent} to {target_name}", "success")
                
                # Update stats
                conn = get_db()
                c = conn.cursor()
                c.execute("UPDATE campaigns SET sent_count = ? WHERE id = ?", (sent, campaign_id))
                conn.commit()
                conn.close()
                
                time.sleep(float(delay or 3.0))
                
            except Exception as e:
                failed += 1
                log_event(user_id, f"❌ Send failed: {e}", "error")
                
                if "login" in str(e).lower() or "session" in str(e).lower():
                    try:
                        cl = login_with_session(user["session_id"], user["username"])
                    except:
                        log_event(user_id, "❌ Re-login failed!", "error")
                        break
                
                time.sleep(5)
        
        # Mark stopped
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE campaigns SET status = 'stopped' WHERE id = ?", (campaign_id,))
        conn.commit()
        conn.close()
        
        log_event(user_id, f"⏹️ Stopped. Sent: {sent}, Failed: {failed}", "info")
        
    except Exception as e:
        log_event(user_id, f"❌ Engine crashed: {e}", "error")
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE campaigns SET status = 'crashed' WHERE id = ?", (campaign_id,))
        conn.commit()
        conn.close()
    
    active_campaigns[campaign_id] = False

# ================= ROUTES =================
@app.route("/")
def index():
    return redirect("/panel")

@app.route("/panel")
def panel():
    users = get_all_users()
    campaigns = get_campaigns()
    logs = get_logs(limit=30)
    return render_template_string(PANEL_HTML, users=users, campaigns=campaigns, logs=logs)

@app.route("/add_user", methods=["POST"])
def add_user():
    username = request.form.get("username", "").strip()
    session_id = request.form.get("session_id", "").strip()
    password = request.form.get("password", "").strip()
    full_name = request.form.get("full_name", "").strip()
    
    if not username or not session_id:
        return jsonify({"status": "error", "message": "Username and Session ID required!"})
    
    try:
        cl = login_with_session(session_id, username)
        # Verify login
        cl.account_info()
    except Exception as e:
        return jsonify({"status": "error", "message": f"Invalid session: {e}"})
    
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (username, session_id, password, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
              (username, session_id, password, full_name or username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    user_id = c.lastrowid
    conn.close()
    
    log_event(user_id, f"✅ User {username} added!", "success")
    return jsonify({"status": "ok", "message": f"User {username} added!"})

@app.route("/start_campaign", methods=["POST"])
def start_campaign():
    user_id = request.form.get("user_id", "").strip()
    target_url = request.form.get("target_url", "").strip()
    target_name = request.form.get("target_name", "").strip()
    messages = request.form.get("messages", "").strip()
    delay = float(request.form.get("delay", 3.0))
    
    if not user_id or not target_url or not target_name:
        return jsonify({"status": "error", "message": "All fields required!"})
    
    if not messages:
        messages = "🔥 SPAM BY SNAPPY 🔥\n🚀 SYSTEM ONLINE\n💥 WAR MODE ACTIVE"
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO campaigns (user_id, target_url, target_name, messages, delay, status, started_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, target_url, target_name, messages, delay, "starting", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    campaign_id = c.lastrowid
    conn.close()
    
    thread = threading.Thread(target=spam_engine, args=(campaign_id, int(user_id), target_url, target_name, messages, delay))
    thread.daemon = True
    thread.start()
    
    log_event(user_id, f"🚀 Campaign {campaign_id} started on {target_name}", "success")
    return jsonify({"status": "ok", "message": f"Campaign started on {target_name}!"})

@app.route("/stop_campaign/<int:campaign_id>", methods=["POST"])
def stop_campaign(campaign_id):
    active_campaigns[campaign_id] = False
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE campaigns SET status = 'stopped' WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "message": "Campaign stopped!"})

@app.route("/delete_campaign/<int:campaign_id>", methods=["POST"])
def delete_campaign(campaign_id):
    active_campaigns.pop(campaign_id, None)
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "message": "Campaign deleted!"})

@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    c.execute("DELETE FROM campaigns WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM logs WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "message": "User deleted!"})

@app.route("/logs")
def get_logs_json():
    logs = get_logs(limit=50)
    return jsonify([{"user_id": l[1], "message": l[2], "level": l[3], "time": l[4]} for l in logs])

# ================= HTML PANEL =================
PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 SPAM ENGINE PRO</title>
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
        .item { background: #1a1a1a; padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
        .item .info { flex: 1; }
        .item .info .name { font-size: 15px; font-weight: 600; }
        .item .info .detail { font-size: 12px; color: #888; }
        .terminal { background: #000; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; border: 1px solid #333; color: #00ffcc; }
        .terminal .log-line { padding: 3px 0; border-bottom: 1px solid #0a0a0a; }
        .terminal .log-line .time { color: #666; margin-right: 10px; }
        .terminal .log-line .success { color: #00ff88; }
        .terminal .log-line .error { color: #ff4444; }
        .terminal .log-line .warning { color: #facc15; }
        .terminal .log-line .info { color: #38bdf8; }
        .text-muted { color: #888; font-size: 12px; }
        .flex { display: flex; gap: 10px; }
        .flex-1 { flex: 1; }
        .mt-10 { margin-top: 10px; }
    </style>
</head>
<body>
<div class="container">
    <div class="header"><h1>🔥 SPAM ENGINE PRO</h1><span style="color:#00ff88;">● STABLE</span></div>
    <div class="grid-2">
        <div>
            <div class="card">
                <h2>➕ Add Account</h2>
                <form id="addForm">
                    <input type="text" name="username" placeholder="Username" required>
                    <input type="text" name="session_id" placeholder="Session ID" required>
                    <input type="text" name="password" placeholder="Password (optional)">
                    <input type="text" name="full_name" placeholder="Full Name (optional)">
                    <button type="submit" class="btn btn-primary">Add Account</button>
                </form>
                <div id="addMsg" class="text-muted mt-10"></div>
            </div>
            
            <div class="card">
                <h2>🚀 Start Campaign</h2>
                <form id="startForm">
                    <select name="user_id" required>
                        <option value="">Select Account</option>
                        {% for user in users %}
                        <option value="{{ user[0] }}">@{{ user[1] }}</option>
                        {% endfor %}
                    </select>
                    <input type="text" name="target_url" placeholder="Thread URL (https://www.instagram.com/direct/t/...)" required>
                    <input type="text" name="target_name" placeholder="Target Name" required>
                    <textarea name="messages" placeholder="Messages (one per line)">🔥 SPAM BY SNAPPY 🔥
🚀 SYSTEM ONLINE
💥 WAR MODE ACTIVE</textarea>
                    <input type="number" name="delay" placeholder="Delay (sec)" value="3.0" step="0.5">
                    <button type="submit" class="btn btn-success">🚀 Start</button>
                </form>
                <div id="startMsg" class="text-muted mt-10"></div>
            </div>
            
            <div class="card">
                <h2>📱 Users</h2>
                {% for user in users %}
                <div class="item">
                    <div class="info"><div class="name">@{{ user[1] }}</div><div class="detail">Added: {{ user[3] }}</div></div>
                    <form method="POST" action="/delete_user/{{ user[0] }}" style="display:inline;">
                        <button type="submit" class="btn btn-danger btn-small" onclick="return confirm('Delete?')">🗑</button>
                    </form>
                </div>
                {% else %}
                <div class="text-muted">No users.</div>
                {% endfor %}
            </div>
        </div>
        
        <div>
            <div class="card">
                <h2>📊 Campaigns</h2>
                {% for camp in campaigns %}
                <div class="item">
                    <div class="info">
                        <div class="name">{{ camp[4] }} <span class="badge badge-{{ camp[7] }}">{{ camp[7]|upper }}</span></div>
                        <div class="detail">Sent: {{ camp[8] }} | Failed: {{ camp[9] }} | {% for u in users %}{% if u[0] == camp[1] %}@{{ u[1] }}{% endif %}{% endfor %}</div>
                    </div>
                    <div class="actions">
                        {% if camp[7] == 'running' or camp[7] == 'starting' %}
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
                    <div class="log-line"><span class="time">[{{ log[4] }}]</span><span class="{{ log[3] }}">[{{ log[3] }}]</span> {{ log[2] }}</div>
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
    const res = await fetch('/add_user', {method:'POST', body:new URLSearchParams(data)});
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
    print("🔥 SPAM ENGINE PRO Running on http://0.0.0.0:" + str(port))
    app.run(host="0.0.0.0", port=port, debug=False)
