#  ╭───𓆩🛡️𓆪───╮
#  👨‍💻 𝘿𝙚𝙫: @j4ck_721s  
#  👤 𝙉𝙖𝙢𝙚: ﮼جــاڪ ,.⏳🤎:)
#   📢 𝘾𝙝: @j4ck_721s
import telebot
import subprocess
import os
import zipfile
import shutil
import re
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import logging
from logging import StreamHandler
import threading
import sys
import atexit
import requests
from flask import Flask
from threading import Thread

# Flask Keep-Alive Setup
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Bot is hosted by ﮼جــاڪ ,.⏳🤎:) 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- Configuration ---
TOKEN = '8441747675:AAF6z8TUeVQKaKwICvh-Ts6MgfxmZARG8hA'
OWNER_ID = 5977475208
YOUR_USERNAME = 'j4ck_721s'
UPDATE_CHANNEL = 'https://t.me/j4ck_721s'

# Absolute Paths for Directories
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')
MAIN_BOT_LOG_PATH = os.path.join(IROTECH_DIR, 'main_bot_log.log')

# Create necessary directories
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)

# --- Data Structures ---
bot_scripts = {} 
user_files = {} 
user_pagination_state = {} 
admin_pagination_state = {} 
bot_usernames_cache = {}
current_file_context = {}  # Track current file for each user


# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(MAIN_BOT_LOG_PATH, encoding='utf-8'),
        StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- ReplyKeyboardMarkup Layouts ---
MAIN_MENU_BUTTONS_LAYOUT = [
    ["ℹ️ دەربارە"],
    ["📤 ناردنی فایل", "📂 فایلەکانم"],
    ["⚙️ دانانی چەناڵ", "📢 کەناڵەکەم"]
]
ADMIN_MENU_BUTTONS_LAYOUT = [
    ["ℹ️ دەربارە"],
    ["📤 ناردنی فایل", "📂 فایلەکانم"],
    ["⚙️ دانانی چەناڵ", "📢 کەناڵەکەم"],
    ["👑 پانێڵی گەشەپێدەر"]
]

# --- Database Setup ---
DB_LOCK = threading.Lock()

