# ==============================================================================
# ==============================================================================
# ==                                                                          ==
# ==                 TIKTOK DOWNLOADER - LEGENDARY EDITION v5.0               ==
# ==                                                                          ==
# ==   • Dev:         @j4ck_721s (﮼جــاڪ ,.⏳🤎)                               ==
# ==   • Version:     5.0 (Legendary)                                         ==
# ==   • Features:    Multi-Language, Super Admin Panel, VIP System & More    ==
# ==                                                                          ==
# ==============================================================================
# ==============================================================================

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
DEVELOPER_USERNAME = "@j4ck_721s"

# ==============================================================================
# ------------------------- گۆڕاوە گشتییەکان (GLOBALS) --------------------------
# ==============================================================================
admins_list = {OWNER_ID} 
forced_channels = []  
blocked_users = set()
vip_users = set()
bot_settings_global = {
    "maintenance_mode": False,
    "total_downloads": 0, "total_videos": 0,
    "total_audios": 0, "total_photos": 0
}

SESSION_EXPIRE = 600
API_TIMEOUT = 60
START_TIME = time.time()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()

# ==============================================================================
# ----------------------------- سیستەمی فرە-زمان (LANGUAGE) ----------------------
# ==============================================================================
LANGUAGES = {
    "ku": {
        "welcome_title": "👋 <b>سڵاو {name} {badge}</b>",
        "welcome_intro": "🤖 <b>من بۆتێکی پێشکەوتووم بۆ دابەزاندنی تیکتۆک!</b>",
        "welcome_features": "📥 دەتوانیت ڤیدیۆ و وێنەکان (Slideshow) دابەزێنیت.",
        "welcome_prompt": "👇 <b>لینک بنێرە یان دوگمە دابگرە:</b>",
        "btn_download": "📥 دابەزاندنی تیکتۆک", "btn_profile": "👤 پرۆفایلی من", "btn_vip": "💎 بەشی VIP",
        "btn_settings": "⚙️ ڕێکخستنەکان", "btn_help": "ℹ️ ڕێنمایی و یارمەتی", "btn_channel": "📢 کەناڵی فەرمی بۆت",
        "btn_admin_panel": "👑 پانێڵی پێشکەوتووی ئەدمین 👑",
        "force_join_text": "🔒 <b>جۆینی ناچاری</b>\nبۆ بەکارهێنان، تکایە جۆینی ئەم چەناڵانە بکە:",
        "btn_join_channel": "📢 جۆین کردن: {ch}", "btn_check_join": "✅ جۆینم کرد، دەستپێکردن",
        "help_title": "📚 <b>ڕێنمایی بەکارهێنان</b>",
        "help_text": "<b>چۆن دایبەزێنم؟</b>\n1️⃣ لە تیکتۆک 'Share' دابگرە و 'Copy Link' بکە.\n2️⃣ لینکەکە لێرە بنێرە وەک نامەیەک.",
        "download_prompt": "<b>🔗 تکایە لینکی تیکتۆکەکە لێرەدا پەیست بکە و بۆمی بنێرە:</b>",
        "profile_title": "👤 <b>پرۆفایلی بەکارهێنەر</b>", "profile_id": "🆔 <b>ئایدی:</b> <code>{id}</code>",
        "profile_name": "👤 <b>ناو:</b> {name}", "profile_vip_status": "💎 <b>هەژماری VIP:</b> {status}",
        "vip_yes": "بەڵێ 💎", "vip_no": "نەخێر (Free)",
        "download_found": "✅ <b>بە سەرکەوتوویی دۆزرایەوە!</b>",
        "download_title": "📝 <b>پۆست:</b> {title}", "download_owner": "👤 <b>خاوەن:</b> {owner}",
        "download_stats": "📊 <b>ئامارەکانی پۆست:</b>", "download_views": "👁 <code>{views}</code> بینەر",
        "download_likes": "❤️ <code>{likes}</code> لایک", "download_comments": "💬 <code>{comments}</code> کۆمێنت",
        "download_prompt_select": "👇 <b>تکایە فۆرماتێک هەڵبژێرە:</b>",
        "btn_video": "🎥 داونلۆدی ڤیدیۆ (بێ لۆگۆ)", "btn_photos": "📸 داونلۆدی وێنەکان ({count})",
        "btn_audio": "🎵 داونلۆدی گۆرانی (MP3)", "btn_delete": "🗑 سڕینەوە", "btn_back": "🔙 گەڕانەوە",
        "error_admin_only": "⛔ ئەم بەشە تەنیا بۆ ئەدمینەکانە!", "error_owner_only": "⛔ ئەم بەشە تەنیا بۆ خاوەنی سەرەکییە!",
        "error_blocked": "⛔ <b>ببورە، تۆ بلۆک کراویت.</b>", "error_maintenance": "🛠 <b>بۆتەکە لە باری چاکسازیدایە!</b>",
        "error_session_expired": "⚠️ کاتەکەت بەسەرچوو، تکایە لینکەکە دووبارە بنێرەوە.",
        "lang_select_title": "🌍 <b>زمان هەڵبژێرە | Select Language</b>", "lang_select_prompt": "تکایە زمانێک هەڵبژێرە:",
    },
    "en": {
        "welcome_title": "👋 <b>Welcome {name} {badge}</b>", "welcome_intro": "🤖 <b>I am an advanced bot for downloading TikToks!</b>",
        "welcome_features": "📥 You can download videos and slideshows.", "welcome_prompt": "👇 <b>Send a link or press a button:</b>",
        "btn_download": "📥 Download TikTok", "btn_profile": "👤 My Profile", "btn_vip": "💎 VIP Section",
        "btn_settings": "⚙️ Settings", "btn_help": "ℹ️ Help & Guide", "btn_channel": "📢 Official Bot Channel",
        "btn_admin_panel": "👑 Advanced Admin Panel 👑",
        "force_join_text": "🔒 <b>Forced Join</b>\nTo use the bot, please join these channels:", "btn_join_channel": "📢 Join: {ch}",
        "btn_check_join": "✅ I Have Joined, Start", "help_title": "📚 <b>How to Use</b>",
        "help_text": "<b>How do I download?</b>\n1️⃣ In TikTok, press 'Share' and then 'Copy Link'.\n2️⃣ Send the link here as a message.",
        "download_prompt": "<b>🔗 Please paste the TikTok link here and send it to me:</b>",
        "profile_title": "👤 <b>User Profile</b>", "profile_id": "🆔 <b>ID:</b> <code>{id}</code>", "profile_name": "👤 <b>Name:</b> {name}",
        "profile_vip_status": "💎 <b>VIP Account:</b> {status}", "vip_yes": "Yes 💎", "vip_no": "No (Free)",
        "download_found": "✅ <b>Successfully Found!</b>", "download_title": "📝 <b>Post:</b> {title}", "download_owner": "👤 <b>Owner:</b> {owner}",
        "download_stats": "📊 <b>Post Stats:</b>", "download_views": "👁 <code>{views}</code> Views", "download_likes": "❤️ <code>{likes}</code> Likes",
        "download_comments": "💬 <code>{comments}</code> Comments", "download_prompt_select": "👇 <b>Please select a format:</b>",
        "btn_video": "🎥 Download Video (No Watermark)", "btn_photos": "📸 Download Photos ({count})", "btn_audio": "🎵 Download Audio (MP3)",
        "btn_delete": "🗑 Delete", "btn_back": "🔙 Back",
        "error_admin_only": "⛔ This section is for admins only!", "error_owner_only": "⛔ This section is for the main owner only!",
        "error_blocked": "⛔ <b>Sorry, you have been blocked.</b>", "error_maintenance": "🛠 <b>The bot is in maintenance mode!</b>",
        "error_session_expired": "⚠️ Your session has expired, please send the link again.",
        "lang_select_title": "🌍 <b>Select Language | هەڵبژاردنی زمان</b>", "lang_select_prompt": "Please select a language:",
    },
    "ar": {
        "welcome_title": "👋 <b>أهلاً بك {name} {badge}</b>", "welcome_intro": "🤖 <b>أنا بوت متقدم لتحميل فيديوهات تيك توك!</b>",
        "welcome_features": "📥 يمكنك تحميل الفيديوهات وعروض الصور.", "welcome_prompt": "👇 <b>أرسل رابطًا أو اضغط على زر:</b>",
        "btn_download": "📥 تحميل من تيك توك", "btn_profile": "👤 ملفي الشخصي", "btn_vip": "💎 قسم VIP",
        "btn_settings": "⚙️ الإعدادات", "btn_help": "ℹ️ المساعدة والدليل", "btn_channel": "📢 قناة البوت الرسمية",
        "btn_admin_panel": "👑 لوحة تحكم الأدمن المتقدمة 👑",
        "force_join_text": "🔒 <b>الاشتراك الإجباري</b>\nلاستخدام البوت, يرجى الانضمام إلى هذه القنوات:", "btn_join_channel": "📢 انضمام: {ch}",
        "btn_check_join": "✅ لقد انضممت، إبدأ", "help_title": "📚 <b>كيفية الاستخدام</b>",
        "help_text": "<b>كيف أحمل؟</b>\n1️⃣ في تيك توك، اضغط على 'مشاركة' ثم 'نسخ الرابط'.\n2️⃣ أرسل الرابط هنا كرسالة.",
        "download_prompt": "<b>🔗 الرجاء لصق رابط تيك توك هنا وإرساله لي:</b>",
        "profile_title": "👤 <b>الملف الشخصي للمستخدم</b>", "profile_id": "🆔 <b>المعرف:</b> <code>{id}</code>", "profile_name": "👤 <b>الاسم:</b> {name}",
        "profile_vip_status": "💎 <b>حساب VIP:</b> {status}", "vip_yes": "نعم 💎", "vip_no": "لا (مجاني)",
        "download_found": "✅ <b>تم العثور عليه بنجاح!</b>", "download_title": "📝 <b>المنشور:</b> {title}", "download_owner": "👤 <b>المالك:</b> {owner}",
        "download_stats": "📊 <b>إحصائيات المنشور:</b>", "download_views": "👁 <code>{views}</code> مشاهدات", "download_likes": "❤️ <code>{likes}</code> إعجابات",
        "download_comments": "💬 <code>{comments}</code> تعليقات", "download_prompt_select": "👇 <b>الرجاء تحديد الصيغة:</b>",
        "btn_video": "🎥 تحميل الفيديو (بدون علامة مائية)", "btn_photos": "📸 تحميل الصور ({count})", "btn_audio": "🎵 تحميل الصوت (MP3)",
        "btn_delete": "🗑 حذف", "btn_back": "🔙 رجوع",
        "error_admin_only": "⛔ هذا القسم مخصص للمسؤولين فقط!", "error_owner_only": "⛔ هذا القسم مخصص للمالك الرئيسي فقط!",
        "error_blocked": "⛔ <b>عذراً، لقد تم حظرك.</b>", "error_maintenance": "🛠 <b>البوت في وضع الصيانة!</b>",
        "error_session_expired": "⚠️ انتهت صلاحية جلستك، يرجى إرسال الرابط مرة أخرى.",
        "lang_select_title": "🌍 <b>اختر اللغة | Select Language</b>", "lang_select_prompt": "الرجاء اختيار لغة:",
    }
}

