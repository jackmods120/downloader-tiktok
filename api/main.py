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
TOKEN       = os.getenv("BOT_TOKEN")
API_URL     = "https://www.api.hyper-bd.site/Tiktok/?url="
CHANNEL_URL = "https://t.me/jack_721_mod"
DB_URL      = os.getenv("DB_URL")
DB_SECRET   = os.getenv("DB_SECRET")

# زانیاری خاوەنی سەرەکی
OWNER_ID             = 5977475208
DEVELOPER_USERNAME   = "@j4ck_721s"

# ==============================================================================
# ------------------------- گۆڕاوە گشتییەکان (GLOBALS) --------------------------
# ==============================================================================
admins_list        : set  = {OWNER_ID}
forced_channels    : list = []
blocked_users      : set  = set()
vip_users          : set  = set()
bot_settings_global: dict = {
    "maintenance_mode" : False,
    "total_downloads"  : 0,
    "total_videos"     : 0,
    "total_audios"     : 0,
    "total_photos"     : 0,
}

# کاتی session و API
SESSION_EXPIRE = 600
API_TIMEOUT    = 60
START_TIME     = time.time()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app    = FastAPI()

# ==============================================================================
# ----------------------------- سیستەمی فرە-زمان (LANGUAGE) ----------------------
# ==============================================================================
LANGUAGES = {
    "ku": {
        "welcome_title"        : "👋 <b>سڵاو {name} {badge}</b>",
        "welcome_intro"        : "🤖 <b>من بۆتێکی پێشکەوتووم بۆ دابەزاندنی تیکتۆک!</b>",
        "welcome_features"     : "📥 دەتوانیت ڤیدیۆ و وێنەکان (Slideshow) دابەزێنیت.",
        "welcome_prompt"       : "👇 <b>لینک بنێرە یان دوگمە دابگرە:</b>",
        "btn_download"         : "📥 دابەزاندنی تیکتۆک",
        "btn_profile"          : "👤 پرۆفایلی من",
        "btn_vip"              : "💎 بەشی VIP",
        "btn_settings"         : "⚙️ ڕێکخستنەکان",
        "btn_help"             : "ℹ️ ڕێنمایی و یارمەتی",
        "btn_channel"          : "📢 کەناڵی فەرمی بۆت",
        "btn_admin_panel"      : "👑 پانێڵی پێشکەوتووی ئەدمین 👑",
        "force_join_text"      : "🔒 <b>جۆینی ناچاری</b>\nبۆ بەکارهێنان، تکایە جۆینی ئەم چەناڵانە بکە:",
        "btn_join_channel"     : "📢 جۆین کردن: {ch}",
        "btn_check_join"       : "✅ جۆینم کرد، دەستپێکردن",
        "help_title"           : "📚 <b>ڕێنمایی بەکارهێنان</b>",
        "help_text"            : "<b>چۆن دایبەزێنم؟</b>\n1️⃣ لە تیکتۆک 'Share' دابگرە و 'Copy Link' بکە.\n2️⃣ لینکەکە لێرە بنێرە وەک نامەیەک.",
        "download_prompt"      : "<b>🔗 تکایە لینکی تیکتۆکەکە لێرەدا پەیست بکە و بۆمی بنێرە:</b>",
        "profile_title"        : "👤 <b>پرۆفایلی بەکارهێنەر</b>",
        "profile_id"           : "🆔 <b>ئایدی:</b> <code>{id}</code>",
        "profile_name"         : "👤 <b>ناو:</b> {name}",
        "profile_vip_status"   : "💎 <b>هەژماری VIP:</b> {status}",
        "vip_yes"              : "بەڵێ 💎",
        "vip_no"               : "نەخێر (Free)",
        "download_found"       : "✅ <b>بە سەرکەوتوویی دۆزرایەوە!</b>",
        "download_title"       : "📝 <b>پۆست:</b> {title}",
        "download_owner"       : "👤 <b>خاوەن:</b> {owner}",
        "download_stats"       : "📊 <b>ئامارەکانی پۆست:</b>",
        "download_views"       : "👁 <code>{views}</code> بینەر",
        "download_likes"       : "❤️ <code>{likes}</code> لایک",
        "download_comments"    : "💬 <code>{comments}</code> کۆمێنت",
        "download_prompt_select": "👇 <b>تکایە فۆرماتێک هەڵبژێرە:</b>",
        "btn_video"            : "🎥 داونلۆدی ڤیدیۆ (بێ لۆگۆ)",
        "btn_photos"           : "📸 داونلۆدی وێنەکان ({count})",
        "btn_audio"            : "🎵 داونلۆدی گۆرانی (MP3)",
        "btn_delete"           : "🗑 سڕینەوە",
        "btn_back"             : "🔙 گەڕانەوە",
        "error_admin_only"     : "⛔ ئەم بەشە تەنیا بۆ ئەدمینەکانە!",
        "error_owner_only"     : "⛔ ئەم بەشە تەنیا بۆ خاوەنی سەرەکییە!",
        "error_blocked"        : "⛔ <b>ببورە، تۆ بلۆک کراویت.</b>",
        "error_maintenance"    : "🛠 <b>بۆتەکە لە باری چاکسازیدایە!</b>",
        "error_session_expired": "⚠️ کاتەکەت بەسەرچوو، تکایە لینکەکە دووبارە بنێرەوە.",
        "lang_select_title"    : "🌍 <b>زمان هەڵبژێرە | Select Language</b>",
        "lang_select_prompt"   : "تکایە زمانێک هەڵبژێرە:",
        "no_users_found"       : "📭 هیچ بەکارهێنەرێک نەدۆزرایەوە.",
        "broadcast_sent"       : "📢 <b>برۆدکاست ئەنجامدرا!</b>\n✅ گەیشت بە: {success}\n❌ نەگەیشت: {fail}",
        "admin_added"          : "✅ ئەدمینی نوێ زیادکرا: <code>{id}</code>",
        "admin_removed"        : "✅ ئەدمین لابرا: <code>{id}</code>",
        "vip_added"            : "✅ VIP زیادکرا: <code>{id}</code>",
        "vip_removed"          : "✅ VIP لابرا: <code>{id}</code>",
        "user_blocked"         : "✅ بەکارهێنەر بلۆک کرا: <code>{id}</code>",
        "user_unblocked"       : "✅ بلۆکی بەکارهێنەر لادرا: <code>{id}</code>",
        "channel_added"        : "✅ چەناڵ زیادکرا: {ch}",
        "channel_removed"      : "✅ چەناڵ لابرا: {ch}",
        "invalid_id"           : "❌ ئایدی دروست نییە. ئایدیەکی ژمارەیی بنێرە.",
        "send_user_id"         : "🆔 تکایە ئایدی بەکارهێنەرەکە بنێرە:",
        "send_channel"         : "📢 تکایە یوزەرنەیمی چەناڵەکە بنێرە (بە @ دەستپێدەکات):",
        "send_broadcast_msg"   : "📢 تکایە نامەکە بنێرە:",
        "not_owner"            : "⛔ تەنیا خاوەن دەتوانێت ئەم کارە بکات!",
    },
    "en": {
        "welcome_title"        : "👋 <b>Welcome {name} {badge}</b>",
        "welcome_intro"        : "🤖 <b>I am an advanced bot for downloading TikToks!</b>",
        "welcome_features"     : "📥 You can download videos and slideshows.",
        "welcome_prompt"       : "👇 <b>Send a link or press a button:</b>",
        "btn_download"         : "📥 Download TikTok",
        "btn_profile"          : "👤 My Profile",
        "btn_vip"              : "💎 VIP Section",
        "btn_settings"         : "⚙️ Settings",
        "btn_help"             : "ℹ️ Help & Guide",
        "btn_channel"          : "📢 Official Bot Channel",
        "btn_admin_panel"      : "👑 Advanced Admin Panel 👑",
        "force_join_text"      : "🔒 <b>Forced Join</b>\nTo use the bot, please join these channels:",
        "btn_join_channel"     : "📢 Join: {ch}",
        "btn_check_join"       : "✅ I Have Joined, Start",
        "help_title"           : "📚 <b>How to Use</b>",
        "help_text"            : "<b>How do I download?</b>\n1️⃣ In TikTok, press 'Share' and then 'Copy Link'.\n2️⃣ Send the link here as a message.",
        "download_prompt"      : "<b>🔗 Please paste the TikTok link here and send it to me:</b>",
        "profile_title"        : "👤 <b>User Profile</b>",
        "profile_id"           : "🆔 <b>ID:</b> <code>{id}</code>",
        "profile_name"         : "👤 <b>Name:</b> {name}",
        "profile_vip_status"   : "💎 <b>VIP Account:</b> {status}",
        "vip_yes"              : "Yes 💎",
        "vip_no"               : "No (Free)",
        "download_found"       : "✅ <b>Successfully Found!</b>",
        "download_title"       : "📝 <b>Post:</b> {title}",
        "download_owner"       : "👤 <b>Owner:</b> {owner}",
        "download_stats"       : "📊 <b>Post Stats:</b>",
        "download_views"       : "👁 <code>{views}</code> Views",
        "download_likes"       : "❤️ <code>{likes}</code> Likes",
        "download_comments"    : "💬 <code>{comments}</code> Comments",
        "download_prompt_select": "👇 <b>Please select a format:</b>",
        "btn_video"            : "🎥 Download Video (No Watermark)",
        "btn_photos"           : "📸 Download Photos ({count})",
        "btn_audio"            : "🎵 Download Audio (MP3)",
        "btn_delete"           : "🗑 Delete",
        "btn_back"             : "🔙 Back",
        "error_admin_only"     : "⛔ This section is for admins only!",
        "error_owner_only"     : "⛔ This section is for the main owner only!",
        "error_blocked"        : "⛔ <b>Sorry, you have been blocked.</b>",
        "error_maintenance"    : "🛠 <b>The bot is in maintenance mode!</b>",
        "error_session_expired": "⚠️ Your session has expired, please send the link again.",
        "lang_select_title"    : "🌍 <b>Select Language | هەڵبژاردنی زمان</b>",
        "lang_select_prompt"   : "Please select a language:",
        "no_users_found"       : "📭 No users found.",
        "broadcast_sent"       : "📢 <b>Broadcast Done!</b>\n✅ Sent: {success}\n❌ Failed: {fail}",
        "admin_added"          : "✅ New admin added: <code>{id}</code>",
        "admin_removed"        : "✅ Admin removed: <code>{id}</code>",
        "vip_added"            : "✅ VIP added: <code>{id}</code>",
        "vip_removed"          : "✅ VIP removed: <code>{id}</code>",
        "user_blocked"         : "✅ User blocked: <code>{id}</code>",
        "user_unblocked"       : "✅ User unblocked: <code>{id}</code>",
        "channel_added"        : "✅ Channel added: {ch}",
        "channel_removed"      : "✅ Channel removed: {ch}",
        "invalid_id"           : "❌ Invalid ID. Please send a numeric ID.",
        "send_user_id"         : "🆔 Please send the user's ID:",
        "send_channel"         : "📢 Please send the channel username (starts with @):",
        "send_broadcast_msg"   : "📢 Please send your broadcast message:",
        "not_owner"            : "⛔ Only the owner can do this!",
    },
    "ar": {
        "welcome_title"        : "👋 <b>أهلاً بك {name} {badge}</b>",
        "welcome_intro"        : "🤖 <b>أنا بوت متقدم لتحميل فيديوهات تيك توك!</b>",
        "welcome_features"     : "📥 يمكنك تحميل الفيديوهات وعروض الصور.",
        "welcome_prompt"       : "👇 <b>أرسل رابطًا أو اضغط على زر:</b>",
        "btn_download"         : "📥 تحميل من تيك توك",
        "btn_profile"          : "👤 ملفي الشخصي",
        "btn_vip"              : "💎 قسم VIP",
        "btn_settings"         : "⚙️ الإعدادات",
        "btn_help"             : "ℹ️ المساعدة والدليل",
        "btn_channel"          : "📢 قناة البوت الرسمية",
        "btn_admin_panel"      : "👑 لوحة تحكم الأدمن المتقدمة 👑",
        "force_join_text"      : "🔒 <b>الاشتراك الإجباري</b>\nلاستخدام البوت, يرجى الانضمام إلى هذه القنوات:",
        "btn_join_channel"     : "📢 انضمام: {ch}",
        "btn_check_join"       : "✅ لقد انضممت، إبدأ",
        "help_title"           : "📚 <b>كيفية الاستخدام</b>",
        "help_text"            : "<b>كيف أحمل؟</b>\n1️⃣ في تيك توك، اضغط على 'مشاركة' ثم 'نسخ الرابط'.\n2️⃣ أرسل الرابط هنا كرسالة.",
        "download_prompt"      : "<b>🔗 الرجاء لصق رابط تيك توك هنا وإرساله لي:</b>",
        "profile_title"        : "👤 <b>الملف الشخصي للمستخدم</b>",
        "profile_id"           : "🆔 <b>المعرف:</b> <code>{id}</code>",
        "profile_name"         : "👤 <b>الاسم:</b> {name}",
        "profile_vip_status"   : "💎 <b>حساب VIP:</b> {status}",
        "vip_yes"              : "نعم 💎",
        "vip_no"               : "لا (مجاني)",
        "download_found"       : "✅ <b>تم العثور عليه بنجاح!</b>",
        "download_title"       : "📝 <b>المنشور:</b> {title}",
        "download_owner"       : "👤 <b>المالك:</b> {owner}",
        "download_stats"       : "📊 <b>إحصائيات المنشور:</b>",
        "download_views"       : "👁 <code>{views}</code> مشاهدات",
        "download_likes"       : "❤️ <code>{likes}</code> إعجابات",
        "download_comments"    : "💬 <code>{comments}</code> تعليقات",
        "download_prompt_select": "👇 <b>الرجاء تحديد الصيغة:</b>",
        "btn_video"            : "🎥 تحميل الفيديو (بدون علامة مائية)",
        "btn_photos"           : "📸 تحميل الصور ({count})",
        "btn_audio"            : "🎵 تحميل الصوت (MP3)",
        "btn_delete"           : "🗑 حذف",
        "btn_back"             : "🔙 رجوع",
        "error_admin_only"     : "⛔ هذا القسم مخصص للمسؤولين فقط!",
        "error_owner_only"     : "⛔ هذا القسم مخصص للمالك الرئيسي فقط!",
        "error_blocked"        : "⛔ <b>عذراً، لقد تم حظرك.</b>",
        "error_maintenance"    : "🛠 <b>البوت في وضع الصيانة!</b>",
        "error_session_expired": "⚠️ انتهت صلاحية جلستك، يرجى إرسال الرابط مرة أخرى.",
        "lang_select_title"    : "🌍 <b>اختر اللغة | Select Language</b>",
        "lang_select_prompt"   : "الرجاء اختيار لغة:",
        "no_users_found"       : "📭 لم يتم العثور على أي مستخدم.",
        "broadcast_sent"       : "📢 <b>تم الإرسال الجماعي!</b>\n✅ تم الإرسال: {success}\n❌ فشل: {fail}",
        "admin_added"          : "✅ تمت إضافة مسؤول جديد: <code>{id}</code>",
        "admin_removed"        : "✅ تمت إزالة المسؤول: <code>{id}</code>",
        "vip_added"            : "✅ تمت إضافة VIP: <code>{id}</code>",
        "vip_removed"          : "✅ تمت إزالة VIP: <code>{id}</code>",
        "user_blocked"         : "✅ تم حظر المستخدم: <code>{id}</code>",
        "user_unblocked"       : "✅ تم رفع الحظر عن المستخدم: <code>{id}</code>",
        "channel_added"        : "✅ تمت إضافة القناة: {ch}",
        "channel_removed"      : "✅ تمت إزالة القناة: {ch}",
        "invalid_id"           : "❌ معرف غير صالح. يرجى إرسال معرف رقمي.",
        "send_user_id"         : "🆔 يرجى إرسال معرف المستخدم:",
        "send_channel"         : "📢 يرجى إرسال اسم مستخدم القناة (يبدأ بـ @):",
        "send_broadcast_msg"   : "📢 يرجى إرسال رسالتك:",
        "not_owner"            : "⛔ فقط المالك يمكنه فعل هذا!",
    }
}

