# ==============================================================================
# ==                                                                          ==
# ==           TIKTOK DOWNLOADER BOT - V14.0 ULTRA PRO MAX (GOD MODE)         ==
# ==           Developed exclusively for: @j4ck_721s                          ==
# ==           Features: 3-Language, Unified Panel, Auto-Fallback             ==
# ==                                                                          ==
# ==============================================================================

import os, time, logging, httpx, re, html, asyncio, json, io, traceback
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, ForceReply
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, CallbackQueryHandler, filters,
)
from telegram.constants import ChatMemberStatus
from telegram.error import BadRequest

# ==============================================================================
# ── 1. CONFIGURATION ──────────────────────────────────────────────────────────
# ==============================================================================
TOKEN        = os.getenv("BOT_TOKEN") or "DUMMY_TOKEN"
DB_URL       = os.getenv("DB_URL") or ""
DB_SECRET    = os.getenv("DB_SECRET") or ""
OWNER_ID     = 5977475208
DEV          = "@j4ck_721s"
CHANNEL_URL  = "https://t.me/jack_721_mod"
START_TIME   = time.time()
SESSION_TTL  = 1800

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)
app = FastAPI()

super_admins_set : set  = {OWNER_ID}
admins_set       : set  = {OWNER_ID}
channels_list    : list = []
blocked_set      : set  = set()
vip_set          : set  = set()
waiting_state    : dict = {}
last_cfg_load    = 0

CFG: dict = {
    "maintenance"  : False,
    "welcome_msg"  : "",
    "default_lang" : "ku",
    "max_photos"   : 15,
    "api_timeout"  : 60,
    "vip_bypass"   : True,
    "admin_bypass" : True,
    "total_dl"     : 0,
    "total_users"  : 0,
    "active_api"   : "auto",
}

