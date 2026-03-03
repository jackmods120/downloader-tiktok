# ==============================================================================
# ==============================================================================
# ==                                                                          ==
# ==              TIKTOK DOWNLOADER - ULTRA LEGENDARY EDITION v6.0            ==
# ==                                                                          ==
# ==   • Dev:         @j4ck_721s (﮼جــاڪ ,.⏳🤎)                               ==
# ==   • Version:     6.0 (Ultra Legendary)                                   ==
# ==   • Features:    Multi-Language, Mega Owner Panel, VIP, Photo Fix        ==
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
import json
from datetime import datetime
from fastapi import FastAPI, Request
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
from telegram.error import TelegramError, BadRequest, Forbidden

# ==============================================================================
# ------------------------- ڕێکخستنە سەرەکییەکان (CONFIG) ----------------------
# ==============================================================================
TOKEN             = os.getenv("BOT_TOKEN")
API_URL           = "https://www.api.hyper-bd.site/Tiktok/?url="
API_URL_BACKUP    = "https://www.tikwm.com/api/?url="   # بەکاپ API
CHANNEL_URL       = "https://t.me/jack_721_mod"
DB_URL            = os.getenv("DB_URL")
DB_SECRET         = os.getenv("DB_SECRET")

# زانیاری خاوەن
OWNER_ID           = 5977475208
DEVELOPER_USERNAME = "@j4ck_721s"

# ==============================================================================
# ------------------------- گۆڕاوە گشتییەکان (GLOBALS) -------------------------
# ==============================================================================
admins_list        : set  = {OWNER_ID}
forced_channels    : list = []
blocked_users      : set  = set()
vip_users          : set  = set()
bot_settings_global: dict = {
    "maintenance_mode"  : False,
    "welcome_msg"       : "",
    "total_downloads"   : 0,
    "total_videos"      : 0,
    "total_audios"      : 0,
    "total_photos"      : 0,
    "total_users"       : 0,
    "bot_name"          : "TikTok Downloader",
    "bot_version"       : "6.0",
    "photo_mode"        : "auto",   # auto | force_photos | force_video
    "max_photos"        : 10,
    "api_timeout"       : 60,
    "allow_forward"     : True,
    "vip_bypass_join"   : True,
    "admin_bypass_join" : True,
    "log_downloads"     : True,
    "auto_delete_sec"   : 0,        # 0 = بێ سڕینەوەی خۆکار
}

SESSION_EXPIRE  = 600
API_TIMEOUT     = 60
START_TIME      = time.time()

# دۆخی چاوەڕوانی کردنی ئەدمین
admin_waiting_state: dict[int, str] = {}

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s | %(levelname)s | %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
app    = FastAPI()