async def get_user_lang(user_id: int) -> str:
    async with httpx.AsyncClient() as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}/language"))
            if r.status_code == 200 and r.json():
                return r.json()
        except:
            pass
    return "ku"

def t(lang: str, key: str, **kwargs) -> str:
    text = LANGUAGES.get(lang, LANGUAGES["ku"]).get(key, key)
    return text.format(**kwargs)

# ==============================================================================
# ------------------------- فەنکشنە یارمەتیدەرەکان (HELPERS) ----------------------
# ==============================================================================

def get_random_id(length: int = 6) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def clean_title(title: str) -> str:
    if not title:
        return "TikTok_Video"
    cleaned = re.sub(r'[\\/*?:"<>|]', '', title)
    return cleaned[:60]

def firebase_url(path: str) -> str:
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d | %I:%M:%S %p")

def get_uptime() -> str:
    uptime_sec = int(time.time() - START_TIME)
    days, rem     = divmod(uptime_sec, 86400)
    hours, rem    = divmod(rem, 3600)
    minutes, _    = divmod(rem, 60)
    return f"{days} ڕۆژ و {hours} کاتژمێر و {minutes} خولەک"

def back_btn(lang: str, target: str = "cmd_start") -> list:
    return [[InlineKeyboardButton(t(lang, "btn_back"), callback_data=target)]]

