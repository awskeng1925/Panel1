# ======================== ig_api_spam_panel.py ========================
# Instagram Multi-GC Spam Panel - PURE API VERSION (No Selenium/Playwright)

import os
import sys
import json
import time
import random
import threading
import re
import urllib.parse
import uuid
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "INSTA_API_SPAM_PANEL_2026"

# ================= CONFIGURATION =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MESSAGES_FILE = os.path.join(BASE_DIR, "messages.txt")
RENAMES_FILE = os.path.join(BASE_DIR, "renames.txt")
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.json")

# ================= IN-MEMORY STORE =================
accounts = {}
running_tasks = {}
stats = {}
terminal_logs = []

# ================= HELPER FUNCTIONS =================
def log_message(uid, msg, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {
        "time": timestamp,
        "uid": str(uid),
        "level": level,
        "msg": msg
    }
    terminal_logs.append(entry)
    if len(terminal_logs) > 200:
        terminal_logs.pop(0)
    print(f"[{timestamp}] [{uid}] [{level}] {msg}")

def load_messages():
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip()]
    return ["🔥 UI SNAPPY ON TOP!", "💥 SYSTEM ONLINE", "🚀 WAR MODE ACTIVE"]

def load_renames():
    if os.path.exists(RENAMES_FILE):
        with open(RENAMES_FILE, "r", encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip()]
    return ["LOCKED BY UI SNAPPY", "GOD CLAN", "MASTER CONTROL"]

def save_accounts():
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2)

def load_accounts():
    global accounts
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            accounts = json.load(f)

def parse_session_cookie(session_input):
    """Parse session ID from various formats"""
    raw = session_input.strip()
    
    cookies = {}
    if ";" in raw:
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k.strip()] = v.strip()
    
    sid = cookies.get("sessionid", raw)
    if "%3A" in sid or "%3a" in sid:
        sid = urllib.parse.unquote(sid)
    if sid.lower().startswith("sessionid="):
        sid = sid[10:].strip()
    
    csrf = cookies.get("csrftoken", "")
    if not csrf:
        match = re.search(r'csrftoken=([^;]+)', raw)
        if match:
            csrf = match.group(1).strip()
    
    user_id = cookies.get("ds_user_id", "")
    if not user_id:
        match = re.search(r'ds_user_id=([^;]+)', raw)
        if match:
            user_id = match.group(1).strip()
    
    return {
        "sessionid": sid,
        "csrftoken": csrf,
        "ds_user_id": user_id
    }