async def get_user_lang(user_id):
    async with httpx.AsyncClient() as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}/language"))
            if r.status_code == 200 and r.json(): return r.json()
        except: pass
    return "ku"

def t(lang, key, **kwargs):
    text = LANGUAGES.get(lang, LANGUAGES["ku"]).get(key, key)
    return text.format(**kwargs)

# ==============================================================================
# ------------------------- فەنکشنە یارمەتیدەرەکان (HELPERS) ----------------------
# ==============================================================================

def get_random_id(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def clean_title(title):
    if not title: return "TikTok_Video"
    cleaned = re.sub(r'[\\/*?:"<>|]', '', title)
    return cleaned[:60]

def firebase_url(path: str):
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

def get_current_time():
    return datetime.now().strftime("%Y-%m-%d | %I:%M:%S %p")

def get_uptime():
    uptime_sec = int(time.time() - START_TIME)
    days, rem = divmod(uptime_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days} ڕۆژ و {hours} کاتژمێر و {minutes} خولەک"

# ==============================================================================
# ------------------------- پشکنینە ئەمنییەکان (SECURITY) -----------------------
# ==============================================================================

def is_owner(user_id): return user_id == OWNER_ID
def is_admin(user_id): return user_id in admins_list or user_id == OWNER_ID
def is_blocked(user_id): return user_id in blocked_users
def is_vip(user_id): return user_id in vip_users or is_owner(user_id)

async def check_user_subscription(user_id, context):
    if not forced_channels: return True, []
    not_joined =[]
    for channel in forced_channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                not_joined.append(channel)
        except: pass
    return len(not_joined) == 0, not_joined

# ==============================================================================
# ------------------------- کارەکانی داتابەیس (DATABASE CRUD) -------------------
# ==============================================================================

async def load_settings():
    global admins_list, forced_channels, blocked_users, vip_users, bot_settings_global
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(firebase_url("system_settings"))
            if r.status_code == 200 and r.json():
                data = r.json()
                admins_list = set(data.get("admins", [OWNER_ID]))
                forced_channels = data.get("channels", [])
                blocked_users = set(data.get("blocked",[]))
                vip_users = set(data.get("vips",[]))
                bot_settings_global.update(data.get("settings", {}))
                logger.info("✅ زانیارییەکان لە داتابەیسەوە هێنرانەوە.")
        except: logger.error("❌ هەڵە لە هێنانەوەی داتابەیس")

async def save_settings():
    settings = {
        "admins": list(admins_list), "channels": forced_channels,
        "blocked": list(blocked_users), "vips": list(vip_users),
        "settings": bot_settings_global
    }
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try: await c.put(firebase_url("system_settings"), json=settings)
        except: logger.error("❌ هەڵە لە سەیڤکردنی داتابەیس")

async def save_user_session_data(user_id: int, data: dict):
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient() as c: await c.put(firebase_url(f"user_sessions/{user_id}"), json=data)

async def is_user_exist(user_id: int):
    async with httpx.AsyncClient() as c:
        r = await c.get(firebase_url(f"registered_users/{user_id}"))
        return r.status_code == 200 and r.json() is not None

async def register_new_user(user_id: int, user_info: dict):
    async with httpx.AsyncClient() as c: await c.put(firebase_url(f"registered_users/{user_id}"), json=user_info)

async def get_user_session_data(user_id: int):
    async with httpx.AsyncClient() as c:
        r = await c.get(firebase_url(f"user_sessions/{user_id}"))
        if r.status_code == 200 and r.json() and int(time.time()) - r.json().get("timestamp", 0) <= SESSION_EXPIRE:
            return r.json()
        return None

async def notify_admin_new_user(context, user):
    msg = (f"🔔 <b>بەکارهێنەرێکی نوێ</b>\n\n👤 {html.escape(user.first_name)}\n🆔 <code>{user.id}</code>\n🔗 @{user.username or 'نییە'}")
    try: await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode=ParseMode.HTML)
    except: pass

