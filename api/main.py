# ==============================================================================
# ==============================================================================
# ==                                                                          ==
# ==         TIKTOK DOWNLOADER - ULTRA LEGENDARY EDITION v7.0                ==
# ==                                                                          ==
# ==   • Dev:         @j4ck_721s (﮼جــاڪ ,.⏳🤎)                              ==
# ==   • Version:     7.0 (Ultra Legendary - Full Rewrite & Bug Fix)         ==
# ==   • Features:    Multi-Language, Mega Owner Panel, VIP, Photo Fix       ==
# ==                  Smart Session, Retry Logic, Rate-Limit Safe            ==
# ==                  Anti-Flood, Inline Numpad, Full Admin Control          ==
# ==                                                                          ==
# ==============================================================================
# ==============================================================================

import os
import io
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
from telegram.error import TelegramError, BadRequest, Forbidden, RetryAfter

# ==============================================================================
# ─── CONFIG ───────────────────────────────────────────────────────────────────
# ==============================================================================
TOKEN          = os.getenv("BOT_TOKEN")
API_URL        = "https://www.api.hyper-bd.site/Tiktok/?url="
API_URL_BACKUP = "https://www.tikwm.com/api/?url="
CHANNEL_URL    = "https://t.me/jack_721_mod"
DB_URL         = os.getenv("DB_URL")
DB_SECRET      = os.getenv("DB_SECRET")

OWNER_ID           = 5977475208
DEVELOPER_USERNAME = "@j4ck_721s"

# ==============================================================================
# ─── GLOBALS ──────────────────────────────────────────────────────────────────
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
    "bot_version"       : "7.0",
    "photo_mode"        : "auto",
    "max_photos"        : 10,
    "api_timeout"       : 60,
    "allow_forward"     : True,
    "vip_bypass_join"   : True,
    "admin_bypass_join" : True,
    "log_downloads"     : True,
    "auto_delete_sec"   : 0,
    "default_lang"      : "ku",
    "anti_flood"        : True,
    "max_retries"       : 3,
}

SESSION_EXPIRE = 600
API_TIMEOUT    = 60
START_TIME     = time.time()

# دۆخی چاوەڕوانی کردنی ئەدمین
admin_waiting_state: dict[int, str] = {}

# Anti-flood tracker
flood_tracker: dict[int, list] = {}

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s | %(levelname)s | %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
app    = FastAPI()

# ==============================================================================
# ─── LANGUAGES ────────────────────────────────────────────────────────────────
# ==============================================================================
LANGUAGES = {
    "ku": {
        "welcome_title"         : "👋 <b>سڵاو {name} {badge}</b>",
        "welcome_intro"         : "🤖 <b>من بۆتێکی پێشکەوتووم بۆ دابەزاندنی تیکتۆک!</b>",
        "welcome_features"      : (
            "📥 دەتوانیت دابەزێنیت:\n"
            "   🎥 ڤیدیۆ بێ لۆگۆ\n"
            "   📸 وێنەکانی Slideshow\n"
            "   🎵 گۆرانی / MP3"
        ),
        "welcome_prompt"        : "👇 <b>لینک بنێرە یان دوگمە دابگرە:</b>",
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
        "force_join_text"       : "🔒 <b>جۆینی ناچاری</b>\nبۆ بەکارهێنان، تکایە جۆینی ئەم چەناڵانە بکە:",
        "btn_join_channel"      : "📢 جۆین کردن: {ch}",
        "btn_check_join"        : "✅ جۆینم کرد، دەستپێکردن",
        "help_title"            : "📚 <b>ڕێنمایی بەکارهێنان</b>",
        "help_text"             : (
            "<b>📱 چۆن دایبەزێنم؟</b>\n"
            "1️⃣ لە تیکتۆک «Share» دابگرە و «Copy Link» بکە.\n"
            "2️⃣ لینکەکە لێرە بنێرە وەک نامەیەک.\n"
            "3️⃣ فۆرماتێک هەڵبژێرە و دابەزێنە!\n\n"
            "<b>📥 چی دابەزێنم؟</b>\n"
            "🎥 ڤیدیۆ بێ لۆگۆ\n"
            "📸 وێنەکانی Slideshow\n"
            "🎵 گۆرانی / MP3\n\n"
            "<b>ℹ️ زانیاری تر:</b>\n"
            "• VIP بەکارهێنەرەکان بێ جۆین چەناڵ دەتوانن بەکاربێنن.\n"
            f"• پەیوەندی بکە بە: {DEVELOPER_USERNAME}"
        ),
        "download_prompt"       : "<b>🔗 تکایە لینکی تیکتۆکەکە لێرەدا پەیست بکە و بۆمی بنێرە:</b>",
        "profile_title"         : "👤 <b>پرۆفایلی بەکارهێنەر</b>",
        "profile_id"            : "🆔 <b>ئایدی:</b> <code>{id}</code>",
        "profile_name"          : "👤 <b>ناو:</b> {name}",
        "profile_username"      : "🔗 <b>یوزەرنەیم:</b> @{username}",
        "profile_join_date"     : "📅 <b>بەروار تۆمارکردن:</b> {date}",
        "profile_vip_status"    : "💎 <b>هەژماری VIP:</b> {status}",
        "profile_total_dl"      : "📥 <b>داونلۆدەکانت:</b> {count}",
        "vip_yes"               : "بەڵێ 💎",
        "vip_no"                : "نەخێر (Free)",
        "download_found"        : "✅ <b>بە سەرکەوتوویی دۆزرایەوە!</b>",
        "download_title"        : "📝 <b>پۆست:</b> {title}",
        "download_owner"        : "👤 <b>خاوەن:</b> {owner}",
        "download_views"        : "👁 <code>{views}</code> بینەر",
        "download_likes"        : "❤️ <code>{likes}</code> لایک",
        "download_comments"     : "💬 <code>{comments}</code> کۆمێنت",
        "btn_video"             : "🎥 داونلۆدی ڤیدیۆ (بێ لۆگۆ)",
        "btn_photos"            : "📸 داونلۆدی وێنەکان ({count})",
        "btn_audio"             : "🎵 داونلۆدی گۆرانی (MP3)",
        "error_admin_only"      : "⛔ ئەم بەشە تەنیا بۆ ئەدمینەکانە!",
        "error_owner_only"      : "⛔ ئەم بەشە تەنیا بۆ خاوەنی سەرەکییە!",
        "error_blocked"         : "⛔ <b>ببورە، تۆ بلۆک کراویت.</b>",
        "error_maintenance"     : "🛠 <b>بۆتەکە لە باری چاکسازیدایە. تکایە چاوەڕوان بە!</b>",
        "error_session_expired" : "⚠️ کاتەکەت بەسەرچوو، تکایە لینکەکە دووبارە بنێرەوە.",
        "error_download_fail"   : "❌ هەڵەیەک ڕوویدا. تکایە دووبارە هەوڵبدەوە.",
        "error_invalid_link"    : "❌ لینکەکە دروست نییە یان بلۆک کراوە!",
        "error_flood"           : "⏳ زۆر زیاد نامەت ناردووە! کەمێک چاوەڕوان بە.",
        "lang_select_title"     : "🌍 <b>زمان هەڵبژێرە | Select Language</b>",
        "lang_select_prompt"    : "تکایە زمانێک هەڵبژێرە:",
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
        "downloading"           : "⏳ <b>داونلۆد دەکرێت...</b>",
        "searching"             : "🔍 <b>گەڕان دەکرێت...</b>",
        "photos_sending"        : "📸 <b>وێنەکان دەنێردرێن ({current}/{total})...</b>",
        "download_complete"     : "✅ <b>داونلۆد تەواو بوو!</b>",
        "photo_fallback"        : "⚠️ <b>وێنەکان لێرەوە دابەزێنە:</b>",
        "video_fallback"        : "⚠️ <b>ڤیدیۆ لێرەوە دابەزێنە:</b>",
        "audio_fallback"        : "⚠️ <b>گۆرانی لێرەوە دابەزێنە:</b>",
        "api_retry"             : "🔄 <b>دووبارەهەوڵدانەوە... ({n}/{max})</b>",
        "no_video_url"          : "❌ ئەم پۆستە ڤیدیۆی نییە!",
        "no_audio_url"          : "❌ ئەم پۆستە گۆرانیی نییە!",
        "no_photos_url"         : "❌ ئەم پۆستە وێنەی نییە!",
        "vip_features"          : (
            "✅ خێرایی داونلۆدی زیاتر.\n"
            "✅ بێ جۆین کردنی چەناڵ.\n"
            "✅ داونلۆدی بێسنوور بۆ وێنەکان.\n"
            "✅ گەیشتن بە تایبەتمەندییە تازەکان.\n\n"
            f"💳 <b>پەیوەندی بکە بە:</b> {DEVELOPER_USERNAME}"
        ),
    },
    "en": {
        "welcome_title"         : "👋 <b>Welcome {name} {badge}</b>",
        "welcome_intro"         : "🤖 <b>I am an advanced TikTok downloader bot!</b>",
        "welcome_features"      : (
            "📥 You can download:\n"
            "   🎥 Video without watermark\n"
            "   📸 Slideshow photos\n"
            "   🎵 Audio / MP3"
        ),
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
        "download_prompt"       : "<b>🔗 Please paste the TikTok link here and send it:</b>",
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
        "error_flood"           : "⏳ Too many requests! Please wait a moment.",
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
        "downloading"           : "⏳ <b>Downloading...</b>",
        "searching"             : "🔍 <b>Searching...</b>",
        "photos_sending"        : "📸 <b>Sending photos ({current}/{total})...</b>",
        "download_complete"     : "✅ <b>Download complete!</b>",
        "photo_fallback"        : "⚠️ <b>Download photos from here:</b>",
        "video_fallback"        : "⚠️ <b>Download video from here:</b>",
        "audio_fallback"        : "⚠️ <b>Download audio from here:</b>",
        "api_retry"             : "🔄 <b>Retrying... ({n}/{max})</b>",
        "no_video_url"          : "❌ This post has no video!",
        "no_audio_url"          : "❌ This post has no audio!",
        "no_photos_url"         : "❌ This post has no photos!",
        "vip_features"          : (
            "✅ Faster download speed.\n"
            "✅ No channel join required.\n"
            "✅ Unlimited photo downloads.\n"
            "✅ Access to new features.\n\n"
            f"💳 <b>Contact:</b> {DEVELOPER_USERNAME}"
        ),
    },
    "ar": {
        "welcome_title"         : "👋 <b>أهلاً بك {name} {badge}</b>",
        "welcome_intro"         : "🤖 <b>أنا بوت متقدم لتحميل فيديوهات تيك توك!</b>",
        "welcome_features"      : (
            "📥 يمكنك تحميل:\n"
            "   🎥 فيديو بدون علامة مائية\n"
            "   📸 صور عرض الشرائح\n"
            "   🎵 الصوت / MP3"
        ),
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
        "force_join_text"       : "🔒 <b>الاشتراك الإجباري</b>\nلاستخدام البوت، يرجى الانضمام إلى هذه القنوات:",
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
        "download_prompt"       : "<b>🔗 الرجاء لصق رابط تيك توك هنا وإرساله:</b>",
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
        "error_flood"           : "⏳ طلبات كثيرة جداً! يرجى الانتظار لحظة.",
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
        "downloading"           : "⏳ <b>جاري التحميل...</b>",
        "searching"             : "🔍 <b>جاري البحث...</b>",
        "photos_sending"        : "📸 <b>إرسال الصور ({current}/{total})...</b>",
        "download_complete"     : "✅ <b>اكتمل التحميل!</b>",
        "photo_fallback"        : "⚠️ <b>حمّل الصور من هنا:</b>",
        "video_fallback"        : "⚠️ <b>حمّل الفيديو من هنا:</b>",
        "audio_fallback"        : "⚠️ <b>حمّل الصوت من هنا:</b>",
        "api_retry"             : "🔄 <b>إعادة المحاولة... ({n}/{max})</b>",
        "no_video_url"          : "❌ هذا المنشور لا يحتوي على فيديو!",
        "no_audio_url"          : "❌ هذا المنشور لا يحتوي على صوت!",
        "no_photos_url"         : "❌ هذا المنشور لا يحتوي على صور!",
        "vip_features"          : (
            "✅ سرعة تحميل أعلى.\n"
            "✅ بدون الاشتراك في القنوات.\n"
            "✅ تحميل صور غير محدود.\n"
            "✅ الوصول إلى الميزات الجديدة.\n\n"
            f"💳 <b>للتواصل:</b> {DEVELOPER_USERNAME}"
        ),
    },
}


