import os
import time
import random
import threading
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)

# ================= CONFIG =================
SESSION_ID = "39581976351%3AgTCNTb8gCkU2cK%3A27%3AAYiHU6zgI6b9mOJkTOvLm_QBYNGl6Br0wrIrWDE-zg"
THREAD_ID = "18091118003240787"
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "5"))
NAME_CHANGE_INTERVAL = 15
# ==========================================

# ===== LONG SPAM MESSAGES =====
LONG_MESSAGES = [
    """
🔥🔥🔥 PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🔥🔥🔥
💀💀💀 PRVR/DHRUV/OSKE TATTE TMKC ON TOP 💀💀💀
⚡⚡⚡ PRVR/DHRUV/OSKE TATTE TMKC ON TOP ⚡⚡⚡
🩸🩸🩸 PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🩸🩸🩸
🖤🖤🖤 PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🖤🖤🖤
""",
    """
╔══════════════════════════════════════════════════════════════╗
║  🔥 PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🔥  ║
╠══════════════════════════════════════════════════════════════╣
║  💀 PRVR/DHRUV/OSKE TATTE TMKC ON TOP 💀  ║
╠══════════════════════════════════════════════════════════════╣
║  ⚡ PRVR/DHRUV/OSKE TATTE TMKC ON TOP ⚡  ║
╠══════════════════════════════════════════════════════════════╣
║  🩸 PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🩸  ║
╚══════════════════════════════════════════════════════════════╝
""",
    """
PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🔥
PRVR/DHRUV/OSKE TATTE TMKC ON TOP 💀
PRVR/DHRUV/OSKE TATTE TMKC ON TOP ⚡
PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🩸
PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🖤
PRVR/DHRUV/OSKE TATTE TMKC ON TOP ☠️
PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🕷️
""",
    """
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
░░ PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🔥  ░░
░░ PRVR/DHRUV/OSKE TATTE TMKC ON TOP 💀  ░░
░░ PRVR/DHRUV/OSKE TATTE TMKC ON TOP ⚡  ░░
░░ PRVR/DHRUV/OSKE TATTE TMKC ON TOP 🩸  ░░
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
""",
]

# ===== GROUP NAMES =====
GROUP_NAMES = [
    "PRVR/DHRUV/OSKE TATTE 🔥",
    "PRVR/DHRUV/OSKE TATTE 💀",
    "PRVR/DHRUV/OSKE TATTE ⚡",
    "PRVR/DHRUV/OSKE TATTE 🩸",
    "PRVR/DHRUV/OSKE TATTE 🖤",
    "PRVR/DHRUV/OSKE TATTE ☠️",
    "PRVR/DHRUV/OSKE TATTE 🕷️",
    "PRVR/DHRUV/OSKE TATTE 😈",
    "PRVR/DHRUV/OSKE TATTE 💥",
    "PRVR/DHRUV/OSKE TATTE 👑",
]

running = False
total_sent = 0
name_index = 0

# ===== WORKER =====
class SpamWorker:
    def __init__(self, worker_id):
        self.worker_id = worker_id
        self.driver = None
        self.running = True
        self.count = 0
        self.msg_index = 0
        
    def setup_driver(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(30)
        return True
    
    def login(self):
        try:
            self.setup_driver()
            
            self.driver.get("https://www.instagram.com/")
            time.sleep(2)
            
            self.driver.add_cookie({
                "name": "sessionid",
                "value": SESSION_ID,
                "domain": ".instagram.com",
                "path": "/",
                "secure": True,
                "httpOnly": True
            })
            
            self.driver.refresh()
            time.sleep(2)
            
            url = f"https://www.instagram.com/direct/t/{THREAD_ID}/"
            self.driver.get(url)
            time.sleep(3)
            
            if "accounts/login" in self.driver.current_url:
                return False
            
            print(f"[{self.worker_id}] ✅ Ready")
            return True
            
        except Exception as e:
            print(f"[{self.worker_id}] ❌ Error: {e}")
            return False
    
    def change_group_name(self, new_name):
        try:
            name_element = self.driver.find_element(By.CSS_SELECTOR, 'div[role="button"] span')
            name_element.click()
            time.sleep(1)
            
            edit_btn = self.driver.find_element(By.XPATH, "//span[text()='Edit group']")
            edit_btn.click()
            time.sleep(1)
            
            name_input = self.driver.find_element(By.CSS_SELECTOR, 'input[placeholder*="Group name"]')
            name_input.clear()
            name_input.send_keys(new_name)
            time.sleep(0.5)
            
            save_btn = self.driver.find_element(By.XPATH, "//div[text()='Save']")
            save_btn.click()
            time.sleep(1)
            
            close_btn = self.driver.find_element(By.XPATH, "//div[text()='Close']")
            close_btn.click()
            time.sleep(1)
            
            print(f"[{self.worker_id}] 📛 {new_name}")
            return True
            
        except Exception as e:
            return False
    
    def send_message(self, msg):
        try:
            result = self.driver.execute_script("""
                var msg = arguments[0];
                var inputs = document.querySelectorAll('div[contenteditable="true"]');
                if (inputs.length > 0) {
                    var input = inputs[0];
                    input.focus();
                    input.innerText = msg;
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                    input.dispatchEvent(new KeyboardEvent('keydown', {
                        key: 'Enter',
                        code: 'Enter',
                        bubbles: true
                    }));
                    return true;
                }
                return false;
            """, msg)
            return result
        except:
            return False
    
    def run(self):
        global total_sent, name_index
        
        if not self.login():
            return
        
        while self.running:
            try:
                msg = LONG_MESSAGES[self.msg_index % len(LONG_MESSAGES)]
                self.msg_index += 1
                
                success = self.send_message(msg)
                
                if success:
                    self.count += 1
                    total_sent += 1
                    
                    if self.count % NAME_CHANGE_INTERVAL == 0:
                        new_name = GROUP_NAMES[name_index % len(GROUP_NAMES)]
                        name_index += 1
                        self.change_group_name(new_name)
                    
                    if self.count % 50 == 0:
                        print(f"[{self.worker_id}] ✅ {self.count} sent")
                
                time.sleep(0.001)
                
            except Exception as e:
                time.sleep(0.5)
        
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass

# ===== API =====
@app.route('/')
def home():
    return jsonify({
        "status": "🚀 Running",
        "total_sent": total_sent,
        "running": running
    })

@app.route('/start', methods=['POST'])
def start_spam():
    global running
    
    if running:
        return jsonify({"status": "already running"})
    
    running = True
    
    for i in range(MAX_WORKERS):
        worker = SpamWorker(i+1)
        t = threading.Thread(target=worker.run)
        t.daemon = True
        t.start()
    
    return jsonify({
        "status": "started",
        "workers": MAX_WORKERS
    })

@app.route('/stop', methods=['POST'])
def stop_spam():
    global running
    running = False
    return jsonify({
        "status": "stopped",
        "total_sent": total_sent
    })

@app.route('/status')
def status():
    return jsonify({
        "running": running,
        "total_sent": total_sent,
        "name_changes": name_index
    })

# ===== MAIN =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