# ==============================================================================
# ── 2. LANGUAGE DICTIONARY (Kurdish / English / Arabic) ───────────────────────
# ==============================================================================
L: dict = {

# ─────────────────────────────────── KURDISH ──────────────────────────────────
"ku": {
    "welcome"         : "👋 سڵاو {name} {badge}\n\n🤖 بەخێربێیت بۆ پێشکەوتووترین بۆتی تیکتۆک!\n📥 ڤیدیۆ (بێ لۆگۆ)، وێنە و گۆرانی دابەزێنە بە بەرزترین خێرایی.\n\n━━━━━━━━━━━━━━━━━━━\n👇 تەنیا لینکی تیکتۆکەکە بنێرەم:",
    "help"            : "📚 ڕێنمایی بەکارهێنان\n\n1️⃣ لینکی ڤیدیۆ لە تیکتۆک کۆپی بکە.\n2️⃣ لینکەکە لێرە پەیست بکە.\n3️⃣ جۆری دابەزاندن هەڵبژێرە!\n\n🎥 ڤیدیۆ: بەبێ لۆگۆ.\n📸 وێنە: هەموو وێنەکانی پۆستەکە.\n🎵 گۆرانی: فۆرماتی MP3.\n\n💎 VIP: بێ جۆینی ناچاری، خێرایی زۆرتر.\n📩 پەیوەندی: {dev}",
    "profile"         : "👤 کارتی پرۆفایل\n\n🆔 ئایدی: {id}\n👤 ناو: {name}\n🔗 یوزەرنەیم: @{user}\n📅 تۆماربوون: {date}\n💎 VIP: {vip}\n🌍 زمان: {ulang}\n📥 دابەزاندن: {dl} جار",
    "vip_info"        : "💎 تایبەتمەندییەکانی VIP\n\n✅ بەبێ جۆینی ناچاری.\n✅ خێرایی دابەزاندنی زیاتر.\n✅ وێنەی بێسنوور.\n\nبۆ کڕینی VIP: {dev}",
    "lang_title"      : "🌍 زمانی خۆت هەڵبژێرە:",
    "lang_saved"      : "✅ زمانەکە گۆڕدرا!",
    "bot_lang_title"  : "🌍 زمانی سەرەکی بۆتەکە هەڵبژێرە:\n(ئەمە زمانی سەرەکی بۆ هەموو بەکارهێنەرانە)",
    "bot_lang_saved"  : "✅ زمانی سەرەکی بۆتەکە گۆڕدرا بۆ: {lang}",
    "force_join"      : "🔒 جۆینی ناچاری\nتکایە سەرەتا ئەم چەناڵانە جۆین بکە، پاشان کلیک لە '✅ جۆینم کرد' بکە:",
    "processing"      : "🔍 دەگەڕێم بۆ لینکەکە...\nچەند چرکەیەک چاوەڕێبە ⏳",
    "found"           : "📝 سەردێڕ: {title}\n👤 خاوەن: {owner}\n\n📊 ئامارەکان:\n👁 بینەر: {views}  \n❤️ لایک: {likes}  \n💬 کۆمێنت: {comments}",
    "sending_photos"  : "📸 وێنەکان ئامادە دەکرێن...",
    "blocked_msg"     : "⛔ تۆ بلۆک کراویت.",
    "maintenance_msg" : "🛠 چاکسازی کاتی!\n\n⚙️ بۆتەکەمان لە ژێر نوێکردنەوەیەکی گەورەدایە.\n⏳ زووترین کاتێکدا دەگەڕێینەوە!\n\n📩 پەیوەندی: {dev}",
    "session_expired" : "⚠️ کات بەسەرچوو! لینکەکە سەرلەنوێ بنێرەوە.",
    "invalid_link"    : "❌ لینکەکە هەڵەیە یان نادۆزرێتەوە!",
    "dl_fail"         : "❌ هەڵەیەک ڕوویدا! ناتوانرێت دابەزێنرێت.",
    "no_photo"        : "❌ ئەم پۆستە وێنەی تێدا نییە!",
    "no_video"        : "❌ ڤیدیۆکە نەدۆزرایەوە!",
    "no_audio"        : "❌ دەنگەکە بەردەست نییە!",
    "invalid_id"      : "❌ ئایدیەکە دروست نییە! تەنیا ژمارە بنووسە.",
    "user_not_found"  : "⚠️ بەکارهێنەر نەدۆزرایەوە.",
    "broadcast_done"  : "📢 برۆدکاست تەواو بوو\n✅ گەیشت بە: {ok}\n❌ نەگەیشت: {fail}",
    "welcome_set"     : "✅ نامەی بەخێرهاتن گۆڕدرا.",
    "write_welcome"   : "✍️ نامەی بەخێرهاتن بنووسە:\n(دەتوانیت {name} و {badge} بەکاربێنیت)",
    "write_id"        : "✍️ ئایدی کەسەکە بنووسە و بینێرە:",
    "write_ch"        : "✍️ یوزەرنەیمی چەناڵ بنووسە (نمونە: @mychannel):",
    "vip_yes"         : "بەڵێ 💎",
    "vip_no"          : "نەخێر",
    "badge_owner"     : "👑",
    "badge_super"     : "🌌",
    "badge_admin"     : "🛡",
    "badge_vip"       : "💎",
    "b_dl"       : "📥 دابەزاندنی نوێ",
    "b_profile"  : "👤 پرۆفایلی من",
    "b_vip"      : "💎 بەشی VIP",
    "b_settings" : "⚙️ ڕێکخستن و زمان",
    "b_help"     : "ℹ️ فێرکاری",
    "b_channel"  : "📢 کەناڵی بۆت",
    "b_panel"    : "⚙️ پانێڵی کۆنتڕۆڵ",
    "b_back"     : "🔙 گەڕانەوە",
    "b_delete"   : "🗑 سڕینەوە",
    "b_joined"   : "✅ جۆینم کرد",
    "b_video"    : "🎥 ڤیدیۆ (بێ لۆگۆ)",
    "b_photos"   : "📸 وێنەکان ({n})",
    "b_audio"    : "🎵 گۆرانی (MP3)",
    "b_ku"       : "🔴🔆🟢 کوردی",
    "b_en"       : "🇺🇸 English",
    "b_ar"       : "🇸🇦 العربية",
    "b_cancel"   : "❌ هەڵوەشاندنەوە",
    "b_confirm_remove" : "✅ بەڵێ، بیسڕەوە",
    "b_cancel_remove"  : "❌ نەخێر، هەڵوەشانەوە",
    "confirm_remove_admin" : "⚠️ دڵنیایت دەتەوێت ئەم ئەدمینە بسڕیتەوە؟\n🆔 {id}",
    "confirm_remove_super" : "⚠️ دڵنیایت دەتەوێت ئەم سوپەر ئەدمینە بسڕیتەوە؟\n🆔 {id}",
    "confirm_remove_ch"    : "⚠️ دڵنیایت دەتەوێت ئەم چەناڵە بسڕیتەوە؟\n{ch}",
    # --- Unified Panel ---
    "unified_panel_title" : "⚙️ پانێڵی کۆنتڕۆڵ\n\n👥 بەکارهێنەران: {users}\n💎 VIP: {vip}\n🚫 بلۆككراو: {blocked}\n📥 داونلۆد: {dl}\n⏱ Uptime: {uptime}",
    # --- Admin Panel ---
    "adm_panel_title"  : "🛡 بەشی ئەدمین",
    "adm_stats_title"  : "📊 ئامارەکان:\n👥 کۆی بەکارهێنەران: {users}\n💎 VIP: {vip}\n🚫 بلۆككراو: {blocked}\n📥 داونلۆدەکان: {dl}\n⏱ Uptime: {uptime}",
    "adm_broadcast_ask": "✍️ پەیامەکەت بنێرە (تێکست، وێنە، ڤیدیۆ):",
    "adm_block_ask"    : "🚫 بلۆككردنی بەکارهێنەر:\n\n{write_id}",
    "adm_info_ask"     : "👤 زانیاری بەکارهێنەر:\n\n{write_id}",
    "b_adm_stats"      : "📊 ئامارەکان",
    "b_adm_broadcast"  : "📢 برۆدکاست",
    "b_adm_block"      : "🚫 بلۆككردن",
    "b_adm_info"       : "👤 زانیاری کەس",
    "b_adm_admins"     : "👮 ئەدمینەکان",
    # --- Super Panel ---
    "sup_panel_title"  : "🌌 بەشی سوپەر",
    "sup_maint_on"     : "🔴 چالاکە",
    "sup_maint_off"    : "🟢 ناچالاکە",
    "sup_api_title"    : "⚙️ سەرچاوەی دابەزاندن هەڵبژێرە:",
    "sup_admins_title" : "👮 ئەدمینەکان ({count}):",
    "sup_vip_title"    : "💎 VIP ({count}):",
    "sup_ch_title"     : "📢 چەناڵەکان ({count}):",
    "sup_ch_empty"     : "📭 بەتاڵە",
    "sup_ch_remove_q"  : "کام چەناڵ دەسڕیتەوە؟",
    "sup_ch_added"     : "✅ {ch} زیاد کرا!",
    "sup_add_adm_ask"  : "➕ ئەدمینی نوێ:\n\n{write_id}",
    "sup_rm_adm_ask"   : "➖ لابردنی ئەدمین:\n\n{write_id}",
    "sup_add_vip_ask"  : "💎 پێدانی VIP:\n\n{write_id}",
    "sup_rm_vip_ask"   : "➖ سەندنەوەی VIP:\n\n{write_id}",
    "sup_add_ch_ask"   : "📢 زیادکردنی چەناڵ:\n\n{write_ch}",
    "b_sup_admins"     : "👮 ئەدمینەکان",
    "b_sup_vip"        : "💎 VIP",
    "b_sup_channels"   : "📢 چەناڵەکان",
    "b_sup_maint"      : "🛠 چاکسازی: {status}",
    "b_sup_api"        : "⚙️ API",
    "b_sup_botlang"    : "🌍 زمانی بۆت",
    "b_add"            : "➕ زیادکردن",
    "b_remove"         : "➖ لابردن",
    "b_add_vip"        : "➕ VIP",
    "b_rm_vip"         : "➖ VIP",
    "b_refresh"        : "🔄 نوێکردنەوە",
    "b_clear"          : "🗑 سڕینەوە",
    # --- Owner Panel ---
    "own_panel_title"  : "👑 بەشی خاوەن",
    "own_super_title"  : "🌌 سوپەر ئەدمینەکان ({count}):",
    "own_add_sup_ask"  : "➕ سوپەر ئەدمینی نوێ:\n\n{write_id}",
    "own_rm_sup_ask"   : "➖ لابردنی سوپەر ئەدمین:\n\n{write_id}",
    "b_own_super"      : "🌌 سوپەر ئەدمین",
    "b_own_botlang"    : "🌍 زمانی بۆت",
    "b_own_welcome"    : "📝 نامەی خێرهاتن",
    "b_own_reset"      : "🗑 ڕیسێتی ئامار",
    "b_own_backup"     : "💾 باکئەپ",
    "own_reset_done"   : "✅ ئامارەکان سفر کرانەوە!",
    "own_backup_prep"  : "⏳ ئامادە دەکرێت...",
    # --- New user notification ---
    "new_user_notify"  : "🔔 بەکارهێنەری نوێ!\n\n👤 ناو: {name}\n🔗 یوزەر: {uname}\n🆔 ئایدی: {uid}\n🌐 زمانی ئەپ: {app_lang}\n📅 {date}",
    "b_notify_block"   : "🚫 بلۆک",
    "b_notify_vip"     : "💎 VIP",
    "b_notify_admin"   : "🛡 ئەدمین",
    "b_notify_info"    : "👤 زانیاری",
    # --- Action results ---
    "act_blocked"      : "🚫 {id} بلۆک کرا!",
    "act_unblocked"    : "✅ {id} بلۆکەکەی لابرا.",
    "act_adm_added"    : "✅ {id} بوو بە ئەدمین!",
    "act_adm_removed"  : "➖ {id} لە ئەدمین لابرا.",
    "act_sup_added"    : "🌌 {id} بوو بە سوپەر ئەدمین!",
    "act_sup_removed"  : "➖ {id} لە سوپەر لابرا.",
    "act_vip_added"    : "💎 {id} کرایە VIP!",
    "act_vip_removed"  : "➖ VIP لە {id} سەندرایەوە.",
    "act_ch_wrong_fmt" : "❌ فۆرماتەکە هەڵەیە! بنووسە: @channelname",
    # --- User info display ---
    "userinfo_text"    : "👤 ناو: {name}\n🔗 یوزەر: @{user}\n🆔 ئایدی: {id}\n💎 VIP: {vip}\n🌍 زمان: {lang}\n📥 داونلۆد: {dl}\n📅 تۆماربوون: {date}",
    # --- Broadcast ---
    "broadcast_sending": "⏳ ناردن دەستی پێکرد بۆ {total} کەس...",
    "broadcast_progress": "⏳ ناردن: {done}/{total}...",
    # --- Bot language ---
    "bot_lang_current" : "🔵 ئێستا: {cur}",
    "ask_link_prompt"  : "🔗 تکایە لینکی تیکتۆکەکە بنێرەم:",
},
"en": {
    "welcome"         : "👋 Hello {name} {badge}\n\n🤖 Welcome to the most advanced TikTok Downloader Bot!\n📥 Download videos (no watermark), photos & audio at top speed.\n\n━━━━━━━━━━━━━━━━━━━\n👇 Just send me a TikTok link:",
    "help"            : "📚 How to Use\n\n1️⃣ Copy a TikTok video link.\n2️⃣ Paste it here.\n3️⃣ Choose your download type!\n\n🎥 Video: No watermark.\n📸 Photos: All post images.\n🎵 Audio: MP3 format.\n\n💎 VIP: No forced join, faster downloads.\n📩 Contact: {dev}",
    "profile"         : "👤 Your Profile\n\n🆔 ID: {id}\n👤 Name: {name}\n🔗 Username: @{user}\n📅 Joined: {date}\n💎 VIP: {vip}\n🌍 Language: {ulang}\n📥 Downloads: {dl} times",
    "vip_info"        : "💎 VIP Benefits\n\n✅ Skip forced channel joins.\n✅ Faster download speed.\n✅ Unlimited photos.\n\nBuy VIP: {dev}",
    "lang_title"      : "🌍 Choose your language:",
    "lang_saved"      : "✅ Language changed!",
    "bot_lang_title"  : "🌍 Choose the bot's default language:\n(This applies to all users globally)",
    "bot_lang_saved"  : "✅ Bot default language changed to: {lang}",
    "force_join"      : "🔒 Forced Join\nPlease join the channels below first, then click '✅ I Joined':",
    "processing"      : "🔍 Fetching your link...\nPlease wait a few seconds ⏳",
    "found"           : "📝 Title: {title}\n👤 Author: {owner}\n\n📊 Stats:\n👁 Views: {views}  \n❤️ Likes: {likes}  \n💬 Comments: {comments}",
    "sending_photos"  : "📸 Preparing photos...",
    "blocked_msg"     : "⛔ You have been blocked.",
    "maintenance_msg" : "🛠 Maintenance Mode!\n\n⚙️ The bot is under a major update.\n⏳ We'll be back soon!\n\n📩 Contact: {dev}",
    "session_expired" : "⚠️ Session expired! Please send the link again.",
    "invalid_link"    : "❌ Invalid link or not found!",
    "dl_fail"         : "❌ An error occurred! Could not download this post.",
    "no_photo"        : "❌ This post has no photos!",
    "no_video"        : "❌ Video not found!",
    "no_audio"        : "❌ Audio not available!",
    "invalid_id"      : "❌ Invalid ID! Numbers only.",
    "user_not_found"  : "⚠️ User not found.",
    "broadcast_done"  : "📢 Broadcast Complete\n✅ Delivered: {ok}\n❌ Failed: {fail}",
    "welcome_set"     : "✅ Welcome message updated.",
    "write_welcome"   : "✍️ Write the welcome message:\n(You can use {name} and {badge})",
    "write_id"        : "✍️ Type the user ID and send:",
    "write_ch"        : "✍️ Type the channel username (e.g. @mychannel):",
    "vip_yes"         : "Yes 💎",
    "vip_no"          : "No",
    "badge_owner"     : "👑",
    "badge_super"     : "🌌",
    "badge_admin"     : "🛡",
    "badge_vip"       : "💎",
    "b_dl"       : "📥 New Download",
    "b_profile"  : "👤 My Profile",
    "b_vip"      : "💎 VIP Section",
    "b_settings" : "⚙️ Settings & Language",
    "b_help"     : "ℹ️ Help",
    "b_channel"  : "📢 Bot Channel",
    "b_panel"    : "⚙️ Control Panel",
    "b_back"     : "🔙 Back",
    "b_delete"   : "🗑 Delete",
    "b_joined"   : "✅ I Joined",
    "b_video"    : "🎥 Video (No Watermark)",
    "b_photos"   : "📸 Photos ({n})",
    "b_audio"    : "🎵 Audio (MP3)",
    "b_ku"       : "🔴🔆🟢 کوردی",
    "b_en"       : "🇺🇸 English",
    "b_ar"       : "🇸🇦 العربية",
    "b_cancel"   : "❌ Cancel",
    "b_confirm_remove" : "✅ Yes, Remove",
    "b_cancel_remove"  : "❌ No, Cancel",
    "confirm_remove_admin" : "⚠️ Are you sure you want to remove this admin?\n🆔 {id}",
    "confirm_remove_super" : "⚠️ Are you sure you want to remove this super admin?\n🆔 {id}",
    "confirm_remove_ch"    : "⚠️ Are you sure you want to remove this channel?\n{ch}",
    # --- Unified Panel ---
    "unified_panel_title" : "⚙️ Control Panel\n\n👥 Users: {users}\n💎 VIP: {vip}\n🚫 Blocked: {blocked}\n📥 Downloads: {dl}\n⏱ Uptime: {uptime}",
    # --- Admin Panel ---
    "adm_panel_title"  : "🛡 Admin Section",
    "adm_stats_title"  : "📊 Stats:\n👥 Total users: {users}\n💎 VIP: {vip}\n🚫 Blocked: {blocked}\n📥 Downloads: {dl}\n⏱ Uptime: {uptime}",
    "adm_broadcast_ask": "✍️ Send your message (text, photo, video):",
    "adm_block_ask"    : "🚫 Block User:\n\n{write_id}",
    "adm_info_ask"     : "👤 User Info:\n\n{write_id}",
    "b_adm_stats"      : "📊 Stats",
    "b_adm_broadcast"  : "📢 Broadcast",
    "b_adm_block"      : "🚫 Block User",
    "b_adm_info"       : "👤 User Info",
    "b_adm_admins"     : "👮 Admins",
    # --- Super Panel ---
    "sup_panel_title"  : "🌌 Super Section",
    "sup_maint_on"     : "🔴 ON",
    "sup_maint_off"    : "🟢 OFF",
    "sup_api_title"    : "⚙️ Choose API source:",
    "sup_admins_title" : "👮 Admins ({count}):",
    "sup_vip_title"    : "💎 VIP ({count}):",
    "sup_ch_title"     : "📢 Channels ({count}):",
    "sup_ch_empty"     : "📭 Empty",
    "sup_ch_remove_q"  : "Which channel to remove?",
    "sup_ch_added"     : "✅ {ch} added!",
    "sup_add_adm_ask"  : "➕ Add Admin:\n\n{write_id}",
    "sup_rm_adm_ask"   : "➖ Remove Admin:\n\n{write_id}",
    "sup_add_vip_ask"  : "💎 Give VIP:\n\n{write_id}",
    "sup_rm_vip_ask"   : "➖ Remove VIP:\n\n{write_id}",
    "sup_add_ch_ask"   : "📢 Add Channel:\n\n{write_ch}",
    "b_sup_admins"     : "👮 Admins",
    "b_sup_vip"        : "💎 VIP",
    "b_sup_channels"   : "📢 Channels",
    "b_sup_maint"      : "🛠 Maintenance: {status}",
    "b_sup_api"        : "⚙️ API",
    "b_sup_botlang"    : "🌍 Bot Language",
    "b_add"            : "➕ Add",
    "b_remove"         : "➖ Remove",
    "b_add_vip"        : "➕ VIP",
    "b_rm_vip"         : "➖ VIP",
    "b_refresh"        : "🔄 Refresh",
    "b_clear"          : "🗑 Clear",
    # --- Owner Panel ---
    "own_panel_title"  : "👑 Owner Section",
    "own_super_title"  : "🌌 Super Admins ({count}):",
    "own_add_sup_ask"  : "➕ Add Super Admin:\n\n{write_id}",
    "own_rm_sup_ask"   : "➖ Remove Super Admin:\n\n{write_id}",
    "b_own_super"      : "🌌 Super Admins",
    "b_own_botlang"    : "🌍 Bot Language",
    "b_own_welcome"    : "📝 Welcome Message",
    "b_own_reset"      : "🗑 Reset Stats",
    "b_own_backup"     : "💾 Backup",
    "own_reset_done"   : "✅ Stats have been reset!",
    "own_backup_prep"  : "⏳ Preparing...",
    # --- New user notification ---
    "new_user_notify"  : "🔔 New User!\n\n👤 Name: {name}\n🔗 User: {uname}\n🆔 ID: {uid}\n🌐 App Lang: {app_lang}\n📅 {date}",
    "b_notify_block"   : "🚫 Block",
    "b_notify_vip"     : "💎 VIP",
    "b_notify_admin"   : "🛡 Admin",
    "b_notify_info"    : "👤 Info",
    # --- Action results ---
    "act_blocked"      : "🚫 {id} has been blocked!",
    "act_unblocked"    : "✅ {id} has been unblocked.",
    "act_adm_added"    : "✅ {id} is now Admin!",
    "act_adm_removed"  : "➖ {id} removed from Admin.",
    "act_sup_added"    : "🌌 {id} is now Super Admin!",
    "act_sup_removed"  : "➖ {id} removed from Super Admin.",
    "act_vip_added"    : "💎 {id} is now VIP!",
    "act_vip_removed"  : "➖ VIP removed from {id}.",
    "act_ch_wrong_fmt" : "❌ Wrong format! Use: @channelname",
    # --- User info display ---
    "userinfo_text"    : "👤 Name: {name}\n🔗 User: @{user}\n🆔 ID: {id}\n💎 VIP: {vip}\n🌍 Lang: {lang}\n📥 Downloads: {dl}\n📅 Joined: {date}",
    # --- Broadcast ---
    "broadcast_sending" : "⏳ Starting broadcast to {total} users...",
    "broadcast_progress": "⏳ Sending: {done}/{total}...",
    # --- Bot language ---
    "bot_lang_current"  : "🔵 Current: {cur}",
    "ask_link_prompt"   : "🔗 Please send me the TikTok link:",
},
"ar": {
    "welcome"         : "👋 مرحباً {name} {badge}\n\n🤖 أهلاً بك في أقوى بوت لتحميل تيك توك!\n📥 حمّل الفيديوهات (بدون علامة مائية)، الصور والصوت بأعلى سرعة.\n\n━━━━━━━━━━━━━━━━━━━\n👇 فقط أرسل لي رابط تيك توك:",
    "help"            : "📚 طريقة الاستخدام\n\n1️⃣ انسخ رابط الفيديو من تيك توك.\n2️⃣ الصقه هنا.\n3️⃣ اختر نوع التحميل!\n\n🎥 فيديو: بدون علامة مائية.\n📸 صور: جميع صور المنشور.\n🎵 صوت: بصيغة MP3.\n\n💎 VIP: بدون انضمام إجباري، سرعة أعلى.\n📩 تواصل: {dev}",
    "profile"         : "👤 بطاقة الملف الشخصي\n\n🆔 المعرّف: {id}\n👤 الاسم: {name}\n🔗 اليوزر: @{user}\n📅 تاريخ التسجيل: {date}\n💎 VIP: {vip}\n🌍 اللغة: {ulang}\n📥 التحميلات: {dl} مرة",
    "vip_info"        : "💎 مميزات VIP\n\n✅ تخطي الانضمام الإجباري.\n✅ سرعة تحميل أعلى.\n✅ صور غير محدودة.\n\nللشراء: {dev}",
    "lang_title"      : "🌍 اختر لغتك:",
    "lang_saved"      : "✅ تم تغيير اللغة!",
    "bot_lang_title"  : "🌍 اختر اللغة الافتراضية للبوت:\n(سيطبق على جميع المستخدمين)",
    "bot_lang_saved"  : "✅ تم تغيير لغة البوت إلى: {lang}",
    "force_join"      : "🔒 انضمام إجباري\nالرجاء الانضمام للقنوات أدناه أولاً، ثم اضغط '✅ انضممت':",
    "processing"      : "🔍 جارٍ البحث عن الرابط...\nانتظر لحظة ⏳",
    "found"           : "📝 العنوان: {title}\n👤 المالك: {owner}\n\n📊 الإحصائيات:\n👁 مشاهدة: {views}  \n❤️ إعجاب: {likes}  \n💬 تعليق: {comments}",
    "sending_photos"  : "📸 جارٍ تجهيز الصور...",
    "blocked_msg"     : "⛔ أنت محظور.",
    "maintenance_msg" : "🛠 وضع الصيانة!\n\n⚙️ البوت تحت تحديث كبير.\n⏳ سنعود قريباً!\n\n📩 تواصل: {dev}",
    "session_expired" : "⚠️ انتهت الجلسة! أرسل الرابط مجدداً.",
    "invalid_link"    : "❌ الرابط غير صحيح أو غير موجود!",
    "dl_fail"         : "❌ حدث خطأ! تعذّر تحميل هذا المنشور.",
    "no_photo"        : "❌ لا توجد صور في هذا المنشور!",
    "no_video"        : "❌ الفيديو غير موجود!",
    "no_audio"        : "❌ الصوت غير متاح!",
    "invalid_id"      : "❌ معرّف غير صحيح! أرقام فقط.",
    "user_not_found"  : "⚠️ المستخدم غير موجود.",
    "broadcast_done"  : "📢 اكتمل البث\n✅ وصل إلى: {ok}\n❌ فشل: {fail}",
    "welcome_set"     : "✅ تم تحديث رسالة الترحيب.",
    "write_welcome"   : "✍️ اكتب رسالة الترحيب:\n(يمكنك استخدام {name} و{badge})",
    "write_id"        : "✍️ اكتب معرّف المستخدم وأرسله:",
    "write_ch"        : "✍️ اكتب اسم القناة (مثال: @mychannel):",
    "vip_yes"         : "نعم 💎",
    "vip_no"          : "لا",
    "badge_owner"     : "👑",
    "badge_super"     : "🌌",
    "badge_admin"     : "🛡",
    "badge_vip"       : "💎",
    "b_dl"       : "📥 تحميل جديد",
    "b_profile"  : "👤 ملفي الشخصي",
    "b_vip"      : "💎 قسم VIP",
    "b_settings" : "⚙️ الإعدادات واللغة",
    "b_help"     : "ℹ️ المساعدة",
    "b_channel"  : "📢 قناة البوت",
    "b_panel"    : "⚙️ لوحة التحكم",
    "b_back"     : "🔙 رجوع",
    "b_delete"   : "🗑 حذف",
    "b_joined"   : "✅ انضممت",
    "b_video"    : "🎥 فيديو (بدون علامة مائية)",
    "b_photos"   : "📸 الصور ({n})",
    "b_audio"    : "🎵 صوت (MP3)",
    "b_ku"       : "🔴🔆🟢 کوردی",
    "b_en"       : "🇺🇸 English",
    "b_ar"       : "🇸🇦 العربية",
    "b_cancel"   : "❌ إلغاء",
    "b_confirm_remove" : "✅ نعم، احذف",
    "b_cancel_remove"  : "❌ لا، إلغاء",
    "confirm_remove_admin" : "⚠️ هل أنت متأكد من حذف هذا المشرف؟\n🆔 {id}",
    "confirm_remove_super" : "⚠️ هل أنت متأكد من حذف هذا المشرف المميز؟\n🆔 {id}",
    "confirm_remove_ch"    : "⚠️ هل أنت متأكد من حذف هذه القناة؟\n{ch}",
    # --- Unified Panel ---
    "unified_panel_title" : "⚙️ لوحة التحكم\n\n👥 المستخدمون: {users}\n💎 VIP: {vip}\n🚫 محظورون: {blocked}\n📥 التحميلات: {dl}\n⏱ وقت التشغيل: {uptime}",
    # --- Admin Panel ---
    "adm_panel_title"  : "🛡 قسم الإدارة",
    "adm_stats_title"  : "📊 الإحصائيات:\n👥 إجمالي المستخدمين: {users}\n💎 VIP: {vip}\n🚫 محظورون: {blocked}\n📥 التحميلات: {dl}\n⏱ وقت التشغيل: {uptime}",
    "adm_broadcast_ask": "✍️ أرسل رسالتك (نص، صورة، فيديو):",
    "adm_block_ask"    : "🚫 حظر مستخدم:\n\n{write_id}",
    "adm_info_ask"     : "👤 معلومات المستخدم:\n\n{write_id}",
    "b_adm_stats"      : "📊 الإحصائيات",
    "b_adm_broadcast"  : "📢 البث",
    "b_adm_block"      : "🚫 حظر مستخدم",
    "b_adm_info"       : "👤 معلومات المستخدم",
    "b_adm_admins"     : "👮 المشرفون",
    # --- Super Panel ---
    "sup_panel_title"  : "🌌 قسم السوبر",
    "sup_maint_on"     : "🔴 مفعّل",
    "sup_maint_off"    : "🟢 معطّل",
    "sup_api_title"    : "⚙️ اختر مصدر التحميل:",
    "sup_admins_title" : "👮 المشرفون ({count}):",
    "sup_vip_title"    : "💎 VIP ({count}):",
    "sup_ch_title"     : "📢 القنوات ({count}):",
    "sup_ch_empty"     : "📭 فارغ",
    "sup_ch_remove_q"  : "أي قناة تريد حذفها؟",
    "sup_ch_added"     : "✅ تمت إضافة {ch}!",
    "sup_add_adm_ask"  : "➕ إضافة مشرف:\n\n{write_id}",
    "sup_rm_adm_ask"   : "➖ إزالة مشرف:\n\n{write_id}",
    "sup_add_vip_ask"  : "💎 منح VIP:\n\n{write_id}",
    "sup_rm_vip_ask"   : "➖ إزالة VIP:\n\n{write_id}",
    "sup_add_ch_ask"   : "📢 إضافة قناة:\n\n{write_ch}",
    "b_sup_admins"     : "👮 المشرفون",
    "b_sup_vip"        : "💎 VIP",
    "b_sup_channels"   : "📢 القنوات",
    "b_sup_maint"      : "🛠 الصيانة: {status}",
    "b_sup_api"        : "⚙️ API",
    "b_sup_botlang"    : "🌍 لغة البوت",
    "b_add"            : "➕ إضافة",
    "b_remove"         : "➖ إزالة",
    "b_add_vip"        : "➕ VIP",
    "b_rm_vip"         : "➖ VIP",
    "b_refresh"        : "🔄 تحديث",
    "b_clear"          : "🗑 مسح",
    # --- Owner Panel ---
    "own_panel_title"  : "👑 قسم المالك",
    "own_super_title"  : "🌌 المشرفون المميزون ({count}):",
    "own_add_sup_ask"  : "➕ إضافة مشرف مميز:\n\n{write_id}",
    "own_rm_sup_ask"   : "➖ إزالة مشرف مميز:\n\n{write_id}",
    "b_own_super"      : "🌌 المشرفون المميزون",
    "b_own_botlang"    : "🌍 لغة البوت",
    "b_own_welcome"    : "📝 رسالة الترحيب",
    "b_own_reset"      : "🗑 إعادة الإحصائيات",
    "b_own_backup"     : "💾 نسخة احتياطية",
    "own_reset_done"   : "✅ تمت إعادة ضبط الإحصائيات!",
    "own_backup_prep"  : "⏳ جارٍ التحضير...",
    # --- New user notification ---
    "new_user_notify"  : "🔔 مستخدم جديد!\n\n👤 الاسم: {name}\n🔗 اليوزر: {uname}\n🆔 المعرّف: {uid}\n🌐 لغة التطبيق: {app_lang}\n📅 {date}",
    "b_notify_block"   : "🚫 حظر",
    "b_notify_vip"     : "💎 VIP",
    "b_notify_admin"   : "🛡 مشرف",
    "b_notify_info"    : "👤 معلومات",
    # --- Action results ---
    "act_blocked"      : "🚫 تم حظر {id}!",
    "act_unblocked"    : "✅ تم رفع الحظر عن {id}.",
    "act_adm_added"    : "✅ {id} أصبح مشرفاً!",
    "act_adm_removed"  : "➖ تمت إزالة {id} من المشرفين.",
    "act_sup_added"    : "🌌 {id} أصبح مشرفاً مميزاً!",
    "act_sup_removed"  : "➖ تمت إزالة {id} من المشرفين المميزين.",
    "act_vip_added"    : "💎 {id} أصبح VIP!",
    "act_vip_removed"  : "➖ تمت إزالة VIP من {id}.",
    "act_ch_wrong_fmt" : "❌ صيغة خاطئة! استخدم: @channelname",
    # --- User info display ---
    "userinfo_text"    : "👤 الاسم: {name}\n🔗 اليوزر: @{user}\n🆔 المعرّف: {id}\n💎 VIP: {vip}\n🌍 اللغة: {lang}\n📥 التحميلات: {dl}\n📅 تاريخ التسجيل: {date}",
    # --- Broadcast ---
    "broadcast_sending" : "⏳ بدء الإرسال إلى {total} مستخدم...",
    "broadcast_progress": "⏳ جارٍ الإرسال: {done}/{total}...",
    # --- Bot language ---
    "bot_lang_current" : "🔵 الحالية: {cur}",
    "ask_link_prompt"  : "🔗 أرسل رابط تيك توك:",
},
}