async def get_user_lang(user_id: int) -> str:
    """دەگەڕێنێتەوە زمانی بەکارهێنەر لە داتابەیس"""
    if not DB_URL:
        return bot_settings_global.get("default_lang", "ku")
    async with httpx.AsyncClient(timeout=10) as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}/language"))
            if r.status_code == 200 and r.json():
                lang = str(r.json())
                if lang in LANGUAGES:
                    return lang
        except Exception:
            pass
    return bot_settings_global.get("default_lang", "ku")


def t(lang: str, key: str, **kwargs) -> str:
    """وەرگێڕانی نامەکان"""
    base = LANGUAGES.get(lang, LANGUAGES["ku"])
    text = base.get(key) or LANGUAGES["ku"].get(key, key)
    try:
        return text.format(**kwargs)
    except Exception:
        return text

# ==============================================================================
# ─── HELPERS ──────────────────────────────────────────────────────────────────
# ==============================================================================

def get_random_id(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def clean_title(title: str) -> str:
    if not title:
        return "TikTok"
    cleaned = re.sub(r'[\\/*?:"<>|#@]', "", title)
    return cleaned[:80].strip() or "TikTok"


def firebase_url(path: str) -> str:
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"


def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d | %I:%M:%S %p")


def get_uptime() -> str:
    s = int(time.time() - START_TIME)
    d, r   = divmod(s, 86400)
    h, r   = divmod(r, 3600)
    m, sec = divmod(r, 60)
    return f"{d}d {h}h {m}m {sec}s"


def format_number(n) -> str:
    try:
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except Exception:
        return str(n)


def back_btn(lang: str, target: str = "cmd_start") -> list:
    return [[InlineKeyboardButton(t(lang, "btn_back"), callback_data=target)]]


def divider() -> str:
    return "━━━━━━━━━━━━━━━━━━━"


def is_tiktok_url(text: str) -> bool:
    """پشکنینی ئایا لینک تیکتۆکە"""
    patterns = [
        r"tiktok\.com",
        r"vm\.tiktok\.com",
        r"vt\.tiktok\.com",
        r"m\.tiktok\.com",
    ]
    return any(re.search(p, text) for p in patterns)


# ==============================================================================
# ─── ANTI-FLOOD ───────────────────────────────────────────────────────────────
# ==============================================================================

def check_flood(uid: int, limit: int = 5, window: int = 10) -> bool:
    """True گەڕاندنەوە ئەگەر فڵۆد بوو"""
    if not bot_settings_global.get("anti_flood", True):
        return False
    now = time.time()
    if uid not in flood_tracker:
        flood_tracker[uid] = []
    # سڕینەوەی کاتە کۆنەکان
    flood_tracker[uid] = [t for t in flood_tracker[uid] if now - t < window]
    flood_tracker[uid].append(now)
    return len(flood_tracker[uid]) > limit

# ==============================================================================
# ─── SECURITY ─────────────────────────────────────────────────────────────────
# ==============================================================================

def is_owner(uid: int) -> bool:   return uid == OWNER_ID
def is_admin(uid: int) -> bool:   return uid in admins_list or uid == OWNER_ID
def is_blocked(uid: int) -> bool: return uid in blocked_users
def is_vip(uid: int) -> bool:     return uid in vip_users or uid == OWNER_ID


async def check_user_subscription(user_id: int, context) -> tuple[bool, list]:
    """پشکنینی جۆین بوونی بەکارهێنەر"""
    if not forced_channels:
        return True, []
    not_joined = []
    for ch in forced_channels:
        try:
            m = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                not_joined.append(ch)
        except Exception:
            pass
    return len(not_joined) == 0, not_joined

# ==============================================================================
# ─── DATABASE ─────────────────────────────────────────────────────────────────
# ==============================================================================

async def load_settings():
    """هێنانی ڕێکخستنەکان لە فایەربەیس"""
    global admins_list, forced_channels, blocked_users, vip_users, bot_settings_global
    if not DB_URL:
        return
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(firebase_url("system_settings"))
            if r.status_code == 200 and r.json():
                d = r.json()
                admins_list     = set(d.get("admins",   [OWNER_ID]))
                forced_channels = d.get("channels",     [])
                blocked_users   = set(d.get("blocked",  []))
                vip_users       = set(d.get("vips",     []))
                bot_settings_global.update(d.get("settings", {}))
                admins_list.add(OWNER_ID)  # ✅ FIX: خاوەن هەمیشە ئەدمینە
                logger.info("✅ داتابەیس هێنرایەوە.")
        except Exception as e:
            logger.error(f"❌ هەڵەی داتابەیس: {e}")


async def save_settings():
    """پاراستنی ڕێکخستنەکان"""
    if not DB_URL:
        return
    admins_list.add(OWNER_ID)  # ✅ FIX: ئارەزووکردنی خاوەن
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
    """پاراستنی سیشنی بەکارهێنەر"""
    if not DB_URL:
        return
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            await c.put(firebase_url(f"user_sessions/{user_id}"), json=data)
        except Exception:
            pass


async def get_user_session(user_id: int) -> dict | None:
    """هێنانی سیشنی بەکارهێنەر"""
    if not DB_URL:
        return None
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            r = await c.get(firebase_url(f"user_sessions/{user_id}"))
            if r.status_code == 200 and r.json():
                d = r.json()
                if int(time.time()) - d.get("timestamp", 0) <= SESSION_EXPIRE:
                    return d
        except Exception:
            pass
    return None


async def is_user_registered(user_id: int) -> bool:
    if not DB_URL:
        return False
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}"))
            return r.status_code == 200 and r.json() is not None
        except Exception:
            return False


async def register_user(user_id: int, info: dict):
    if not DB_URL:
        return
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            await c.put(firebase_url(f"registered_users/{user_id}"), json=info)
        except Exception:
            pass


async def get_user_data(user_id: int) -> dict | None:
    if not DB_URL:
        return None
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            r = await c.get(firebase_url(f"registered_users/{user_id}"))
            if r.status_code == 200 and r.json():
                return r.json()
        except Exception:
            pass
    return None


async def update_user_field(user_id: int, field: str, value):
    if not DB_URL:
        return
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            await c.put(firebase_url(f"registered_users/{user_id}/{field}"), json=value)
        except Exception:
            pass


async def get_all_user_ids() -> list[int]:
    if not DB_URL:
        return []
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(firebase_url("registered_users"))
            if r.status_code == 200 and r.json():
                return [int(k) for k in r.json().keys()]
        except Exception:
            pass
    return []


async def get_all_users_data() -> dict:
    if not DB_URL:
        return {}
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            r = await c.get(firebase_url("registered_users"))
            if r.status_code == 200 and r.json():
                return r.json()
        except Exception:
            pass
    return {}


async def delete_all_users():
    if not DB_URL:
        return
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as c:
        try:
            await c.delete(firebase_url("registered_users"))
        except Exception:
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
    except Exception:
        pass

# ==============================================================================
# ─── DOWNLOAD ENGINE ──────────────────────────────────────────────────────────
# ==============================================================================

