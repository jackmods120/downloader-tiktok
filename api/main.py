# ===================================================================================================
# ===================================================================================================
# ==                                                                                               ==
# ==                                TIKTOK PREMIUM DOWNLOADER BOT                                  ==
# ==                                                                                               ==
# ==  Developer: @j4ck_721s                                                                        ==
# ==  Description: Massive, fully-featured, multi-language, bug-free Telegram Bot for TikTok.      ==
# ==  Architecture: Serverless Ready (Vercel/FastAPI) + Firebase Database.                         ==
# ==  Status: PROD / Fully Optimized / No Watermark / Slide Support / Uptime Fixed                 ==
# ==                                                                                               ==
# ===================================================================================================
# ===================================================================================================

import os
import time
import logging
import httpx
import re
import html
import asyncio
import random
import string
import json
import traceback
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Any, Optional, Set, Tuple

from fastapi import FastAPI, Request, BackgroundTasks
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAudio,
    ForceReply,
    Bot,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError, BadRequest, Forbidden, TimedOut

# ===================================================================================================
# ----------------------------------- ١. ڕێکخستنە سەرەکییەکان (CONFIG) ------------------------------
# ===================================================================================================

# وەرگرتنی زانیارییەکان لە ژینگەی ڤێرسڵ (Environment Variables)
TOKEN              = os.getenv("BOT_TOKEN")
API_URL            = "https://www.api.hyper-bd.site/Tiktok/?url="
API_URL_BACKUP     = "https://www.tikwm.com/api/?url=" 
CHANNEL_URL        = "https://t.me/jack_721_mod"
DB_URL             = os.getenv("DB_URL")
DB_SECRET          = os.getenv("DB_SECRET")

# زانیاری خاوەن (پێویستە نەگۆڕدرێت ئەگەر دەتەوێت دەسەڵاتی خاوەنت هەبێت)
OWNER_ID           = 5977475208
DEVELOPER_USERNAME = "@j4ck_721s"

# ===================================================================================================
# ----------------------------------- ٢. گۆڕاوە گشتییەکان (GLOBALS) ---------------------------------
# ===================================================================================================

# لیستی بەکارهێنەرە تایبەتەکان کە لە داتابەیسەوە نوێ دەکرێنەوە
admins_list: Set[int]         = {OWNER_ID}
forced_channels: List[str]    = []
blocked_users: Set[int]       = set()
vip_users: Set[int]           = set()

# ڕێکخستنە گشتییەکانی بۆتەکە
bot_settings_global: Dict[str, Any] = {
    "maintenance_mode"  : False,
    "total_downloads"   : 0,
    "total_videos"      : 0,
    "total_audios"      : 0,
    "total_photos"      : 0,
    "total_users"       : 0,
    "api_timeout"       : 60,
    "vip_bypass_join"   : True,
    "admin_bypass_join" : True,
}

# کاتی مانەوەی زانیارییەکانی داونلۆد (١٠ خولەک)
SESSION_EXPIRE = 600
# کاتی دەستپێکردنی بۆتەکە بۆ هەژمارکردنی Uptime
START_TIME     = time.time()
# سیستەمی چاوەڕوانی بۆ داخڵکردنی زانیاری لەلایەن ئەدمینەوە
admin_waiting_state: Dict[int, str] = {}

# ڕێکخستنی سیستەمی تۆمارکردنی هەڵەکان (Logging)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# دەستپێکردنی سێرڤەری FastAPI بۆ ڤێرسڵ
app = FastAPI()

# ===================================================================================================
# ----------------------------------- ٣. فەرهەنگی زمانەکان (DICTIONARIES) ---------------------------
# ===================================================================================================

