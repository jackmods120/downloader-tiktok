import os
import time
import logging
import httpx
import re
import html
import asyncio
import random
import string
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAudio,
    ForceReply
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from telegram.constants import ParseMode, ChatMemberStatus

# ==============================================================================
# ------------------------- ڕێکخستنە سەرەکییەکان (CONFIG) -------------------------
# ==============================================================================
TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://www.api.hyper-bd.site/Tiktok/?url="
CHANNEL_URL = "https://t.me/jack_721_mod"
DB_URL = os.getenv("DB_URL")
DB_SECRET = os.getenv("DB_SECRET")

# زانیاری خاوەنی سەرەکی
OWNER_ID = 5977475208 
BOT_VERSION = "Ultimate Pro Max v5.0"
DEVELOPER = "@j4ck_721s"

# ==============================================================================
# ------------------------- گۆڕاوە گشتییەکان (GLOBALS) --------------------------
# ==============================================================================
admins_list = {OWNER_ID} 
forced_channels =[]  
blocked_users = set()
vip_users = set()
bot_settings_global = {
    "maintenance_mode": False,
    "total_downloads": 0,
    "total_videos": 0,
    "total_audios": 0,
    "total_photos": 0
}

SESSION_EXPIRE = 600
API_TIMEOUT = 60
START_TIME = time.time()

# ڕێکخستنی لۆگەکان بۆ بینینی هەڵەکان
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
app = FastAPI()

# ==============================================================================
# ------------------------- فەنکشنە یارمەتیدەرەکان (HELPERS) ----------------------
# ==============================================================================