async def fetch_tiktok_data(url: str, max_retries: int = 3) -> dict | None:
    """
    ✅ FIX: زیاتر retry، بەرپرسایەتی هەموو API فۆرماتەکان،
    نۆرمالایزکردنی ووردی داتای بەکاپ.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; SM-G975F) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.120 Mobile Safari/537.36"
        ),
        "Accept"         : "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer"        : "https://www.tiktok.com/",
    }

    timeout = int(bot_settings_global.get("api_timeout", 60))

    for attempt in range(1, max_retries + 1):
        async with httpx.AsyncClient(
            timeout       = timeout,
            headers       = headers,
            follow_redirects = True,
        ) as c:
            # ── API سەرەکی ─────────────────────────────────────────────────
            try:
                r = await c.get(API_URL + url)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("ok") or data.get("status") == "success":
                        logger.info(f"✅ API سەرەکی سەرکەوتوو (attempt {attempt})")
                        return {"source": "primary", "data": data}
            except Exception as e:
                logger.warning(f"⚠️ API سەرەکی سەرکەوتوو نەبوو (attempt {attempt}): {e}")

            # ── API بەکاپ ──────────────────────────────────────────────────
            try:
                r2 = await c.get(API_URL_BACKUP + url)
                if r2.status_code == 200:
                    raw = r2.json()
                    if raw.get("code") == 0 and raw.get("data"):
                        d = raw["data"]
                        author = d.get("author") or {}

                        # ✅ FIX: وێنەکان لە backup بۆ شێوازی ستاندارد
                        images_raw = d.get("images") or []
                        clean_images = []
                        for img in images_raw:
                            if isinstance(img, str):
                                clean_images.append(img)
                            elif isinstance(img, dict):
                                url_list = img.get("url_list") or []
                                if url_list:
                                    clean_images.append(url_list[0])
                                elif img.get("url"):
                                    clean_images.append(img["url"])

                        normalized = {
                            "ok"   : True,
                            "data" : {
                                "creator": author.get("nickname") or author.get("unique_id") or "Unknown",
                                "details": {
                                    "title"  : d.get("title", ""),
                                    "cover"  : {
                                        "cover": d.get("cover", ""),
                                        "origin_cover": d.get("origin_cover", ""),
                                    },
                                    "images" : clean_images,
                                    "video"  : {
                                        "play"          : d.get("play", "") or d.get("wmplay", ""),
                                        "download_addr" : d.get("download", "") or d.get("play", ""),
                                    },
                                    "audio"  : {
                                        "play"  : d.get("music", "") or d.get("music_info", {}).get("play", ""),
                                        "music" : d.get("music", ""),
                                    },
                                    "stats"  : {
                                        "views"   : d.get("play_count", 0),
                                        "likes"   : d.get("digg_count", 0),
                                        "comments": d.get("comment_count", 0),
                                        "shares"  : d.get("share_count", 0),
                                    },
                                }
                            }
                        }
                        logger.info(f"✅ API بەکاپ سەرکەوتوو (attempt {attempt})")
                        return {"source": "backup", "data": normalized}
            except Exception as e:
                logger.warning(f"⚠️ API بەکاپیش سەرکەوتوو نەبوو (attempt {attempt}): {e}")

        # چاوەڕوانکردن پێش retry
        if attempt < max_retries:
            await asyncio.sleep(attempt * 1.5)

    logger.error(f"❌ هەموو {max_retries} هەوڵ سەرکەوتوو نەبوون بۆ: {url}")
    return None


def parse_api_response(raw: dict) -> tuple[str, dict, list]:
    """
    ✅ FIX: گەڕاندنەوەی (creator, details, images)
    بەرپرسایەتی هەموو فۆرماتی وەڵامی API دەکات.
    """
    data    = raw.get("data", {})
    creator = (
        data.get("creator") or
        data.get("author", {}).get("nickname") or
        "Unknown"
    )
    details = data.get("details", {})

    # ✅ FIX: دۆزینەوەی وێنەکان لە ئامانجی جیاوازەکان
    images_raw = (
        details.get("images") or
        details.get("image_list") or
        data.get("images") or
        []
    )

    clean_images = []
    for img in images_raw:
        if isinstance(img, str) and img.startswith("http"):
            clean_images.append(img)
        elif isinstance(img, dict):
            url_val = (
                (img.get("url_list") or [None])[0]  or
                img.get("url")                       or
                img.get("download_url")              or
                (img.get("display_image") or {}).get("url_list", [None])[0]
            )
            if url_val and isinstance(url_val, str) and url_val.startswith("http"):
                clean_images.append(url_val)

    return creator, details, clean_images


async def safe_send_photo(context, chat_id: int, photo_url: str, **kwargs) -> bool:
    """ناردنی وێنە بە شێوازی ئارام — True ئەگەر سەرکەوتوو بوو"""
    try:
        await context.bot.send_photo(chat_id=chat_id, photo=photo_url, **kwargs)
        return True
    except Exception as e:
        logger.warning(f"send_photo هەڵە: {e}")
        return False

# ==============================================================================
# ─── COMMANDS ─────────────────────────────────────────────────────────────────
# ==============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /start"""
    user  = update.effective_user
    uid   = user.id
    lang  = await get_user_lang(uid)
    is_cb = bool(update.callback_query)

    async def send(text: str, kb: list):
        markup = InlineKeyboardMarkup(kb)
        if is_cb:
            try:
                await update.callback_query.edit_message_text(
                    text, parse_mode=ParseMode.HTML, reply_markup=markup
                )
            except BadRequest:
                await update.callback_query.message.reply_text(
                    text, parse_mode=ParseMode.HTML, reply_markup=markup
                )
        else:
            await update.message.reply_text(
                text, parse_mode=ParseMode.HTML, reply_markup=markup
            )

    if is_blocked(uid):
        await send(t(lang, "error_blocked"), back_btn(lang, "cmd_start"))
        return

    if bot_settings_global["maintenance_mode"] and not is_admin(uid):
        await send(t(lang, "error_maintenance"), back_btn(lang, "cmd_start"))
        return

    # تۆمارکردنی بەکارهێنەر
    if not await is_user_registered(uid):
        asyncio.create_task(notify_owner_new_user(context, user))
        bot_settings_global["total_users"] = bot_settings_global.get("total_users", 0) + 1
        await register_user(uid, {
            "name"       : user.first_name,
            "username"   : user.username or "",
            "joined_date": get_current_time(),
            "is_vip"     : False,
            "language"   : bot_settings_global.get("default_lang", "ku"),
            "downloads"  : 0,
        })

    # پشکنینی جۆین
    is_sub, not_joined = await check_user_subscription(uid, context)
    bypass = (
        (is_admin(uid) and bot_settings_global.get("admin_bypass_join", True)) or
        (is_vip(uid)   and bot_settings_global.get("vip_bypass_join",   True))
    )
    if not is_sub and not bypass:
        kb  = [
            [InlineKeyboardButton(
                t(lang, "btn_join_channel", ch=ch),
                url=f"https://t.me/{ch.replace('@', '')}"
            )]
            for ch in not_joined
        ]
        kb += [[InlineKeyboardButton(t(lang, "btn_check_join"), callback_data="check_sub_start")]]
        await send(t(lang, "force_join_text"), kb)
        return

    # بیجدج
    BADGES = {
        "owner": {"ku": "👑 خاوەن",  "en": "👑 Owner",  "ar": "👑 المالك"},
        "admin": {"ku": "⚡ ئەدمین", "en": "⚡ Admin",  "ar": "⚡ مسؤول"},
        "vip"  : {"ku": "💎 VIP",   "en": "💎 VIP",   "ar": "💎 VIP"},
        "free" : {"ku": "",          "en": "",          "ar": ""},
    }
    if is_owner(uid):
        badge = BADGES["owner"].get(lang, "")
    elif is_admin(uid):
        badge = BADGES["admin"].get(lang, "")
    elif is_vip(uid):
        badge = BADGES["vip"].get(lang, "")
    else:
        badge = ""

    # نامەی خۆشامەدێ
    custom_welcome = bot_settings_global.get("welcome_msg", "")
    if custom_welcome and not is_admin(uid):
        text = (
            custom_welcome
            .replace("{name}", html.escape(user.first_name))
            .replace("{badge}", badge)
        )
    else:
        text = (
            f"╔{'═'*23}╗\n"
            f"  {t(lang, 'welcome_title', name=html.escape(user.first_name), badge=badge)}\n"
            f"╚{'═'*23}╝\n\n"
            f"{t(lang, 'welcome_intro')}\n\n"
            f"{t(lang, 'welcome_features')}\n\n"
            f"{divider()}\n"
            f"{t(lang, 'welcome_prompt')}"
        )

    kb = [
        [InlineKeyboardButton(t(lang, "btn_download"),  callback_data="cmd_download")],
        [
            InlineKeyboardButton(t(lang, "btn_profile"), callback_data="menu_profile"),
            InlineKeyboardButton(t(lang, "btn_vip"),     callback_data="menu_vip"),
        ],
        [
            InlineKeyboardButton(t(lang, "btn_settings"), callback_data="menu_settings"),
            InlineKeyboardButton(t(lang, "btn_help"),     callback_data="cmd_help"),
        ],
        [InlineKeyboardButton(t(lang, "btn_channel"), url=CHANNEL_URL)],
    ]
    if is_admin(uid):
        kb.append([InlineKeyboardButton(t(lang, "btn_admin_panel"), callback_data="admin_main")])
    if is_owner(uid):
        kb.append([InlineKeyboardButton(t(lang, "btn_owner_panel"), callback_data="owner_main")])

    await send(text, kb)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فەرمانی /help"""
    uid  = update.effective_user.id
    lang = await get_user_lang(uid)
    text = (
        f"╔{'═'*23}╗\n"
        f"  {t(lang, 'help_title')}\n"
        f"╚{'═'*23}╝\n\n"
        f"{t(lang, 'help_text')}"
    )
    kb = back_btn(lang)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
            )
        except BadRequest:
            await update.callback_query.message.reply_text(
                text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
            )
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb)
        )

# ==============================================================================
# ─── NUMPAD HELPERS ───────────────────────────────────────────────────────────
# ==============================================================================

def build_numpad(action: str, current: str = "") -> InlineKeyboardMarkup:
    display = f"📟 <code>{current}</code>" if current else "📟 ئایدی داخڵ بکە..."
    rows = [
        [
            InlineKeyboardButton("1", callback_data=f"np_{action}_1"),
            InlineKeyboardButton("2", callback_data=f"np_{action}_2"),
            InlineKeyboardButton("3", callback_data=f"np_{action}_3"),
        ],
        [
            InlineKeyboardButton("4", callback_data=f"np_{action}_4"),
            InlineKeyboardButton("5", callback_data=f"np_{action}_5"),
            InlineKeyboardButton("6", callback_data=f"np_{action}_6"),
        ],
        [
            InlineKeyboardButton("7", callback_data=f"np_{action}_7"),
            InlineKeyboardButton("8", callback_data=f"np_{action}_8"),
            InlineKeyboardButton("9", callback_data=f"np_{action}_9"),
        ],
        [
            InlineKeyboardButton("⌫ سڕینەوە", callback_data=f"np_{action}_back"),
            InlineKeyboardButton("0",          callback_data=f"np_{action}_0"),
            InlineKeyboardButton("✅ پشتگیری", callback_data=f"np_{action}_ok"),
        ],
        [InlineKeyboardButton("❌ هەڵوەشاندنەوە", callback_data="np_cancel")],
    ]
    return InlineKeyboardMarkup(rows)


def build_ch_input(current: str = "") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("a", callback_data="chi_a"),
            InlineKeyboardButton("b", callback_data="chi_b"),
            InlineKeyboardButton("c", callback_data="chi_c"),
            InlineKeyboardButton("d", callback_data="chi_d"),
            InlineKeyboardButton("e", callback_data="chi_e"),
        ],
        [
            InlineKeyboardButton("f", callback_data="chi_f"),
            InlineKeyboardButton("g", callback_data="chi_g"),
            InlineKeyboardButton("h", callback_data="chi_h"),
            InlineKeyboardButton("i", callback_data="chi_i"),
            InlineKeyboardButton("j", callback_data="chi_j"),
        ],
        [
            InlineKeyboardButton("k", callback_data="chi_k"),
            InlineKeyboardButton("l", callback_data="chi_l"),
            InlineKeyboardButton("m", callback_data="chi_m"),
            InlineKeyboardButton("n", callback_data="chi_n"),
            InlineKeyboardButton("o", callback_data="chi_o"),
        ],
        [
            InlineKeyboardButton("p", callback_data="chi_p"),
            InlineKeyboardButton("q", callback_data="chi_q"),
            InlineKeyboardButton("r", callback_data="chi_r"),
            InlineKeyboardButton("s", callback_data="chi_s"),
            InlineKeyboardButton("t", callback_data="chi_t"),
        ],
        [
            InlineKeyboardButton("u", callback_data="chi_u"),
            InlineKeyboardButton("v", callback_data="chi_v"),
            InlineKeyboardButton("w", callback_data="chi_w"),
            InlineKeyboardButton("x", callback_data="chi_x"),
            InlineKeyboardButton("y", callback_data="chi_y"),
        ],
        [
            InlineKeyboardButton("z", callback_data="chi_z"),
            InlineKeyboardButton("_", callback_data="chi__"),
            InlineKeyboardButton(".", callback_data="chi_."),
            InlineKeyboardButton("1", callback_data="chi_1"),
            InlineKeyboardButton("2", callback_data="chi_2"),
        ],
        [
            InlineKeyboardButton("3", callback_data="chi_3"),
            InlineKeyboardButton("4", callback_data="chi_4"),
            InlineKeyboardButton("5", callback_data="chi_5"),
            InlineKeyboardButton("6", callback_data="chi_6"),
            InlineKeyboardButton("7", callback_data="chi_7"),
        ],
        [
            InlineKeyboardButton("8",         callback_data="chi_8"),
            InlineKeyboardButton("9",         callback_data="chi_9"),
            InlineKeyboardButton("0",         callback_data="chi_0"),
            InlineKeyboardButton("⌫",         callback_data="chi_back"),
            InlineKeyboardButton("✅ تەواو",  callback_data="chi_ok"),
        ],
        [InlineKeyboardButton("❌ هەڵوەشاندنەوە", callback_data="np_cancel")],
    ]
    return InlineKeyboardMarkup(rows)

# ==============================================================================
# ─── CALLBACK HANDLER ─────────────────────────────────────────────────────────
# ==============================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بەڕێوەبردنی هەموو callback_queryەکان"""
    query = update.callback_query
    data  = query.data
    uid   = query.from_user.id
    lang  = await get_user_lang(uid)
    await query.answer()

    # ── ناڤیگەیشنی سەرەکی ──────────────────────────────────────────────────
    if data in ("check_sub_start", "cmd_start"):
        await start_command(update, context)
        return

    if data == "cmd_help":
        await help_command(update, context)
        return

    if data == "cmd_download":
        await query.message.reply_text(
            t(lang, "download_prompt"),
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True),
        )
        return

    if data == "close":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    # ── پرۆفایل ─────────────────────────────────────────────────────────────
    if data == "menu_profile":
        user_data = await get_user_data(uid)
        join_date = user_data.get("joined_date", "—") if user_data else "—"
        uname     = query.from_user.username or "—"
        dl_count  = user_data.get("downloads", 0) if user_data else 0
        text = (
            f"╔{'═'*23}╗\n"
            f"  {t(lang, 'profile_title')}\n"
            f"╚{'═'*23}╝\n\n"
            f"{t(lang, 'profile_id',        id=uid)}\n"
            f"{t(lang, 'profile_name',      name=html.escape(query.from_user.first_name))}\n"
            f"{t(lang, 'profile_username',  username=uname)}\n"
            f"{t(lang, 'profile_join_date', date=join_date)}\n"
            f"{t(lang, 'profile_vip_status', status=(t(lang,'vip_yes') if is_vip(uid) else t(lang,'vip_no')))}\n"
            f"{t(lang, 'profile_total_dl',  count=dl_count)}"
        )
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang))
        )
        return

    # ── VIP ──────────────────────────────────────────────────────────────────
    if data == "menu_vip":
        status = "💎 VIP" if is_vip(uid) else "🆓 Free"
        text = (
            f"╔{'═'*23}╗\n"
            f"  💎 <b>{t(lang, 'btn_vip')}</b>\n"
            f"╚{'═'*23}╝\n\n"
            f"<b>دۆخی ئێستا: {status}</b>\n\n"
            f"{t(lang, 'vip_features')}"
        )
        await query.edit_message_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang))
        )
        return

    # ── ڕێکخستنی زمان ────────────────────────────────────────────────────────
    if data == "menu_settings":
        kb = [
            [InlineKeyboardButton("🔴🔆🟢 کوردی",  callback_data="set_lang_ku")],
            [InlineKeyboardButton("🇺🇸 English",   callback_data="set_lang_en")],
            [InlineKeyboardButton("🇸🇦 العربية",  callback_data="set_lang_ar")],
            *back_btn(lang),
        ]
        await query.edit_message_text(
            f"🌍 <b>{t(lang, 'lang_select_title')}</b>\n\n{t(lang, 'lang_select_prompt')}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    if data.startswith("set_lang_"):
        new_lang = data.split("_")[2]
        if new_lang in LANGUAGES:
            await update_user_field(uid, "language", new_lang)
            await query.answer(f"✅ Language → {new_lang.upper()}", show_alert=True)
            await start_command(update, context)
        return

    # ── داونلۆد کردن ─────────────────────────────────────────────────────────
    if data.startswith("dl_"):
        await handle_download_action(update, context, data, uid, lang)
        return

    # ==========================================================================
    # ─── ADMIN PANEL ──────────────────────────────────────────────────────────
    # ==========================================================================
    if not is_admin(uid):
        await query.answer(t(lang, "error_admin_only"), show_alert=True)
        return

    # ── پانێڵی سەرەکی ────────────────────────────────────────────────────────
    if data == "admin_main":
        all_ids = await get_all_user_ids()
        maint   = "🔴 چالاک" if bot_settings_global["maintenance_mode"] else "🟢 ناچالاک"
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
        await query.edit_message_text(
            f"👑 <b>پانێڵی ئەدمین</b>\n\n"
            f"👥 بەکارهێنەر: <b>{len(all_ids)}</b>\n"
            f"🛠 چاکسازی: <b>{maint}</b>\n"
            f"🕐 {get_current_time()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    # ── ئامارەکان ────────────────────────────────────────────────────────────
    if data == "admin_stats":
        all_ids = await get_all_user_ids()
        text = (
            f"╔{'═'*23}╗\n"
            f"  📊 <b>ئاماری بۆت</b>\n"
            f"╚{'═'*23}╝\n\n"
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
            f"└ Uptime: {get_uptime()}\n\n"
            f"🕐 {get_current_time()}"
        )
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang, "btn_refresh"), callback_data="admin_stats")],
                *back_btn(lang, "admin_main"),
            ]),
        )
        return

    # ── برۆدکاست ─────────────────────────────────────────────────────────────
    if data == "admin_broadcast":
        kb = [
            [
                InlineKeyboardButton("📢 بۆ هەمووان",     callback_data="bc_type_all"),
                InlineKeyboardButton("💎 تەنیا VIP",      callback_data="bc_type_vip"),
            ],
            [
                InlineKeyboardButton("🆓 تەنیا Free",     callback_data="bc_type_free"),
                InlineKeyboardButton("✅ ئەنبلۆک کراوان", callback_data="bc_type_noblock"),
            ],
            *back_btn(lang, "admin_main"),
        ]
        await query.edit_message_text(
            "📢 <b>برۆدکاست</b>\n\nکێ دەوێیت نامەکەت پێبگات؟",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    if data.startswith("bc_type_"):
        bc_type = data.split("_")[2]
        admin_waiting_state[uid] = f"broadcast_{bc_type}"
        await query.edit_message_text(
            f"📢 <b>برۆدکاست — {bc_type.upper()}</b>\n\n"
            "✍️ نامەکەت بنووسە و بنێرە بۆ بۆتەکە:\n"
            "<i>(هەر جۆرێک دەبێت — تێکست، وێنە، ڤیدیۆ)</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ هەڵوەشاندنەوە", callback_data="admin_broadcast")
            ]]),
        )
        return

    # ── دۆخی چاکسازی ─────────────────────────────────────────────────────────
    if data == "admin_toggle_maint":
        if not is_owner(uid):
            await query.answer(t(lang, "error_owner_only"), show_alert=True)
            return
        bot_settings_global["maintenance_mode"] = not bot_settings_global["maintenance_mode"]
        await save_settings()
        st = "🔴 چالاک کرا" if bot_settings_global["maintenance_mode"] else "🟢 ناچالاک کرا"
        await query.edit_message_text(
            f"✅ دۆخی چاکسازی گۆڕدرا.\nئێستا: <b>{st}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang, "admin_main")),
        )
        return

    # ── زانیاری بەکارهێنەر ───────────────────────────────────────────────────
    if data == "admin_user_info_ask":
        context.user_data["np_action"] = "user_info"
        context.user_data["np_input"]  = ""
        await query.edit_message_text(
            "👤 <b>زانیاری بەکارهێنەر</b>\n\n📟 ئایدی داخڵ بکە:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_numpad("user_info", ""),
        )
        return

    # ── نامە بنێرە ────────────────────────────────────────────────────────────
    if data == "admin_msg_user_ask":
        context.user_data["np_action"] = "msg_user_ask_id"
        context.user_data["np_input"]  = ""
        await query.edit_message_text(
            "✉️ <b>نامە بنێرە بۆ بەکارهێنەر</b>\n\n📟 ئایدی داخڵ بکە:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_numpad("msg_user_ask_id", ""),
        )
        return

    # ── بەڕێوەبردنی چەناڵ ────────────────────────────────────────────────────
    if data == "admin_channels":
        ch_list = (
            "\n".join([f"  • <code>{ch}</code>" for ch in forced_channels])
            or "  📭 هیچ چەناڵێک نییە."
        )
        kb = [
            [
                InlineKeyboardButton("➕ زیادکردن", callback_data="ch_add"),
                InlineKeyboardButton("➖ لابردن",   callback_data="ch_rm_list"),
            ],
            *back_btn(lang, "admin_main"),
        ]
        await query.edit_message_text(
            f"📢 <b>بەڕێوەبردنی چەناڵەکان</b>\n\n{ch_list}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    if data == "ch_add":
        context.user_data["np_ch_buf"] = "@"
        await query.edit_message_text(
            "📢 <b>زیادکردنی چەناڵ</b>\n\n✍️ ناوی چەناڵەکە داخڵ بکە:\n📟 <code>@</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=build_ch_input("@"),
        )
        return

    if data == "ch_rm_list":
        if not forced_channels:
            await query.answer("📭 هیچ چەناڵێک نییە!", show_alert=True)
            return
        kb  = [[InlineKeyboardButton(f"❌ {ch}", callback_data=f"ch_del_{ch}")] for ch in forced_channels]
        kb += back_btn(lang, "admin_channels")
        await query.edit_message_text(
            "📢 <b>چەناڵێک هەڵبژێرە بۆ لابردن:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    if data.startswith("ch_del_"):
        ch = data[7:]
        if ch in forced_channels:
            forced_channels.remove(ch)
        await save_settings()
        await query.edit_message_text(
            t(lang, "channel_removed", ch=ch),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang, "admin_channels")),
        )
        return

    # ── بەڕێوەبردنی بلۆک ─────────────────────────────────────────────────────
    if data == "admin_blocks":
        blk = (
            "\n".join([f"  • <code>{x}</code>" for x in blocked_users])
            or "  📭 بلۆک نییە."
        )
        kb = [
            [
                InlineKeyboardButton("🚫 بلۆک کردن",   callback_data="blk_add"),
                InlineKeyboardButton("✅ ئەنبلۆک کردن", callback_data="blk_rm"),
            ],
            *back_btn(lang, "admin_main"),
        ]
        await query.edit_message_text(
            f"🚫 <b>بلۆک کراوەکان</b>\n\n{blk}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    if data == "blk_add":
        context.user_data["np_action"] = "blk_add"
        context.user_data["np_input"]  = ""
        await query.edit_message_text(
            "🚫 <b>بلۆک کردنی بەکارهێنەر</b>\n\n📟 ئایدی داخڵ بکە:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_numpad("blk_add", ""),
        )
        return

    if data == "blk_rm":
        context.user_data["np_action"] = "blk_rm"
        context.user_data["np_input"]  = ""
        await query.edit_message_text(
            "✅ <b>ئەنبلۆک کردنی بەکارهێنەر</b>\n\n📟 ئایدی داخڵ بکە:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_numpad("blk_rm", ""),
        )
        return

    # ── بەڕێوەبردنی VIP ──────────────────────────────────────────────────────
    if data == "admin_vips":
        vip_l = (
            "\n".join([f"  • <code>{x}</code>" for x in vip_users])
            or "  📭 VIP نییە."
        )
        kb = [
            [
                InlineKeyboardButton("➕ زیادکردن", callback_data="vip_add"),
                InlineKeyboardButton("➖ لابردن",   callback_data="vip_rm"),
            ],
            *back_btn(lang, "admin_main"),
        ]
        await query.edit_message_text(
            f"💎 <b>VIP بەکارهێنەرەکان</b>\n\n{vip_l}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    if data == "vip_add":
        context.user_data["np_action"] = "vip_add"
        context.user_data["np_input"]  = ""
        await query.edit_message_text(
            "💎 <b>زیادکردنی VIP</b>\n\n📟 ئایدی داخڵ بکە:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_numpad("vip_add", ""),
        )
        return

    if data == "vip_rm":
        context.user_data["np_action"] = "vip_rm"
        context.user_data["np_input"]  = ""
        await query.edit_message_text(
            "➖ <b>لابردنی VIP</b>\n\n📟 ئایدی داخڵ بکە:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_numpad("vip_rm", ""),
        )
        return

    # ==========================================================================
    # ─── OWNER PANEL ──────────────────────────────────────────────────────────
    # ==========================================================================
    if not is_owner(uid):
        await query.answer(t(lang, "error_owner_only"), show_alert=True)
        return

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
                InlineKeyboardButton("🌐 زمانی پێشواز",          callback_data="owner_bot_lang"),
                InlineKeyboardButton("📈 ریپۆرتی ڕۆژانە",        callback_data="owner_daily_report"),
            ],
            *back_btn(lang, "cmd_start"),
        ]
        await query.edit_message_text(
            f"🔱 <b>پانێڵی خاوەنی بۆت</b>\n\n"
            f"👑 خاوەن: <code>{OWNER_ID}</code>\n"
            f"🤖 ڤێرژن: v{bot_settings_global.get('bot_version','7.0')}\n"
            f"⏱ Uptime: {get_uptime()}\n"
            f"🕐 {get_current_time()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    # ── بەڕێوەبردنی ئەدمین ───────────────────────────────────────────────────
    if data == "owner_admins":
        adm = (
            "\n".join([f"  • <code>{x}</code>" for x in admins_list if x != OWNER_ID])
            or "  📭 هیچ ئەدمینێک نییە."
        )
        kb = [
            [
                InlineKeyboardButton("➕ زیادکردنی ئەدمین", callback_data="adm_add"),
                InlineKeyboardButton("➖ لابردنی ئەدمین",   callback_data="adm_rm"),
            ],
            *back_btn(lang, "owner_main"),
        ]
        await query.edit_message_text(
            f"👥 <b>بەڕێوەبردنی ئەدمینەکان</b>\n\n{adm}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    if data == "adm_add":
        context.user_data["np_action"] = "adm_add"
        context.user_data["np_input"]  = ""
        await query.edit_message_text(
            "➕ <b>زیادکردنی ئەدمین</b>\n\n📟 ئایدی داخڵ بکە:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_numpad("adm_add", ""),
        )
        return

    if data == "adm_rm":
        context.user_data["np_action"] = "adm_rm"
        context.user_data["np_input"]  = ""
        await query.edit_message_text(
            "➖ <b>لابردنی ئەدمین</b>\n\n📟 ئایدی داخڵ بکە:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_numpad("adm_rm", ""),
        )
        return

    # ── ئاماری پێشکەوتوو ─────────────────────────────────────────────────────
    if data == "owner_stats_adv":
        all_ids  = await get_all_user_ids()
        all_data = await get_all_users_data()
        total_dls = sum(v.get("downloads", 0) for v in all_data.values())
        text = (
            f"╔{'═'*23}╗\n"
            f"  📊 <b>ئاماری پێشکەوتوو</b>\n"
            f"╚{'═'*23}╝\n\n"
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
            f"├ چاکسازی: {'🔴' if bot_settings_global['maintenance_mode'] else '🟢'}\n"
            f"├ Photo Mode: {bot_settings_global.get('photo_mode','auto')}\n"
            f"├ Max Photos: {bot_settings_global.get('max_photos',10)}\n"
            f"├ VIP Bypass: {'✅' if bot_settings_global.get('vip_bypass_join') else '❌'}\n"
            f"└ Admin Bypass: {'✅' if bot_settings_global.get('admin_bypass_join') else '❌'}\n\n"
            f"🕐 {get_current_time()}"
        )
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang, "btn_refresh"), callback_data="owner_stats_adv")],
                *back_btn(lang, "owner_main"),
            ]),
        )
        return

    # ── ڕێکخستنی بۆت ─────────────────────────────────────────────────────────
    if data == "owner_bot_settings":
        maint    = bot_settings_global.get("maintenance_mode", False)
        ph_mode  = bot_settings_global.get("photo_mode", "auto")
        vip_byp  = bot_settings_global.get("vip_bypass_join", True)
        adm_byp  = bot_settings_global.get("admin_bypass_join", True)
        max_ph   = bot_settings_global.get("max_photos", 10)
        api_to   = bot_settings_global.get("api_timeout", 60)
        af       = bot_settings_global.get("anti_flood", True)
        kb = [
            [InlineKeyboardButton(
                f"🛠 چاکسازی: {'🔴 ON' if maint else '🟢 OFF'}",
                callback_data="owner_toggle_maint",
            )],
            [InlineKeyboardButton(
                f"📸 Photo Mode: {ph_mode}",
                callback_data="owner_toggle_photo_mode",
            )],
            [InlineKeyboardButton(
                f"💎 VIP Bypass: {'✅' if vip_byp else '❌'}",
                callback_data="owner_toggle_vip_bypass",
            )],
            [InlineKeyboardButton(
                f"👑 Admin Bypass: {'✅' if adm_byp else '❌'}",
                callback_data="owner_toggle_admin_bypass",
            )],
            [InlineKeyboardButton(
                f"⚡ Anti-Flood: {'✅' if af else '❌'}",
                callback_data="owner_toggle_anti_flood",
            )],
            [InlineKeyboardButton(
                f"📸 Max Photos: {max_ph}",
                callback_data="owner_set_max_photos",
            )],
            [InlineKeyboardButton(
                f"⏱ API Timeout: {api_to}s",
                callback_data="owner_set_api_timeout",
            )],
            *back_btn(lang, "owner_main"),
        ]
        await query.edit_message_text(
            "⚙️ <b>ڕێکخستنی بۆت</b>\n\nدوگمەیەک هەڵبژێرە بۆ گۆڕانی:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    # toggle ەکان
    if data == "owner_toggle_maint":
        bot_settings_global["maintenance_mode"] = not bot_settings_global["maintenance_mode"]
        await save_settings()
        await query.answer(
            f"چاکسازی: {'🔴 ON' if bot_settings_global['maintenance_mode'] else '🟢 OFF'}",
            show_alert=True,
        )
        # نوێکردنەوەی پانێڵ
        query.data = "owner_bot_settings"
        await button_handler(update, context)
        return

    if data == "owner_toggle_photo_mode":
        modes = ["auto", "force_photos", "force_video"]
        cur   = bot_settings_global.get("photo_mode", "auto")
        nxt   = modes[(modes.index(cur) + 1) % len(modes)]
        bot_settings_global["photo_mode"] = nxt
        await save_settings()
        await query.answer(f"Photo Mode → {nxt}", show_alert=True)
        query.data = "owner_bot_settings"
        await button_handler(update, context)
        return

    if data == "owner_toggle_vip_bypass":
        bot_settings_global["vip_bypass_join"] = not bot_settings_global.get("vip_bypass_join", True)
        await save_settings()
        await query.answer(
            f"VIP Bypass → {'ON' if bot_settings_global['vip_bypass_join'] else 'OFF'}",
            show_alert=True,
        )
        query.data = "owner_bot_settings"
        await button_handler(update, context)
        return

    if data == "owner_toggle_admin_bypass":
        bot_settings_global["admin_bypass_join"] = not bot_settings_global.get("admin_bypass_join", True)
        await save_settings()
        await query.answer(
            f"Admin Bypass → {'ON' if bot_settings_global['admin_bypass_join'] else 'OFF'}",
            show_alert=True,
        )
        query.data = "owner_bot_settings"
        await button_handler(update, context)
        return

    if data == "owner_toggle_anti_flood":
        bot_settings_global["anti_flood"] = not bot_settings_global.get("anti_flood", True)
        await save_settings()
        await query.answer(
            f"Anti-Flood → {'ON' if bot_settings_global['anti_flood'] else 'OFF'}",
            show_alert=True,
        )
        query.data = "owner_bot_settings"
        await button_handler(update, context)
        return

    if data == "owner_set_max_photos":
        context.user_data["np_action"] = "set_max_photos"
        context.user_data["np_input"]  = ""
        await query.edit_message_text(
            f"📸 <b>Max Photos</b>\n\nئێستا: <b>{bot_settings_global.get('max_photos',10)}</b>\n\n📟 ژمارەی نوێ داخڵ بکە (1-30):",
            parse_mode=ParseMode.HTML,
            reply_markup=build_numpad("set_max_photos", ""),
        )
        return

    if data == "owner_set_api_timeout":
        context.user_data["np_action"] = "set_api_timeout"
        context.user_data["np_input"]  = ""
        await query.edit_message_text(
            f"⏱ <b>API Timeout</b>\n\nئێستا: <b>{bot_settings_global.get('api_timeout',60)}s</b>\n\n📟 چرکەی نوێ داخڵ بکە:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_numpad("set_api_timeout", ""),
        )
        return

    # ── نامەی خۆشامەدێ ───────────────────────────────────────────────────────
    if data == "owner_welcome_msg":
        admin_waiting_state[uid] = "set_welcome_msg"
        cur = bot_settings_global.get("welcome_msg", "") or "<i>(بەکارنەهاتوو)</i>"
        await query.edit_message_text(
            f"📝 <b>نامەی خۆشامەدێ</b>\n\n<b>ئێستا:</b>\n{cur}\n\n✍️ نامەی نوێت بنووسە و بنێرە:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🗑 سڕینەوەی نامەکە", callback_data="owner_clear_welcome"),
                InlineKeyboardButton("❌ هەڵوەشاندنەوە",   callback_data="owner_main"),
            ]]),
        )
        return

    if data == "owner_clear_welcome":
        bot_settings_global["welcome_msg"] = ""
        await save_settings()
        await query.edit_message_text(
            "✅ نامەی خۆشامەدێ سڕایەوە.",
            reply_markup=InlineKeyboardMarkup(back_btn(lang, "owner_main")),
        )
        return

    # ── بەکئەپ ───────────────────────────────────────────────────────────────
    if data == "owner_backup":
        await query.answer("⏳ بەکئەپ ئامادە دەکرێت...", show_alert=False)
        all_users = await get_all_users_data()
        backup_data = {
            "timestamp"  : get_current_time(),
            "bot_version": bot_settings_global.get("bot_version", "7.0"),
            "settings"   : bot_settings_global,
            "admins"     : list(admins_list),
            "channels"   : forced_channels,
            "blocked"    : list(blocked_users),
            "vips"       : list(vip_users),
            "total_users": len(all_users),
        }
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
        bio      = io.BytesIO(backup_json.encode())
        bio.name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            await context.bot.send_document(
                chat_id   = uid,
                document  = bio,
                caption   = t(lang, "backup_caption", time=get_current_time()),
                parse_mode= ParseMode.HTML,
            )
        except Exception as e:
            await query.message.reply_text(f"❌ هەڵە: {e}")
        return

    # ── لیستی بەکارهێنەرەکان ─────────────────────────────────────────────────
    if data == "owner_list_users":
        all_data = await get_all_users_data()
        if not all_data:
            await query.answer(t(lang, "no_users_found"), show_alert=True)
            return
        lines = []
        for uid2, info in list(all_data.items())[:50]:
            vip_m  = "💎" if info.get("is_vip") else ""
            blk_m  = "🚫" if int(uid2) in blocked_users else ""
            name_m = html.escape(str(info.get("name", "?"))[:20])
            lines.append(f"{vip_m}{blk_m} <code>{uid2}</code> — {name_m}")
        total = len(all_data)
        text  = f"👥 <b>لیستی بەکارهێنەرەکان ({total})</b>\n\n" + "\n".join(lines)
        if total > 50:
            text += f"\n\n<i>... و {total-50} کەسی تر</i>"
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang, "owner_main")),
        )
        return

    # ── ڕیسێتی ئامارەکان ─────────────────────────────────────────────────────
    if data == "owner_reset_stats_ask":
        kb = [[
            InlineKeyboardButton(t(lang, "btn_confirm"), callback_data="owner_reset_stats_do"),
            InlineKeyboardButton(t(lang, "btn_cancel"),  callback_data="owner_main"),
        ]]
        await query.edit_message_text(
            t(lang, "confirm_reset_stats"),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    if data == "owner_reset_stats_do":
        for k in ("total_downloads", "total_videos", "total_audios", "total_photos"):
            bot_settings_global[k] = 0
        await save_settings()
        await query.edit_message_text(
            t(lang, "stats_reset_done"),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang, "owner_main")),
        )
        return

    # ── سڕینەوەی بەکارهێنەرەکان ──────────────────────────────────────────────
    if data == "owner_reset_users_ask":
        kb = [[
            InlineKeyboardButton(t(lang, "btn_confirm"), callback_data="owner_reset_users_do"),
            InlineKeyboardButton(t(lang, "btn_cancel"),  callback_data="owner_main"),
        ]]
        await query.edit_message_text(
            t(lang, "confirm_reset_users"),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    if data == "owner_reset_users_do":
        await delete_all_users()
        await query.edit_message_text(
            t(lang, "users_reset_done"),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang, "owner_main")),
        )
        return

    # ── بڕۆدکاستی پێشکەوتوو ──────────────────────────────────────────────────
    if data == "owner_adv_broadcast":
        kb = [
            [
                InlineKeyboardButton("📢 بۆ هەمووان",     callback_data="bc_type_all"),
                InlineKeyboardButton("💎 تەنیا VIP",      callback_data="bc_type_vip"),
            ],
            [
                InlineKeyboardButton("🆓 تەنیا Free",     callback_data="bc_type_free"),
                InlineKeyboardButton("✅ ئەنبلۆک کراوان", callback_data="bc_type_noblock"),
            ],
            *back_btn(lang, "owner_main"),
        ]
        await query.edit_message_text(
            "📣 <b>بڕۆدکاستی پێشکەوتوو</b>\n\nکێ دەوێیت نامەکەت پێبگات؟",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    # ── تاقیکردنەوەی API ─────────────────────────────────────────────────────
    if data == "owner_test_api":
        test_url = "https://www.tiktok.com/@tiktok/video/6584647400055385349"
        await query.answer("⏳ API تاقی دەکرێتەوە...", show_alert=False)
        result = await fetch_tiktok_data(test_url, max_retries=1)
        if result:
            src  = result.get("source", "?")
            text = f"✅ <b>API کار دەکات!</b>\n\nSource: <code>{src}</code>\n🕐 {get_current_time()}"
        else:
            text = f"❌ <b>API کار ناکات!</b>\n\n🕐 {get_current_time()}"
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(back_btn(lang, "owner_main")),
        )
        return

    # ── زمانی پێشواز ─────────────────────────────────────────────────────────
    if data == "owner_bot_lang":
        kb = [
            [InlineKeyboardButton("🔴🔆🟢 کوردی (پێشواز)",  callback_data="owner_set_deflang_ku")],
            [InlineKeyboardButton("🇺🇸 English (Default)",   callback_data="owner_set_deflang_en")],
            [InlineKeyboardButton("🇸🇦 Arabic (Default)",    callback_data="owner_set_deflang_ar")],
            *back_btn(lang, "owner_main"),
        ]
        await query.edit_message_text(
            "🌐 <b>زمانی پێشواز بۆ بەکارهێنەرانی نوێ هەڵبژێرە:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    for dl_code in ("ku", "en", "ar"):
        if data == f"owner_set_deflang_{dl_code}":
            bot_settings_global["default_lang"] = dl_code
            await save_settings()
            await query.answer(f"✅ زمانی پێشواز → {dl_code.upper()}", show_alert=True)
            query.data = "owner_main"
            await button_handler(update, context)
            return

    # ── ریپۆرتی ڕۆژانە ──────────────────────────────────────────────────────
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
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang, "btn_refresh"), callback_data="owner_daily_report")],
                *back_btn(lang, "owner_main"),
            ]),
        )
        return