# ==============================================================================
# ------------------------- فەرمانە سەرەکییەکان (COMMANDS) ----------------------
# ==============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name
    lang = await get_user_lang(user_id)
    
    if is_blocked(user_id):
        await update.message.reply_text(t(lang, "error_blocked"), parse_mode=ParseMode.HTML)
        return

    if bot_settings_global["maintenance_mode"] and not is_admin(user_id):
        await update.message.reply_text(t(lang, "error_maintenance"), parse_mode=ParseMode.HTML)
        return

    if not is_admin(user_id):
        user_exists = await is_user_exist(user_id)
        if not user_exists:
            asyncio.create_task(notify_admin_new_user(context, user))
            user_info = {
                "name": first_name, "username": user.username,
                "joined_date": get_current_time(), "is_vip": False, "language": "ku"
            }
            await register_new_user(user_id, user_info)

    is_sub, not_joined = await check_user_subscription(user_id, context)
    if not is_sub and not is_admin(user_id) and not is_vip(user_id):
        text = t(lang, "force_join_text")
        keyboard = [[InlineKeyboardButton(t(lang, "btn_join_channel", ch=ch), url=f"https://t.me/{ch.replace('@','')}") for ch in not_joined]]
        keyboard.append([InlineKeyboardButton(t(lang, "btn_check_join"), callback_data="check_sub_start")])
        if update.callback_query: await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        else: await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    badge_map = {"ku": "👑 خاوەن", "en": "👑 Owner", "ar": "👑 المالك"}
    badge = badge_map[lang] if is_owner(user_id) else ({"ku": "⚡ ئەدمین", "en": "⚡ Admin", "ar": "⚡ مسؤول"}[lang] if is_admin(user_id) else ({"ku": "💎 VIP", "en": "💎 VIP", "ar": "💎 VIP"}[lang] if is_vip(user_id) else ""))
    
    text = (
        f"╔═══════════════════╗\n"
        f"   {t(lang, 'welcome_title', name=html.escape(first_name), badge=badge)}\n"
        f"╚═══════════════════╝\n\n"
        f"{t(lang, 'welcome_intro')}\n"
        f"{t(lang, 'welcome_features')}\n\n"
        f"{t(lang, 'welcome_prompt')}"
    )
    
    keyboard = [
        [InlineKeyboardButton(t(lang, "btn_download"), callback_data="cmd_download")],
        [InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"), InlineKeyboardButton(t(lang, "btn_vip"), callback_data="menu_vip")],
        [InlineKeyboardButton(t(lang, "btn_settings"), callback_data="menu_settings"), InlineKeyboardButton(t(lang, "btn_help"), callback_data="cmd_help")],
        [InlineKeyboardButton(t(lang, "btn_channel"), url=CHANNEL_URL)]
    ]
    if is_admin(user_id): keyboard.append([InlineKeyboardButton(t(lang, "btn_admin_panel"), callback_data="admin_panel_main")])
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    text = f"╔═══════════════════╗\n   {t(lang, 'help_title')}\n╚═══════════════════╝\n\n{t(lang, 'help_text')}"
    if update.callback_query: await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, 'btn_back'), callback_data='cmd_start')]]))
    else: await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, 'btn_back'), callback_data='cmd_start')]]))