def get_random_id(length=6):
    """دروستکردنی کۆدێکی هەڕەمەکی بۆ ناوی گۆرانییەکان"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

def format_number(num):
    """گۆڕینی ژمارە گەورەکان بۆ شێوازی کورتکراوە (نموونە: 1.5M)"""
    if not num: return "0"
    try:
        num = int(num)
        if num >= 1_000_000: return f"{num/1_000_000:.1f}M"
        if num >= 1_000: return f"{num/1_000:.1f}K"
        return str(num)
    except: return "0"

def clean_title(title):
    """پاککردنەوەی ناونیشانی ڤیدیۆ لە هێما قەدەغەکراوەکان"""
    if not title: return "TikTok_Video"
    cleaned = re.sub(r'[\\/*?:"<>|]', '', title)
    return cleaned[:60] + "..." if len(cleaned) > 60 else cleaned

def firebase_url(path: str):
    """دروستکردنی لینکی فایەربەیس"""
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

def get_current_time():
    """وەرگرتنی کاتی ئێستا بە فۆرماتێکی جوان"""
    return datetime.now().strftime("%Y-%m-%d | %I:%M:%S %p")

def get_uptime():
    """هەژمارکردنی کاتی کارکردنی بۆتەکە"""
    uptime_sec = int(time.time() - START_TIME)
    days, rem = divmod(uptime_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, sec = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m {sec}s"

# ==============================================================================
# ------------------------- پشکنینە ئەمنییەکان (SECURITY) -----------------------
# ==============================================================================

def is_owner(user_id):
    """پشکنین ئایا یوزەر خاوەنی سەرەکییە"""
    return user_id == OWNER_ID

def is_admin(user_id):
    """پشکنین ئایا یوزەر ئەدمینە یان خاوەنە"""
    return user_id in admins_list or user_id == OWNER_ID

def is_blocked(user_id):
    """پشکنین ئایا یوزەر بلۆک کراوە"""
    return user_id in blocked_users

def is_vip(user_id):
    """پشکنین ئایا یوزەر VIP یە"""
    return user_id in vip_users or is_owner(user_id)

async def check_user_subscription(user_id, context):
    """پشکنینی جۆینی ناچاری بۆ چەناڵەکان"""
    if not forced_channels:
        return True, []
    
    not_joined =[]
    for channel in forced_channels:
        try:
            channel_username = channel.replace('@', '') if channel.startswith('@') else channel
            member = await context.bot.get_chat_member(chat_id=f"@{channel_username}", user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                not_joined.append(channel)
        except Exception as e:
            logger.warning(f"Failed to check channel {channel}: {e}")
            pass # ئەگەر بۆت ئەدمین نەبوو یان هەڵە هەبوو، یوزەرەکە بلۆک ناکەین
            
    return len(not_joined) == 0, not_joined

# ==============================================================================
# ------------------------- کارەکانی داتابەیس (DATABASE CRUD) -------------------
# ==============================================================================

async def load_settings():
    """هێنانەوەی هەموو ڕێکخستنەکان لە داتابەیس (بۆ کاتی ڕیستارت بوونی ڤێرسڵ)"""
    global admins_list, forced_channels, blocked_users, vip_users, bot_settings_global
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            r = await client.get(firebase_url("system_settings"))
            if r.status_code == 200 and r.json():
                data = r.json()
                admins_list = set(data.get("admins", [OWNER_ID]))
                forced_channels = data.get("channels", [])
                blocked_users = set(data.get("blocked",[]))
                vip_users = set(data.get("vips",[]))
                saved_stats = data.get("stats", {})
                bot_settings_global["maintenance_mode"] = data.get("maintenance", False)
                bot_settings_global["total_downloads"] = saved_stats.get("total_downloads", 0)
                bot_settings_global["total_videos"] = saved_stats.get("total_videos", 0)
                bot_settings_global["total_audios"] = saved_stats.get("total_audios", 0)
                bot_settings_global["total_photos"] = saved_stats.get("total_photos", 0)
                logger.info("✅ زانیارییەکان لە داتابەیسەوە هێنرانەوە.")
        except Exception as e:
            logger.error(f"❌ هەڵە لە هێنانەوەی داتابەیس: {e}")

async def save_settings():
    """پاشەکەوتکردنی هەموو ڕێکخستنەکان لە داتابەیس"""
    settings = {
        "admins": list(admins_list),
        "channels": forced_channels,
        "blocked": list(blocked_users),
        "vips": list(vip_users),
        "maintenance": bot_settings_global["maintenance_mode"],
        "stats": {
            "total_downloads": bot_settings_global["total_downloads"],
            "total_videos": bot_settings_global["total_videos"],
            "total_audios": bot_settings_global["total_audios"],
            "total_photos": bot_settings_global["total_photos"]
        }
    }
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            await client.put(firebase_url("system_settings"), json=settings)
        except Exception as e:
            logger.error(f"❌ هەڵە لە سەیڤکردنی داتابەیس: {e}")

async def save_user_data(user_id: int, data: dict):
    """سەیڤکردنی زانیاری کاتی یوزەر (وەک لینکی کۆتایی)"""
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        await client.put(firebase_url(f"user_sessions/{user_id}"), json=data)

async def is_user_exist(user_id: int):
    """پشکنین کە ئایا یوزەرەکە پێشتر بۆتی بەکارهێناوە"""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        r = await client.get(firebase_url(f"registered_users/{user_id}"))
        return r.status_code == 200 and r.json() is not None

async def register_new_user(user_id: int, user_info: dict):
    """تۆمارکردنی یوزەری نوێ لە داتابەیس هەمیشەیی"""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        await client.put(firebase_url(f"registered_users/{user_id}"), json=user_info)

async def get_user_data(user_id: int):
    """هێنانەوەی زانیاری کاتی یوزەر (بۆ دوگمەکانی داونلۆد)"""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        r = await client.get(firebase_url(f"user_sessions/{user_id}"))
        if r.status_code != 200: return None
        data = r.json()
        if not data or int(time.time()) - data.get("timestamp", 0) > SESSION_EXPIRE: return None
        return data

async def notify_admin_new_user(context, user):
    """ناردنی ئاگادارکردنەوە بۆ خاوەنی بۆت کاتێک یوزەرێکی نوێ دێت"""
    msg = (
        f"╔═══════════════════╗\n"
        f"   🔔 <b>بەکارهێنەرێکی نوێ</b>\n"
        f"╚═══════════════════╝\n\n"
        f"👤 <b>ناو:</b> {html.escape(user.first_name)}\n"
        f"🆔 <b>ئایدی:</b> <code>{user.id}</code>\n"
        f"🔗 <b>یوزەرنەیم:</b> @{user.username if user.username else 'نییە'}\n"
        f"📱 <b>پلاتفۆرم:</b> {user.language_code}\n\n"
        f"🕐 <b>کات:</b> {get_current_time()}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>Bot Engine:</b> {BOT_VERSION}"
    )
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode=ParseMode.HTML)
    except: pass

# ==============================================================================
# ------------------------- دروستکەری کیبۆردەکان (KEYBOARDS) --------------------
# ==============================================================================

def get_main_keyboard(user_id):
    """کیبۆردی سەرەکی بۆتەکە کە پڕە لە دوگمە"""
    keyboard = [[InlineKeyboardButton("📥 دابەزاندنی تیکتۆک", callback_data="cmd_download")],[
            InlineKeyboardButton("👤 پرۆفایلی من", callback_data="menu_profile"),
            InlineKeyboardButton("💎 بەشی VIP", callback_data="menu_vip")
        ],[
            InlineKeyboardButton("⚙️ ڕێکخستنەکان", callback_data="menu_settings"),
            InlineKeyboardButton("ℹ️ ڕێنمایی و یارمەتی", callback_data="cmd_help")
        ],
        [InlineKeyboardButton("📢 کەناڵی فەرمی بۆت", url=CHANNEL_URL)]
    ]
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 پانێڵی پێشکەوتووی ئەدمین 👑", callback_data="admin_panel_main")])
        
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard(user_id):
    """کیبۆردی پانێڵی ئەدمینی زەبەلاح"""
    keyboard = [[
            InlineKeyboardButton("📊 ئاماری گشتی", callback_data="admin_stats_full"),
            InlineKeyboardButton("📢 برۆدکاست (گشتی)", callback_data="admin_broadcast_ask")
        ],[
            InlineKeyboardButton("📢 بەڕێوەبردنی چەناڵ", callback_data="manage_channels_menu"),
            InlineKeyboardButton("🚫 بەڕێوەبردنی بلۆک", callback_data="manage_blocks_menu")
        ],[
            InlineKeyboardButton("💎 بەڕێوەبردنی VIP", callback_data="manage_vips_menu"),
            InlineKeyboardButton("⚙️ دۆخی چاکسازی", callback_data="admin_toggle_maintenance")
        ]
    ]
    
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("👥 بەڕێوەبردنی ئەدمینەکان", callback_data="manage_admins_menu")])
        
    keyboard.append([InlineKeyboardButton("🏠 گەڕانەوە بۆ مینیوی سەرەکی", callback_data="cmd_start")])
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard(callback_data="cmd_start"):
    """دوگمەیەکی سادەی گەڕانەوە"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 گەڕانەوە", callback_data=callback_data)]])