# ==============================================================================
# ------------------------- پشکنینە ئەمنییەکان (SECURITY) -----------------------
# ==============================================================================

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_admin(user_id: int) -> bool:
    return user_id in admins_list or user_id == OWNER_ID

def is_blocked(user_id: int) -> bool:
    return user_id in blocked_users

def is_vip(user_id: int) -> bool:
    return user_id in vip_users or is_owner(user_id)

async def check_user_subscription(user_id: int, context) -> tuple[bool, list]:
    if not forced_channels:
        return True, []
    not_joined = []
    for channel in forced_channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                not_joined.append(channel)
        except:
            pass
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
                admins_list        = set(data.get("admins",   [OWNER_ID]))
                forced_channels    = data.get("channels",     [])
                blocked_users      = set(data.get("blocked",  []))
                vip_users          = set(data.get("vips",     []))
                bot_settings_global.update(data.get("settings", {}))
                logger.info("✅ زانیارییەکان لە داتابەیسەوە هێنرانەوە.")
        except Exception as e:
            logger.error(f"❌ هەڵە لە هێنانەوەی داتابەیس: {e}")

async def save_settings():
    settings_data = {
        "admins"  : list(admins_list),
        "channels": forced_channels,
        "blocked" : list(blocked_users),
        "vips"    : list(vip_users),
        "settings": bot_settings_global,
    }
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            await c.put(firebase_url("system_settings"), json=settings_data)
        except Exception as e:
            logger.error(f"❌ هەڵە لە سەیڤکردنی داتابەیس: {e}")