# ==============================================================================
# ─── DOWNLOAD ACTION HANDLER ──────────────────────────────────────────────────
# ==============================================================================

async def handle_download_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
    uid: int,
    lang: str,
):
    """
    ✅ FIX: هەموو کێشەکانی داونلۆدکردن چارەسەرکراون:
    - ✅ وێنەکان بە شێوازی media_group دەنێردرێن یان تاکەیەک تاکەیەک
    - ✅ ئەگەر media_group سەرکەوتوو نەبوو، وێنەکان تاکەیەک تاکەیەک دەنێردرێن
    - ✅ ئەگەر video url هەبوو و هیچ وێنەیەک نەبوو، video button دیاری دەکرێت
    - ✅ کاونتەری داونلۆد بەدرستی نوێدەکرێتەوە
    - ✅ پیامی فڵبەک بۆ کاتی هەڵە
    """
    query  = update.callback_query
    action = data.split("_")[1]   # photos | video | audio

    sess = await get_user_session(uid)
    if not sess:
        await query.answer(t(lang, "error_session_expired"), show_alert=True)
        return

    creator = sess.get("creator", "Unknown")
    details = sess.get("details", {})
    images  = sess.get("images", [])
    title   = clean_title(details.get("title", ""))

    caption = (
        f"🎬 <b>{html.escape(title)}</b>\n"
        f"👤 <b>{html.escape(creator)}</b>\n\n"
        f"🤖 @{context.bot.username}"
    )

    del_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "btn_delete"), callback_data="close")
    ]])

    # ─── وێنەکان ──────────────────────────────────────────────────────────────
    if action == "photos":
        if not images:
            await query.answer(t(lang, "no_photos_url"), show_alert=True)
            return

        bot_settings_global["total_downloads"] = bot_settings_global.get("total_downloads", 0) + 1
        bot_settings_global["total_photos"]    = bot_settings_global.get("total_photos", 0) + 1
        asyncio.create_task(save_settings())

        # نوێکردنەوەی ژمارەی داونلۆدی بەکارهێنەر
        udata = await get_user_data(uid)
        cur_dl = udata.get("downloads", 0) if udata else 0
        asyncio.create_task(update_user_field(uid, "downloads", cur_dl + 1))

        max_p  = int(bot_settings_global.get("max_photos", 10))
        photos = images[:max_p]
        total  = len(photos)

        # ✅ سڕینەوەی نامەی کۆن
        try:
            await query.message.delete()
        except Exception:
            pass

        # ناردنی وێنەکان بە chunk ی 10 تا
        chunks      = [photos[i:i+10] for i in range(0, total, 10)]
        sent_count  = 0

        for chunk_idx, chunk in enumerate(chunks):
            # ناردن بە شێوازی گروپ
            media_group = []
            for idx, img_url in enumerate(chunk):
                mitem = InputMediaPhoto(media=img_url)
                if idx == 0 and chunk_idx == 0:
                    mitem.caption    = caption
                    mitem.parse_mode = ParseMode.HTML
                media_group.append(mitem)

            try:
                await context.bot.send_media_group(chat_id=uid, media=media_group)
                sent_count += len(chunk)
            except Exception as e:
                logger.warning(f"send_media_group هەڵە: {e}, تاکەیەک تاکەیەک هەوڵدەدرێتەوە...")
                # ✅ FIX: ئەگەر گروپ کار نەکرد، تاکەیەک تاکەیەک بنێرە
                for idx2, img_url in enumerate(chunk):
                    cap = (caption if (idx2 == 0 and chunk_idx == 0) else None)
                    try:
                        await context.bot.send_photo(
                            chat_id    = uid,
                            photo      = img_url,
                            caption    = cap,
                            parse_mode = ParseMode.HTML if cap else None,
                        )
                        sent_count += 1
                        await asyncio.sleep(0.3)
                    except Exception as e2:
                        logger.warning(f"تاکە وێنەی {idx2} نەنێردرا: {e2}")

            await asyncio.sleep(0.5)

        # ئەگەر هیچ وێنەیەک نەنێردرا، لینک بنێرە
        if sent_count == 0:
            links = "\n".join([
                f"🖼 <a href='{img}'>وێنەی {i+1}</a>"
                for i, img in enumerate(photos[:10])
            ])
            await context.bot.send_message(
                chat_id    = uid,
                text       = f"{t(lang, 'photo_fallback')}\n\n{links}",
                parse_mode = ParseMode.HTML,
                reply_markup = del_kb,
            )
        return

    # ─── ڤیدیۆ ────────────────────────────────────────────────────────────────
    if action == "video":
        video_url = (
            details.get("video", {}).get("play", "") or
            details.get("video", {}).get("download_addr", "") or
            details.get("video", {}).get("wmplay", "")
        )
        if not video_url:
            await query.answer(t(lang, "no_video_url"), show_alert=True)
            return

        bot_settings_global["total_downloads"] = bot_settings_global.get("total_downloads", 0) + 1
        bot_settings_global["total_videos"]    = bot_settings_global.get("total_videos", 0) + 1
        asyncio.create_task(save_settings())

        udata  = await get_user_data(uid)
        cur_dl = udata.get("downloads", 0) if udata else 0
        asyncio.create_task(update_user_field(uid, "downloads", cur_dl + 1))

        try:
            await query.message.edit_media(
                InputMediaVideo(
                    media      = video_url,
                    caption    = caption,
                    parse_mode = ParseMode.HTML,
                ),
                reply_markup = del_kb,
            )
        except Exception as e:
            logger.warning(f"edit_media video هەڵە: {e}")
            # ✅ FIX: ناردنی لینک بۆ کاتی هەڵە
            try:
                await query.message.edit_caption(
                    f"{t(lang, 'video_fallback')}\n<a href='{video_url}'>📥 دابەزاندنی ڤیدیۆ</a>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = del_kb,
                )
            except Exception:
                await context.bot.send_message(
                    chat_id      = uid,
                    text         = f"{t(lang, 'video_fallback')}\n<a href='{video_url}'>📥 دابەزاندنی ڤیدیۆ</a>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = del_kb,
                )
        return

    # ─── گۆرانی ───────────────────────────────────────────────────────────────
    if action == "audio":
        audio_url = (
            details.get("audio", {}).get("play", "") or
            details.get("audio", {}).get("music", "") or
            details.get("music", {}).get("playUrl", "")
        )
        if not audio_url:
            await query.answer(t(lang, "no_audio_url"), show_alert=True)
            return

        bot_settings_global["total_downloads"] = bot_settings_global.get("total_downloads", 0) + 1
        bot_settings_global["total_audios"]    = bot_settings_global.get("total_audios", 0) + 1
        asyncio.create_task(save_settings())

        udata  = await get_user_data(uid)
        cur_dl = udata.get("downloads", 0) if udata else 0
        asyncio.create_task(update_user_field(uid, "downloads", cur_dl + 1))

        music_title = f"{clean_title(title)}"
        try:
            await query.message.edit_media(
                InputMediaAudio(
                    media     = audio_url,
                    caption   = caption,
                    parse_mode= ParseMode.HTML,
                    title     = music_title,
                    performer = creator,
                ),
                reply_markup = del_kb,
            )
        except Exception as e:
            logger.warning(f"edit_media audio هەڵە: {e}")
            try:
                await query.message.edit_caption(
                    f"{t(lang, 'audio_fallback')}\n<a href='{audio_url}'>🎵 دابەزاندنی گۆرانی</a>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = del_kb,
                )
            except Exception:
                await context.bot.send_message(
                    chat_id      = uid,
                    text         = f"{t(lang, 'audio_fallback')}\n<a href='{audio_url}'>🎵 دابەزاندنی گۆرانی</a>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = del_kb,
                )
        return