# ==============================================================================
# ------------------------- بەڕێوەبردنی کڵیکەکان (CALLBACK QUERY) ---------------
# ==============================================================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    lang = await get_user_lang(user_id)
    
    # ------------------ دوگمە بنەڕەتییەکان ------------------
    if data == "check_sub_start" or data == "cmd_start": await start_command(update, context); return
    elif data == "cmd_help": await help_command(update, context); return
    elif data == "cmd_download": await query.message.reply_text(t(lang, "download_prompt"), parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True)); return
    elif data == "close": await query.message.delete(); return

    # ------------------ مینیوی بەکارهێنەر ------------------
    if data == "menu_profile":
        text = (f"╔═══════════════════╗\n   {t(lang, 'profile_title')}\n╚═══════════════════╝\n\n"
                f"{t(lang, 'profile_id', id=user_id)}\n{t(lang, 'profile_name', name=html.escape(query.from_user.first_name))}\n"
                f"{t(lang, 'profile_vip_status', status=(t(lang, 'vip_yes') if is_vip(user_id) else t(lang, 'vip_no')))}")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, 'btn_back'), callback_data='cmd_start')]]))
        return
    elif data == "menu_vip":
        text = (f"╔═══════════════════╗\n   💎 <b>{t(lang, 'btn_vip')}</b>\n╚═══════════════════╝\n\n"
                f"بە کڕینی VIP، ئەم تایبەتمەندیانەت دەبێت:\n✅ خێرایی داونلۆدی زۆر زیاتر.\n✅ بێ ڕیکلام و بێ جۆین کردنی چەناڵ.\n✅ داونلۆدی بێسنوور بۆ وێنەکان.\n\n"
                f"💳 <b>بۆ کڕین پەیوەندی بکە بە:</b>\n{DEVELOPER_USERNAME}")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, 'btn_back'), callback_data='cmd_start')]]))
        return
    elif data == "menu_settings":
        text = f"🌍 <b>{t(lang, 'lang_select_title')}</b>\n\n{t(lang, 'lang_select_prompt')}"
        kb = [[InlineKeyboardButton("🔴🔆🟢 کوردی", callback_data="set_lang_ku")], [InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")], [InlineKeyboardButton("🇸🇦 العربية", callback_data="set_lang_ar")]]
        kb.append([InlineKeyboardButton(t(lang, "btn_back"), callback_data="cmd_start")])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return
    elif data.startswith("set_lang_"):
        new_lang = data.split("_")[2]
        async with httpx.AsyncClient() as c: await c.put(firebase_url(f"registered_users/{user_id}/language"), json=new_lang)
        await query.answer(f"Language set to {new_lang.upper()}!", show_alert=True)
        await start_command(update, context)
        return

    # ------------------ بەشی داونلۆد و پرۆسێس ------------------
    if data.startswith("dl_"):
        action = data.split("_")[1]
        user_data = await get_user_session_data(user_id)
        if not user_data: await query.answer(t(lang, "error_session_expired"), show_alert=True); return
        
        d = user_data["details"]; creator = user_data["creator"]; title = clean_title(d.get('title', '')); images = d.get("images", [])
        caption = (f"🎬 <b>{html.escape(title)}</b>\n👤 <b>{html.escape(creator)}</b>\n\n🤖 <b>@{context.bot.username}</b>")
        
        try:
            if action == "photos" or (action == "video" and images):
                await query.answer("⏳ ...", show_alert=False)
                if not images: await query.answer("❌ ...", show_alert=True); return
                bot_settings_global["total_downloads"] += 1; bot_settings_global["total_photos"] += 1; await save_settings()
                media_group =[InputMediaPhoto(media=img) for img in images[:10]]
                media_group[0].caption = caption; media_group[0].parse_mode = ParseMode.HTML
                await query.message.delete()
                await context.bot.send_media_group(chat_id=user_id, media=media_group)
            elif action == "video":
                await query.answer("⏳ ...", show_alert=False)
                bot_settings_global["total_downloads"] += 1; bot_settings_global["total_videos"] += 1; await save_settings()
                await query.message.edit_media(InputMediaVideo(media=d["video"]["play"], caption=caption, parse_mode=ParseMode.HTML), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, 'btn_delete'), callback_data='close')]]))
            elif action == "audio":
                await query.answer("⏳ ...", show_alert=False)
                bot_settings_global["total_downloads"] += 1; bot_settings_global["total_audios"] += 1; await save_settings()
                music_name = f"{DEVELOPER_USERNAME}-{get_random_id()}"
                await query.message.edit_media(InputMediaAudio(media=d["audio"]["play"], caption=caption, parse_mode=ParseMode.HTML, title=music_name, performer=DEVELOPER_USERNAME), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, 'btn_delete'), callback_data='close')]]))
        except:
            link_to_send = d["video"]["play"] if not images else images[0]
            await query.message.edit_caption(f"⚠️ <b>هەڵەیەک ڕوویدا، دایبەزێنە: <a href='{link_to_send}'>لێرە</a></b>", parse_mode=ParseMode.HTML)
        return

    # ==========================================================================
    # ------------------------- پانێڵی پێشکەوتووی ئەدمین -------------------------
    # ==========================================================================
    if not is_admin(user_id): await query.answer(t(lang, "error_admin_only"), show_alert=True); return

    if data == "admin_panel_main":
        await query.edit_message_text("👑 <b>پانێڵی کۆنترۆڵی سەرەکی</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 ئاماری گشتی", callback_data="admin_stats_full"), InlineKeyboardButton("📢 برۆدکاست", callback_data="admin_broadcast_ask")],
            [InlineKeyboardButton("📢 بەڕێوەبردنی چەناڵ", callback_data="manage_channels_menu"), InlineKeyboardButton("🚫 بلۆککردن", callback_data="manage_blocks_menu")],
            [InlineKeyboardButton("💎 بەڕێوەبردنی VIP", callback_data="manage_vips_menu"), InlineKeyboardButton("⚙️ دۆخی چاکسازی", callback_data="admin_toggle_maintenance")],
            [InlineKeyboardButton("👥 بەڕێوەبردنی ئەدمین", callback_data="manage_admins_menu")],
            [InlineKeyboardButton(t(lang, "btn_back"), callback_data="cmd_start")]
        ]))
    
    elif data == "admin_stats_full":
        text = (f"╔═══════════════════╗\n   📊 <b>ئاماری پێشکەوتووی بۆت</b>\n╚═══════════════════╝\n\n"
                f"👥 <b>دەسەڵاتەکان:</b>\n├ ئەدمین: {len(admins_list)}\n├ VIP: {len(vip_users)}\n├ چەناڵ: {len(forced_channels)}\n└ بلۆک: {len(blocked_users)}\n\n"
                f"📈 <b>داونلۆدەکان:</b>\n├ گشتی: {bot_settings_global['total_downloads']}\n├ ڤیدیۆ: {bot_settings_global['total_videos']}\n├ گۆرانی: {bot_settings_global['total_audios']}\n└ وێنە: {bot_settings_global['total_photos']}\n\n"
                f"⚙️ <b>سیستەم:</b>\n├ دۆخی چاکسازی: {'بەڵێ 🔴' if bot_settings_global['maintenance_mode'] else 'نەخێر 🟢'}\n├ کاتی کارکردن: {get_uptime()}\n\n🕐 {get_current_time()}")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, 'btn_back'), callback_data='admin_panel_main')]]))
    
    # ... (کۆدی پانێڵەکانی تر لێرە بەردەوام دەبێت)