async def save_user_session_data(user_id: int, data: dict):
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        await c.put(firebase_url(f"user_sessions/{user_id}"), json=data)

async def is_user_exist(user_id: int) -> bool:
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        r = await c.get(firebase_url(f"registered_users/{user_id}"))
        return r.status_code == 200 and r.json() is not None

async def register_new_user(user_id: int, user_info: dict):
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        await c.put(firebase_url(f"registered_users/{user_id}"), json=user_info)

async def get_user_session_data(user_id: int) -> dict | None:
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        r = await c.get(firebase_url(f"user_sessions/{user_id}"))
        if r.status_code == 200 and r.json():
            data = r.json()
            if int(time.time()) - data.get("timestamp", 0) <= SESSION_EXPIRE:
                return data
    return None

async def get_all_registered_users() -> list[int]:
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(firebase_url("registered_users"))
            if r.status_code == 200 and r.json():
                return [int(uid) for uid in r.json().keys()]
        except:
            pass
    return []

async def notify_admin_new_user(context, user):
    msg = (
        f"🔔 <b>بەکارهێنەرێکی نوێ تۆمار کرا!</b>\n\n"
        f"👤 <b>ناو:</b> {html.escape(user.first_name)}\n"
        f"🆔 <b>ئایدی:</b> <code>{user.id}</code>\n"
        f"🔗 <b>یوزەرنەیم:</b> @{user.username or '—'}"
    )
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ==============================================================================
# -------------------------- یارمەتی پانێڵی ئەدمین (ADMIN STATE) ----------------
# ==============================================================================
# بۆ هەڵگرتنی دۆخی چاوەڕوانی کردنی نامەکانی ئەدمین
admin_waiting_state: dict[int, str] = {}