LANG_NAMES = {"ku": "🔴🔆🟢 کوردی", "en": "🇺🇸 English", "ar": "🇸🇦 العربية"}

def tx(lang: str, key: str, **kw) -> str:
    base = L.get(lang, L["ku"])
    text = base.get(key, L["ku"].get(key, key))
    try:    return text.format(**kw)
    except: return text

# ==============================================================================
# ── 3. UTILS & DATABASE ───────────────────────────────────────────────────────
# ==============================================================================
DIV = "━━━━━━━━━━━━━━━━━━━"

def clean_title(t: str) -> str:
    return re.sub(r'[\\/*?:"<>|#]', "", str(t))[:100].strip() or "No Title"

def fb(path: str) -> str:
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def fmt(n) -> str:
    try:
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return str(n)
    except: return str(n)

def uptime() -> str:
    d, r = divmod(int(time.time() - START_TIME), 86400)
    h, r = divmod(r, 3600); m, s = divmod(r, 60)
    return f"{d}d {h}h {m}m {s}s"

def back(lang, to="main_menu_render"):
    return [[InlineKeyboardButton(tx(lang, "b_back"), callback_data=to)]]

def is_owner(uid):   return uid == OWNER_ID
def is_super(uid):   return uid in super_admins_set or is_owner(uid)
def is_admin(uid):   return uid in admins_set or is_super(uid)
def is_vip(uid):     return uid in vip_set or is_super(uid)
def is_blocked(uid): return uid in blocked_set