# لێرەدا هەموو زمانەکان بە درێژی و بێ کورتکردنەوە نووسراون. هیچ ناوی ڤێرژنێکی تێدا نییە.
LANGUAGES = {
    "ku": {
        "welcome_title": "👋 <b>سڵاو بەڕێزم {name} {badge}</b>",
        "welcome_intro": "🤖 <b>بەخێربێیت بۆ خێراترین بۆتی دابەزاندنی تیکتۆک!</b>",
        "welcome_features": "📥 لێرە دەتوانیت بەبێ لۆگۆ ڤیدیۆ، وێنە و گۆرانییەکان دابەزێنیت.",
        "welcome_prompt": "👇 <b>بۆ دەستپێکردن، لینکی ڤیدیۆیەک بنێرە:</b>",
        
        "btn_download": "📥 دابەزاندنی پۆست",
        "btn_profile": "👤 پرۆفایلی من",
        "btn_vip": "💎 بەشی VIP",
        "btn_settings": "⚙️ ڕێکخستنی زمان",
        "btn_help": "ℹ️ ڕێنمایی",
        "btn_channel": "📢 کەناڵی بۆت",
        "btn_admin_panel": "👑 پانێڵی ئەدمین",
        "btn_owner_panel": "🔱 پانێڵی خاوەن",
        "btn_back": "🔙 گەڕانەوە",
        "btn_delete": "🗑 سڕینەوە",
        "btn_refresh": "🔄 نوێکردنەوە",
        "btn_confirm": "✅ دڵنیام",
        "btn_cancel": "❌ نەخێر",
        
        "force_join_text": "🔒 <b>جۆینی ناچاری</b>\nتکایە بۆ بەکارهێنانی بۆتەکە، سەرەتا جۆینی ئەم چەناڵانە بکە:",
        "btn_join_channel": "📢 جۆین: {ch}",
        "btn_check_join": "✅ جۆینم کرد",
        
        "help_title": "📚 <b>چۆنیەتی بەکارهێنان</b>",
        "help_text": "1️⃣ بڕۆ تیکتۆک و لینکەکە کۆپی بکە (Copy Link).\n2️⃣ لینکەکە لێرە پەیست بکە و بینێرە.\n3️⃣ جۆری دابەزاندنەکە هەڵبژێرە.",
        "download_prompt": "<b>🔗 تکایە لینکەکە لێرە بنێرە:</b>",
        
        "profile_title": "👤 <b>زانیاری هەژمارەکەت</b>",
        "profile_id": "🆔 <b>ئایدی:</b> <code>{id}</code>",
        "profile_name": "👤 <b>ناو:</b> {name}",
        "profile_username": "🔗 <b>یوزەر:</b> @{username}",
        "profile_vip_status": "💎 <b>دۆخی VIP:</b> {status}",
        "profile_total_dl": "📥 <b>داونلۆدەکانت:</b> {count}",
        
        "vip_yes": "چالاکە 💎",
        "vip_no": "ناچالاکە",
        
        "download_found": "✅ <b>پۆستەکە دۆزرایەوە!</b>",
        "download_title": "📝 <b>ناونیشان:</b> {title}",
        "download_owner": "👤 <b>خاوەن:</b> {owner}",
        "download_views": "👁 <code>{views}</code> بینەر",
        "download_likes": "❤️ <code>{likes}</code> لایک",
        "download_comments": "💬 <code>{comments}</code> کۆمێنت",
        "download_prompt_select": "👇 <b>فۆرماتێک هەڵبژێرە:</b>",
        
        "btn_video": "🎥 ڤیدیۆ (بێ لۆگۆ)",
        "btn_photos": "📸 وێنەکان ({count})",
        "btn_audio": "🎵 گۆرانی (MP3)",
        
        "error_admin_only": "⛔ ئەمە تایبەتە بە ئەدمین!",
        "error_owner_only": "⛔ ئەمە تایبەتە بە خاوەن!",
        "error_blocked": "⛔ <b>تۆ بلۆک کراویت لەلایەن ئەدمینەوە.</b>",
        "error_maintenance": "🛠 <b>بۆتەکە خەریکی نوێبوونەوەیە، تکایە کەمێکی تر هەوڵبدەوە.</b>",
        "error_session_expired": "⚠️ کاتەکەت بەسەرچوو، لینکەکە بنێرەوە.",
        "error_download_fail": "❌ هەڵەیەک ڕوویدا. دووبارە هەوڵبدەوە.",
        "error_invalid_link": "❌ لینکەکە هەڵەیە یان ڤیدیۆکە سڕاوەتەوە.",
        
        "lang_select_title": "🌍 <b>زمان هەڵبژێرە</b>",
        "lang_select_prompt": "ئەو زمانە هەڵبژێرە کە دەتەوێت بۆتەکەی پێ بەکاربهێنیت:",
        
        "no_users_found": "📭 هیچ بەکارهێنەرێک نییە.",
        "broadcast_sent": "📢 <b>ناردن تەواو بوو!</b>\n✅ سەرکەوتوو: <b>{success}</b>\n❌ سەرنەکەوتوو: <b>{fail}</b>",
        "admin_added": "✅ ئەدمین زیادکرا: <code>{id}</code>",
        "admin_removed": "✅ ئەدمین لابرا: <code>{id}</code>",
        "vip_added": "✅ VIP درا بە: <code>{id}</code>",
        "vip_removed": "✅ VIP لابرا لە: <code>{id}</code>",
        "user_blocked": "✅ بەکارهێنەر بلۆک کرا: <code>{id}</code>",
        "user_unblocked": "✅ بەکارهێنەر ئەنبلۆک کرا: <code>{id}</code>",
        "channel_added": "✅ چەناڵ زیادکرا: <b>{ch}</b>",
        "channel_removed": "✅ چەناڵ لابرا: <b>{ch}</b>",
        
        "invalid_id": "❌ ئایدییەکە هەڵەیە.",
        "send_user_id": "🆔 تکایە ئایدی بنێرە:",
        "send_channel": "📢 تکایە یوزەری چەناڵ بنێرە:",
        "send_broadcast_msg": "📢 نامەکە بنووسە بۆ ناردن:",
        "user_not_found": "⚠️ بەکارهێنەر نەدۆزرایەوە.",
        "user_info_text": "👤 <b>زانیاری یوزەر</b>\n🆔 ئایدی: <code>{id}</code>\n👤 ناو: {name}\n💎 VIP: {vip}\n🚫 بلۆک: {blocked}",
        "msg_sent_to_user": "✅ نامەکە نێردرا.",
        "send_msg_to_user": "✉️ نامەکە بنووسە بۆ یوزەری <code>{id}</code>:",
        "confirm_reset_stats": "⚠️ <b>دڵنیای لە ڕیسێت کردنی ئامارەکان؟</b>",
        "stats_reset_done": "✅ ئامارەکان سفر کرانەوە.",
        "confirm_reset_users": "⚠️ <b>دڵنیای لە سڕینەوەی داتابەیسی یوزەرەکان؟</b>",
        "users_reset_done": "✅ داتابەیس پاککرایەوە.",
        "backup_caption": "💾 <b>بەکئەپ</b>\n🕐 {time}",
    },
    "en": {
        "welcome_title": "👋 <b>Hello {name} {badge}</b>",
        "welcome_intro": "🤖 <b>Welcome to the fastest TikTok downloader!</b>",
        "welcome_features": "📥 You can download videos, photos, and audio without watermark.",
        "welcome_prompt": "👇 <b>Send a link to start:</b>",
        
        "btn_download": "📥 Download Post",
        "btn_profile": "👤 My Profile",
        "btn_vip": "💎 VIP Status",
        "btn_settings": "⚙️ Language",
        "btn_help": "ℹ️ Help",
        "btn_channel": "📢 Official Channel",
        "btn_admin_panel": "👑 Admin Panel",
        "btn_owner_panel": "🔱 Owner Panel",
        "btn_back": "🔙 Back",
        "btn_delete": "🗑 Delete",
        "btn_refresh": "🔄 Refresh",
        "btn_confirm": "✅ Confirm",
        "btn_cancel": "❌ Cancel",
        
        "force_join_text": "🔒 <b>Join Required</b>\nPlease join these channels to use the bot:",
        "btn_join_channel": "📢 Join: {ch}",
        "btn_check_join": "✅ I've Joined",
        
        "help_title": "📚 <b>How to Use</b>",
        "help_text": "1️⃣ Copy the TikTok link.\n2️⃣ Paste it here.\n3️⃣ Choose download format.",
        "download_prompt": "<b>🔗 Send your link here:</b>",
        
        "profile_title": "👤 <b>Account Info</b>",
        "profile_id": "🆔 <b>ID:</b> <code>{id}</code>",
        "profile_name": "👤 <b>Name:</b> {name}",
        "profile_username": "🔗 <b>Username:</b> @{username}",
        "profile_vip_status": "💎 <b>VIP:</b> {status}",
        "profile_total_dl": "📥 <b>Downloads:</b> {count}",
        
        "vip_yes": "Active 💎",
        "vip_no": "Inactive",
        
        "download_found": "✅ <b>Post Found!</b>",
        "download_title": "📝 <b>Title:</b> {title}",
        "download_owner": "👤 <b>Owner:</b> {owner}",
        "download_views": "👁 <code>{views}</code> Views",
        "download_likes": "❤️ <code>{likes}</code> Likes",
        "download_comments": "💬 <code>{comments}</code> Comments",
        "download_prompt_select": "👇 <b>Select Format:</b>",
        
        "btn_video": "🎥 Video (No WM)",
        "btn_photos": "📸 Photos ({count})",
        "btn_audio": "🎵 Audio (MP3)",
        
        "error_admin_only": "⛔ Admins only!",
        "error_owner_only": "⛔ Owner only!",
        "error_blocked": "⛔ <b>You are blocked from using this bot.</b>",
        "error_maintenance": "🛠 <b>Bot is updating, try again later.</b>",
        "error_session_expired": "⚠️ Session expired, send the link again.",
        "error_download_fail": "❌ Error occurred. Try again.",
        "error_invalid_link": "❌ Invalid link or post deleted.",
        
        "lang_select_title": "🌍 <b>Select Language</b>",
        "lang_select_prompt": "Choose your preferred language:",
        
        "no_users_found": "📭 No users found.",
        "broadcast_sent": "📢 <b>Broadcast Done!</b>\n✅ Success: <b>{success}</b>\n❌ Failed: <b>{fail}</b>",
        "admin_added": "✅ Admin added: <code>{id}</code>",
        "admin_removed": "✅ Admin removed: <code>{id}</code>",
        "vip_added": "✅ VIP granted: <code>{id}</code>",
        "vip_removed": "✅ VIP revoked: <code>{id}</code>",
        "user_blocked": "✅ User blocked: <code>{id}</code>",
        "user_unblocked": "✅ User unblocked: <code>{id}</code>",
        "channel_added": "✅ Channel added: <b>{ch}</b>",
        "channel_removed": "✅ Channel removed: <b>{ch}</b>",
        
        "invalid_id": "❌ Invalid ID.",
        "send_user_id": "🆔 Send User ID:",
        "send_channel": "📢 Send Channel username:",
        "send_broadcast_msg": "📢 Send broadcast message:",
        "user_not_found": "⚠️ User not found.",
        "user_info_text": "👤 <b>User Info</b>\n🆔 ID: <code>{id}</code>\n👤 Name: {name}\n💎 VIP: {vip}\n🚫 Blocked: {blocked}",
        "msg_sent_to_user": "✅ Message sent.",
        "send_msg_to_user": "✉️ Send message to <code>{id}</code>:",
        "confirm_reset_stats": "⚠️ <b>Reset all stats?</b>",
        "stats_reset_done": "✅ Stats reset.",
        "confirm_reset_users": "⚠️ <b>Wipe user database?</b>",
        "users_reset_done": "✅ DB wiped.",
        "backup_caption": "💾 <b>Backup</b>\n🕐 {time}",
    },
    "ar": {
        "welcome_title": "👋 <b>أهلاً بك {name} {badge}</b>",
        "welcome_intro": "🤖 <b>مرحباً بك في أسرع بوت لتحميل تيك توك!</b>",
        "welcome_features": "📥 يمكنك تحميل الفيديو، الصور، والصوتيات بدون علامة مائية.",
        "welcome_prompt": "👇 <b>أرسل رابطاً للبدء:</b>",
        
        "btn_download": "📥 تحميل منشور",
        "btn_profile": "👤 حسابي",
        "btn_vip": "💎 قسم VIP",
        "btn_settings": "⚙️ اللغة",
        "btn_help": "ℹ️ مساعدة",
        "btn_channel": "📢 قناة البوت",
        "btn_admin_panel": "👑 لوحة الأدمن",
        "btn_owner_panel": "🔱 لوحة المالك",
        "btn_back": "🔙 رجوع",
        "btn_delete": "🗑 حذف",
        "btn_refresh": "🔄 تحديث",
        "btn_confirm": "✅ تأكيد",
        "btn_cancel": "❌ إلغاء",
        
        "force_join_text": "🔒 <b>اشتراك إجباري</b>\nيرجى الاشتراك في القنوات التالية أولاً:",
        "btn_join_channel": "📢 انضمام: {ch}",
        "btn_check_join": "✅ لقد انضممت",
        
        "help_title": "📚 <b>كيفية الاستخدام</b>",
        "help_text": "1️⃣ انسخ رابط التيك توك.\n2️⃣ الصقه هنا.\n3️⃣ اختر صيغة التحميل.",
        "download_prompt": "<b>🔗 أرسل الرابط هنا:</b>",
        
        "profile_title": "👤 <b>معلومات حسابك</b>",
        "profile_id": "🆔 <b>المعرف:</b> <code>{id}</code>",
        "profile_name": "👤 <b>الاسم:</b> {name}",
        "profile_username": "🔗 <b>اليوزر:</b> @{username}",
        "profile_vip_status": "💎 <b>حالة VIP:</b> {status}",
        "profile_total_dl": "📥 <b>تحميلاتك:</b> {count}",
        
        "vip_yes": "مفعل 💎",
        "vip_no": "غير مفعل",
        
        "download_found": "✅ <b>تم العثور على المنشور!</b>",
        "download_title": "📝 <b>العنوان:</b> {title}",
        "download_owner": "👤 <b>المالك:</b> {owner}",
        "download_views": "👁 <code>{views}</code> مشاهدات",
        "download_likes": "❤️ <code>{likes}</code> إعجابات",
        "download_comments": "💬 <code>{comments}</code> تعليقات",
        "download_prompt_select": "👇 <b>اختر الصيغة:</b>",
        
        "btn_video": "🎥 فيديو (بدون حقوق)",
        "btn_photos": "📸 صور ({count})",
        "btn_audio": "🎵 صوت (MP3)",
        
        "error_admin_only": "⛔ للأدمن فقط!",
        "error_owner_only": "⛔ للمالك فقط!",
        "error_blocked": "⛔ <b>لقد تم حظرك من استخدام البوت.</b>",
        "error_maintenance": "🛠 <b>البوت قيد التحديث، جرب لاحقاً.</b>",
        "error_session_expired": "⚠️ انتهت الجلسة، أرسل الرابط مجدداً.",
        "error_download_fail": "❌ حدث خطأ، حاول مجدداً.",
        "error_invalid_link": "❌ رابط غير صحيح أو محذوف.",
        
        "lang_select_title": "🌍 <b>اختر اللغة</b>",
        "lang_select_prompt": "اختر لغتك المفضلة:",
        
        "no_users_found": "📭 لا يوجد مستخدمين.",
        "broadcast_sent": "📢 <b>تم الإرسال!</b>\n✅ نجاح: <b>{success}</b>\n❌ فشل: <b>{fail}</b>",
        "admin_added": "✅ تم إضافة أدمن: <code>{id}</code>",
        "admin_removed": "✅ تم إزالة أدمن: <code>{id}</code>",
        "vip_added": "✅ تم منح VIP: <code>{id}</code>",
        "vip_removed": "✅ تم إزالة VIP: <code>{id}</code>",
        "user_blocked": "✅ تم حظر: <code>{id}</code>",
        "user_unblocked": "✅ تم فك حظر: <code>{id}</code>",
        "channel_added": "✅ تمت الإضافة: <b>{ch}</b>",
        "channel_removed": "✅ تمت الإزالة: <b>{ch}</b>",
        
        "invalid_id": "❌ معرف غير صحيح.",
        "send_user_id": "🆔 أرسل المعرف:",
        "send_channel": "📢 أرسل يوزر القناة:",
        "send_broadcast_msg": "📢 أرسل رسالة الإذاعة:",
        "user_not_found": "⚠️ المستخدم غير موجود.",
        "user_info_text": "👤 <b>معلومات المستخدم</b>\n🆔 المعرف: <code>{id}</code>\n👤 الاسم: {name}\n💎 VIP: {vip}\n🚫 محظور: {blocked}",
        "msg_sent_to_user": "✅ تم إرسال الرسالة.",
        "send_msg_to_user": "✉️ أرسل رسالة إلى <code>{id}</code>:",
        "confirm_reset_stats": "⚠️ <b>هل أنت متأكد من تصفير الإحصائيات؟</b>",
        "stats_reset_done": "✅ تم التصفير.",
        "confirm_reset_users": "⚠️ <b>هل أنت متأكد من مسح قاعدة البيانات؟</b>",
        "users_reset_done": "✅ تم المسح.",
        "backup_caption": "💾 <b>نسخة احتياطية</b>\n🕐 {time}",
    },
}

