from flask import Flask, render_template_string, request, redirect, url_for, session, send_file, jsonify
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
import urllib.parse
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "SNAPPY_KEY_ULTIMATE_SECURE"

# ================= OWNER CREDENTIALS =================
OWNER_USERNAME = "snappygod"
OWNER_PASSWORD = "ANISHHU11"

active_spam_threads = {}
lock_name_threads = {}
live_logs = []
app_start_time = time.time()
account_stats = {}
campaign_info = {}
dynamic_targets = {}
node_quarantine_status = {}

ADMIN_TG_BOT_TOKEN = "8797760883:AAGk050hX-7IK26deFOfR3e0Gu8KtbtqLC0"
ADMIN_TG_CHAT_ID = "7420788495"

# ================= DATABASE =================
def init_db():
    try:
        conn = sqlite3.connect('panel_users.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                is_owner INTEGER DEFAULT 0,
                created_by TEXT,
                created_at TEXT,
                total_nodes INTEGER DEFAULT 0,
                total_spam_sent INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT UNIQUE,
                full_name TEXT,
                followers INTEGER,
                following INTEGER,
                session_id TEXT,
                ip_address TEXT,
                device TEXT,
                added_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute("SELECT * FROM users WHERE username = ?", (OWNER_USERNAME,))
        if not cursor.fetchone():
            hashed_pw = generate_password_hash(OWNER_PASSWORD)
            cursor.execute("INSERT INTO users (username, password, is_owner, created_at) VALUES (?, ?, ?, ?)",
                          (OWNER_USERNAME, hashed_pw, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database error: {e}")
        return False

init_db()

# ================= SESSION HELPER =================
def get_session_file(username):
    os.makedirs("sessions", exist_ok=True)
    return f"sessions/{username}.pkl"

def login_with_session(session_id, username):
    cl = Client()
    session_file = get_session_file(username)
    
    if os.path.exists(session_file):
        try:
            with open(session_file, 'rb') as f:
                cl.load_settings(f.read())
            cl.login(username, "")
            return cl
        except Exception as e:
            print(f"Saved session failed: {e}")
    
    try:
        sid = session_id.strip()
        if '%3A' in sid:
            sid = urllib.parse.unquote(sid)
        
        try:
            cl.login_by_sessionid(sid)
            with open(session_file, 'wb') as f:
                f.write(cl.get_settings())
            return cl
        except Exception as e1:
            try:
                cl.set_user_agent("Instagram 269.0.0.18.96 Android")
                cl.login_by_sessionid(sid)
                with open(session_file, 'wb') as f:
                    f.write(cl.get_settings())
                return cl
            except Exception as e2:
                raise Exception(f"Session login failed: {e2}")
    except Exception as e:
        raise e

def refresh_session(cl, username):
    try:
        if cl is None:
            return None
        try:
            cl.get_user_id(cl.username)
            return cl
        except:
            session_file = get_session_file(username)
            if os.path.exists(session_file):
                try:
                    with open(session_file, 'rb') as f:
                        cl.load_settings(f.read())
                    cl.login(username, "")
                    return cl
                except:
                    return None
            return None
    except:
        return None

# ================= SPAM LISTS =================
def repeat_text(text, times=25):
    return "\n\n".join([text] * times)

SIREN_LIST_1 = [
    repeat_text("ANTAR MANTER SHETANI KHOPDA < {target}> TERI MAA KA BHOSDA"),
    repeat_text("MAI PITA HUN PANI < {target}> KI MAA RANDI"),
    repeat_text("< {target} > OYE TERI RANDI MAA KO HAKLA KE CHODU"),
    repeat_text("ACHHA SUN TO < {target}> TERI MAA KO BHAGA BHAGA CHODU"),
    repeat_text("< {target} > TERI BHEN KI TANG UTHA KE IDHER UDHER CHODUNGA"),
    repeat_text("< {target} > KUTTIYA BANA KI CODU TERI MAA KO")
]

SIREN_LIST_2 = [
    repeat_text("< {target} > TERI MAA KA BHOSDA??"),
    repeat_text("< {target} > TERI MAA KA BHOSDA??"),
    repeat_text("< {target} > TERI MAA KA BHOSDA??"),
    repeat_text("< {target} > TERI MAA KA BHOSDA??"),
    repeat_text("< {target} > TERI MAA KA BHOSDA??"),
    repeat_text("< {target} > TERI MAA KA BHOSDA??")
]

SIREN_LIST_3 = [
    repeat_text("( {target} ) PR TERI MAA CHUDNE KIUI LAG GAI"),
    repeat_text("( {target} ) PR TERI MAA CHUDNE KIUI LAG GAI"),
    repeat_text("( {target} ) PR TERI MAA CHUDNE KIUI LAG GAI"),
    repeat_text("( {target} ) PR TERI MAA CHUDNE KIUI LAG GAI")
]

SIREN_LIST_4 = [
    repeat_text("Ants In Your Ass 🐊 < {target} >")
]

# ================= LOGS =================
def log_event(message, level="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {"time": timestamp, "msg": message, "level": level}
    live_logs.insert(0, log_entry)
    if len(live_logs) > 300:
        live_logs.pop()

# ================= WORKERS =================
def resolve_thread_id(cl, raw_input):
    raw_input = raw_input.strip()
    match = re.search(r'(\d{15,})', raw_input)
    if match:
        return match.group(1)
    return raw_input

def run_spam_worker(session_id, initial_target, custom_texts_list, template_list, target_scope, target_gc_input, custom_delay, module_key, uname, user_id):
    if custom_texts_list:
        custom_texts_list = [repeat_text(text) for text in custom_texts_list]
    
    message_cycle = cycle(custom_texts_list if custom_texts_list else template_list)
    
    user_stats_key = f"{user_id}_{uname}"
    if user_stats_key not in account_stats:
        account_stats[user_stats_key] = {"sent": 0, "failed": 0, "gcs_count": 0, "target": initial_target, "active": True, "user_id": user_id}
    
    dynamic_targets[user_stats_key] = initial_target
    campaign_info[user_stats_key] = {"target": initial_target, "active": True, "start_time": time.time(), "user_id": user_id}

    cl = None
    reconnect_attempts = 0

    while active_spam_threads.get(module_key, False):
        try:
            if cl is None:
                cl = login_with_session(session_id, uname)
                if cl is None:
                    reconnect_attempts += 1
                    if reconnect_attempts > 3:
                        log_event(f"[{uname}] Failed to connect", "error")
                        break
                    time.sleep(10)
                    continue
                reconnect_attempts = 0
            
            try:
                cl.get_user_id(cl.username)
            except:
                log_event(f"[{uname}] Session expired", "warning")
                cl = None
                continue
            
            try:
                threads = cl.direct_threads(amount=99999)
                all_gc_ids = []
                for t in threads:
                    t_id = getattr(t, 'id', None) or getattr(t, 'pk', None)
                    if t_id:
                        all_gc_ids.append(str(t_id))
                
                if target_scope == "single":
                    resolved_gc = resolve_thread_id(cl, target_gc_input)
                    target_threads = [resolved_gc] if resolved_gc else all_gc_ids
                    account_stats[user_stats_key]["gcs_count"] = 1
                else:
                    target_threads = all_gc_ids
                    account_stats[user_stats_key]["gcs_count"] = len(all_gc_ids)
            except Exception as e:
                log_event(f"[{uname}] Failed to fetch threads", "error")
                time.sleep(10)
                continue

            while active_spam_threads.get(module_key, False):
                try:
                    if not target_threads:
                        time.sleep(3)
                        break
                    
                    current_target = dynamic_targets.get(user_stats_key, initial_target)
                    
                    for thread_id in target_threads:
                        if not active_spam_threads.get(module_key, False):
                            break
                        
                        raw_text = next(message_cycle)
                        message = raw_text.replace("{target}", current_target)
                        
                        try:
                            cl.direct_send(message, thread_ids=[thread_id])
                            account_stats[user_stats_key]["sent"] += 1
                            log_event(f"[{uname}] Sent to {current_target}", "success")
                            
                            time.sleep(max(float(custom_delay), 2.0) + random.uniform(0.8, 2.5))
                        except Exception as ex:
                            account_stats[user_stats_key]["failed"] += 1
                            log_event(f"[{uname}] Error: {str(ex)[:30]}", "error")
                            time.sleep(5)
                except Exception as inner_e:
                    log_event(f"[{uname}] Error: {str(inner_e)[:30]}", "warning")
                    time.sleep(3)
        except Exception as e:
            log_event(f"[{uname}] Worker error: {str(e)[:30]}", "error")
            cl = None
            time.sleep(10)
    
    if user_stats_key in campaign_info:
        campaign_info[user_stats_key]["active"] = False

# ================= HTML TEMPLATES (FIXED - NO EXTENDS) =================
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SNAPPY PANEL - Login</title>
    <style>
        body{background:#0b0f19;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
        .login-card{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:30px;width:360px}
        h1{text-align:center;font-size:18px}
        input{width:100%;padding:10px;background:#0d1117;border:1px solid #1f2937;color:#fff;border-radius:6px;margin-bottom:12px}
        .btn{width:100%;padding:10px;background:#3b82f6;border:none;color:#fff;border-radius:6px;cursor:pointer}
        .error{background:rgba(239,68,68,0.1);border:1px solid #ef4444;color:#ef4444;padding:10px;border-radius:6px;margin-bottom:12px}
    </style>
</head>
<body>
<div class="login-card">
    <h1>🔐 SNAPPY PANEL</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST">
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit" class="btn">Sign In</button>
    </form>
</div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SNAPPY PANEL</title>
    <style>
        *{box-sizing:border-box}
        body{background:#0b0f19;color:#f9fafb;font-family:sans-serif;margin:0;padding:20px}
        .container{max-width:1200px;margin:0 auto}
        .header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1f2937;padding-bottom:15px;margin-bottom:20px}
        .header h1{font-size:16px;margin:0}
        .user-info{display:flex;align-items:center;gap:15px;font-size:12px;color:#9ca3af}
        .role{background:#3b82f6;color:#fff;padding:2px 10px;border-radius:12px;font-size:10px}
        .role.owner{background:#f59e0b;color:#000}
        .nav-tabs{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
        .nav-tabs a{background:#111827;border:1px solid #1f2937;color:#9ca3af;padding:8px 16px;border-radius:6px;text-decoration:none;font-size:12px}
        .nav-tabs a.active{background:#3b82f6;color:#fff}
        .nav-tabs a.logout{background:#ef4444;color:#fff}
        .card{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:20px;margin-bottom:20px}
        .card-title{font-size:13px;font-weight:600;border-bottom:1px solid #1f2937;padding-bottom:10px;margin-bottom:15px}
        .form-group{margin-bottom:14px}
        label{display:block;font-size:11px;color:#9ca3af;margin-bottom:6px}
        input,select,textarea{width:100%;padding:10px;background:#0d1117;border:1px solid #1f2937;color:#f9fafb;border-radius:6px;font-size:13px}
        .btn{width:100%;padding:10px;background:#3b82f6;border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;margin-top:5px}
        .btn-danger{background:#ef4444}
        .btn-success{background:#10b981;color:#000}
        .terminal{background:#0d1117;border:1px solid #1f2937;border-radius:8px;height:460px;overflow-y:auto;padding:14px;font-size:12px;font-family:monospace;display:flex;flex-direction:column-reverse}
        .log-line{margin-bottom:6px}
        .success{color:#10b981}
        .error{color:#ef4444}
        .warning{color:#f59e0b}
        .info{color:#3b82f6}
        .grid-2{display:grid;grid-template-columns:420px 1fr;gap:20px}
        .stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:15px}
        .stat-box{background:#0d1117;border:1px solid #1f2937;border-radius:6px;padding:10px;text-align:center}
        .stat-box .number{font-size:20px;font-weight:700}
        .stat-box .label{font-size:10px;color:#9ca3af}
        .checkbox-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;background:#0d1117;padding:10px;border-radius:6px;border:1px solid #1f2937}
        .checkbox-item{display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer}
        .msg-box{padding:12px;margin-bottom:18px;border-radius:6px;font-size:12px;background:rgba(16,185,129,0.1);border:1px solid #10b981;color:#10b981}
        @media(max-width:900px){.grid-2{grid-template-columns:1fr}}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>SNAPPY PANEL</h1>
        <div class="user-info">
            <span>{{ session.get('username', '') }}</span>
            <span class="role{% if session.get('is_owner') %} owner{% endif %}">
                {% if session.get('is_owner') %}👑 OWNER{% else %}👤 CLIENT{% endif %}
            </span>
            <span>Uptime: <span id="uptime">0h 0m 0s</span></span>
        </div>
    </div>

    <div class="nav-tabs">
        <a href="/" class="active">Dashboard</a>
        <a href="/nodes">My Nodes</a>
        {% if session.get('is_owner') %}
            <a href="/clients">👥 Clients</a>
            <a href="/all_nodes">🌐 All Nodes</a>
        {% endif %}
        <a href="/logout" class="logout">Logout</a>
    </div>

    {% if message %}
        <div class="msg-box">{{ message }}</div>
    {% endif %}

    <div class="grid-2">
        <div>
            <div class="stats-grid">
                <div class="stat-box"><div class="number">{{ stats.nodes }}</div><div class="label">My Nodes</div></div>
                <div class="stat-box"><div class="number">{{ stats.sent }}</div><div class="label">Sent</div></div>
                <div class="stat-box"><div class="number">{{ stats.failed }}</div><div class="label">Failed</div></div>
                <div class="stat-box"><div class="number">{{ stats.active }}</div><div class="label">Active</div></div>
            </div>

            <div class="card">
                <div class="card-title">Add Node</div>
                <form method="POST">
                    <input type="hidden" name="action_type" value="add_session">
                    <div class="form-group">
                        <label>Session ID</label>
                        <input type="text" name="new_session_id" placeholder="Paste sessionid..." required>
                    </div>
                    <button type="submit" class="btn">Authorize</button>
                </form>
            </div>

            <div class="card">
                <div class="card-title">⚡ Target Switcher</div>
                <form method="POST">
                    <input type="hidden" name="action_type" value="update_live_target">
                    <div class="form-group">
                        <label>New Target</label>
                        <input type="text" name="new_target_name" placeholder="New target..." required>
                    </div>
                    <button type="submit" class="btn btn-success">Update</button>
                </form>
            </div>

            <div class="card">
                <div class="card-title">🚀 Launch Campaign</div>
                <form method="POST">
                    <input type="hidden" name="action_type" value="start_spam">
                    <div class="form-group">
                        <label>Select Nodes</label>
                        <div class="checkbox-grid">
                            {% if all_nodes %}
                                {% for node in all_nodes %}
                                    <label class="checkbox-item">
                                        <input type="checkbox" name="selected_nodes" value="{{ node }}" checked> @{{ node }}
                                    </label>
                                {% endfor %}
                            {% else %}
                                <span style="font-size:11px;color:#9ca3af;">No nodes registered.</span>
                            {% endif %}
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Target</label>
                        <input type="text" name="target_name" placeholder="Target Name" required>
                    </div>
                    <div class="form-group">
                        <label>Scope</label>
                        <select name="target_scope">
                            <option value="all">All Groups</option>
                            <option value="single">Single Group</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Single Group ID</label>
                        <input type="text" name="single_gc_input" placeholder="Thread ID...">
                    </div>
                    <div class="form-group">
                        <label>Delay (Seconds)</label>
                        <input type="number" step="any" name="custom_delay" value="3.5" min="2.0" required>
                    </div>
                    <div class="form-group">
                        <label>Template</label>
                        <select name="spam_option">
                            <option value="opt1">Template 1</option>
                            <option value="opt2">Template 2</option>
                            <option value="opt3">Template 3</option>
                            <option value="opt4">Template 4</option>
                            <option value="opt_custom">Custom</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Custom Lines (Use {target})</label>
                        <textarea name="custom_text" placeholder="Line 1 for {target}"></textarea>
                    </div>
                    <button type="submit" class="btn">Launch</button>
                </form>
                <form method="POST" style="margin-top:10px;">
                    <input type="hidden" name="action_type" value="stop_spam">
                    <button type="submit" class="btn btn-danger">Stop All</button>
                </form>
            </div>
        </div>

        <div>
            <div class="card">
                <div class="card-title">Live Logs</div>
                <div id="terminal" class="terminal">
                    <div class="log-line info">[System] Ready.</div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    let startTime = Math.floor(Date.now() / 1000) - {{ uptime_seconds }};
    setInterval(function() {
        let now = Math.floor(Date.now() / 1000);
        let diff = now - startTime;
        let h = Math.floor(diff / 3600);
        let m = Math.floor((diff % 3600) / 60);
        let s = diff % 60;
        document.getElementById('uptime').innerText = h + "h " + m + "m " + s + "s";
    }, 1000);

    function updateTelemetry() {
        fetch('/get_logs')
            .then(res => res.json())
            .then(data => {
                let terminal = document.getElementById('terminal');
                let html = '';
                data.logs.forEach(log => {
                    let cls = 'info';
                    if(log.level === 'success') cls = 'success';
                    if(log.level === 'error') cls = 'error';
                    if(log.level === 'warning') cls = 'warning';
                    html += `<div class="log-line ${cls}">[${log.time}] ${log.msg}</div>`;
                });
                terminal.innerHTML = html;
            });
    }
    setInterval(updateTelemetry, 1500);
</script>
</body>
</html>
"""

NODES_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SNAPPY PANEL - Nodes</title>
    <style>
        *{box-sizing:border-box}
        body{background:#0b0f19;color:#f9fafb;font-family:sans-serif;margin:0;padding:20px}
        .container{max-width:1200px;margin:0 auto}
        .header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1f2937;padding-bottom:15px;margin-bottom:20px}
        .header h1{font-size:16px;margin:0}
        .user-info{display:flex;align-items:center;gap:15px;font-size:12px;color:#9ca3af}
        .role{background:#3b82f6;color:#fff;padding:2px 10px;border-radius:12px;font-size:10px}
        .role.owner{background:#f59e0b;color:#000}
        .nav-tabs{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
        .nav-tabs a{background:#111827;border:1px solid #1f2937;color:#9ca3af;padding:8px 16px;border-radius:6px;text-decoration:none;font-size:12px}
        .nav-tabs a.active{background:#3b82f6;color:#fff}
        .nav-tabs a.logout{background:#ef4444;color:#fff}
        .card{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:20px;margin-bottom:20px}
        .card-title{font-size:13px;font-weight:600;border-bottom:1px solid #1f2937;padding-bottom:10px;margin-bottom:15px}
        .btn-danger{background:#ef4444;border:none;color:#fff;border-radius:6px;cursor:pointer;padding:6px;font-size:11px;width:100%}
        .node-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:15px}
        .node-card{background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:15px}
        .node-header{display:flex;justify-content:space-between;border-bottom:1px solid #1f2937;padding-bottom:8px;margin-bottom:10px}
        .node-name{font-weight:600}
        .node-status{background:rgba(16,185,129,0.1);border:1px solid #10b981;color:#10b981;padding:2px 6px;font-size:10px;border-radius:4px}
        .node-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;text-align:center;background:#0b0f19;padding:8px;border-radius:6px;border:1px solid #1f2937;margin-bottom:12px}
        .stat-label{font-size:9px;color:#9ca3af}
        .stat-value{font-weight:700}
        .stat-value.success{color:#10b981}
        .stat-value.danger{color:#ef4444}
        .stat-value.primary{color:#3b82f6}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>SNAPPY PANEL</h1>
        <div class="user-info">
            <span>{{ session.get('username', '') }}</span>
            <span class="role{% if session.get('is_owner') %} owner{% endif %}">
                {% if session.get('is_owner') %}👑 OWNER{% else %}👤 CLIENT{% endif %}
            </span>
            <span>Uptime: <span id="uptime">0h 0m 0s</span></span>
        </div>
    </div>

    <div class="nav-tabs">
        <a href="/">Dashboard</a>
        <a href="/nodes" class="active">My Nodes</a>
        {% if session.get('is_owner') %}
            <a href="/clients">👥 Clients</a>
            <a href="/all_nodes">🌐 All Nodes</a>
        {% endif %}
        <a href="/logout" class="logout">Logout</a>
    </div>

    <div class="card">
        <div class="card-title">My Nodes</div>
        <div style="font-size:12px;color:#9ca3af;margin-bottom:15px">
            Total: <b style="color:#10b981;">{{ nodes|length }}</b>
        </div>
        <div class="node-grid">
            {% for node in nodes %}
                <div class="node-card">
                    <div class="node-header">
                        <span class="node-name">@{{ node.username }}</span>
                        <span class="node-status">{% if node.active %}ACTIVE{% else %}IDLE{% endif %}</span>
                    </div>
                    <div style="font-size:11px;color:#9ca3af;margin-bottom:8px">
                        Followers: {{ node.followers }} | Following: {{ node.following }}
                    </div>
                    <div class="node-stats">
                        <div><div class="stat-label">SENT</div><div class="stat-value success">{{ node.sent }}</div></div>
                        <div><div class="stat-label">FAILED</div><div class="stat-value danger">{{ node.failed }}</div></div>
                        <div><div class="stat-label">GCS</div><div class="stat-value primary">{{ node.gcs }}</div></div>
                    </div>
                    <form method="POST" action="/">
                        <input type="hidden" name="action_type" value="remove_node">
                        <input type="hidden" name="node_username" value="{{ node.username }}">
                        <button type="submit" class="btn-danger">Remove</button>
                    </form>
                </div>
            {% endfor %}
        </div>
    </div>
</div>

<script>
    let startTime = Math.floor(Date.now() / 1000) - {{ uptime_seconds }};
    setInterval(function() {
        let now = Math.floor(Date.now() / 1000);
        let diff = now - startTime;
        let h = Math.floor(diff / 3600);
        let m = Math.floor((diff % 3600) / 60);
        let s = diff % 60;
        document.getElementById('uptime').innerText = h + "h " + m + "m " + s + "s";
    }, 1000);
</script>
</body>
</html>
"""

CLIENTS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SNAPPY PANEL - Clients</title>
    <style>
        *{box-sizing:border-box}
        body{background:#0b0f19;color:#f9fafb;font-family:sans-serif;margin:0;padding:20px}
        .container{max-width:1200px;margin:0 auto}
        .header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1f2937;padding-bottom:15px;margin-bottom:20px}
        .header h1{font-size:16px;margin:0}
        .user-info{display:flex;align-items:center;gap:15px;font-size:12px;color:#9ca3af}
        .role{background:#f59e0b;color:#000;padding:2px 10px;border-radius:12px;font-size:10px}
        .nav-tabs{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
        .nav-tabs a{background:#111827;border:1px solid #1f2937;color:#9ca3af;padding:8px 16px;border-radius:6px;text-decoration:none;font-size:12px}
        .nav-tabs a.active{background:#3b82f6;color:#fff}
        .nav-tabs a.logout{background:#ef4444;color:#fff}
        .card{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:20px;margin-bottom:20px}
        .card-title{font-size:13px;font-weight:600;border-bottom:1px solid #1f2937;padding-bottom:10px;margin-bottom:15px}
        .form-group{margin-bottom:14px}
        label{display:block;font-size:11px;color:#9ca3af;margin-bottom:6px}
        input{width:100%;padding:10px;background:#0d1117;border:1px solid #1f2937;color:#f9fafb;border-radius:6px;font-size:13px}
        .btn{width:100%;padding:10px;background:#3b82f6;border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;margin-top:5px}
        .btn-success{background:#10b981;color:#000}
        .btn-danger{background:#ef4444;color:#fff;padding:6px;font-size:11px;width:100%;border:none;border-radius:6px;cursor:pointer}
        .client-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:15px;margin-top:20px}
        .client-card{background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:15px}
        .client-header{display:flex;justify-content:space-between;border-bottom:1px solid #1f2937;padding-bottom:8px;margin-bottom:10px}
        .client-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;text-align:center;margin-bottom:10px}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>SNAPPY PANEL</h1>
        <div class="user-info">
            <span>{{ session.get('username', '') }}</span>
            <span class="role">👑 OWNER</span>
            <span>Uptime: <span id="uptime">0h 0m 0s</span></span>
        </div>
    </div>

    <div class="nav-tabs">
        <a href="/">Dashboard</a>
        <a href="/nodes">My Nodes</a>
        <a href="/clients" class="active">👥 Clients</a>
        <a href="/all_nodes">🌐 All Nodes</a>
        <a href="/logout" class="logout">Logout</a>
    </div>

    <div class="card">
        <div class="card-title">👥 Client Management</div>
        <div class="card" style="border-color:#10b981;">
            <div class="card-title" style="color:#10b981;">➕ Create Client</div>
            <form method="POST" action="/">
                <input type="hidden" name="action_type" value="create_client">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="client_username" placeholder="client123" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="text" name="client_password" placeholder="password123" required>
                </div>
                <button type="submit" class="btn btn-success">Create</button>
            </form>
        </div>

        <div class="client-grid">
            {% for client in clients %}
                <div class="client-card">
                    <div class="client-header">
                        <span style="font-weight:600;">@{{ client.username }}</span>
                        <span style="font-size:10px;color:#9ca3af;">ID: {{ client.id }}</span>
                    </div>
                    <div class="client-stats">
                        <div><div style="font-size:9px;color:#9ca3af;">Nodes</div><strong>{{ client.nodes }}</strong></div>
                        <div><div style="font-size:9px;color:#9ca3af;">Sent</div><strong style="color:#10b981;">{{ client.total_sent }}</strong></div>
                        <div><div style="font-size:9px;color:#9ca3af;">Created</div><strong style="font-size:10px;">{{ client.created_at[:10] }}</strong></div>
                    </div>
                    <form method="POST" action="/">
                        <input type="hidden" name="action_type" value="delete_client">
                        <input type="hidden" name="client_id" value="{{ client.id }}">
                        <button type="submit" class="btn-danger">Delete Client</button>
                    </form>
                </div>
            {% endfor %}
        </div>
    </div>
</div>

<script>
    let startTime = Math.floor(Date.now() / 1000) - {{ uptime_seconds }};
    setInterval(function() {
        let now = Math.floor(Date.now() / 1000);
        let diff = now - startTime;
        let h = Math.floor(diff / 3600);
        let m = Math.floor((diff % 3600) / 60);
        let s = diff % 60;
        document.getElementById('uptime').innerText = h + "h " + m + "m " + s + "s";
    }, 1000);
</script>
</body>
</html>
"""

ALL_NODES_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SNAPPY PANEL - All Nodes</title>
    <style>
        *{box-sizing:border-box}
        body{background:#0b0f19;color:#f9fafb;font-family:sans-serif;margin:0;padding:20px}
        .container{max-width:1200px;margin:0 auto}
        .header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1f2937;padding-bottom:15px;margin-bottom:20px}
        .header h1{font-size:16px;margin:0}
        .user-info{display:flex;align-items:center;gap:15px;font-size:12px;color:#9ca3af}
        .role{background:#f59e0b;color:#000;padding:2px 10px;border-radius:12px;font-size:10px}
        .nav-tabs{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
        .nav-tabs a{background:#111827;border:1px solid #1f2937;color:#9ca3af;padding:8px 16px;border-radius:6px;text-decoration:none;font-size:12px}
        .nav-tabs a.active{background:#3b82f6;color:#fff}
        .nav-tabs a.logout{background:#ef4444;color:#fff}
        .card{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:20px;margin-bottom:20px}
        .card-title{font-size:13px;font-weight:600;border-bottom:1px solid #1f2937;padding-bottom:10px;margin-bottom:15px}
        .node-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:15px}
        .node-card{background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:15px}
        .node-header{display:flex;justify-content:space-between;border-bottom:1px solid #1f2937;padding-bottom:8px;margin-bottom:10px}
        .node-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;text-align:center;background:#0b0f19;padding:8px;border-radius:6px;border:1px solid #1f2937}
        .stat-label{font-size:9px;color:#9ca3af}
        .stat-value.success{color:#10b981}
        .stat-value.danger{color:#ef4444}
        .stat-value.primary{color:#3b82f6}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>SNAPPY PANEL</h1>
        <div class="user-info">
            <span>{{ session.get('username', '') }}</span>
            <span class="role">👑 OWNER</span>
            <span>Uptime: <span id="uptime">0h 0m 0s</span></span>
        </div>
    </div>

    <div class="nav-tabs">
        <a href="/">Dashboard</a>
        <a href="/nodes">My Nodes</a>
        <a href="/clients">👥 Clients</a>
        <a href="/all_nodes" class="active">🌐 All Nodes</a>
        <a href="/logout" class="logout">Logout</a>
    </div>

    <div class="card">
        <div class="card-title">🌐 All Nodes (All Clients)</div>
        <div class="node-grid">
            {% for node in all_nodes %}
                <div class="node-card">
                    <div class="node-header">
                        <span style="font-weight:600;">@{{ node.username }}</span>
                        <span style="font-size:10px;color:#9ca3af;">Client: {{ node.client }}</span>
                    </div>
                    <div style="font-size:11px;color:#9ca3af;margin-bottom:8px;">
                        Followers: {{ node.followers }}
                    </div>
                    <div class="node-stats">
                        <div><div class="stat-label">SENT</div><div class="stat-value success">{{ node.sent }}</div></div>
                        <div><div class="stat-label">FAILED</div><div class="stat-value danger">{{ node.failed }}</div></div>
                        <div><div class="stat-label">GCS</div><div class="stat-value primary">{{ node.gcs }}</div></div>
                    </div>
                </div>
            {% endfor %}
        </div>
    </div>
</div>

<script>
    let startTime = Math.floor(Date.now() / 1000) - {{ uptime_seconds }};
    setInterval(function() {
        let now = Math.floor(Date.now() / 1000);
        let diff = now - startTime;
        let h = Math.floor(diff / 3600);
        let m = Math.floor((diff % 3600) / 60);
        let s = diff % 60;
        document.getElementById('uptime').innerText = h + "h " + m + "m " + s + "s";
    }, 1000);
</script>
</body>
</html>
"""

# ================= ROUTES =================
@app.route("/", methods=["GET", "POST"])
def index():
    if "user_id" not in session:
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            
            try:
                conn = sqlite3.connect('panel_users.db')
                cursor = conn.cursor()
                cursor.execute("SELECT id, username, password, is_owner FROM users WHERE username = ?", (username,))
                user = cursor.fetchone()
                conn.close()
                
                if user and check_password_hash(user[2], password):
                    session["user_id"] = user[0]
                    session["username"] = user[1]
                    session["is_owner"] = bool(user[3])
                    return redirect(url_for("dashboard"))
                else:
                    return render_template_string(LOGIN_HTML, error="Invalid credentials!")
            except Exception as e:
                return render_template_string(LOGIN_HTML, error=f"Error: {str(e)[:30]}")
        
        return render_template_string(LOGIN_HTML)
    
    return redirect(url_for("dashboard"))

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("index"))
    
    user_id = session["user_id"]
    message = None
    
    try:
        conn = sqlite3.connect('panel_users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM sessions WHERE user_id = ?", (user_id,))
        user_nodes = [row[0] for row in cursor.fetchall()]
        
        if request.method == "POST":
            action_type = request.form.get("action_type")
            
            if action_type == "add_session":
                new_sid = request.form.get("new_session_id", "").strip()
                try:
                    cl = login_with_session(new_sid, "temp_user")
                    acc_info = cl.account_info()
                    username = acc_info.username
                    full_name = acc_info.full_name or "N/A"
                    
                    try:
                        user_id_from_insta = cl.user_id_from_username(username)
                        user_details = cl.user_info(user_id_from_insta)
                        followers = user_details.follower_count
                        following = user_details.following_count
                    except:
                        followers = 0
                        following = 0
                    
                    cursor.execute("INSERT OR REPLACE INTO sessions (user_id, username, full_name, followers, following, session_id, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                 (user_id, username, full_name, followers, following, new_sid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    cursor.execute("UPDATE users SET total_nodes = total_nodes + 1 WHERE id = ?", (user_id,))
                    conn.commit()
                    message = f"Node @{username} registered!"
                    log_event(f"Added node @{username}", "success")
                except Exception as e:
                    message = f"Registration failed: {str(e)[:50]}"
            
            elif action_type == "update_live_target":
                new_tgt = request.form.get("new_target_name", "").strip()
                if new_tgt:
                    for uname in user_nodes:
                        user_stats_key = f"{user_id}_{uname}"
                        dynamic_targets[user_stats_key] = new_tgt
                    message = f"Target switched to: '{new_tgt}'"
            
            elif action_type == "start_spam":
                target_name = request.form.get("target_name")
                target_scope = request.form.get("target_scope")
                single_gc_input = request.form.get("single_gc_input", "").strip()
                spam_option = request.form.get("spam_option")
                custom_text = request.form.get("custom_text", "").strip()
                selected_nodes = request.form.getlist("selected_nodes")
                custom_delay = float(request.form.get("custom_delay", 3.5) or 3.5)
                
                if not selected_nodes:
                    message = "Select at least one node!"
                else:
                    selected_list = SIREN_LIST_1
                    if spam_option == "opt2": selected_list = SIREN_LIST_2
                    elif spam_option == "opt3": selected_list = SIREN_LIST_3
                    elif spam_option == "opt4": selected_list = SIREN_LIST_4
                    elif spam_option == "opt_custom": 
                        selected_list = [line.strip() for line in custom_text.split('\n') if line.strip()] if custom_text else SIREN_LIST_1
                    
                    for uname in selected_nodes:
                        cursor.execute("SELECT session_id FROM sessions WHERE username = ? AND user_id = ?", (uname, user_id))
                        row = cursor.fetchone()
                        if row:
                            sid = row[0]
                            module_key = f"spam_{user_id}_{uname}"
                            active_spam_threads[module_key] = True
                            t = threading.Thread(target=run_spam_worker, args=(sid, target_name, None, selected_list, target_scope, single_gc_input, custom_delay, module_key, uname, user_id))
                            t.daemon = True
                            t.start()
                    message = f"Campaign started for '{target_name}'"
            
            elif action_type == "stop_spam":
                for uname in user_nodes:
                    active_spam_threads[f"spam_{user_id}_{uname}"] = False
                message = "Stopped all threads"
            
            elif action_type == "remove_node":
                node_username = request.form.get("node_username")
                cursor.execute("DELETE FROM sessions WHERE username = ? AND user_id = ?", (node_username, user_id))
                conn.commit()
                message = f"Removed @{node_username}"
            
            elif action_type == "create_client" and session.get("is_owner"):
                client_user = request.form.get("client_username", "").strip()
                client_pass = request.form.get("client_password", "").strip()
                if client_user and client_pass:
                    hashed = generate_password_hash(client_pass)
                    cursor.execute("INSERT INTO users (username, password, is_owner, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                                 (client_user, hashed, 0, session['username'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    message = f"Client @{client_user} created!"
            
            elif action_type == "delete_client" and session.get("is_owner"):
                client_id = request.form.get("client_id")
                cursor.execute("DELETE FROM users WHERE id = ? AND is_owner = 0", (client_id,))
                conn.commit()
                message = "Client deleted!"
        
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,))
        total_nodes = cursor.fetchone()[0] or 0
        
        total_sent = 0
        total_failed = 0
        active_count = 0
        for uname in user_nodes:
            stats_key = f"{user_id}_{uname}"
            stats = account_stats.get(stats_key, {})
            total_sent += stats.get("sent", 0)
            total_failed += stats.get("failed", 0)
            if active_spam_threads.get(f"spam_{user_id}_{uname}", False):
                active_count += 1
        
        conn.close()
        
        uptime_seconds = int(time.time() - app_start_time)
        return render_template_string(DASHBOARD_HTML, 
                                     message=message, 
                                     uptime_seconds=uptime_seconds, 
                                     all_nodes=user_nodes, 
                                     stats={"nodes": total_nodes, "sent": total_sent, "failed": total_failed, "active": active_count})
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/nodes")
def nodes():
    if "user_id" not in session:
        return redirect(url_for("index"))
    
    try:
        user_id = session["user_id"]
        conn = sqlite3.connect('panel_users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username, full_name, followers, following FROM sessions WHERE user_id = ?", (user_id,))
        nodes_data = cursor.fetchall()
        conn.close()
        
        nodes_list = []
        for username, full_name, followers, following in nodes_data:
            stats_key = f"{user_id}_{username}"
            stats = account_stats.get(stats_key, {})
            nodes_list.append({
                "username": username, 
                "full_name": full_name, 
                "followers": followers, 
                "following": following, 
                "sent": stats.get("sent", 0), 
                "failed": stats.get("failed", 0), 
                "gcs": stats.get("gcs_count", 0), 
                "active": active_spam_threads.get(f"spam_{user_id}_{username}", False)
            })
        
        uptime_seconds = int(time.time() - app_start_time)
        return render_template_string(NODES_HTML, nodes=nodes_list, uptime_seconds=uptime_seconds)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/clients")
def clients():
    if "user_id" not in session or not session.get("is_owner"):
        return redirect(url_for("dashboard"))
    
    try:
        conn = sqlite3.connect('panel_users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, created_at, total_nodes, total_spam_sent FROM users WHERE is_owner = 0 ORDER BY id DESC")
        clients_data = cursor.fetchall()
        conn.close()
        
        clients_list = []
        for id, username, created_at, total_nodes, total_spam_sent in clients_data:
            clients_list.append({
                "id": id, 
                "username": username, 
                "created_at": created_at, 
                "nodes": total_nodes or 0, 
                "total_sent": total_spam_sent or 0
            })
        
        uptime_seconds = int(time.time() - app_start_time)
        return render_template_string(CLIENTS_HTML, clients=clients_list, uptime_seconds=uptime_seconds)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/all_nodes")
def all_nodes():
    if "user_id" not in session or not session.get("is_owner"):
        return redirect(url_for("dashboard"))
    
    try:
        conn = sqlite3.connect('panel_users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT s.username, s.followers, u.username as client_name, s.user_id FROM sessions s JOIN users u ON s.user_id = u.id ORDER BY s.user_id")
        all_nodes_data = cursor.fetchall()
        conn.close()
        
        all_nodes_list = []
        for username, followers, client_name, user_id in all_nodes_data:
            stats_key = f"{user_id}_{username}"
            stats = account_stats.get(stats_key, {})
            all_nodes_list.append({
                "username": username, 
                "client": client_name, 
                "followers": followers, 
                "sent": stats.get("sent", 0), 
                "failed": stats.get("failed", 0), 
                "gcs": stats.get("gcs_count", 0)
            })
        
        uptime_seconds = int(time.time() - app_start_time)
        return render_template_string(ALL_NODES_HTML, all_nodes=all_nodes_list, uptime_seconds=uptime_seconds)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/get_logs")
def get_logs():
    return jsonify({"logs": live_logs})

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "="*50)
    print("🔥 SNAPPY PANEL STARTED 🔥")
    print("="*50)
    print(f"👑 Owner: {OWNER_USERNAME}")
    print(f"🔑 Password: {OWNER_PASSWORD}")
    print(f"🌐 URL: http://localhost:{port}")
    print("="*50 + "\n")
    
    app.run(host="0.0.0.0", port=port, debug=False)