# ==============================================================================
# ----------------------------- سیستەمی فرە-زمان (LANGUAGES) -------------------
# ==============================================================================
LANGUAGES = {
    "ku": {
        # ── سڵاو ──────────────────────────────────────────────────────────────
        "welcome_title"         : "👋 <b>سڵاو {name} {badge}</b>",
        "welcome_intro"         : "🤖 <b>من بۆتێکی پێشکەوتووم بۆ دابەزاندنی تیکتۆک!</b>",
        "welcome_features"      : "📥 دەتوانیت ڤیدیۆ، وێنەکان (Slideshow) و گۆرانی دابەزێنیت.",
        "welcome_prompt"        : "👇 <b>لینک بنێرە یان دوگمە دابگرە:</b>",
        # ── دوگمەکان ─────────────────────────────────────────────────────────
        "btn_download"          : "📥 دابەزاندنی تیکتۆک",
        "btn_profile"           : "👤 پرۆفایلی من",
        "btn_vip"               : "💎 بەشی VIP",
        "btn_settings"          : "⚙️ ڕێکخستنەکان",
        "btn_help"              : "ℹ️ ڕێنمایی و یارمەتی",
        "btn_channel"           : "📢 کەناڵی فەرمی بۆت",
        "btn_admin_panel"       : "👑 پانێڵی پێشکەوتووی ئەدمین 👑",
        "btn_owner_panel"       : "🔱 پانێڵی خاوەن 🔱",
        "btn_back"              : "🔙 گەڕانەوە",
        "btn_delete"            : "🗑 سڕینەوە",
        "btn_refresh"           : "🔄 نوێکردنەوە",
        "btn_confirm"           : "✅ دڵنیام",
        "btn_cancel"            : "❌ هەڵوەشاندنەوە",
        # ── جۆین ────────────────────────────────────────────────────────────
        "force_join_text"       : "🔒 <b>جۆینی ناچاری</b>\nبۆ بەکارهێنان، تکایە جۆینی ئەم چەناڵانە بکە:",
        "btn_join_channel"      : "📢 جۆین کردن: {ch}",
        "btn_check_join"        : "✅ جۆینم کرد، دەستپێکردن",
        # ── یارمەتی ──────────────────────────────────────────────────────────
        "help_title"            : "📚 <b>ڕێنمایی بەکارهێنان</b>",
        "help_text"             : (
            "<b>📱 چۆن دایبەزێنم؟</b>\n"
            "1️⃣ لە تیکتۆک 'Share' دابگرە و 'Copy Link' بکە.\n"
            "2️⃣ لینکەکە لێرە بنێرە وەک نامەیەک.\n"
            "3️⃣ فۆرماتێک هەڵبژێرە و دابەزێنە!\n\n"
            "<b>📥 چی دابەزێنم?</b>\n"
            "🎥 ڤیدیۆ بێ لۆگۆ\n"
            "📸 وێنەکانی Slideshow\n"
            "🎵 گۆرانی / MP3\n\n"
            "<b>ℹ️ زانیاریی تر:</b>\n"
            "• VIP بەکارهێنەرەکان بێ جۆین چەناڵ دەتوانن بەکاربێنن.\n"
            f"• پەیوەندی بکە بە: {DEVELOPER_USERNAME}"
        ),
        "download_prompt"       : "<b>🔗 تکایە لینکی تیکتۆکەکە لێرەدا پەیست بکە و بۆمی بنێرە:</b>",
        # ── پرۆفایل ──────────────────────────────────────────────────────────
        "profile_title"         : "👤 <b>پرۆفایلی بەکارهێنەر</b>",
        "profile_id"            : "🆔 <b>ئایدی:</b> <code>{id}</code>",
        "profile_name"          : "👤 <b>ناو:</b> {name}",
        "profile_username"      : "🔗 <b>یوزەرنەیم:</b> @{username}",
        "profile_join_date"     : "📅 <b>بەروار تۆمارکردن:</b> {date}",
        "profile_vip_status"    : "💎 <b>هەژماری VIP:</b> {status}",
        "profile_total_dl"      : "📥 <b>داونلۆدەکانت:</b> {count}",
        "vip_yes"               : "بەڵێ 💎",
        "vip_no"                : "نەخێر (Free)",
        # ── داونلۆد ──────────────────────────────────────────────────────────
        "download_found"        : "✅ <b>بە سەرکەوتوویی دۆزرایەوە!</b>",
        "download_title"        : "📝 <b>پۆست:</b> {title}",
        "download_owner"        : "👤 <b>خاوەن:</b> {owner}",
        "download_views"        : "👁 <code>{views}</code> بینەر",
        "download_likes"        : "❤️ <code>{likes}</code> لایک",
        "download_comments"     : "💬 <code>{comments}</code> کۆمێنت",
        "btn_video"             : "🎥 داونلۆدی ڤیدیۆ (بێ لۆگۆ)",
        "btn_photos"            : "📸 داونلۆدی وێنەکان ({count})",
        "btn_audio"             : "🎵 داونلۆدی گۆرانی (MP3)",
        # ── هەڵەکان ──────────────────────────────────────────────────────────
        "error_admin_only"      : "⛔ ئەم بەشە تەنیا بۆ ئەدمینەکانە!",
        "error_owner_only"      : "⛔ ئەم بەشە تەنیا بۆ خاوەنی سەرەکییە!",
        "error_blocked"         : "⛔ <b>ببورە، تۆ بلۆک کراویت.</b>",
        "error_maintenance"     : "🛠 <b>بۆتەکە لە باری چاکسازیدایە. تکایە چاوەڕوان بە!</b>",
        "error_session_expired" : "⚠️ کاتەکەت بەسەرچوو، تکایە لینکەکە دووبارە بنێرەوە.",
        "error_download_fail"   : "❌ هەڵەیەک ڕوویدا. تکایە دووبارە هەوڵبدەوە.",
        "error_invalid_link"    : "❌ لینکەکە دروست نییە یان بلۆک کراوە!",
        # ── زمان ────────────────────────────────────────────────────────────
        "lang_select_title"     : "🌍 <b>زمان هەڵبژێرە | Select Language</b>",
        "lang_select_prompt"    : "تکایە زمانێک هەڵبژێرە:",
        # ── پانێڵی ئەدمین ────────────────────────────────────────────────────
        "no_users_found"        : "📭 هیچ بەکارهێنەرێک نەدۆزرایەوە.",
        "broadcast_sent"        : "📢 <b>برۆدکاست ئەنجامدرا!</b>\n✅ گەیشت بە: <b>{success}</b>\n❌ نەگەیشت: <b>{fail}</b>",
        "admin_added"           : "✅ ئەدمینی نوێ زیادکرا: <code>{id}</code>",
        "admin_removed"         : "✅ ئەدمین لابرا: <code>{id}</code>",
        "vip_added"             : "✅ VIP زیادکرا: <code>{id}</code>",
        "vip_removed"           : "✅ VIP لابرا: <code>{id}</code>",
        "user_blocked"          : "✅ بەکارهێنەر بلۆک کرا: <code>{id}</code>",
        "user_unblocked"        : "✅ بلۆکی بەکارهێنەر لادرا: <code>{id}</code>",
        "channel_added"         : "✅ چەناڵ زیادکرا: <b>{ch}</b>",
        "channel_removed"       : "✅ چەناڵ لابرا: <b>{ch}</b>",
        "invalid_id"            : "❌ ئایدی دروست نییە. ئایدیەکی ژمارەیی بنێرە.",
        "send_user_id"          : "🆔 تکایە ئایدی بەکارهێنەرەکە بنێرە:",
        "send_channel"          : "📢 تکایە یوزەرنەیمی چەناڵەکە بنێرە (بە @ دەستپێدەکات):",
        "send_broadcast_msg"    : "📢 تکایە نامەکە بنێرە (هەر جۆرێک - تێکست، وێنە، ڤیدیۆ):",
        "not_owner"             : "⛔ تەنیا خاوەن دەتوانێت ئەم کارە بکات!",
        "send_new_value"        : "✏️ نرخی نوێ بنێرە:",
        "setting_updated"       : "✅ ڕێکخستن نوێکرایەوە!",
        "user_not_found"        : "⚠️ بەکارهێنەر نەدۆزرایەوە لە داتابەیسدا.",
        "user_info_text"        : (
            "👤 <b>زانیاری بەکارهێنەر</b>\n\n"
            "🆔 ئایدی: <code>{id}</code>\n"
            "👤 ناو: {name}\n"
            "🔗 یوزەرنەیم: @{username}\n"
            "📅 تۆمارکردن: {date}\n"
            "💎 VIP: {vip}\n"
            "🚫 بلۆک: {blocked}"
        ),
        "msg_sent_to_user"      : "✅ نامەکە نێردرا بۆ بەکارهێنەر.",
        "send_msg_to_user"      : "✉️ نامەکەت بنووسە بنێرە بۆ بەکارهێنەر <code>{id}</code>:",
        "confirm_reset_stats"   : "⚠️ <b>دڵنیای دەتەوێت ئامارەکان ڕیسێت بکەیت؟</b>",
        "stats_reset_done"      : "✅ هەموو ئامارەکان ڕیسێت کران.",
        "confirm_reset_users"   : "⚠️ <b>دڵنیای دەتەوێت هەموو بەکارهێنەرەکان بسڕیتەوە؟</b>",
        "users_reset_done"      : "✅ هەموو بەکارهێنەرەکان سڕانەوە.",
        "backup_caption"        : "💾 <b>بەکئەپی داتابەیس</b>\n🕐 {time}",
        "send_welcome_msg"      : "✏️ نامەی خۆشامەدێکە بنووسە (HTML پشتگیری دەکرێت):",
        "welcome_msg_set"       : "✅ نامەی خۆشامەدێ نوێکرایەوە.",
    },
    "en": {
        "welcome_title"         : "👋 <b>Welcome {name} {badge}</b>",
        "welcome_intro"         : "🤖 <b>I am an advanced TikTok downloader bot!</b>",
        "welcome_features"      : "📥 Download videos, slideshows, and audio.",
        "welcome_prompt"        : "👇 <b>Send a link or press a button:</b>",
        "btn_download"          : "📥 Download TikTok",
        "btn_profile"           : "👤 My Profile",
        "btn_vip"               : "💎 VIP Section",
        "btn_settings"          : "⚙️ Settings",
        "btn_help"              : "ℹ️ Help & Guide",
        "btn_channel"           : "📢 Official Bot Channel",
        "btn_admin_panel"       : "👑 Advanced Admin Panel 👑",
        "btn_owner_panel"       : "🔱 Owner Panel 🔱",
        "btn_back"              : "🔙 Back",
        "btn_delete"            : "🗑 Delete",
        "btn_refresh"           : "🔄 Refresh",
        "btn_confirm"           : "✅ Confirm",
        "btn_cancel"            : "❌ Cancel",
        "force_join_text"       : "🔒 <b>Forced Join</b>\nTo use the bot, please join these channels:",
        "btn_join_channel"      : "📢 Join: {ch}",
        "btn_check_join"        : "✅ I Have Joined, Start",
        "help_title"            : "📚 <b>How to Use</b>",
        "help_text"             : (
            "<b>📱 How do I download?</b>\n"
            "1️⃣ In TikTok, press 'Share' then 'Copy Link'.\n"
            "2️⃣ Send the link here as a message.\n"
            "3️⃣ Choose a format and download!\n\n"
            "<b>📥 What can I download?</b>\n"
            "🎥 Video without watermark\n"
            "📸 Slideshow photos\n"
            "🎵 Audio / MP3\n\n"
            "<b>ℹ️ More info:</b>\n"
            "• VIP users can use the bot without joining channels.\n"
            f"• Contact: {DEVELOPER_USERNAME}"
        ),
        "download_prompt"       : "<b>🔗 Please paste the TikTok link here and send it to me:</b>",
        "profile_title"         : "👤 <b>User Profile</b>",
        "profile_id"            : "🆔 <b>ID:</b> <code>{id}</code>",
        "profile_name"          : "👤 <b>Name:</b> {name}",
        "profile_username"      : "🔗 <b>Username:</b> @{username}",
        "profile_join_date"     : "📅 <b>Registered:</b> {date}",
        "profile_vip_status"    : "💎 <b>VIP Account:</b> {status}",
        "profile_total_dl"      : "📥 <b>Your Downloads:</b> {count}",
        "vip_yes"               : "Yes 💎",
        "vip_no"                : "No (Free)",
        "download_found"        : "✅ <b>Successfully Found!</b>",
        "download_title"        : "📝 <b>Post:</b> {title}",
        "download_owner"        : "👤 <b>Owner:</b> {owner}",
        "download_views"        : "👁 <code>{views}</code> Views",
        "download_likes"        : "❤️ <code>{likes}</code> Likes",
        "download_comments"     : "💬 <code>{comments}</code> Comments",
        "btn_video"             : "🎥 Download Video (No Watermark)",
        "btn_photos"            : "📸 Download Photos ({count})",
        "btn_audio"             : "🎵 Download Audio (MP3)",
        "error_admin_only"      : "⛔ This section is for admins only!",
        "error_owner_only"      : "⛔ This section is for the main owner only!",
        "error_blocked"         : "⛔ <b>Sorry, you have been blocked.</b>",
        "error_maintenance"     : "🛠 <b>The bot is in maintenance mode. Please wait!</b>",
        "error_session_expired" : "⚠️ Your session has expired. Please send the link again.",
        "error_download_fail"   : "❌ An error occurred. Please try again.",
        "error_invalid_link"    : "❌ Invalid or blocked link!",
        "lang_select_title"     : "🌍 <b>Select Language | هەڵبژاردنی زمان</b>",
        "lang_select_prompt"    : "Please select a language:",
        "no_users_found"        : "📭 No users found.",
        "broadcast_sent"        : "📢 <b>Broadcast Done!</b>\n✅ Sent: <b>{success}</b>\n❌ Failed: <b>{fail}</b>",
        "admin_added"           : "✅ New admin added: <code>{id}</code>",
        "admin_removed"         : "✅ Admin removed: <code>{id}</code>",
        "vip_added"             : "✅ VIP added: <code>{id}</code>",
        "vip_removed"           : "✅ VIP removed: <code>{id}</code>",
        "user_blocked"          : "✅ User blocked: <code>{id}</code>",
        "user_unblocked"        : "✅ User unblocked: <code>{id}</code>",
        "channel_added"         : "✅ Channel added: <b>{ch}</b>",
        "channel_removed"       : "✅ Channel removed: <b>{ch}</b>",
        "invalid_id"            : "❌ Invalid ID. Please send a numeric ID.",
        "send_user_id"          : "🆔 Please send the user's ID:",
        "send_channel"          : "📢 Please send the channel username (starts with @):",
        "send_broadcast_msg"    : "📢 Please send your broadcast message (any type):",
        "not_owner"             : "⛔ Only the owner can do this!",
        "send_new_value"        : "✏️ Send the new value:",
        "setting_updated"       : "✅ Setting updated!",
        "user_not_found"        : "⚠️ User not found in database.",
        "user_info_text"        : (
            "👤 <b>User Information</b>\n\n"
            "🆔 ID: <code>{id}</code>\n"
            "👤 Name: {name}\n"
            "🔗 Username: @{username}\n"
            "📅 Registered: {date}\n"
            "💎 VIP: {vip}\n"
            "🚫 Blocked: {blocked}"
        ),
        "msg_sent_to_user"      : "✅ Message sent to user.",
        "send_msg_to_user"      : "✉️ Write your message to send to user <code>{id}</code>:",
        "confirm_reset_stats"   : "⚠️ <b>Are you sure you want to reset all stats?</b>",
        "stats_reset_done"      : "✅ All stats have been reset.",
        "confirm_reset_users"   : "⚠️ <b>Are you sure you want to delete all users?</b>",
        "users_reset_done"      : "✅ All users have been deleted.",
        "backup_caption"        : "💾 <b>Database Backup</b>\n🕐 {time}",
        "send_welcome_msg"      : "✏️ Write the new welcome message (HTML supported):",
        "welcome_msg_set"       : "✅ Welcome message updated.",
    },
    "ar": {
        "welcome_title"         : "👋 <b>أهلاً بك {name} {badge}</b>",
        "welcome_intro"         : "🤖 <b>أنا بوت متقدم لتحميل فيديوهات تيك توك!</b>",
        "welcome_features"      : "📥 يمكنك تحميل الفيديوهات وعروض الصور والصوت.",
        "welcome_prompt"        : "👇 <b>أرسل رابطًا أو اضغط على زر:</b>",
        "btn_download"          : "📥 تحميل من تيك توك",
        "btn_profile"           : "👤 ملفي الشخصي",
        "btn_vip"               : "💎 قسم VIP",
        "btn_settings"          : "⚙️ الإعدادات",
        "btn_help"              : "ℹ️ المساعدة والدليل",
        "btn_channel"           : "📢 قناة البوت الرسمية",
        "btn_admin_panel"       : "👑 لوحة تحكم الأدمن المتقدمة 👑",
        "btn_owner_panel"       : "🔱 لوحة تحكم المالك 🔱",
        "btn_back"              : "🔙 رجوع",
        "btn_delete"            : "🗑 حذف",
        "btn_refresh"           : "🔄 تحديث",
        "btn_confirm"           : "✅ تأكيد",
        "btn_cancel"            : "❌ إلغاء",
        "force_join_text"       : "🔒 <b>الاشتراك الإجباري</b>\nلاستخدام البوت, يرجى الانضمام إلى هذه القنوات:",
        "btn_join_channel"      : "📢 انضمام: {ch}",
        "btn_check_join"        : "✅ لقد انضممت، إبدأ",
        "help_title"            : "📚 <b>كيفية الاستخدام</b>",
        "help_text"             : (
            "<b>📱 كيف أحمل؟</b>\n"
            "1️⃣ في تيك توك، اضغط على 'مشاركة' ثم 'نسخ الرابط'.\n"
            "2️⃣ أرسل الرابط هنا كرسالة.\n"
            "3️⃣ اختر الصيغة وقم بالتحميل!\n\n"
            "<b>📥 ماذا يمكنني تحميله؟</b>\n"
            "🎥 فيديو بدون علامة مائية\n"
            "📸 صور عرض الشرائح\n"
            "🎵 الصوت / MP3\n\n"
            "<b>ℹ️ معلومات إضافية:</b>\n"
            "• يمكن لمستخدمي VIP استخدام البوت دون الاشتراك في القنوات.\n"
            f"• للتواصل: {DEVELOPER_USERNAME}"
        ),
        "download_prompt"       : "<b>🔗 الرجاء لصق رابط تيك توك هنا وإرساله لي:</b>",
        "profile_title"         : "👤 <b>الملف الشخصي للمستخدم</b>",
        "profile_id"            : "🆔 <b>المعرف:</b> <code>{id}</code>",
        "profile_name"          : "👤 <b>الاسم:</b> {name}",
        "profile_username"      : "🔗 <b>اسم المستخدم:</b> @{username}",
        "profile_join_date"     : "📅 <b>تاريخ التسجيل:</b> {date}",
        "profile_vip_status"    : "💎 <b>حساب VIP:</b> {status}",
        "profile_total_dl"      : "📥 <b>تنزيلاتك:</b> {count}",
        "vip_yes"               : "نعم 💎",
        "vip_no"                : "لا (مجاني)",
        "download_found"        : "✅ <b>تم العثور عليه بنجاح!</b>",
        "download_title"        : "📝 <b>المنشور:</b> {title}",
        "download_owner"        : "👤 <b>المالك:</b> {owner}",
        "download_views"        : "👁 <code>{views}</code> مشاهدات",
        "download_likes"        : "❤️ <code>{likes}</code> إعجابات",
        "download_comments"     : "💬 <code>{comments}</code> تعليقات",
        "btn_video"             : "🎥 تحميل الفيديو (بدون علامة مائية)",
        "btn_photos"            : "📸 تحميل الصور ({count})",
        "btn_audio"             : "🎵 تحميل الصوت (MP3)",
        "error_admin_only"      : "⛔ هذا القسم مخصص للمسؤولين فقط!",
        "error_owner_only"      : "⛔ هذا القسم مخصص للمالك الرئيسي فقط!",
        "error_blocked"         : "⛔ <b>عذراً، لقد تم حظرك.</b>",
        "error_maintenance"     : "🛠 <b>البوت في وضع الصيانة. يرجى الانتظار!</b>",
        "error_session_expired" : "⚠️ انتهت صلاحية جلستك. يرجى إرسال الرابط مرة أخرى.",
        "error_download_fail"   : "❌ حدث خطأ. يرجى المحاولة مرة أخرى.",
        "error_invalid_link"    : "❌ رابط غير صالح أو محظور!",
        "lang_select_title"     : "🌍 <b>اختر اللغة | Select Language</b>",
        "lang_select_prompt"    : "الرجاء اختيار لغة:",
        "no_users_found"        : "📭 لم يتم العثور على أي مستخدم.",
        "broadcast_sent"        : "📢 <b>تم الإرسال الجماعي!</b>\n✅ تم: <b>{success}</b>\n❌ فشل: <b>{fail}</b>",
        "admin_added"           : "✅ تمت إضافة مسؤول جديد: <code>{id}</code>",
        "admin_removed"         : "✅ تمت إزالة المسؤول: <code>{id}</code>",
        "vip_added"             : "✅ تمت إضافة VIP: <code>{id}</code>",
        "vip_removed"           : "✅ تمت إزالة VIP: <code>{id}</code>",
        "user_blocked"          : "✅ تم حظر المستخدم: <code>{id}</code>",
        "user_unblocked"        : "✅ تم رفع الحظر: <code>{id}</code>",
        "channel_added"         : "✅ تمت إضافة القناة: <b>{ch}</b>",
        "channel_removed"       : "✅ تمت إزالة القناة: <b>{ch}</b>",
        "invalid_id"            : "❌ معرف غير صالح. يرجى إرسال معرف رقمي.",
        "send_user_id"          : "🆔 يرجى إرسال معرف المستخدم:",
        "send_channel"          : "📢 يرجى إرسال اسم مستخدم القناة (يبدأ بـ @):",
        "send_broadcast_msg"    : "📢 يرجى إرسال رسالتك (أي نوع):",
        "not_owner"             : "⛔ فقط المالك يمكنه فعل هذا!",
        "send_new_value"        : "✏️ أرسل القيمة الجديدة:",
        "setting_updated"       : "✅ تم تحديث الإعداد!",
        "user_not_found"        : "⚠️ لم يتم العثور على المستخدم في قاعدة البيانات.",
        "user_info_text"        : (
            "👤 <b>معلومات المستخدم</b>\n\n"
            "🆔 المعرف: <code>{id}</code>\n"
            "👤 الاسم: {name}\n"
            "🔗 اسم المستخدم: @{username}\n"
            "📅 تاريخ التسجيل: {date}\n"
            "💎 VIP: {vip}\n"
            "🚫 محظور: {blocked}"
        ),
        "msg_sent_to_user"      : "✅ تم إرسال الرسالة للمستخدم.",
        "send_msg_to_user"      : "✉️ اكتب رسالتك للمستخدم <code>{id}</code>:",
        "confirm_reset_stats"   : "⚠️ <b>هل أنت متأكد من إعادة تعيين الإحصائيات؟</b>",
        "stats_reset_done"      : "✅ تمت إعادة تعيين جميع الإحصائيات.",
        "confirm_reset_users"   : "⚠️ <b>هل أنت متأكد من حذف جميع المستخدمين؟</b>",
        "users_reset_done"      : "✅ تم حذف جميع المستخدمين.",
        "backup_caption"        : "💾 <b>نسخة احتياطية من قاعدة البيانات</b>\n🕐 {time}",
        "send_welcome_msg"      : "✏️ اكتب رسالة الترحيب الجديدة (HTML مدعوم):",
        "welcome_msg_set"       : "✅ تم تحديث رسالة الترحيب.",
    },
}