# ===================================================================================================
# ----------------------------------- ٤. فەنکشنە یارمەتیدەرەکان (HELPERS) ---------------------------
# ===================================================================================================

async def get_user_lang(user_id: int) -> str:
    """
    ئەم فەنکشنە زمانی بەکارهێنەر لە داتابەیس دەهێنێت.
    ئەگەر یوزەرەکە تازە بێت، ئەوا کوردی "ku" وەردەگرێت وەک بنەڕەت.
    """
    async with httpx.AsyncClient(timeout=10) as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}/language"))
            if r.status_code == 200 and r.json():
                return str(r.json())
        except Exception as e:
            logger.error(f"Failed to get user language: {e}")
    return "ku"

def t(lang: str, key: str, **kwargs) -> str:
    """
    ئەمە فەنکشنێکی زۆر گرنگە بۆ وەرگێڕانی وشەکان.
    وشەکان بەپێی زمانی یوزەرەکە دەهێنێت و گۆڕاوەکان جێگیر دەکات.
    """
    text = LANGUAGES.get(lang, LANGUAGES["ku"]).get(key, LANGUAGES["ku"].get(key, key))
    try:
        return text.format(**kwargs)
    except:
        return text

def get_random_id(length: int = 8) -> str:
    """دروستکردنی ئایدییەکی ڕاندۆم بۆ ناوی گۆرانییەکان تا دووبارە نەبنەوە"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def clean_title(title: str) -> str:
    """پاککردنەوەی ناونیشانی ڤیدیۆ بۆ ئەوەی هێمای تێکدەر لەخۆ نەگرێت"""
    if not title:
        return "TikTok Video"
    cleaned = re.sub(r'[\\/*?:"<>|#]', '', title)
    return cleaned[:80].strip()

def firebase_url(path: str) -> str:
    """دروستکردنی لینکی تەواوەتی داتابەیسی فایەربەیس"""
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

def get_current_time() -> str:
    """کاتی ئێستا بە شێوازێکی ڕێکخراو"""
    return datetime.now().strftime("%Y-%m-%d | %H:%M:%S")

def format_number(n) -> str:
    """گۆڕینی ژمارە گەورەکان بۆ شێوازی کورتکراوە (وەک 1.5M یان 10K)"""
    try:
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except:
        return str(n)

def back_btn(lang: str, target: str = "cmd_start") -> list:
    """دروستکردنی دوگمەی گەڕانەوە بۆ هەر زمانێک"""
    return [[InlineKeyboardButton(t(lang, "btn_back"), callback_data=target)]]

def divider() -> str:
    """هێڵێکی جیاکەرەوە بۆ جوانی نامەکان"""
    return "━━━━━━━━━━━━━━━━━━━"

# ===================================================================================================
# ----------------------------------- ٥. کاتی کارکردن (UPTIME بە کوردی) -----------------------------
# ===================================================================================================

def get_uptime_localized(lang: str) -> str:
    """
    ئەم فەنکشنە کاتی کارکردنی سێرڤەرەکە بە کوردی دەردەهێنێت.
    نموونە: 0 ڕۆژ و 0 کاتژمێر و 7 خولەک و 2 چرکە
    """
    s = int(time.time() - START_TIME)
    d, r = divmod(s, 86400)
    h, r = divmod(r, 3600)
    m, sec = divmod(r, 60)
    
    if lang == "ku":
        return f"{d} ڕۆژ و {h} کاتژمێر و {m} خولەک و {sec} چرکە"
    elif lang == "ar":
        return f"{d} يوم و {h} ساعة و {m} دقيقة و {sec} ثانية"
    else:
        return f"{d} days, {h} hours, {m} mins, {sec} secs"

# ===================================================================================================
# ----------------------------------- ٦. پشکنینەکان (SECURITY) --------------------------------------
# ===================================================================================================

def is_owner(uid: int) -> bool:
    """ئایا ئەم کەسە خاوەنی سەرەکییە؟"""
    return uid == OWNER_ID

def is_admin(uid: int) -> bool:
    """ئایا ئەم کەسە ئەدمینە یان خاوەنە؟"""
    return uid in admins_list or uid == OWNER_ID

def is_blocked(uid: int) -> bool:
    """ئایا ئەم کەسە بلۆک کراوە؟"""
    return uid in blocked_users

def is_vip(uid: int) -> bool:
    """ئایا ئەم کەسە VIP یە؟"""
    return uid in vip_users or uid == OWNER_ID

async def check_user_subscription(user_id: int, context) -> Tuple[bool, List[str]]:
    """
    ئەم فەنکشنە دەپشکنێت بزانێت ئایا یوزەرەکە لەو چەناڵانەدایە کە ئەدمین دیاری کردووە.
    """
    if not forced_channels:
        return True, []
    not_joined =[]
    for ch in forced_channels:
        try:
            m = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status in[ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                not_joined.append(ch)
        except Exception as e:
            logger.error(f"Error checking channel {ch}: {e}")
    
    return len(not_joined) == 0, not_joined

# ===================================================================================================
# ----------------------------------- ٧. بەڕێوەبردنی داتابەیس (DATABASE CRUD) -----------------------
# ===================================================================================================

async def load_settings():
    """
    لە کاتی ئیشپێکردنی بۆتەکەدا، هەموو زانیارییەکان (ئەدمین، VIP، چەناڵ، ئامار)
    لە فایەربەیسەوە دەهێنێتە ناو مێمۆری بۆ خێرایی.
    """
    global admins_list, forced_channels, blocked_users, vip_users, bot_settings_global
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(firebase_url("system_settings"))
            if r.status_code == 200 and r.json():
                d = r.json()
                admins_list        = set(d.get("admins", [OWNER_ID]))
                forced_channels    = d.get("channels",[])
                blocked_users      = set(d.get("blocked",[]))
                vip_users          = set(d.get("vips",[]))
                bot_settings_global.update(d.get("settings", {}))
                logger.info("✅ داتابەیس بە سەرکەوتوویی هێنرایەوە.")
        except Exception as e:
            logger.error(f"❌ کێشە لە هێنانەوەی داتابەیس: {e}")

async def save_settings():
    """
    هەر کاتێک گۆڕانکارییەک کرا (وەک زیادکردنی ئەدمین)، 
    ئەم فەنکشنە زانیارییە نوێیەکان دەنێرێتەوە بۆ فایەربەیس.
    """
    data = {
        "admins"  : list(admins_list),
        "channels": forced_channels,
        "blocked" : list(blocked_users),
        "vips"    : list(vip_users),
        "settings": bot_settings_global,
    }
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            await c.put(firebase_url("system_settings"), json=data)
            logger.info("✅ داتابەیس سەیڤ کرا.")
        except Exception as e:
            logger.error(f"❌ کێشە لە سەیڤکردنی داتابەیس: {e}")

async def save_user_session(user_id: int, data: dict):
    """سەیڤکردنی زانیاری ڤیدیۆی ئێستا کە یوزەر داوای کردووە"""
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            await c.put(firebase_url(f"user_sessions/{user_id}"), json=data)
        except Exception as e:
            logger.error(f"Failed to save user session: {e}")

async def get_user_session(user_id: int) -> Optional[dict]:
    """هێنانەوەی زانیاری ڤیدیۆی ئێستا"""
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            r = await c.get(firebase_url(f"user_sessions/{user_id}"))
            if r.status_code == 200 and r.json():
                d = r.json()
                if int(time.time()) - d.get("timestamp", 0) <= SESSION_EXPIRE:
                    return d
        except Exception as e:
            logger.error(f"Failed to get user session: {e}")
    return None

async def is_user_registered(user_id: int) -> bool:
    """پشکنین کە ئایا یوزەر پێشتر لە بۆتەکە بووە"""
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}"))
            return r.status_code == 200 and r.json() is not None
        except:
            return False

async def register_user(user_id: int, info: dict):
    """تۆمارکردنی یوزەری نوێ"""
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            await c.put(firebase_url(f"registered_users/{user_id}"), json=info)
        except Exception as e:
            logger.error(f"Failed to register user: {e}")

async def get_user_data(user_id: int) -> Optional[dict]:
    """هێنانەوەی زانیاری تەواوی یوزەر (وەک پرۆفایل و ئامار)"""
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}"))
            if r.status_code == 200 and r.json():
                return r.json()
        except:
            pass
    return None

async def update_user_field(user_id: int, field: str, value):
    """نوێکردنەوەی تەنها یەک بەش لە زانیاری یوزەر (نموونە گۆڕینی زمان)"""
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            await c.put(firebase_url(f"registered_users/{user_id}/{field}"), json=value)
        except Exception as e:
            logger.error(f"Failed to update user field: {e}")

async def get_all_user_ids() -> List[int]:
    """هێنانەوەی لیستی هەموو ئایدییەکان بۆ برۆدکاست و ئامار"""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(firebase_url("registered_users"))
            if r.status_code == 200 and r.json():
                return [int(k) for k in r.json().keys()]
        except Exception as e:
            logger.error(f"Failed to get all user IDs: {e}")
    return[]

async def delete_all_users():
    """پاککردنەوەی تەواوی داتابەیسی یوزەرەکان (تایبەت بە خاوەن)"""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            await c.delete(firebase_url("registered_users"))
        except Exception as e:
            logger.error(f"Failed to delete all users: {e}")

async def notify_owner_new_user(context, user):
    """ناردنی ئاگادارکردنەوە بۆ خاوەن کاتێک یوزەری نوێ دێت"""
    msg = (
        f"🔔 <b>بەکارهێنەرێکی نوێ تۆمار کرا!</b>\n\n"
        f"👤 ناو: {html.escape(user.first_name)}\n"
        f"🆔 ئایدی: <code>{user.id}</code>\n"
        f"🔗 یوزەرنەیم: @{user.username or '—'}\n"
        f"🕐 کات: {get_current_time()}"
    )
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ===================================================================================================
# ----------------------------------- ٨. سیستەمی دابەزاندن و وێنە (CORE DOWNLOADER) -----------------
# ===================================================================================================

async def fetch_tiktok_data(url: str) -> Optional[dict]:
    """
    دەکۆشێت دیتا لە API هەڵبگرێت.
    ئەگەر API یەکەم شکستی هێنا، API دووەم بەکاردەهێنێت.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=API_TIMEOUT, headers=headers, follow_redirects=True) as c:
        
        # ── API یەکەم ──
        try:
            r = await c.get(API_URL + url)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok") or data.get("status") == "success":
                    return {"source": "primary", "data": data}
        except Exception as e:
            logger.warning(f"Primary API Failed: {e}")

        # ── API دووەم (بەکاپ) ──
        try:
            r2 = await c.get(API_URL_BACKUP + url)
            if r2.status_code == 200:
                raw = r2.json()
                if raw.get("code") == 0 and raw.get("data"):
                    d = raw["data"]
                    normalized = {
                        "ok": True,
                        "data": {
                            "creator": d.get("author", {}).get("nickname", "Unknown"),
                            "details": {
                                "title": d.get("title", ""),
                                "cover": {"cover": d.get("cover", "")},
                                "images": d.get("images",[]),
                                "video": {"play": d.get("play", "")},
                                "audio": {"play": d.get("music", "")},
                                "stats": {
                                    "views": d.get("play_count", 0),
                                    "likes": d.get("digg_count", 0),
                                    "comments": d.get("comment_count", 0),
                                }
                            }
                        }
                    }
                    return {"source": "backup", "data": normalized}
        except Exception as e:
            logger.error(f"Backup API Failed too: {e}")
            
    return None