def init_db():
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # Check if bot_username column exists, if not add it
        c.execute("PRAGMA table_info(user_files)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'bot_username' not in columns:
            logger.info("Adding bot_username column to user_files table...")
            c.execute('ALTER TABLE user_files ADD COLUMN bot_username TEXT')
        
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
                     (user_id INTEGER, file_name TEXT, file_type TEXT, status TEXT, bot_token_id TEXT, bot_username TEXT,
                      PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS purchases
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      purchase_date TEXT,
                      days_count INTEGER,
                      price REAL,
                      expiry_date TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY,
                      added_by INTEGER,
                      added_date TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS bot_settings
                     (setting_key TEXT PRIMARY KEY,
                      setting_value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_channels
                     (user_id INTEGER PRIMARY KEY,
                      channels TEXT)''')
        c.execute('INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)',
                  ('bot_locked', 'false'))
        c.execute('INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)',
                  ('free_mode', 'false'))
        conn.commit()
        conn.close()

def load_data():
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # Get column info to handle missing bot_username column
        c.execute("PRAGMA table_info(user_files)")
        columns = [column[1] for column in c.fetchall()]
        has_username = 'bot_username' in columns
        
        if has_username:
            c.execute('SELECT user_id, file_name, file_type, status, bot_token_id, bot_username FROM user_files')
        else:
            c.execute('SELECT user_id, file_name, file_type, status, bot_token_id FROM user_files')
        
        for row in c.fetchall():
            user_id = row[0]
            file_name = row[1]
            file_type = row[2]
            status = row[3]
            bot_token_id = row[4]
            bot_username = row[5] if has_username and len(row) > 5 else None
            user_files.setdefault(user_id, []).append((file_name, file_type, status, bot_token_id, bot_username))
        conn.close()

def add_user_to_db(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()

def update_user_file_db(user_id, file_name, file_type, status, bot_token_id, bot_username=None):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type, status, bot_token_id, bot_username) VALUES (?, ?, ?, ?, ?, ?)',
                  (user_id, file_name, file_type, status, bot_token_id, bot_username))
        conn.commit()
        conn.close()

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
        conn.commit()
        conn.close()

def get_all_user_files_from_db():
    all_files = []
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        c.execute("PRAGMA table_info(user_files)")
        columns = [column[1] for column in c.fetchall()]
        has_username = 'bot_username' in columns
        
        if has_username:
            c.execute('SELECT user_id, file_name, file_type, status, bot_token_id, bot_username FROM user_files')
        else:
            c.execute('SELECT user_id, file_name, file_type, status, bot_token_id FROM user_files')
        
        for row in c.fetchall():
            all_files.append({
                'user_id': row[0],
                'file_name': row[1],
                'file_type': row[2],
                'status': row[3],
                'bot_token_id': row[4],
                'bot_username': row[5] if has_username and len(row) > 5 else None
            })
        conn.close()
    return all_files

def add_purchase(user_id, days_count, price):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        purchase_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        expiry_date = (datetime.now() + timedelta(days=days_count)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute('INSERT INTO purchases (user_id, purchase_date, days_count, price, expiry_date) VALUES (?, ?, ?, ?, ?)',
                  (user_id, purchase_date, days_count, price, expiry_date))
        conn.commit()
        conn.close()

def get_all_purchases():
    purchases = []
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT id, user_id, purchase_date, days_count, price, expiry_date FROM purchases ORDER BY id DESC')
        for row in c.fetchall():
            purchases.append({
                'id': row[0],
                'user_id': row[1],
                'purchase_date': row[2],
                'days_count': row[3],
                'price': row[4],
                'expiry_date': row[5]
            })
        conn.close()
    return purchases

def get_user_active_subscription(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('SELECT expiry_date FROM purchases WHERE user_id = ? AND expiry_date > ? ORDER BY expiry_date DESC LIMIT 1',
                  (user_id, now))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result is not None

def add_admin(user_id, added_by):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        added_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('INSERT OR REPLACE INTO admins (user_id, added_by, added_date) VALUES (?, ?, ?)',
                  (user_id, added_by, added_date))
        conn.commit()
        conn.close()

def remove_admin(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

def get_all_admins():
    admins = []
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, added_by, added_date FROM admins')
        for row in c.fetchall():
            admins.append({
                'user_id': row[0],
                'added_by': row[1],
                'added_date': row[2]
            })
        conn.close()
    return admins

def get_bot_setting(key):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT setting_value FROM bot_settings WHERE setting_key = ?', (key,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

def set_bot_setting(key, value):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)',
                  (key, value))
        conn.commit()
        conn.close()

def is_bot_locked():
    return get_bot_setting('bot_locked') == 'true'

def is_free_mode():
    return get_bot_setting('free_mode') == 'true'

def count_user_hosted_bots(user_id):
    files = user_files.get(user_id, [])
    return len(files)

def save_user_channels(user_id, channels):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO user_channels (user_id, channels) VALUES (?, ?)',
                  (user_id, channels))
        conn.commit()
        conn.close()

def get_user_channels(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT channels FROM user_channels WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

def get_bot_username_from_token(token):
    if token in bot_usernames_cache:
        return bot_usernames_cache[token]
    
    try:
        temp_bot = telebot.TeleBot(token)
        me = temp_bot.get_me()
        username = f"@{me.username}" if me.username else "N/A"
        bot_usernames_cache[token] = username
        return username
    except Exception as e:
        logger.error(f"Error getting bot username: {e}")
        return "N/A"

def get_bot_start_count(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    script_info = bot_scripts.get(script_key, {})
    return script_info.get('start_count', 0)

def increment_bot_start_count(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    if script_key in bot_scripts:
        bot_scripts[script_key]['start_count'] = bot_scripts[script_key].get('start_count', 0) + 1
    else:
        bot_scripts[script_key] = {'start_count': 1}

def get_bot_uptime(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and 'start_time' in script_info:
        uptime_seconds = int(time.time() - script_info['start_time'])
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        return f"{hours}h {minutes}m {seconds}s"
    return "N/A"

init_db()
load_data()

def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def is_bot_running(script_owner_id, file_name):
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if not script_info or not script_info.get('process'):
        return False
    
    try:
        proc = psutil.Process(script_info['process'].pid)
        is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        if not is_running:
            _cleanup_stale_script_entry(script_key, script_info)
        return is_running
    except psutil.NoSuchProcess:
        _cleanup_stale_script_entry(script_key, script_info)
        return False
    except Exception as e:
        logger.error(f"Error checking process status for {script_key}: {e}", exc_info=True)
        return False

def _cleanup_stale_script_entry(script_key, script_info):
    if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
        try: script_info['log_file'].close()
        except Exception as log_e: logger.error(f"Error closing log file for stale script {script_key}: {log_e}")
    if script_key in bot_scripts: del bot_scripts[script_key]

def kill_process_tree(process_info):
    pid = None
    if 'log_file' in process_info and hasattr(process_info['log_file'], 'close') and not process_info['log_file'].closed:
        try: process_info['log_file'].close()
        except Exception as log_e: logger.error(f"Error closing log file during termination for {process_info.get('script_key', 'N/A')}: {log_e}")

    process = process_info.get('process')
    if not process or not hasattr(process, 'pid'):
        return

    pid = process.pid
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        for child in children:
            try: child.terminate()
            except (psutil.NoSuchProcess, Exception) as e:
                try: child.kill()
                except Exception as e2: logger.error(f"Failed to kill child process {child.pid} forcefully: {e2}")

        try:
            parent.terminate()
            parent.wait(timeout=5)
        except psutil.TimeoutExpired:
            try: parent.kill()
            except Exception as e: logger.error(f"Failed to forcefully kill parent process {pid}: {e}")
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            logger.error(f"Error terminating parent process {pid}: {e}")
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        logger.error(f"Error managing process tree for PID {pid}: {e}", exc_info=True)

def start_script(user_id, file_name):
    user_folder = get_user_folder(user_id)
    script_path = os.path.join(user_folder, file_name)
    
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script file {file_name} not found in user folder.")

    script_key = f"{user_id}_{file_name}"
    if is_bot_running(user_id, file_name):
        raise RuntimeError(f"Script {file_name} is already running.")

    log_filename = f"{script_key}_log.log"
    log_path = os.path.join(user_folder, log_filename)
    
    try:
        log_file = open(log_path, 'w', encoding='utf-8')
        
        process = subprocess.Popen(
            ['python3', script_path],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=user_folder,
            start_new_session=True
        )
        
        if script_key not in bot_scripts:
            bot_scripts[script_key] = {'start_count': 0}
        
        bot_scripts[script_key].update({
            'process': process,
            'log_file': log_file,
            'log_path': log_path,
            'script_key': script_key,
            'user_id': user_id,
            'file_name': file_name,
            'start_time': time.time()
        })
        
        increment_bot_start_count(user_id, file_name)
        
        logger.info(f"Started script: {script_key} (PID: {process.pid})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start script {script_key}: {e}", exc_info=True)
        if 'log_file' in locals() and not log_file.closed:
            log_file.close()
        raise

def stop_script(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    
    if not script_info:
        raise KeyError(f"Script {file_name} is not tracked or not running.")
    
    kill_process_tree(script_info)
    
    start_count = script_info.get('start_count', 0)
    
    if script_key in bot_scripts:
        del bot_scripts[script_key]
    
    bot_scripts[script_key] = {'start_count': start_count}
    
    logger.info(f"Stopped script: {script_key}")
    return True

def send_main_menu(chat_id, user_id):
    if user_id == OWNER_ID or is_admin(user_id):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for row in ADMIN_MENU_BUTTONS_LAYOUT:
            markup.add(*row)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for row in MAIN_MENU_BUTTONS_LAYOUT:
            markup.add(*row)
    bot.send_message(chat_id, "🏠 مینیوی سەرەکی:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id):
        bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.\n\nتکایە دواتر هەوڵبدەوە.")
        return

    add_user_to_db(user_id)
    
    welcome_text = (
        f"✨ <b>بەخێربێیت بۆ بۆتی Hosting!</b> ✨\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 👤 <b>ناو:</b> {message.from_user.first_name}\n"
        f"┃ 🆔 <b>ئایدی:</b> <code>{user_id}</code>\n"
        f"┃ 📢 <b>کەناڵ:</b> @{YOUR_USERNAME}\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"🚀 <b>ئەم بۆتە تایبەتە بە:</b>\n"
        f"   • Host کردنی بۆتەکانت بە خێرایی\n"
        f"   • کۆنترۆڵی تەواو بەسەر بۆتەکانتدا\n"
        f"   • سیستەمی پێشکەوتوو و ئاسان\n\n"
        f"💡 <i>بۆ دەستپێکردن دوگمەیەک هەڵبژێرە...</i>"
    )
    
    send_main_menu(message.chat.id, user_id)
    bot.send_message(message.chat.id, welcome_text, parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text == "ℹ️ دەربارە")
def about_button(message):
    user_id = message.from_user.id
    
    about_text = (
        f"🌟 <b>دەربارەی بۆتی Hosting</b> 🌟\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 🤖 <b>ناوی بۆت:</b> Hosting Bot\n"
        f"┃ 👨‍💻 <b>گەشەپێدەر:</b> @{YOUR_USERNAME}\n"
        f"┃ 📢 <b>کەناڵ:</b> @{YOUR_USERNAME}\n"
        f"┃ 🔖 <b>وەشان:</b> 2.0 Pro\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"✨ <b>تایبەتمەندییەکان:</b>\n"
        f"   ✅ Host کردنی بۆت بە خێرایی\n"
        f"   ✅ کۆنترۆڵی تەواو (Start/Stop/Restart)\n"
        f"   ✅ بینینی لۆگەکان بە ڕاستەوخۆ\n"
        f"   ✅ پشتیوانی لە .py و .zip\n"
        f"   ✅ سیستەمی ئەدمین\n"
        f"   ✅ ئاماری تەواو\n\n"
        f"🔐 <b>ئاسایشی بەرز و کارایی زۆر!</b>\n\n"
        f"💬 بۆ هەر پرسیارێک: @{YOUR_USERNAME}"
    )
    
    bot.send_message(message.chat.id, about_text, parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text == "📢 کەناڵەکەم")
def channel_button(message):
    user_id = message.from_user.id
    
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id):
        bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 کەناڵەکەم", url=UPDATE_CHANNEL))
    bot.send_message(message.chat.id, "لێرە کەناڵەکەمە:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "⚙️ دانانی چەناڵ")
def set_channel_button(message):
    user_id = message.from_user.id
    
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id):
        bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.")
        return
    
    current_channels = get_user_channels(user_id)
    
    msg_text = (
        "⚙️ <b>دانانی چەناڵەکانت</b>\n\n"
        "📝 یوزەرنەیمی چەناڵەکانت بنێرە (بە @ دەست پێبکات)\n"
        "📌 بۆ زیاتر لە یەک چەناڵ، بە کۆما جیابکەوە:\n\n"
        "<code>@channel1,@channel2,@channel3</code>\n\n"
    )
    
    if current_channels:
        msg_text += f"✅ چەناڵەکانی ئێستا:\n<code>{current_channels}</code>"
    else:
        msg_text += "❌ <i>هیچ چەناڵێک دانەنراوە</i>"
    
    msg = bot.send_message(message.chat.id, msg_text, parse_mode='HTML')
    bot.register_next_step_handler(msg, process_set_channels)

def process_set_channels(message):
    user_id = message.from_user.id
    channels = message.text.strip()
    
    if not channels:
        bot.send_message(message.chat.id, "❌ هیچ چەناڵێک نەنووسرا!")
        return
    
    save_user_channels(user_id, channels)
    bot.send_message(
        message.chat.id,
        f"✅ <b>چەناڵەکان بە سەرکەوتوویی دانران!</b>\n\n"
        f"📋 چەناڵەکان:\n<code>{channels}</code>\n\n"
        f"💡 ئێستا ئەم چەناڵانە لە بۆتەکانتدا بەکاربهێنە.",
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda message: message.text == "📤 ناردنی فایل")
def upload_file_button(message):
    user_id = message.from_user.id
    
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id):
        bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.")
        return

    if not is_free_mode():
        expiry = get_user_active_subscription(user_id)
        if not expiry and user_id != OWNER_ID and not is_admin(user_id):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💰 کڕین", callback_data="buy_subscription"))
            markup.add(types.InlineKeyboardButton("📞 پەیوەندی", url=f"https://t.me/{YOUR_USERNAME}"))
            bot.send_message(
                user_id,
                "⚠️ بۆ بەکارهێنانی بۆت پێویستە بەشداریکردن بکەیت.\n\n"
                "تکایە یەکێک لە گرێبەستەکان بکڕە یان پەیوەندی بە گەشەپێدەر بکە.",
                reply_markup=markup
            )
            return
    
    hosted_count = count_user_hosted_bots(user_id)
    if hosted_count >= 1 and user_id != OWNER_ID and not is_admin(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📞 پەیوەندی بە گەشەپێدەر", url=f"https://t.me/{YOUR_USERNAME}"))
        bot.send_message(
            user_id,
            "⚠️ تەنیا دەتوانیت یەک بۆت Host بکەیت.\n\n"
            "بۆ زیادکردنی بۆتی تر، تکایە پەیوەندی بە گەشەپێدەر بکە.",
            reply_markup=markup
        )
        return

    bot.send_message(
        message.chat.id,
        "📤 <b>ناردنی فایل</b>\n\n"
        "📂 تکایە فایلی بۆتەکەت بنێرە\n"
        "📌 فۆرماتی پشتگیریکراو: <code>.py</code> یان <code>.zip</code>\n"
        "📏 قەبارەی زۆرینە: <code>50MB</code>",
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda message: message.text == "📂 فایلەکانم")
def my_files_button(message):
    user_id = message.from_user.id
    
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id):
        bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.")
        return

    list_user_files(message)

@bot.message_handler(func=lambda message: message.text == "👑 پانێڵی گەشەپێدەر")
def admin_panel_button(message):
    user_id = message.from_user.id
    
    if user_id != OWNER_ID and not is_admin(user_id):
        bot.send_message(user_id, "⛔ تۆ ڕێگەپێدراو نیت بۆ بەکارهێنانی ئەم تایبەتمەندییە.")
        return
    
    show_owner_panel(message)

def show_owner_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("💰 لیستی کڕیارەکان", callback_data="owner_purchases_list"),
        types.InlineKeyboardButton("🗂️ فایلەکانی بەکارهێنەران", callback_data="owner_view_all_users")
    )
    
    lock_status = "🔓 کردنەوە" if is_bot_locked() else "🔒 قفڵکردن"
    free_status = "💵 بەپارە" if is_free_mode() else "🆓 بێ بەرامبەر"
    
    markup.add(
        types.InlineKeyboardButton(f"{lock_status} بۆت", callback_data="owner_toggle_lock"),
        types.InlineKeyboardButton(f"{free_status} کردن", callback_data="owner_toggle_free")
    )
    
    if message.from_user.id == OWNER_ID:
        markup.add(
            types.InlineKeyboardButton("➕ زیادکردنی ئەدمین", callback_data="owner_add_admin"),
            types.InlineKeyboardButton("➖ سڕینەوەی ئەدمین", callback_data="owner_remove_admin")
        )
        markup.add(
            types.InlineKeyboardButton("📋 لیستی ئەدمینەکان", callback_data="owner_list_admins")
        )
    
    markup.add(
        types.InlineKeyboardButton("📊 ئاماری بۆت", callback_data="owner_statistics"),
        types.InlineKeyboardButton("📚 فێرکاری", callback_data="owner_tutorial")
    )
    
    panel_text = (
        f"👑 <b>پانێڵی کۆنتڕۆڵی گەشەپێدەر</b>\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 🎯 تکایە یەکێک لە\n"
        f"┃ 🔧 گرێبەستەکان هەڵبژێرە\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛"
    )
    
    bot.send_message(
        message.chat.id,
        panel_text,
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "owner_tutorial")
def show_tutorial(call):
    if call.from_user.id != OWNER_ID and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ ڕێگەپێدراو نیت")
        return
    
    tutorial_text = (
        f"📚 <b>فێرکاری و ڕێنمایی بۆ ئەدمین</b>\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 🎯 <b>چۆنیەتی فرۆشتن:</b>\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"1️⃣ <b>وەرگرتنی پارە:</b>\n"
        f"   • بەکارهێنەر پەیوەندیت پێوە دەکات\n"
        f"   • نرخی گرێبەست دیاری دەکەیت\n"
        f"   • پارە وەردەگریت (PayPal, Crypto...)\n\n"
        f"2️⃣ <b>چالاککردنی گرێبەست:</b>\n"
        f"   • بڕۆ بۆ پانێڵی گەشەپێدەر\n"
        f"   • دوگمەی '🆓 بێ بەرامبەر کردن' دابگرە\n"
        f"   • یان لە database گرێبەست زیاد بکە\n\n"
        f"3️⃣ <b>لێکۆڵینەوەی کڕیارەکان:</b>\n"
        f"   • لیستی کڕیارەکان ببینە\n"
        f"   • بەروار و کاتی گرێبەستەکان بزانە\n"
        f"   • کۆی داهات بزانە\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ ⚙️ <b>بەڕێوەبردنی بۆت:</b>\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"🔒 <b>قفڵکردنی بۆت:</b>\n"
        f"   • هەموو بەکارهێنەران دەوەستێنن\n"
        f"   • تەنیا خاوەن و ئەدمین دەتوانن بەکاری بهێنن\n\n"
        f"🆓 <b>بێ بەرامبەر کردن:</b>\n"
        f"   • هەموو کەس دەتوانێت بەکاری بهێنێت\n"
        f"   • هیچ پارەیەک پێویست ناکات\n\n"
        f"👥 <b>بەڕێوەبردنی ئەدمینەکان:</b>\n"
        f"   • ئەدمین زیاد بکە بە ناردنی ID\n"
        f"   • ئەدمینەکان دەتوانن کۆنترۆڵ بکەن\n"
        f"   • بەڵام ناتوانن ئەدمین زیاد بکەن\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 💡 <b>تێبینیە گرنگەکان:</b>\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"• هەمیشە دڵنیابە لە پارەدان پێش چالاککردن\n"
        f"• لیستی کڕیارەکان پاراستن بکە\n"
        f"• بەکارهێنەرانی گومان لێکراو بلۆک بکە\n"
        f"• ئاماری بۆت بە بەردەوامی سەیربکە\n\n"
        f"📞 بۆ یارمەتی زیاتر: @{YOUR_USERNAME}"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 گەڕانەوە", callback_data="back_to_owner_panel"))
    
    bot.edit_message_text(
        tutorial_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "owner_purchases_list")
def show_purchases_list(call):
    if call.from_user.id != OWNER_ID and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ ڕێگەپێدراو نیت")
        return
    
    purchases = get_all_purchases()
    
    if not purchases:
        bot.edit_message_text(
            "📋 هیچ کڕینێک تۆمار نەکراوە.",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    response = "💰 <b>لیستی کڕیارەکان:</b>\n\n"
    
    for i, purchase in enumerate(purchases[:20], 1):
        user_info = f"<a href='tg://user?id={purchase['user_id']}'>{purchase['user_id']}</a>"
        response += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{i}. 👤 بەکارهێنەر: {user_info}\n"
            f"   📅 بەروار: {purchase['purchase_date']}\n"
            f"   ⏳ ماوە: {purchase['days_count']} ڕۆژ\n"
            f"   💵 نرخ: ${purchase['price']}\n"
            f"   📆 بەسەردەچێت: {purchase['expiry_date']}\n"
        )
    
    if len(purchases) > 20:
        response += f"\n<i>... و {len(purchases) - 20} کڕینی تر</i>"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 گەڕانەوە", callback_data="back_to_owner_panel"))
    
    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "owner_toggle_lock")
def toggle_bot_lock(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "⛔ تەنیا خاوەن دەتوانێت")
        return
    
    current_status = is_bot_locked()
    new_status = 'false' if current_status else 'true'
    set_bot_setting('bot_locked', new_status)
    
    status_text = "🔒 قفڵ کرا" if new_status == 'true' else "🔓 کرایەوە"
    bot.answer_callback_query(call.id, f"✅ بۆت {status_text}")
    
    show_owner_panel(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "owner_toggle_free")
def toggle_free_mode(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "⛔ تەنیا خاوەن دەتوانێت")
        return
    
    current_status = is_free_mode()
    new_status = 'false' if current_status else 'true'
    set_bot_setting('free_mode', new_status)
    
    status_text = "🆓 بێ بەرامبەر" if new_status == 'true' else "💵 بەپارە"
    bot.answer_callback_query(call.id, f"✅ بۆت {status_text} کرا")
    
    show_owner_panel(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "owner_add_admin")
def add_admin_prompt(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "⛔ تەنیا خاوەن دەتوانێت")
        return
    
    msg = bot.send_message(call.message.chat.id, "📝 تکایە ئایدی بەکارهێنەر بنێرە بۆ کردنی بە ئەدمین:")
    bot.register_next_step_handler(msg, process_add_admin)

def process_add_admin(message):
    try:
        new_admin_id = int(message.text.strip())
        
        if new_admin_id == OWNER_ID:
            bot.send_message(message.chat.id, "⚠️ خاوەن لە ڕەسەن ئەدمینە!")
            return
        
        if is_admin(new_admin_id):
            bot.send_message(message.chat.id, "⚠️ ئەم بەکارهێنەرە پێشتر ئەدمینە!")
            return
        
        add_admin(new_admin_id, OWNER_ID)
        bot.send_message(
            message.chat.id,
            f"✅ بەکارهێنەر <code>{new_admin_id}</code> بە سەرکەوتوویی وەک ئەدمین زیاد کرا.",
            parse_mode='HTML'
        )
        
        try:
            bot.send_message(
                new_admin_id,
                "🎉 پیرۆزە! تۆ وەک ئەدمین زیاد کرایت.\n\n"
                "ئێستا دەتوانیت دەستگەیشتن بە پانێڵی ئەدمین هەبێت."
            )
        except:
            pass
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ ئایدی نادروستە! تکایە ژمارەیەک بنێرە.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ هەڵەیەک ڕوویدا: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "owner_remove_admin")
def remove_admin_prompt(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "⛔ تەنیا خاوەن دەتوانێت")
        return
    
    admins = get_all_admins()
    
    if not admins:
        bot.answer_callback_query(call.id, "هیچ ئەدمینێک نییە بۆ سڕینەوە")
        return
    
    msg = bot.send_message(call.message.chat.id, "📝 تکایە ئایدی ئەدمین بنێرە بۆ سڕینەوە:")
    bot.register_next_step_handler(msg, process_remove_admin)

def process_remove_admin(message):
    try:
        admin_id = int(message.text.strip())
        
        if admin_id == OWNER_ID:
            bot.send_message(message.chat.id, "⚠️ ناتوانیت خاوەن بسڕیتەوە!")
            return
        
        if not is_admin(admin_id):
            bot.send_message(message.chat.id, "⚠️ ئەم بەکارهێنەرە ئەدمین نییە!")
            return
        
        remove_admin(admin_id)
        bot.send_message(
            message.chat.id,
            f"✅ ئەدمین <code>{admin_id}</code> بە سەرکەوتوویی سڕایەوە.",
            parse_mode='HTML'
        )
        
        try:
            bot.send_message(
                admin_id,
                "⚠️ ڕۆڵی ئەدمینیت لێسەنرایەوە."
            )
        except:
            pass
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ ئایدی نادروستە! تکایە ژمارەیەک بنێرە.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ هەڵەیەک ڕوویدا: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "owner_list_admins")
def show_admins_list(call):
    if call.from_user.id != OWNER_ID:
        bot.answer_callback_query(call.id, "⛔ تەنیا خاوەن دەتوانێت")
        return
    
    admins = get_all_admins()
    
    response = "👥 <b>لیستی ئەدمینەکان:</b>\n\n"
    response += f"👑 خاوەن: <code>{OWNER_ID}</code>\n\n"
    
    if not admins:
        response += "<i>هیچ ئەدمینێکی تر نییە.</i>"
    else:
        for i, admin in enumerate(admins, 1):
            response += (
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{i}. ئەدمین: <code>{admin['user_id']}</code>\n"
                f"   زیادکرا لەلایەن: <code>{admin['added_by']}</code>\n"
                f"   بەروار: {admin['added_date']}\n"
            )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 گەڕانەوە", callback_data="back_to_owner_panel"))
    
    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "owner_statistics")
def show_statistics(call):
    if call.from_user.id != OWNER_ID and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ ڕێگەپێدراو نیت")
        return
    
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM active_users')
        total_users = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM user_files')
        total_files = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM user_files WHERE status = "approved"')
        active_files = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM purchases')
        total_purchases = c.fetchone()[0]
        
        c.execute('SELECT SUM(price) FROM purchases')
        total_revenue = c.fetchone()[0] or 0
        
        conn.close()
    
    running_bots = len([k for k in bot_scripts.keys() if is_bot_running(*k.split('_', 1))])
    
    bot_status = "🔒 قفڵکراو" if is_bot_locked() else "🔓 کراوەیە"
    mode_status = "🆓 بێ بەرامبەر" if is_free_mode() else "💵 بەپارە"
    
    response = (
        "📊 <b>ئاماری بۆت:</b>\n\n"
        "┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 👥 بەکارهێنەران: <code>{total_users}</code>\n"
        f"┃ 📂 کۆی فایلەکان: <code>{total_files}</code>\n"
        f"┃ ✅ فایلە چالاکەکان: <code>{active_files}</code>\n"
        f"┃ 🟢 بۆتی کارپێکراو: <code>{running_bots}</code>\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 💰 کۆی کڕینەکان: <code>{total_purchases}</code>\n"
        f"┃ 💵 کۆی داهات: <code>${total_revenue:.2f}</code>\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ ⚙️ دۆخی بۆت: {bot_status}\n"
        f"┃ 🎯 شێوازی بەکارهێنان: {mode_status}\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 گەڕانەوە", callback_data="back_to_owner_panel"))
    
    bot.edit_message_text(
        response,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_owner_panel")
def back_to_owner_panel(call):
    if call.from_user.id != OWNER_ID and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ ڕێگەپێدراو نیت")
        return
    
    show_owner_panel(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "buy_subscription")
def show_buy_options(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📅 1 ڕۆژ - $1", callback_data="buy_1_day"),
        types.InlineKeyboardButton("📅 7 ڕۆژ - $5", callback_data="buy_7_days"),
        types.InlineKeyboardButton("📅 30 ڕۆژ - $15", callback_data="buy_30_days"),
        types.InlineKeyboardButton("🔙 گەڕانەوە", callback_data="cancel_buy")
    )
    
    bot.edit_message_text(
        "💰 <b>گرێبەستەکانی کڕین:</b>\n\n"
        "┏━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃ 📅 1 ڕۆژ: $1\n"
        "┃ 📅 7 ڕۆژ: $5\n"
        "┃ 📅 30 ڕۆژ: $15\n"
        "┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "<i>دوای کڕین پەیوەندی بە گەشەپێدەر بکە بۆ چالاککردن.</i>",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def process_buy(call):
    if call.data == "cancel_buy":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return
    
    days_map = {
        "buy_1_day": (1, 1),
        "buy_7_days": (7, 5),
        "buy_30_days": (30, 15)
    }
    
    days, price = days_map.get(call.data, (0, 0))
    
    if days == 0:
        bot.answer_callback_query(call.id, "❌ هەڵە لە گرێبەست")
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📞 پەیوەندی بە گەشەپێدەر", url=f"https://t.me/{YOUR_USERNAME}"))
    
    bot.edit_message_text(
        f"✅ <b>گرێبەستەکەت:</b>\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ ⏳ ماوە: {days} ڕۆژ\n"
        f"┃ 💵 نرخ: ${price}\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"📝 <b>زانیاری بۆ گەشەپێدەر:</b>\n"
        f"• ئایدی تۆ: <code>{call.from_user.id}</code>\n"
        f"• گرێبەست: {days} ڕۆژ\n"
        f"• نرخ: ${price}\n\n"
        f"💡 دوای پارەدان، گەشەپێدەر گرێبەستەکەت چالاک دەکات.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

@bot.message_handler(content_types=['document'])
def handle_file_upload(message):
    user_id = message.from_user.id
    
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id):
        bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.")
        return

    if not is_free_mode():
        expiry = get_user_active_subscription(user_id)
        if not expiry and user_id != OWNER_ID and not is_admin(user_id):
            bot.send_message(user_id, "⚠️ پێویستە گرێبەست بکڕیت بۆ ناردنی فایل.")
            return
    
    hosted_count = count_user_hosted_bots(user_id)
    if hosted_count >= 1 and user_id != OWNER_ID and not is_admin(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📞 پەیوەندی بە گەشەپێدەر", url=f"https://t.me/{YOUR_USERNAME}"))
        bot.send_message(
            user_id,
            "⚠️ تەنیا دەتوانیت یەک بۆت Host بکەیت.",
            reply_markup=markup
        )
        return

    file = message.document
    file_name = file.file_name
    file_size = file.file_size

    if not (file_name.endswith('.py') or file_name.endswith('.zip')):
        bot.send_message(message.chat.id, "❌ فۆرماتی فایل پشتگیری نەکراوە. تەنیا `.py` یان `.zip` قبووڵە.", parse_mode='Markdown')
        return

    max_file_size = 50 * 1024 * 1024
    if file_size > max_file_size:
        bot.send_message(message.chat.id, "❌ قەبارەی فایل گەورە زۆرە (زۆرینە: 50MB).")
        return

    user_folder = get_user_folder(user_id)
    
    progress_msg = bot.send_message(message.chat.id, "⏳ بارکردنی فایل...\n\n▓░░░░░░░░░ 10%")

    try:
        file_info = bot.get_file(file.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        bot.edit_message_text("⏳ بارکردنی فایل...\n\n▓▓▓▓▓░░░░░ 50%", message.chat.id, progress_msg.message_id)
        
        file_path = os.path.join(user_folder, file_name)
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        bot.edit_message_text("⏳ پرۆسێسکردن...\n\n▓▓▓▓▓▓▓▓░░ 80%", message.chat.id, progress_msg.message_id)

        if file_name.endswith('.zip'):
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(user_folder)
                os.remove(file_path)
                
                extracted_files = [f for f in os.listdir(user_folder) if f.endswith('.py')]
                for extracted_file in extracted_files:
                    bot_token_match = extract_bot_token(os.path.join(user_folder, extracted_file))
                    bot_token_id = bot_token_match.split(':')[0] if bot_token_match else None
                    bot_username = get_bot_username_from_token(bot_token_match) if bot_token_match else "N/A"
                    user_files.setdefault(user_id, []).append((extracted_file, 'py', 'approved', bot_token_id, bot_username))
                    update_user_file_db(user_id, extracted_file, 'py', 'approved', bot_token_id, bot_username)
                    
                    # Auto-start the bot
                    try:
                        start_script(user_id, extracted_file)
                    except Exception as e:
                        logger.error(f"Error auto-starting bot {extracted_file}: {e}")
                
                bot.edit_message_text("✅ فایلەکان بە سەرکەوتوویی بارکران و دەستیان پێکرد! 🎉", message.chat.id, progress_msg.message_id)
                            
            except zipfile.BadZipFile:
                bot.edit_message_text("❌ فایلی `.zip` تێکچووە.", message.chat.id, progress_msg.message_id)
                os.remove(file_path)
                return

        else:
            bot_token_match = extract_bot_token(file_path)
            bot_token_id = bot_token_match.split(':')[0] if bot_token_match else None
            bot_username = get_bot_username_from_token(bot_token_match) if bot_token_match else "N/A"
            user_files.setdefault(user_id, []).append((file_name, 'py', 'approved', bot_token_id, bot_username))
            update_user_file_db(user_id, file_name, 'py', 'approved', bot_token_id, bot_username)
            
            # Auto-start the bot
            try:
                start_script(user_id, file_name)
                bot.edit_message_text("✅ فایلەکەت بە سەرکەوتوویی بارکرا و دەستی پێکرد! 🎉", message.chat.id, progress_msg.message_id)
            except Exception as e:
                logger.error(f"Error auto-starting bot {file_name}: {e}")
                bot.edit_message_text("✅ فایلەکەت بارکرا! بەڵام هەڵەیەک ڕوویدا لە دەستپێکردن.", message.chat.id, progress_msg.message_id)

    except Exception as e:
        logger.error(f"Error uploading file for user {user_id}: {e}", exc_info=True)
        bot.edit_message_text(f"❌ هەڵەیەک ڕوویدا: {str(e)}", message.chat.id, progress_msg.message_id)

def extract_bot_token(file_path):
    token_pattern = re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            match = token_pattern.search(content)
            return match.group(0) if match else None
    except Exception as e:
        logger.error(f"Error extracting token from {file_path}: {e}")
        return None

def list_user_files(message):
    user_id = message.from_user.id
    files = user_files.get(user_id, [])
    
    if not files:
        bot.send_message(
            message.chat.id,
            "📂 <b>فایلەکانت</b>\n\n"
            "❌ هیچ فایلێکت نییە.\n\n"
            "💡 فایلێک بنێرە بۆ دەستپێکردن!",
            parse_mode='HTML'
        )
        return
    
    # Send header message
    bot.send_message(
        message.chat.id,
        f"📂 <b>فایلەکانت</b>\n\n"
        f"کۆی فایلەکان: {len(files)}",
        parse_mode='HTML'
    )
    
    # Create keyboard with file buttons
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    
    for file_name, file_type, status, bot_token_id, bot_username in files:
        is_running = is_bot_running(user_id, file_name)
        status_emoji = "🟢" if is_running else "🔴"
        button_text = f"{status_emoji} {file_name}"
        markup.add(types.KeyboardButton(button_text))
    
    # Add back button
    markup.add("🔙 گەڕانەوە بۆ مینیو")
    
    bot.send_message(
        message.chat.id,
        "دوگمەیەک هەڵبژێرە بۆ بینینی زانیاری:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text and (message.text.startswith("🟢 ") or message.text.startswith("🔴 ")))
def handle_file_button(message):
    user_id = message.from_user.id
    file_name = message.text[2:]  # Remove emoji
    
    files = user_files.get(user_id, [])
    file_info = next((f for f in files if f[0] == file_name), None)
    
    if not file_info:
        bot.send_message(message.chat.id, "❌ فایلەکە نەدۆزرایەوە!")
        return
    
    # Store current file context
    current_file_context[user_id] = file_name
    show_bot_control(message.chat.id, user_id, file_info)

def show_bot_control(chat_id, user_id, file_info):
    file_name, file_type, status, bot_token_id, bot_username = file_info
    script_key = f"{user_id}_{file_name}"
    is_running = is_bot_running(user_id, file_name)
    
    status_emoji = "🟢 Running" if is_running else "🔴 Stopped"
    uptime = get_bot_uptime(user_id, file_name)
    start_count = get_bot_start_count(user_id, file_name)
    
    bot_token_short = f"{bot_token_id[:4]}...{bot_token_id[-4:]}" if bot_token_id and len(bot_token_id) > 8 else "N/A"
    
    response = (
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"🤖 <b>کۆنترۆڵی بۆت</b>\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"📂 فایل: <code>{file_name}</code>\n"
        f"📊 دۆخ: {status_emoji}\n"
        f"🤖 یوزەر: {bot_username}\n"
        f"🔑 تۆکین: <code>{bot_token_short}</code>\n"
        f"⏱️ کات: {uptime}\n"
        f"📈 دەستپێکردن: {start_count}"
    )
    
    # Create ReplyKeyboard buttons
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if is_running:
        markup.add("⏸ وەستاندن", "🔄 نوێکردنەوە")
    else:
        markup.add("▶️ دەستپێکردن", "🔄 نوێکردنەوە")
    
    markup.add("📥 دابەزاندن", "🗑 سڕینەوە")
    markup.add("📋 لۆگ", "📋 Requirements")
    markup.add("🔙 گەڕانەوە بۆ مینیو")
    
    bot.send_message(chat_id, response, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["▶️ دەستپێکردن", "⏸ وەستاندن", "🔄 نوێکردنەوە", "📥 دابەزاندن", "🗑 سڕینەوە", "📋 لۆگ", "📋 Requirements"])
def handle_control_buttons(message):
    user_id = message.from_user.id
    action = message.text
    
    # Get current file from context
    file_name = current_file_context.get(user_id)
    if not file_name:
        files = user_files.get(user_id, [])
        if files:
            file_name = files[-1][0]
        else:
            bot.send_message(message.chat.id, "❌ هیچ فایلێکت نییە!")
            return
    
    files = user_files.get(user_id, [])
    file_info = next((f for f in files if f[0] == file_name), None)
    
    if not file_info:
        bot.send_message(message.chat.id, "❌ فایل نەدۆزرایەوە!")
        return
    
    script_key = f"{user_id}_{file_name}"
    
    try:
        if action == "▶️ دەستپێکردن":
            if is_bot_running(user_id, file_name):
                bot.send_message(message.chat.id, "⚠️ بۆت پێشتر کاردەکات!")
                return
            start_script(user_id, file_name)
            bot.send_message(message.chat.id, "▶️ بۆت دەستی پێکرد!")
            show_bot_control(message.chat.id, user_id, file_info)
            
        elif action == "⏸ وەستاندن":
            if not is_bot_running(user_id, file_name):
                bot.send_message(message.chat.id, "⚠️ بۆت پێشتر وەستاوە!")
                return
            stop_script(user_id, file_name)
            bot.send_message(message.chat.id, "⏸ بۆت وەستاندرا!")
            show_bot_control(message.chat.id, user_id, file_info)
            
        elif action == "🔄 نوێکردنەوە":
            if is_bot_running(user_id, file_name):
                stop_script(user_id, file_name)
                time.sleep(1)
            start_script(user_id, file_name)
            bot.send_message(message.chat.id, "🔄 بۆت نوێکرایەوە!")
            show_bot_control(message.chat.id, user_id, file_info)
            
        elif action == "📥 دابەزاندن":
            user_folder = get_user_folder(user_id)
            file_path = os.path.join(user_folder, file_name)
            
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    bot.send_document(message.chat.id, f, caption=f"📥 {file_name}")
                bot.send_message(message.chat.id, "✅ فایل نێردرا!")
            else:
                bot.send_message(message.chat.id, "❌ فایل نەدۆزرایەوە!")
                
        elif action == "🗑 سڕینەوە":
            if is_bot_running(user_id, file_name):
                stop_script(user_id, file_name)
            
            user_folder = get_user_folder(user_id)
            file_path = os.path.join(user_folder, file_name)
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
                if not user_files[user_id]:
                    del user_files[user_id]
            
            remove_user_file_db(user_id, file_name)
            
            bot.send_message(message.chat.id, "🗑 فایل سڕایەوە!")
            send_main_menu(message.chat.id, user_id)
            
        elif action == "📋 لۆگ":
            user_folder = get_user_folder(user_id)
            log_filename = f"{script_key}_log.log"
            log_path = os.path.join(user_folder, log_filename)
            
            if not os.path.exists(log_path):
                bot.send_message(message.chat.id, "📄 هیچ تۆمارێک نییە.")
                return

            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_file:
                    log_content = log_file.read()
                
                if not log_content.strip():
                    bot.send_message(message.chat.id, "📄 تۆمار بەتاڵە.")
                    return
                
                max_message_length = 4000
                if len(log_content) > max_message_length:
                    log_content = log_content[-max_message_length:]
                    log_content = "... (کۆتایی تۆمار)\n\n" + log_content
                
                bot.send_message(message.chat.id, f"📄 <b>تۆماری {file_name}:</b>\n\n<pre>{log_content}</pre>", parse_mode='HTML')
                
            except Exception as e:
                logger.error(f"Error sending log: {e}")
                bot.send_message(message.chat.id, f"❌ هەڵە: {str(e)}")
                
        elif action == "📋 Requirements":
            user_folder = get_user_folder(user_id)
            req_path = os.path.join(user_folder, 'requirements.txt')
            
            if os.path.exists(req_path):
                with open(req_path, 'r', encoding='utf-8') as f:
                    requirements = f.read()
                bot.send_message(message.chat.id, f"📋 <b>Requirements.txt:</b>\n\n<pre>{requirements}</pre>", parse_mode='HTML')
            else:
                bot.send_message(message.chat.id, "❌ فایلی requirements.txt نەدۆزرایەوە!")
                
    except Exception as e:
        logger.error(f"Error in bot control {action}: {e}", exc_info=True)
        bot.send_message(message.chat.id, f"❌ هەڵە: {str(e)}")

@bot.message_handler(func=lambda message: message.text == "🔙 گەڕانەوە بۆ مینیو")
def back_to_main_menu(message):
    send_main_menu(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('start_', 'stop_', 'restart_', 'download_', 'delete_', 'log_', 'requirements_')))
def handle_bot_controls(call):
    action = call.data.split('_')[0]
    script_key = '_'.join(call.data.split('_')[1:])
    parts = script_key.split('_', 1)
    
    if len(parts) != 2:
        bot.answer_callback_query(call.id, "❌ فۆرماتی نادروست.")
        return
    
    user_id = int(parts[0])
    file_name = parts[1]
    
    if call.from_user.id != user_id and call.from_user.id != OWNER_ID and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ ڕێگەپێدراو نیت")
        return

    try:
        if action == 'start':
            if is_bot_running(user_id, file_name):
                bot.answer_callback_query(call.id, "⚠️ بۆت پێشتر کاردەکات!")
                return
            start_script(user_id, file_name)
            bot.answer_callback_query(call.id, "▶️ بۆت دەستی پێکرد!")
            
        elif action == 'stop':
            if not is_bot_running(user_id, file_name):
                bot.answer_callback_query(call.id, "⚠️ بۆت پێشتر وەستاوە!")
                return
            stop_script(user_id, file_name)
            bot.answer_callback_query(call.id, "⏸ بۆت وەستاندرا!")
            
        elif action == 'restart':
            if is_bot_running(user_id, file_name):
                stop_script(user_id, file_name)
                time.sleep(1)
            start_script(user_id, file_name)
            bot.answer_callback_query(call.id, "🔄 بۆت نوێکرایەوە!")
            
        elif action == 'download':
            user_folder = get_user_folder(user_id)
            file_path = os.path.join(user_folder, file_name)
            
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    bot.send_document(call.message.chat.id, f, caption=f"📥 {file_name}")
                bot.answer_callback_query(call.id, "✅ فایل نێردرا!")
            else:
                bot.answer_callback_query(call.id, "❌ فایل نەدۆزرایەوە!")
                
        elif action == 'delete':
            if is_bot_running(user_id, file_name):
                stop_script(user_id, file_name)
            
            user_folder = get_user_folder(user_id)
            file_path = os.path.join(user_folder, file_name)
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
                if not user_files[user_id]:
                    del user_files[user_id]
            
            remove_user_file_db(user_id, file_name)
            
            bot.answer_callback_query(call.id, "🗑 فایل سڕایەوە!")
            send_main_menu(call.message.chat.id, call.from_user.id)
            
        elif action == 'log':
            user_folder = get_user_folder(user_id)
            log_filename = f"{script_key}_log.log"
            log_path = os.path.join(user_folder, log_filename)
            
            if not os.path.exists(log_path):
                bot.answer_callback_query(call.id, "📄 هیچ تۆمارێک نییە.", show_alert=True)
                return

            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_file:
                    log_content = log_file.read()
                
                if not log_content.strip():
                    bot.answer_callback_query(call.id, "📄 تۆمار بەتاڵە.", show_alert=True)
                    return
                
                max_message_length = 4000
                if len(log_content) > max_message_length:
                    log_content = log_content[-max_message_length:]
                    log_content = "... (کۆتایی تۆمار)\n\n" + log_content
                
                bot.send_message(call.message.chat.id, f"📄 <b>تۆماری {file_name}:</b>\n\n<pre>{log_content}</pre>", parse_mode='HTML')
                bot.answer_callback_query(call.id, "✅ تۆمار نێردرا.")
                
            except Exception as e:
                logger.error(f"Error sending log: {e}")
                bot.answer_callback_query(call.id, f"❌ هەڵە: {str(e)}", show_alert=True)
                
        elif action == 'requirements':
            user_folder = get_user_folder(user_id)
            req_path = os.path.join(user_folder, 'requirements.txt')
            
            if os.path.exists(req_path):
                with open(req_path, 'r', encoding='utf-8') as f:
                    requirements = f.read()
                bot.send_message(call.message.chat.id, f"📋 <b>Requirements.txt:</b>\n\n<pre>{requirements}</pre>", parse_mode='HTML')
                bot.answer_callback_query(call.id, "✅ Requirements نێردرا!")
            else:
                bot.answer_callback_query(call.id, "❌ فایلی requirements.txt نەدۆزرایەوە!")
                
    except Exception as e:
        logger.error(f"Error in bot control {action}: {e}", exc_info=True)
        bot.answer_callback_query(call.id, f"❌ هەڵە: {str(e)}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "owner_view_all_users")
def admin_view_all_users(call):
    if call.from_user.id != OWNER_ID and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ ڕێگەپێدراو نیت")
        return

    display_all_user_files(OWNER_ID, call.message.message_id)

def display_all_user_files(admin_chat_id, message_id=None):
    all_files_data = get_all_user_files_from_db()
    
    user_file_groups = {}
    for file_info in all_files_data:
        user_id = file_info['user_id']
        if user_id not in user_file_groups:
            user_file_groups[user_id] = []
        user_file_groups[user_id].append(file_info)
    
    response = f"👑 <b>هەموو بەکارهێنەران:</b>\n\n"
    
    if not user_file_groups:
        response += "هیچ بەکارهێنەرێک نییە."
    
    markup = types.InlineKeyboardMarkup()
    for user_id, files_list in user_file_groups.items():
        file_count = len(files_list)
        running_count = sum(1 for f in files_list if is_bot_running(user_id, f['file_name']))
        markup.add(types.InlineKeyboardButton(
            f"👤 {user_id} ({file_count} فایل, {running_count} کاردەکات)",
            callback_data=f"view_user_{user_id}"
        ))

    markup.add(types.InlineKeyboardButton("🔙 گەڕانەوە", callback_data="back_to_owner_panel"))

    if message_id:
        try:
            bot.edit_message_text(
                chat_id=admin_chat_id,
                message_id=message_id,
                text=response,
                parse_mode='HTML',
                reply_markup=markup
            )
        except:
            bot.send_message(admin_chat_id, response, parse_mode='HTML', reply_markup=markup)
    else:
        bot.send_message(admin_chat_id, response, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_user_'))
def view_specific_user(call):
    if call.from_user.id != OWNER_ID and not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ ڕێگەپێدراو نیت")
        return
    
    user_id = int(call.data.split('_')[2])
    files = user_files.get(user_id, [])
    
    if not files:
        bot.answer_callback_query(call.id, "هیچ فایلێک نییە بۆ ئەم بەکارهێنەرە")
        return
    
    for file_name, file_type, status, bot_token_id, bot_username in files:
        script_key = f"{user_id}_{file_name}"
        is_running = is_bot_running(user_id, file_name)
        
        status_emoji = "🟢 Running" if is_running else "🔴 Stopped"
        uptime = get_bot_uptime(user_id, file_name)
        start_count = get_bot_start_count(user_id, file_name)
        
        bot_token_short = f"{bot_token_id[:4]}...{bot_token_id[-4:]}" if bot_token_id and len(bot_token_id) > 8 else "N/A"
        
        response = (
            f"👑 <b>کۆنترۆڵی ئەدمین</b>\n\n"
            f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
            f"┃ 👤 بەکارهێنەر: <code>{user_id}</code>\n"
            f"┃ 📂 فایل: <code>{file_name}</code>\n"
            f"┃ 📊 دۆخ: {status_emoji}\n"
            f"┃ 🤖 یوزەر: {bot_username}\n"
            f"┃ 🔑 تۆکین: <code>{bot_token_short}</code>\n"
            f"┃ ⏱️ کات: {uptime}\n"
            f"┃ 📈 دەستپێکردن: {start_count}\n"
            f"┗━━━━━━━━━━━━━━━━━━━━┛"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        if is_running:
            markup.add(
                types.InlineKeyboardButton("⏸ وەستاندن", callback_data=f"stop_{script_key}"),
                types.InlineKeyboardButton("🔄 نوێکردنەوە", callback_data=f"restart_{script_key}")
            )
        else:
            markup.add(
                types.InlineKeyboardButton("▶️ دەستپێکردن", callback_data=f"start_{script_key}"),
                types.InlineKeyboardButton("🔄 نوێکردنەوە", callback_data=f"restart_{script_key}")
            )
        
        markup.add(
            types.InlineKeyboardButton("📋 لۆگ", callback_data=f"log_{script_key}"),
            types.InlineKeyboardButton("🗑 سڕینەوە", callback_data=f"delete_{script_key}")
        )
        
        bot.send_message(call.message.chat.id, response, parse_mode='HTML', reply_markup=markup)
    
    bot.answer_callback_query(call.id, f"✅ فایلەکانی بەکارهێنەر {user_id}")

def cleanup():
    script_keys_to_stop = list(bot_scripts.keys())
    for key in script_keys_to_stop:
        if key in bot_scripts and 'process' in bot_scripts[key]: 
            script_info_to_kill = bot_scripts[key]
            kill_process_tree(script_info_to_kill)
            if key in bot_scripts:
                del bot_scripts[key]
atexit.register(cleanup)

if __name__ == '__main__':
    keep_alive()
    logger.info("=" * 50)
    logger.info("🚀 بۆتی Hosting دەستی پێکرد بە سەرکەوتوویی!")
    logger.info(f"👑 خاوەن: {OWNER_ID}")
    logger.info(f"📢 کەناڵ: {UPDATE_CHANNEL}")
    logger.info(f"💎 وەشان: 2.0 Pro")
    logger.info("=" * 50)
    bot.infinity_polling()