# ==============================================================================
# ------------------------- فەرمانە سەرەکییەکان (COMMANDS) ----------------------
# ==============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /start کە هەموو شتێک کۆنترۆڵ دەکات"""
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name
    
    # پشکنینی بلۆک
    if is_blocked(user_id):
        await update.message.reply_text("⛔ <b>ببورە، تۆ بلۆک کراویت لەلایەن بەڕێوەبەرایەتییەوە.</b>", parse_mode=ParseMode.HTML)
        return

    # پشکنینی دۆخی چاکسازی (Maintenance)
    if bot_settings_global["maintenance_mode"] and not is_admin(user_id):
        await update.message.reply_text(
            "🛠 <b>بۆتەکە لە باری چاکسازیدایە!</b>\n\n"
            "تکایە دواتر هەوڵ بدەرەوە، لە ئێستادا خەریکی نوێکردنەوەین.", 
            parse_mode=ParseMode.HTML
        )
        return

    # تۆمارکردنی یوزەری نوێ
    if not is_admin(user_id):
        user_exists = await is_user_exist(user_id)
        if not user_exists:
            asyncio.create_task(notify_admin_new_user(context, user))
            user_info = {
                "name": first_name,
                "username": user.username,
                "joined_date": get_current_time(),
                "is_vip": False
            }
            await register_new_user(user_id, user_info)

    # پشکنینی جۆینی چەناڵ
    if not is_admin(user_id) and forced_channels:
        is_sub, not_joined = await check_user_subscription(user_id, context)
        if not is_sub:
            text = (
                "╔═══════════════════╗\n"
                "   🔒 <b>جۆینی ناچاری</b>\n"
                "╚═══════════════════╝\n\n"
                "بۆ بەکارهێنانی بۆتەکەمان بێ بەرامبەر، تکایە سەرەتا جۆینی ئەم چەناڵانەی خوارەوە بکە:\n"
            )
            keyboard =[]
            for ch in not_joined:
                keyboard.append([InlineKeyboardButton(f"📢 جۆین کردن: {ch}", url=f"https://t.me/{ch.replace('@','')}")])
            keyboard.append([InlineKeyboardButton("✅ جۆینم کرد، دەستپێکردن", callback_data="check_sub_start")])
            
            if update.callback_query:
                await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
            return
    
    # دروستکردنی دەقی بەخێرهاتن بەپێی جۆری یوزەر
    badge = "👑 خاوەن" if is_owner(user_id) else ("⚡ ئەدمین" if is_admin(user_id) else ("💎 VIP" if is_vip(user_id) else "👤 بەکارهێنەر"))
    
    text = (
        f"╔═══════════════════╗\n"
        f"   👋 <b>سڵاو {html.escape(first_name)}</b>\n"
        f"╚═══════════════════╝\n\n"
        f"🤖 <b>ئاستی تۆ:</b> {badge}\n"
        f"🚀 <b>وەشان:</b> {BOT_VERSION}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"من پێشکەوتووترین بۆتی تیکتۆکم، دەتوانم بە خێراییەکی باوەڕنەکراو ڤیدیۆ و وێنە و گۆرانییەکانت بۆ دابەزێنم بەبێ لۆگۆ!\n\n"
        f"👇 <b>تکایە لە مینیوی خوارەوە خزمەتگوزارییەک هەڵبژێرە:</b>"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user_id))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user_id))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی یارمەتی دەربارەی چۆنیەتی بەکارهێنان"""
    text = (
        "╔═══════════════════╗\n"
        "     📚 <b>ڕێنمایی بەکارهێنان</b>\n"
        "╚═══════════════════╝\n\n"
        "<b>چۆن ڤیدیۆ دابەزێنم؟</b>\n"
        "1️⃣ بڕۆ ناو ئەپڵیکەیشنی تیکتۆک.\n"
        "2️⃣ ڤیدیۆکە یان وێنەکە بدۆزەرەوە.\n"
        "3️⃣ کلیک لە دوگمەی Share (بەشداریکردن) بکە.\n"
        "4️⃣ کلیک لە Copy Link (کۆپیکردنی بەستەر) بکە.\n"
        "5️⃣ وەرە ئێرە و لینکەکە بنێرە وەک نامەیەک.\n\n"
        "<b>تێبینییەکان:</b>\n"
        "🔸 ڤیدیۆی پرایڤت دانابەزێت.\n"
        "🔸 بۆتەکە پشتگیری Slide (وێنەکان) دەکات.\n"
        "🔸 دەتوانیت گۆرانییەکە بە جیا دابەزێنیت."
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())

# ==============================================================================
# ------------------------- بەڕێوەبردنی کڵیکەکان (CALLBACK QUERY) ---------------
# ==============================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    # ------------------ دوگمە بنەڕەتییەکان ------------------
    if data == "check_sub_start" or data == "cmd_start":
        await start_command(update, context)
        return
    elif data == "cmd_help": 
        await help_command(update, context)
        return
    elif data == "cmd_download":
        await query.message.reply_text(
            "<b>🔗 تکایە لینکی تیکتۆکەکە لێرەدا پەیست (Paste) بکە و بۆمی بنێرە:</b>", 
            parse_mode=ParseMode.HTML, 
            reply_markup=ForceReply(selective=True)
        )
        return
    elif data == "close": 
        await query.message.delete()
        return

    # ------------------ مینیوی بەکارهێنەر ------------------
    elif data == "menu_profile":
        is_user_vip = "بەڵێ 💎" if is_vip(user_id) else "نەخێر (Free)"
        text = (
            f"╔═══════════════════╗\n"
            f"   👤 <b>پرۆفایلی بەکارهێنەر</b>\n"
            f"╚═══════════════════╝\n\n"
            f"🆔 <b>ئایدی:</b> <code>{user_id}</code>\n"
            f"👤 <b>ناو:</b> {html.escape(query.from_user.first_name)}\n"
            f"💎 <b>هەژماری VIP:</b> {is_user_vip}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>تێبینی: لە داهاتوودا ئاماری داونلۆدەکانت لێرە زیاد دەکرێت.</i>"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
        return

    elif data == "menu_vip":
        text = (
            f"╔═══════════════════╗\n"
            f"   💎 <b>هەژماری VIP (پریمیۆم)</b>\n"
            f"╚═══════════════════╝\n\n"
            f"بە کڕینی VIP، ئەم تایبەتمەندیانەت دەبێت:\n"
            f"✅ خێرایی داونلۆدی زۆر زیاتر.\n"
            f"✅ بێ ڕیکلام و بێ جۆین کردنی چەناڵ.\n"
            f"✅ داونلۆدی بێسنوور بۆ وێنەکان.\n\n"
            f"💳 <b>بۆ کڕین پەیوەندی بکە بە:</b>\n{DEVELOPER}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
        return

    elif data == "menu_settings":
        text = (
            f"╔═══════════════════╗\n"
            f"   ⚙️ <b>ڕێکخستنەکانی بۆت</b>\n"
            f"╚═══════════════════╝\n\n"
            f"🌍 <b>زمان:</b> کوردی (سەرەکی)\n"
            f"🔔 <b>ئاگادارکردنەوەکان:</b> چالاکە\n\n"
            f"<i>ئەم بەشە لە ژێر پەرەپێداندایە...</i>"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
        return

    # ------------------ بەشی داونلۆد و پرۆسێس ------------------
    if data.startswith("dl_"):
        action = data.split("_")[1]
        user_data = await get_user_data(user_id)
        
        if not user_data:
            await query.answer("⚠️ کاتەکەت بەسەرچووە، تکایە لینکەکە دووبارە بنێرەوە.", show_alert=True)
            return
        
        d = user_data["details"]
        creator = user_data["creator"]
        title = clean_title(d.get('title', ''))
        images = d.get("images",[])
        
        # دیزاینی کەپشنی ڤیدیۆ/گۆرانی
        caption = (
            f"🎬 <b>{html.escape(title)}</b>\n"
            f"👤 <b>{html.escape(creator)}</b>\n\n"
            f"🤖 <b>Downloaded by {DEVELOPER}</b>"
        )
        
        buttons = [[InlineKeyboardButton("🗑 سڕینەوەی ئەم نامەیە", callback_data="close")]]
        
        try:
            # مامەڵەکردن لەگەڵ وێنەکان یان ڤیدیۆ
            if action == "photos" or (action == "video" and images):
                await query.answer("⏳ خەریکی ناردنی وێنەکانم...", show_alert=False)
                if not images:
                    await query.answer("❌ کێشە هەیە، هیچ وێنەیەک نەدۆزرایەوە.", show_alert=True)
                    return
                
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_photos"] += 1
                await save_settings()
                
                # تەلەگرام تەنها ڕێگە بە ١٠ وێنە دەدات لە یەک گروپدا
                media_group =[InputMediaPhoto(media=img) for img in images[:10]]
                media_group[0].caption = caption
                media_group[0].parse_mode = ParseMode.HTML
                
                await query.message.delete()
                await context.bot.send_media_group(chat_id=user_id, media=media_group)
            
            elif action == "video":
                await query.answer("⏳ ئامادەکردنی ڤیدیۆکە...", show_alert=False)
                await query.message.edit_caption("<b>🚀 کەمێک چاوەڕێ بکە، خەریکی ئاپلۆدی ڤیدیۆکەم...</b>", parse_mode=ParseMode.HTML)
                
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_videos"] += 1
                await save_settings()
                
                await query.message.edit_media(InputMediaVideo(media=d["video"]["play"], caption=caption, parse_mode=ParseMode.HTML))
            
            elif action == "audio":
                await query.answer("⏳ ئامادەکردنی گۆرانی...", show_alert=False)
                
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_audios"] += 1
                await save_settings()
                
                music_name = f"{DEVELOPER}-{get_random_id()}"
                await query.message.edit_caption("<b>🚀 کەمێک چاوەڕێ بکە، خەریکی ئاپلۆدی گۆرانییەکەم...</b>", parse_mode=ParseMode.HTML)
                await query.message.edit_media(
                    InputMediaAudio(
                        media=d["audio"]["play"], 
                        caption=caption, 
                        parse_mode=ParseMode.HTML, 
                        title=music_name, 
                        performer=DEVELOPER
                    )
                )

        except Exception as e:
            logger.error(f"Upload Error: {e}")
            link_to_send = d["video"]["play"] if not images else images[0]
            link_btn = [[InlineKeyboardButton("🔗 دابەزاندن لە ڕێگەی بڕاوسەر", url=link_to_send)],[InlineKeyboardButton("🗑 داخستن", callback_data="close")]
            ]
            await query.message.edit_caption(
                f"⚠️ <b>ببورە، قەبارەی ئەم فایلە زۆر گەورەیە بۆ تەلەگرام!</b>\n\nتکایە لە ڕێگەی دوگمەی خوارەوە ڕاستەوخۆ دایبەزێنە ناو مۆبایلەکەت.", 
                parse_mode=ParseMode.HTML, 
                reply_markup=InlineKeyboardMarkup(link_btn)
            )
        return

    # ==========================================================================
    # ------------------------- پانێڵی پێشکەوتووی ئەدمین -------------------------
    # ==========================================================================
    
    if not is_admin(user_id):
        await query.answer("⛔ ئەم بەشە تەنیا بۆ ئەدمینەکانە!", show_alert=True)
        return

    if data == "admin_panel_main":
        text = (
            f"╔═══════════════════╗\n"
            f"   👑 <b>پانێڵی کۆنترۆڵی سەرەکی</b>\n"
            f"╚═══════════════════╝\n\n"
            f"بەخێربێیت گەورەم. لێرەوە دەتوانیت کۆنترۆڵی تەواوی بۆتەکە بکەیت."
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard(user_id))
    
    # ----------------- ئامارەکان -----------------
    elif data == "admin_stats_full":
        text = (
            f"╔═══════════════════╗\n"
            f"   📊 <b>ئاماری پێشکەوتووی بۆت</b>\n"
            f"╚═══════════════════╝\n\n"
            f"👥 <b>دەسەڵاتەکان:</b>\n"
            f"├ ئەدمینەکان: <code>{len(admins_list)}</code>\n"
            f"├ کەسانی VIP: <code>{len(vip_users)}</code>\n"
            f"├ چەناڵەکان: <code>{len(forced_channels)}</code>\n"
            f"└ بلۆککراوەکان: <code>{len(blocked_users)}</code>\n\n"
            f"📈 <b>ئاماری داونلۆدەکان:</b>\n"
            f"├ کۆی گشتی پرۆسەکان: <code>{bot_settings_global['total_downloads']}</code>\n"
            f"├ ڤیدیۆکان: <code>{bot_settings_global['total_videos']}</code>\n"
            f"├ گۆرانییەکان: <code>{bot_settings_global['total_audios']}</code>\n"
            f"└ وێنەکان: <code>{bot_settings_global['total_photos']}</code>\n\n"
            f"⚙️ <b>سیستەم:</b>\n"
            f"├ دۆخی چاکسازی: {'بەڵێ 🔴' if bot_settings_global['maintenance_mode'] else 'نەخێر 🟢'}\n"
            f"├ کاتی کارکردن: <code>{get_uptime()}</code>\n"
            f"└ ڤێرژن: {BOT_VERSION}\n\n"
            f"🕐 {get_current_time()}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard("admin_panel_main"))

    # ----------------- ناردنی گشتی (Broadcast) -----------------
    elif data == "admin_broadcast_ask":
        await query.message.reply_text(
            "📢 <b>سیستەمی برۆدکاست:</b>\n\nتکایە ئەو نامەیەی دەتەوێت بینێریت بۆم بنێرە (وەک Reply):\n<i>تێبینی: لە Vercel ڕەنگە بۆ هەمووان نەڕوات.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        )

    # ----------------- دۆخی چاکسازی (Maintenance) -----------------
    elif data == "admin_toggle_maintenance":
        if not is_owner(user_id):
            await query.answer("⛔ تەنیا خاوەنی سەرەکی دەتوانێت ئەمە بکات!", show_alert=True)
            return
            
        current = bot_settings_global["maintenance_mode"]
        bot_settings_global["maintenance_mode"] = not current
        await save_settings()
        
        status = "چالاک کرا 🔴 (بۆت وەستا بۆ یوزەر)" if not current else "ناچالاک کرا 🟢 (بۆت ئیش دەکاتەوە)"
        await query.answer(f"دۆخی چاکسازی {status}", show_alert=True)
        
        # گەڕانەوە بۆ پانێڵ
        await query.edit_message_text(f"✅ <b>سەرکەوتوو بوو.</b> دۆخی چاکسازی گۆڕدرا.\nئێستا: {status}", parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard("admin_panel_main"))

    # ----------------- بەڕێوەبردنی ئەدمینەکان -----------------
    elif data == "manage_admins_menu":
        if not is_owner(user_id): 
            await query.answer("⛔ تەنیا خاوەنی سەرەکی دەتوانێت ئەدمین بەڕێوە ببات!", show_alert=True)
            return
            
        kb = [[InlineKeyboardButton("➕ زیادکردنی ئەدمین پێشکەوتوو", callback_data="add_admin_ask")],[InlineKeyboardButton("📋 لیستی ئەدمینەکان", callback_data="list_admins")],[InlineKeyboardButton("🔙 گەڕانەوە بۆ پانێڵ", callback_data="admin_panel_main")]
        ]
        await query.edit_message_text("👥 <b>بەشی بەڕێوەبردنی ئەدمینەکان</b>\n\nچی دەکەیت؟", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "add_admin_ask":
        await query.message.reply_text(
            "🆔 <b>تکایە ئایدی تێلیگرامی ئەو کەسە بنێرە:</b>\nدەبێت تەنها ژمارە بێت.",
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        )

    elif data == "list_admins":
        kb =[]
        for admin in admins_list:
            tag = " (خاوەن 👑)" if admin == OWNER_ID else ""
            kb.append([InlineKeyboardButton(f"👤 {admin}{tag}", callback_data=f"sel_admin_{admin}")])
        kb.append([InlineKeyboardButton("🔙 گەڕانەوە", callback_data="manage_admins_menu")])
        await query.edit_message_text("📋 <b>لیستی ئەدمینەکان:</b>\nکلیک لە هەر یەکێکیان بکە بۆ بینینی هەڵبژاردەکان.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("sel_admin_"):
        target_id = int(data.split("_")[2])
        if target_id == OWNER_ID:
            await query.answer("⚠️ خاوەنی سەرەکی ناسڕدرێتەوە!", show_alert=True)
            return
        
        kb = [[InlineKeyboardButton("🗑 سڕینەوەی ئەم ئەدمینە", callback_data=f"del_admin_{target_id}")],
            [InlineKeyboardButton("❌ پەشیمان بوونەوە", callback_data="list_admins")]
        ]
        await query.edit_message_text(f"⚠️ <b>ئایە بەتەواوی دڵنیایت کە دەتەوێت دەسەڵات لە ئایدی <code>{target_id}</code> وەربگریتەوە؟</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_admin_"):
        target_id = int(data.split("_")[2])
        if target_id in admins_list: 
            admins_list.remove(target_id)
            await save_settings() 
            await query.answer("✅ ئەدمینەکە سڕایەوە بە سەرکەوتوویی", show_alert=True)
        await query.edit_message_text("✅ <b>سڕایەوە.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="manage_admins_menu")]]))

    # ----------------- بەڕێوەبردنی چەناڵەکان -----------------
    elif data == "manage_channels_menu":
        kb = [[InlineKeyboardButton("➕ زیادکردنی چەناڵ بۆ جۆین", callback_data="add_channel_ask")],[InlineKeyboardButton("📋 لیستی چەناڵەکان", callback_data="list_channels")],[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel_main")]
        ]
        await query.edit_message_text("📢 <b>بەشی جۆینی ناچاری</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "add_channel_ask":
        await query.message.reply_text(
            "📢 <b>یوزەرنەیمی چەناڵەکە بنێرە (بە @ ەوە):</b>\nتێبینی: دەبێت بۆتەکە لەو چەناڵەدا ئەدمین بێت.",
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        )

    elif data == "list_channels":
        if not forced_channels:
            await query.edit_message_text("❌ <b>هیچ چەناڵێک بوونی نییە بۆ جۆینی ناچاری.</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="manage_channels_menu")]]))
            return

        kb =[]
        for ch in forced_channels:
            kb.append([InlineKeyboardButton(f"📢 {ch}", callback_data=f"sel_channel_{ch}")])
        kb.append([InlineKeyboardButton("🔙 گەڕانەوە", callback_data="manage_channels_menu")])
        await query.edit_message_text("📋 <b>لیستی چەناڵەکان:</b>\nکلیک بکە بۆ سڕینەوە.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("sel_channel_"):
        target_ch = data.replace("sel_channel_", "")
        kb = [[InlineKeyboardButton("🗑 سڕینەوەی چەناڵ", callback_data=f"del_channel_{target_ch}")],[InlineKeyboardButton("❌ پەشیمان بوونەوە", callback_data="list_channels")]
        ]
        await query.edit_message_text(f"⚠️ <b>دڵنیایت لە سڕینەوەی چەناڵی {target_ch}؟</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_channel_"):
        target_ch = data.replace("del_channel_", "")
        if target_ch in forced_channels:
            forced_channels.remove(target_ch)
            await save_settings() 
            await query.answer("✅ چەناڵەکە سڕایەوە", show_alert=True)
        await query.edit_message_text("✅ <b>سڕایەوە.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="manage_channels_menu")]]))

    # ----------------- بەڕێوەبردنی VIP -----------------
    elif data == "manage_vips_menu":
        kb = [[InlineKeyboardButton("➕ پێدانی VIP", callback_data="add_vip_ask")],[InlineKeyboardButton("📋 لیستی VIP (سڕینەوە)", callback_data="list_vips")],[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel_main")]
        ]
        await query.edit_message_text("💎 <b>بەڕێوەبردنی بەکارهێنەرانی VIP</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "add_vip_ask":
        await query.message.reply_text("💎 <b>ئایدی ئەو کەسە بنێرە کە دەتەوێت بیکەیت بە VIP:</b>", parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True))
        
    elif data == "list_vips":
        if not vip_users:
            await query.edit_message_text("❌ <b>هیچ کەسێکی VIP نییە.</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="manage_vips_menu")]]))
            return
        kb = [[InlineKeyboardButton(f"💎 {v}", callback_data=f"sel_vip_{v}")] for v in vip_users]
        kb.append([InlineKeyboardButton("🔙", callback_data="manage_vips_menu")])
        await query.edit_message_text("📋 <b>کەسانی VIP:</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        
    elif data.startswith("sel_vip_"):
        v_id = int(data.split("_")[2])
        kb = [[InlineKeyboardButton("🗑 لابردنی VIP", callback_data=f"del_vip_{v_id}")],[InlineKeyboardButton("❌", callback_data="list_vips")]]
        await query.edit_message_text(f"⚠️ <b>لابردنی VIP لە <code>{v_id}</code>؟</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_vip_"):
        v_id = int(data.split("_")[2])
        if v_id in vip_users: vip_users.remove(v_id); await save_settings()
        await query.edit_message_text("✅ <b>VIP لابرا.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="manage_vips_menu")]]))

    # ----------------- بەڕێوەبردنی بلۆک -----------------
    elif data == "manage_blocks_menu":
        kb = [[InlineKeyboardButton("🚫 بلۆککردنی کەسێک", callback_data="add_block_ask")],[InlineKeyboardButton("📋 لیستی بلۆککراوەکان", callback_data="list_blocks")],[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel_main")]
        ]
        await query.edit_message_text("🚫 <b>بەشی سزادان و بلۆککردن</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "add_block_ask":
        await query.message.reply_text("🚫 <b>ئایدی ئەو کەسە بنێرە کە دەیدەیتە بلۆک:</b>", parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True))
        
    elif data == "list_blocks":
        if not blocked_users:
            await query.edit_message_text("✅ <b>هیچ کەسێک بلۆک نەکراوە.</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="manage_blocks_menu")]]))
            return
        kb = [[InlineKeyboardButton(f"🚫 {b}", callback_data=f"sel_block_{b}")] for b in blocked_users]
        kb.append([InlineKeyboardButton("🔙", callback_data="manage_blocks_menu")])
        await query.edit_message_text("📋 <b>لیستی ڕەش:</b>\nبۆ لابردنی بلۆک کلیک بکە.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        
    elif data.startswith("sel_block_"):
        b_id = int(data.split("_")[2])
        kb = [[InlineKeyboardButton("✅ لابردنی بلۆک (لێخۆشبوون)", callback_data=f"del_block_{b_id}")],[InlineKeyboardButton("❌", callback_data="list_blocks")]]
        await query.edit_message_text(f"⚠️ <b>لێخۆشبوون بۆ <code>{b_id}</code>؟</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_block_"):
        b_id = int(data.split("_")[2])
        if b_id in blocked_users: blocked_users.remove(b_id); await save_settings()
        await query.edit_message_text("✅ <b>بلۆک لابرا.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="manage_blocks_menu")]]))


# ==============================================================================
# ------------------------- وەرگرتنی نامە و ڕیپلەی (MESSAGE HANDLER) -------------
# ==============================================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text: return
    user_id = update.effective_user.id
    msg = update.message.text.strip()
    
    # ----------------- مامەڵەکردن لەگەڵ ڕیپلەی ئەدمین -----------------
    if update.message.reply_to_message and update.message.reply_to_message.from_user.is_bot:
        original_text = update.message.reply_to_message.text
        
        if "ئایدی تێلیگرامی ئەو کەسە بنێرە" in original_text:
            if not is_owner(user_id): return
            try: 
                new_id = int(msg)
                admins_list.add(new_id)
                await save_settings()
                await update.message.reply_text(f"✅ <b>سەرکەوتوو بوو!</b> ئایدی <code>{new_id}</code> ئێستا ئەدمینە.", parse_mode=ParseMode.HTML)
            except: 
                await update.message.reply_text("❌ <b>هەڵە!</b> دەبێت تەنها ژمارە بنێریت.", parse_mode=ParseMode.HTML)
            return

        elif "یوزەرنەیمی چەناڵەکە بنێرە" in original_text:
            if not is_admin(user_id): return
            ch = msg if msg.startswith("@") else f"@{msg}"
            if ch not in forced_channels: 
                forced_channels.append(ch)
                await save_settings()
                await update.message.reply_text(f"✅ <b>زیادکرا!</b> چەناڵی {ch} خرایە لیستی ناچاری.", parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text("⚠️ ئەم چەناڵە پێشتر هەیە.", parse_mode=ParseMode.HTML)
            return

        elif "ئەو پەیامە بنێرە کە دەتەوێت بۆ هەمووانی" in original_text:
            if not is_admin(user_id): return
            await update.message.reply_text(f"✅ <b>پەیامەکەت ئامادەکرا بۆ ناردن:</b>\n\n{msg}\n\n<i>(لە سیستەمی Vercel ناردن بۆ هەزاران کەس قورسە، ئەمە تەنها ڕووکارە)</i>", parse_mode=ParseMode.HTML)
            return
            
        elif "ئایدی ئەو کەسە بنێرە کە دەتەوێت بیکەیت بە VIP" in original_text:
            if not is_admin(user_id): return
            try: 
                v_id = int(msg)
                vip_users.add(v_id)
                await save_settings()
                await update.message.reply_text(f"💎 <b>پیرۆزە!</b> ئایدی <code>{v_id}</code> بوو بە VIP.", parse_mode=ParseMode.HTML)
            except: 
                await update.message.reply_text("❌ ژمارە بنێرە.")
            return
            
        elif "ئایدی ئەو کەسە بنێرە کە دەیدەیتە بلۆک" in original_text:
            if not is_admin(user_id): return
            try: 
                b_id = int(msg)
                if is_owner(b_id):
                    await update.message.reply_text("⚠️ ناتوانیت خاوەن بلۆک بکەیت!")
                    return
                blocked_users.add(b_id)
                await save_settings()
                await update.message.reply_text(f"🚫 <b>باند کرا!</b> ئایدی <code>{b_id}</code> بلۆک کرا.", parse_mode=ParseMode.HTML)
            except: 
                await update.message.reply_text("❌ ژمارە بنێرە.")
            return

    # ----------------- مامەڵەکردن لەگەڵ لینکی تیکتۆک -----------------
    if is_blocked(user_id) or "tiktok.com" not in msg: return 
    
    if bot_settings_global["maintenance_mode"] and not is_admin(user_id):
        await update.message.reply_text("🛠 <b>بۆت لە باری چاکسازییە.</b>", parse_mode=ParseMode.HTML)
        return
    
    is_sub, _ = await check_user_subscription(user_id, context)
    if not is_sub and not is_admin(user_id) and not is_vip(user_id): 
        await update.message.reply_text("⚠️ تکایە سەرەتا جۆینی چەناڵەکان بکە (بنێرە /start)")
        return

    status_msg = await update.message.reply_text("<b>🔍 خەریکی پشکنینی لینکەکەم... چاوەڕێ بکە...</b>", parse_mode=ParseMode.HTML)
    
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            r = await client.get(API_URL + msg)
            res = r.json()
            if not res.get("ok"): 
                await status_msg.edit_text("<b>❌ ببورە، ڤیدیۆکە نەدۆزرایەوە یان پرایڤەتە!</b>", parse_mode=ParseMode.HTML)
                return
            
            video = res["data"]
            details = video["details"]
            images = details.get("images",[])
            
            await save_user_data(user_id, {"creator": video["creator"], "details": details})
            
            title = clean_title(details.get('title'))
            
            caption = (
                f"╔═══════════════════╗\n"
                f"   ✅ <b>بە سەرکەوتوویی دۆزرایەوە!</b>\n"
                f"╚═══════════════════╝\n\n"
                f"📝 <b>پۆست:</b> {html.escape(title)}\n"
                f"👤 <b>خاوەن:</b> {html.escape(video['creator'])}\n\n"
                f"📊 <b>ئامارەکانی پۆست:</b>\n"
                f"👁 <code>{format_number(details.get('views'))}</code> بینەر\n"
                f"❤️ <code>{format_number(details.get('like'))}</code> لایک\n"
                f"💬 <code>{format_number(details.get('comment'))}</code> کۆمێنت\n\n"
                f"👇 <b>تکایە فۆرماتێک هەڵبژێرە:</b>"
            )
            
            if images:
                kb = [[InlineKeyboardButton(f"📸 داونلۆدی وێنەکان ({len(images)})", callback_data="dl_photos")],[InlineKeyboardButton("🎵 داونلۆدی گۆرانی (MP3)", callback_data="dl_audio")], 
                    [InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]
                ]
            else:
                kb = [[InlineKeyboardButton("🎥 داونلۆدی ڤیدیۆ (بێ لۆگۆ)", callback_data="dl_video")],[InlineKeyboardButton("🎵 داونلۆدی گۆرانی (MP3)", callback_data="dl_audio")],[InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]
                ]
            
            await status_msg.edit_media(
                InputMediaPhoto(details["cover"]["cover"], caption=caption, parse_mode=ParseMode.HTML), 
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except Exception as e: 
            logger.error(f"Error fetching tiktok: {e}")
            await status_msg.edit_text("<b>❌ کێشەیەک ڕوویدا لە کاتی پەیوەندیکردن بە سێرڤەر.</b>", parse_mode=ParseMode.HTML)

# ==============================================================================
# ------------------------- ڕێکخستنی کۆتایی (INITIALIZATION) -------------------
# ==============================================================================

ptb_app = ApplicationBuilder().token(TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CommandHandler("help", help_command))
ptb_app.add_handler(CallbackQueryHandler(button_handler))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

@app.post("/api/main")
async def webhook(req: Request):
    if not ptb_app.running: 
        await ptb_app.initialize()
    # هێنانەوەی ڕێکخستنەکان لە داتابەیس بۆ دڵنیابوون لەوەی هیچی نەسڕاوەتەوە
    await load_settings()
    data = await req.json()
    await ptb_app.process_update(Update.de_json(data, ptb_app.bot))
    return {"ok": True, "message": "Pro Max Processed"}

@app.get("/api/main")
async def health(): 
    return {"status": "active", "bot_version": BOT_VERSION, "developer": DEVELOPER}