async def check_join(uid, ctx) -> tuple[bool, list]:
    if not channels_list: return True, []
    missing = []
    for ch in channels_list:
        try:
            m = await ctx.bot.get_chat_member(ch, uid)
            if m.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                missing.append(ch)
        except BadRequest as e:
            log.warning(f"check_join error for {ch}: {e}")
        except Exception: pass
    return len(missing) == 0, missing

def bypass_join(uid):
    return (is_admin(uid) and CFG.get("admin_bypass", True)) or \
           (is_vip(uid)   and CFG.get("vip_bypass",   True))

# ── DB helpers ─────────────────────────────────────────────────────────────────
async def db_get(path):
    if not DB_URL: return None
    async with httpx.AsyncClient(timeout=10) as c:
        try:
            r = await c.get(fb(path))
            if r.status_code == 200 and r.text != "null": return r.json()
        except: pass
    return None

async def db_put(path, data):
    if not DB_URL: return
    async with httpx.AsyncClient(timeout=10) as c:
        try: await c.put(fb(path), json=data)
        except: pass

async def load_cfg(force=False):
    global super_admins_set, admins_set, channels_list, blocked_set, vip_set, last_cfg_load
    if not force and (time.time() - last_cfg_load < 45): return
    d = await db_get("sys")
    if d:
        super_admins_set = set(d.get("super_admins", [OWNER_ID]))
        admins_set       = set(d.get("admins",       [OWNER_ID]))
        channels_list    = d.get("channels", [])
        blocked_set      = set(d.get("blocked", []))
        vip_set          = set(d.get("vips",    []))
        CFG.update(d.get("cfg", {}))
        last_cfg_load = time.time()

async def save_cfg():
    await db_put("sys", {
        "super_admins": list(super_admins_set),
        "admins":       list(admins_set),
        "channels":     channels_list,
        "blocked":      list(blocked_set),
        "vips":         list(vip_set),
        "cfg":          CFG,
    })

