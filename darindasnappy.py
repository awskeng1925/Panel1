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

# ================= DATABASE (FIXED) =================
def init_db():
    try:
        conn = sqlite3.connect('panel_users.db')
        cursor = conn.cursor()
        
        # Users table
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
        
        # Sessions table
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
        
        # Force create owner if not exists
        cursor.execute("SELECT * FROM users WHERE username = ?", (OWNER_USERNAME,))
        if not cursor.fetchone():
            hashed_pw = generate_password_hash(OWNER_PASSWORD)
            cursor.execute("INSERT INTO users (username, password, is_owner, created_at) VALUES (?, ?, ?, ?)",
                          (OWNER_USERNAME, hashed_pw, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            print("✅ Owner created!")
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully!")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

# Try to init DB
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
            print(f"✅ [{username}] Session loaded from file!")
            return cl
        except Exception as e:
            print(f"⚠️ [{username}] Saved session failed: {e}")
    
    try:
        sid = session_id.strip()
        if '%3A' in sid:
            sid = urllib.parse.unquote(sid)
        
        try:
            cl.login_by_sessionid(sid)
            print(f"✅ [{username}] Logged in with session ID!")
            with open(session_file, 'wb') as f:
                f.write(cl.get_settings())
            return cl
        except Exception as e1:
            print(f"⚠️ Session ID login failed: {e1}")
            try:
                cl.set_user_agent("Instagram 269.0.0.18.96 Android")
                cl.login_by_sessionid(sid)
                with open(session_file, 'wb') as f:
                    f.write(cl.get_settings())
                return cl
            except Exception as e2:
                print(f"⚠️ Cookie login failed: {e2}")
                raise Exception(f"Session login failed: {e2}")
    except Exception as e:
        print(f"❌ [{username}] Login failed: {e}")
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
                    print(f"🔄 [{username}] Session refreshed!")
                    return cl
                except Exception as e:
                    print(f"❌ [{username}] Refresh failed: {e}")
                    return None
            else:
                print(f"❌ [{username}] No saved session file")
                return None
    except Exception as e:
        print(f"⚠️ Session refresh error: {e}")
        return None

# ================= SPAM LISTS =================
def repeat_text(text, times=5):
    return "\n\n".join([text] * times)

SIREN_LIST_1 = [
    repeat_text("𝗔𝗡𝗧𝗘𝗥 𝗠𝗔𝗡𝗧𝗘𝗥 𝗦𝗛𝗘𝗧𝗔𝗡𝗜 𝗞𝗛𝗢𝗣𝗗𝗔 < {target}> 𝗧𝗘𝗥𝗜 𝗠𝗔𝗔 𝗞𝗔 𝗕𝗛𝗢𝗦𝗗𝗔 🪼⋆｡𖦹°🫧⋆.ೃ࿔*:･"),
    repeat_text("𝗠𝗔𝗜 𝗣𝗜𝗧𝗔 𝗛𝗨𝗡 𝗣𝗔𝗡𝗜 < {target}> 𝗞𝗜 𝗠𝗔𝗔 𝗥𝗔𝗡𝗗𝗜𝗢𝗡 𝗞𝗜 𝗥𝗔𝗡𝗜 ˖°𓇼🌊⋆🐚🫧"),
    repeat_text("< {target} > 𝗢𝗬𝗘 𝗧𝗘𝗥𝗜 𝗥𝗔𝗡𝗗𝗜 𝗠𝗔𝗔 𝗞𝗢 𝗛𝗔𝗞𝗟𝗔 𝗞𝗘 𝗖𝗛𝗢𝗗𝗨 ‧₊˚🖇️✩ ₊˚🎧⊹♡"),
    repeat_text("𝗔𝗖𝗛𝗔 𝗦𝗨𝗡 𝗧𝗢 < {target}> 𝗧𝗘𝗥𝗜 𝗠𝗔𝗔 𝗞𝗢 𝗕𝗛𝗔𝗚𝗔 𝗕𝗛𝗔𝗚𝗔 𝗖𝗛𝗢𝗗𝗨 ‧₊˚ ☁️⋅♡🪐༘⋆"),
    repeat_text("< {target} > 𝗧𝗘𝗥𝗜 𝗕𝗛𝗘𝗡 𝗞𝗜 𝗧𝗔𝗡𝗚 𝗨𝗧𝗛𝗔 𝗞𝗘 𝗜𝗗𝗛𝗘𝗥 𝗨𝗗𝗛𝗘𝗥 𝗖𝗛𝗢𝗗𝗨𝗡𝗚𝗔 ༘⋆🌷🫧💭₊˚ෆ"),
    repeat_text("< {target} > -----𝗞𝗨𝗧𝗧𝗜𝗬𝗔 𝗕𝗔𝗡𝗔 𝗞𝗜 𝗖𝗢𝗗𝗨 𝗧𝗘𝗥𝗜 𝗠𝗔𝗔 𝗞𝗢 🧉❀🐚🐉︎ ࿔*:･ﾟ☾")
]

SIREN_LIST_2 = [
    repeat_text("< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??"),
    repeat_text("< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??"),
    repeat_text("< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??"),
    repeat_text("< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??"),
    repeat_text("< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??"),
    repeat_text("< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??")
]

SIREN_LIST_3 = [
    repeat_text("( {target} )-----------𝑷𝑹 𝑻𝑬𝑹𝑰 𝑴𝑨𝑨 𝑪𝑯𝑼𝑫𝑵𝑬 𝑲𝑰𝑼 𝑳𝑨𝑮 𝑮𝑨𝑰 <🙄🔥>"),
    repeat_text("( {target} )-----------𝑷𝑹 𝑻𝑬𝑹𝑰 𝑴𝑨𝑨 𝑪𝑯𝑼𝑫𝑵𝑬 𝑲𝑰𝑼 𝑳𝑨𝑮 𝑮𝑨𝑰 <🙄🔥>"),
    repeat_text("( {target} )-----------𝑷𝑹 𝑻𝑬𝑹𝑰 𝑴𝑨𝑨 𝑪𝑯𝑼𝑫𝑵𝑬 𝑲𝑰𝑼 𝑳𝑨𝑮 𝑮𝑨𝑰 <🙄🔥>"),
    repeat_text("( {target} )-----------𝑷𝑹 𝑻𝑬𝑹𝑰 𝑴𝑨𝑨 𝑪𝑯𝑼𝑫𝑵𝑬 𝑲𝑰𝑼 𝑳𝑨𝑮 𝑮𝑨𝑰 <🙄🔥>")
]

SIREN_LIST_4 = [
    repeat_text("𝑨𝒏𝒕𝒔 𝑰𝒏 𝒀𝒐𝒖𝒓 𝑨𝒔𝒔🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･⏔⏔⏔ ꒰ {target} ꒱ ⏔⏔⏔"),
]

# ================= TELEGRAM ALERT =================
def send_telegram_alert(message):
    try:
        if ADMIN_TG_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
            url = f"https://api.telegram.org/bot{ADMIN_TG_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": ADMIN_TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
            requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram alert error: {e}")

def log_event(message, level="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {"time": timestamp, "msg": message, "level": level}
    live_logs.insert(0, log_entry)
    if len(live_logs) > 300:
        live_logs.pop()

# ================= RESOLVE THREAD ID =================
def resolve_thread_id(cl, raw_input):
    raw_input = raw_input.strip()
    match = re.search(r'(\d{15,})', raw_input)
    if match:
        return match.group(1)
    return raw_input

# ================= NAME LOCK WORKER =================
def run_name_lock_worker(session_id, raw_gc_input, desired_name, module_key, uname):
    log_event(f"[{uname}] NC Lock active. Enforcing group name: '{desired_name}'", "success")
    while lock_name_threads.get(module_key, False):
        try:
            cl = login_with_session(session_id, uname)
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
                            log_event(f"[{uname}] NC Lock: Name reverted to '{desired_name}'!", "warning")
                    
                    time.sleep(10)
                except Exception as inner_ex:
                    log_event(f"[{uname}] NC Lock error: {str(inner_ex)[:50]}", "error")
                    time.sleep(5)
        except Exception as e:
            log_event(f"[{uname}] NC Lock Reconnecting...", "error")
            time.sleep(10)

# ================= SPAM WORKER =================
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
    max_reconnect_attempts = 3

    while active_spam_threads.get(module_key, False):
        if node_quarantine_status.get(user_stats_key, False):
            time.sleep(5)
            continue

        try:
            if cl is None:
                cl = login_with_session(session_id, uname)
                if cl is None:
                    reconnect_attempts += 1
                    if reconnect_attempts > max_reconnect_attempts:
                        log_event(f"[{uname}] Failed to connect after {max_reconnect_attempts} attempts", "error")
                        break
                    log_event(f"[{uname}] Retrying connection... ({reconnect_attempts}/{max_reconnect_attempts})", "warning")
                    time.sleep(10)
                    continue
                reconnect_attempts = 0
            
            try:
                cl.get_user_id(cl.username)
            except:
                log_event(f"[{uname}] Session expired, reconnecting...", "warning")
                cl = None
                continue
            
            log_event(f"[{uname}] Authenticated & Ready", "success")
            
            try:
                threads = cl.direct_threads(amount=99999)
                all_gc_ids = []
                for t in threads:
                    t_id = getattr(t, 'id', None) or getattr(t, 'pk', None)
                    if t_id:
                        all_gc_ids.append(str(t_id))
                        
                with open(f"link_{uname}.txt", "w", encoding="utf-8") as f:
                    for t in threads:
                        t_id = getattr(t, 'id', None) or getattr(t, 'pk', None)
                        f.write(f"ID: {t_id} | Title: {getattr(t, 'title', 'No Title')}\n")
                
                if target_scope == "single":
                    resolved_gc = resolve_thread_id(cl, target_gc_input)
                    target_threads = [resolved_gc] if resolved_gc else all_gc_ids
                    account_stats[user_stats_key]["gcs_count"] = 1
                else:
                    target_threads = all_gc_ids
                    account_stats[user_stats_key]["gcs_count"] = len(all_gc_ids)

            except Exception as e:
                log_event(f"[{uname}] Failed to fetch threads: {str(e)[:50]}", "error")
                time.sleep(10)
                continue

            consecutive_errors = 0
            while active_spam_threads.get(module_key, False):
                if node_quarantine_status.get(user_stats_key, False):
                    break

                try:
                    if not target_threads:
                        log_event(f"[{uname}] No GCs detected. Refreshing...", "warning")
                        time.sleep(3)
                        break
                    
                    current_target = dynamic_targets.get(user_stats_key, initial_target)
                    campaign_info[user_stats_key]["target"] = current_target
                    account_stats[user_stats_key]["target"] = current_target

                    for thread_id in target_threads:
                        if not active_spam_threads.get(module_key, False) or node_quarantine_status.get(user_stats_key, False):
                            break
                        
                        raw_text = next(message_cycle)
                        message = raw_text.replace("{target}", current_target)
                        
                        try:
                            cl.direct_send(message, thread_ids=[thread_id])
                            account_stats[user_stats_key]["sent"] += 1
                            consecutive_errors = 0
                            log_event(f"[{uname}] ✅ Sent to {current_target} | GC: {str(thread_id)[:8]}...", "success")
                            
                            update_user_stats(user_id, 1)
                            
                            base_wait = max(float(custom_delay), 2.0)
                            jitter_sleep = base_wait + random.uniform(0.8, 3.5)
                            time.sleep(jitter_sleep)

                        except Exception as ex:
                            account_stats[user_stats_key]["failed"] += 1
                            consecutive_errors += 1
                            err_msg = str(ex)
                            
                            if "block" in err_msg.lower() or "limit" in err_msg.lower() or "item_ack" in err_msg.lower():
                                log_event(f"[{uname}] ⚠️ SPAM DETECTED! Quarantine 60s", "error")
                                
                                node_quarantine_status[user_stats_key] = True
                                def release_quarantine(u):
                                    time.sleep(60)
                                    node_quarantine_status[u] = False
                                    log_event(f"[{uname}] ✅ Quarantine lifted!", "success")
                                
                                q_thread = threading.Thread(target=release_quarantine, args=(user_stats_key,))
                                q_thread.daemon = True
                                q_thread.start()
                                break
                            elif "login" in err_msg.lower() or "auth" in err_msg.lower():
                                log_event(f"[{uname}] Session invalid, reconnecting...", "error")
                                cl = None
                                break
                            else:
                                log_event(f"[{uname}] Error: {err_msg[:35]}", "error")
                            
                            if consecutive_errors > 4:
                                log_event(f"[{uname}] Cooling node for 15s...", "warning")
                                time.sleep(15)
                                consecutive_errors = 0
                    
                    time.sleep(2)
                except Exception as inner_e:
                    log_event(f"[{uname}] Glitch: {str(inner_e)[:30]}", "warning")
                    time.sleep(3)
        except Exception as e:
            log_event(f"[{uname}] ⚠️ Worker error: {str(e)[:50]}", "error")
            cl = None
            time.sleep(10)
    
    if user_stats_key in campaign_info:
        campaign_info[user_stats_key]["active"] = False

def update_user_stats(user_id, count):
    try:
        conn = sqlite3.connect('panel_users.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET total_spam_sent = total_spam_sent + ? WHERE id = ?", (count, user_id))
        conn.commit()
        conn.close()
    except:
        pass

# ================= HTML TEMPLATES (MINIFIED) =================
LOGIN_HTML = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Login</title>
<style>
body{background:#0b0f19;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
.login-card{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:30px;width:360px}
h1{text-align:center;font-size:18px}
input{width:100%;padding:10px;background:#0d1117;border:1px solid #1f2937;color:#fff;border-radius:6px;margin-bottom:12px}
.btn{width:100%;padding:10px;background:#3b82f6;border:none;color:#fff;border-radius:6px;cursor:pointer}
.error{background:rgba(239,68,68,0.1);border:1px solid #ef4444;color:#ef4444;padding:10px;border-radius:6px;margin-bottom:12px}
</style></head>
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
</body></html>
"""

LAYOUT_TEMPLATE = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>SNAPPY PANEL</title>
<style>
:root{--bg-base:#0b0f19;--panel-bg:#111827;--border-color:#1f2937;--accent-primary:#3b82f6;--accent-success:#10b981;--accent-warning:#f59e0b;--accent-danger:#ef4444;--text-main:#f9fafb;--text-muted:#9ca3af}
*{box-sizing:border-box}body{background:var(--bg-base);color:var(--text-main);font-family:sans-serif;margin:0;padding:20px}
.container{max-width:1200px;margin:0 auto}
.header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border-color);padding-bottom:15px;margin-bottom:20px}
.header h1{font-size:16px;margin:0}
.user-info{display:flex;align-items:center;gap:15px;font-size:12px;color:var(--text-muted)}
.role{background:var(--accent-primary);color:#fff;padding:2px 10px;border-radius:12px;font-size:10px}
.role.owner{background:var(--accent-warning);color:#000}
.nav-tabs{display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap}
.nav-tabs a{background:var(--panel-bg);border:1px solid var(--border-color);color:var(--text-muted);padding:8px 16px;border-radius:6px;text-decoration:none;font-size:12px}
.nav-tabs a.active{background:var(--accent-primary);color:#fff}
.nav-tabs a.logout{background:var(--accent-danger);color:#fff}
.card{background:var(--panel-bg);border:1px solid var(--border-color);border-radius:10px;padding:20px;margin-bottom:20px}
.card-title{font-size:13px;font-weight:600;border-bottom:1px solid var(--border-color);padding-bottom:10px;margin-bottom:15px}
.form-group{margin-bottom:14px}
label{display:block;font-size:11px;color:var(--text-muted);margin-bottom:6px}
input,select,textarea{width:100%;padding:10px;background:#0d1117;border:1px solid var(--border-color);color:var(--text-main);border-radius:6px;font-size:13px}
.btn{width:100%;padding:10px;background:var(--accent-primary);border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;margin-top:5px}
.btn-danger{background:var(--accent-danger)}
.btn-success{background:var(--accent-success);color:#000}
.terminal{background:#0d1117;border:1px solid var(--border-color);border-radius:8px;height:460px;overflow-y:auto;padding:14px;font-size:12px;font-family:monospace;display:flex;flex-direction:column-reverse}
.log-line{margin-bottom:6px}.success{color:var(--accent-success)}.error{color:var(--accent-danger)}.warning{color:var(--accent-warning)}.info{color:var(--accent-primary)}
.grid-2{display:grid;grid-template-columns:420px 1fr;gap:20px}
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:15px}
.stat-box{background:#0d1117;border:1px solid var(--border-color);border-radius:6px;padding:10px;text-align:center}
.stat-box .number{font-size:20px;font-weight:700}
.stat-box .label{font-size:10px;color:var(--text-muted)}
.checkbox-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;background:#0d1117;padding:10px;border-radius:6px;border:1px solid var(--border-color)}
.checkbox-item{display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer}
@media(max-width:900px){.grid-2{grid-template-columns:1fr}.stats-grid{grid-template-columns:repeat(2,1fr)}}
</style></head>
<body>
<div class="container">
<div class="header"><h1>SNAPPY PANEL</h1>
<div class="user-info">
<span>{{ session.get('username') }}</span>
<span class="role{% if session.get('is_owner') %} owner{% endif %}">{% if session.get('is_owner') %}👑 OWNER{% else %}👤 CLIENT{% endif %}</span>
<span>Uptime: <span id="uptime">0h 0m 0s</span></span>
</div></div>
<div class="nav-tabs">
<a href="/" class="{% if active_tab=='dashboard' %}active{% endif %}">Dashboard</a>
<a href="/nodes" class="{% if active_tab=='nodes' %}active{% endif %}">My Nodes</a>
{% if session.get('is_owner') %}
<a href="/clients" class="{% if active_tab=='clients' %}active{% endif %}">👥 Clients</a>
<a href="/all_nodes" class="{% if active_tab=='all_nodes' %}active{% endif %}">🌐 All Nodes</a>
{% endif %}
<a href="/logout" class="logout">Logout</a>
</div>
{% if message %}<div style="padding:12px;margin-bottom:18px;border-radius:6px;font-size:12px;background:rgba(16,185,129,0.1);border:1px solid var(--accent-success);color:var(--accent-success)">{{ message }}</div>{% endif %}
{% block content %}{% endblock %}
</div>
<script>
let startTime=Math.floor(Date.now()/1000)-{{ uptime_seconds }};
setInterval(function(){let now=Math.floor(Date.now()/1000);let diff=now-startTime;let h=Math.floor(diff/3600);let m=Math.floor((diff%3600)/60);let s=diff%60;document.getElementById('uptime').innerText=h+"h "+m+"m "+s+"s"},1000);
</script>
</body></html>
"""

DASHBOARD_HTML = """
{% extends "layout" %}
{% block content %}
<div class="grid-2"><div>
<div class="stats-grid">
<div class="stat-box"><div class="number">{{ stats.nodes }}</div><div class="label">My Nodes</div></div>
<div class="stat-box"><div class="number">{{ stats.sent }}</div><div class="label">Sent</div></div>
<div class="stat-box"><div class="number">{{ stats.failed }}</div><div class="label">Failed</div></div>
<div class="stat-box"><div class="number">{{ stats.active }}</div><div class="label">Active</div></div>
</div>

<div class="card"><div class="card-title">Add Node</div>
<form method="POST"><input type="hidden" name="action_type" value="add_session">
<div class="form-group"><label>Session ID</label><input type="text" name="new_session_id" placeholder="Paste sessionid..." required></div>
<button type="submit" class="btn">Authorize</button></form></div>

<div class="card"><div class="card-title">⚡ Target Switcher</div>
<form method="POST"><input type="hidden" name="action_type" value="update_live_target">
<div class="form-group"><label>New Target</label><input type="text" name="new_target_name" placeholder="New target..." required></div>
<button type="submit" class="btn btn-success">Update</button></form></div>

<div class="card"><div class="card-title">🚀 Launch Campaign</div>
<form method="POST"><input type="hidden" name="action_type" value="start_spam">
<div class="form-group"><label>Select Nodes</label>
<div class="checkbox-grid">{% if all_nodes %}{% for node in all_nodes %}<label class="checkbox-item"><input type="checkbox" name="selected_nodes" value="{{ node }}" checked> @{{ node }}</label>{% endfor %}{% else %}<span style="font-size:11px;color:var(--text-muted)">No nodes registered.</span>{% endif %}</div></div>
<div class="form-group"><label>Target</label><input type="text" name="target_name" placeholder="Target Name" required></div>
<div class="form-group"><label>Scope</label><select name="target_scope"><option value="all">All Groups</option><option value="single">Single Group</option></select></div>
<div class="form-group"><label>Single Group ID</label><input type="text" name="single_gc_input" placeholder="Thread ID..."></div>
<div class="form-group"><label>Delay (Seconds)</label><input type="number" step="any" name="custom_delay" value="3.5" min="2.0" required></div>
<div class="form-group"><label>Template</label><select name="spam_option"><option value="opt1">Template 1</option><option value="opt2">Template 2</option><option value="opt3">Template 3</option><option value="opt4">Template 4</option><option value="opt_custom">Custom</option></select></div>
<div class="form-group"><label>Custom Lines (Use {target})</label><textarea name="custom_text" placeholder="Line 1 for {target}"></textarea></div>
<button type="submit" class="btn">Launch</button></form>
<form method="POST" style="margin-top:10px"><input type="hidden" name="action_type" value="stop_spam"><button type="submit" class="btn btn-danger">Stop All</button></form></div>
</div><div>
<div class="card"><div class="card-title">Live Logs</div><div id="terminal" class="terminal"><div class="log-line info">[System] Ready.</div></div></div>
</div></div>
<script>
function updateTelemetry(){fetch('/get_logs').then(res=>res.json()).then(data=>{let terminal=document.getElementById('terminal');let html='';data.logs.forEach(log=>{let cls='info';if(log.level==='success')cls='success';if(log.level==='error')cls='error';if(log.level==='warning')cls='warning';html+=`<div class="log-line ${cls}">[${log.time}] ${log.msg}</div>`;});terminal.innerHTML=html;});}
setInterval(updateTelemetry,1500);
</script>
{% endblock %}
"""

NODES_HTML = """
{% extends "layout" %}
{% block content %}
<div class="card"><div class="card-title">My Nodes</div>
<div style="font-size:12px;color:var(--text-muted);margin-bottom:15px">Total: <b style="color:var(--accent-success)">{{ nodes|length }}</b></div>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:15px">{% for node in nodes %}
<div style="background:#0d1117;border:1px solid var(--border-color);border-radius:8px;padding:15px">
<div style="display:flex;justify-content:space-between;border-bottom:1px solid var(--border-color);padding-bottom:8px;margin-bottom:10px">
<span style="font-weight:600">@{{ node.username }}</span>
<span style="background:rgba(16,185,129,0.1);border:1px solid var(--accent-success);color:var(--accent-success);padding:2px 6px;font-size:10px;border-radius:4px">{% if node.active %}ACTIVE{% else %}IDLE{% endif %}</span></div>
<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Followers: {{ node.followers }} | Following: {{ node.following }}</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;text-align:center;background:var(--bg-base);padding:8px;border-radius:6px;border:1px solid var(--border-color);margin-bottom:12px">
<div><span style="font-size:9px;color:var(--text-muted)">SENT</span><br><strong style="color:var(--accent-success)">{{ node.sent }}</strong></div>
<div><span style="font-size:9px;color:var(--text-muted)">FAILED</span><br><strong style="color:var(--accent-danger)">{{ node.failed }}</strong></div>
<div><span style="font-size:9px;color:var(--text-muted)">GCS</span><br><strong style="color:var(--accent-primary)">{{ node.gcs }}</strong></div></div>
<form method="POST"><input type="hidden" name="action_type" value="remove_node"><input type="hidden" name="node_username" value="{{ node.username }}"><button type="submit" class="btn btn-danger" style="padding:6px;font-size:11px">Remove</button></form>
</div>{% endfor %}</div></div>
{% endblock %}
"""

CLIENTS_HTML = """
{% extends "layout" %}
{% block content %}
<div class="card"><div class="card-title">👥 Client Management</div>
<div class="card" style="border-color:var(--accent-success)"><div class="card-title" style="color:var(--accent-success)">➕ Create Client</div>
<form method="POST"><input type="hidden" name="action_type" value="create_client">
<div class="form-group"><label>Username</label><input type="text" name="client_username" placeholder="client123" required></div>
<div class="form-group"><label>Password</label><input type="text" name="client_password" placeholder="password123" required></div>
<button type="submit" class="btn btn-success">Create</button></form></div>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:15px;margin-top:20px">{% for client in clients %}
<div style="background:#0d1117;border:1px solid var(--border-color);border-radius:8px;padding:15px">
<div style="display:flex;justify-content:space-between;border-bottom:1px solid var(--border-color);padding-bottom:8px;margin-bottom:10px">
<span style="font-weight:600">@{{ client.username }}</span><span style="font-size:10px;color:var(--text-muted)">ID: {{ client.id }}</span></div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;text-align:center;margin-bottom:10px">
<div><span style="font-size:9px;color:var(--text-muted)">Nodes</span><br><strong>{{ client.nodes }}</strong></div>
<div><span style="font-size:9px;color:var(--text-muted)">Sent</span><br><strong style="color:var(--accent-success)">{{ client.total_sent }}</strong></div>
<div><span style="font-size:9px;color:var(--text-muted)">Created</span><br><strong style="font-size:10px">{{ client.created_at[:10] }}</strong></div></div>
<form method="POST"><input type="hidden" name="action_type" value="delete_client"><input type="hidden" name="client_id" value="{{ client.id }}"><button type="submit" class="btn btn-danger" style="padding:6px;font-size:11px">Delete</button></form>
</div>{% endfor %}</div></div>
{% endblock %}
"""

ALL_NODES_HTML = """
{% extends "layout" %}
{% block content %}
<div class="card"><div class="card-title">🌐 All Nodes</div>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:15px">{% for node in all_nodes %}
<div style="background:#0d1117;border:1px solid var(--border-color);border-radius:8px;padding:15px">
<div style="display:flex;justify-content:space-between;border-bottom:1px solid var(--border-color);padding-bottom:8px;margin-bottom:10px">
<span style="font-weight:600">@{{ node.username }}</span><span style="font-size:10px;color:var(--text-muted)">Client: {{ node.client }}</span></div>
<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Followers: {{ node.followers }}</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;text-align:center;background:var(--bg-base);padding:8px;border-radius:6px;border:1px solid var(--border-color)">
<div><span style="font-size:9px;color:var(--text-muted)">SENT</span><br><strong style="color:var(--accent-success)">{{ node.sent }}</strong></div>
<div><span style="font-size:9px;color:var(--text-muted)">FAILED</span><br><strong style="color:var(--accent-danger)">{{ node.failed }}</strong></div>
<div><span style="font-size:9px;color:var(--text-muted)">GCS</span><br><strong style="color:var(--accent-primary)">{{ node.gcs }}</strong></div></div>
</div>{% endfor %}</div></div>
{% endblock %}
"""

# ================= ROUTES =================
@app.route("/", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    
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
            return render_template_string(LOGIN_HTML, error=f"Database error: {str(e)[:50]}")
    
    return render_template_string(LOGIN_HTML)

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    is_owner = session.get("is_owner", False)
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
                    log_event(f"User {session['username']} added node @{username}", "success")
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
            
            elif action_type == "create_client" and is_owner:
                client_user = request.form.get("client_username", "").strip()
                client_pass = request.form.get("client_password", "").strip()
                if client_user and client_pass:
                    hashed = generate_password_hash(client_pass)
                    cursor.execute("INSERT INTO users (username, password, is_owner, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                                 (client_user, hashed, 0, session['username'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    message = f"Client @{client_user} created!"
            
            elif action_type == "delete_client" and is_owner:
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
        return render_template_string(DASHBOARD_HTML, active_tab="dashboard", message=message, uptime_seconds=uptime_seconds, all_nodes=user_nodes, stats={"nodes": total_nodes, "sent": total_sent, "failed": total_failed, "active": active_count})
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/nodes")
def nodes():
    if "user_id" not in session:
        return redirect(url_for("login"))
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
            nodes_list.append({"username": username, "full_name": full_name, "followers": followers, "following": following, "sent": stats.get("sent", 0), "failed": stats.get("failed", 0), "gcs": stats.get("gcs_count", 0), "active": active_spam_threads.get(f"spam_{user_id}_{username}", False)})
        
        uptime_seconds = int(time.time() - app_start_time)
        return render_template_string(NODES_HTML, active_tab="nodes", nodes=nodes_list, uptime_seconds=uptime_seconds)
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
            clients_list.append({"id": id, "username": username, "created_at": created_at, "nodes": total_nodes or 0, "total_sent": total_spam_sent or 0})
        
        uptime_seconds = int(time.time() - app_start_time)
        return render_template_string(CLIENTS_HTML, active_tab="clients", clients=clients_list, uptime_seconds=uptime_seconds)
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
            all_nodes_list.append({"username": username, "client": client_name, "followers": followers, "sent": stats.get("sent", 0), "failed": stats.get("failed", 0), "gcs": stats.get("gcs_count", 0)})
        
        uptime_seconds = int(time.time() - app_start_time)
        return render_template_string(ALL_NODES_HTML, active_tab="all_nodes", all_nodes=all_nodes_list, uptime_seconds=uptime_seconds)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

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