# ==============================================================================
# ------------------------- فەرمانە سەرەکییەکان (COMMANDS) ----------------------
# ==============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    user_id = user.id
    lang    = await get_user_lang(user_id)

    if is_blocked(user_id):
        msg = t(lang, "error_blocked")
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return

    if bot_settings_global["maintenance_mode"] and not is_admin(user_id):
        msg = t(lang, "error_maintenance")
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return

    if not is_admin(user_id):
        user_exists = await is_user_exist(user_id)
        if not user_exists:
            asyncio.create_task(notify_admin_new_user(context, user))
            user_info = {
                "name"       : user.first_name,
                "username"   : user.username,
                "joined_date": get_current_time(),
                "is_vip"     : False,
                "language"   : "ku",
            }
            await register_new_user(user_id, user_info)

    is_sub, not_joined = await check_user_subscription(user_id, context)
    if not is_sub and not is_admin(user_id) and not is_vip(user_id):
        text     = t(lang, "force_join_text")
        keyboard = [
            [InlineKeyboardButton(t(lang, "btn_join_channel", ch=ch), url=f"https://t.me/{ch.replace('@','')}")
             for ch in not_joined]
        ]
        keyboard.append([InlineKeyboardButton(t(lang, "btn_check_join"), callback_data="check_sub_start")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        return

    # badge بەرپرسی بژاردن
    owner_badges = {"ku": "👑 خاوەن",    "en": "👑 Owner",  "ar": "👑 المالك"}
    admin_badges = {"ku": "⚡ ئەدمین",   "en": "⚡ Admin",  "ar": "⚡ مسؤول"}
    vip_badges   = {"ku": "💎 VIP",      "en": "💎 VIP",    "ar": "💎 VIP"}
    badge = (
        owner_badges.get(lang, "👑 Owner") if is_owner(user_id) else
        admin_badges.get(lang, "⚡ Admin") if is_admin(user_id) else
        vip_badges.get(lang, "💎 VIP")     if is_vip(user_id)   else ""
    )

    text = (
        f"╔═══════════════════╗\n"
        f"   {t(lang, 'welcome_title', name=html.escape(user.first_name), badge=badge)}\n"
        f"╚═══════════════════╝\n\n"
        f"{t(lang, 'welcome_intro')}\n"
        f"{t(lang, 'welcome_features')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{t(lang, 'welcome_prompt')}"
    )

    keyboard = [
        [InlineKeyboardButton(t(lang, "btn_download"), callback_data="cmd_download")],
        [
            InlineKeyboardButton(t(lang, "btn_profile"),  callback_data="menu_profile"),
            InlineKeyboardButton(t(lang, "btn_vip"),      callback_data="menu_vip"),
        ],
        [
            InlineKeyboardButton(t(lang, "btn_settings"), callback_data="menu_settings"),
            InlineKeyboardButton(t(lang, "btn_help"),     callback_data="cmd_help"),
        ],
        [InlineKeyboardButton(t(lang, "btn_channel"),     url=CHANNEL_URL)],
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton(t(lang, "btn_admin_panel"), callback_data="admin_panel_main")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_user_lang(update.effective_user.id)
    text = (
        f"╔═══════════════════╗\n"
        f"   {t(lang, 'help_title')}\n"
        f"╚═══════════════════╝\n\n"
        f"{t(lang, 'help_text')}"
    )
    reply_markup = InlineKeyboardMarkup(back_btn(lang))
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

# ==============================================================================
# ------------------------- بەڕێوەبردنی کڵیکەکان (CALLBACK QUERY) ---------------
# ==============================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    data    = query.data
    user_id = query.from_user.id
    lang    = await get_user_lang(user_id)
    await query.answer()

    # دووبارەدەستپێکردن / یارمەتی / چاودێری جۆین
    if data in ("check_sub_start", "cmd_start"):
        await start_command(update, context); return
    if data == "cmd_help":
        await help_command(update, context); return
    if data == "cmd_download":
        await query.message.reply_text(
            t(lang, "download_prompt"), parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        ); return
    if data == "close":
        await query.message.delete(); return

    # ─── پرۆفایل ─────────────────────────────────────────────────────────────
    if data == "menu_profile":
        vip_status = t(lang, "vip_yes") if is_vip(user_id) else t(lang, "vip_no")
        text = (
            f"╔═══════════════════╗\n"
            f"   {t(lang, 'profile_title')}\n"
            f"╚═══════════════════╝\n\n"
            f"{t(lang, 'profile_id',         id=user_id)}\n"
            f"{t(lang, 'profile_name',       name=html.escape(query.from_user.first_name))}\n"
            f"{t(lang, 'profile_vip_status', status=vip_status)}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(back_btn(lang))); return

    # ─── VIP ──────────────────────────────────────────────────────────────────
    if data == "menu_vip":
        text = (
            f"╔═══════════════════╗\n"
            f"   💎 <b>{t(lang, 'btn_vip')}</b>\n"
            f"╚═══════════════════╝\n\n"
            f"بە کڕینی VIP، ئەم تایبەتمەندیانەت دەبێت:\n"
            f"✅ خێرایی داونلۆدی زۆر زیاتر.\n"
            f"✅ بێ ڕیکلام و بێ جۆین کردنی چەناڵ.\n"
            f"✅ داونلۆدی بێسنوور بۆ وێنەکان.\n\n"
            f"💳 <b>بۆ کڕین پەیوەندی بکە بە:</b>\n{DEVELOPER_USERNAME}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(back_btn(lang))); return

    # ─── ڕێکخستنی زمان ────────────────────────────────────────────────────────
    if data == "menu_settings":
        text = f"🌍 <b>{t(lang, 'lang_select_title')}</b>\n\n{t(lang, 'lang_select_prompt')}"
        kb   = [
            [InlineKeyboardButton("🔴🔆🟢 کوردی",    callback_data="set_lang_ku")],
            [InlineKeyboardButton("🇺🇸 English",      callback_data="set_lang_en")],
            [InlineKeyboardButton("🇸🇦 العربية",     callback_data="set_lang_ar")],
            *back_btn(lang),
        ]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(kb)); return

    if data.startswith("set_lang_"):
        new_lang = data.split("_")[2]
        async with httpx.AsyncClient() as c:
            await c.put(firebase_url(f"registered_users/{user_id}/language"), json=new_lang)
        await query.answer(f"✅ Language → {new_lang.upper()}", show_alert=True)
        await start_command(update, context); return

    # ─── داونلۆد کردن ─────────────────────────────────────────────────────────
    if data.startswith("dl_"):
        action    = data.split("_")[1]
        user_data = await get_user_session_data(user_id)
        if not user_data:
            await query.answer(t(lang, "error_session_expired"), show_alert=True); return

        d        = user_data["details"]
        creator  = user_data["creator"]
        title    = clean_title(d.get("title", ""))
        images   = d.get("images", [])
        caption  = (
            f"🎬 <b>{html.escape(title)}</b>\n"
            f"👤 <b>{html.escape(creator)}</b>\n\n"
            f"🤖 <b>@{context.bot.username}</b>"
        )
        delete_kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_delete"), callback_data="close")]])

        try:
            if action == "photos":
                if not images:
                    await query.answer("❌ هیچ وێنەیەک نەدۆزرایەوە!", show_alert=True); return
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_photos"]    += 1
                await save_settings()
                media_group          = [InputMediaPhoto(media=img) for img in images[:10]]
                media_group[0].caption    = caption
                media_group[0].parse_mode = ParseMode.HTML
                await query.message.delete()
                await context.bot.send_media_group(chat_id=user_id, media=media_group)

            elif action == "video":
                if images:
                    # اگر Slideshow بوو، وێنەکان دابەزێنە
                    bot_settings_global["total_downloads"] += 1
                    bot_settings_global["total_photos"]    += 1
                    await save_settings()
                    media_group          = [InputMediaPhoto(media=img) for img in images[:10]]
                    media_group[0].caption    = caption
                    media_group[0].parse_mode = ParseMode.HTML
                    await query.message.delete()
                    await context.bot.send_media_group(chat_id=user_id, media=media_group)
                else:
                    bot_settings_global["total_downloads"] += 1
                    bot_settings_global["total_videos"]    += 1
                    await save_settings()
                    await query.message.edit_media(
                        InputMediaVideo(
                            media=d["video"]["play"], caption=caption, parse_mode=ParseMode.HTML
                        ),
                        reply_markup=delete_kb,
                    )

            elif action == "audio":
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_audios"]    += 1
                await save_settings()
                music_name = f"{DEVELOPER_USERNAME}-{get_random_id()}"
                await query.message.edit_media(
                    InputMediaAudio(
                        media=d["audio"]["play"], caption=caption, parse_mode=ParseMode.HTML,
                        title=music_name, performer=DEVELOPER_USERNAME,
                    ),
                    reply_markup=delete_kb,
                )
        except Exception as e:
            logger.error(f"داونلۆد هەڵە: {e}")
            link = d["video"]["play"] if not images else images[0]
            try:
                await query.message.edit_caption(
                    f"⚠️ <b>هەڵەیەک ڕوویدا، دایبەزێنە: <a href='{link}'>لێرە کلیک بکە</a></b>",
                    parse_mode=ParseMode.HTML,
                )
            except:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ هەڵە. لینک: {link}"
                )
        return

    # ==========================================================================
    # ========================= پانێڵی ئەدمین ===================================
    # ==========================================================================
    if not is_admin(user_id):
        await query.answer(t(lang, "error_admin_only"), show_alert=True); return

    # ─── پانێڵی سەرەکی ────────────────────────────────────────────────────────
    if data == "admin_panel_main":
        kb = [
            [
                InlineKeyboardButton("📊 ئاماری گشتی",        callback_data="admin_stats_full"),
                InlineKeyboardButton("📢 برۆدکاست",            callback_data="admin_broadcast_ask"),
            ],
            [
                InlineKeyboardButton("📢 بەڕێوەبردنی چەناڵ",  callback_data="manage_channels_menu"),
                InlineKeyboardButton("🚫 بلۆک / ئەنبلۆک",     callback_data="manage_blocks_menu"),
            ],
            [
                InlineKeyboardButton("💎 بەڕێوەبردنی VIP",    callback_data="manage_vips_menu"),
                InlineKeyboardButton("⚙️ دۆخی چاکسازی",       callback_data="admin_toggle_maintenance"),
            ],
            [InlineKeyboardButton("👥 بەڕێوەبردنی ئەدمین",    callback_data="manage_admins_menu")],
            [InlineKeyboardButton(t(lang, "btn_back"),          callback_data="cmd_start")],
        ]
        await query.edit_message_text(
            "👑 <b>پانێڵی کۆنترۆڵی سەرەکی</b>\n\n"
            f"🕐 {get_current_time()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        ); return

    # ─── ئامارەکان ─────────────────────────────────────────────────────────────
    if data == "admin_stats_full":
        all_users = await get_all_registered_users()
        text = (
            f"╔═══════════════════╗\n"
            f"   📊 <b>ئاماری پێشکەوتووی بۆت</b>\n"
            f"╚═══════════════════╝\n\n"
            f"👥 <b>بەکارهێنەرەکان:</b>\n"
            f"├ گشتی تۆمارکراو: {len(all_users)}\n"
            f"├ ئەدمین: {len(admins_list)}\n"
            f"├ VIP: {len(vip_users)}\n"
            f"├ چەناڵی ناچاری: {len(forced_channels)}\n"
            f"└ بلۆک: {len(blocked_users)}\n\n"
            f"📈 <b>داونلۆدەکان:</b>\n"
            f"├ گشتی: {bot_settings_global['total_downloads']}\n"
            f"├ ڤیدیۆ: {bot_settings_global['total_videos']}\n"
            f"├ گۆرانی: {bot_settings_global['total_audios']}\n"
            f"└ وێنە: {bot_settings_global['total_photos']}\n\n"
            f"⚙️ <b>سیستەم:</b>\n"
            f"├ دۆخی چاکسازی: {'بەڵێ 🔴' if bot_settings_global['maintenance_mode'] else 'نەخێر 🟢'}\n"
            f"└ کاتی کارکردن: {get_uptime()}\n\n"
            f"🕐 {get_current_time()}"
        )
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang, "admin_panel_main")),
        ); return

    # ─── دۆخی چاکسازی ──────────────────────────────────────────────────────────
    if data == "admin_toggle_maintenance":
        if not is_owner(user_id):
            await query.answer(t(lang, "error_owner_only"), show_alert=True); return
        bot_settings_global["maintenance_mode"] = not bot_settings_global["maintenance_mode"]
        await save_settings()
        status = "چالاک کرا 🔴" if bot_settings_global["maintenance_mode"] else "ناچالاک کرا 🟢"
        await query.edit_message_text(
            f"✅ دۆخی چاکسازی گۆڕدرا.\n\nئێستا: <b>{status}</b>\n\n🕐 {get_current_time()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang, "admin_panel_main")),
        ); return

    # ─── برۆدکاست ──────────────────────────────────────────────────────────────
    if data == "admin_broadcast_ask":
        admin_waiting_state[user_id] = "broadcast"
        await query.message.reply_text(
            f"📢 {t(lang, 'send_broadcast_msg')}",
            reply_markup=ForceReply(selective=True),
        ); return

    # ==========================================================================
    # ─── بەڕێوەبردنی چەناڵەکان ─────────────────────────────────────────────────
    # ==========================================================================
    if data == "manage_channels_menu":
        ch_list = "\n".join([f"  • <code>{ch}</code>" for ch in forced_channels]) or "  📭 هیچ چەناڵێک نییە."
        kb = [
            [
                InlineKeyboardButton("➕ زیادکردن",  callback_data="ch_add"),
                InlineKeyboardButton("➖ لابردن",     callback_data="ch_remove_list"),
            ],
            *back_btn(lang, "admin_panel_main"),
        ]
        await query.edit_message_text(
            f"📢 <b>بەڕێوەبردنی چەناڵە ناچارییەکان</b>\n\n<b>چەناڵەکان:</b>\n{ch_list}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if data == "ch_add":
        admin_waiting_state[user_id] = "ch_add"
        await query.message.reply_text(
            t(lang, "send_channel"), reply_markup=ForceReply(selective=True)
        ); return

    if data == "ch_remove_list":
        if not forced_channels:
            await query.answer("📭 هیچ چەناڵێک نییە!", show_alert=True); return
        kb = [[InlineKeyboardButton(f"❌ {ch}", callback_data=f"ch_del_{ch}")] for ch in forced_channels]
        kb.extend(back_btn(lang, "manage_channels_menu"))
        await query.edit_message_text(
            "📢 <b>چەناڵێک هەڵبژێرە بۆ لابردن:</b>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if data.startswith("ch_del_"):
        ch = data[7:]
        if ch in forced_channels:
            forced_channels.remove(ch)
            await save_settings()
            await query.edit_message_text(
                t(lang, "channel_removed", ch=ch), parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(back_btn(lang, "manage_channels_menu")),
            )
        return

    # ==========================================================================
    # ─── بەڕێوەبردنی بلۆک ──────────────────────────────────────────────────────
    # ==========================================================================
    if data == "manage_blocks_menu":
        blk_list = "\n".join([f"  • <code>{uid}</code>" for uid in blocked_users]) or "  📭 هیچ بلۆکێک نییە."
        kb = [
            [
                InlineKeyboardButton("🚫 بلۆک کردن",    callback_data="blk_add"),
                InlineKeyboardButton("✅ ئەنبلۆک کردن",  callback_data="blk_remove"),
            ],
            *back_btn(lang, "admin_panel_main"),
        ]
        await query.edit_message_text(
            f"🚫 <b>بەڕێوەبردنی بلۆک</b>\n\n<b>بلۆک کراوەکان:</b>\n{blk_list}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if data == "blk_add":
        admin_waiting_state[user_id] = "blk_add"
        await query.message.reply_text(
            t(lang, "send_user_id"), reply_markup=ForceReply(selective=True)
        ); return

    if data == "blk_remove":
        admin_waiting_state[user_id] = "blk_remove"
        await query.message.reply_text(
            t(lang, "send_user_id"), reply_markup=ForceReply(selective=True)
        ); return

    # ==========================================================================
    # ─── بەڕێوەبردنی VIP ───────────────────────────────────────────────────────
    # ==========================================================================
    if data == "manage_vips_menu":
        vip_list = "\n".join([f"  • <code>{uid}</code>" for uid in vip_users]) or "  📭 هیچ VIPێک نییە."
        kb = [
            [
                InlineKeyboardButton("➕ زیادکردنی VIP", callback_data="vip_add"),
                InlineKeyboardButton("➖ لابردنی VIP",   callback_data="vip_remove"),
            ],
            *back_btn(lang, "admin_panel_main"),
        ]
        await query.edit_message_text(
            f"💎 <b>بەڕێوەبردنی VIP</b>\n\n<b>VIPەکان:</b>\n{vip_list}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if data == "vip_add":
        admin_waiting_state[user_id] = "vip_add"
        await query.message.reply_text(
            t(lang, "send_user_id"), reply_markup=ForceReply(selective=True)
        ); return

    if data == "vip_remove":
        admin_waiting_state[user_id] = "vip_remove"
        await query.message.reply_text(
            t(lang, "send_user_id"), reply_markup=ForceReply(selective=True)
        ); return

    # ==========================================================================
    # ─── بەڕێوەبردنی ئەدمین (تەنیا خاوەن) ─────────────────────────────────────
    # ==========================================================================
    if data == "manage_admins_menu":
        if not is_owner(user_id):
            await query.answer(t(lang, "not_owner"), show_alert=True); return
        adm_list = "\n".join([f"  • <code>{uid}</code>" for uid in admins_list if uid != OWNER_ID]) or "  📭 هیچ ئەدمینێکی تر نییە."
        kb = [
            [
                InlineKeyboardButton("➕ زیادکردنی ئەدمین", callback_data="adm_add"),
                InlineKeyboardButton("➖ لابردنی ئەدمین",   callback_data="adm_remove"),
            ],
            *back_btn(lang, "admin_panel_main"),
        ]
        await query.edit_message_text(
            f"👥 <b>بەڕێوەبردنی ئەدمینەکان</b>\n\n<b>ئەدمینەکان:</b>\n{adm_list}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if data == "adm_add":
        if not is_owner(user_id):
            await query.answer(t(lang, "not_owner"), show_alert=True); return
        admin_waiting_state[user_id] = "adm_add"
        await query.message.reply_text(
            t(lang, "send_user_id"), reply_markup=ForceReply(selective=True)
        ); return

    if data == "adm_remove":
        if not is_owner(user_id):
            await query.answer(t(lang, "not_owner"), show_alert=True); return
        admin_waiting_state[user_id] = "adm_remove"
        await query.message.reply_text(
            t(lang, "send_user_id"), reply_markup=ForceReply(selective=True)
        ); return

# ==============================================================================
# --------------------- وەرگرتنی نامە و ڕیپلەی (MESSAGE HANDLER) ----------------
# ==============================================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_id = update.effective_user.id
    msg     = update.message.text.strip()
    lang    = await get_user_lang(user_id)

    # ──────────────────────────────────────────────────────────────────────────
    # بەڕێوەبردنی وەڵامی ئەدمین (وەڵامدانەوەی ForceReply)
    # ──────────────────────────────────────────────────────────────────────────
    if is_admin(user_id) and user_id in admin_waiting_state:
        state = admin_waiting_state.pop(user_id)

        # ── برۆدکاست ─────────────────────────────────────────────────────────
        if state == "broadcast":
            all_users  = await get_all_registered_users()
            success, fail = 0, 0
            status_msg = await update.message.reply_text("⏳ <b>برۆدکاست دەکرێت...</b>", parse_mode=ParseMode.HTML)
            for uid in all_users:
                try:
                    await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
                    success += 1
                    await asyncio.sleep(0.05)
                except:
                    fail += 1
            await status_msg.edit_text(
                t(lang, "broadcast_sent", success=success, fail=fail),
                parse_mode=ParseMode.HTML,
            )
            return

        # ── زیادکردنی چەناڵ ──────────────────────────────────────────────────
        if state == "ch_add":
            channel = msg if msg.startswith("@") else f"@{msg}"
            if channel not in forced_channels:
                forced_channels.append(channel)
                await save_settings()
            await update.message.reply_text(t(lang, "channel_added", ch=channel), parse_mode=ParseMode.HTML)
            return

        # ── زیادکردنی بلۆک ───────────────────────────────────────────────────
        if state == "blk_add":
            if not msg.isdigit():
                await update.message.reply_text(t(lang, "invalid_id")); return
            target_id = int(msg)
            blocked_users.add(target_id)
            await save_settings()
            await update.message.reply_text(t(lang, "user_blocked", id=target_id), parse_mode=ParseMode.HTML)
            return

        # ── لابردنی بلۆک ─────────────────────────────────────────────────────
        if state == "blk_remove":
            if not msg.isdigit():
                await update.message.reply_text(t(lang, "invalid_id")); return
            target_id = int(msg)
            blocked_users.discard(target_id)
            await save_settings()
            await update.message.reply_text(t(lang, "user_unblocked", id=target_id), parse_mode=ParseMode.HTML)
            return

        # ── زیادکردنی VIP ─────────────────────────────────────────────────────
        if state == "vip_add":
            if not msg.isdigit():
                await update.message.reply_text(t(lang, "invalid_id")); return
            target_id = int(msg)
            vip_users.add(target_id)
            await save_settings()
            await update.message.reply_text(t(lang, "vip_added", id=target_id), parse_mode=ParseMode.HTML)
            return

        # ── لابردنی VIP ───────────────────────────────────────────────────────
        if state == "vip_remove":
            if not msg.isdigit():
                await update.message.reply_text(t(lang, "invalid_id")); return
            target_id = int(msg)
            vip_users.discard(target_id)
            await save_settings()
            await update.message.reply_text(t(lang, "vip_removed", id=target_id), parse_mode=ParseMode.HTML)
            return

        # ── زیادکردنی ئەدمین ─────────────────────────────────────────────────
        if state == "adm_add":
            if not is_owner(user_id):
                await update.message.reply_text(t(lang, "not_owner")); return
            if not msg.isdigit():
                await update.message.reply_text(t(lang, "invalid_id")); return
            target_id = int(msg)
            admins_list.add(target_id)
            await save_settings()
            await update.message.reply_text(t(lang, "admin_added", id=target_id), parse_mode=ParseMode.HTML)
            return

        # ── لابردنی ئەدمین ───────────────────────────────────────────────────
        if state == "adm_remove":
            if not is_owner(user_id):
                await update.message.reply_text(t(lang, "not_owner")); return
            if not msg.isdigit():
                await update.message.reply_text(t(lang, "invalid_id")); return
            target_id = int(msg)
            if target_id == OWNER_ID:
                await update.message.reply_text("⛔ ناتوانیت خاوەنەکە لابەری!"); return
            admins_list.discard(target_id)
            await save_settings()
            await update.message.reply_text(t(lang, "admin_removed", id=target_id), parse_mode=ParseMode.HTML)
            return

    # ──────────────────────────────────────────────────────────────────────────
    # پشکنینی بلۆک و چاکسازی
    # ──────────────────────────────────────────────────────────────────────────
    if is_blocked(user_id):
        return

    if bot_settings_global["maintenance_mode"] and not is_admin(user_id):
        await update.message.reply_text(t(lang, "error_maintenance"), parse_mode=ParseMode.HTML)
        return

    # ──────────────────────────────────────────────────────────────────────────
    # پشکنینی لینک تیکتۆک
    # ──────────────────────────────────────────────────────────────────────────
    if "tiktok.com" not in msg:
        return

    is_sub, not_joined = await check_user_subscription(user_id, context)
    if not is_sub and not is_admin(user_id) and not is_vip(user_id):
        await update.message.reply_text(
            t(lang, "force_join_text"), parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(t(lang, "btn_join_channel", ch=ch), url=f"https://t.me/{ch.replace('@','')}")]
                 for ch in not_joined] +
                [[InlineKeyboardButton(t(lang, "btn_check_join"), callback_data="check_sub_start")]]
            ),
        )
        return

    # ──────────────────────────────────────────────────────────────────────────
    # ئاستی داونلۆدکردن
    # ──────────────────────────────────────────────────────────────────────────
    status_msg = await update.message.reply_text("🔍 <b>دابەزاندن دەستپێدەکات...</b>", parse_mode=ParseMode.HTML)

    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r   = await c.get(API_URL + msg)
            res = r.json()
            if not res.get("ok"):
                await status_msg.edit_text("❌ لینکەکە دروست نییە یان بلۆک کراوە!"); return

            video   = res["data"]
            details = video["details"]
            images  = details.get("images", [])
            creator = video.get("creator", "نەزانراو")

            await save_user_session_data(user_id, {"creator": creator, "details": details})

            caption = (
                f"✅ <b>{t(lang, 'download_found')}</b>\n\n"
                f"📝 <b>{t(lang, 'download_title', title=html.escape(clean_title(details.get('title'))))}</b>\n"
                f"👤 <b>{t(lang, 'download_owner', owner=html.escape(creator))}</b>"
            )

            if images:
                kb = [
                    [InlineKeyboardButton(t(lang, "btn_photos", count=len(images)), callback_data="dl_photos")],
                    [InlineKeyboardButton(t(lang, "btn_audio"),                      callback_data="dl_audio")],
                    [InlineKeyboardButton(t(lang, "btn_delete"),                     callback_data="close")],
                ]
            else:
                kb = [
                    [InlineKeyboardButton(t(lang, "btn_video"),  callback_data="dl_video")],
                    [InlineKeyboardButton(t(lang, "btn_audio"),  callback_data="dl_audio")],
                    [InlineKeyboardButton(t(lang, "btn_delete"), callback_data="close")],
                ]

            cover = details.get("cover", {}).get("cover", "")
            if cover:
                await status_msg.edit_media(
                    InputMediaPhoto(cover, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=InlineKeyboardMarkup(kb),
                )
            else:
                await status_msg.edit_text(caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

        except Exception as e:
            logger.error(f"❌ هەڵە لە داونلۆدکردن: {e}")
            await status_msg.edit_text("❌ هەڵەیەک ڕوویدا. تکایە دووبارە هەوڵبدەوە.")

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
    if not ptb_app.running:
        await ptb_app.initialize()
    await load_settings()
    data = await req.json()
    await ptb_app.process_update(Update.de_json(data, ptb_app.bot))
    return {"ok": True}


@app.get("/api/main")
async def health():
    return {"status": "active", "uptime": get_uptime(), "time": get_current_time()}