def parse_api_response(raw: dict) -> Tuple[str, dict, list]:
    """
    ڕێکخستنی زانیارییەکانی تیکتۆک بۆ ئەوەی بۆتەکە بە ئاسانی بیانخوێنێتەوە.
    """
    data = raw.get("data", {})
    creator = data.get("creator", "Unknown")
    details = data.get("details", {})
    
    # دۆزینەوەی وێنەکان ئەگەر پۆستەکە Slideshow بێت
    images = details.get("images") or details.get("image_list") or data.get("images") or []
    
    clean_images =[]
    for img in images:
        if isinstance(img, str):
            clean_images.append(img)
        elif isinstance(img, dict):
            url_val = img.get("url_list", [None])[0] or img.get("url") or img.get("download_url")
            if url_val:
                clean_images.append(url_val)
                
    return creator, details, clean_images

async def fetch_image_as_bytes(url: str) -> Optional[BytesIO]:
    """
    پێویستە زۆر بە باشی سەرنجی ئەمە بدەیت!
    ئەم فەنکشنە وێنەکان داونلۆد دەکاتە ناو مێمۆری، بۆ ئەوەی ئەگەر تەلەگرام
    نەیتوانی ڕاستەوخۆ لە لینکەکەوە بیخوێنێتەوە، ئێرە کێشەکە چارەسەر دەکات.
    ئەمە ئەو پارچە کۆدەیە کە کێشەی وێنەکانت ١٠٠٪ بۆ چارەسەر دەکات!
    """
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                b = BytesIO(resp.content)
                b.name = f"tiktok_photo_{get_random_id(4)}.jpg"
                return b
    except Exception as e:
        logger.error(f"Failed to fetch image as bytes: {e}")
    return None