async def get_user_lang(user_id: int) -> str:
    async with httpx.AsyncClient(timeout=10) as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}/language"))
            if r.status_code == 200 and r.json():
                return str(r.json())
        except:
            pass
    return "ku"

def t(lang: str, key: str, **kwargs) -> str:
    text = LANGUAGES.get(lang, LANGUAGES["ku"]).get(key, LANGUAGES["ku"].get(key, key))
    try:
        return text.format(**kwargs)
    except:
        return text

# ==============================================================================
# -------------------------- یارمەتیدەرەکان (HELPERS) --------------------------
# ==============================================================================

def get_random_id(length: int = 8) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def clean_title(title: str) -> str:
    if not title:
        return "TikTok"
    cleaned = re.sub(r'[\\/*?:"<>|#]', '', title)
    return cleaned[:80].strip()

def firebase_url(path: str) -> str:
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d | %I:%M:%S %p")

def get_uptime() -> str:
    s = int(time.time() - START_TIME)
    d, r   = divmod(s, 86400)
    h, r   = divmod(r, 3600)
    m, sec = divmod(r, 60)
    return f"{d}ڕۆژ {h}کاتژمێر {m}خولەک {sec}چرکە"

def format_number(n) -> str:
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
    return [[InlineKeyboardButton(t(lang, "btn_back"), callback_data=target)]]

def divider() -> str:
    return "━━━━━━━━━━━━━━━━━━━"

# ==============================================================================
# ------------------------- پشکنینە ئەمنییەکان (SECURITY) ----------------------
# ==============================================================================

def is_owner(uid: int) -> bool:   return uid == OWNER_ID
def is_admin(uid: int) -> bool:   return uid in admins_list or uid == OWNER_ID
def is_blocked(uid: int) -> bool: return uid in blocked_users
def is_vip(uid: int) -> bool:     return uid in vip_users or uid == OWNER_ID

async def check_user_subscription(user_id: int, context) -> tuple[bool, list]:
    if not forced_channels:
        return True, []
    not_joined = []
    for ch in forced_channels:
        try:
            m = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                not_joined.append(ch)
        except:
            pass
    return len(not_joined) == 0, not_joined

# ==============================================================================
# ----------------------------- داتابەیس (DATABASE) ----------------------------
# ==============================================================================

async def load_settings():
    global admins_list, forced_channels, blocked_users, vip_users, bot_settings_global
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(firebase_url("system_settings"))
            if r.status_code == 200 and r.json():
                d = r.json()
                admins_list        = set(d.get("admins",   [OWNER_ID]))
                forced_channels    = d.get("channels",     [])
                blocked_users      = set(d.get("blocked",  []))
                vip_users          = set(d.get("vips",     []))
                bot_settings_global.update(d.get("settings", {}))
                logger.info("✅ داتابەیس هێنرایەوە.")
        except Exception as e:
            logger.error(f"❌ هەڵەی داتابەیس: {e}")

async def save_settings():
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
        except Exception as e:
            logger.error(f"❌ هەڵەی سەیڤ: {e}")

async def save_user_session(user_id: int, data: dict):
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            await c.put(firebase_url(f"user_sessions/{user_id}"), json=data)
        except:
            pass

async def get_user_session(user_id: int) -> dict | None:
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            r = await c.get(firebase_url(f"user_sessions/{user_id}"))
            if r.status_code == 200 and r.json():
                d = r.json()
                if int(time.time()) - d.get("timestamp", 0) <= SESSION_EXPIRE:
                    return d
        except:
            pass
    return None

async def is_user_registered(user_id: int) -> bool:
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}"))
            return r.status_code == 200 and r.json() is not None
        except:
            return False

async def register_user(user_id: int, info: dict):
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            await c.put(firebase_url(f"registered_users/{user_id}"), json=info)
        except:
            pass

async def get_user_data(user_id: int) -> dict | None:
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}"))
            if r.status_code == 200 and r.json():
                return r.json()
        except:
            pass
    return None

async def update_user_field(user_id: int, field: str, value):
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            await c.put(firebase_url(f"registered_users/{user_id}/{field}"), json=value)
        except:
            pass

async def get_all_user_ids() -> list[int]:
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(firebase_url("registered_users"))
            if r.status_code == 200 and r.json():
                return [int(k) for k in r.json().keys()]
        except:
            pass
    return []

async def get_all_users_data() -> dict:
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(firebase_url("registered_users"))
            if r.status_code == 200 and r.json():
                return r.json()
        except:
            pass
    return {}

async def delete_all_users():
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            await c.delete(firebase_url("registered_users"))
        except:
            pass

async def notify_owner_new_user(context, user):
    msg = (
        f"🔔 <b>بەکارهێنەرێکی نوێ تۆمار کرا!</b>\n\n"
        f"👤 ناو: {html.escape(user.first_name)}\n"
        f"🆔 ئایدی: <code>{user.id}</code>\n"
        f"🔗 یوزەرنەیم: @{user.username or '—'}"
    )
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode=ParseMode.HTML)
    except:
        pass

# ==============================================================================
# ----------------------- API داونلۆد (DOWNLOAD ENGINE) ------------------------
# ==============================================================================