async def user_get(uid) -> dict | None:   return await db_get(f"users/{uid}")
async def user_put(uid, data):            await db_put(f"users/{uid}", data)
async def user_field(uid, field, val):    await db_put(f"users/{uid}/{field}", val)
async def user_exists(uid) -> bool:       return (await db_get(f"users/{uid}")) is not None
async def all_uids() -> list:             return [int(k) for k in (await db_get("users") or {}).keys()]
async def all_users_data() -> dict:       return await db_get("users") or {}

async def session_save(uid, data):
    data["_ts"] = int(time.time())
    await db_put(f"sessions/{uid}", data)

async def session_get(uid) -> dict | None:
    d = await db_get(f"sessions/{uid}")
    if d and int(time.time()) - d.get("_ts", 0) <= SESSION_TTL: return d
    return None

async def get_user_lang(uid: int) -> str:
    ud = await db_get(f"users/{uid}/lang")
    if ud and ud in L: return ud
    return CFG.get("default_lang", "ku")

# ── Helper: get admin name from DB ─────────────────────────────────────────────
async def get_user_display(uid: int) -> str:
    ud = await db_get(f"users/{uid}")
    if ud:
        name = ud.get("name", str(uid))
        username = ud.get("user", "")
        if username:
            return f"{name} (@{username}) [{uid}]"
        return f"{name} [{uid}]"
    return str(uid)

# ==============================================================================
# ── 4. TIKTOK SCRAPER ─────────────────────────────────────────────────────────
# ==============================================================================
async def fetch_tiktok(url: str) -> dict | None:
    headers = {"User-Agent": "Mozilla/5.0"}
    timeout = int(CFG.get("api_timeout", 45))
    active  = CFG.get("active_api", "auto")

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as c:
        if active in ("auto", "tikwm"):
            try:
                r = await c.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1})
                if r.status_code == 200 and r.json().get("code") == 0:
                    return _parse_tikwm(r.json()["data"])
            except: pass

        if active in ("auto", "hyper"):
            try:
                r = await c.get(f"https://www.api.hyper-bd.site/Tiktok/?url={url}")
                if r.status_code == 200 and r.json().get("ok"):
                    return _parse_hyper(r.json().get("data", {}))
            except: pass

    return None

def _parse_tikwm(d: dict) -> dict:
    imgs = [i for i in d.get("images", []) if isinstance(i, str) and i.startswith("http")]
    return {
        "creator":   d.get("author", {}).get("nickname", "Unknown"),
        "title":     d.get("title", ""),
        "cover":     d.get("cover", ""),
        "video_url": d.get("play", "") or d.get("wmplay", ""),
        "audio_url": d.get("music", ""),
        "images":    imgs,
        "views":     d.get("play_count", 0),
        "likes":     d.get("digg_count", 0),
        "comments":  d.get("comment_count", 0),
    }

def _parse_hyper(d: dict) -> dict:
    det  = d.get("details", {})
    imgs = [i for i in det.get("images", []) if isinstance(i, str) and i.startswith("http")]
    return {
        "creator":   d.get("creator", "Unknown"),
        "title":     det.get("title", ""),
        "cover":     det.get("cover", {}).get("cover", ""),
        "video_url": det.get("video", {}).get("play", ""),
        "audio_url": det.get("audio", {}).get("play", ""),
        "images":    imgs,
        "views":     det.get("stats", {}).get("views", 0),
        "likes":     det.get("stats", {}).get("likes", 0),
        "comments":  det.get("stats", {}).get("comments", 0),
    }

# ==============================================================================
# ── 5. UI HELPERS ─────────────────────────────────────────────────────────────
# ==============================================================================
async def render_main_menu(uid: int, lang: str, name: str) -> tuple[str, InlineKeyboardMarkup]:
    badge = (
        tx(lang, "badge_owner") if is_owner(uid) else
        tx(lang, "badge_super") if is_super(uid) else
        tx(lang, "badge_admin") if is_admin(uid) else
        tx(lang, "badge_vip")   if is_vip(uid)   else ""
    )
    wm   = CFG.get("welcome_msg", "")
    text = (
        wm.replace("{name}", html.escape(name)).replace("{badge}", badge)
        if wm and not is_admin(uid)
        else tx(lang, "welcome", name=html.escape(name), badge=badge)
    )

    kb = [
        [InlineKeyboardButton(tx(lang, "b_dl"), callback_data="ask_link")],
        [InlineKeyboardButton(tx(lang, "b_profile"), callback_data="show_profile"),
         InlineKeyboardButton(tx(lang, "b_vip"),     callback_data="show_vip")],
        [InlineKeyboardButton(tx(lang, "b_settings"), callback_data="show_settings"),
         InlineKeyboardButton(tx(lang, "b_help"),     callback_data="show_help")],
        [InlineKeyboardButton(tx(lang, "b_channel"), url=CHANNEL_URL)],
    ]
    # Single unified panel button for any admin/super/owner
    if is_admin(uid):
        kb.append([InlineKeyboardButton(tx(lang, "b_panel"), callback_data="panel_unified")])

    return text, InlineKeyboardMarkup(kb)

def lang_select_buttons() -> list:
    return [[
        InlineKeyboardButton(L["ku"]["b_ku"], callback_data="set_lang_ku"),
        InlineKeyboardButton(L["en"]["b_en"], callback_data="set_lang_en"),
        InlineKeyboardButton(L["ar"]["b_ar"], callback_data="set_lang_ar"),
    ]]

def bot_lang_select_buttons() -> list:
    return [[
        InlineKeyboardButton(L["ku"]["b_ku"], callback_data="set_bot_lang_ku"),
        InlineKeyboardButton(L["en"]["b_en"], callback_data="set_bot_lang_en"),
        InlineKeyboardButton(L["ar"]["b_ar"], callback_data="set_bot_lang_ar"),
    ]]

# ==============================================================================
# ── 6. HANDLERS ───────────────────────────────────────────────────────────────
# ==============================================================================
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    user = update.effective_user
    lang = await get_user_lang(uid)

    if is_blocked(uid): return
    if CFG["maintenance"] and not is_admin(uid):
        await update.message.reply_text(tx(lang, "maintenance_msg", dev=DEV)); return

    is_new = not await user_exists(uid)
    if is_new:
        user_count = CFG.get("total_users", 0) + 1
        CFG["total_users"] = user_count
        await save_cfg()
        await user_put(uid, {
            "name": user.first_name,
            "user": user.username or "",
            "date": now_str(),
            "vip":  False,
            "dl":   0,
            "lang": CFG.get("default_lang", "ku"),
        })
        uname = f"@{user.username}" if user.username else "—"
        notify_text = tx("ku", "new_user_notify",
            name=html.escape(user.first_name),
            uname=uname,
            uid=uid,
            app_lang=user.language_code or "—",
            date=now_str()
        )
        # دوگمەکانی کۆنتڕۆڵ لەگەڵ ئاگادارکردنەوە
        notify_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(tx("ku", "b_notify_block"), callback_data=f"quick_blk_{uid}"),
                InlineKeyboardButton(tx("ku", "b_notify_vip"),   callback_data=f"quick_vip_{uid}"),
            ],
            [
                InlineKeyboardButton(tx("ku", "b_notify_admin"), callback_data=f"quick_adm_{uid}"),
                InlineKeyboardButton(tx("ku", "b_notify_info"),  callback_data=f"quick_inf_{uid}"),
            ],
        ])
        try: await ctx.bot.send_message(OWNER_ID, notify_text, parse_mode="HTML", reply_markup=notify_kb)
        except: pass

    ok_sub, missing = await check_join(uid, ctx)
    if not ok_sub and not bypass_join(uid):
        kb = [[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in missing]
        kb.append([InlineKeyboardButton(tx(lang, "b_joined"), callback_data="check_join_btn")])
        await update.message.reply_text(tx(lang, "force_join"), reply_markup=InlineKeyboardMarkup(kb)); return

    text, markup = await render_main_menu(uid, lang, user.first_name)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)

async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_owner(update.effective_user.id):
        await update.message.reply_text("✅ PONG! Bot is alive.")