# ===================================================================================================
# ----------------------------------- ٩. فەرمانەکانی تەلەگرام (TELEGRAM COMMANDS) -------------------
# ===================================================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    فەرمانی سەرەکی بۆتەکە. هەموو پشکنینەکانی جۆین، بلۆک، و چاکسازی لێرە دەکرێن.
    """
    user = update.effective_user
    uid = user.id
    lang = await get_user_lang(uid)
    is_cb = bool(update.callback_query)

    # فەنکشنێکی ناوخۆیی بۆ ناردنی نامە یان نوێکردنەوەی
    async def send(text, kb):
        markup = InlineKeyboardMarkup(kb)
        if is_cb:
            try:
                await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
            except BadRequest:
                await update.callback_query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)

    # پشکنینی بلۆک
    if is_blocked(uid):
        await send(t(lang, "error_blocked"), back_btn(lang, "cmd_start"))
        return

    # پشکنینی دۆخی چاکسازی
    if bot_settings_global["maintenance_mode"] and not is_admin(uid):
        await send(t(lang, "error_maintenance"), back_btn(lang, "cmd_start"))
        return

    # تۆمارکردنی یوزەری نوێ لە داتابەیس
    if not is_admin(uid):
        if not await is_user_registered(uid):
            asyncio.create_task(notify_owner_new_user(context, user))
            bot_settings_global["total_users"] += 1
            await save_settings()
            await register_user(uid, {
                "name": user.first_name,
                "username": user.username or "",
                "joined_date": get_current_time(),
                "is_vip": False,
                "language": "ku",
                "downloads": 0,
            })

    # پشکنینی جۆینی ناچاری
    is_sub, not_joined = await check_user_subscription(uid, context)
    bypass = (is_admin(uid) and bot_settings_global.get("admin_bypass_join", True)) or \
             (is_vip(uid) and bot_settings_global.get("vip_bypass_join", True))
    
    if not is_sub and not bypass:
        kb = [[InlineKeyboardButton(t(lang, "btn_join_channel", ch=ch), url=f"https://t.me/{ch.replace('@','')}")] for ch in not_joined]
        kb.append([InlineKeyboardButton(t(lang, "btn_check_join"), callback_data="check_sub_start")])
        await send(t(lang, "force_join_text"), kb)
        return

    # پێدانی لۆگۆی تایبەت (👑, ⚡, 💎) بەپێی ئاستی یوزەرەکە
    badges = {
        "ku": {"owner": "👑", "admin": "⚡", "vip": "💎", "free": ""},
        "en": {"owner": "👑", "admin": "⚡", "vip": "💎", "free": ""},
        "ar": {"owner": "👑", "admin": "⚡", "vip": "💎", "free": ""}
    }
    lang_badges = badges.get(lang, badges["ku"])
    
    badge = (
        lang_badges["owner"] if is_owner(uid) else
        lang_badges["admin"] if is_admin(uid) else
        lang_badges["vip"] if is_vip(uid) else
        lang_badges["free"]
    )

    # دەقی بەخێرهاتن کە هیچ ڤێرژنێکی تێدا نییە
    text = (
        f"╭━━━━━━━━━━━━━━━━━━━━╮\n"
        f"  {t(lang, 'welcome_title', name=html.escape(user.first_name), badge=badge)}\n"
        f"╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"{t(lang, 'welcome_intro')}\n"
        f"{t(lang, 'welcome_features')}\n\n"
        f"{divider()}\n"
        f"{t(lang, 'welcome_prompt')}"
    )

    # دوگمەکانی مینیوی سەرەکی
    kb = [[InlineKeyboardButton(t(lang, "btn_download"), callback_data="cmd_download")],[
            InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
            InlineKeyboardButton(t(lang, "btn_vip"), callback_data="menu_vip"),
        ],[
            InlineKeyboardButton(t(lang, "btn_settings"), callback_data="menu_settings"),
            InlineKeyboardButton(t(lang, "btn_help"), callback_data="cmd_help"),
        ],[InlineKeyboardButton(t(lang, "btn_channel"), url=CHANNEL_URL)],
    ]
    
    if is_admin(uid):
        kb.append([InlineKeyboardButton(t(lang, "btn_admin_panel"), callback_data="admin_main")])
    if is_owner(uid):
        kb.append([InlineKeyboardButton(t(lang, "btn_owner_panel"), callback_data="owner_main")])

    await send(text, kb)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /help بۆ پیشاندانی ڕێنمایی"""
    uid = update.effective_user.id
    lang = await get_user_lang(uid)
    text = (
        f"╭━━━━━━━━━━━━━━━━━━━━╮\n"
        f"  {t(lang, 'help_title')}\n"
        f"╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"{t(lang, 'help_text')}"
    )
    kb = back_btn(lang)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


# ===================================================================================================
# ----------------------------------- ١٠. کیبۆردە تایبەتەکان (INLINE NUMPAD) ------------------------
# ===================================================================================================

def build_numpad(action: str, current: str = "") -> InlineKeyboardMarkup:
    """
    ئەم کیبۆردە تایبەتە دروست کراوە بۆ ئەوەی ئەدمینەکان بەبێ نووسین 
    تەنها بە پەنجەدان لە ژمارەکان ئایدی داخل بکەن.
    """
    rows =[[
            InlineKeyboardButton("1", callback_data=f"np_{action}_1"),
            InlineKeyboardButton("2", callback_data=f"np_{action}_2"),
            InlineKeyboardButton("3", callback_data=f"np_{action}_3")
        ],[
            InlineKeyboardButton("4", callback_data=f"np_{action}_4"),
            InlineKeyboardButton("5", callback_data=f"np_{action}_5"),
            InlineKeyboardButton("6", callback_data=f"np_{action}_6")
        ],[
            InlineKeyboardButton("7", callback_data=f"np_{action}_7"),
            InlineKeyboardButton("8", callback_data=f"np_{action}_8"),
            InlineKeyboardButton("9", callback_data=f"np_{action}_9")
        ],[
            InlineKeyboardButton("⌫ سڕینەوە", callback_data=f"np_{action}_back"),
            InlineKeyboardButton("0", callback_data=f"np_{action}_0"),
            InlineKeyboardButton("✅ تەواو", callback_data=f"np_{action}_ok")
        ],
        [InlineKeyboardButton("❌ هەڵوەشاندنەوە", callback_data="np_cancel")],
    ]
    return InlineKeyboardMarkup(rows)

