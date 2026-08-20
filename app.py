from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import threading
import os
import json
import random
from itertools import cycle
from instagrapi import Client
import requests
import sqlite3
import time
import re
from datetime import datetime
import jwt
from pyngrok import ngrok  

app = Flask(__name__)
app.secret_key = "SNAPPY_KEY_ULTIMATE_SECURE_2026"

active_spam_threads = {}
lock_name_threads = {}
live_logs = {} 
app_start_time = time.time()
account_stats = {}
campaign_info = {}
dynamic_targets = {}
node_quarantine_status = {}

ADMIN_TG_BOT_TOKEN = "8797760883:AAGk050hX-7IK26deFOfR3e0Gu8KtbtqLC0"
ADMIN_TG_CHAT_ID = "7420788495"

# --- ADMIN LOGIN CREDENTIALS ---
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# --- CLIENT DATABASE (Initial dummy client) ---
CLIENT_DB = {
    "testclient": "testpass"
}

def send_telegram_alert(message):
    try:
        if ADMIN_TG_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
            url = f"https://api.telegram.org/bot{ADMIN_TG_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": ADMIN_TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram alert error: {e}")

def log_event(client_username, message, level="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {"time": timestamp, "msg": message, "level": level}
    if client_username not in live_logs:
        live_logs[client_username] = []
    live_logs[client_username].insert(0, log_entry)
    if len(live_logs[client_username]) > 300:
        live_logs[client_username].pop()

def init_db():
    conn = sqlite3.connect('panel_users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            full_name TEXT,
            followers INTEGER,
            following INTEGER,
            session_id TEXT,
            ip_address TEXT,
            device TEXT,
            added_at TEXT,
            owner TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- SIREN LISTS ---
SIREN_LIST_1 = [
    "𝗔𝗡𝗧𝗘𝗥 𝗠𝗔𝗡𝗧𝗘𝗥 𝗦𝗛𝗘𝗧𝗔𝗡𝗜 𝗞𝗛𝗢𝗣𝗗𝗔 < {target}> 𝗧𝗘𝗥𝗜 𝗠𝗔𝗔 𝗞𝗔 𝗕𝗛𝗢𝗦𝗗𝗔 🪼⋆｡𖦹°🫧⋆.ೃ࿔*:･"
]
SIREN_LIST_2 = [
    "< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??"
]
SIREN_LIST_3 = [
    "( {target} )-----------𝑷𝑹 𝑻𝑬𝑹𝑰 𝑴𝑨𝑨 𝑪𝑯𝑼𝑫𝑵𝑬 𝑲𝑰𝑼 𝑳𝑨𝑮 𝑮𝑨𝑰 <🙄🔥>"
]
SIREN_LIST_4 = [
    "𝑨𝒏𝒕𝒔 𝑰𝒏 𝒀𝒐𝒖𝒓 𝑨𝒔𝒔🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･⏔⏔⏔ ꒰ {target} ꒱ ⏔⏔⏔𝑨𝒏𝒕𝒔 𝑰𝒏 𝒀𝒐𝒖𝒓 𝑨𝒔𝒔🦀⋆｡𖦹°🫧⋆.ೃ࿔*:･"
]

def resolve_thread_id(cl, raw_input):
    raw_input = raw_input.strip()
    match = re.search(r'(\d{15,})', raw_input)
    if match:
        return match.group(1)
    return raw_input

def run_name_lock_worker(session_id, raw_gc_input, desired_name, module_key, uname):
    log_event(uname, f"NC Lock active. Enforcing: '{desired_name}'", "success")
    while lock_name_threads.get(module_key, False):
        try:
            cl = Client()
            cl.login_by_sessionid(session_id)
            thread_id = resolve_thread_id(cl, raw_gc_input)
            while lock_name_threads.get(module_key, False):
                try:
                    threads = cl.direct_threads(amount=20)
                    target_thread = None
                    for t in threads:
                        t_id = str(getattr(t, 'id', None) or getattr(t, 'pk', None))
                        if t_id == str(thread_id):
                            target_thread = t
                            break
                    if target_thread:
                        current_title = getattr(target_thread, 'title', '')
                        if current_title != desired_name:
                            cl.direct_thread_update_title(thread_id, desired_name)
                            log_event(uname, f"NC Lock: Name reverted!", "warning")
                    time.sleep(10)
                except:
                    time.sleep(5)
        except:
            log_event(uname, f"NC Lock Reconnecting...", "error")
            time.sleep(10)

def run_spam_worker(session_id, initial_target, custom_texts_list, template_list, target_scope, target_gc_input, custom_delay, module_key, uname):
    message_cycle = cycle(custom_texts_list if custom_texts_list else template_list)
    if uname not in account_stats:
        account_stats[uname] = {"sent": 0, "failed": 0, "gcs_count": 0, "target": initial_target, "active": True}
    dynamic_targets[uname] = initial_target
    campaign_info[uname] = {"target": initial_target, "active": True, "start_time": time.time()}

    while active_spam_threads.get(module_key, False):
        if node_quarantine_status.get(uname, False):
            time.sleep(5)
            continue
        try:
            cl = Client()
            cl.login_by_sessionid(session_id)
            log_event(uname, f"Authenticated.", "success")
            threads = cl.direct_threads(amount=99999)
            all_gc_ids = []
            for t in threads:
                t_id = getattr(t, 'id', None) or getattr(t, 'pk', None)
                if t_id:
                    all_gc_ids.append(str(t_id))
            
            if target_scope == "single":
                resolved_gc = resolve_thread_id(cl, target_gc_input)
                target_threads = [resolved_gc] if resolved_gc else all_gc_ids
                account_stats[uname]["gcs_count"] = 1
            else:
                target_threads = all_gc_ids
                account_stats[uname]["gcs_count"] = len(all_gc_ids)

            consecutive_errors = 0
            while active_spam_threads.get(module_key, False):
                if node_quarantine_status.get(uname, False):
                    break
                try:
                    if not target_threads:
                        time.sleep(3)
                        continue
                    current_target = dynamic_targets.get(uname, initial_target)

                    for thread_id in target_threads:
                        if not active_spam_threads.get(module_key, False) or node_quarantine_status.get(uname, False):
                            break
                        raw_text = next(message_cycle)
                        message = raw_text.replace("{target}", current_target)
                        try:
                            cl.direct_send(message, thread_ids=[thread_id])
                            account_stats[uname]["sent"] += 1
                            consecutive_errors = 0
                            log_event(uname, f"SENT ➔ Target: {current_target}", "success")
                            time.sleep(max(float(custom_delay), 2.0) + random.uniform(0.8, 3.5))
                        except Exception as ex:
                            account_stats[uname]["failed"] += 1
                            consecutive_errors += 1
                            if "block" in str(ex).lower() or "limit" in str(ex).lower():
                                node_quarantine_status[uname] = True
                                time.sleep(60)
                                node_quarantine_status[uname] = False
                                break
                            else:
                                log_event(uname, f"Error: {str(ex)[:35]}", "error")
                    time.sleep(2)
                except:
                    time.sleep(3)
        except:
            log_event(uname, f"Reconnecting...", "error")
            time.sleep(10)
    
    if uname in campaign_info:
        campaign_info[uname]["active"] = False

# ============================================================
# TERA ORIGINAL DARK RED LOGIN TEMPLATE
# ============================================================
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LOGIN V3</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: Arial, sans-serif; }
        body { background: #0a0000; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login-container { 
            background: #1a0a0a; padding: 30px; border-radius: 12px; border: 2px solid #ff0000; 
            box-shadow: 0 0 25px rgba(255, 0, 0, 0.6); width: 320px; text-align: center;
        }
        .header { color: #fff; font-size: 20px; font-weight: bold; margin-bottom: 20px; display: flex; justify-content: center; gap: 8px; }
        .section-title { color: #fff; font-size: 14px; font-weight: 600; text-align: left; margin-bottom: 10px; margin-top: 5px; }
        input { width: 100%; padding: 12px; border-radius: 6px; border: none; outline: none; background: #fff; font-size: 14px; margin-bottom: 10px; }
        .btn-red { width: 100%; padding: 12px; border: none; border-radius: 6px; background: #ff0000; color: #fff; font-weight: bold; font-size: 14px; cursor: pointer; transition: 0.3s; margin-bottom: 5px; }
        .btn-red:hover { background: #cc0000; }
        .divider { border: 0; height: 1px; background: #ff0000; opacity: 0.3; margin: 15px 0; }
        .alert { color: #ff6666; font-size: 13px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="header">⚡ LOGIN PANEL</div>
        
        {% if error %}<div class="alert">{{ error }}</div>{% endif %}

        <form method="POST" action="/login">
            <div class="section-title">User Login</div>
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit" name="role" value="client" class="btn-red">LOGIN USER</button>

            <hr class="divider">

            <div class="section-title">Owner Login</div>
            <input type="text" name="admin_username" placeholder="Owner Username" required>
            <input type="password" name="admin_password" placeholder="Owner Password" required>
            <button type="submit" name="role" value="admin" class="btn-red">LOGIN OWNER</button>
        </form>
    </div>
</body>
</html>
"""

# ============================================================
# DASHBOARD TEMPLATE
# ============================================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Control Panel</title>
    <style>
        body { background: #0b0f19; color: #f9fafb; font-family: sans-serif; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; border-bottom: 1px solid #1f2937; padding-bottom: 15px; margin-bottom: 20px; }
        .header h1 { font-size: 16px; margin: 0; }
        .grid { display: grid; grid-template-columns: 400px 1fr; gap: 20px; }
        .card { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .card h3 { font-size: 13px; border-bottom: 1px solid #1f2937; padding-bottom: 10px; margin-bottom: 15px; }
        input, select, textarea { width: 100%; padding: 8px; background: #0d1117; border: 1px solid #1f2937; color: #fff; border-radius: 4px; margin-bottom: 10px; }
        .btn { width: 100%; padding: 8px; background: #3b82f6; border: none; color: #fff; border-radius: 4px; cursor: pointer; }
        .btn-red { background: #ef4444; }
        .btn-green { background: #10b981; }
        .terminal { background: #0d1117; border: 1px solid #1f2937; border-radius: 8px; height: 400px; overflow-y: auto; padding: 10px; font-family: monospace; font-size: 12px; display: flex; flex-direction: column-reverse; }
        .success { color: #10b981; } .error { color: #ef4444; } .warning { color: #f59e0b; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>SIREN CLAN &mdash; User: {{ username }}</h1>
        <div><a href="/logout" style="color: #ef4444; text-decoration: none;">Logout</a></div>
    </div>

    {% if message %}
    <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid #10b981; color: #10b981; padding: 10px; border-radius: 4px; margin-bottom: 15px;">{{ message }}</div>
    {% endif %}

    <div class="grid">
        <div>
            {% if role == 'admin' %}
            <!-- SIRF ADMIN KO YE DIKHEGA: Create Client ID -->
            <div class="card" style="border-color: #10b981;">
                <h3 style="color: #10b981;">➕ Create Client ID (Admin Only)</h3>
                <form method="POST">
                    <input type="hidden" name="action_type" value="create_client">
                    <input type="text" name="new_client_user" placeholder="New Client Username" required>
                    <input type="text" name="new_client_pass" placeholder="New Client Password" required>
                    <button type="submit" class="btn btn-green">Create Client Account</button>
                </form>
            </div>
            {% endif %}

            <div class="card">
                <h3>Add Node Account</h3>
                <form method="POST">
                    <input type="hidden" name="action_type" value="add_session">
                    <input type="text" name="new_session_id" placeholder="Session ID Cookie" required>
                    <button type="submit" class="btn">Authorize Node</button>
                </form>
            </div>

            <div class="card" style="border-color: #10b981;">
                <h3 style="color: #10b981;">⚡ Live Target Switcher</h3>
                <form method="POST">
                    <input type="hidden" name="action_type" value="update_live_target">
                    <input type="text" name="new_target_name" placeholder="New Target Name" required>
                    <button type="submit" class="btn btn-green">Update Target</button>
                </form>
            </div>

            <div class="card">
                <h3>Group Name Lock (NC Lock)</h3>
                <form method="POST">
                    <input type="hidden" name="action_type" value="start_nc_lock">
                    <input type="text" name="lock_gc_input" placeholder="Group ID" required>
                    <input type="text" name="locked_name" placeholder="Locked Name" required>
                    <button type="submit" class="btn btn-warning" style="background: #f59e0b;">Enable Lock</button>
                </form>
            </div>

            <div class="card">
                <h3>Advanced Multi-Node Router</h3>
                <form method="POST">
                    <input type="hidden" name="action_type" value="start_spam">
                    <input type="text" name="target_name" placeholder="Target Identity" required>
                    
                    <div style="background: #0d1117; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                        <h4 style="margin:0 0 10px 0; font-size:12px;">Select Nodes:</h4>
                        {% for node in all_nodes %}
                        <label style="font-size:12px; display:block;"><input type="checkbox" name="selected_nodes" value="{{ node }}" checked> @{{ node }}</label>
                        {% endfor %}
                    </div>

                    <select name="spam_option">
                        <option value="opt1">Template 1</option>
                        <option value="opt2">Template 2</option>
                        <option value="opt_custom">Custom</option>
                    </select>
                    <textarea name="custom_text" placeholder="Custom lines"></textarea>
                    <button type="submit" class="btn">Launch Campaign</button>
                </form>
                <form method="POST" style="margin-top:5px;">
                    <input type="hidden" name="action_type" value="stop_spam">
                    <button type="submit" class="btn btn-red">Stop All</button>
                </form>
            </div>
        </div>

        <div>
            <div class="card">
                <h3>Live Telemetry Logs</h3>
                <div id="terminal" class="terminal">
                    <div class="success">[System] Console ready.</div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    function updateTelemetry() {
        fetch('/get_logs')
            .then(res => res.json())
            .then(data => {
                let terminal = document.getElementById('terminal');
                let html = '';
                data.logs.forEach(log => {
                    let cls = 'success';
                    if(log.level === 'error') cls = 'error';
                    if(log.level === 'warning') cls = 'warning';
                    html += `<div class="${cls}">[${log.time}] ${log.msg}</div>`;
                });
                terminal.innerHTML = html;
            });
    }
    setInterval(updateTelemetry, 1500);
</script>
</body>
</html>
"""

# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET", "POST"])
def index():
    if "username" not in session:
        return redirect(url_for("login_page"))
    
    role = session.get("role")
    username = session.get("username")
    message = None

    if request.method == "POST":
        action_type = request.form.get("action_type")
        
        # --- SIRF ADMIN KAAM KAR SAKTA HAI ID CREATE KARNE ME ---
        if action_type == "create_client":
            if role != "admin":
                message = "Access Denied! Only Admin can create clients."
            else:
                new_u = request.form.get("new_client_user").strip()
                new_p = request.form.get("new_client_pass").strip()
                if new_u and new_p:
                    if new_u in CLIENT_DB:
                        message = "Client username already exists!"
                    else:
                        CLIENT_DB[new_u] = new_p
                        message = f"Client @{new_u} created successfully! Password: {new_p}"
                        log_event("System", f"Admin created client: {new_u}", "success")
                else:
                    message = "Fill all fields!"

        elif action_type == "add_session":
            new_sid = request.form.get("new_session_id", "").strip()
            try:
                cl = Client()
                cl.login_by_sessionid(new_sid)
                acc_info = cl.account_info()
                uname_db = acc_info.username
                full_name = acc_info.full_name or "N/A"
                conn = sqlite3.connect('panel_users.db')
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO sessions (username, full_name, session_id, owner) VALUES (?, ?, ?, ?)", 
                               (uname_db, full_name, new_sid, username))
                conn.commit()
                conn.close()
                message = f"Node @{uname_db} registered for {username}!"
                log_event(username, f"Registered @{uname_db}", "success")
            except Exception as e:
                message = f"Failed: {e}"

        elif action_type == "update_live_target":
            new_tgt = request.form.get("new_target_name", "").strip()
            if new_tgt:
                conn = sqlite3.connect('panel_users.db')
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM sessions WHERE owner = ?", (username,))
                for row in cursor.fetchall():
                    uname = row[0]
                    dynamic_targets[uname] = new_tgt
                conn.close()
                message = f"Target switched to: '{new_tgt}'"

        elif action_type == "start_spam":
            target_name = request.form.get("target_name")
            selected_nodes = request.form.getlist("selected_nodes")
            spam_option = request.form.get("spam_option")
            custom_text = request.form.get("custom_text", "").strip()

            if not selected_nodes:
                message = "Select at least one node!"
            else:
                selected_list = SIREN_LIST_1
                if spam_option == "opt2": selected_list = SIREN_LIST_2
                elif spam_option == "opt_custom": 
                    selected_list = [line.strip() for line in custom_text.split('\n') if line.strip()]

                for uname in selected_nodes:
                    conn = sqlite3.connect('panel_users.db')
                    cursor = conn.cursor()
                    cursor.execute("SELECT session_id FROM sessions WHERE username = ? AND owner = ?", (uname, username))
                    row = cursor.fetchone()
                    conn.close()
                    
                    if row:
                        sid = row[0]
                        module_key = f"spam_{uname}"
                        active_spam_threads[module_key] = True
                        t = threading.Thread(target=run_spam_worker, args=(sid, target_name, None, selected_list, "all", "", 3.5, module_key, uname))
                        t.daemon = True
                        t.start()
                        log_event(username, f"Node @{uname} deployed", "info")
                message = f"Campaign active for {username}."

        elif action_type == "stop_spam":
            conn = sqlite3.connect('panel_users.db')
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM sessions WHERE owner = ?", (username,))
            for acc in cursor.fetchall():
                active_spam_threads[f"spam_{acc[0]}"] = False
            conn.close()
            message = "All active threads halted."

    # Fetch only user's nodes
    conn = sqlite3.connect('panel_users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM sessions WHERE owner = ?", (username,))
    all_nodes = [row[0] for row in cursor.fetchall()]
    conn.close()

    return render_template_string(DASHBOARD_HTML, username=username, role=role, message=message, all_nodes=all_nodes)

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        role = request.form.get("role")
        
        if role == "admin":
            admin_u = request.form.get("admin_username")
            admin_p = request.form.get("admin_password")
            if admin_u == ADMIN_USER and admin_p == ADMIN_PASS:
                session["username"] = admin_u
                session["role"] = "admin"
                return redirect(url_for("index"))
            else:
                return render_template_string(LOGIN_HTML, error="Invalid Owner Login!")

        elif role == "client":
            username = request.form.get("username")
            password = request.form.get("password")
            
            if username in CLIENT_DB and CLIENT_DB[username] == password:
                session["username"] = username
                session["role"] = "client"
                return redirect(url_for("index"))
            else:
                return render_template_string(LOGIN_HTML, error="Invalid Client Credentials!")
    
    return render_template_string(LOGIN_HTML)

@app.route("/get_logs")
def get_logs():
    username = session.get("username", "Unknown")
    return jsonify({"logs": live_logs.get(username, [])})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.template_global()
def render_template_string(source, **context):
    from flask import render_template_string as rts
    return rts(source, **context)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    try:
        ngrok.set_auth_token("3I9s1ivPTyVes5lY6VGZEJYmjoA_HGAmAnRZdUqSkbSCyath")
        public_url = ngrok.connect(port).public_url
        print(f"\n * 🌐 Ngrok Public URL: {public_url} *\n")
    except:
        pass
    app.run(host="0.0.0.0", port=port, debug=False)