# ================= INSTAGRAM API HELPERS =================
def instagram_api_request(session_cookies, endpoint, method="GET", data=None, retries=3):
    """Make authenticated Instagram API request"""
    sid = session_cookies.get("sessionid", "")
    csrf = session_cookies.get("csrftoken", "")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-IG-App-ID": "936619743392459",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "*/*",
        "Referer": "https://www.instagram.com/direct/inbox/",
        "Origin": "https://www.instagram.com",
        "X-CSRFToken": csrf
    }
    
    cookies = {
        "sessionid": sid,
        "csrftoken": csrf
    }
    
    if session_cookies.get("ds_user_id"):
        cookies["ds_user_id"] = session_cookies["ds_user_id"]
    
    url = f"https://www.instagram.com/api/v1/{endpoint}"
    
    for attempt in range(retries):
        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, cookies=cookies, timeout=15)
            else:
                resp = requests.post(url, headers=headers, cookies=cookies, json=data, timeout=15)
            
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                time.sleep(5)
                continue
            else:
                return resp
        except Exception:
            time.sleep(2)
            continue
    
    return None

def get_group_threads(session_cookies, limit=50):
    """Fetch group chats from Instagram API"""
    threads = []
    cursor = None
    
    for page in range(3):
        try:
            endpoint = f"direct_v2/inbox/?visual_message_return_type=unseen&limit=20"
            if cursor:
                endpoint += f"&cursor={cursor}"
            
            resp = instagram_api_request(session_cookies, endpoint)
            if not resp or resp.status_code != 200:
                break
            
            data = resp.json()
            inbox = data.get("inbox", {})
            thread_list = inbox.get("threads", [])
            
            for thread in thread_list:
                if thread.get("is_group", False):
                    thread_id = thread.get("thread_v2_id") or thread.get("thread_id")
                    if thread_id:
                        threads.append({
                            "id": thread_id,
                            "title": thread.get("thread_title", f"Group {thread_id}"),
                            "users": thread.get("users", []),
                            "link": f"https://www.instagram.com/direct/t/{thread_id}/"
                        })
            
            cursor = inbox.get("oldest_cursor")
            if not cursor or len(threads) >= limit:
                break
        except Exception as e:
            log_message("API", f"Error fetching groups: {e}", "ERROR")
            break
    
    return threads[:limit]

def send_message_to_thread(session_cookies, thread_id, message):
    """Send message to a thread"""
    try:
        data = {
            "thread_ids": [thread_id],
            "text": message
        }
        resp = instagram_api_request(session_cookies, "direct_v2/threads/broadcast/text/", "POST", data)
        return resp and resp.status_code == 200
    except Exception:
        return False

def update_thread_title(session_cookies, thread_id, title):
    """Update group chat title"""
    try:
        data = {"title": title}
        resp = instagram_api_request(session_cookies, f"direct_v2/threads/{thread_id}/update_title/", "POST", data)
        return resp and resp.status_code == 200
    except Exception:
        return False

def get_user_id_from_username(session_cookies, username):
    """Get user ID from username"""
    try:
        resp = instagram_api_request(session_cookies, f"users/web_profile_info/?username={username}")
        if resp and resp.status_code == 200:
            data = resp.json()
            user = data.get("data", {}).get("user")
            if user:
                return user.get("id")
        return None
    except Exception:
        return None

def create_group_thread(session_cookies, user_ids, title=""):
    """Create a new group chat"""
    try:
        data = {
            "recipient_users": user_ids,
            "thread_title": title or "UI SNAPPY GROUP"
        }
        resp = instagram_api_request(session_cookies, "direct_v2/create_group_thread/", "POST", data)
        if resp and resp.status_code == 200:
            result = resp.json()
            thread_id = result.get("thread_id") or result.get("thread_v2_id")
            if thread_id:
                return {
                    "success": True,
                    "thread_id": thread_id,
                    "link": f"https://www.instagram.com/direct/t/{thread_id}/"
                }
        return {"success": False, "error": "Failed to create group"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_user_followers(session_cookies, user_id, limit=100):
    """Get followers of a user"""
    try:
        resp = instagram_api_request(session_cookies, f"friendships/{user_id}/followers/?count={limit}")
        if resp and resp.status_code == 200:
            data = resp.json()
            return data.get("users", [])
        return []
    except Exception:
        return []

def get_user_following(session_cookies, user_id, limit=100):
    """Get following of a user"""
    try:
        resp = instagram_api_request(session_cookies, f"friendships/{user_id}/following/?count={limit}")
        if resp and resp.status_code == 200:
            data = resp.json()
            return data.get("users", [])
        return []
    except Exception:
        return []

# ================= SPAM ENGINE (PURE API) =================
def spam_engine(uid, account_data):
    """Main spam engine using Instagram API"""
    log_message(uid, "🚀 Starting API spam engine...", "SUCCESS")
    
    session_cookies = parse_session_cookie(account_data.get("sessionid", ""))
    sid = session_cookies.get("sessionid", "")
    
    if not sid:
        log_message(uid, "❌ Invalid session ID!", "ERROR")
        running_tasks[uid] = False
        return
    
    # Get configuration
    messages = account_data.get("messages", load_messages())
    renames = account_data.get("renames", load_renames())
    gc_links = account_data.get("gc_links", [])
    target_usernames = account_data.get("target_usernames", [])
    
    delay = float(account_data.get("delay", 3))
    cycle_delay = int(account_data.get("cycle_delay", 10))
    max_groups = int(account_data.get("max_groups", 10))
    use_long_format = account_data.get("use_long_format", True)
    space_lines = int(account_data.get("space_lines", 35))
    header_text = account_data.get("header_text", "👑 SPAM BY SNAPPY 👑")
    footer_text = account_data.get("footer_text", "👑 SCRIPT BY UI SNAPPY 👑")
    auto_create = account_data.get("auto_create", False)
    scrape_mode = account_data.get("scrape_mode", "followers")  # followers, following, custom
    
    blank_block = "\n".join(["⠀" for _ in range(space_lines)])
    
    # Auto-create groups from followers/following
    if auto_create and not gc_links:
        log_message(uid, "🔄 Auto-create mode: Fetching users...", "INFO")
        
        # Get user ID from session
        user_id = session_cookies.get("ds_user_id", "")
        if not user_id:
            log_message(uid, "⚠️ Could not get user ID", "WARN")
        else:
            # Fetch users based on mode
            users = []
            if scrape_mode == "followers":
                users = get_user_followers(session_cookies, user_id, 50)
                log_message(uid, f"📋 Found {len(users)} followers", "INFO")
            elif scrape_mode == "following":
                users = get_user_following(session_cookies, user_id, 50)
                log_message(uid, f"📋 Found {len(users)} following", "INFO")
            elif target_usernames:
                users = [{"username": u} for u in target_usernames]
            
            # Create groups from users
            if users:
                created = []
                for i in range(0, len(users), 5):
                    batch = users[i:i+5]
                    if len(batch) < 2:
                        continue
                    
                    user_ids = []
                    for u in batch:
                        uid_val = u.get("id") or u.get("pk")
                        if not uid_val:
                            username = u.get("username")
                            if username:
                                uid_val = get_user_id_from_username(session_cookies, username)
                        if uid_val:
                            user_ids.append(str(uid_val))
                    
                    if len(user_ids) >= 2:
                        result = create_group_thread(session_cookies, user_ids, f"UI SNAPPY {i//5 + 1}")
                        if result.get("success"):
                            created.append(result["link"])
                            log_message(uid, f"✅ Created group {i//5 + 1}: {result['link']}", "SUCCESS")
                        time.sleep(2)
                
                gc_links = created
                log_message(uid, f"✅ Created {len(gc_links)} groups", "SUCCESS")
    
    # Use existing links or fallback
    if not gc_links:
        # Try to get existing groups
        try:
            groups = get_group_threads(session_cookies, max_groups)
            gc_links = [g["link"] for g in groups]
            log_message(uid, f"✅ Found {len(gc_links)} existing groups", "SUCCESS")
        except Exception as e:
            log_message(uid, f"⚠️ Could not fetch groups: {e}", "WARN")
    
    if not gc_links:
        log_message(uid, "⚠️ No group links found! Add manually or enable auto-create.", "WARN")
        running_tasks[uid] = False
        return
    
    # Limit groups
    gc_links = gc_links[:max_groups]
    log_message(uid, f"📋 Processing {len(gc_links)} groups", "INFO")
    
    msg_idx = 0
    rename_idx = 0
    cycle_count = 0
    
    while running_tasks.get(uid, False):
        cycle_count += 1
        log_message(uid, f"🔄 Cycle #{cycle_count} started", "INFO")
        
        for idx, gc_url in enumerate(gc_links):
            if not running_tasks.get(uid, False):
                break
            
            # Extract thread ID from URL
            thread_id = None
            match = re.search(r'/direct/t/([^/?]+)', gc_url)
            if match:
                thread_id = match.group(1)
            else:
                # Try to get from link
                thread_id = gc_url.split("/")[-2] if gc_url.endswith("/") else gc_url.split("/")[-1]
            
            if not thread_id:
                log_message(uid, f"⚠️ Invalid group link: {gc_url}", "WARN")
                continue
            
            log_message(uid, f"👉 [{idx+1}/{len(gc_links)}] Processing group: {gc_url}", "INFO")
            
            # --- Send 2 text messages ---
            for m in range(2):
                if not running_tasks.get(uid, False):
                    break
                
                current_msg = messages[msg_idx % len(messages)]
                msg_idx += 1
                
                if use_long_format:
                    payload = f"{header_text}\n{blank_block}\n{current_msg}\n{blank_block}\n{footer_text}"
                else:
                    payload = current_msg
                
                try:
                    success = send_message_to_thread(session_cookies, thread_id, payload)
                    if success:
                        stats[uid]["sent"] = stats[uid].get("sent", 0) + 1
                        log_message(uid, f"📨 Sent message {m+1}/2 to group {idx+1}", "SUCCESS")
                    else:
                        stats[uid]["failed"] = stats[uid].get("failed", 0) + 1
                        log_message(uid, f"❌ Failed to send message {m+1}/2", "ERROR")
                    time.sleep(delay)
                except Exception as e:
                    log_message(uid, f"❌ Send error: {e}", "ERROR")
                    stats[uid]["failed"] = stats[uid].get("failed", 0) + 1
            
            # --- Rename group ---
            if renames and running_tasks.get(uid, False):
                try:
                    new_name = renames[rename_idx % len(renames)]
                    rename_idx += 1
                    
                    success = update_thread_title(session_cookies, thread_id, new_name)
                    if success:
                        stats[uid]["renamed"] = stats[uid].get("renamed", 0) + 1
                        log_message(uid, f"🏷️ Renamed group to: {new_name}", "SUCCESS")
                    else:
                        log_message(uid, f"⚠️ Failed to rename group", "WARN")
                except Exception as e:
                    log_message(uid, f"⚠️ Rename error: {e}", "WARN")
            
            time.sleep(delay)
        
        if not running_tasks.get(uid, False):
            break
        
        log_message(uid, f"✨ Cycle #{cycle_count} completed. Waiting {cycle_delay}s...", "INFO")
        for _ in range(cycle_delay):
            if not running_tasks.get(uid, False):
                break
            time.sleep(1)
    
    running_tasks[uid] = False
    log_message(uid, "⏹️ Spam engine stopped", "INFO")

# ================= ROUTES =================

@app.route("/")
def index():
    return redirect("/panel")

@app.route("/panel")
def panel():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/status")
def api_status():
    return jsonify({
        "accounts": accounts,
        "stats": stats,
        "running": running_tasks,
        "logs": terminal_logs[-50:]
    })

@app.route("/api/add_account", methods=["POST"])
def api_add_account():
    data = request.json or {}
    uid = data.get("uid") or str(uuid.uuid4())[:8]
    
    sessionid = data.get("sessionid", "").strip()
    if not sessionid:
        return jsonify({"success": False, "error": "Session ID is required"}), 400
    
    account_data = {
        "uid": uid,
        "sessionid": sessionid,
        "messages": data.get("messages", load_messages()),
        "renames": data.get("renames", load_renames()),
        "gc_links": data.get("gc_links", []),
        "target_usernames": data.get("target_usernames", []),
        "delay": float(data.get("delay", 3)),
        "cycle_delay": int(data.get("cycle_delay", 10)),
        "max_groups": int(data.get("max_groups", 10)),
        "use_long_format": data.get("use_long_format", True),
        "space_lines": int(data.get("space_lines", 35)),
        "header_text": data.get("header_text", "👑 SPAM BY SNAPPY 👑"),
        "footer_text": data.get("footer_text", "👑 SCRIPT BY UI SNAPPY 👑"),
        "auto_create": data.get("auto_create", False),
        "scrape_mode": data.get("scrape_mode", "followers")
    }
    
    accounts[uid] = account_data
    stats[uid] = {"sent": 0, "failed": 0, "renamed": 0}
    running_tasks[uid] = False
    save_accounts()
    
    return jsonify({"success": True, "uid": uid})

@app.route("/api/start", methods=["POST"])
def api_start():
    uid = request.json.get("uid")
    if not uid or uid not in accounts:
        return jsonify({"success": False, "error": "Account not found"}), 404
    
    if running_tasks.get(uid, False):
        return jsonify({"success": False, "error": "Already running"}), 400
    
    running_tasks[uid] = True
    threading.Thread(target=spam_engine, args=(uid, accounts[uid]), daemon=True).start()
    
    return jsonify({"success": True, "message": "Started"})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    uid = request.json.get("uid")
    running_tasks[uid] = False
    return jsonify({"success": True, "message": "Stopping..."})

@app.route("/api/delete", methods=["POST"])
def api_delete():
    uid = request.json.get("uid")
    running_tasks[uid] = False
    accounts.pop(uid, None)
    stats.pop(uid, None)
    save_accounts()
    return jsonify({"success": True})

@app.route("/api/scrape_groups", methods=["POST"])
def api_scrape_groups():
    sessionid = request.json.get("sessionid", "").strip()
    if not sessionid:
        return jsonify({"success": False, "error": "Session ID required"}), 400
    
    session_cookies = parse_session_cookie(sessionid)
    groups = get_group_threads(session_cookies, 50)
    
    return jsonify({"success": True, "groups": groups})

@app.route("/api/create_group", methods=["POST"])
def api_create_group():
    sessionid = request.json.get("sessionid", "").strip()
    usernames = request.json.get("usernames", [])
    title = request.json.get("title", "UI SNAPPY GROUP")
    
    if not sessionid or not usernames:
        return jsonify({"success": False, "error": "Session ID and usernames required"}), 400
    
    session_cookies = parse_session_cookie(sessionid)
    
    user_ids = []
    for username in usernames:
        uid_val = get_user_id_from_username(session_cookies, username.strip())
        if uid_val:
            user_ids.append(str(uid_val))
    
    if len(user_ids) < 2:
        return jsonify({"success": False, "error": "Need at least 2 valid users"}), 400
    
    result = create_group_thread(session_cookies, user_ids, title)
    return jsonify(result)

@app.route("/api/auto_create_groups", methods=["POST"])
def api_auto_create_groups():
    sessionid = request.json.get("sessionid", "").strip()
    mode = request.json.get("mode", "followers")
    count = int(request.json.get("count", 50))
    group_size = int(request.json.get("group_size", 5))
    
    if not sessionid:
        return jsonify({"success": False, "error": "Session ID required"}), 400
    
    session_cookies = parse_session_cookie(sessionid)
    user_id = session_cookies.get("ds_user_id", "")
    
    if not user_id:
        return jsonify({"success": False, "error": "Could not get user ID"}), 400
    
    users = []
    if mode == "followers":
        users = get_user_followers(session_cookies, user_id, count)
    elif mode == "following":
        users = get_user_following(session_cookies, user_id, count)
    else:
        return jsonify({"success": False, "error": "Invalid mode"}), 400
    
    if not users:
        return jsonify({"success": False, "error": "No users found"}), 400
    
    created_groups = []
    for i in range(0, len(users), group_size):
        batch = users[i:i+group_size]
        if len(batch) < 2:
            continue
        
        user_ids = []
        for u in batch:
            uid_val = u.get("id") or u.get("pk")
            if uid_val:
                user_ids.append(str(uid_val))
        
        if len(user_ids) >= 2:
            result = create_group_thread(session_cookies, user_ids, f"UI SNAPPY {i//group_size + 1}")
            if result.get("success"):
                created_groups.append(result["link"])
            time.sleep(2)
    
    return jsonify({"success": True, "created": created_groups, "count": len(created_groups)})

@app.route("/api/save_messages", methods=["POST"])
def api_save_messages():
    messages = request.json.get("messages", [])
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(messages))
    return jsonify({"success": True})

@app.route("/api/save_renames", methods=["POST"])
def api_save_renames():
    renames = request.json.get("renames", [])
    with open(RENAMES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(renames))
    return jsonify({"success": True})

@app.route("/api/get_config")
def api_get_config():
    return jsonify({
        "messages": load_messages(),
        "renames": load_renames()
    })

# ================= HTML TEMPLATE =================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 Instagram Multi-GC Spam Panel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0a0a1a; color: #e0e0e0; font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #ff3b8d; text-align: center; margin-bottom: 20px; font-size: 28px; }
        h1 span { color: #00ffcc; }
        .subtitle { text-align: center; color: #888; margin-bottom: 20px; font-size: 14px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { background: #141428; border-radius: 12px; padding: 20px; border: 1px solid #2a2a4a; }
        .card h3 { color: #ff3b8d; margin-bottom: 15px; font-size: 16px; }
        .card h3 .icon { margin-right: 8px; }
        input, textarea, select { width: 100%; padding: 10px; background: #1a1a35; border: 1px solid #2a2a5a; border-radius: 8px; color: #fff; font-size: 14px; margin-bottom: 10px; }
        textarea { resize: vertical; min-height: 80px; font-family: monospace; }
        select { cursor: pointer; }
        .btn { padding: 10px 20px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.3s; font-size: 14px; }
        .btn-primary { background: #ff3b8d; color: #fff; }
        .btn-primary:hover { background: #e62e7a; }
        .btn-success { background: #00cc88; color: #000; }
        .btn-success:hover { background: #00b377; }
        .btn-danger { background: #ff3355; color: #fff; }
        .btn-danger:hover { background: #e62e4a; }
        .btn-warning { background: #ffaa00; color: #000; }
        .btn-warning:hover { background: #e69900; }
        .btn-secondary { background: #2a2a5a; color: #fff; }
        .btn-secondary:hover { background: #3a3a7a; }
        .btn-group { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
        .status { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; }
        .status-running { background: #00cc88; color: #000; }
        .status-stopped { background: #555; color: #fff; }
        .log-area { background: #0a0a10; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; border: 1px solid #1a1a3a; }
        .log-entry { padding: 2px 0; border-bottom: 1px solid #111; }
        .log-time { color: #666; }
        .log-info { color: #4fc3f7; }
        .log-success { color: #00cc88; }
        .log-error { color: #ff3355; }
        .log-warn { color: #ffaa00; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 10px; }
        .stat-box { background: #1a1a35; padding: 12px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 24px; font-weight: bold; color: #ff3b8d; }
        .stat-label { font-size: 12px; color: #888; }
        .account-item { background: #1a1a35; padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid #555; }
        .account-item.running { border-left-color: #00cc88; }
        .account-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
        .account-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 5px; }
        .btn-sm { padding: 5px 12px; font-size: 12px; }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
        @media (max-width: 600px) { .account-header { flex-direction: column; align-items: flex-start; gap: 8px; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔥 INSTAGRAM <span>MULTI-GC</span> SPAM PANEL</h1>
        <p class="subtitle">⚡ Pure API Version | No Selenium/Playwright Required</p>
        
        <div class="grid">
            <!-- Account Setup -->
            <div class="card">
                <h3><span class="icon">🔐</span> Account Setup</h3>
                <input id="uid" placeholder="Account ID (auto-generated if empty)">
                <input id="sessionid" placeholder="Instagram Session ID / Cookie" value="sessionid=...">
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                    <input id="delay" type="number" value="3" placeholder="Delay (sec)">
                    <input id="cycle_delay" type="number" value="10" placeholder="Cycle delay (sec)">
                </div>
                <input id="max_groups" type="number" value="10" placeholder="Max groups per cycle">
                
                <label style="color:#888;font-size:13px;display:flex;align-items:center;gap:8px;">
                    <input id="use_long_format" type="checkbox" checked> Use Long Format
                </label>
                <label style="color:#888;font-size:13px;display:flex;align-items:center;gap:8px;">
                    <input id="auto_create" type="checkbox"> Auto-Create Groups
                </label>
                
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
                    <select id="scrape_mode">
                        <option value="followers">From Followers</option>
                        <option value="following">From Following</option>
                        <option value="custom">Custom Users</option>
                    </select>
                    <input id="target_usernames" placeholder="Target usernames (comma separated)" style="margin:0;">
                </div>
                
                <textarea id="gc_links" placeholder="Group links (one per line)"></textarea>
                <div class="btn-group">
                    <button class="btn btn-primary" onclick="addAccount()">➕ Add Account</button>
                    <button class="btn btn-secondary" onclick="scrapeGroups()">🔍 Scrape Groups</button>
                    <button class="btn btn-warning" onclick="autoCreateGroups()">🤖 Auto Create</button>
                </div>
            </div>
            
            <!-- Messages & Renames -->
            <div class="card">
                <h3><span class="icon">💬</span> Messages & Renames</h3>
                <textarea id="messages" rows="4" placeholder="Spam messages (one per line)"></textarea>
                <textarea id="renames" rows="3" placeholder="Group rename titles (one per line)"></textarea>
                <div class="btn-group">
                    <button class="btn btn-warning" onclick="saveMessages()">💾 Save Messages</button>
                    <button class="btn btn-warning" onclick="saveRenames()">💾 Save Renames</button>
                    <button class="btn btn-secondary" onclick="loadConfig()">📂 Load Config</button>
                </div>
            </div>
        </div>
        
        <!-- Accounts List -->
        <div class="card" style="margin-top:20px;">
            <h3><span class="icon">📋</span> Active Accounts</h3>
            <div id="accountsList"></div>
        </div>
        
        <!-- Stats & Logs -->
        <div class="grid" style="margin-top:20px;">
            <div class="card">
                <h3><span class="icon">📊</span> Statistics</h3>
                <div class="stats-grid">
                    <div class="stat-box"><div class="stat-value" id="stat_sent">0</div><div class="stat-label">Messages Sent</div></div>
                    <div class="stat-box"><div class="stat-value" id="stat_failed">0</div><div class="stat-label">Failed</div></div>
                    <div class="stat-box"><div class="stat-value" id="stat_renamed">0</div><div class="stat-label">Renamed</div></div>
                    <div class="stat-box"><div class="stat-value" id="stat_running">0</div><div class="stat-label">Running</div></div>
                </div>
            </div>
            <div class="card">
                <h3><span class="icon">📝</span> Terminal Logs</h3>
                <div class="log-area" id="logArea"></div>
                <button class="btn btn-secondary" onclick="clearLogs()" style="margin-top:10px;">🗑️ Clear Logs</button>
            </div>
        </div>
    </div>

    <script>
        let accounts = {};
        
        async function addAccount() {
            const data = {
                uid: document.getElementById('uid').value || undefined,
                sessionid: document.getElementById('sessionid').value.trim(),
                delay: parseFloat(document.getElementById('delay').value) || 3,
                cycle_delay: parseInt(document.getElementById('cycle_delay').value) || 10,
                max_groups: parseInt(document.getElementById('max_groups').value) || 10,
                use_long_format: document.getElementById('use_long_format').checked,
                auto_create: document.getElementById('auto_create').checked,
                scrape_mode: document.getElementById('scrape_mode').value,
                target_usernames: document.getElementById('target_usernames').value.split(',').map(x => x.trim()).filter(x => x),
                messages: document.getElementById('messages').value.split('\\n').filter(x => x.trim()),
                renames: document.getElementById('renames').value.split('\\n').filter(x => x.trim()),
                gc_links: document.getElementById('gc_links').value.split('\\n').filter(x => x.trim().startsWith('http'))
            };
            
            if (!data.sessionid) {
                alert('❌ Session ID is required!');
                return;
            }
            
            try {
                const res = await fetch('/api/add_account', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const result = await res.json();
                if (result.success) {
                    alert('✅ Account added! UID: ' + result.uid);
                    loadAccounts();
                } else {
                    alert('❌ Error: ' + result.error);
                }
            } catch(e) {
                alert('❌ Error: ' + e.message);
            }
        }
        
        async function scrapeGroups() {
            const sessionid = document.getElementById('sessionid').value.trim();
            if (!sessionid) {
                alert('❌ Session ID required!');
                return;
            }
            
            try {
                const res = await fetch('/api/scrape_groups', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({sessionid})
                });
                const result = await res.json();
                if (result.success) {
                    const links = result.groups.map(g => g.link).join('\\n');
                    document.getElementById('gc_links').value = links;
                    alert('✅ Found ' + result.groups.length + ' groups!');
                } else {
                    alert('❌ Error: ' + result.error);
                }
            } catch(e) {
                alert('❌ Error: ' + e.message);
            }
        }
        
        async function autoCreateGroups() {
            const sessionid = document.getElementById('sessionid').value.trim();
            if (!sessionid) {
                alert('❌ Session ID required!');
                return;
            }
            
            const mode = document.getElementById('scrape_mode').value;
            const usernames = document.getElementById('target_usernames').value.split(',').map(x => x.trim()).filter(x => x);
            
            let body = {sessionid, mode};
            if (mode === 'custom' && usernames.length) {
                body.usernames = usernames;
            }
            
            try {
                const res = await fetch('/api/auto_create_groups', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body)
                });
                const result = await res.json();
                if (result.success) {
                    const links = result.created.join('\\n');
                    document.getElementById('gc_links').value = links;
                    alert('✅ Created ' + result.count + ' groups!');
                } else {
                    alert('❌ Error: ' + (result.error || 'Unknown error'));
                }
            } catch(e) {
                alert('❌ Error: ' + e.message);
            }
        }
        
        async function saveMessages() {
            const messages = document.getElementById('messages').value.split('\\n').filter(x => x.trim());
            await fetch('/api/save_messages', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({messages})
            });
            alert('✅ Messages saved!');
        }
        
        async function saveRenames() {
            const renames = document.getElementById('renames').value.split('\\n').filter(x => x.trim());
            await fetch('/api/save_renames', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({renames})
            });
            alert('✅ Renames saved!');
        }
        
        async function loadConfig() {
            const res = await fetch('/api/get_config');
            const data = await res.json();
            document.getElementById('messages').value = data.messages.join('\\n');
            document.getElementById('renames').value = data.renames.join('\\n');
        }
        
        async function loadAccounts() {
            const res = await fetch('/api/status');
            const data = await res.json();
            accounts = data.accounts || {};
            
            let html = '';
            for (const [uid, acc] of Object.entries(accounts)) {
                const isRunning = data.running && data.running[uid];
                const stat = data.stats && data.stats[uid] || {sent: 0, failed: 0, renamed: 0};
                html += `
                    <div class="account-item ${isRunning ? 'running' : ''}">
                        <div class="account-header">
                            <div>
                                <strong style="color:#ff3b8d;">${uid}</strong>
                                <span class="status ${isRunning ? 'status-running' : 'status-stopped'}">${isRunning ? '▶ RUNNING' : '⏹ STOPPED'}</span>
                            </div>
                            <div style="color:#888;font-size:13px;">
                                📨 ${stat.sent} | ❌ ${stat.failed} | 🏷️ ${stat.renamed}
                            </div>
                            <div class="account-actions">
                                ${!isRunning ? `<button class="btn btn-success btn-sm" onclick="startBot('${uid}')">▶ Start</button>` : `<button class="btn btn-danger btn-sm" onclick="stopBot('${uid}')">⏹ Stop</button>`}
                                <button class="btn btn-danger btn-sm" onclick="deleteBot('${uid}')">🗑 Delete</button>
                            </div>
                        </div>
                        <div style="font-size:12px;color:#888;margin-top:5px;">
                            Groups: ${(acc.gc_links || []).length} | Delay: ${acc.delay}s | Cycle: ${acc.cycle_delay}s
                        </div>
                    </div>
                `;
            }
            document.getElementById('accountsList').innerHTML = html || '<p style="color:#888;">No accounts added yet.</p>';
            
            // Update stats
            document.getElementById('stat_sent').textContent = Object.values(data.stats || {}).reduce((s, v) => s + (v.sent || 0), 0);
            document.getElementById('stat_failed').textContent = Object.values(data.stats || {}).reduce((s, v) => s + (v.failed || 0), 0);
            document.getElementById('stat_renamed').textContent = Object.values(data.stats || {}).reduce((s, v) => s + (v.renamed || 0), 0);
            document.getElementById('stat_running').textContent = Object.values(data.running || {}).filter(v => v).length;
        }
        
        async function startBot(uid) {
            await fetch('/api/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({uid})
            });
            loadAccounts();
        }
        
        async function stopBot(uid) {
            await fetch('/api/stop', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({uid})
            });
            loadAccounts();
        }
        
        async function deleteBot(uid) {
            if (!confirm('Delete account ' + uid + '?')) return;
            await fetch('/api/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({uid})
            });
            loadAccounts();
        }
        
        function updateLogs() {
            fetch('/api/status')
                .then(res => res.json())
                .then(data => {
                    const logs = data.logs || [];
                    const logArea = document.getElementById('logArea');
                    let html = '';
                    for (const entry of logs.slice(-50)) {
                        const cls = {
                            'INFO': 'log-info',
                            'SUCCESS': 'log-success',
                            'ERROR': 'log-error',
                            'WARN': 'log-warn'
                        }[entry.level] || 'log-info';
                        html += `<div class="log-entry"><span class="log-time">[${entry.time}]</span> <span class="${cls}">[${entry.uid}] ${entry.msg}</span></div>`;
                    }
                    logArea.innerHTML = html;
                    logArea.scrollTop = logArea.scrollHeight;
                });
        }
        
        function clearLogs() {
            document.getElementById('logArea').innerHTML = '';
        }
        
        // Load on page load
        window.onload = function() {
            loadConfig();
            loadAccounts();
            updateLogs();
            setInterval(loadAccounts, 3000);
            setInterval(updateLogs, 2000);
        };
    </script>
</body>
</html>
'''

# ================= RUN SERVER =================
if __name__ == "__main__":
    # Load existing accounts
    load_accounts()
    
    port = int(os.getenv("PORT", 20822))
    print("=" * 60)
    print("🔥 INSTAGRAM MULTI-GC SPAM PANEL (PURE API)")
    print("=" * 60)
    print(f"📱 Panel URL: http://localhost:{port}/panel")
    print(f"📊 Status API: http://localhost:{port}/api/status")
    print("=" * 60)
    print("⚡ No Selenium/Playwright required!")
    print("⚡ Uses Instagram API directly")
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=port, debug=False)