# ── Main Callback Handler ──────────────────────────────────────────────────────
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    uid  = q.from_user.id
    lang = await get_user_lang(uid)

    try: await q.answer()
    except: pass

    # ── Quick actions from new user notification ───────────────────────────────
    if data.startswith("quick_") and is_owner(uid):
        parts  = data.split("_")
        action = parts[1]
        tid    = int(parts[2])
        olang  = "ku"  # Owner always sees Kurdish for quick actions

        if action == "blk":
            blocked_set.add(tid); await save_cfg()
            await q.answer(tx(olang, "act_blocked", id=tid), show_alert=True)
            return
        if action == "vip":
            vip_set.add(tid); await user_field(tid, "vip", True); await save_cfg()
            await q.answer(tx(olang, "act_vip_added", id=tid), show_alert=True)
            return
        if action == "adm":
            admins_set.add(tid); await save_cfg()
            await q.answer(tx(olang, "act_adm_added", id=tid), show_alert=True)
            return
        if action == "inf":
            ud = await user_get(tid)
            if not ud:
                await q.answer(tx(olang, "user_not_found"), show_alert=True); return
            ulang_str = LANG_NAMES.get(ud.get("lang", "—"), ud.get("lang", "—"))
            vip_str   = tx(olang, "vip_yes") if ud.get("vip") else tx(olang, "vip_no")
            info = tx(olang, "userinfo_text",
                name=ud.get("name","—"), user=ud.get("user","—"),
                id=tid, vip=vip_str, lang=ulang_str,
                dl=ud.get("dl", 0), date=ud.get("date","—")
            )
            await q.answer(info[:200], show_alert=True)
            return

    # ── Navigation ─────────────────────────────────────────────────────────────
    if data in ("main_menu_render", "check_join_btn"):
        ok_sub, _ = await check_join(uid, ctx)
        if not ok_sub and not bypass_join(uid): return
        text, markup = await render_main_menu(uid, lang, q.from_user.first_name)
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=markup); return

    if data == "close":
        try: await q.message.delete()
        except: pass
        return

    if data == "ask_link":
        await q.message.reply_text(tx(lang, "ask_link_prompt"), reply_markup=ForceReply(selective=True))
        return

    # ── Info Pages ─────────────────────────────────────────────────────────────
    if data == "show_profile":
        ud        = await user_get(uid) or {}
        ulang_key = ud.get("lang", CFG.get("default_lang", "ku"))
        ulang_str = LANG_NAMES.get(ulang_key, ulang_key)
        text = tx(lang, "profile",
            id=uid, name=html.escape(q.from_user.first_name),
            user=q.from_user.username or "—", date=ud.get("date", "—"),
            vip=tx(lang, "vip_yes") if is_vip(uid) else tx(lang, "vip_no"),
            ulang=ulang_str, dl=ud.get("dl", 0),
        )
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang))); return

    if data == "show_vip":
        await q.edit_message_text(tx(lang, "vip_info", dev=DEV), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang))); return

    if data == "show_help":
        await q.edit_message_text(tx(lang, "help", dev=DEV), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang))); return

    # ── Settings / Language (per-user) ─────────────────────────────────────────
    if data == "show_settings":
        cur  = LANG_NAMES.get(lang, "?")
        kb   = lang_select_buttons() + back(lang)
        await q.edit_message_text(
            tx(lang, "lang_title") + f"\n\n🔵 {cur}",
            reply_markup=InlineKeyboardMarkup(kb)
        ); return

    if data.startswith("set_lang_"):
        chosen = data.split("_")[2]
        await user_field(uid, "lang", chosen)
        text, markup = await render_main_menu(uid, chosen, q.from_user.first_name)
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=markup); return

    # ── Bot-wide language ──────────────────────────────────────────────────────
    if data.startswith("set_bot_lang_") and is_super(uid):
        chosen = data.split("_")[3]
        CFG["default_lang"] = chosen
        await save_cfg()
        await q.answer(tx(lang, "bot_lang_saved", lang=LANG_NAMES.get(chosen, chosen)), show_alert=True)
        q.data = "panel_unified"; await on_callback(update, ctx); return

    # ── Download ───────────────────────────────────────────────────────────────
    if data.startswith("dl_"):
        sess = await session_get(uid)
        if not sess: await q.answer(tx(lang, "session_expired"), show_alert=True); return

        cap    = f"🎬 {html.escape(sess.get('title',''))}\n👤 {html.escape(sess.get('creator',''))}\n\n🤖 @{ctx.bot.username}"
        del_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_delete"), callback_data="close")]])

        if data == "dl_photo":
            imgs = sess.get("images", [])
            if not imgs: await q.answer(tx(lang, "no_photo"), show_alert=True); return
            try: await q.message.delete()
            except: pass
            w = await ctx.bot.send_message(uid, tx(lang, "sending_photos"))
            for i in range(0, min(len(imgs), int(CFG.get("max_photos", 15))), 10):
                chunk = imgs[i:i+10]
                media = [InputMediaPhoto(u) for u in chunk]
                if i == 0: media[0].caption = cap; media[0].parse_mode = "HTML"
                try: await ctx.bot.send_media_group(uid, media)
                except:
                    for u in chunk:
                        try: await ctx.bot.send_photo(uid, u)
                        except: pass
                await asyncio.sleep(1)
            try: await w.delete()
            except: pass

        elif data == "dl_video":
            vurl = sess.get("video_url")
            if not vurl: await q.answer(tx(lang, "no_video"), show_alert=True); return
            try: await q.message.delete()
            except: pass
            try: await ctx.bot.send_video(uid, vurl, caption=cap, parse_mode="HTML", reply_markup=del_kb)
            except: await ctx.bot.send_message(uid, f"{cap}\n📥 <a href='{vurl}'>Link</a>", parse_mode="HTML", reply_markup=del_kb)

        elif data == "dl_audio":
            aurl = sess.get("audio_url")
            if not aurl: await q.answer(tx(lang, "no_audio"), show_alert=True); return
            try: await q.message.delete()
            except: pass
            try: await ctx.bot.send_audio(uid, aurl, caption=cap, parse_mode="HTML", title="TikTok Audio", performer="TikTok", reply_markup=del_kb)
            except: await ctx.bot.send_message(uid, f"{cap}\n🎵 <a href='{aurl}'>Link</a>", parse_mode="HTML", reply_markup=del_kb)

        CFG["total_dl"] = CFG.get("total_dl", 0) + 1
        await save_cfg()
        ud = await user_get(uid) or {}
        await user_field(uid, "dl", ud.get("dl", 0) + 1)
        return

    # ══════════════════════════════════════════════════════════════════════════
    # ── UNIFIED PANEL ─────────────────────────────────────────────────────────
    if data == "panel_unified":
        if not is_admin(uid): return
        uids_list = await all_uids()
        kb = []

        # Admin section (all admins see this)
        kb.append([
            InlineKeyboardButton(tx(lang, "b_adm_stats"),     callback_data="adm_stats"),
            InlineKeyboardButton(tx(lang, "b_adm_broadcast"), callback_data="adm_broadcast"),
        ])
        kb.append([
            InlineKeyboardButton(tx(lang, "b_adm_block"),   callback_data="adm_block"),
            InlineKeyboardButton(tx(lang, "b_adm_info"),    callback_data="adm_userinfo"),
        ])
        # Admins can also add admins (but not remove)
        kb.append([
            InlineKeyboardButton(tx(lang, "b_adm_admins"), callback_data="adm_manage_admins"),
        ])

        # Super section (super admins only)
        if is_super(uid):
            kb.append([InlineKeyboardButton("─── 🌌 Super ───", callback_data="noop")])
            kb.append([
                InlineKeyboardButton(tx(lang, "b_sup_vip"),      callback_data="sup_vips"),
                InlineKeyboardButton(tx(lang, "b_sup_channels"), callback_data="sup_channels"),
            ])
            maint_status = tx(lang, "sup_maint_on") if CFG["maintenance"] else tx(lang, "sup_maint_off")
            kb.append([
                InlineKeyboardButton(tx(lang, "b_sup_maint", status=maint_status), callback_data="sup_toggle_maint"),
                InlineKeyboardButton(tx(lang, "b_sup_api"),    callback_data="sup_api_settings"),
            ])
            kb.append([
                InlineKeyboardButton(tx(lang, "b_sup_botlang"), callback_data="sup_bot_lang"),
            ])

        # Owner section
        if is_owner(uid):
            kb.append([InlineKeyboardButton("─── 👑 Owner ───", callback_data="noop")])
            kb.append([
                InlineKeyboardButton(tx(lang, "b_own_super"),   callback_data="own_super_adms"),
                InlineKeyboardButton(tx(lang, "b_own_welcome"), callback_data="own_welcome"),
            ])
            kb.append([
                InlineKeyboardButton(tx(lang, "b_own_reset"),  callback_data="own_reset_stats"),
                InlineKeyboardButton(tx(lang, "b_own_backup"), callback_data="own_backup"),
            ])

        kb += back(lang)
        await q.edit_message_text(
            tx(lang, "unified_panel_title",
               users=len(uids_list), vip=len(vip_set),
               blocked=len(blocked_set), dl=fmt(CFG.get("total_dl", 0)),
               uptime=uptime()),
            reply_markup=InlineKeyboardMarkup(kb)
        ); return

    if data == "noop":
        return

    # ══════════════════════════════════════════════════════════════════════════
    # ── ADMIN SECTION ─────────────────────────────────────────────────────────
    if data.startswith("adm_"):
        if not is_admin(uid): return

        if data == "adm_stats":
            txt = tx(lang, "adm_stats_title",
                users=len(await all_uids()), vip=len(vip_set),
                blocked=len(blocked_set), dl=fmt(CFG.get("total_dl", 0)), uptime=uptime()
            )
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(tx(lang, "b_refresh"), callback_data="adm_stats")],
                 *back(lang, "panel_unified")]
            )); return

        if data == "adm_broadcast":
            waiting_state[uid] = "broadcast_all"
            await q.edit_message_text(
                tx(lang, "adm_broadcast_ask"),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_cancel"), callback_data="panel_unified")]])
            ); return

        if data == "adm_block":
            waiting_state[uid] = "action_blk_add"
            await q.edit_message_text(
                tx(lang, "adm_block_ask", write_id=tx(lang, "write_id")),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_cancel"), callback_data="panel_unified")]])
            ); return

        if data == "adm_userinfo":
            waiting_state[uid] = "action_info_check"
            await q.edit_message_text(
                tx(lang, "adm_info_ask", write_id=tx(lang, "write_id")),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_cancel"), callback_data="panel_unified")]])
            ); return

        # Admin manage admins — all admins can add, only super/owner can remove
        if data == "adm_manage_admins":
            adm_list = admins_set - {OWNER_ID}
            lines = []
            for aid in adm_list:
                display = await get_user_display(aid)
                lines.append(display)
            text = tx(lang, "sup_admins_title", count=len(adm_list))
            if lines:
                text += "\n" + "\n".join(f"• {l}" for l in lines)
            kb = [
                [InlineKeyboardButton(tx(lang, "b_add"), callback_data="sup_add_adm")],
            ]
            # Only super/owner can see remove button
            if is_super(uid):
                kb[0].append(InlineKeyboardButton(tx(lang, "b_remove"), callback_data="sup_rm_adm_list"))
            kb += back(lang, "panel_unified")
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb)); return

    # ══════════════════════════════════════════════════════════════════════════
    # ── SUPER SECTION ─────────────────────────────────────────────────────────
    if data.startswith("sup_"):
        if not is_super(uid): return

        if data == "sup_toggle_maint":
            CFG["maintenance"] = not CFG["maintenance"]; await save_cfg()
            q.data = "panel_unified"; await on_callback(update, ctx); return

        if data == "sup_bot_lang":
            cur = LANG_NAMES.get(CFG.get("default_lang", "ku"), "?")
            kb  = bot_lang_select_buttons() + back(lang, "panel_unified")
            await q.edit_message_text(
                tx(lang, "bot_lang_title") + "\n\n" + tx(lang, "bot_lang_current", cur=cur),
                reply_markup=InlineKeyboardMarkup(kb)
            ); return

        if data == "sup_api_settings":
            act = CFG.get("active_api", "auto")
            kb = [
                [InlineKeyboardButton(f"{'✅ ' if act=='auto'  else ''}Auto",      callback_data="sup_setapi_auto")],
                [InlineKeyboardButton(f"{'✅ ' if act=='tikwm' else ''}TikWM",     callback_data="sup_setapi_tikwm")],
                [InlineKeyboardButton(f"{'✅ ' if act=='hyper' else ''}Hyper API", callback_data="sup_setapi_hyper")],
                *back(lang, "panel_unified"),
            ]
            await q.edit_message_text(tx(lang, "sup_api_title"), reply_markup=InlineKeyboardMarkup(kb)); return

        if data.startswith("sup_setapi_"):
            CFG["active_api"] = data.split("_")[2]; await save_cfg()
            q.data = "sup_api_settings"; await on_callback(update, ctx); return

        # Add admin (accessible from adm_manage_admins too)
        if data == "sup_add_adm":
            waiting_state[uid] = "action_adm_add"
            await q.edit_message_text(
                tx(lang, "sup_add_adm_ask", write_id=tx(lang, "write_id")),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_cancel"), callback_data="adm_manage_admins")]])
            ); return

        # Remove admin — show list with confirm
        if data == "sup_rm_adm_list":
            adm_list = admins_set - super_admins_set - {OWNER_ID}
            if not adm_list:
                await q.answer("—", show_alert=True); return
            kb = []
            for aid in adm_list:
                display = await get_user_display(aid)
                kb.append([InlineKeyboardButton(f"❌ {display}", callback_data=f"sup_confirm_rm_adm_{aid}")])
            kb += back(lang, "adm_manage_admins")
            await q.edit_message_text(tx(lang, "sup_admins_title", count=len(adm_list)), reply_markup=InlineKeyboardMarkup(kb)); return

        if data.startswith("sup_confirm_rm_adm_"):
            tid = int(data.split("_")[4])
            await q.edit_message_text(
                tx(lang, "confirm_remove_admin", id=tid),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(tx(lang, "b_confirm_remove"), callback_data=f"sup_do_rm_adm_{tid}")],
                    [InlineKeyboardButton(tx(lang, "b_cancel_remove"),  callback_data="adm_manage_admins")],
                ])
            ); return

        if data.startswith("sup_do_rm_adm_"):
            tid = int(data.split("_")[4])
            admins_set.discard(tid); await save_cfg()
            await q.answer(tx(lang, "act_adm_removed", id=tid), show_alert=True)
            q.data = "adm_manage_admins"; await on_callback(update, ctx); return

        if data == "sup_vips":
            vip_real = vip_set - super_admins_set - {OWNER_ID}
            lines = []
            for vid in vip_real:
                display = await get_user_display(vid)
                lines.append(display)
            text = tx(lang, "sup_vip_title", count=len(vip_real))
            if lines:
                text += "\n" + "\n".join(f"• {l}" for l in lines)
            kb = [
                [InlineKeyboardButton(tx(lang, "b_add_vip"), callback_data="sup_add_vip"),
                 InlineKeyboardButton(tx(lang, "b_rm_vip"),  callback_data="sup_rm_vip_list")],
                *back(lang, "panel_unified"),
            ]
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb)); return

        if data == "sup_add_vip":
            waiting_state[uid] = "action_vip_add"
            await q.edit_message_text(
                tx(lang, "sup_add_vip_ask", write_id=tx(lang, "write_id")),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_cancel"), callback_data="sup_vips")]])
            ); return

        if data == "sup_rm_vip_list":
            vip_real = vip_set - super_admins_set - {OWNER_ID}
            if not vip_real:
                await q.answer(tx(lang, "sup_ch_empty"), show_alert=True); return
            kb = []
            for vid in vip_real:
                display = await get_user_display(vid)
                kb.append([InlineKeyboardButton(f"❌ {display}", callback_data=f"sup_confirm_rm_vip_{vid}")])
            kb += back(lang, "sup_vips")
            await q.edit_message_text(tx(lang, "sup_vip_title", count=len(vip_real)), reply_markup=InlineKeyboardMarkup(kb)); return

        if data.startswith("sup_confirm_rm_vip_"):
            vid = int(data.split("_")[4])
            await q.edit_message_text(
                tx(lang, "confirm_remove_admin", id=vid),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(tx(lang, "b_confirm_remove"), callback_data=f"sup_do_rm_vip_{vid}")],
                    [InlineKeyboardButton(tx(lang, "b_cancel_remove"),  callback_data="sup_vips")],
                ])
            ); return

        if data.startswith("sup_do_rm_vip_"):
            vid = int(data.split("_")[4])
            vip_set.discard(vid); await user_field(vid, "vip", False); await save_cfg()
            await q.answer(tx(lang, "act_vip_removed", id=vid), show_alert=True)
            q.data = "sup_vips"; await on_callback(update, ctx); return

        if data == "sup_channels":
            lst_lines = []
            for ch in channels_list:
                lst_lines.append(f"• {ch}")
            text = tx(lang, "sup_ch_title", count=len(channels_list))
            if lst_lines:
                text += "\n" + "\n".join(lst_lines)
            else:
                text += f"\n{tx(lang, 'sup_ch_empty')}"
            kb = [
                [InlineKeyboardButton(tx(lang, "b_add"),    callback_data="sup_add_ch"),
                 InlineKeyboardButton(tx(lang, "b_remove"), callback_data="sup_rm_ch_list")],
                *back(lang, "panel_unified"),
            ]
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb)); return

        if data == "sup_add_ch":
            waiting_state[uid] = "action_add_ch"
            await q.edit_message_text(
                tx(lang, "sup_add_ch_ask", write_ch=tx(lang, "write_ch")),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_cancel"), callback_data="sup_channels")]])
            ); return

        if data == "sup_rm_ch_list":
            if not channels_list: await q.answer(tx(lang, "sup_ch_empty"), show_alert=True); return
            kb = [[InlineKeyboardButton(f"❌ {c}", callback_data=f"sup_confirm_rm_ch_{c}")] for c in channels_list]
            kb += back(lang, "sup_channels")
            await q.edit_message_text(tx(lang, "sup_ch_remove_q"), reply_markup=InlineKeyboardMarkup(kb)); return

        if data.startswith("sup_confirm_rm_ch_"):
            ch = data[len("sup_confirm_rm_ch_"):]
            await q.edit_message_text(
                tx(lang, "confirm_remove_ch", ch=ch),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(tx(lang, "b_confirm_remove"), callback_data=f"sup_do_rm_ch_{ch}")],
                    [InlineKeyboardButton(tx(lang, "b_cancel_remove"),  callback_data="sup_channels")],
                ])
            ); return

        if data.startswith("sup_do_rm_ch_"):
            ch = data[len("sup_do_rm_ch_"):]
            if ch in channels_list: channels_list.remove(ch); await save_cfg()
            q.data = "sup_channels"; await on_callback(update, ctx); return

    # ══════════════════════════════════════════════════════════════════════════
    # ── OWNER SECTION ─────────────────────────────────────────────────────────
    if data.startswith("own_"):
        if not is_owner(uid): return

        if data == "own_super_adms":
            sup_real = super_admins_set - {OWNER_ID}
            lines = []
            for sid in sup_real:
                display = await get_user_display(sid)
                lines.append(display)
            text = tx(lang, "own_super_title", count=len(sup_real))
            if lines:
                text += "\n" + "\n".join(f"• {l}" for l in lines)
            kb = [
                [InlineKeyboardButton(tx(lang, "b_add"),    callback_data="own_add_sup"),
                 InlineKeyboardButton(tx(lang, "b_remove"), callback_data="own_rm_sup_list")],
                *back(lang, "panel_unified"),
            ]
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb)); return

        if data == "own_add_sup":
            waiting_state[uid] = "action_sup_add"
            await q.edit_message_text(
                tx(lang, "own_add_sup_ask", write_id=tx(lang, "write_id")),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_cancel"), callback_data="own_super_adms")]])
            ); return

        if data == "own_rm_sup_list":
            sup_real = super_admins_set - {OWNER_ID}
            if not sup_real:
                await q.answer("—", show_alert=True); return
            kb = []
            for sid in sup_real:
                display = await get_user_display(sid)
                kb.append([InlineKeyboardButton(f"❌ {display}", callback_data=f"own_confirm_rm_sup_{sid}")])
            kb += back(lang, "own_super_adms")
            await q.edit_message_text(tx(lang, "own_super_title", count=len(sup_real)), reply_markup=InlineKeyboardMarkup(kb)); return

        if data.startswith("own_confirm_rm_sup_"):
            sid = int(data.split("_")[4])
            await q.edit_message_text(
                tx(lang, "confirm_remove_super", id=sid),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(tx(lang, "b_confirm_remove"), callback_data=f"own_do_rm_sup_{sid}")],
                    [InlineKeyboardButton(tx(lang, "b_cancel_remove"),  callback_data="own_super_adms")],
                ])
            ); return

        if data.startswith("own_do_rm_sup_"):
            sid = int(data.split("_")[4])
            super_admins_set.discard(sid); await save_cfg()
            await q.answer(tx(lang, "act_sup_removed", id=sid), show_alert=True)
            q.data = "own_super_adms"; await on_callback(update, ctx); return

        if data == "own_welcome":
            waiting_state[uid] = "set_welcome"
            await q.edit_message_text(
                tx(lang, "write_welcome"),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(tx(lang, "b_clear"), callback_data="own_clear_welcome")],
                    *back(lang, "panel_unified"),
                ])
            ); return

        if data == "own_clear_welcome":
            CFG["welcome_msg"] = ""; await save_cfg()
            q.data = "panel_unified"; await on_callback(update, ctx); return

        if data == "own_reset_stats":
            for k in ("total_dl", "total_users"): CFG[k] = 0
            await save_cfg(); await q.answer(tx(lang, "own_reset_done"), show_alert=True); return

        if data == "own_backup":
            await q.answer(tx(lang, "own_backup_prep"), show_alert=False)
            bdata = {"time": now_str(), "cfg": CFG, "users": await all_users_data()}
            bio   = io.BytesIO(json.dumps(bdata, ensure_ascii=False, indent=2).encode())
            bio.name = f"Backup_{now_str()}.json"
            try: await ctx.bot.send_document(uid, bio)
            except: pass
            return