# ==============================================================================
# ─── NUMPAD HANDLER ───────────────────────────────────────────────────────────
# ==============================================================================

async def numpad_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هەموو کلیکەکانی np_* و chi_* بەڕێوە دەبات"""
    query = update.callback_query
    data  = query.data
    uid   = query.from_user.id
    lang  = await get_user_lang(uid)
    await query.answer()

    # هەڵوەشاندنەوە
    if data == "np_cancel":
        context.user_data.pop("np_action", None)
        context.user_data.pop("np_input",  None)
        context.user_data.pop("np_ch_buf", None)
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    # ── Numpad ────────────────────────────────────────────────────────────────
    if data.startswith("np_"):
        parts = data.split("_", 2)
        if len(parts) < 3:
            return
        action  = parts[1]
        key     = parts[2]
        current = context.user_data.get("np_input", "")

        if key == "back":
            current = current[:-1]
        elif key == "ok":
            # پشتگیری
            if not current.isdigit():
                await query.answer("❌ ئایدی دروست نییە!", show_alert=True)
                return
            target_id = int(current)
            context.user_data.pop("np_input",  None)
            context.user_data.pop("np_action", None)

            if action == "blk_add":
                blocked_users.add(target_id)
                await save_settings()
                await query.edit_message_text(
                    f"✅ بلۆک کرا: <code>{target_id}</code>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup(back_btn(lang, "admin_blocks")),
                )

            elif action == "blk_rm":
                blocked_users.discard(target_id)
                await save_settings()
                await query.edit_message_text(
                    f"✅ ئەنبلۆک کرا: <code>{target_id}</code>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup(back_btn(lang, "admin_blocks")),
                )

            elif action == "vip_add":
                vip_users.add(target_id)
                await save_settings()
                asyncio.create_task(update_user_field(target_id, "is_vip", True))
                await query.edit_message_text(
                    f"✅ VIP زیادکرا: <code>{target_id}</code>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup(back_btn(lang, "admin_vips")),
                )

            elif action == "vip_rm":
                vip_users.discard(target_id)
                await save_settings()
                asyncio.create_task(update_user_field(target_id, "is_vip", False))
                await query.edit_message_text(
                    f"✅ VIP لابرا: <code>{target_id}</code>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup(back_btn(lang, "admin_vips")),
                )

            elif action == "adm_add":
                if not is_owner(uid):
                    await query.answer(t(lang, "not_owner"), show_alert=True)
                    return
                admins_list.add(target_id)
                await save_settings()
                await query.edit_message_text(
                    f"✅ ئەدمین زیادکرا: <code>{target_id}</code>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup(back_btn(lang, "owner_admins")),
                )

            elif action == "adm_rm":
                if not is_owner(uid):
                    await query.answer(t(lang, "not_owner"), show_alert=True)
                    return
                if target_id == OWNER_ID:
                    await query.answer("⛔ ناتوانیت خاوەنەکە لابەری!", show_alert=True)
                    return
                admins_list.discard(target_id)
                await save_settings()
                await query.edit_message_text(
                    f"✅ ئەدمین لابرا: <code>{target_id}</code>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup(back_btn(lang, "owner_admins")),
                )

            elif action == "user_info":
                udata = await get_user_data(target_id)
                if not udata:
                    await query.edit_message_text(
                        t(lang, "user_not_found"),
                        reply_markup = InlineKeyboardMarkup(back_btn(lang, "admin_main")),
                    )
                    return
                vip_s = "✅" if target_id in vip_users or udata.get("is_vip") else "❌"
                blk_s = "✅" if target_id in blocked_users else "❌"
                await query.edit_message_text(
                    t(lang, "user_info_text",
                      id       = target_id,
                      name     = html.escape(str(udata.get("name", "?"))),
                      username = udata.get("username", "—"),
                      date     = udata.get("joined_date", "—"),
                      vip      = vip_s,
                      blocked  = blk_s,
                    ),
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "🟢 ئەنبلۆک" if target_id in blocked_users else "🚫 بلۆک",
                                callback_data=f"quick_blk_{target_id}",
                            ),
                            InlineKeyboardButton(
                                "❌ VIP لابردن" if target_id in vip_users else "💎 VIP زیادکردن",
                                callback_data=f"quick_vip_{target_id}",
                            ),
                        ],
                        [InlineKeyboardButton("✉️ نامە بنێرە", callback_data=f"quick_msg_{target_id}")],
                        *back_btn(lang, "admin_main"),
                    ]),
                )

            elif action == "msg_user_ask_id":
                admin_waiting_state[uid] = f"msg_user_send_{target_id}"
                await query.edit_message_text(
                    t(lang, "send_msg_to_user", id=target_id),
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup([[
                        InlineKeyboardButton("❌ هەڵوەشاندنەوە", callback_data="np_cancel")
                    ]]),
                )

            elif action == "set_max_photos":
                val = min(max(int(current), 1), 30)
                bot_settings_global["max_photos"] = val
                await save_settings()
                await query.edit_message_text(
                    f"✅ Max Photos نوێکرایەوە: <b>{val}</b>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup(back_btn(lang, "owner_bot_settings")),
                )

            elif action == "set_api_timeout":
                val = max(int(current), 10)
                bot_settings_global["api_timeout"] = val
                await save_settings()
                await query.edit_message_text(
                    f"✅ API Timeout نوێکرایەوە: <b>{val}s</b>",
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup(back_btn(lang, "owner_bot_settings")),
                )
            return

        else:
            if len(current) < 15:
                current += key

        context.user_data["np_input"] = current

        titles_np = {
            "blk_add"         : "🚫 بلۆک کردن",
            "blk_rm"          : "✅ ئەنبلۆک کردن",
            "vip_add"         : "💎 VIP زیادکردن",
            "vip_rm"          : "➖ VIP لابردن",
            "adm_add"         : "➕ ئەدمین زیادکردن",
            "adm_rm"          : "➖ ئەدمین لابردن",
            "user_info"       : "👤 زانیاری بەکارهێنەر",
            "msg_user_ask_id" : "✉️ نامە بنێرە",
            "set_max_photos"  : "📸 Max Photos",
            "set_api_timeout" : "⏱ API Timeout",
        }
        title_text = titles_np.get(action, "📟 ئایدی داخڵ بکە")
        display    = f"<code>{current}</code>" if current else "<i>(بەتاڵ)</i>"
        try:
            await query.edit_message_text(
                f"{title_text}\n\n📟 ئایدی: {display}",
                parse_mode   = ParseMode.HTML,
                reply_markup = build_numpad(action, current),
            )
        except Exception:
            pass
        return

    # ── Channel Input ────────────────────────────────────────────────────────
    if data.startswith("chi_"):
        key = data[4:]
        buf = context.user_data.get("np_ch_buf", "@")

        if key == "back":
            if len(buf) > 1:
                buf = buf[:-1]
        elif key == "ok":
            ch = buf if buf.startswith("@") else f"@{buf}"
            if len(ch) < 3:
                await query.answer("❌ ناوی چەناڵ کورتە!", show_alert=True)
                return
            context.user_data.pop("np_ch_buf", None)
            if ch not in forced_channels:
                forced_channels.append(ch)
                await save_settings()
            await query.edit_message_text(
                t(lang, "channel_added", ch=ch),
                parse_mode   = ParseMode.HTML,
                reply_markup = InlineKeyboardMarkup(back_btn(lang, "admin_channels")),
            )
            return
        else:
            if len(buf) < 33:
                buf += key

        context.user_data["np_ch_buf"] = buf
        display = f"<code>{buf}</code>" if buf else "<i>(بەتاڵ)</i>"
        try:
            await query.edit_message_text(
                f"📢 <b>زیادکردنی چەناڵ</b>\n\n📟 ناو: {display}",
                parse_mode   = ParseMode.HTML,
                reply_markup = build_ch_input(buf),
            )
        except Exception:
            pass
        return


# ==============================================================================
# ─── QUICK ACTION HANDLER ─────────────────────────────────────────────────────
# ==============================================================================

async def quick_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    uid   = query.from_user.id
    lang  = await get_user_lang(uid)

    if not is_admin(uid):
        await query.answer(t(lang, "error_admin_only"), show_alert=True)
        return

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
            asyncio.create_task(update_user_field(tid, "is_vip", False))
            await query.answer(f"✅ VIP لابرا: {tid}", show_alert=True)
        else:
            vip_users.add(tid)
            asyncio.create_task(update_user_field(tid, "is_vip", True))
            await query.answer(f"✅ VIP زیادکرا: {tid}", show_alert=True)
        await save_settings()

    elif data.startswith("quick_msg_"):
        tid = int(data.split("_")[2])
        admin_waiting_state[uid] = f"msg_user_send_{tid}"
        await query.message.reply_text(
            t(lang, "send_msg_to_user", id=tid),
            parse_mode   = ParseMode.HTML,
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ هەڵوەشاندنەوە", callback_data="np_cancel")
            ]]),
        )


# ==============================================================================
# ─── MESSAGE HANDLER ──────────────────────────────────────────────────────────
# ==============================================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بەڕێوەبردنی هەموو نامەکانی تێکست"""
    if not update.message:
        return

    uid  = update.effective_user.id
    lang = await get_user_lang(uid)
    msg  = update.message

    # ── وەڵامی ئەدمین / خاوەن ────────────────────────────────────────────────
    if is_admin(uid) and uid in admin_waiting_state:
        state = admin_waiting_state.pop(uid)
        text  = (msg.text or "").strip()

        # برۆدکاست
        if state.startswith("broadcast"):
            bc_type  = state.split("_")[1] if "_" in state else "all"
            all_uids = await get_all_user_ids()
            all_udata = await get_all_users_data()

            target_ids = []
            for uid2 in all_uids:
                if bc_type == "all":
                    target_ids.append(uid2)
                elif bc_type == "vip" and uid2 in vip_users:
                    target_ids.append(uid2)
                elif bc_type == "free" and uid2 not in vip_users:
                    target_ids.append(uid2)
                elif bc_type == "noblock" and uid2 not in blocked_users:
                    target_ids.append(uid2)

            success, fail = 0, 0
            status_msg = await msg.reply_text(
                f"⏳ برۆدکاست دەستپێدەکات بۆ <b>{len(target_ids)}</b> کەس...",
                parse_mode=ParseMode.HTML,
            )
            for i, tuid in enumerate(target_ids):
                try:
                    await context.bot.copy_message(
                        chat_id      = tuid,
                        from_chat_id = msg.chat_id,
                        message_id   = msg.message_id,
                    )
                    success += 1
                    await asyncio.sleep(0.05)
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after + 1)
                    try:
                        await context.bot.copy_message(
                            chat_id      = tuid,
                            from_chat_id = msg.chat_id,
                            message_id   = msg.message_id,
                        )
                        success += 1
                    except Exception:
                        fail += 1
                except (Forbidden, BadRequest):
                    fail += 1
                except Exception:
                    fail += 1
                    await asyncio.sleep(1)

                if i % 50 == 0 and i > 0:
                    try:
                        await status_msg.edit_text(
                            f"⏳ {i}/{len(target_ids)}...", parse_mode=ParseMode.HTML
                        )
                    except Exception:
                        pass

            try:
                await status_msg.edit_text(
                    t(lang, "broadcast_sent", success=success, fail=fail),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
            return

        # زیادکردنی چەناڵ
        if state == "ch_add":
            ch = text if text.startswith("@") else f"@{text}"
            if ch not in forced_channels:
                forced_channels.append(ch)
                await save_settings()
            await msg.reply_text(t(lang, "channel_added", ch=ch), parse_mode=ParseMode.HTML)
            return

        if state == "blk_add":
            if not text.isdigit():
                await msg.reply_text(t(lang, "invalid_id"))
                return
            blocked_users.add(int(text))
            await save_settings()
            await msg.reply_text(t(lang, "user_blocked", id=text), parse_mode=ParseMode.HTML)
            return

        if state == "blk_rm":
            if not text.isdigit():
                await msg.reply_text(t(lang, "invalid_id"))
                return
            blocked_users.discard(int(text))
            await save_settings()
            await msg.reply_text(t(lang, "user_unblocked", id=text), parse_mode=ParseMode.HTML)
            return

        if state == "vip_add":
            if not text.isdigit():
                await msg.reply_text(t(lang, "invalid_id"))
                return
            tid = int(text)
            vip_users.add(tid)
            await save_settings()
            asyncio.create_task(update_user_field(tid, "is_vip", True))
            await msg.reply_text(t(lang, "vip_added", id=text), parse_mode=ParseMode.HTML)
            return

        if state == "vip_rm":
            if not text.isdigit():
                await msg.reply_text(t(lang, "invalid_id"))
                return
            tid = int(text)
            vip_users.discard(tid)
            await save_settings()
            asyncio.create_task(update_user_field(tid, "is_vip", False))
            await msg.reply_text(t(lang, "vip_removed", id=text), parse_mode=ParseMode.HTML)
            return

        if state == "adm_add":
            if not is_owner(uid):
                await msg.reply_text(t(lang, "not_owner"))
                return
            if not text.isdigit():
                await msg.reply_text(t(lang, "invalid_id"))
                return
            admins_list.add(int(text))
            await save_settings()
            await msg.reply_text(t(lang, "admin_added", id=text), parse_mode=ParseMode.HTML)
            return

        if state == "adm_rm":
            if not is_owner(uid):
                await msg.reply_text(t(lang, "not_owner"))
                return
            if not text.isdigit():
                await msg.reply_text(t(lang, "invalid_id"))
                return
            if int(text) == OWNER_ID:
                await msg.reply_text("⛔ ناتوانیت خاوەنەکە لابەری!")
                return
            admins_list.discard(int(text))
            await save_settings()
            await msg.reply_text(t(lang, "admin_removed", id=text), parse_mode=ParseMode.HTML)
            return

        if state == "user_info":
            if not text.isdigit():
                await msg.reply_text(t(lang, "invalid_id"))
                return
            tuid  = int(text)
            udata = await get_user_data(tuid)
            if not udata:
                await msg.reply_text(t(lang, "user_not_found"))
                return
            vip_s = "✅" if tuid in vip_users or udata.get("is_vip") else "❌"
            blk_s = "✅" if tuid in blocked_users else "❌"
            await msg.reply_text(
                t(lang, "user_info_text",
                  id       = tuid,
                  name     = html.escape(str(udata.get("name", "?"))),
                  username = udata.get("username", "—"),
                  date     = udata.get("joined_date", "—"),
                  vip      = vip_s,
                  blocked  = blk_s,
                ),
                parse_mode   = ParseMode.HTML,
                reply_markup = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🟢 ئەنبلۆک" if tuid in blocked_users else "🚫 بلۆک",
                            callback_data=f"quick_blk_{tuid}",
                        ),
                        InlineKeyboardButton(
                            "❌ VIP لابردن" if tuid in vip_users else "💎 VIP زیادکردن",
                            callback_data=f"quick_vip_{tuid}",
                        ),
                    ],
                    [InlineKeyboardButton("✉️ نامە بنێرە", callback_data=f"quick_msg_{tuid}")],
                ]),
            )
            return

        if state == "msg_user_ask_id":
            if not text.isdigit():
                await msg.reply_text(t(lang, "invalid_id"))
                return
            admin_waiting_state[uid] = f"msg_user_send_{text}"
            await msg.reply_text(
                t(lang, "send_msg_to_user", id=text),
                parse_mode   = ParseMode.HTML,
                reply_markup = InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ هەڵوەشاندنەوە", callback_data="np_cancel")
                ]]),
            )
            return

        if state.startswith("msg_user_send_"):
            target_id = int(state.split("_")[-1])
            try:
                await context.bot.copy_message(
                    chat_id      = target_id,
                    from_chat_id = msg.chat_id,
                    message_id   = msg.message_id,
                )
                await msg.reply_text(t(lang, "msg_sent_to_user"))
            except Exception as e:
                await msg.reply_text(f"❌ هەڵە: {e}")
            return

        if state == "set_max_photos":
            if not text.isdigit():
                await msg.reply_text(t(lang, "invalid_id"))
                return
            bot_settings_global["max_photos"] = min(int(text), 30)
            await save_settings()
            await msg.reply_text(t(lang, "setting_updated"))
            return

        if state == "set_api_timeout":
            if not text.isdigit():
                await msg.reply_text(t(lang, "invalid_id"))
                return
            bot_settings_global["api_timeout"] = int(text)
            await save_settings()
            await msg.reply_text(t(lang, "setting_updated"))
            return

        if state == "set_welcome_msg":
            bot_settings_global["welcome_msg"] = msg.text or ""
            await save_settings()
            await msg.reply_text(t(lang, "welcome_msg_set"))
            return

    # ── پشکنینی بلۆک و چاکسازی ───────────────────────────────────────────────
    if not msg.text:
        return

    txt = msg.text.strip()

    if is_blocked(uid):
        return

    if bot_settings_global["maintenance_mode"] and not is_admin(uid):
        await msg.reply_text(t(lang, "error_maintenance"), parse_mode=ParseMode.HTML)
        return

    # ✅ FIX: پشکنینی لینک بە شێوازی ووردتر
    if not is_tiktok_url(txt):
        return

    # ✅ Anti-Flood
    if check_flood(uid):
        await msg.reply_text(t(lang, "error_flood"), parse_mode=ParseMode.HTML)
        return

    # پشکنینی جۆین
    is_sub, not_joined = await check_user_subscription(uid, context)
    bypass = (
        (is_admin(uid) and bot_settings_global.get("admin_bypass_join", True)) or
        (is_vip(uid)   and bot_settings_global.get("vip_bypass_join",   True))
    )
    if not is_sub and not bypass:
        kb  = [
            [InlineKeyboardButton(
                t(lang, "btn_join_channel", ch=ch),
                url=f"https://t.me/{ch.replace('@', '')}",
            )]
            for ch in not_joined
        ]
        kb += [[InlineKeyboardButton(t(lang, "btn_check_join"), callback_data="check_sub_start")]]
        await msg.reply_text(
            t(lang, "force_join_text"),
            parse_mode   = ParseMode.HTML,
            reply_markup = InlineKeyboardMarkup(kb),
        )
        return

    # ── داونلۆدکردن ───────────────────────────────────────────────────────────
    status_msg = await msg.reply_text(
        t(lang, "searching"), parse_mode=ParseMode.HTML
    )

    try:
        max_retries = int(bot_settings_global.get("max_retries", 3))
        result = await fetch_tiktok_data(txt, max_retries=max_retries)

        if not result:
            await status_msg.edit_text(t(lang, "error_invalid_link"))
            return

        raw_data = result["data"]
        creator, details, images = parse_api_response(raw_data)

        # photo_mode ڕێکخستن
        photo_mode = bot_settings_global.get("photo_mode", "auto")
        if photo_mode == "force_video":
            images = []
        elif photo_mode == "force_photos" and not images:
            pass  # بەردەوامبە بۆ video

        # پاراستنی session
        await save_user_session(uid, {
            "creator": creator,
            "details": details,
            "images" : images,
        })

        # دروستکردنی caption
        title    = clean_title(details.get("title", "") or "")
        stats    = details.get("stats", {})
        views    = format_number(stats.get("views", 0)    or stats.get("play_count", 0))
        likes    = format_number(stats.get("likes", 0)    or stats.get("digg_count", 0))
        comments = format_number(stats.get("comments", 0) or stats.get("comment_count", 0))

        caption = (
            f"{t(lang, 'download_found')}\n\n"
            f"{t(lang, 'download_title', title=html.escape(title))}\n"
            f"{t(lang, 'download_owner', owner=html.escape(creator))}\n\n"
            f"👁 {views}   ❤️ {likes}   💬 {comments}"
        )

        # ✅ FIX: keyboard بەپێی بوونی images یان video
        if images:
            kb = [
                [InlineKeyboardButton(t(lang, "btn_photos", count=len(images)), callback_data="dl_photos")],
                [InlineKeyboardButton(t(lang, "btn_audio"),                     callback_data="dl_audio")],
                [InlineKeyboardButton(t(lang, "btn_delete"),                    callback_data="close")],
            ]
        else:
            # ✅ FIX: تەنیا ئەگەر ڤیدیۆ URL هەبوو، btn_video نیشان بدە
            video_url = (
                details.get("video", {}).get("play", "") or
                details.get("video", {}).get("download_addr", "")
            )
            kb = []
            if video_url:
                kb.append([InlineKeyboardButton(t(lang, "btn_video"), callback_data="dl_video")])
            kb.append([InlineKeyboardButton(t(lang, "btn_audio"),  callback_data="dl_audio")])
            kb.append([InlineKeyboardButton(t(lang, "btn_delete"), callback_data="close")])

        # cover url
        cover_url = (
            details.get("cover", {}).get("cover", "") or
            details.get("cover", {}).get("origin_cover", "") or
            details.get("origin_cover", "") or
            (images[0] if images else "")
        )

        if cover_url:
            try:
                await status_msg.edit_media(
                    InputMediaPhoto(
                        cover_url,
                        caption    = caption,
                        parse_mode = ParseMode.HTML,
                    ),
                    reply_markup = InlineKeyboardMarkup(kb),
                )
            except Exception as e:
                logger.warning(f"Cover هەڵە: {e}")
                # ✅ FIX: ئەگەر cover کار نەکرد، تێکست بنێرە
                try:
                    await status_msg.edit_text(
                        caption,
                        parse_mode   = ParseMode.HTML,
                        reply_markup = InlineKeyboardMarkup(kb),
                    )
                except Exception:
                    await msg.reply_text(
                        caption,
                        parse_mode   = ParseMode.HTML,
                        reply_markup = InlineKeyboardMarkup(kb),
                    )
        else:
            try:
                await status_msg.edit_text(
                    caption,
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup(kb),
                )
            except Exception:
                await msg.reply_text(
                    caption,
                    parse_mode   = ParseMode.HTML,
                    reply_markup = InlineKeyboardMarkup(kb),
                )

    except Exception as e:
        logger.error(f"❌ هەڵەی گشتی داونلۆد: {e}")
        try:
            await status_msg.edit_text(t(lang, "error_download_fail"))
        except Exception:
            pass


# ==============================================================================
# ─── INITIALIZATION ───────────────────────────────────────────────────────────
# ==============================================================================
ptb_app = ApplicationBuilder().token(TOKEN).build()

ptb_app.add_handler(CommandHandler(["start", "menu"], start_command))
ptb_app.add_handler(CommandHandler("help",            help_command))

# numpad و channel input باشترەیە پێش button_handler تۆمار بکرێن
ptb_app.add_handler(CallbackQueryHandler(numpad_handler,       pattern=r"^(np_|chi_)"))
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
        "version": bot_settings_global.get("bot_version", "7.0"),
        "time"   : get_current_time(),
    }


# ==============================================================================
# ========================= END OF FILE ========================================
# ==============================================================================