async def numpad_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بەڕێوەبردنی کلیکەکانی سەر کیبۆردی ژمارەیی"""
    query = update.callback_query
    data = query.data
    uid = query.from_user.id
    lang = await get_user_lang(uid)
    await query.answer()

    if data == "np_cancel":
        context.user_data.pop("np_action", None)
        context.user_data.pop("np_input", None)
        try:
            await query.message.delete()
        except:
            pass
        return

    if data.startswith("np_"):
        parts = data.split("_", 2)
        if len(parts) < 3: return
        action, key = parts[1], parts[2]
        current = context.user_data.get("np_input", "")

        if key == "back":
            current = current[:-1]
        elif key == "ok":
            if not current.isdigit():
                await query.answer(t(lang, "invalid_id"), show_alert=True)
                return
            
            target_id = int(current)
            context.user_data.pop("np_input", None)
            context.user_data.pop("np_action", None)

            # --- جێبەجێکردنی کارەکە بەپێی Action ---
            if action == "blk_add":
                blocked_users.add(target_id)
                await save_settings()
                await query.edit_message_text(f"✅ بلۆک کرا: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn(lang, "admin_main")))
            elif action == "blk_rm":
                blocked_users.discard(target_id)
                await save_settings()
                await query.edit_message_text(f"✅ ئەنبلۆک کرا: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn(lang, "admin_main")))
            elif action == "vip_add":
                vip_users.add(target_id)
                await save_settings()
                await update_user_field(target_id, "is_vip", True)
                await query.edit_message_text(f"✅ VIP پێدرا: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn(lang, "admin_main")))
            elif action == "vip_rm":
                vip_users.discard(target_id)
                await save_settings()
                await update_user_field(target_id, "is_vip", False)
                await query.edit_message_text(f"✅ VIP لابرا: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn(lang, "admin_main")))
            elif action == "adm_add":
                if not is_owner(uid): 
                    await query.answer(t(lang, "error_owner_only"), show_alert=True); return
                admins_list.add(target_id)
                await save_settings()
                await query.edit_message_text(f"✅ ئەدمین زیادکرا: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn(lang, "owner_main")))
            elif action == "adm_rm":
                if not is_owner(uid): 
                    await query.answer(t(lang, "error_owner_only"), show_alert=True); return
                if target_id == OWNER_ID: 
                    await query.answer("⛔ ناتوانیت خاوەن بسڕیتەوە!", show_alert=True); return
                admins_list.discard(target_id)
                await save_settings()
                await query.edit_message_text(f"✅ ئەدمین لابرا: <code>{target_id}</code>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn(lang, "owner_main")))
            return
        else:
            if len(current) < 15:
                current += key
        
        context.user_data["np_input"] = current
        display = f"<code>{current}</code>" if current else "<i>(بەتاڵ)</i>"
        try:
            await query.edit_message_text(f"📟 تکایە ئایدیەکە داخڵ بکە:\n\n{display}", parse_mode=ParseMode.HTML, reply_markup=build_numpad(action, current))
        except:
            pass


# ===================================================================================================
# ----------------------------------- ١١. بەڕێوەبردنی دوگمەکان (CALLBACK HANDLER) -------------------
# ===================================================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    گەورەترین فەنکشن لە کۆدەکەدا کە بەرپرسە لە هەموو دوگمەکانی ناو بۆتەکە.
    """
    query = update.callback_query
    data = query.data
    uid = query.from_user.id
    lang = await get_user_lang(uid)
    await query.answer()

    # ------------------- ناڤیگەیشنی سەرەکی -------------------
    if data in ("check_sub_start", "cmd_start"):
        await start_command(update, context)
        return
    if data == "cmd_help":
        await help_command(update, context)
        return
    if data == "cmd_download":
        await query.message.reply_text(t(lang, "download_prompt"), parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True))
        return
    if data == "close":
        try:
            await query.message.delete()
        except: pass
        return

    # ------------------- پرۆفایل و ڕێکخستنەکان -------------------
    if data == "menu_profile":
        user_data = await get_user_data(uid)
        join_date = user_data.get("joined_date", "—") if user_data else "—"
        uname = query.from_user.username or "—"
        dl_count = user_data.get("downloads", 0) if user_data else 0
        
        text = (
            f"╭━━━━━━━━━━━━━━━━━━━━╮\n"
            f"  {t(lang, 'profile_title')}\n"
            f"╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
            f"{t(lang, 'profile_id', id=uid)}\n"
            f"{t(lang, 'profile_name', name=html.escape(query.from_user.first_name))}\n"
            f"{t(lang, 'profile_username', username=uname)}\n"
            f"📅 <b>بەروار:</b> {join_date}\n"
            f"{t(lang, 'profile_vip_status', status=(t(lang, 'vip_yes') if is_vip(uid) else t(lang, 'vip_no')))}\n"
            f"{t(lang, 'profile_total_dl', count=dl_count)}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn(lang)))
        return

    if data == "menu_vip":
        text = (
            f"╭━━━━━━━━━━━━━━━━━━━━╮\n"
            f"  💎 <b>{t(lang, 'btn_vip')}</b>\n"
            f"╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "✅ داونلۆدی بێسنوور و خێرا.\n"
            "✅ بێ جۆین کردنی هیچ چەناڵێک.\n"
            "✅ داونلۆدکردنی وێنەکان بە کوالێتی بەرز.\n\n"
            f"💳 <b>بۆ چالاککردنی پەیوەندی بکە بە:</b> {DEVELOPER_USERNAME}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn(lang)))
        return

    if data == "menu_settings":
        kb = [[InlineKeyboardButton("🔴🔆🟢 کوردی", callback_data="set_lang_ku")],[InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")],[InlineKeyboardButton("🇸🇦 العربية", callback_data="set_lang_ar")],
            *back_btn(lang)
        ]
        await query.edit_message_text(f"{t(lang, 'lang_select_title')}\n\n{t(lang, 'lang_select_prompt')}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("set_lang_"):
        new_lang = data.split("_")[2]
        await update_user_field(uid, "language", new_lang)
        await query.answer(f"✅ زمانەکەت گۆڕدرا بۆ {new_lang.upper()}", show_alert=True)
        await start_command(update, context)
        return

    # =================================================================================================
    # ----------------------------------- بەشی داونلۆد و وێنەکان (THE PHOTO FIX) ----------------------
    # =================================================================================================
    if data.startswith("dl_"):
        action = data.split("_")[1]
        sess = await get_user_session(uid)
        
        if not sess:
            await query.answer(t(lang, "error_session_expired"), show_alert=True)
            return

        creator = sess.get("creator", "Unknown")
        details = sess.get("details", {})
        images = sess.get("images",[])
        title = clean_title(details.get("title", ""))
        
        caption = (
            f"🎬 <b>{html.escape(title)}</b>\n"
            f"👤 <b>{html.escape(creator)}</b>\n\n"
            f"🤖 <b>@{context.bot.username}</b>"
        )
        del_kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_delete"), callback_data="close")]])

        try:
            # ----------------- ناردنی وێنەکان (چارەسەری کۆتایی) -----------------
            if action == "photos" or (action == "video" and images):
                if not images:
                    await query.answer("❌ هیچ وێنەیەک نەدۆزرایەوە!", show_alert=True)
                    return
                    
                await query.answer("⏳ تکایە کەمێک چاوەڕێ بکە، وێنەکان ئامادە دەکرێن...", show_alert=False)
                
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_photos"] += 1
                await save_settings()
                
                old_dl_count = (await get_user_data(uid) or {}).get("downloads", 0)
                await update_user_field(uid, "downloads", old_dl_count + 1)

                # تەلەگرام ڕێگە بە ١٠ وێنە دەدات لە یەک جاردا
                chunks = [images[i:i+10] for i in range(0, min(len(images), 30), 10)]
                await query.message.delete()
                
                for chunk in chunks:
                    media_group = []
                    files_to_close =[]
                    
                    for url in chunk:
                        # یەکەمجار هەوڵ دەدەین وێنەکە بخەینە ناو مێمۆرییەوە
                        bio = await fetch_image_as_bytes(url)
                        if bio:
                            media_group.append(InputMediaPhoto(media=bio))
                            files_to_close.append(bio)
                        else:
                            # ئەگەر مێمۆری شکستی هێنا، لینکەکە دەنێرین بە هیوای ئەوەی تەلەگرام بیخوێنێتەوە
                            media_group.append(InputMediaPhoto(media=url))
                    
                    if media_group:
                        media_group[0].caption = caption
                        media_group[0].parse_mode = ParseMode.HTML
                        try:
                            await context.bot.send_media_group(chat_id=uid, media=media_group)
                        except Exception as e:
                            logger.error(f"Failed to send media group: {e}")
                            # دواین هەوڵ: ناردنی لینکەکان بە تێکست ئەگەر هەموو شتێک شکستی هێنا
                            fallback_links = "\n".join([f"🖼 <a href='{u}'>لینک</a>" for u in chunk])
                            await context.bot.send_message(chat_id=uid, text=f"⚠️ نەتوانرا ڕاستەوخۆ بنێردرێت:\n\n{fallback_links}", parse_mode=ParseMode.HTML)
                    
                    # داخستنی فایلەکان بۆ پاراستنی ڕام
                    for f in files_to_close:
                        f.close()
                    
                    await asyncio.sleep(1)

            # ----------------- ناردنی ڤیدیۆ -----------------
            elif action == "video":
                v_url = details.get("video", {}).get("play", "")
                if not v_url:
                    await query.answer("❌ ڤیدیۆ بەردەست نییە!", show_alert=True)
                    return
                
                await query.answer("⏳ ئامادەکردنی ڤیدیۆ...", show_alert=False)
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_videos"] += 1
                await save_settings()
                
                old_dl_count = (await get_user_data(uid) or {}).get("downloads", 0)
                await update_user_field(uid, "downloads", old_dl_count + 1)
                
                await query.message.edit_media(InputMediaVideo(media=v_url, caption=caption, parse_mode=ParseMode.HTML), reply_markup=del_kb)

            # ----------------- ناردنی گۆرانی -----------------
            elif action == "audio":
                a_url = details.get("audio", {}).get("play", "")
                if not a_url:
                    await query.answer("❌ گۆرانی بەردەست نییە!", show_alert=True)
                    return
                
                await query.answer("⏳ ئامادەکردنی گۆرانی...", show_alert=False)
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_audios"] += 1
                await save_settings()
                
                old_dl_count = (await get_user_data(uid) or {}).get("downloads", 0)
                await update_user_field(uid, "downloads", old_dl_count + 1)
                
                music_title = f"{DEVELOPER_USERNAME}-{get_random_id()}"
                await query.message.edit_media(
                    InputMediaAudio(media=a_url, caption=caption, parse_mode=ParseMode.HTML, title=music_title, performer=DEVELOPER_USERNAME), 
                    reply_markup=del_kb
                )

        except Exception as e:
            logger.error(f"Download Action Error: {e}")
            if action == "photos" and images:
                links = "\n".join([f"🖼 <a href='{img}'>داونلۆدکردنی وێنەی {i+1}</a>" for i, img in enumerate(images[:10])])
                await context.bot.send_message(chat_id=uid, text=f"⚠️ <b>ببورە، وێنەکان زۆر گەورەن. لێرەوە دایانبەزێنە:</b>\n\n{links}", parse_mode=ParseMode.HTML)
            else:
                link_to_send = details.get("video", {}).get("play", "") if action == "video" else details.get("audio", {}).get("play", "")
                await query.message.edit_caption(f"⚠️ <b>قەبارەی فایلەکە زۆر گەورەیە، لەم لینکەوە دایبەزێنە: <a href='{link_to_send}'>لێرە کلیک بکە</a></b>", parse_mode=ParseMode.HTML, reply_markup=del_kb)
        return

    # =================================================================================================
    # ----------------------------------- پانێڵی ئەدمین و خاوەن ---------------------------------------
    # =================================================================================================
    
    if not is_admin(uid):
        return

    if data == "admin_main":
        kb = [[InlineKeyboardButton("📊 ئامارەکان", callback_data="admin_stats"), InlineKeyboardButton("📢 برۆدکاست", callback_data="admin_broadcast_ask")],[InlineKeyboardButton("🚫 بلۆک کردن", callback_data="admin_blocks"), InlineKeyboardButton("💎 VIP کردن", callback_data="admin_vips")],
            *back_btn(lang)
        ]
        maint_status = "🔴 بەڵێ" if bot_settings_global["maintenance_mode"] else "🟢 نەخێر"
        await query.edit_message_text(f"👑 <b>پانێڵی کۆنترۆڵی ئەدمین</b>\n\n🛠 دۆخی چاکسازی: {maint_status}\n🕐 {get_current_time()}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    
    elif data == "admin_stats":
        all_ids = await get_all_user_ids()
        uptime_text = get_uptime_localized(lang)
        
        text = (
            f"╭━━━━━━━━━━━━━━━━━━━━╮\n"
            f"  📊 <b>ئاماری گشتی بۆتەکە</b>\n"
            f"╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
            f"👥 <b>بەکارهێنەرەکان:</b>\n"
            f"├ گشتی تۆمارکراو: <b>{format_number(len(all_ids))}</b>\n"
            f"├ کەسانی VIP: <b>{len(vip_users)}</b>\n"
            f"└ بلۆککراوەکان: <b>{len(blocked_users)}</b>\n\n"
            f"📈 <b>ئاماری داونلۆدەکان:</b>\n"
            f"├ کۆی گشتی: <b>{format_number(bot_settings_global['total_downloads'])}</b>\n"
            f"├ ڤیدیۆکان: <b>{format_number(bot_settings_global['total_videos'])}</b>\n"
            f"├ گۆرانییەکان: <b>{format_number(bot_settings_global['total_audios'])}</b>\n"
            f"└ وێنەکان: <b>{format_number(bot_settings_global['total_photos'])}</b>\n\n"
            f"⚙️ <b>زانیاری سیستەم:</b>\n"
            f"├ کاتی کارکردن:\n  └ <code>{uptime_text}</code>\n\n"
            f"🕐 {get_current_time()}"
        )
        
        await query.edit_message_text(
            text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_refresh"), callback_data="admin_stats")], 
                *back_btn(lang, "admin_main")
            ])
        )

    elif data == "admin_broadcast_ask":
        admin_waiting_state[uid] = "broadcast_all"
        await query.message.reply_text("📢 <b>تکایە نامەکە بنێرە بۆ ناردنی گشتی:</b>\n(دەتوانیت تێکست، وێنە یان ڤیدیۆ بنێریت)", parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True))

    elif data == "admin_blocks":
        context.user_data["np_action"] = "blk_add"
        context.user_data["np_input"] = ""
        await query.edit_message_text("🚫 <b>بلۆک کردنی بەکارهێنەر</b>\n\n📟 تکایە ئایدی بەکارهێنەرەکە داخڵ بکە:", parse_mode=ParseMode.HTML, reply_markup=build_numpad("blk_add"))

    elif data == "admin_vips":
        context.user_data["np_action"] = "vip_add"
        context.user_data["np_input"] = ""
        await query.edit_message_text("💎 <b>پێدانی VIP بە بەکارهێنەر</b>\n\n📟 تکایە ئایدی بەکارهێنەرەکە داخڵ بکە:", parse_mode=ParseMode.HTML, reply_markup=build_numpad("vip_add"))

    # ------------------- تەنها بۆ خاوەن (OWNER ONLY) -------------------
    if not is_owner(uid):
        return

    if data == "owner_main":
        kb = [[InlineKeyboardButton("👥 ئەدمینەکان", callback_data="owner_admins"), InlineKeyboardButton("⚙️ ڕێکخستن", callback_data="owner_bot_settings")],[InlineKeyboardButton("🗑 ڕیسێتی ئامار", callback_data="owner_reset_stats_ask"), InlineKeyboardButton("💾 بەکئەپ", callback_data="owner_backup")],
            *back_btn(lang, "cmd_start")
        ]
        await query.edit_message_text(f"🔱 <b>پانێڵی تایبەتی خاوەنی بۆت</b>\n\n👑 خاوەن: <code>{OWNER_ID}</code>\n🕐 {get_current_time()}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    
    elif data == "owner_admins":
        context.user_data["np_action"] = "adm_add"
        context.user_data["np_input"] = ""
        await query.edit_message_text("➕ <b>زیادکردنی ئەدمینی نوێ</b>\n\n📟 تکایە ئایدی کەسەکە داخڵ بکە:", parse_mode=ParseMode.HTML, reply_markup=build_numpad("adm_add"))
        
    elif data == "owner_bot_settings":
        maint_text = "🔴 دۆخی چاکسازی (ON)" if bot_settings_global["maintenance_mode"] else "🟢 دۆخی چاکسازی (OFF)"
        kb = [[InlineKeyboardButton(maint_text, callback_data="owner_toggle_maint")], *back_btn(lang, "owner_main")]
        await query.edit_message_text("⚙️ <b>ڕێکخستنە هەستیارەکانی بۆت</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        
    elif data == "owner_toggle_maint":
        bot_settings_global["maintenance_mode"] = not bot_settings_global["maintenance_mode"]
        await save_settings()
        await query.answer("دۆخی چاکسازی گۆڕدرا", show_alert=True)
        query.data = "owner_bot_settings"
        await button_handler(update, context)
        
    elif data == "owner_backup":
        await query.answer("⏳ بەکئەپ ئامادە دەکرێت...", show_alert=False)
        all_users = await get_all_users_data()
        backup_data = {
            "timestamp": get_current_time(),
            "settings": bot_settings_global,
            "admins": list(admins_list),
            "channels": forced_channels,
            "blocked": list(blocked_users),
            "vips": list(vip_users),
            "total_users": len(all_users),
        }
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
        bio = BytesIO(backup_json.encode())
        bio.name = f"backup_{datetime.now().strftime('%Y%m%d')}.json"
        
        try:
            await context.bot.send_document(chat_id=uid, document=bio, caption=t(lang, "backup_caption", time=get_current_time()), parse_mode=ParseMode.HTML)
        except Exception as e:
            await query.message.reply_text(f"❌ هەڵە لە ناردنی بەکئەپ: {e}")

    elif data == "owner_reset_stats_ask":
        kb = [[InlineKeyboardButton(t(lang, "btn_confirm"), callback_data="owner_reset_stats_do"), InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="owner_main")]]
        await query.edit_message_text(t(lang, "confirm_reset_stats"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "owner_reset_stats_do":
        bot_settings_global["total_downloads"] = 0
        bot_settings_global["total_videos"] = 0
        bot_settings_global["total_audios"] = 0
        bot_settings_global["total_photos"] = 0
        await save_settings()
        await query.edit_message_text(t(lang, "stats_reset_done"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn(lang, "owner_main")))

# ===================================================================================================
# ----------------------------------- ١٢. وەرگرتنی نامە و تێکست (MESSAGE HANDLER) -------------------
# ===================================================================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    uid = update.effective_user.id
    msg = update.message
    txt = msg.text.strip()
    lang = await get_user_lang(uid)

    # ----------------- مامەڵەکردن لەگەڵ وەڵامەکانی ئەدمین -----------------
    if is_admin(uid) and uid in admin_waiting_state:
        state = admin_waiting_state.pop(uid)
        
        if state == "broadcast_all":
            all_ids = await get_all_user_ids()
            success, fail = 0, 0
            status = await msg.reply_text("⏳ <b>خەریکی ناردنی برۆدکاستم...</b>", parse_mode=ParseMode.HTML)
            
            for tuid in all_ids:
                try:
                    await context.bot.copy_message(chat_id=tuid, from_chat_id=msg.chat_id, message_id=msg.message_id)
                    success += 1
                    await asyncio.sleep(0.04) # خۆپاراستن لە سپام
                except:
                    fail += 1
            
            await status.edit_text(t(lang, "broadcast_sent", success=success, fail=fail), parse_mode=ParseMode.HTML)
            return

    # ----------------- پرۆسێس کردنی لینکی تیکتۆک -----------------
    if is_blocked(uid) or "tiktok.com" not in txt:
        return 
    
    if bot_settings_global["maintenance_mode"] and not is_admin(uid):
        await msg.reply_text(t(lang, "error_maintenance"), parse_mode=ParseMode.HTML)
        return
        
    is_sub, not_joined = await check_user_subscription(uid, context)
    bypass = (is_admin(uid) and bot_settings_global.get("admin_bypass_join", True)) or (is_vip(uid) and bot_settings_global.get("vip_bypass_join", True))
    
    if not is_sub and not bypass:
        kb = [[InlineKeyboardButton(t(lang, "btn_join_channel", ch=ch), url=f"https://t.me/{ch.replace('@','')}")] for ch in not_joined]
        kb.append([InlineKeyboardButton(t(lang, "btn_check_join"), callback_data="check_sub_start")])
        await msg.reply_text(t(lang, "force_join_text"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return

    status_msg = await msg.reply_text("🔍 <b>دەگەڕێم بەدوای پۆستەکەدا... کەمێک چاوەڕێ بە...</b>", parse_mode=ParseMode.HTML)

    try:
        result = await fetch_tiktok_data(txt)
        if not result:
            await status_msg.edit_text(t(lang, "error_invalid_link"), parse_mode=ParseMode.HTML)
            return

        creator, details, images = parse_api_response(result["data"])
        await save_user_session(uid, {"creator": creator, "details": details, "images": images})

        title = clean_title(details.get("title", ""))
        stats = details.get("stats", {})
        views = format_number(stats.get("views", 0) or stats.get("play_count", 0))
        likes = format_number(stats.get("likes", 0) or stats.get("digg_count", 0))
        comments = format_number(stats.get("comments", 0) or stats.get("comment_count", 0))

        caption = (
            f"{t(lang, 'download_found')}\n\n"
            f"📝 <b>ناونیشان:</b> {html.escape(title)}\n"
            f"👤 <b>خاوەن:</b> {html.escape(creator)}\n\n"
            f"👁 {views}   ❤️ {likes}   💬 {comments}\n\n"
            f"🤖 <b>@{context.bot.username}</b>"
        )

        if images:
            kb =[[InlineKeyboardButton(t(lang, "btn_photos", count=len(images)), callback_data="dl_photos")], 
                [InlineKeyboardButton(t(lang, "btn_audio"), callback_data="dl_audio")], 
                [InlineKeyboardButton(t(lang, "btn_delete"), callback_data="close")]
            ]
        else:
            kb = [[InlineKeyboardButton(t(lang, "btn_video"), callback_data="dl_video")],[InlineKeyboardButton(t(lang, "btn_audio"), callback_data="dl_audio")],[InlineKeyboardButton(t(lang, "btn_delete"), callback_data="close")]
            ]

        # هێنانەوەی کەڤەری ڤیدیۆکە
        cover_url = details.get("cover", {}).get("cover", "") or details.get("origin_cover", "") or (images[0] if images else "")
        
        if cover_url:
            try:
                await status_msg.edit_media(InputMediaPhoto(cover_url, caption=caption, parse_mode=ParseMode.HTML), reply_markup=InlineKeyboardMarkup(kb))
            except Exception as e:
                logger.warning(f"Failed to load cover, sending as text instead: {e}")
                await status_msg.edit_text(caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await status_msg.edit_text(caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

    except Exception as e:
        logger.error(f"General Download Error: {e}")
        try:
            await status_msg.edit_text(t(lang, "error_download_fail"), parse_mode=ParseMode.HTML)
        except:
            pass

# ===================================================================================================
# ----------------------------------- ١٣. کارپێکردنی کۆتایی (INITIALIZATION) ------------------------
# ===================================================================================================

# دروستکردنی ئەپڵیکەیشنی بۆت
ptb_app = ApplicationBuilder().token(TOKEN).build()

# زیادکردنی هاندلەرەکان
ptb_app.add_handler(CommandHandler(["start", "menu"], start_command))
ptb_app.add_handler(CommandHandler("help", help_command))
ptb_app.add_handler(CallbackQueryHandler(numpad_handler, pattern=r"^(np_|chi_)"))
ptb_app.add_handler(CallbackQueryHandler(button_handler))
ptb_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))

@app.post("/api/main")
async def webhook(req: Request):
    """
    ئەمە ئەو بەشەیە کە ڤێرسڵ (Vercel) پەیوەندی پێوە دەکات.
    """
    if not ptb_app.running:
        await ptb_app.initialize()
        
    await load_settings()
    data = await req.json()
    await ptb_app.process_update(Update.de_json(data, ptb_app.bot))
    return {"ok": True, "status": "processed"}

@app.get("/api/main")
async def health():
    """
    بۆ پشکنینی ئەوەی سێرڤەرەکە بەخەبەرە یان نا.
    """
    return {
        "status": "active",
        "time": get_current_time(),
        "developer": DEVELOPER_USERNAME
    }

# ===================================================================================================
# ========================================= END OF FILE =============================================
# ===================================================================================================