# ── Message Handler ────────────────────────────────────────────────────────────
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid  = update.effective_user.id
    msg  = update.message
    txt  = msg.text or ""
    lang = await get_user_lang(uid)

    # ── Waiting State ──────────────────────────────────────────────────────────
    if uid in waiting_state:
        state = waiting_state.pop(uid)

        if state == "set_welcome":
            CFG["welcome_msg"] = txt; await save_cfg()
            await msg.reply_text(tx(lang, "welcome_set")); return

        if state.startswith("broadcast_"):
            all_u = await all_uids(); ok = fail = 0
            st = await msg.reply_text(tx(lang, "broadcast_sending", total=len(all_u)))
            for i, t in enumerate(all_u):
                try:
                    await ctx.bot.copy_message(chat_id=t, from_chat_id=msg.chat_id, message_id=msg.message_id)
                    ok += 1; await asyncio.sleep(0.04)
                except: fail += 1
                if i % 100 == 0 and i > 0:
                    try: await st.edit_text(tx(lang, "broadcast_progress", done=i, total=len(all_u)))
                    except: pass
            await st.edit_text(tx(lang, "broadcast_done", ok=ok, fail=fail)); return

        if state.startswith("action_"):
            action = state[len("action_"):]

            if action == "add_ch":
                ch = txt.strip()
                if not ch.startswith("@") or len(ch) < 3:
                    await msg.reply_text(tx(lang, "act_ch_wrong_fmt")); return
                if ch not in channels_list:
                    channels_list.append(ch); await save_cfg()
                await msg.reply_text(tx(lang, "sup_ch_added", ch=ch)); return

            if not txt.strip().isdigit():
                await msg.reply_text(tx(lang, "invalid_id")); return
            tid = int(txt.strip())

            if action == "blk_add":
                blocked_set.add(tid); await save_cfg()
                await msg.reply_text(tx(lang, "act_blocked", id=tid))
            elif action == "info_check":
                ud = await user_get(tid)
                if not ud: await msg.reply_text(tx(lang, "user_not_found")); return
                ulang_str = LANG_NAMES.get(ud.get("lang", "—"), ud.get("lang", "—"))
                vip_str   = tx(lang, "vip_yes") if ud.get("vip") else tx(lang, "vip_no")
                await msg.reply_text(tx(lang, "userinfo_text",
                    name=ud.get("name","—"), user=ud.get("user","—"),
                    id=tid, vip=vip_str, lang=ulang_str,
                    dl=ud.get("dl", 0), date=ud.get("date","—")
                ))
            elif action == "adm_add":
                if not is_super(uid):
                    # Regular admins can add admins (but not super admins)
                    admins_set.add(tid); await save_cfg()
                    await msg.reply_text(tx(lang, "act_adm_added", id=tid))
                else:
                    admins_set.add(tid); await save_cfg()
                    await msg.reply_text(tx(lang, "act_adm_added", id=tid))
            elif action == "sup_add":
                super_admins_set.add(tid); admins_set.add(tid); await save_cfg()
                await msg.reply_text(tx(lang, "act_sup_added", id=tid))
            elif action == "vip_add":
                vip_set.add(tid); await user_field(tid, "vip", True); await save_cfg()
                await msg.reply_text(tx(lang, "act_vip_added", id=tid))
            elif action == "vip_rm":
                vip_set.discard(tid); await user_field(tid, "vip", False); await save_cfg()
                await msg.reply_text(tx(lang, "act_vip_removed", id=tid))
            return

    # ── TikTok Link ────────────────────────────────────────────────────────────
    if is_blocked(uid): return
    if CFG["maintenance"] and not is_admin(uid):
        await msg.reply_text(tx(lang, "maintenance_msg", dev=DEV)); return
    if not any(x in txt for x in ("tiktok.com", "vm.tiktok", "vt.tiktok")): return

    ok_sub, missing = await check_join(uid, ctx)
    if not ok_sub and not bypass_join(uid):
        kb = [[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in missing]
        kb.append([InlineKeyboardButton(tx(lang, "b_joined"), callback_data="check_join_btn")])
        await msg.reply_text(tx(lang, "force_join"), reply_markup=InlineKeyboardMarkup(kb)); return

    async def animated_progress(status_msg):
        frames = [
            "⬜⬜⬜⬜⬜",
            "⬛⬜⬜⬜⬜",
            "⬛⬛⬜⬜⬜",
            "⬛⬛⬛⬜⬜",
            "⬛⬛⬛⬛⬜",
            "⬛⬛⬛⬛⬛",
        ]
        for frame in frames:
            try: await status_msg.edit_text(f"🔍 {frame}")
            except: pass
            await asyncio.sleep(0.4)

    status = await msg.reply_text("🔍 ⬜⬜⬜⬜⬜")
    progress_task = asyncio.create_task(animated_progress(status))

    try:
        data = await fetch_tiktok(txt)
        progress_task.cancel()
        if not data:
            await status.edit_text(tx(lang, "invalid_link")); return

        await session_save(uid, data)
        photo_post = len(data["images"]) > 0

        caption = tx(lang, "found",
            title=html.escape(clean_title(data["title"])),
            owner=html.escape(data["creator"]),
            views=fmt(data["views"]),
            likes=fmt(data["likes"]),
            comments=fmt(data["comments"]),
        )
        audio_cap = f"🎵 {html.escape(clean_title(data['title']))}\n👤 {html.escape(data['creator'])}"

        try: await status.delete()
        except: pass

        if photo_post:
            # Photo post: send photos then audio
            imgs = data["images"]
            w = await ctx.bot.send_message(uid, tx(lang, "sending_photos"))
            for i in range(0, min(len(imgs), int(CFG.get("max_photos", 15))), 10):
                chunk = imgs[i:i+10]
                media = [InputMediaPhoto(u) for u in chunk]
                if i == 0: media[0].caption = caption; media[0].parse_mode = "HTML"
                try: await ctx.bot.send_media_group(uid, media)
                except:
                    for u in chunk:
                        try: await ctx.bot.send_photo(uid, u)
                        except: pass
                await asyncio.sleep(1)
            try: await w.delete()
            except: pass
        else:
            # Video post: send video with caption, no delete button
            vurl = data.get("video_url")
            if vurl:
                try: await ctx.bot.send_video(uid, vurl, caption=caption, parse_mode="HTML")
                except: await ctx.bot.send_message(uid, f"{caption}\n📥 <a href='{vurl}'>Link</a>", parse_mode="HTML")
            else:
                await ctx.bot.send_message(uid, caption, parse_mode="HTML")

        # Send audio without caption and without delete button
        aurl = data.get("audio_url")
        if aurl:
            try: await ctx.bot.send_audio(uid, aurl, title="TikTok Audio", performer="TikTok")
            except: pass

        CFG["total_dl"] = CFG.get("total_dl", 0) + 1
        await save_cfg()
        ud = await user_get(uid) or {}
        await user_field(uid, "dl", ud.get("dl", 0) + 1)

    except Exception as e:
        progress_task.cancel()
        log.error(f"Download Error: {e}")
        try: await status.edit_text(tx(lang, "dl_fail"))
        except: pass

# ==============================================================================
# ── 7. FASTAPI WEBHOOK ────────────────────────────────────────────────────────
# ==============================================================================
_token = TOKEN if TOKEN != "DUMMY_TOKEN" else "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
ptb = ApplicationBuilder().token(_token).build()
ptb.add_handler(CommandHandler(["start", "menu"], cmd_start))
ptb.add_handler(CommandHandler("ping", cmd_ping))
ptb.add_handler(CallbackQueryHandler(on_callback))
ptb.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))