async def fetch_tiktok_data(url: str) -> dict | None:
    """
    دەکۆشێت دیتا لە API هەڵبگرێت.
    ئەگەر API سەرەکی سەرکەوتوو نەبوو، API بەکاپ تاقی دەکاتەوە.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept"    : "application/json",
    }
    # ── API سەرەکی ────────────────────────────────────────────────────────────
    async with httpx.AsyncClient(timeout=API_TIMEOUT, headers=headers, follow_redirects=True) as c:
        try:
            r = await c.get(API_URL + url)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok") or data.get("status") == "success":
                    return {"source": "primary", "data": data}
        except Exception as e:
            logger.warning(f"⚠️ API سەرەکی سەرکەوتوو نەبوو: {e}")

        # ── API بەکاپ ─────────────────────────────────────────────────────────
        try:
            r2 = await c.get(API_URL_BACKUP + url)
            if r2.status_code == 200:
                raw = r2.json()
                # تبدیل فۆرماتی بەکاپ بۆ فۆرماتی سەرەکی
                if raw.get("code") == 0 and raw.get("data"):
                    d = raw["data"]
                    normalized = {
                        "ok"   : True,
                        "data" : {
                            "creator": d.get("author", {}).get("nickname", "Unknown"),
                            "details": {
                                "title"  : d.get("title", ""),
                                "cover"  : {"cover": d.get("cover", "")},
                                "images" : d.get("images", []),
                                "video"  : {"play": d.get("play", "")},
                                "audio"  : {"play": d.get("music", "")},
                                "stats"  : {
                                    "views"   : d.get("play_count", 0),
                                    "likes"   : d.get("digg_count", 0),
                                    "comments": d.get("comment_count", 0),
                                },
                            }
                        }
                    }
                    return {"source": "backup", "data": normalized}
        except Exception as e:
            logger.warning(f"⚠️ API بەکاپیش سەرکەوتوو نەبوو: {e}")

    return None

def parse_api_response(raw: dict) -> tuple[str, dict, list]:
    """
    دەگەڕێنێتەوە: (creator, details, images)
    چارەسەری هەموو فۆرماتی وەڵامی API دەکات.
    """
    data    = raw.get("data", {})
    creator = data.get("creator", "Unknown")
    details = data.get("details", {})

    # وێنەکان — دەکۆشێت لە چەندین شوێن بیدۆزێتەوە
    images = (
        details.get("images") or
        details.get("image_list") or
        data.get("images") or
        []
    )

    # دڵنیابوون لەوەی images لیستی URL-ە نەک لیستی dict
    clean_images = []
    for img in images:
        if isinstance(img, str):
            clean_images.append(img)
        elif isinstance(img, dict):
            url_val = (
                img.get("url_list", [None])[0] or
                img.get("url") or
                img.get("download_url") or
                img.get("display_image", {}).get("url_list", [None])[0]
            )
            if url_val:
                clean_images.append(url_val)

    return creator, details, clean_images

# ==============================================================================
# ----------------------------- فەرمانەکان (COMMANDS) --------------------------
# ==============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    uid     = user.id
    lang    = await get_user_lang(uid)
    is_cb   = bool(update.callback_query)

    async def send(text, kb):
        markup = InlineKeyboardMarkup(kb)
        if is_cb:
            try:
                await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
            except BadRequest:
                await update.callback_query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)

    if is_blocked(uid):
        await send(t(lang, "error_blocked"), back_btn(lang, "cmd_start")); return

    if bot_settings_global["maintenance_mode"] and not is_admin(uid):
        await send(t(lang, "error_maintenance"), back_btn(lang, "cmd_start")); return

    if not is_admin(uid):
        if not await is_user_registered(uid):
            asyncio.create_task(notify_owner_new_user(context, user))
            bot_settings_global["total_users"] = bot_settings_global.get("total_users", 0) + 1
            await register_user(uid, {
                "name"       : user.first_name,
                "username"   : user.username or "",
                "joined_date": get_current_time(),
                "is_vip"     : False,
                "language"   : "ku",
                "downloads"  : 0,
            })

    is_sub, not_joined = await check_user_subscription(uid, context)
    bypass = (is_admin(uid) and bot_settings_global.get("admin_bypass_join", True)) or \
             (is_vip(uid) and bot_settings_global.get("vip_bypass_join", True))
    if not is_sub and not bypass:
        kb  = [[InlineKeyboardButton(t(lang,"btn_join_channel",ch=ch), url=f"https://t.me/{ch.replace('@','')}")]
               for ch in not_joined]
        kb += [[InlineKeyboardButton(t(lang,"btn_check_join"), callback_data="check_sub_start")]]
        await send(t(lang,"force_join_text"), kb); return

    badges = {
        "owner": {"ku":"👑 خاوەن","en":"👑 Owner","ar":"👑 المالك"},
        "admin": {"ku":"⚡ ئەدمین","en":"⚡ Admin","ar":"⚡ مسؤول"},
        "vip"  : {"ku":"💎 VIP",  "en":"💎 VIP",  "ar":"💎 VIP"},
        "free" : {"ku":"",        "en":"",        "ar":""},
    }
    badge = (
        badges["owner"].get(lang,"") if is_owner(uid) else
        badges["admin"].get(lang,"") if is_admin(uid) else
        badges["vip"].get(lang,"")   if is_vip(uid)   else ""
    )

    custom_welcome = bot_settings_global.get("welcome_msg", "")
    if custom_welcome and not is_admin(uid):
        text = custom_welcome.replace("{name}", html.escape(user.first_name)).replace("{badge}", badge)
    else:
        text = (
            f"╔{'═'*21}╗\n"
            f"  {t(lang,'welcome_title',name=html.escape(user.first_name),badge=badge)}\n"
            f"╚{'═'*21}╝\n\n"
            f"{t(lang,'welcome_intro')}\n"
            f"{t(lang,'welcome_features')}\n\n"
            f"{divider()}\n"
            f"{t(lang,'welcome_prompt')}"
        )

    kb = [
        [InlineKeyboardButton(t(lang,"btn_download"),  callback_data="cmd_download")],
        [
            InlineKeyboardButton(t(lang,"btn_profile"), callback_data="menu_profile"),
            InlineKeyboardButton(t(lang,"btn_vip"),     callback_data="menu_vip"),
        ],
        [
            InlineKeyboardButton(t(lang,"btn_settings"),callback_data="menu_settings"),
            InlineKeyboardButton(t(lang,"btn_help"),    callback_data="cmd_help"),
        ],
        [InlineKeyboardButton(t(lang,"btn_channel"),   url=CHANNEL_URL)],
    ]
    if is_admin(uid):
        kb.append([InlineKeyboardButton(t(lang,"btn_admin_panel"), callback_data="admin_main")])
    if is_owner(uid):
        kb.append([InlineKeyboardButton(t(lang,"btn_owner_panel"), callback_data="owner_main")])

    await send(text, kb)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    lang = await get_user_lang(uid)
    text = (
        f"╔{'═'*21}╗\n"
        f"  {t(lang,'help_title')}\n"
        f"╚{'═'*21}╝\n\n"
        f"{t(lang,'help_text')}"
    )
    kb = back_btn(lang)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

# ==============================================================================
# ---------------------- بەڕێوەبردنی کڵیکەکان (CALLBACK) -----------------------
# ==============================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    data    = query.data
    uid     = query.from_user.id
    lang    = await get_user_lang(uid)
    await query.answer()

    # ── ناڤیگەیشنی سەرەکی ─────────────────────────────────────────────────────
    if data in ("check_sub_start", "cmd_start"):
        await start_command(update, context); return
    if data == "cmd_help":
        await help_command(update, context); return
    if data == "cmd_download":
        await query.message.reply_text(
            t(lang,"download_prompt"), parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        ); return
    if data == "close":
        try: await query.message.delete()
        except: pass
        return

    # ── پرۆفایل ────────────────────────────────────────────────────────────────
    if data == "menu_profile":
        user_data = await get_user_data(uid)
        join_date = user_data.get("joined_date","—") if user_data else "—"
        uname     = query.from_user.username or "—"
        dl_count  = user_data.get("downloads", 0) if user_data else 0
        text = (
            f"╔{'═'*21}╗\n"
            f"  {t(lang,'profile_title')}\n"
            f"╚{'═'*21}╝\n\n"
            f"{t(lang,'profile_id',       id=uid)}\n"
            f"{t(lang,'profile_name',     name=html.escape(query.from_user.first_name))}\n"
            f"{t(lang,'profile_username', username=uname)}\n"
            f"{t(lang,'profile_join_date',date=join_date)}\n"
            f"{t(lang,'profile_vip_status',status=(t(lang,'vip_yes') if is_vip(uid) else t(lang,'vip_no')))}\n"
            f"{t(lang,'profile_total_dl', count=dl_count)}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(back_btn(lang))); return

    # ── VIP ────────────────────────────────────────────────────────────────────
    if data == "menu_vip":
        text = (
            f"╔{'═'*21}╗\n"
            f"  💎 <b>{t(lang,'btn_vip')}</b>\n"
            f"╚{'═'*21}╝\n\n"
            "✅ خێرایی داونلۆدی زیاتر.\n"
            "✅ بێ جۆین کردنی چەناڵ.\n"
            "✅ داونلۆدی بێسنوور بۆ وێنەکان.\n"
            "✅ گەیشتن بە تایبەتمەندییە تازەکان.\n\n"
            f"💳 <b>پەیوەندی بکە بە:</b> {DEVELOPER_USERNAME}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(back_btn(lang))); return

    # ── ڕێکخستنی زمان ──────────────────────────────────────────────────────────
    if data == "menu_settings":
        kb = [
            [InlineKeyboardButton("🔴🔆🟢 کوردی",  callback_data="set_lang_ku")],
            [InlineKeyboardButton("🇺🇸 English",    callback_data="set_lang_en")],
            [InlineKeyboardButton("🇸🇦 العربية",   callback_data="set_lang_ar")],
            *back_btn(lang),
        ]
        await query.edit_message_text(
            f"🌍 <b>{t(lang,'lang_select_title')}</b>\n\n{t(lang,'lang_select_prompt')}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
        ); return

    if data.startswith("set_lang_"):
        new_lang = data.split("_")[2]
        await update_user_field(uid, "language", new_lang)
        await query.answer(f"✅ Language → {new_lang.upper()}", show_alert=True)
        await start_command(update, context); return

    # ── داونلۆد کردن ───────────────────────────────────────────────────────────
    if data.startswith("dl_"):
        action    = data.split("_")[1]
        sess      = await get_user_session(uid)
        if not sess:
            await query.answer(t(lang,"error_session_expired"), show_alert=True); return

        creator  = sess.get("creator","Unknown")
        details  = sess.get("details",{})
        images   = sess.get("images",[])     # ✅ وێنەکان جیاکراوەتەوە لە session
        title    = clean_title(details.get("title",""))
        caption  = (
            f"🎬 <b>{html.escape(title)}</b>\n"
            f"👤 <b>{html.escape(creator)}</b>\n\n"
            f"🤖 @{context.bot.username}"
        )
        del_kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang,"btn_delete"), callback_data="close")]])

        try:
            if action == "photos":
                # ── ناردنی وێنەکان ─────────────────────────────────────────
                if not images:
                    await query.answer("❌ هیچ وێنەیەک نەدۆزرایەوە!", show_alert=True); return
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_photos"]    += 1
                await save_settings()
                await update_user_field(uid, "downloads", (await get_user_data(uid) or {}).get("downloads",0)+1)

                max_p  = int(bot_settings_global.get("max_photos",10))
                chunks = [images[i:i+10] for i in range(0, min(len(images), max_p), 10)]

                await query.message.delete()
                for chunk in chunks:
                    media_group = [InputMediaPhoto(media=img) for img in chunk]
                    media_group[0].caption    = caption
                    media_group[0].parse_mode = ParseMode.HTML
                    try:
                        await context.bot.send_media_group(chat_id=uid, media=media_group)
                    except Exception as e:
                        logger.error(f"وێنە ناردن هەڵە: {e}")
                        # دوبارە هەوڵدان بەرامبەر خرابوونی URLی تاکەکە
                        for img_url in chunk:
                            try:
                                await context.bot.send_photo(
                                    chat_id=uid, photo=img_url,
                                    caption=caption, parse_mode=ParseMode.HTML
                                )
                            except:
                                pass
                    await asyncio.sleep(0.5)

            elif action == "video":
                # ── ناردنی ڤیدیۆ ───────────────────────────────────────────
                video_url = details.get("video",{}).get("play","") or details.get("video",{}).get("download_addr","")
                if not video_url:
                    await query.answer("❌ ڤیدیۆ نەدۆزرایەوە!", show_alert=True); return
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_videos"]    += 1
                await save_settings()
                await update_user_field(uid, "downloads", (await get_user_data(uid) or {}).get("downloads",0)+1)
                await query.message.edit_media(
                    InputMediaVideo(media=video_url, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=del_kb,
                )

            elif action == "audio":
                # ── ناردنی گۆرانی ──────────────────────────────────────────
                audio_url = details.get("audio",{}).get("play","") or details.get("audio",{}).get("music","")
                if not audio_url:
                    await query.answer("❌ گۆرانی نەدۆزرایەوە!", show_alert=True); return
                bot_settings_global["total_downloads"] += 1
                bot_settings_global["total_audios"]    += 1
                await save_settings()
                await update_user_field(uid, "downloads", (await get_user_data(uid) or {}).get("downloads",0)+1)
                music_title = f"{DEVELOPER_USERNAME}-{get_random_id()}"
                await query.message.edit_media(
                    InputMediaAudio(
                        media=audio_url, caption=caption, parse_mode=ParseMode.HTML,
                        title=music_title, performer=DEVELOPER_USERNAME,
                    ),
                    reply_markup=del_kb,
                )

        except Exception as e:
            logger.error(f"داونلۆد هەڵە: {e}")
            # ناردنی لینک بە شێوەی تێکست
            if action == "photos" and images:
                links = "\n".join([f"🖼 <a href='{img}'>وێنەی {i+1}</a>" for i,img in enumerate(images[:10])])
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"⚠️ <b>هەڵەیەک ڕوویدا، وێنەکان لێرەوە دابەزێنە:</b>\n\n{links}",
                    parse_mode=ParseMode.HTML,
                )
            elif action == "video":
                link = details.get("video",{}).get("play","")
                try:
                    await query.message.edit_caption(
                        f"⚠️ <a href='{link}'>📥 دابەزاندنی ڤیدیۆ</a>",
                        parse_mode=ParseMode.HTML,
                    )
                except:
                    await context.bot.send_message(chat_id=uid, text=f"📥 <a href='{link}'>ڤیدیۆ</a>", parse_mode=ParseMode.HTML)
            elif action == "audio":
                link = details.get("audio",{}).get("play","")
                try:
                    await query.message.edit_caption(
                        f"⚠️ <a href='{link}'>🎵 دابەزاندنی گۆرانی</a>",
                        parse_mode=ParseMode.HTML,
                    )
                except:
                    await context.bot.send_message(chat_id=uid, text=f"🎵 <a href='{link}'>گۆرانی</a>", parse_mode=ParseMode.HTML)
        return

    # ==========================================================================
    # ========================= پانێڵی ئەدمین ==================================
    # ==========================================================================
    if not is_admin(uid):
        await query.answer(t(lang,"error_admin_only"), show_alert=True); return

    # ── پانێڵی سەرەکی ──────────────────────────────────────────────────────────
    if data == "admin_main":
        all_ids = await get_all_user_ids()
        kb = [
            [
                InlineKeyboardButton("📊 ئامارەکان",           callback_data="admin_stats"),
                InlineKeyboardButton("📢 برۆدکاست",            callback_data="admin_broadcast"),
            ],
            [
                InlineKeyboardButton("📢 چەناڵەکان",           callback_data="admin_channels"),
                InlineKeyboardButton("🚫 بلۆک / ئەنبلۆک",     callback_data="admin_blocks"),
            ],
            [
                InlineKeyboardButton("💎 VIP",                  callback_data="admin_vips"),
                InlineKeyboardButton("⚙️ دۆخی چاکسازی",        callback_data="admin_toggle_maint"),
            ],
            [
                InlineKeyboardButton("👤 زانیاری بەکارهێنەر",  callback_data="admin_user_info_ask"),
                InlineKeyboardButton("✉️ نامە بنێرە",           callback_data="admin_msg_user_ask"),
            ],
            *back_btn(lang),
        ]
        maint = "🔴 چالاک" if bot_settings_global["maintenance_mode"] else "🟢 ناچالاک"
        await query.edit_message_text(
            f"👑 <b>پانێڵی ئەدمین</b>\n\n"
            f"👥 بەکارهێنەر: <b>{len(all_ids)}</b>\n"
            f"🛠 چاکسازی: <b>{maint}</b>\n"
            f"🕐 {get_current_time()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        ); return

    # ── ئامارەکان ───────────────────────────────────────────────────────────────
    if data == "admin_stats":
        all_ids = await get_all_user_ids()
        text = (
            f"╔{'═'*21}╗\n"
            f"  📊 <b>ئاماری بۆت</b>\n"
            f"╚{'═'*21}╝\n\n"
            f"👥 <b>بەکارهێنەرەکان:</b>\n"
            f"├ گشتی تۆمارکراو: <b>{len(all_ids)}</b>\n"
            f"├ ئەدمین: <b>{len(admins_list)}</b>\n"
            f"├ VIP: <b>{len(vip_users)}</b>\n"
            f"├ بلۆک: <b>{len(blocked_users)}</b>\n"
            f"└ چەناڵی ناچاری: <b>{len(forced_channels)}</b>\n\n"
            f"📈 <b>داونلۆدەکان:</b>\n"
            f"├ گشتی: <b>{format_number(bot_settings_global['total_downloads'])}</b>\n"
            f"├ ڤیدیۆ: <b>{format_number(bot_settings_global['total_videos'])}</b>\n"
            f"├ گۆرانی: <b>{format_number(bot_settings_global['total_audios'])}</b>\n"
            f"└ وێنە: <b>{format_number(bot_settings_global['total_photos'])}</b>\n\n"
            f"⚙️ <b>سیستەم:</b>\n"
            f"├ چاکسازی: {'🔴 بەڵێ' if bot_settings_global['maintenance_mode'] else '🟢 نەخێر'}\n"
            f"└ کاتی کارکردن: {get_uptime()}\n\n"
            f"🕐 {get_current_time()}"
        )
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang,"btn_refresh"), callback_data="admin_stats")],
                *back_btn(lang, "admin_main"),
            ])
        ); return

    # ── برۆدکاست ────────────────────────────────────────────────────────────────
    if data == "admin_broadcast":
        admin_waiting_state[uid] = "broadcast"
        await query.message.reply_text(
            t(lang,"send_broadcast_msg"), reply_markup=ForceReply(selective=True)
        ); return

    # ── دۆخی چاکسازی ────────────────────────────────────────────────────────────
    if data == "admin_toggle_maint":
        if not is_owner(uid):
            await query.answer(t(lang,"error_owner_only"), show_alert=True); return
        bot_settings_global["maintenance_mode"] = not bot_settings_global["maintenance_mode"]
        await save_settings()
        st = "🔴 چالاک کرا" if bot_settings_global["maintenance_mode"] else "🟢 ناچالاک کرا"
        await query.edit_message_text(
            f"✅ دۆخی چاکسازی گۆڕدرا.\nئێستا: <b>{st}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang,"admin_main")),
        ); return

    # ── زانیاری بەکارهێنەر ──────────────────────────────────────────────────────
    if data == "admin_user_info_ask":
        admin_waiting_state[uid] = "user_info"
        await query.message.reply_text(t(lang,"send_user_id"), reply_markup=ForceReply(selective=True)); return

    # ── نامە بنێرە بۆ بەکارهێنەر ────────────────────────────────────────────────
    if data == "admin_msg_user_ask":
        admin_waiting_state[uid] = "msg_user_ask_id"
        await query.message.reply_text(t(lang,"send_user_id"), reply_markup=ForceReply(selective=True)); return

    # ── بەڕێوەبردنی چەناڵ ───────────────────────────────────────────────────────
    if data == "admin_channels":
        ch_list = "\n".join([f"  • <code>{ch}</code>" for ch in forced_channels]) or "  📭 هیچ چەناڵێک نییە."
        kb = [
            [
                InlineKeyboardButton("➕ زیادکردن", callback_data="ch_add"),
                InlineKeyboardButton("➖ لابردن",   callback_data="ch_rm_list"),
            ],
            *back_btn(lang,"admin_main"),
        ]
        await query.edit_message_text(
            f"📢 <b>بەڕێوەبردنی چەناڵەکان</b>\n\n{ch_list}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
        ); return

    if data == "ch_add":
        admin_waiting_state[uid] = "ch_add"
        await query.message.reply_text(t(lang,"send_channel"), reply_markup=ForceReply(selective=True)); return

    if data == "ch_rm_list":
        if not forced_channels:
            await query.answer("📭 هیچ چەناڵێک نییە!", show_alert=True); return
        kb  = [[InlineKeyboardButton(f"❌ {ch}", callback_data=f"ch_del_{ch}")] for ch in forced_channels]
        kb += back_btn(lang,"admin_channels")
        await query.edit_message_text(
            "📢 <b>چەناڵێک هەڵبژێرە بۆ لابردن:</b>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
        ); return

    if data.startswith("ch_del_"):
        ch = data[7:]
        if ch in forced_channels: forced_channels.remove(ch)
        await save_settings()
        await query.edit_message_text(
            t(lang,"channel_removed",ch=ch), parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang,"admin_channels"))
        ); return

    # ── بەڕێوەبردنی بلۆک ────────────────────────────────────────────────────────
    if data == "admin_blocks":
        blk = "\n".join([f"  • <code>{x}</code>" for x in blocked_users]) or "  📭 بلۆک نییە."
        kb = [
            [
                InlineKeyboardButton("🚫 بلۆک کردن",    callback_data="blk_add"),
                InlineKeyboardButton("✅ ئەنبلۆک کردن",  callback_data="blk_rm"),
            ],
            *back_btn(lang,"admin_main"),
        ]
        await query.edit_message_text(
            f"🚫 <b>بلۆک کراوەکان</b>\n\n{blk}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
        ); return

    if data == "blk_add":
        admin_waiting_state[uid] = "blk_add"
        await query.message.reply_text(t(lang,"send_user_id"), reply_markup=ForceReply(selective=True)); return

    if data == "blk_rm":
        admin_waiting_state[uid] = "blk_rm"
        await query.message.reply_text(t(lang,"send_user_id"), reply_markup=ForceReply(selective=True)); return

    # ── بەڕێوەبردنی VIP ─────────────────────────────────────────────────────────
    if data == "admin_vips":
        vip_l = "\n".join([f"  • <code>{x}</code>" for x in vip_users]) or "  📭 VIP نییە."
        kb = [
            [
                InlineKeyboardButton("➕ زیادکردن",  callback_data="vip_add"),
                InlineKeyboardButton("➖ لابردن",    callback_data="vip_rm"),
            ],
            *back_btn(lang,"admin_main"),
        ]
        await query.edit_message_text(
            f"💎 <b>VIP بەکارهێنەرەکان</b>\n\n{vip_l}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
        ); return

    if data == "vip_add":
        admin_waiting_state[uid] = "vip_add"
        await query.message.reply_text(t(lang,"send_user_id"), reply_markup=ForceReply(selective=True)); return

    if data == "vip_rm":
        admin_waiting_state[uid] = "vip_rm"
        await query.message.reply_text(t(lang,"send_user_id"), reply_markup=ForceReply(selective=True)); return

    # ==========================================================================
    # ========================= پانێڵی خاوەن (OWNER PANEL) ====================
    # ==========================================================================
    if not is_owner(uid):
        await query.answer(t(lang,"error_owner_only"), show_alert=True); return

    if data == "owner_main":
        kb = [
            [
                InlineKeyboardButton("👥 بەڕێوەبردنی ئەدمین",   callback_data="owner_admins"),
                InlineKeyboardButton("📊 ئاماری پێشکەوتوو",     callback_data="owner_stats_adv"),
            ],
            [
                InlineKeyboardButton("⚙️ ڕێکخستنی بۆت",         callback_data="owner_bot_settings"),
                InlineKeyboardButton("📝 نامەی خۆشامەدێ",        callback_data="owner_welcome_msg"),
            ],
            [
                InlineKeyboardButton("💾 بەکئەپی داتابەیس",      callback_data="owner_backup"),
                InlineKeyboardButton("📋 لیستی بەکارهێنەرەکان", callback_data="owner_list_users"),
            ],
            [
                InlineKeyboardButton("🗑 ڕیسێتی ئامارەکان",     callback_data="owner_reset_stats_ask"),
                InlineKeyboardButton("☢️ سڕینەوەی بەکارهێنەر",  callback_data="owner_reset_users_ask"),
            ],
            [
                InlineKeyboardButton("📣 بڕۆدکاستی پێشکەوتوو",  callback_data="owner_adv_broadcast"),
                InlineKeyboardButton("🔧 API تاقیکردنەوە",       callback_data="owner_test_api"),
            ],
            [
                InlineKeyboardButton("🌐 ڕێکخستنی زمان بۆت",   callback_data="owner_bot_lang"),
                InlineKeyboardButton("📈 ریپۆرتی ڕۆژانە",       callback_data="owner_daily_report"),
            ],
            *back_btn(lang,"cmd_start"),
        ]
        await query.edit_message_text(
            f"🔱 <b>پانێڵی خاوەنی بۆت</b>\n\n"
            f"👑 خاوەن: <code>{OWNER_ID}</code>\n"
            f"🤖 نەرمەکاڵای بۆت: v{bot_settings_global.get('bot_version','6.0')}\n"
            f"⏱ کاتی کارکردن: {get_uptime()}\n"
            f"🕐 {get_current_time()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        ); return

    # ── بەڕێوەبردنی ئەدمین ─────────────────────────────────────────────────────
    if data == "owner_admins":
        adm = "\n".join([f"  • <code>{x}</code>" for x in admins_list if x != OWNER_ID]) or "  📭 هیچ ئەدمینێک نییە."
        kb  = [
            [
                InlineKeyboardButton("➕ زیادکردنی ئەدمین",  callback_data="adm_add"),
                InlineKeyboardButton("➖ لابردنی ئەدمین",    callback_data="adm_rm"),
            ],
            *back_btn(lang,"owner_main"),
        ]
        await query.edit_message_text(
            f"👥 <b>بەڕێوەبردنی ئەدمینەکان</b>\n\n{adm}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
        ); return

    if data == "adm_add":
        admin_waiting_state[uid] = "adm_add"
        await query.message.reply_text(t(lang,"send_user_id"), reply_markup=ForceReply(selective=True)); return

    if data == "adm_rm":
        admin_waiting_state[uid] = "adm_rm"
        await query.message.reply_text(t(lang,"send_user_id"), reply_markup=ForceReply(selective=True)); return

    # ── ئاماری پێشکەوتوو ─────────────────────────────────────────────────────────
    if data == "owner_stats_adv":
        all_ids   = await get_all_user_ids()
        all_data  = await get_all_users_data()
        vip_cnt   = sum(1 for v in all_data.values() if v.get("is_vip"))
        total_dls = sum(v.get("downloads",0) for v in all_data.values())
        text = (
            f"╔{'═'*21}╗\n"
            f"  📊 <b>ئاماری پێشکەوتوو</b>\n"
            f"╚{'═'*21}╝\n\n"
            f"👥 <b>بەکارهێنەرەکان:</b>\n"
            f"├ کۆی گشتی: <b>{len(all_ids)}</b>\n"
            f"├ VIP: <b>{len(vip_users)}</b>\n"
            f"├ ئەدمین: <b>{len(admins_list)}</b>\n"
            f"├ بلۆک: <b>{len(blocked_users)}</b>\n"
            f"└ چەناڵ: <b>{len(forced_channels)}</b>\n\n"
            f"📥 <b>داونلۆدەکان:</b>\n"
            f"├ کۆی گشتی (سیستەم): <b>{format_number(bot_settings_global['total_downloads'])}</b>\n"
            f"├ کۆی گشتی (بەکارهێنەر): <b>{format_number(total_dls)}</b>\n"
            f"├ ڤیدیۆ: <b>{format_number(bot_settings_global['total_videos'])}</b>\n"
            f"├ گۆرانی: <b>{format_number(bot_settings_global['total_audios'])}</b>\n"
            f"└ وێنە: <b>{format_number(bot_settings_global['total_photos'])}</b>\n\n"
            f"⚙️ <b>ڕێکخستنەکان:</b>\n"
            f"├ دۆخی چاکسازی: {'🔴' if bot_settings_global['maintenance_mode'] else '🟢'}\n"
            f"├ Photo Mode: {bot_settings_global.get('photo_mode','auto')}\n"
            f"├ Max Photos: {bot_settings_global.get('max_photos',10)}\n"
            f"├ VIP Bypass Join: {'✅' if bot_settings_global.get('vip_bypass_join') else '❌'}\n"
            f"└ Admin Bypass Join: {'✅' if bot_settings_global.get('admin_bypass_join') else '❌'}\n\n"
            f"🕐 {get_current_time()}"
        )
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang,"btn_refresh"), callback_data="owner_stats_adv")],
                *back_btn(lang,"owner_main"),
            ])
        ); return

    # ── ڕێکخستنی بۆت ─────────────────────────────────────────────────────────────
    if data == "owner_bot_settings":
        kb = [
            [InlineKeyboardButton(
                f"🛠 چاکسازی: {'🔴 ON' if bot_settings_global['maintenance_mode'] else '🟢 OFF'}",
                callback_data="owner_toggle_maint"
            )],
            [InlineKeyboardButton(
                f"📸 Photo Mode: {bot_settings_global.get('photo_mode','auto')}",
                callback_data="owner_toggle_photo_mode"
            )],
            [InlineKeyboardButton(
                f"💎 VIP Bypass: {'✅' if bot_settings_global.get('vip_bypass_join',True) else '❌'}",
                callback_data="owner_toggle_vip_bypass"
            )],
            [InlineKeyboardButton(
                f"👑 Admin Bypass: {'✅' if bot_settings_global.get('admin_bypass_join',True) else '❌'}",
                callback_data="owner_toggle_admin_bypass"
            )],
            [InlineKeyboardButton(
                f"📸 Max Photos: {bot_settings_global.get('max_photos',10)}",
                callback_data="owner_set_max_photos"
            )],
            [InlineKeyboardButton(
                f"⏱ API Timeout: {bot_settings_global.get('api_timeout',60)}s",
                callback_data="owner_set_api_timeout"
            )],
            *back_btn(lang,"owner_main"),
        ]
        await query.edit_message_text(
            "⚙️ <b>ڕێکخستنی بۆت</b>\n\nدوگمەیەک هەڵبژێرە بۆ گۆڕانی:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if data == "owner_toggle_maint":
        bot_settings_global["maintenance_mode"] = not bot_settings_global["maintenance_mode"]
        await save_settings()
        await query.answer(
            f"دۆخی چاکسازی: {'🔴 ON' if bot_settings_global['maintenance_mode'] else '🟢 OFF'}",
            show_alert=True
        )
        await button_handler.__wrapped__(update, context) if hasattr(button_handler,"__wrapped__") else None
        # نوێکردنەوەی پانێڵ
        query.data = "owner_bot_settings"
        await button_handler(update, context); return

    if data == "owner_toggle_photo_mode":
        modes = ["auto", "force_photos", "force_video"]
        cur   = bot_settings_global.get("photo_mode","auto")
        nxt   = modes[(modes.index(cur)+1) % len(modes)]
        bot_settings_global["photo_mode"] = nxt
        await save_settings()
        await query.answer(f"Photo Mode → {nxt}", show_alert=True)
        query.data = "owner_bot_settings"
        await button_handler(update, context); return

    if data == "owner_toggle_vip_bypass":
        bot_settings_global["vip_bypass_join"] = not bot_settings_global.get("vip_bypass_join",True)
        await save_settings()
        await query.answer(f"VIP Bypass → {'ON' if bot_settings_global['vip_bypass_join'] else 'OFF'}", show_alert=True)
        query.data = "owner_bot_settings"
        await button_handler(update, context); return

    if data == "owner_toggle_admin_bypass":
        bot_settings_global["admin_bypass_join"] = not bot_settings_global.get("admin_bypass_join",True)
        await save_settings()
        await query.answer(f"Admin Bypass → {'ON' if bot_settings_global['admin_bypass_join'] else 'OFF'}", show_alert=True)
        query.data = "owner_bot_settings"
        await button_handler(update, context); return

    if data == "owner_set_max_photos":
        admin_waiting_state[uid] = "set_max_photos"
        await query.message.reply_text(
            f"📸 ژمارەی زۆرترین وێنەکان بنووسە (ئێستا: {bot_settings_global.get('max_photos',10)}):",
            reply_markup=ForceReply(selective=True)
        ); return

    if data == "owner_set_api_timeout":
        admin_waiting_state[uid] = "set_api_timeout"
        await query.message.reply_text(
            f"⏱ API Timeout بنووسە بە چرکە (ئێستا: {bot_settings_global.get('api_timeout',60)}):",
            reply_markup=ForceReply(selective=True)
        ); return

    # ── نامەی خۆشامەدێ ───────────────────────────────────────────────────────────
    if data == "owner_welcome_msg":
        admin_waiting_state[uid] = "set_welcome_msg"
        cur = bot_settings_global.get("welcome_msg","") or "(ئێستا بەکارنەهاتوو)"
        await query.message.reply_text(
            f"{t(lang,'send_welcome_msg')}\n\n<b>ئێستا:</b>\n{cur}",
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        ); return

    # ── بەکئەپ ───────────────────────────────────────────────────────────────────
    if data == "owner_backup":
        await query.answer("⏳ بەکئەپ ئامادە دەکرێت...", show_alert=False)
        all_users = await get_all_users_data()
        backup_data = {
            "timestamp"  : get_current_time(),
            "settings"   : bot_settings_global,
            "admins"     : list(admins_list),
            "channels"   : forced_channels,
            "blocked"    : list(blocked_users),
            "vips"       : list(vip_users),
            "total_users": len(all_users),
        }
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
        import io
        bio = io.BytesIO(backup_json.encode())
        bio.name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            await context.bot.send_document(
                chat_id=uid,
                document=bio,
                caption=t(lang,"backup_caption",time=get_current_time()),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await query.message.reply_text(f"❌ هەڵە: {e}")
        return

    # ── لیستی بەکارهێنەرەکان ─────────────────────────────────────────────────────
    if data == "owner_list_users":
        all_data = await get_all_users_data()
        if not all_data:
            await query.answer(t(lang,"no_users_found"), show_alert=True); return
        lines    = []
        for uid2, info in list(all_data.items())[:50]:
            vip_m    = "💎" if info.get("is_vip") else ""
            blk_m    = "🚫" if int(uid2) in blocked_users else ""
            name_m   = html.escape(str(info.get("name","?")))[:20]
            lines.append(f"{vip_m}{blk_m} <code>{uid2}</code> — {name_m}")
        total = len(all_data)
        text  = f"👥 <b>لیستی بەکارهێنەرەکان ({total})</b>\n\n" + "\n".join(lines)
        if total > 50:
            text += f"\n\n<i>... و {total-50} کەسی تری تر</i>"
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang,"owner_main"))
        ); return

    # ── ڕیسێتی ئامارەکان ─────────────────────────────────────────────────────────
    if data == "owner_reset_stats_ask":
        kb = [
            [
                InlineKeyboardButton(t(lang,"btn_confirm"), callback_data="owner_reset_stats_do"),
                InlineKeyboardButton(t(lang,"btn_cancel"),  callback_data="owner_main"),
            ]
        ]
        await query.edit_message_text(
            t(lang,"confirm_reset_stats"), parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        ); return

    if data == "owner_reset_stats_do":
        bot_settings_global["total_downloads"] = 0
        bot_settings_global["total_videos"]    = 0
        bot_settings_global["total_audios"]    = 0
        bot_settings_global["total_photos"]    = 0
        await save_settings()
        await query.edit_message_text(
            t(lang,"stats_reset_done"), parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang,"owner_main"))
        ); return

    # ── سڕینەوەی هەموو بەکارهێنەرەکان ───────────────────────────────────────────
    if data == "owner_reset_users_ask":
        kb = [
            [
                InlineKeyboardButton(t(lang,"btn_confirm"), callback_data="owner_reset_users_do"),
                InlineKeyboardButton(t(lang,"btn_cancel"),  callback_data="owner_main"),
            ]
        ]
        await query.edit_message_text(
            t(lang,"confirm_reset_users"), parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        ); return

    if data == "owner_reset_users_do":
        await delete_all_users()
        await query.edit_message_text(
            t(lang,"users_reset_done"), parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang,"owner_main"))
        ); return

    # ── بڕۆدکاستی پێشکەوتوو ──────────────────────────────────────────────────────
    if data == "owner_adv_broadcast":
        kb = [
            [
                InlineKeyboardButton("📢 بۆ هەمووان",     callback_data="owner_bc_all"),
                InlineKeyboardButton("💎 تەنیا VIP",      callback_data="owner_bc_vip"),
            ],
            [
                InlineKeyboardButton("🆓 تەنیا Free",     callback_data="owner_bc_free"),
                InlineKeyboardButton("🚫 بلۆک نەکراوان", callback_data="owner_bc_noblock"),
            ],
            *back_btn(lang,"owner_main"),
        ]
        await query.edit_message_text(
            "📣 <b>بڕۆدکاستی پێشکەوتوو</b>\n\nکێ دەوێیت نامەکەت پێبگات؟",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
        ); return

    for bc_type in ("all","vip","free","noblock"):
        if data == f"owner_bc_{bc_type}":
            admin_waiting_state[uid] = f"broadcast_{bc_type}"
            await query.message.reply_text(
                t(lang,"send_broadcast_msg"), reply_markup=ForceReply(selective=True)
            ); return

    # ── تاقیکردنەوەی API ─────────────────────────────────────────────────────────
    if data == "owner_test_api":
        test_url = "https://www.tiktok.com/@tiktok/video/6584647400055385349"
        await query.answer("⏳ API تاقی دەکرێتەوە...", show_alert=False)
        result = await fetch_tiktok_data(test_url)
        if result:
            src  = result.get("source","?")
            text = f"✅ <b>API کار دەکات!</b>\n\nSource: <code>{src}</code>\n🕐 {get_current_time()}"
        else:
            text = f"❌ <b>API کار ناکات!</b>\n\n🕐 {get_current_time()}"
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang,"owner_main"))
        ); return

    # ── ڕێکخستنی زمان بۆت ────────────────────────────────────────────────────────
    if data == "owner_bot_lang":
        kb = [
            [InlineKeyboardButton("🔴🔆🟢 کوردی (پێشواز)",   callback_data="owner_set_deflang_ku")],
            [InlineKeyboardButton("🇺🇸 English (Default)",    callback_data="owner_set_deflang_en")],
            [InlineKeyboardButton("🇸🇦 Arabic (Default)",     callback_data="owner_set_deflang_ar")],
            *back_btn(lang,"owner_main"),
        ]
        await query.edit_message_text(
            "🌐 <b>زمانی پێشواز بۆ بەکارهێنەرانی نوێ هەڵبژێرە:</b>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
        ); return

    for dl in ("ku","en","ar"):
        if data == f"owner_set_deflang_{dl}":
            bot_settings_global["default_lang"] = dl
            await save_settings()
            await query.answer(f"✅ زمانی پێشواز → {dl.upper()}", show_alert=True)
            query.data = "owner_main"
            await button_handler(update, context); return

    # ── ریپۆرتی ڕۆژانە ──────────────────────────────────────────────────────────
    if data == "owner_daily_report":
        all_ids = await get_all_user_ids()
        text = (
            f"📈 <b>ریپۆرتی ڕۆژانەی بۆت</b>\n\n"
            f"📅 بەروار: {get_current_time()}\n"
            f"{divider()}\n"
            f"👥 کۆی بەکارهێنەر: <b>{len(all_ids)}</b>\n"
            f"📥 داونلۆدی کۆ: <b>{format_number(bot_settings_global['total_downloads'])}</b>\n"
            f"🎥 ڤیدیۆ: <b>{format_number(bot_settings_global['total_videos'])}</b>\n"
            f"📸 وێنە: <b>{format_number(bot_settings_global['total_photos'])}</b>\n"
            f"🎵 گۆرانی: <b>{format_number(bot_settings_global['total_audios'])}</b>\n"
            f"{divider()}\n"
            f"💎 VIP: <b>{len(vip_users)}</b>\n"
            f"🚫 بلۆک: <b>{len(blocked_users)}</b>\n"
            f"👑 ئەدمین: <b>{len(admins_list)}</b>\n"
            f"{divider()}\n"
            f"⏱ Uptime: {get_uptime()}"
        )
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang,"btn_refresh"), callback_data="owner_daily_report")],
                *back_btn(lang,"owner_main"),
            ])
        ); return

# ==============================================================================
# ---------------------- وەرگرتنی نامەکان (MESSAGE HANDLER) --------------------
# ==============================================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    uid  = update.effective_user.id
    lang = await get_user_lang(uid)
    msg  = update.message

    # ──────────────────────────────────────────────────────────────────────────
    # بەڕێوەبردنی وەڵامی ئەدمین / خاوەن
    # ──────────────────────────────────────────────────────────────────────────
    if is_admin(uid) and uid in admin_waiting_state:
        state = admin_waiting_state.pop(uid)
        text  = (msg.text or "").strip()

        # ── برۆدکاست (جۆرەکانی جیاواز) ───────────────────────────────────────
        if state.startswith("broadcast"):
            bc_type   = state.split("_")[1] if "_" in state else "all"
            all_uids  = await get_all_user_ids()
            all_udata = await get_all_users_data()

            target_ids = []
            for uid2 in all_uids:
                udata = all_udata.get(str(uid2), {})
                if bc_type == "all":
                    target_ids.append(uid2)
                elif bc_type == "vip" and uid2 in vip_users:
                    target_ids.append(uid2)
                elif bc_type == "free" and uid2 not in vip_users:
                    target_ids.append(uid2)
                elif bc_type == "noblock" and uid2 not in blocked_users:
                    target_ids.append(uid2)

            success, fail = 0, 0
            status = await msg.reply_text(f"⏳ برۆدکاست دەستپێدەکات بۆ <b>{len(target_ids)}</b> کەس...", parse_mode=ParseMode.HTML)
            for i, tuid in enumerate(target_ids):
                try:
                    await context.bot.copy_message(
                        chat_id    = tuid,
                        from_chat_id = msg.chat_id,
                        message_id = msg.message_id,
                    )
                    success += 1
                    await asyncio.sleep(0.04)
                    if i % 50 == 0 and i > 0:
                        try:
                            await status.edit_text(
                                f"⏳ ئەنجامدان: {i}/{len(target_ids)}...",
                                parse_mode=ParseMode.HTML
                            )
                        except: pass
                except (Forbidden, BadRequest):
                    fail += 1
                except Exception:
                    fail += 1
                    await asyncio.sleep(1)
            await status.edit_text(t(lang,"broadcast_sent",success=success,fail=fail), parse_mode=ParseMode.HTML)
            return

        # ── زیادکردنی چەناڵ ─────────────────────────────────────────────────
        if state == "ch_add":
            ch = text if text.startswith("@") else f"@{text}"
            if ch not in forced_channels:
                forced_channels.append(ch)
                await save_settings()
            await msg.reply_text(t(lang,"channel_added",ch=ch), parse_mode=ParseMode.HTML); return

        # ── بلۆک / ئەنبلۆک ─────────────────────────────────────────────────
        if state == "blk_add":
            if not text.isdigit(): await msg.reply_text(t(lang,"invalid_id")); return
            blocked_users.add(int(text)); await save_settings()
            await msg.reply_text(t(lang,"user_blocked",id=text), parse_mode=ParseMode.HTML); return

        if state == "blk_rm":
            if not text.isdigit(): await msg.reply_text(t(lang,"invalid_id")); return
            blocked_users.discard(int(text)); await save_settings()
            await msg.reply_text(t(lang,"user_unblocked",id=text), parse_mode=ParseMode.HTML); return

        # ── VIP ─────────────────────────────────────────────────────────────
        if state == "vip_add":
            if not text.isdigit(): await msg.reply_text(t(lang,"invalid_id")); return
            tid = int(text); vip_users.add(tid); await save_settings()
            await update_user_field(tid, "is_vip", True)
            await msg.reply_text(t(lang,"vip_added",id=text), parse_mode=ParseMode.HTML); return

        if state == "vip_rm":
            if not text.isdigit(): await msg.reply_text(t(lang,"invalid_id")); return
            tid = int(text); vip_users.discard(tid); await save_settings()
            await update_user_field(tid, "is_vip", False)
            await msg.reply_text(t(lang,"vip_removed",id=text), parse_mode=ParseMode.HTML); return

        # ── ئەدمین (تەنیا خاوەن) ─────────────────────────────────────────
        if state == "adm_add":
            if not is_owner(uid): await msg.reply_text(t(lang,"not_owner")); return
            if not text.isdigit(): await msg.reply_text(t(lang,"invalid_id")); return
            admins_list.add(int(text)); await save_settings()
            await msg.reply_text(t(lang,"admin_added",id=text), parse_mode=ParseMode.HTML); return

        if state == "adm_rm":
            if not is_owner(uid): await msg.reply_text(t(lang,"not_owner")); return
            if not text.isdigit(): await msg.reply_text(t(lang,"invalid_id")); return
            if int(text) == OWNER_ID: await msg.reply_text("⛔ ناتوانیت خاوەنەکە لابەری!"); return
            admins_list.discard(int(text)); await save_settings()
            await msg.reply_text(t(lang,"admin_removed",id=text), parse_mode=ParseMode.HTML); return

        # ── زانیاری بەکارهێنەر ───────────────────────────────────────────
        if state == "user_info":
            if not text.isdigit(): await msg.reply_text(t(lang,"invalid_id")); return
            tuid   = int(text)
            udata  = await get_user_data(tuid)
            if not udata: await msg.reply_text(t(lang,"user_not_found")); return
            vip_s  = "✅" if tuid in vip_users or udata.get("is_vip") else "❌"
            blk_s  = "✅" if tuid in blocked_users else "❌"
            await msg.reply_text(
                t(lang,"user_info_text",
                  id=tuid,
                  name=html.escape(str(udata.get("name","?"))),
                  username=udata.get("username","—"),
                  date=udata.get("joined_date","—"),
                  vip=vip_s, blocked=blk_s,
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🚫 بلۆک", callback_data=f"quick_blk_{tuid}"),
                        InlineKeyboardButton("💎 VIP",  callback_data=f"quick_vip_{tuid}"),
                    ],
                    [InlineKeyboardButton("✉️ نامە بنێرە", callback_data=f"quick_msg_{tuid}")],
                ])
            ); return

        # ── ئایدی بەکارهێنەر بۆ نامەی پێوندی ────────────────────────────
        if state == "msg_user_ask_id":
            if not text.isdigit(): await msg.reply_text(t(lang,"invalid_id")); return
            admin_waiting_state[uid] = f"msg_user_send_{text}"
            await msg.reply_text(
                t(lang,"send_msg_to_user",id=text),
                parse_mode=ParseMode.HTML,
                reply_markup=ForceReply(selective=True)
            ); return

        if state.startswith("msg_user_send_"):
            target_id = int(state.split("_")[-1])
            try:
                await context.bot.copy_message(
                    chat_id=target_id, from_chat_id=msg.chat_id, message_id=msg.message_id
                )
                await msg.reply_text(t(lang,"msg_sent_to_user")); return
            except Exception as e:
                await msg.reply_text(f"❌ هەڵە: {e}"); return

        # ── ڕێکخستنی خاوەن ──────────────────────────────────────────────
        if state == "set_max_photos":
            if not text.isdigit(): await msg.reply_text(t(lang,"invalid_id")); return
            bot_settings_global["max_photos"] = min(int(text), 30)
            await save_settings()
            await msg.reply_text(t(lang,"setting_updated")); return

        if state == "set_api_timeout":
            if not text.isdigit(): await msg.reply_text(t(lang,"invalid_id")); return
            bot_settings_global["api_timeout"] = int(text)
            await save_settings()
            await msg.reply_text(t(lang,"setting_updated")); return

        if state == "set_welcome_msg":
            bot_settings_global["welcome_msg"] = msg.text or ""
            await save_settings()
            await msg.reply_text(t(lang,"welcome_msg_set")); return

    # ──────────────────────────────────────────────────────────────────────────
    # بەڕێوەبردنی کڵیکی خێرای (Quick Actions)
    # ──────────────────────────────────────────────────────────────────────────
    # (ئەمە بۆ دوگمەی quick_* لە callback_data)

    # ──────────────────────────────────────────────────────────────────────────
    # پشکنینی بلۆک و چاکسازی
    # ──────────────────────────────────────────────────────────────────────────
    if not msg.text:
        return

    txt = msg.text.strip()

    if is_blocked(uid):
        return

    if bot_settings_global["maintenance_mode"] and not is_admin(uid):
        await msg.reply_text(t(lang,"error_maintenance"), parse_mode=ParseMode.HTML); return

    if "tiktok.com" not in txt:
        return

    # پشکنینی جۆین
    is_sub, not_joined = await check_user_subscription(uid, context)
    bypass = (is_admin(uid) and bot_settings_global.get("admin_bypass_join",True)) or \
             (is_vip(uid)   and bot_settings_global.get("vip_bypass_join",True))
    if not is_sub and not bypass:
        kb  = [[InlineKeyboardButton(t(lang,"btn_join_channel",ch=ch), url=f"https://t.me/{ch.replace('@','')}")]
               for ch in not_joined]
        kb += [[InlineKeyboardButton(t(lang,"btn_check_join"), callback_data="check_sub_start")]]
        await msg.reply_text(t(lang,"force_join_text"), parse_mode=ParseMode.HTML,
                             reply_markup=InlineKeyboardMarkup(kb)); return

    # ──────────────────────────────────────────────────────────────────────────
    # داونلۆدکردن
    # ──────────────────────────────────────────────────────────────────────────
    status_msg = await msg.reply_text("🔍 <b>داونلۆد دەستپێدەکات...</b>", parse_mode=ParseMode.HTML)

    try:
        result = await fetch_tiktok_data(txt)
        if not result:
            await status_msg.edit_text(t(lang,"error_invalid_link")); return

        raw_data = result["data"]
        creator, details, images = parse_api_response(raw_data)

        # ── دڵنیابوون لەسەر جۆری داتا ──────────────────────────────────────
        # ئەگەر photo_mode لە ڕێکخستندا بوو، ئایا وێنە یان ڤیدیۆ
        photo_mode = bot_settings_global.get("photo_mode","auto")
        if photo_mode == "force_video":
            images = []    # بەرپرسایەتی بكردن وەک ڤیدیۆ

        # ── ذخیرەکردنی session ─────────────────────────────────────────────
        await save_user_session(uid, {
            "creator": creator,
            "details": details,
            "images" : images,       # ✅ وێنەکان جیاکراوەتەوە لە session
        })

        # ── دروستکردنی caption ──────────────────────────────────────────────
        title     = clean_title(details.get("title","") or "")
        stats     = details.get("stats",{})
        views     = format_number(stats.get("views",0)   or stats.get("play_count",0))
        likes     = format_number(stats.get("likes",0)   or stats.get("digg_count",0))
        comments  = format_number(stats.get("comments",0)or stats.get("comment_count",0))

        caption = (
            f"{t(lang,'download_found')}\n\n"
            f"{t(lang,'download_title', title=html.escape(title))}\n"
            f"{t(lang,'download_owner', owner=html.escape(creator))}\n\n"
            f"👁 {views}   ❤️ {likes}   💬 {comments}"
        )

        # ── دروستکردنی keyboard ─────────────────────────────────────────────
        if images:
            kb = [
                [InlineKeyboardButton(t(lang,"btn_photos",count=len(images)), callback_data="dl_photos")],
                [InlineKeyboardButton(t(lang,"btn_audio"),                    callback_data="dl_audio")],
                [InlineKeyboardButton(t(lang,"btn_delete"),                   callback_data="close")],
            ]
        else:
            kb = [
                [InlineKeyboardButton(t(lang,"btn_video"),  callback_data="dl_video")],
                [InlineKeyboardButton(t(lang,"btn_audio"),  callback_data="dl_audio")],
                [InlineKeyboardButton(t(lang,"btn_delete"), callback_data="close")],
            ]

        # ── ناردنی وەڵام ────────────────────────────────────────────────────
        cover_url = (
            details.get("cover",{}).get("cover","") or
            details.get("cover",{}).get("origin_cover","") or
            details.get("origin_cover","") or
            (images[0] if images else "")
        )

        if cover_url:
            try:
                await status_msg.edit_media(
                    InputMediaPhoto(cover_url, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=InlineKeyboardMarkup(kb),
                )
            except Exception as e:
                logger.warning(f"Cover هەڵە: {e}")
                await status_msg.edit_text(caption, parse_mode=ParseMode.HTML,
                                           reply_markup=InlineKeyboardMarkup(kb))
        else:
            await status_msg.edit_text(caption, parse_mode=ParseMode.HTML,
                                       reply_markup=InlineKeyboardMarkup(kb))

    except Exception as e:
        logger.error(f"❌ هەڵەی گشتی داونلۆد: {e}")
        try:
            await status_msg.edit_text(t(lang,"error_download_fail"))
        except:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# بەڕێوەبردنی quick_* callback ها
# ──────────────────────────────────────────────────────────────────────────────
async def quick_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    data    = query.data
    uid     = query.from_user.id
    lang    = await get_user_lang(uid)

    if not is_admin(uid):
        await query.answer(t(lang,"error_admin_only"), show_alert=True); return

    await query.answer()

    if data.startswith("quick_blk_"):
        tid = int(data.split("_")[2])
        if tid in blocked_users:
            blocked_users.discard(tid)
            await query.answer(f"✅ ئەنبلۆک کرا: {tid}", show_alert=True)
        else:
            blocked_users.add(tid)
            await query.answer(f"✅ بلۆک کرا: {tid}", show_alert=True)
        await save_settings()

    elif data.startswith("quick_vip_"):
        tid = int(data.split("_")[2])
        if tid in vip_users:
            vip_users.discard(tid)
            await update_user_field(tid,"is_vip",False)
            await query.answer(f"✅ VIP لابرا: {tid}", show_alert=True)
        else:
            vip_users.add(tid)
            await update_user_field(tid,"is_vip",True)
            await query.answer(f"✅ VIP زیادکرا: {tid}", show_alert=True)
        await save_settings()

    elif data.startswith("quick_msg_"):
        tid = int(data.split("_")[2])
        admin_waiting_state[uid] = f"msg_user_send_{tid}"
        await query.message.reply_text(
            t(lang,"send_msg_to_user",id=tid),
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True),
        )

# ==============================================================================
# ------------------------- ڕێکخستنی کۆتایی (INITIALIZATION) ------------------
# ==============================================================================
ptb_app = ApplicationBuilder().token(TOKEN).build()
ptb_app.add_handler(CommandHandler(["start", "menu"],          start_command))
ptb_app.add_handler(CommandHandler("help",                     help_command))
ptb_app.add_handler(CallbackQueryHandler(quick_action_handler, pattern=r"^quick_"))
ptb_app.add_handler(CallbackQueryHandler(button_handler))
ptb_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))


@app.post("/api/main")
async def webhook(req: Request):
    if not ptb_app.running:
        await ptb_app.initialize()
    await load_settings()
    body = await req.json()
    await ptb_app.process_update(Update.de_json(body, ptb_app.bot))
    return {"ok": True}


@app.get("/api/main")
async def health():
    return {
        "status" : "active",
        "uptime" : get_uptime(),
        "version": bot_settings_global.get("bot_version","6.0"),
        "time"   : get_current_time(),
    }


# ==============================================================================
# ========================= فەرمانە تایبەتییەکانی خاوەن (OWNER COMMANDS) ========
# ==============================================================================

async def owner_cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /stats بۆ خاوەن"""
    uid = update.effective_user.id
    if not is_owner(uid):
        return
    all_ids = await get_all_user_ids()
    text = (
        f"📊 <b>ئاماری خێرا</b>\n\n"
        f"👥 بەکارهێنەر: <b>{len(all_ids)}</b>\n"
        f"📥 داونلۆد: <b>{format_number(bot_settings_global['total_downloads'])}</b>\n"
        f"⏱ Uptime: {get_uptime()}\n"
        f"🕐 {get_current_time()}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def owner_cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /ban [id] بۆ بلۆک کردنی خێرا"""
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("بەکارهێنان: /ban [ئایدی]"); return
    tid = int(args[0])
    blocked_users.add(tid)
    await save_settings()
    await update.message.reply_text(f"✅ بلۆک کرا: <code>{tid}</code>", parse_mode=ParseMode.HTML)


async def owner_cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /unban [id] بۆ ئەنبلۆک کردنی خێرا"""
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("بەکارهێنان: /unban [ئایدی]"); return
    tid = int(args[0])
    blocked_users.discard(tid)
    await save_settings()
    await update.message.reply_text(f"✅ ئەنبلۆک کرا: <code>{tid}</code>", parse_mode=ParseMode.HTML)


async def owner_cmd_addvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /addvip [id] بۆ زیادکردنی VIP"""
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("بەکارهێنان: /addvip [ئایدی]"); return
    tid = int(args[0])
    vip_users.add(tid)
    await save_settings()
    await update_user_field(tid, "is_vip", True)
    await update.message.reply_text(f"✅ VIP زیادکرا: <code>{tid}</code>", parse_mode=ParseMode.HTML)


async def owner_cmd_rmvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /rmvip [id] بۆ لابردنی VIP"""
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("بەکارهێنان: /rmvip [ئایدی]"); return
    tid = int(args[0])
    vip_users.discard(tid)
    await save_settings()
    await update_user_field(tid, "is_vip", False)
    await update.message.reply_text(f"✅ VIP لابرا: <code>{tid}</code>", parse_mode=ParseMode.HTML)


async def owner_cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /broadcast — ڕیپلایی نامەیەک بکە بنێرێت بۆ هەمووان"""
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ تکایە ڕیپلای نامەیەکی بکە پاشان /broadcast بنووسە."); return
    all_ids   = await get_all_user_ids()
    success, fail = 0, 0
    for tuid in all_ids:
        try:
            await context.bot.copy_message(
                chat_id    = tuid,
                from_chat_id = update.message.reply_to_message.chat_id,
                message_id   = update.message.reply_to_message.message_id,
            )
            success += 1
            await asyncio.sleep(0.04)
        except:
            fail += 1
    await update.message.reply_text(
        f"📢 برۆدکاست تەواوبوو!\n✅ {success} گەیشت\n❌ {fail} نەگەیشت"
    )


async def owner_cmd_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /user [id] بۆ زانیاری بەکارهێنەر"""
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("بەکارهێنان: /user [ئایدی]"); return
    tid   = int(args[0])
    udata = await get_user_data(tid)
    if not udata:
        await update.message.reply_text("⚠️ بەکارهێنەر نەدۆزرایەوە."); return
    lang = await get_user_lang(uid)
    vip_s = "✅" if tid in vip_users or udata.get("is_vip") else "❌"
    blk_s = "✅" if tid in blocked_users else "❌"
    await update.message.reply_text(
        t(lang,"user_info_text",
          id=tid,
          name=html.escape(str(udata.get("name","?"))),
          username=udata.get("username","—"),
          date=udata.get("joined_date","—"),
          vip=vip_s, blocked=blk_s,
        ),
        parse_mode=ParseMode.HTML,
    )


async def owner_cmd_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /maint بۆ گۆڕانی دۆخی چاکسازی"""
    uid = update.effective_user.id
    if not is_owner(uid):
        return
    bot_settings_global["maintenance_mode"] = not bot_settings_global["maintenance_mode"]
    await save_settings()
    st = "🔴 چالاک" if bot_settings_global["maintenance_mode"] else "🟢 ناچالاک"
    await update.message.reply_text(f"🛠 دۆخی چاکسازی: <b>{st}</b>", parse_mode=ParseMode.HTML)


async def owner_cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /addadmin [id]"""
    uid = update.effective_user.id
    if not is_owner(uid):
        await update.message.reply_text("⛔ تەنیا خاوەن!"); return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("بەکارهێنان: /addadmin [ئایدی]"); return
    admins_list.add(int(args[0]))
    await save_settings()
    await update.message.reply_text(f"✅ ئەدمین زیادکرا: <code>{args[0]}</code>", parse_mode=ParseMode.HTML)


async def owner_cmd_rmadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /rmadmin [id]"""
    uid = update.effective_user.id
    if not is_owner(uid):
        await update.message.reply_text("⛔ تەنیا خاوەن!"); return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("بەکارهێنان: /rmadmin [ئایدی]"); return
    if int(args[0]) == OWNER_ID:
        await update.message.reply_text("⛔ ناتوانیت خاوەنەکە لابەری!"); return
    admins_list.discard(int(args[0]))
    await save_settings()
    await update.message.reply_text(f"✅ ئەدمین لابرا: <code>{args[0]}</code>", parse_mode=ParseMode.HTML)


async def owner_cmd_addchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /addchannel [@channel]"""
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if not args:
        await update.message.reply_text("بەکارهێنان: /addchannel [@channel]"); return
    ch = args[0] if args[0].startswith("@") else f"@{args[0]}"
    if ch not in forced_channels:
        forced_channels.append(ch)
        await save_settings()
    await update.message.reply_text(f"✅ چەناڵ زیادکرا: <b>{ch}</b>", parse_mode=ParseMode.HTML)


async def owner_cmd_rmchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /rmchannel [@channel]"""
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if not args:
        await update.message.reply_text("بەکارهێنان: /rmchannel [@channel]"); return
    ch = args[0] if args[0].startswith("@") else f"@{args[0]}"
    if ch in forced_channels:
        forced_channels.remove(ch)
        await save_settings()
    await update.message.reply_text(f"✅ چەناڵ لابرا: <b>{ch}</b>", parse_mode=ParseMode.HTML)


# ==============================================================================
# ── تۆمارکردنی فەرمانە نوێیەکان بۆ ptb_app ────────────────────────────────────
# ==============================================================================
ptb_app.add_handler(CommandHandler("stats",       owner_cmd_stats))
ptb_app.add_handler(CommandHandler("ban",         owner_cmd_ban))
ptb_app.add_handler(CommandHandler("unban",       owner_cmd_unban))
ptb_app.add_handler(CommandHandler("addvip",      owner_cmd_addvip))
ptb_app.add_handler(CommandHandler("rmvip",       owner_cmd_rmvip))
ptb_app.add_handler(CommandHandler("broadcast",   owner_cmd_broadcast))
ptb_app.add_handler(CommandHandler("user",        owner_cmd_userinfo))
ptb_app.add_handler(CommandHandler("maint",       owner_cmd_maintenance))
ptb_app.add_handler(CommandHandler("addadmin",    owner_cmd_addadmin))
ptb_app.add_handler(CommandHandler("rmadmin",     owner_cmd_rmadmin))
ptb_app.add_handler(CommandHandler("addchannel",  owner_cmd_addchannel))
ptb_app.add_handler(CommandHandler("rmchannel",   owner_cmd_rmchannel))

# ==============================================================================
# ========================= کۆتایی فایل (END OF FILE) ==========================
# ==============================================================================