# ==============================================================================
# --------------------- وەرگرتنی نامە و ڕیپلەی (MESSAGE HANDLER) ------------------
# ==============================================================================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text: return
    user_id = update.effective_user.id
    msg = update.message.text.strip()
    lang = await get_user_lang(user_id)
    
    if update.message.reply_to_message and is_admin(user_id):
        # ... (کۆدی ڕیپلەی ئەدمین لێرە دادەنرێت)
        pass

    if is_blocked(user_id) or "tiktok.com" not in msg: return 
    
    if bot_settings_global["maintenance_mode"] and not is_admin(user_id):
        await update.message.reply_text(t(lang, "error_maintenance"), parse_mode=ParseMode.HTML)
        return
    
    is_sub, _ = await check_user_subscription(user_id, context)
    if not is_sub and not is_admin(user_id) and not is_vip(user_id): 
        await update.message.reply_text("⚠️ تکایە جۆینی چەناڵەکان بکە (/start)"); return

    status_msg = await update.message.reply_text("<b>🔍 ...</b>", parse_mode=ParseMode.HTML)
    
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(API_URL + msg); res = r.json()
            if not res.get("ok"): await status_msg.edit_text("❌ ...!"); return
            
            video = res["data"]; details = video["details"]; images = details.get("images", [])
            await save_user_session_data(user_id, {"creator": video["creator"], "details": details})
            
            caption = (f"✅ <b>{t(lang, 'download_found')}</b>\n\n📝 <b>{t(lang, 'download_title', title=html.escape(clean_title(details.get('title'))))}</b>\n"
                       f"👤 <b>{t(lang, 'download_owner', owner=html.escape(video['creator']))}</b>")
            
            if images:
                kb = [[InlineKeyboardButton(t(lang, "btn_photos", count=len(images)), callback_data="dl_photos")], [InlineKeyboardButton(t(lang, "btn_audio"), callback_data="dl_audio")], [InlineKeyboardButton(t(lang, "btn_delete"), callback_data="close")]]
            else:
                kb = [[InlineKeyboardButton(t(lang, "btn_video"), callback_data="dl_video")], [InlineKeyboardButton(t(lang, "btn_audio"), callback_data="dl_audio")], [InlineKeyboardButton(t(lang, "btn_delete"), callback_data="close")]]
            
            await status_msg.edit_media(InputMediaPhoto(details["cover"]["cover"], caption=caption, parse_mode=ParseMode.HTML), reply_markup=InlineKeyboardMarkup(kb))
        except: await status_msg.edit_text("❌ ...")

# ==============================================================================
# ------------------------- ڕێکخستنی کۆتایی (INITIALIZATION) -------------------
# ==============================================================================
ptb_app = ApplicationBuilder().token(TOKEN).build()
ptb_app.add_handler(CommandHandler(["start", "menu"], start_command))
ptb_app.add_handler(CommandHandler("help", help_command))
ptb_app.add_handler(CallbackQueryHandler(button_handler))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

@app.post("/api/main")
async def webhook(req: Request):
    if not ptb_app.running: await ptb_app.initialize()
    await load_settings()
    data = await req.json()
    await ptb_app.process_update(Update.de_json(data, ptb_app.bot))
    return {"ok": True}

@app.get("/api/main")
async def health(): return {"status": "active"}