@app.post("/api/main")
async def webhook(req: Request):
    if TOKEN == "DUMMY_TOKEN" or not TOKEN:
        return {"ok": False, "error": "BOT_TOKEN IS MISSING"}
    try:
        body = await req.json()
        if not ptb.running: await ptb.initialize()
        await load_cfg(force=False)
        await ptb.process_update(Update.de_json(body, ptb.bot))
        return {"ok": True}
    except Exception as e:
        log.error(f"WEBHOOK ERROR: {traceback.format_exc()}")
        try:
            await ptb.bot.send_message(
                OWNER_ID,
                f"⚠️ Critical Error on Vercel:\n\n{html.escape(str(e))}",
                parse_mode="HTML"
            )
        except: pass
        return {"ok": False, "error": str(e)}

@app.get("/api/main")
async def health_check():
    t = "✅ Set" if TOKEN and TOKEN != "DUMMY_TOKEN" else "❌ Missing"
    d = "✅ Set" if DB_URL    else "❌ Missing"
    s = "✅ Set" if DB_SECRET else "❌ Missing"
    html_content = f"""
    <html><head><title>JackTik Bot</title>
    <style>
        body{{font-family:Arial;background:#f4f4f9;padding:40px;direction:rtl;text-align:right}}
        .box{{background:#fff;padding:24px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,.1);max-width:560px;margin:0 auto}}
        li{{padding:10px 0;border-bottom:1px solid #eee;font-size:17px}}
    </style></head>
    <body><div class="box">
        <h2>🤖 JackTik Bot — System Check</h2>
        <ul>
            <li>BOT_TOKEN: {t}</li>
            <li>DB_URL: {d}</li>
            <li>DB_SECRET: {s}</li>
        </ul>
        <p style="color:red">ئەگەر ❌ بوو، بڕۆ Vercel → Settings → Environment Variables</p>
    </div></body></html>
    """
    return HTMLResponse(content=html_content)
