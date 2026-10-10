# ╔══════════════════════════════════════════════════════════════════════════╗
# ║   JackTik  ·  TikTok Downloader Bot for Telegram                         ║
# ║   Version : v15.0 (Pro)         Stack : FastAPI · PTB 21 · Firebase      ║
# ║   Owner   : @j4ck_721s          Deploy: Vercel (Python serverless)       ║
# ╚══════════════════════════════════════════════════════════════════════════╝
"""
JackTik v15 — TikTok downloader bot (Telegram webhook, Vercel serverless).

What changed in v15 (short version)
  • Media is DOWNLOADED by the bot and UPLOADED to Telegram (v14 handed the
    TikTok CDN URL to Telegram, which fails for a large share of videos/audio).
  • Robust URL extraction, TikWM rate-limit retry, HD preference, size limits,
    multiple candidate URLs per media, and a clean "too big" fallback.
  • Serverless-safe state (Firebase instead of in-memory), atomic counters,
    one HTTP client per invocation, per-user lock, duplicate-update guard.
  • Fixed crashes: PTB objects are immutable (`q.data = ...` raised), callback
    queries were answered twice, silent bare `except:` everywhere.
  • Optional webhook secret verification (WEBHOOK_SECRET).
  • Fully redesigned messages and menus (HTML, ku / en / ar).
"""

import asyncio
import hashlib
import hmac
import html
import io
import json
import logging
import os
import re
import time
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from telegram import (
    ForceReply,
    InlineKeyboardButton as Btn,
    InlineKeyboardMarkup as Kb,
    InputFile,
    InputMediaPhoto,
    Update,
)
from telegram.constants import ChatAction, ChatMemberStatus, ParseMode
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)

# ══════════════════════════════════════════════════════════════════════════════
# 1 · CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


TOKEN          = os.getenv("BOT_TOKEN", "").strip()
DB_URL         = (os.getenv("DB_URL", "") or "").strip().rstrip("/")
DB_SECRET      = os.getenv("DB_SECRET", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()      # optional but recommended

# ⚠️  Set OWNER_ID in Vercel → Environment Variables to YOUR Telegram numeric ID.
#     The default below is the original developer's ID and gets full owner rights.
OWNER_ID       = _int_env("OWNER_ID", 5977475208)
DEV            = os.getenv("DEV_USERNAME", "@j4ck_721s")
CHANNEL_URL    = os.getenv("CHANNEL_URL", "https://t.me/jack_721_mod")
BOT_USERNAME   = os.getenv("BOT_USERNAME", "TikTok_Downloader_Jack_Robot").lstrip("@")

# Secret story viewer — optional extra provider. Use {username} as the placeholder, e.g.
#   STORY_API_URL     = https://your-provider.example/tiktok/story?username={username}
#   STORY_API_HEADERS = {"x-api-key": "..."}        (JSON, optional)
STORY_API_URL     = os.getenv("STORY_API_URL", "").strip()
STORY_API_HEADERS = os.getenv("STORY_API_HEADERS", "").strip()
STORY_MAX         = 40               # newest stories per request (VIP: STORY_MAX_VIP)
STORY_MAX_VIP     = 80
STORY_PAGES       = 8                # max provider pages fetched per username

START_TIME     = time.time()
SESSION_TTL    = 3600                # seconds an audio/"again" session stays valid
WAIT_TTL       = 600                 # seconds an admin "type the ID" prompt stays valid
LOCK_TTL       = 90                  # seconds a per-user download lock lives
CFG_TTL        = 20                  # seconds between config reloads per instance
FUNC_BUDGET    = 52                  # seconds we allow ourselves (vercel maxDuration = 60)
TG_MAX_BYTES   = 49_000_000          # Telegram bot upload limit is 50 MB
TG_PHOTO_MAX   = 10_000_000          # photo limit for sendPhoto

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("jacktik")
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# In-memory cache of the shared config (reloaded from Firebase every CFG_TTL s)
super_admins_set: set  = {OWNER_ID}
admins_set:       set  = {OWNER_ID}
channels_list:    list = []
blocked_set:      set  = set()
vip_set:          set  = set()
last_cfg_load:    float = 0.0

CFG: dict = {
    "maintenance":  False,
    "welcome_msg":  "",
    "default_lang": "ku",
    "max_photos":   15,
    "vip_photos":   35,
    "api_timeout":  40,
    "vip_bypass":   True,
    "admin_bypass": True,
    "total_dl":     0,
    "total_users":  0,
    "active_api":   "auto",
    "auto_audio":   False,
}

# ══════════════════════════════════════════════════════════════════════════════
# 2 · LANGUAGES  (Sorani Kurdish · English · Arabic)
#     Every message is HTML.  Dynamic values are escaped before formatting.
# ══════════════════════════════════════════════════════════════════════════════
L: dict = {}

L["ku"] = {
    # ── user-facing ───────────────────────────────────────────────────────────
    "welcome": (
        "✨ <b>بەخێربێیت، {name}</b> {badge}\n\n"
        "بە یەک لینک، ڤیدیۆ و وێنە و گۆرانییەکانی <b>تیکتۆک</b> دابەزێنە — "
        "<b>بێ لۆگۆ</b> و بە کوالێتی بەرز.\n\n"
        "<blockquote>🎬  ڤیدیۆی HD بێ واتەرمارک\n"
        "🖼  هەموو وێنەکانی پۆستەکە\n"
        "🎵  گۆرانی بە فۆرماتی MP3</blockquote>\n"
        "👇 <b>لینکی تیکتۆکەکە بنێرە</b> و چەند چرکەیەک چاوەڕێ بکە."
    ),
    "help": (
        "<b>📖 ڕێنمایی بەکارهێنان</b>\n\n"
        "<b>١</b> · لە تیکتۆک دوگمەی <b>Share</b> دابگرە و <b>Copy link</b> هەڵبژێرە.\n"
        "<b>٢</b> · لینکەکە لێرە پەیست بکە و بینێرە.\n"
        "<b>٣</b> · چەند چرکەیەک چاوەڕێ بکە — ئامادەیە ⚡\n\n"
        "<blockquote>🎬 ڤیدیۆ — بێ لۆگۆ و بە کوالێتی بەرز\n"
        "🖼 وێنە — هەموو وێنەکانی پۆستەکە وەک ئەلبوم\n"
        "🎵 گۆرانی — دوگمەی <b>MP3</b> لە ژێر ڤیدیۆکە\n"
        "👤 پرۆفایل — یوزەرنەیمێک بنێرە بۆ وەرگرتنی وێنەی پرۆفایل بە HD\n"
        "🕵️ ستۆری — دوگمەی <b>ستۆری نهێنی</b> دابگرە و یوزەرنەیمێک بنێرە</blockquote>\n"
        "💎 <b>VIP</b> — بێ جۆینی ناچاری و وێنەی زیاتر.\n"
        "📩 پەیوەندی: {dev}"
    ),
    "profile": (
        "<b>👤 پرۆفایلی من</b>\n\n"
        "<blockquote>🆔 ئایدی: <code>{id}</code>\n"
        "✨ ناو: {name}\n"
        "🔗 یوزەرنەیم: {user}\n"
        "🏅 پلە: {rank}\n"
        "🌐 زمان: {ulang}\n"
        "📥 دابەزاندن: <b>{dl}</b>\n"
        "📅 بەشداربوون: {date}</blockquote>"
    ),
    "vip_info": (
        "<b>💎 بەشی VIP</b>\n\n"
        "<blockquote>✅ بێ جۆینی ناچاری\n"
        "✅ ژمارەی وێنەی زیاتر لە هەر پۆستێک\n"
        "✅ پشتگیری تایبەت</blockquote>\n"
        "🛒 بۆ کڕینی VIP پەیوەندی بکە بە {dev}"
    ),
    "rank_owner": "👑 خاوەن", "rank_super": "🌌 سوپەر ئەدمین", "rank_admin": "🛡 ئەدمین",
    "rank_vip": "💎 VIP", "rank_user": "👤 بەکارهێنەر",
    "lang_title": "🌐 <b>زمانی خۆت هەڵبژێرە</b>",
    "lang_current": "🔵 ئێستا: {cur}",
    "lang_saved": "✅ زمانەکە گۆڕدرا",
    "force_join": (
        "🔒 <b>جۆینی ناچاری</b>\n\n"
        "بۆ بەردەوامبوون، سەرەتا ئەم چەناڵانە جۆین بکە، پاشان دوگمەی "
        "<b>«جۆینم کرد»</b> دابگرە 👇"
    ),
    "not_joined": "⚠️ هێشتا هەموو چەناڵەکانت جۆین نەکردووە!",
    "st_search": "🔎 <b>گەڕان بۆ لینکەکە…</b>\n{bar}",
    "st_download": "⬇️ <b>دابەزاندن…</b>\n{bar}",
    "st_upload": "📤 <b>ناردن بۆ تێلەگرام…</b>\n{bar}",
    "st_audio": "🎵 <b>گۆرانییەکە ئامادە دەکرێت…</b>\n{bar}",
    "blocked_msg": "⛔ <b>بلۆک کراویت</b>\nناتوانیت ئەم بۆتە بەکاربێنیت.",
    "maintenance_msg": (
        "🛠 <b>چاکسازی</b>\n\n"
        "بۆتەکە لە ژێر نوێکردنەوەدایە و زوو دەگەڕێتەوە ⏳\n"
        "📩 {dev}"
    ),
    "busy_msg": "⏳ داواکارییەکەی پێشووت هێشتا تەواو نەبووە — چەند چرکەیەک چاوەڕێ بکە.",
    "session_expired": "⚠️ کاتەکە بەسەرچوو — لینکەکە دووبارە بنێرە.",
    "invalid_link": (
        "❌ <b>لینکەکە نەدۆزرایەوە</b>\n\n"
        "دڵنیابە لینکەکە دروستە و پۆستەکە تایبەت (Private) نییە، پاشان دووبارە هەوڵبدەرەوە."
    ),
    "not_link": (
        "🔗 تکایە <b>لینکی تیکتۆک</b> یان <b>یوزەرنەیمێک</b> بنێرە.\n"
        "نموونە: <code>https://vm.tiktok.com/xxxxxxx</code> یان <code>@username</code>"
    ),
    "dl_fail": "❌ <b>دابەزاندن سەرکەوتوو نەبوو</b>\nتکایە دوای چەند چرکەیەک دووبارە هەوڵبدەرەوە.",
    "no_photo": "❌ ئەم پۆستە وێنەی تێدا نییە!",
    "no_video": "❌ ڤیدیۆکە نەدۆزرایەوە!",
    "no_audio": "❌ گۆرانییەکە بەردەست نییە!",
    "too_big": (
        "⚠️ <b>فایلەکە زۆر گەورەیە</b> بۆ تێلەگرام (زیاتر لە ٥٠ مێگابایت).\n"
        "لە دوگمەی خوارەوە ڕاستەوخۆ دایبەزێنە 👇"
    ),
    "photos_done": "🖼 <b>{n} وێنە</b> ئامادەیە ✅",
    "ask_link_prompt": "🔗 <b>لینکی تیکتۆکەکە بنێرە:</b>",
    "ask_avatar_prompt": "👤 <b>یوزەرنەیمی تیکتۆک بنێرە:</b>\nنموونە: <code>@username</code>",
    "avatar_caption": "👤 <b>وێنەی پرۆفایلی @{user}</b>\n\n⚡ <a href=\"https://t.me/{bot}\">@{bot}</a>",
    "no_avatar": "❌ وێنەی پرۆفایل نەدۆزرایەوە! ڕەنگە ئەکاونتەکە تایبەت بێت یان بوونی نەبێت.",
    "private_account": "🔒 <b>ئەم ئەکاونتە تایبەتییە!</b>\nتەنیا ئەکاونتی گشتی پشتگیری دەکرێت.",
    "st_avatar": "👤 <b>وێنەی پرۆفایل ئامادە دەکرێت…</b>\n{bar}",
    # ── secret story viewer ───────────────────────────────────────────────────
    "ask_story_prompt": "🕵️ <b>بینینی ستۆری نهێنی</b>\n\nیوزەرنەیمی تیکتۆکی کەسەکە بنێرە:\nنموونە: <code>@username</code>",
    "st_story": "🕵️ <b>بە نهێنی دەگەڕێم بۆ ستۆرییەکان…</b>\n{bar}",
    "story_header": (
        "🕵️ <b>ستۆری نهێنی · @{user}</b>\n\n"
        "<blockquote>📖 ستۆری چالاک: <b>{n}</b>\n"
        "🎬 ڤیدیۆ: <b>{v}</b>   🖼 وێنە: <b>{p}</b>\n"
        "👻 بێ شوێنپێ — لە لیستی بینەران دەرناکەویت</blockquote>"
    ),
    "story_caption": "🕵️ <b>@{user}</b> · ستۆری <b>{i}/{n}</b>\n🕒 {when}\n\n⚡ <a href=\"https://t.me/{bot}\">@{bot}</a>",
    "story_done": "✅ <b>{n} ستۆری</b> نێردرا 👻",
    "story_partial": "⏱ کاتەکە تەواو بوو — <b>{n}</b> ستۆری نێردرا، <b>{left}</b> ماوە. دوگمەی خوارەوە دابگرە بۆ بەردەوامبوون.",
    "b_story_more": "▶️ بەردەوامبە ({left} ماوە)",
    "story_expired": "⌛ ئەم بەردەوامبوونە بەسەرچووە. دووبارە داوای ستۆری بکەرەوە.",
    "no_story": "📭 <b>@{user}</b> ئێستا ستۆری چالاکی نییە.\nستۆری تیکتۆک ٢٤ کاتژمێر دەمێنێتەوە.",
    "story_unavailable": "⚠️ ستۆری ئەم ئەکاونتە بەردەست نییە (ڕەنگە تایبەت بێت یان سەرچاوەکە پشتگیری نەکات).",
    "b_story": "🕵️ ستۆری نهێنی", "b_story_again": "🔄 ستۆری کەسێکی تر",
    # ── buttons ───────────────────────────────────────────────────────────────
    "b_dl": "📥 دابەزاندنی نوێ", "b_profile": "👤 پرۆفایل", "b_vip": "💎 VIP", "b_avatar": "🖼 وێنەی پرۆفایل",
    "b_lang": "🌐 زمان", "b_help": "📖 ڕێنمایی", "b_channel": "📢 کەناڵی بۆت",
    "b_panel": "🛠 پانێڵی کۆنتڕۆڵ", "b_back": "🔙 گەڕانەوە", "b_delete": "🗑 سڕینەوە",
    "b_joined": "✅ جۆینم کرد", "b_audio": "🎵 گۆرانی MP3", "b_orig": "🔗 لینکی ڕەسەن",
    "b_direct": "⬇️ دابەزاندنی ڕاستەوخۆ", "b_cancel": "✖️ هەڵوەشاندنەوە",
    "b_confirm": "✅ بەڵێ، دڵنیام", "b_deny": "✖️ نەخێر", "b_refresh": "🔄 نوێکردنەوە",
    "b_clear": "🧹 پاککردنەوە", "b_add": "➕ زیادکردن", "b_remove": "➖ سڕینەوە",
    "b_add_vip": "➕ VIP", "b_rm_vip": "➖ VIP",
    "on": "🟢 چالاک", "off": "🔴 ناچالاک",
    # ── admin panel ───────────────────────────────────────────────────────────
    "panel_title": (
        "🛠 <b>پانێڵی کۆنتڕۆڵ</b>\n\n"
        "<blockquote>👥 بەکارهێنەران: <b>{users}</b>\n"
        "💎 VIP: <b>{vip}</b>\n"
        "🚫 بلۆککراو: <b>{blocked}</b>\n"
        "📥 دابەزاندن: <b>{dl}</b></blockquote>"
    ),
    "adm_stats": (
        "📊 <b>ئامارەکان</b>\n\n"
        "<blockquote>👥 کۆی بەکارهێنەران: <b>{users}</b>\n"
        "💎 VIP: <b>{vip}</b>\n"
        "🚫 بلۆککراو: <b>{blocked}</b>\n"
        "🛡 ئەدمین: <b>{admins}</b>\n"
        "📢 چەناڵی ناچاری: <b>{channels}</b>\n"
        "📥 کۆی دابەزاندن: <b>{dl}</b>\n"
        "🛠 چاکسازی: {maint}\n"
        "⚙️ سەرچاوە: <b>{api}</b></blockquote>"
    ),
    "b_adm_stats": "📊 ئامار", "b_adm_broadcast": "📢 برۆدکاست", "b_adm_block": "🚫 بلۆککردن",
    "b_adm_unblock": "✅ لابردنی بلۆک", "b_adm_info": "🔎 زانیاری کەس",
    "b_sup_admins": "👮 ئەدمینەکان", "b_sup_vip": "💎 VIP", "b_sup_channels": "📢 چەناڵەکان",
    "b_sup_maint": "🛠 چاکسازی: {status}", "b_sup_api": "⚙️ سەرچاوەی API",
    "b_sup_botlang": "🌍 زمانی بۆت", "b_sup_audio": "🎵 گۆرانی خۆکار: {status}",
    "b_own_super": "🌌 سوپەر ئەدمینەکان", "b_own_welcome": "📝 نامەی بەخێرهاتن",
    "b_own_reset": "♻️ سفرکردنەوەی ئامار", "b_own_backup": "💾 باکئەپ",
    "adm_broadcast_ask": "✍️ <b>پەیامەکەت بنێرە</b>\n(دەق، وێنە، ڤیدیۆ یان هەر شتێک):",
    "adm_block_ask": "🚫 <b>بلۆککردنی بەکارهێنەر</b>\n\n{write_id}",
    "adm_unblock_ask": "✅ <b>لابردنی بلۆک</b>\n\n{write_id}",
    "adm_info_ask": "🔎 <b>زانیاری بەکارهێنەر</b>\n\n{write_id}",
    "write_id": "✍️ ئایدی ژمارەییەکەی بنووسە و بینێرە:",
    "write_ch": "✍️ یوزەرنەیمی چەناڵ بنووسە (نموونە: <code>@mychannel</code>):",
    "write_welcome": (
        "✍️ <b>نامەی بەخێرهاتن بنووسە</b>\n"
        "دەتوانیت <code>{name}</code> و <code>{badge}</code> بەکاربێنیت.\n"
        "فۆرماتی تێلەگرام (Bold و…) پاڵپشتی دەکرێت."
    ),
    "userinfo": (
        "🔎 <b>زانیاری بەکارهێنەر</b>\n\n"
        "<blockquote>✨ ناو: {name}\n🔗 یوزەر: {user}\n🆔 ئایدی: <code>{id}</code>\n"
        "🏅 پلە: {rank}\n🚫 بلۆک: {blocked}\n🌐 زمان: {lang}\n"
        "📥 دابەزاندن: <b>{dl}</b>\n📅 بەشداربوون: {date}</blockquote>"
    ),
    "yes": "بەڵێ", "no": "نەخێر",
    "broadcast_start": "⏳ ناردن دەستی پێکرد بۆ <b>{total}</b> کەس…",
    "broadcast_progress": "⏳ ناردن: <b>{done}</b> / {total}",
    "broadcast_done": "📢 <b>برۆدکاست تەواو بوو</b>\n\n✅ گەیشت: <b>{ok}</b>\n❌ نەگەیشت: <b>{fail}</b>",
    "broadcast_partial": (
        "📢 <b>برۆدکاست بەشێکی نێردرا</b>\n\n✅ گەیشت: <b>{ok}</b>\n❌ نەگەیشت: <b>{fail}</b>\n"
        "⏱ کاتەکە تەواو بوو — <b>{left}</b> کەس ماوە."
    ),
    "welcome_set": "✅ نامەی بەخێرهاتن گۆڕدرا.",
    "invalid_id": "❌ ئایدییەکە دروست نییە! تەنیا ژمارە بنووسە.",
    "user_not_found": "⚠️ ئەم بەکارهێنەرە نەدۆزرایەوە.",
    "cant_touch": "⛔ ناتوانیت ئەم کەسە بلۆک بکەیت.",
    "no_perm": "⛔ دەسەڵاتت نییە.",
    "act_blocked": "🚫 {id} بلۆک کرا.", "act_unblocked": "✅ بلۆکی {id} لابرا.",
    "act_adm_added": "✅ {id} بوو بە ئەدمین.", "act_adm_removed": "➖ {id} لە ئەدمین لابرا.",
    "act_sup_added": "🌌 {id} بوو بە سوپەر ئەدمین.", "act_sup_removed": "➖ {id} لە سوپەر ئەدمین لابرا.",
    "act_vip_added": "💎 {id} کرایە VIP.", "act_vip_removed": "➖ VIP لە {id} سەندرایەوە.",
    "act_ch_bad": "❌ فۆرماتەکە هەڵەیە! بنووسە: <code>@channelname</code>",
    "ch_not_admin": (
        "⚠️ بۆتەکە لە {ch} <b>ئەدمین</b> نییە یان چەناڵەکە نەدۆزرایەوە.\n"
        "سەرەتا بۆتەکە بکە بە ئەدمین لە چەناڵەکە، پاشان دووبارە هەوڵبدەرەوە."
    ),
    "sup_admins_title": "👮 <b>ئەدمینەکان</b> ({count})",
    "sup_vip_title": "💎 <b>VIP</b> ({count})",
    "sup_ch_title": "📢 <b>چەناڵەکانی جۆینی ناچاری</b> ({count})",
    "sup_ch_empty": "📭 بەتاڵە",
    "sup_ch_remove_q": "کام چەناڵ دەسڕیتەوە؟",
    "sup_ch_added": "✅ {ch} زیاد کرا.",
    "sup_add_adm_ask": "➕ <b>زیادکردنی ئەدمین</b>\n\n{write_id}",
    "sup_add_vip_ask": "💎 <b>پێدانی VIP</b>\n\n{write_id}",
    "sup_add_ch_ask": "📢 <b>زیادکردنی چەناڵ</b>\n\n{write_ch}",
    "own_super_title": "🌌 <b>سوپەر ئەدمینەکان</b> ({count})",
    "own_add_sup_ask": "➕ <b>زیادکردنی سوپەر ئەدمین</b>\n\n{write_id}",
    "confirm_rm": "⚠️ دڵنیایت دەتەوێت ئەمە بسڕیتەوە؟\n<b>{what}</b>",
    "api_title": "⚙️ <b>سەرچاوەی دابەزاندن هەڵبژێرە</b>",
    "bot_lang_title": "🌍 <b>زمانی سەرەکی بۆتەکە</b>\n<i>بۆ هەموو ئەو کەسانەی هێشتا زمانیان هەڵنەبژاردووە.</i>",
    "bot_lang_saved": "✅ زمانی سەرەکی گۆڕدرا بۆ: {lang}",
    "reset_confirm": "⚠️ <b>ئاماری دابەزاندن سفر دەکرێتەوە.</b>\nدڵنیایت؟",
    "reset_done": "✅ ئامار سفر کرایەوە.",
    "backup_prep": "⏳ ئامادە دەکرێت…",
    "new_user_notify": (
        "🔔 <b>بەکارهێنەری نوێ</b>\n\n"
        "<blockquote>✨ ناو: {name}\n🔗 یوزەر: {uname}\n🆔 ئایدی: <code>{uid}</code>\n"
        "🌐 زمانی ئەپ: {app_lang}\n📅 {date}</blockquote>"
    ),
    "b_notify_block": "🚫 بلۆک", "b_notify_vip": "💎 VIP", "b_notify_admin": "🛡 ئەدمین", "b_notify_info": "🔎 زانیاری",
}

L["en"] = {
    "welcome": (
        "✨ <b>Welcome, {name}</b> {badge}\n\n"
        "Download <b>TikTok</b> videos, photos and music with a single link — "
        "<b>no watermark</b>, high quality.\n\n"
        "<blockquote>🎬  HD video without watermark\n"
        "🖼  Every photo of a post\n"
        "🎵  Music as MP3</blockquote>\n"
        "👇 <b>Send a TikTok link</b> and wait a few seconds."
    ),
    "help": (
        "<b>📖 How to use</b>\n\n"
        "<b>1</b> · In TikTok tap <b>Share</b> and choose <b>Copy link</b>.\n"
        "<b>2</b> · Paste the link here and send it.\n"
        "<b>3</b> · Wait a few seconds — done ⚡\n\n"
        "<blockquote>🎬 Video — no watermark, high quality\n"
        "🖼 Photos — the whole post as an album\n"
        "🎵 Music — tap the <b>MP3</b> button under the video\n"
        "👤 Profile — send a username for an HD profile picture\n"
        "🕵️ Stories — tap <b>Secret story</b> and send a username</blockquote>\n"
        "💎 <b>VIP</b> — no forced join, more photos.\n"
        "📩 Contact: {dev}"
    ),
    "profile": (
        "<b>👤 My profile</b>\n\n"
        "<blockquote>🆔 ID: <code>{id}</code>\n"
        "✨ Name: {name}\n"
        "🔗 Username: {user}\n"
        "🏅 Rank: {rank}\n"
        "🌐 Language: {ulang}\n"
        "📥 Downloads: <b>{dl}</b>\n"
        "📅 Joined: {date}</blockquote>"
    ),
    "vip_info": (
        "<b>💎 VIP</b>\n\n"
        "<blockquote>✅ No forced channel join\n"
        "✅ More photos per post\n"
        "✅ Priority support</blockquote>\n"
        "🛒 To get VIP contact {dev}"
    ),
    "rank_owner": "👑 Owner", "rank_super": "🌌 Super Admin", "rank_admin": "🛡 Admin",
    "rank_vip": "💎 VIP", "rank_user": "👤 User",
    "lang_title": "🌐 <b>Choose your language</b>",
    "lang_current": "🔵 Current: {cur}",
    "lang_saved": "✅ Language changed",
    "force_join": (
        "🔒 <b>Forced join</b>\n\n"
        "To continue, join the channels below first, then tap <b>“I joined”</b> 👇"
    ),
    "not_joined": "⚠️ You haven't joined all the channels yet!",
    "st_search": "🔎 <b>Looking up the link…</b>\n{bar}",
    "st_download": "⬇️ <b>Downloading…</b>\n{bar}",
    "st_upload": "📤 <b>Uploading to Telegram…</b>\n{bar}",
    "st_audio": "🎵 <b>Preparing the audio…</b>\n{bar}",
    "blocked_msg": "⛔ <b>You are blocked</b>\nYou can't use this bot.",
    "maintenance_msg": (
        "🛠 <b>Maintenance</b>\n\n"
        "The bot is being updated and will be back soon ⏳\n"
        "📩 {dev}"
    ),
    "busy_msg": "⏳ Your previous request is still running — please wait a few seconds.",
    "session_expired": "⚠️ This request expired — please send the link again.",
    "invalid_link": (
        "❌ <b>Link not found</b>\n\n"
        "Make sure the link is valid and the post isn't private, then try again."
    ),
    "not_link": (
        "🔗 Please send a <b>TikTok link</b> or a <b>username</b>.\n"
        "Example: <code>https://vm.tiktok.com/xxxxxxx</code> or <code>@username</code>"
    ),
    "dl_fail": "❌ <b>Download failed</b>\nPlease try again in a few seconds.",
    "no_photo": "❌ This post has no photos!",
    "no_video": "❌ Video not found!",
    "no_audio": "❌ Audio not available!",
    "too_big": (
        "⚠️ <b>The file is too large</b> for Telegram (over 50 MB).\n"
        "Use the button below to download it directly 👇"
    ),
    "photos_done": "🖼 <b>{n} photos</b> ready ✅",
    "ask_link_prompt": "🔗 <b>Send the TikTok link:</b>",
    "ask_avatar_prompt": "👤 <b>Send a TikTok username:</b>\nExample: <code>@username</code>",
    "avatar_caption": "👤 <b>Profile picture of @{user}</b>\n\n⚡ <a href=\"https://t.me/{bot}\">@{bot}</a>",
    "no_avatar": "❌ Profile picture not found! The account may be private or not exist.",
    "private_account": "🔒 <b>This account is private!</b>\nOnly public accounts are supported.",
    "st_avatar": "👤 <b>Preparing the profile picture…</b>\n{bar}",
    "ask_story_prompt": "🕵️ <b>Secret story viewer</b>\n\nSend the TikTok username:\nExample: <code>@username</code>",
    "st_story": "🕵️ <b>Quietly looking for stories…</b>\n{bar}",
    "story_header": (
        "🕵️ <b>Secret stories · @{user}</b>\n\n"
        "<blockquote>📖 Active stories: <b>{n}</b>\n"
        "🎬 Videos: <b>{v}</b>   🖼 Photos: <b>{p}</b>\n"
        "👻 Zero trace — you won't appear in the viewer list</blockquote>"
    ),
    "story_caption": "🕵️ <b>@{user}</b> · story <b>{i}/{n}</b>\n🕒 {when}\n\n⚡ <a href=\"https://t.me/{bot}\">@{bot}</a>",
    "story_done": "✅ <b>{n} stories</b> delivered 👻",
    "story_partial": "⏱ Time limit reached — <b>{n}</b> stories sent, <b>{left}</b> left. Tap the button below to continue.",
    "b_story_more": "▶️ Continue ({left} left)",
    "story_expired": "⌛ This continuation expired. Request the stories again.",
    "no_story": "📭 <b>@{user}</b> has no active stories right now.\nTikTok stories last 24 hours.",
    "story_unavailable": "⚠️ This account's stories aren't available (it may be private, or the source doesn't support them).",
    "b_story": "🕵️ Secret story", "b_story_again": "🔄 Another story",
    "b_dl": "📥 New download", "b_profile": "👤 Profile", "b_vip": "💎 VIP", "b_avatar": "🖼 Profile picture",
    "b_lang": "🌐 Language", "b_help": "📖 Help", "b_channel": "📢 Bot channel",
    "b_panel": "🛠 Control panel", "b_back": "🔙 Back", "b_delete": "🗑 Delete",
    "b_joined": "✅ I joined", "b_audio": "🎵 MP3 audio", "b_orig": "🔗 Original link",
    "b_direct": "⬇️ Direct download", "b_cancel": "✖️ Cancel",
    "b_confirm": "✅ Yes, I'm sure", "b_deny": "✖️ No", "b_refresh": "🔄 Refresh",
    "b_clear": "🧹 Clear", "b_add": "➕ Add", "b_remove": "➖ Remove",
    "b_add_vip": "➕ VIP", "b_rm_vip": "➖ VIP",
    "on": "🟢 ON", "off": "🔴 OFF",
    "panel_title": (
        "🛠 <b>Control panel</b>\n\n"
        "<blockquote>👥 Users: <b>{users}</b>\n"
        "💎 VIP: <b>{vip}</b>\n"
        "🚫 Blocked: <b>{blocked}</b>\n"
        "📥 Downloads: <b>{dl}</b></blockquote>"
    ),
    "adm_stats": (
        "📊 <b>Statistics</b>\n\n"
        "<blockquote>👥 Total users: <b>{users}</b>\n"
        "💎 VIP: <b>{vip}</b>\n"
        "🚫 Blocked: <b>{blocked}</b>\n"
        "🛡 Admins: <b>{admins}</b>\n"
        "📢 Forced channels: <b>{channels}</b>\n"
        "📥 Total downloads: <b>{dl}</b>\n"
        "🛠 Maintenance: {maint}\n"
        "⚙️ Source: <b>{api}</b></blockquote>"
    ),
    "b_adm_stats": "📊 Stats", "b_adm_broadcast": "📢 Broadcast", "b_adm_block": "🚫 Block",
    "b_adm_unblock": "✅ Unblock", "b_adm_info": "🔎 User info",
    "b_sup_admins": "👮 Admins", "b_sup_vip": "💎 VIP", "b_sup_channels": "📢 Channels",
    "b_sup_maint": "🛠 Maintenance: {status}", "b_sup_api": "⚙️ API source",
    "b_sup_botlang": "🌍 Bot language", "b_sup_audio": "🎵 Auto audio: {status}",
    "b_own_super": "🌌 Super admins", "b_own_welcome": "📝 Welcome message",
    "b_own_reset": "♻️ Reset stats", "b_own_backup": "💾 Backup",
    "adm_broadcast_ask": "✍️ <b>Send your message</b>\n(text, photo, video — anything):",
    "adm_block_ask": "🚫 <b>Block a user</b>\n\n{write_id}",
    "adm_unblock_ask": "✅ <b>Unblock a user</b>\n\n{write_id}",
    "adm_info_ask": "🔎 <b>User info</b>\n\n{write_id}",
    "write_id": "✍️ Type the numeric user ID and send:",
    "write_ch": "✍️ Type the channel username (e.g. <code>@mychannel</code>):",
    "write_welcome": (
        "✍️ <b>Write the welcome message</b>\n"
        "You can use <code>{name}</code> and <code>{badge}</code>.\n"
        "Telegram formatting (bold etc.) is supported."
    ),
    "userinfo": (
        "🔎 <b>User info</b>\n\n"
        "<blockquote>✨ Name: {name}\n🔗 User: {user}\n🆔 ID: <code>{id}</code>\n"
        "🏅 Rank: {rank}\n🚫 Blocked: {blocked}\n🌐 Language: {lang}\n"
        "📥 Downloads: <b>{dl}</b>\n📅 Joined: {date}</blockquote>"
    ),
    "yes": "Yes", "no": "No",
    "broadcast_start": "⏳ Sending to <b>{total}</b> users…",
    "broadcast_progress": "⏳ Sending: <b>{done}</b> / {total}",
    "broadcast_done": "📢 <b>Broadcast complete</b>\n\n✅ Delivered: <b>{ok}</b>\n❌ Failed: <b>{fail}</b>",
    "broadcast_partial": (
        "📢 <b>Broadcast partially sent</b>\n\n✅ Delivered: <b>{ok}</b>\n❌ Failed: <b>{fail}</b>\n"
        "⏱ Time limit reached — <b>{left}</b> users left."
    ),
    "welcome_set": "✅ Welcome message updated.",
    "invalid_id": "❌ Invalid ID! Numbers only.",
    "user_not_found": "⚠️ User not found.",
    "cant_touch": "⛔ You can't block this person.",
    "no_perm": "⛔ You don't have permission.",
    "act_blocked": "🚫 {id} has been blocked.", "act_unblocked": "✅ {id} has been unblocked.",
    "act_adm_added": "✅ {id} is now an Admin.", "act_adm_removed": "➖ {id} removed from Admin.",
    "act_sup_added": "🌌 {id} is now a Super Admin.", "act_sup_removed": "➖ {id} removed from Super Admin.",
    "act_vip_added": "💎 {id} is now VIP.", "act_vip_removed": "➖ VIP removed from {id}.",
    "act_ch_bad": "❌ Wrong format! Write: <code>@channelname</code>",
    "ch_not_admin": (
        "⚠️ The bot is not an <b>admin</b> in {ch}, or the channel doesn't exist.\n"
        "Make the bot an admin of the channel first, then try again."
    ),
    "sup_admins_title": "👮 <b>Admins</b> ({count})",
    "sup_vip_title": "💎 <b>VIP</b> ({count})",
    "sup_ch_title": "📢 <b>Forced-join channels</b> ({count})",
    "sup_ch_empty": "📭 Empty",
    "sup_ch_remove_q": "Which channel do you want to remove?",
    "sup_ch_added": "✅ {ch} added.",
    "sup_add_adm_ask": "➕ <b>Add admin</b>\n\n{write_id}",
    "sup_add_vip_ask": "💎 <b>Give VIP</b>\n\n{write_id}",
    "sup_add_ch_ask": "📢 <b>Add channel</b>\n\n{write_ch}",
    "own_super_title": "🌌 <b>Super admins</b> ({count})",
    "own_add_sup_ask": "➕ <b>Add super admin</b>\n\n{write_id}",
    "confirm_rm": "⚠️ Are you sure you want to remove this?\n<b>{what}</b>",
    "api_title": "⚙️ <b>Choose the download source</b>",
    "bot_lang_title": "🌍 <b>Bot default language</b>\n<i>Applies to everyone who hasn't picked a language yet.</i>",
    "bot_lang_saved": "✅ Default language changed to: {lang}",
    "reset_confirm": "⚠️ <b>Download stats will be reset.</b>\nAre you sure?",
    "reset_done": "✅ Stats have been reset.",
    "backup_prep": "⏳ Preparing…",
    "new_user_notify": (
        "🔔 <b>New user</b>\n\n"
        "<blockquote>✨ Name: {name}\n🔗 User: {uname}\n🆔 ID: <code>{uid}</code>\n"
        "🌐 App language: {app_lang}\n📅 {date}</blockquote>"
    ),
    "b_notify_block": "🚫 Block", "b_notify_vip": "💎 VIP", "b_notify_admin": "🛡 Admin", "b_notify_info": "🔎 Info",
}

L["ar"] = {
    "welcome": (
        "✨ <b>أهلاً بك، {name}</b> {badge}\n\n"
        "حمّل فيديوهات <b>تيك توك</b> وصورها وموسيقاها برابط واحد — "
        "<b>بدون علامة مائية</b> وبجودة عالية.\n\n"
        "<blockquote>🎬  فيديو HD بدون علامة مائية\n"
        "🖼  جميع صور المنشور\n"
        "🎵  الموسيقى بصيغة MP3</blockquote>\n"
        "👇 <b>أرسل رابط تيك توك</b> وانتظر ثوانٍ قليلة."
    ),
    "help": (
        "<b>📖 طريقة الاستخدام</b>\n\n"
        "<b>١</b> · في تيك توك اضغط <b>Share</b> ثم اختر <b>Copy link</b>.\n"
        "<b>٢</b> · الصق الرابط هنا وأرسله.\n"
        "<b>٣</b> · انتظر ثوانٍ قليلة — جاهز ⚡\n\n"
        "<blockquote>🎬 الفيديو — بدون علامة مائية وبجودة عالية\n"
        "🖼 الصور — كل صور المنشور كألبوم\n"
        "🎵 الموسيقى — زر <b>MP3</b> أسفل الفيديو\n"
        "👤 الملف الشخصي — أرسل اسم مستخدم للحصول على صورة الملف الشخصي بجودة HD\n"
        "🕵️ القصص — اضغط <b>قصة سرية</b> وأرسل اسم مستخدم</blockquote>\n"
        "💎 <b>VIP</b> — بدون اشتراك إجباري وصور أكثر.\n"
        "📩 للتواصل: {dev}"
    ),
    "profile": (
        "<b>👤 ملفي الشخصي</b>\n\n"
        "<blockquote>🆔 المعرّف: <code>{id}</code>\n"
        "✨ الاسم: {name}\n"
        "🔗 اسم المستخدم: {user}\n"
        "🏅 الرتبة: {rank}\n"
        "🌐 اللغة: {ulang}\n"
        "📥 التحميلات: <b>{dl}</b>\n"
        "📅 تاريخ الانضمام: {date}</blockquote>"
    ),
    "vip_info": (
        "<b>💎 قسم VIP</b>\n\n"
        "<blockquote>✅ بدون اشتراك إجباري\n"
        "✅ عدد صور أكبر لكل منشور\n"
        "✅ دعم مميز</blockquote>\n"
        "🛒 للحصول على VIP تواصل مع {dev}"
    ),
    "rank_owner": "👑 المالك", "rank_super": "🌌 مشرف عام", "rank_admin": "🛡 مشرف",
    "rank_vip": "💎 VIP", "rank_user": "👤 مستخدم",
    "lang_title": "🌐 <b>اختر لغتك</b>",
    "lang_current": "🔵 الحالية: {cur}",
    "lang_saved": "✅ تم تغيير اللغة",
    "force_join": (
        "🔒 <b>الاشتراك الإجباري</b>\n\n"
        "للمتابعة اشترك في القنوات التالية أولاً ثم اضغط <b>«اشتركت»</b> 👇"
    ),
    "not_joined": "⚠️ لم تشترك في جميع القنوات بعد!",
    "st_search": "🔎 <b>جارٍ البحث عن الرابط…</b>\n{bar}",
    "st_download": "⬇️ <b>جارٍ التحميل…</b>\n{bar}",
    "st_upload": "📤 <b>جارٍ الرفع إلى تيليجرام…</b>\n{bar}",
    "st_audio": "🎵 <b>جارٍ تجهيز الصوت…</b>\n{bar}",
    "blocked_msg": "⛔ <b>أنت محظور</b>\nلا يمكنك استخدام هذا البوت.",
    "maintenance_msg": (
        "🛠 <b>وضع الصيانة</b>\n\n"
        "البوت قيد التحديث وسيعود قريباً ⏳\n"
        "📩 {dev}"
    ),
    "busy_msg": "⏳ طلبك السابق لم ينتهِ بعد — انتظر ثوانٍ قليلة.",
    "session_expired": "⚠️ انتهت صلاحية الطلب — أرسل الرابط مجدداً.",
    "invalid_link": (
        "❌ <b>لم يتم العثور على الرابط</b>\n\n"
        "تأكد أن الرابط صحيح وأن المنشور ليس خاصاً، ثم حاول مرة أخرى."
    ),
    "not_link": (
        "🔗 من فضلك أرسل <b>رابط تيك توك</b> أو <b>اسم مستخدم</b>.\n"
        "مثال: <code>https://vm.tiktok.com/xxxxxxx</code> أو <code>@username</code>"
    ),
    "dl_fail": "❌ <b>فشل التحميل</b>\nحاول مرة أخرى بعد ثوانٍ.",
    "no_photo": "❌ هذا المنشور لا يحتوي على صور!",
    "no_video": "❌ لم يتم العثور على الفيديو!",
    "no_audio": "❌ الصوت غير متاح!",
    "too_big": (
        "⚠️ <b>الملف كبير جداً</b> على تيليجرام (أكثر من 50 ميغابايت).\n"
        "استخدم الزر أدناه للتحميل المباشر 👇"
    ),
    "photos_done": "🖼 <b>{n} صورة</b> جاهزة ✅",
    "ask_link_prompt": "🔗 <b>أرسل رابط تيك توك:</b>",
    "ask_avatar_prompt": "👤 <b>أرسل اسم مستخدم تيك توك:</b>\nمثال: <code>@username</code>",
    "avatar_caption": "👤 <b>صورة الملف الشخصي لـ @{user}</b>\n\n⚡ <a href=\"https://t.me/{bot}\">@{bot}</a>",
    "no_avatar": "❌ لم يتم العثور على صورة الملف الشخصي! ربما الحساب خاص أو غير موجود.",
    "private_account": "🔒 <b>هذا الحساب خاص!</b>\nيتم دعم الحسابات العامة فقط.",
    "st_avatar": "👤 <b>جارٍ تجهيز صورة الملف الشخصي…</b>\n{bar}",
    "ask_story_prompt": "🕵️ <b>مشاهدة القصص السرية</b>\n\nأرسل اسم مستخدم تيك توك:\nمثال: <code>@username</code>",
    "st_story": "🕵️ <b>جارٍ البحث عن القصص بسرّية…</b>\n{bar}",
    "story_header": (
        "🕵️ <b>قصص سرية · @{user}</b>\n\n"
        "<blockquote>📖 القصص النشطة: <b>{n}</b>\n"
        "🎬 فيديو: <b>{v}</b>   🖼 صور: <b>{p}</b>\n"
        "👻 بلا أثر — لن تظهر في قائمة المشاهدين</blockquote>"
    ),
    "story_caption": "🕵️ <b>@{user}</b> · قصة <b>{i}/{n}</b>\n🕒 {when}\n\n⚡ <a href=\"https://t.me/{bot}\">@{bot}</a>",
    "story_done": "✅ تم إرسال <b>{n} قصة</b> 👻",
    "story_partial": "⏱ انتهى الوقت — أُرسلت <b>{n}</b> قصة وتبقّت <b>{left}</b>. اضغط الزر أدناه للمتابعة.",
    "b_story_more": "▶️ متابعة (تبقّى {left})",
    "story_expired": "⌛ انتهت صلاحية المتابعة. اطلب القصص مجدداً.",
    "no_story": "📭 <b>@{user}</b> لا يملك قصصاً نشطة حالياً.\nقصص تيك توك تبقى 24 ساعة.",
    "story_unavailable": "⚠️ قصص هذا الحساب غير متاحة (ربما الحساب خاص أو المصدر لا يدعمها).",
    "b_story": "🕵️ قصة سرية", "b_story_again": "🔄 قصة أخرى",
    "b_dl": "📥 تحميل جديد", "b_profile": "👤 الملف الشخصي", "b_vip": "💎 VIP", "b_avatar": "🖼 صورة الملف الشخصي",
    "b_lang": "🌐 اللغة", "b_help": "📖 المساعدة", "b_channel": "📢 قناة البوت",
    "b_panel": "🛠 لوحة التحكم", "b_back": "🔙 رجوع", "b_delete": "🗑 حذف",
    "b_joined": "✅ اشتركت", "b_audio": "🎵 صوت MP3", "b_orig": "🔗 الرابط الأصلي",
    "b_direct": "⬇️ تحميل مباشر", "b_cancel": "✖️ إلغاء",
    "b_confirm": "✅ نعم، متأكد", "b_deny": "✖️ لا", "b_refresh": "🔄 تحديث",
    "b_clear": "🧹 مسح", "b_add": "➕ إضافة", "b_remove": "➖ إزالة",
    "b_add_vip": "➕ VIP", "b_rm_vip": "➖ VIP",
    "on": "🟢 مفعّل", "off": "🔴 معطّل",
    "panel_title": (
        "🛠 <b>لوحة التحكم</b>\n\n"
        "<blockquote>👥 المستخدمون: <b>{users}</b>\n"
        "💎 VIP: <b>{vip}</b>\n"
        "🚫 المحظورون: <b>{blocked}</b>\n"
        "📥 التحميلات: <b>{dl}</b></blockquote>"
    ),
    "adm_stats": (
        "📊 <b>الإحصائيات</b>\n\n"
        "<blockquote>👥 إجمالي المستخدمين: <b>{users}</b>\n"
        "💎 VIP: <b>{vip}</b>\n"
        "🚫 المحظورون: <b>{blocked}</b>\n"
        "🛡 المشرفون: <b>{admins}</b>\n"
        "📢 قنوات الاشتراك: <b>{channels}</b>\n"
        "📥 إجمالي التحميلات: <b>{dl}</b>\n"
        "🛠 الصيانة: {maint}\n"
        "⚙️ المصدر: <b>{api}</b></blockquote>"
    ),
    "b_adm_stats": "📊 الإحصائيات", "b_adm_broadcast": "📢 بث", "b_adm_block": "🚫 حظر",
    "b_adm_unblock": "✅ فك الحظر", "b_adm_info": "🔎 معلومات مستخدم",
    "b_sup_admins": "👮 المشرفون", "b_sup_vip": "💎 VIP", "b_sup_channels": "📢 القنوات",
    "b_sup_maint": "🛠 الصيانة: {status}", "b_sup_api": "⚙️ مصدر API",
    "b_sup_botlang": "🌍 لغة البوت", "b_sup_audio": "🎵 صوت تلقائي: {status}",
    "b_own_super": "🌌 المشرفون العامون", "b_own_welcome": "📝 رسالة الترحيب",
    "b_own_reset": "♻️ تصفير الإحصائيات", "b_own_backup": "💾 نسخة احتياطية",
    "adm_broadcast_ask": "✍️ <b>أرسل رسالتك</b>\n(نص، صورة، فيديو — أي شيء):",
    "adm_block_ask": "🚫 <b>حظر مستخدم</b>\n\n{write_id}",
    "adm_unblock_ask": "✅ <b>فك حظر مستخدم</b>\n\n{write_id}",
    "adm_info_ask": "🔎 <b>معلومات مستخدم</b>\n\n{write_id}",
    "write_id": "✍️ اكتب معرّف المستخدم الرقمي وأرسله:",
    "write_ch": "✍️ اكتب معرّف القناة (مثال: <code>@mychannel</code>):",
    "write_welcome": (
        "✍️ <b>اكتب رسالة الترحيب</b>\n"
        "يمكنك استخدام <code>{name}</code> و <code>{badge}</code>.\n"
        "تنسيق تيليجرام (الخط العريض وغيره) مدعوم."
    ),
    "userinfo": (
        "🔎 <b>معلومات المستخدم</b>\n\n"
        "<blockquote>✨ الاسم: {name}\n🔗 المستخدم: {user}\n🆔 المعرّف: <code>{id}</code>\n"
        "🏅 الرتبة: {rank}\n🚫 محظور: {blocked}\n🌐 اللغة: {lang}\n"
        "📥 التحميلات: <b>{dl}</b>\n📅 الانضمام: {date}</blockquote>"
    ),
    "yes": "نعم", "no": "لا",
    "broadcast_start": "⏳ بدأ الإرسال إلى <b>{total}</b> مستخدم…",
    "broadcast_progress": "⏳ الإرسال: <b>{done}</b> / {total}",
    "broadcast_done": "📢 <b>اكتمل البث</b>\n\n✅ وصلت: <b>{ok}</b>\n❌ لم تصل: <b>{fail}</b>",
    "broadcast_partial": (
        "📢 <b>تم إرسال جزء من البث</b>\n\n✅ وصلت: <b>{ok}</b>\n❌ لم تصل: <b>{fail}</b>\n"
        "⏱ انتهى الوقت المسموح — تبقّى <b>{left}</b> مستخدم."
    ),
    "welcome_set": "✅ تم تحديث رسالة الترحيب.",
    "invalid_id": "❌ المعرّف غير صحيح! أرقام فقط.",
    "user_not_found": "⚠️ المستخدم غير موجود.",
    "cant_touch": "⛔ لا يمكنك حظر هذا الشخص.",
    "no_perm": "⛔ ليست لديك صلاحية.",
    "act_blocked": "🚫 تم حظر {id}.", "act_unblocked": "✅ تم فك حظر {id}.",
    "act_adm_added": "✅ {id} أصبح مشرفاً.", "act_adm_removed": "➖ تمت إزالة {id} من المشرفين.",
    "act_sup_added": "🌌 {id} أصبح مشرفاً عاماً.", "act_sup_removed": "➖ تمت إزالة {id} من المشرفين العامين.",
    "act_vip_added": "💎 {id} أصبح VIP.", "act_vip_removed": "➖ تم سحب VIP من {id}.",
    "act_ch_bad": "❌ الصيغة خاطئة! اكتب: <code>@channelname</code>",
    "ch_not_admin": (
        "⚠️ البوت ليس <b>مشرفاً</b> في {ch} أو أن القناة غير موجودة.\n"
        "اجعل البوت مشرفاً في القناة أولاً ثم حاول مجدداً."
    ),
    "sup_admins_title": "👮 <b>المشرفون</b> ({count})",
    "sup_vip_title": "💎 <b>VIP</b> ({count})",
    "sup_ch_title": "📢 <b>قنوات الاشتراك الإجباري</b> ({count})",
    "sup_ch_empty": "📭 فارغة",
    "sup_ch_remove_q": "أي قناة تريد إزالتها؟",
    "sup_ch_added": "✅ تمت إضافة {ch}.",
    "sup_add_adm_ask": "➕ <b>إضافة مشرف</b>\n\n{write_id}",
    "sup_add_vip_ask": "💎 <b>منح VIP</b>\n\n{write_id}",
    "sup_add_ch_ask": "📢 <b>إضافة قناة</b>\n\n{write_ch}",
    "own_super_title": "🌌 <b>المشرفون العامون</b> ({count})",
    "own_add_sup_ask": "➕ <b>إضافة مشرف عام</b>\n\n{write_id}",
    "confirm_rm": "⚠️ هل أنت متأكد أنك تريد إزالة هذا؟\n<b>{what}</b>",
    "api_title": "⚙️ <b>اختر مصدر التحميل</b>",
    "bot_lang_title": "🌍 <b>اللغة الافتراضية للبوت</b>\n<i>تُطبَّق على كل من لم يختر لغة بعد.</i>",
    "bot_lang_saved": "✅ تم تغيير اللغة الافتراضية إلى: {lang}",
    "reset_confirm": "⚠️ <b>سيتم تصفير إحصائيات التحميل.</b>\nهل أنت متأكد؟",
    "reset_done": "✅ تم تصفير الإحصائيات.",
    "backup_prep": "⏳ جارٍ التجهيز…",
    "new_user_notify": (
        "🔔 <b>مستخدم جديد</b>\n\n"
        "<blockquote>✨ الاسم: {name}\n🔗 المستخدم: {uname}\n🆔 المعرّف: <code>{uid}</code>\n"
        "🌐 لغة التطبيق: {app_lang}\n📅 {date}</blockquote>"
    ),
    "b_notify_block": "🚫 حظر", "b_notify_vip": "💎 VIP", "b_notify_admin": "🛡 مشرف", "b_notify_info": "🔎 معلومات",
}

LANG_NAMES = {"ku": "🔴🔆🟢 کوردی", "en": "🇺🇸 English", "ar": "🇸🇦 العربية"}


def tx(lang: str, key: str, **kw) -> str:
    """Translate `key` into `lang` (falls back to Kurdish, then to the key)."""
    text = L.get(lang, L["ku"]).get(key) or L["ku"].get(key) or key
    try:
        return text.format(**kw)
    except (KeyError, IndexError, ValueError):
        return text


# ══════════════════════════════════════════════════════════════════════════════
# 3 · SMALL HELPERS
# ══════════════════════════════════════════════════════════════════════════════
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Mobile Safari/537.36")


def esc(s) -> str:
    """HTML-escape any value for Telegram's HTML parse mode."""
    return html.escape("" if s is None else str(s), quote=False)


def clip(s, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def fmt_num(n) -> str:
    """1234 → 1.2K · 5_600_000 → 5.6M"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    for lim, suf in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= lim:
            return f"{n / lim:.1f}".rstrip("0").rstrip(".") + suf
    return str(n)


def now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def bar(step: int, total: int = 5) -> str:
    step = max(0, min(step, total))
    return "▰" * step + "▱" * (total - step)


def as_list(v) -> list:
    """Firebase returns lists as list / dict / None depending on shape."""
    if not v:
        return []
    if isinstance(v, dict):
        v = list(v.values())
    return [x for x in v if x is not None]


def is_owner(uid) -> bool:   return uid == OWNER_ID
def is_super(uid) -> bool:   return uid in super_admins_set or is_owner(uid)
def is_admin(uid) -> bool:   return uid in admins_set or is_super(uid)
def is_vip(uid) -> bool:     return uid in vip_set or is_super(uid)
def is_blocked(uid) -> bool: return uid in blocked_set and not is_owner(uid)


def rank_key(uid) -> str:
    return ("owner" if is_owner(uid) else "super" if is_super(uid) else
            "admin" if is_admin(uid) else "vip" if is_vip(uid) else "user")


def badge_of(uid) -> str:
    return {"owner": "👑", "super": "🌌", "admin": "🛡", "vip": "💎", "user": ""}[rank_key(uid)]


def bypass_join(uid) -> bool:
    return (is_admin(uid) and CFG.get("admin_bypass", True)) or \
           (is_vip(uid) and CFG.get("vip_bypass", True))


def deadline_left(started: float) -> float:
    return FUNC_BUDGET - (time.monotonic() - started)


# ══════════════════════════════════════════════════════════════════════════════
# 4 · HTTP + FIREBASE (REST)
#     One httpx client per webhook invocation (stored in a ContextVar) so
#     connections are reused and nothing outlives the serverless request.
# ══════════════════════════════════════════════════════════════════════════════
_http_ctx: ContextVar = ContextVar("http_client", default=None)


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": UA},
        limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
    )


def http() -> httpx.AsyncClient:
    c = _http_ctx.get()
    if c is None or c.is_closed:          # only happens outside the webhook (tests)
        c = new_client()
        _http_ctx.set(c)
    return c


def _fb(path: str) -> str:
    return f"{DB_URL}/{path}.json"


def _auth() -> dict:
    return {"auth": DB_SECRET} if DB_SECRET else {}


async def db_get(path: str, default=None):
    if not DB_URL:
        return default
    try:
        r = await http().get(_fb(path), params=_auth(), timeout=10)
        if r.status_code == 200:
            v = r.json()
            return default if v is None else v
        log.warning("db_get %s → HTTP %s", path, r.status_code)
    except Exception as e:
        log.warning("db_get %s failed: %s", path, e)
    return default


async def db_put(path: str, value) -> bool:
    if not DB_URL:
        return False
    try:
        r = await http().put(_fb(path), params=_auth(), json=value, timeout=10)
        if r.status_code == 200:
            return True
        log.warning("db_put %s → HTTP %s", path, r.status_code)
    except Exception as e:
        log.warning("db_put %s failed: %s", path, e)
    return False


async def db_patch(path: str, value: dict) -> bool:
    if not DB_URL:
        return False
    try:
        r = await http().patch(_fb(path), params=_auth(), json=value, timeout=10)
        return r.status_code == 200
    except Exception as e:
        log.warning("db_patch %s failed: %s", path, e)
    return False


async def db_del(path: str) -> bool:
    if not DB_URL:
        return False
    try:
        r = await http().delete(_fb(path), params=_auth(), timeout=10)
        return r.status_code == 200
    except Exception as e:
        log.warning("db_del %s failed: %s", path, e)
    return False


async def db_incr(path: str, n: int = 1) -> bool:
    """Atomic server-side increment (no read-modify-write race)."""
    return await db_put(path, {".sv": {"increment": n}})


# ── shared configuration ──────────────────────────────────────────────────────
async def load_cfg(force: bool = False) -> None:
    global super_admins_set, admins_set, channels_list, blocked_set, vip_set, last_cfg_load
    if not DB_URL:
        return
    if not force and time.time() - last_cfg_load < CFG_TTL:
        return
    d = await db_get("sys")
    last_cfg_load = time.time()             # even when empty/down: don't hammer the DB
    if not isinstance(d, dict):
        return
    super_admins_set = {OWNER_ID} | {int(x) for x in as_list(d.get("super_admins"))}
    admins_set       = {OWNER_ID} | super_admins_set | {int(x) for x in as_list(d.get("admins"))}
    channels_list    = [str(x) for x in as_list(d.get("channels"))]
    blocked_set      = {int(x) for x in as_list(d.get("blocked"))}
    vip_set          = {int(x) for x in as_list(d.get("vips"))}
    if isinstance(d.get("cfg"), dict):
        CFG.update(d["cfg"])


_SYS_KEYS = {
    "super_admins": lambda: sorted(super_admins_set),
    "admins":       lambda: sorted(admins_set),
    "channels":     lambda: list(channels_list),
    "blocked":      lambda: sorted(blocked_set),
    "vips":         lambda: sorted(vip_set),
}


async def save_sys(*keys: str) -> None:
    """Persist only the given keys → concurrent edits to other keys survive."""
    for k in keys:
        await db_put(f"sys/{k}", _SYS_KEYS[k]())


async def set_cfg(**kv) -> None:
    CFG.update(kv)
    await db_patch("sys/cfg", kv)


# ── users / sessions / admin prompts / locks ─────────────────────────────────
async def all_users() -> dict:
    d = await db_get("users", {})
    return d if isinstance(d, dict) else {}


def user_lang(ud: dict | None) -> str:
    lg = (ud or {}).get("lang")
    return lg if lg in L else (CFG.get("default_lang", "ku") if CFG.get("default_lang") in L else "ku")


async def ensure_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> tuple[dict, str]:
    """Load the user's record (creating + notifying the owner on first contact)."""
    u = update.effective_user
    ud = await db_get(f"users/{u.id}")
    if not isinstance(ud, dict):
        ud = {
            "name": u.first_name or "", "user": u.username or "", "date": now_str(),
            "vip": False, "dl": 0, "lang": CFG.get("default_lang", "ku"),
        }
        await db_put(f"users/{u.id}", ud)
        await db_incr("sys/cfg/total_users")
        await notify_new_user(ctx, u)
    return ud, user_lang(ud)


async def notify_new_user(ctx, u) -> None:
    try:
        kb = Kb([
            [Btn(tx("ku", "b_notify_block"), callback_data=f"quick_blk_{u.id}"),
             Btn(tx("ku", "b_notify_vip"),   callback_data=f"quick_vip_{u.id}")],
            [Btn(tx("ku", "b_notify_admin"), callback_data=f"quick_adm_{u.id}"),
             Btn(tx("ku", "b_notify_info"),  callback_data=f"quick_inf_{u.id}")],
        ])
        await ctx.bot.send_message(
            OWNER_ID,
            tx("ku", "new_user_notify", name=esc(u.first_name), uname=f"@{u.username}" if u.username else "—",
               uid=u.id, app_lang=esc(u.language_code or "—"), date=now_str()),
            reply_markup=kb,
        )
    except TelegramError as e:
        log.info("owner notification failed: %s", e)


async def session_save(key: str, data: dict) -> None:
    data["_ts"] = int(time.time())
    await db_put(f"sessions/{key}", data)


async def session_get(key: str) -> dict | None:
    d = await db_get(f"sessions/{key}")
    if isinstance(d, dict) and time.time() - d.get("_ts", 0) <= SESSION_TTL:
        return d
    return None


async def set_wait(uid: int, state: str) -> None:
    await db_put(f"wait/{uid}", {"s": state, "t": int(time.time())})


async def pop_wait(uid: int) -> str | None:
    d = await db_get(f"wait/{uid}")
    if not isinstance(d, dict):
        return None
    await db_del(f"wait/{uid}")
    return d.get("s") if time.time() - d.get("t", 0) <= WAIT_TTL else None


async def acquire_lock(uid: int) -> bool:
    """Per-user download lock: stops double-taps, spam and Telegram webhook retries."""
    t = await db_get(f"locks/{uid}")
    if isinstance(t, (int, float)) and time.time() - t < LOCK_TTL:
        return False
    await db_put(f"locks/{uid}", time.time())
    return True


async def release_lock(uid: int) -> None:
    await db_del(f"locks/{uid}")


async def display_name(uid: int) -> str:
    ud = await db_get(f"users/{uid}")
    if isinstance(ud, dict):
        name = esc(clip(ud.get("name") or str(uid), 24))
        return f"{name} (@{esc(ud['user'])})" if ud.get("user") else f"{name} [{uid}]"
    return str(uid)


# ══════════════════════════════════════════════════════════════════════════════
# 5 · TIKTOK PROVIDERS
# ══════════════════════════════════════════════════════════════════════════════
_URL_RE = re.compile(
    r"(?<![\w@.\-])(?:https?://)?(?:[a-z0-9\-]+\.)*tiktok\.com/[^\s<>\"']+", re.I
)


def extract_url(text: str) -> str | None:
    """Pull the first TikTok URL out of arbitrary text (people paste 'Look at this <link>')."""
    m = _URL_RE.search(text or "")
    if not m:
        return None
    u = m.group(0).rstrip(".,;:!?)]}>»«’”،؟")
    return u if u.lower().startswith("http") else "https://" + u


def abs_url(u, base: str = "") -> str:
    u = (u or "").strip() if isinstance(u, str) else ""
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/") and base:
        return base + u
    return u if u.lower().startswith("http") else ""


def _to_int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _media_key(vid: str, url: str) -> str:
    vid = str(vid or "")
    return vid if vid.isdigit() and len(vid) <= 24 else hashlib.md5(url.encode()).hexdigest()[:14]


def parse_tikwm(d: dict, src: str) -> dict:
    base = "https://www.tikwm.com"
    cands: list = []
    for key, skey in (("hdplay", "hd_size"), ("play", "size"), ("wmplay", "wm_size")):
        u = abs_url(d.get(key), base)
        if u and u not in [c[0] for c in cands]:
            cands.append((u, _to_int(d.get(skey))))
    mi = d.get("music_info") if isinstance(d.get("music_info"), dict) else {}
    au = d.get("author") if isinstance(d.get("author"), dict) else {}
    return {
        "key":      _media_key(d.get("id"), src),
        "src":      src,
        "creator":  au.get("nickname") or au.get("unique_id") or "TikTok",
        "title":    d.get("title") or "",
        "cover":    abs_url(d.get("cover"), base),
        "duration": _to_int(d.get("duration")),
        "videos":   cands,
        "audio":    abs_url(d.get("music") or mi.get("play"), base),
        "a_title":  mi.get("title") or "",
        "a_author": mi.get("author") or au.get("nickname") or "TikTok",
        "images":   [abs_url(i, base) for i in (d.get("images") or []) if isinstance(i, str) and abs_url(i, base)],
        "views":    _to_int(d.get("play_count")),
        "likes":    _to_int(d.get("digg_count")),
        "comments": _to_int(d.get("comment_count")),
        "shares":   _to_int(d.get("share_count")),
    }


def parse_hyper(d: dict, src: str) -> dict:
    det   = d.get("details") or {}
    stats = det.get("stats") or {}
    vurl  = abs_url((det.get("video") or {}).get("play"))
    return {
        "key":      _media_key("", src),
        "src":      src,
        "creator":  d.get("creator") or "TikTok",
        "title":    det.get("title") or "",
        "cover":    abs_url((det.get("cover") or {}).get("cover")),
        "duration": 0,
        "videos":   [(vurl, 0)] if vurl else [],
        "audio":    abs_url((det.get("audio") or {}).get("play")),
        "a_title":  "",
        "a_author": d.get("creator") or "TikTok",
        "images":   [i for i in (det.get("images") or []) if isinstance(i, str) and i.startswith("http")],
        "views":    _to_int(stats.get("views")),
        "likes":    _to_int(stats.get("likes")),
        "comments": _to_int(stats.get("comments")),
        "shares":   _to_int(stats.get("shares")),
    }


async def _via_tikwm(url: str) -> dict | None:
    t = min(int(CFG.get("api_timeout", 40)), 20)
    for attempt in range(3):
        try:
            r = await http().post("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, timeout=t)
            j = r.json()
        except Exception as e:
            log.warning("tikwm attempt %s failed: %s", attempt + 1, e)
            await asyncio.sleep(0.8)
            continue
        if j.get("code") == 0 and isinstance(j.get("data"), dict):
            return parse_tikwm(j["data"], url)
        msg = str(j.get("msg", "")).lower()
        if "limit" in msg or "second" in msg:          # free tier: 1 request / second
            await asyncio.sleep(1.3)
            continue
        log.info("tikwm rejected %s: %s", url, msg)
        return None
    return None


async def _via_hyper(url: str) -> dict | None:
    try:
        r = await http().get("https://www.api.hyper-bd.site/Tiktok/", params={"url": url},
                             timeout=min(int(CFG.get("api_timeout", 40)), 20))
        j = r.json()
        if r.status_code == 200 and j.get("ok"):
            return parse_hyper(j.get("data") or {}, url)
    except Exception as e:
        log.warning("hyper failed: %s", e)
    return None


async def fetch_tiktok(url: str) -> dict | None:
    """Try the configured provider(s); returns a normalised media dict or None."""
    active = CFG.get("active_api", "auto")
    for name, fn in (("tikwm", _via_tikwm), ("hyper", _via_hyper)):
        if active in ("auto", name):
            m = await fn(url)
            if m and (m["videos"] or m["images"] or m["audio"]):
                return m
    return None


# ── profile picture ───────────────────────────────────────────────────────────
_USERNAME_RE = re.compile(r"^@?([\w.]{1,24})$")


def extract_username(text: str) -> str | None:
    """Pull a TikTok @handle out of a bare '@user', a profile link, or plain text."""
    t = (text or "").strip()
    m = _USERNAME_RE.match(t)
    if m:
        return m.group(1)
    m = re.search(r"tiktok\.com/@([\w.]{1,24})", t, re.I)
    return m.group(1) if m else None


async def _avatar_via_tikwm(username: str) -> dict | None:
    t = min(int(CFG.get("api_timeout", 40)), 20)
    try:
        r = await http().get("https://www.tikwm.com/api/user/info",
                             params={"unique_id": f"@{username}"}, timeout=t)
        j = r.json()
    except Exception as e:
        log.warning("tikwm avatar failed: %s", e)
        return None
    if j.get("code") != 0 or not isinstance(j.get("data"), dict):
        return None
    u = (j["data"].get("user") or {})
    if not u:
        return None
    if u.get("privateAccount"):
        return {"private": True, "user": u.get("uniqueId") or username}
    pic = abs_url(u.get("avatarLarger") or u.get("avatarMedium") or u.get("avatarThumb"), "https://www.tikwm.com")
    if not pic:
        return None
    return {"private": False, "user": u.get("uniqueId") or username, "pic": pic,
            "full_name": u.get("nickname") or ""}


async def _avatar_via_scrape(username: str) -> dict | None:
    try:
        r = await http().get(f"https://www.tiktok.com/@{username}",
                             headers={"User-Agent": "facebookexternalhit/1.1",
                                      "Accept-Language": "en-US,en;q=0.9"},
                             timeout=min(int(CFG.get("api_timeout", 40)), 20))
        if r.status_code != 200:
            return None
        m = re.search(r'<meta property="og:image" content="([^"]+)"', r.text)
        if not m:
            return None
        return {"private": False, "user": username, "pic": html.unescape(m.group(1)), "full_name": ""}
    except Exception as e:
        log.warning("tiktok avatar scrape failed: %s", e)
        return None


async def fetch_avatar(username: str) -> dict | None:
    """→ {'private': True, 'user': ...}  or  {'private': False, 'user','pic','full_name'}  or None."""
    for fn in (_avatar_via_tikwm, _avatar_via_scrape):
        r = await fn(username)
        if r:
            return r
    return None


# ── secret stories ────────────────────────────────────────────────────────────
def _first_url(v, base: str = "") -> str:
    """Find the first http(s) URL inside a str / dict / list (providers differ a lot)."""
    if isinstance(v, str):
        return abs_url(v, base)
    if isinstance(v, dict):
        for k in ("url", "play", "play_addr", "playAddr", "download_addr", "downloadAddr", "url_list", "src"):
            if k in v:
                r = _first_url(v[k], base)
                if r:
                    return r
        return ""
    if isinstance(v, list):
        for x in v:
            r = _first_url(x, base)
            if r:
                return r
    return ""


def _all_urls(v, base: str = "") -> list:
    """Every image URL in a str / dict / list (a photo story can hold several pictures)."""
    if isinstance(v, str):
        u = abs_url(v, base)
        return [u] if u else []
    if isinstance(v, list):
        return [u for u in (_first_url(x, base) for x in v) if u]
    if isinstance(v, dict):
        u = _first_url(v, base)
        return [u] if u else []
    return []


def _story_list(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("stories", "story", "storyItems", "list", "items", "itemList", "videos", "data"):
            v = data.get(k)
            if isinstance(v, (list, dict)):
                r = _story_list(v)
                if r:
                    return r
    return []


def parse_story_items(data, base: str = "") -> list:
    """Normalise whatever a provider returns → [{'type','url','cover','ts','dur'}]."""
    out = []
    raw = _story_list(data)
    for it in raw:
        if not isinstance(it, dict):
            continue
        vurl = ""
        for k in ("hdplay", "play", "playAddr", "video_url", "video", "downloadAddr", "download_addr"):
            vurl = _first_url(it.get(k), base)
            if vurl:
                break
        cover = ""
        for k in ("cover", "origin_cover", "originCover", "thumbnail", "dynamicCover"):
            cover = _first_url(it.get(k), base)
            if cover:
                break
        ts = _to_int(it.get("create_time") or it.get("createTime") or it.get("time") or it.get("timestamp"))
        dur = _to_int(it.get("duration"))
        # Photo story: its `play` link is only the background MUSIC, so pictures win over `play`.
        pics = (_all_urls(it.get("images"), base) or _all_urls(it.get("image"), base)
                or _all_urls(it.get("photos"), base) or _all_urls(it.get("photo"), base))
        if pics:
            for u in pics:
                out.append({"type": "photo", "url": u, "cover": u, "ts": ts, "dur": 0})
            continue
        if vurl:
            out.append({"type": "video", "url": vurl, "cover": cover, "ts": ts, "dur": dur})
            continue
        iurl = _first_url(it.get("images")) or _first_url(it.get("image")) or _first_url(it.get("photo")) or cover
        if iurl:
            out.append({"type": "photo", "url": iurl, "cover": iurl, "ts": ts, "dur": 0})
    seen, uniq = set(), []
    for x in out:
        if x["url"] not in seen:
            seen.add(x["url"]); uniq.append(x)
    uniq.sort(key=lambda x: x["ts"] or 0)           # oldest → newest, like the TikTok app
    if len(raw) != len(uniq):
        log.info("story parse: %s raw entries → %s usable items", len(raw), len(uniq))
    return uniq


def _page_meta(data) -> tuple:
    """(next_cursor, has_more) under whatever names the provider uses · has_more None = unknown."""
    d = data if isinstance(data, dict) else {}
    nxt = None
    for k in ("cursor", "next_cursor", "nextCursor", "max_cursor", "maxCursor"):
        if d.get(k) not in (None, "", 0, "0"):
            nxt = d[k]
            break
    more = None
    for k in ("hasMore", "has_more", "hasmore", "more"):
        if k in d:
            more = bool(d[k]) and str(d[k]).strip().lower() not in ("0", "false")
            break
    return nxt, more


async def _story_via_tikwm(username: str) -> list | None:
    """ALL active stories: the endpoint answers page by page (a page holds only a few stories)."""
    t = min(int(CFG.get("api_timeout", 40)), 20)
    t0 = time.monotonic()
    items, seen, cursor, reached = [], set(), None, False
    for page in range(STORY_PAGES):
        params = {"unique_id": f"@{username}", "count": 30}
        if cursor is not None:
            params["cursor"] = cursor
        j = None
        for _ in range(2):
            try:
                r = await http().get("https://www.tikwm.com/api/user/story", params=params, timeout=t)
                j = r.json()
            except Exception as e:
                log.info("tikwm story page %s failed: %s", page, e)
                j = None
                break
            if j.get("code") == 0:
                break
            if "limit" in str(j.get("msg", "")).lower():       # tikwm: ~1 request / second
                await asyncio.sleep(1.3)
                continue
            break
        if not j or j.get("code") != 0:
            break
        reached = True
        data = j.get("data")
        got = parse_story_items(data, "https://www.tikwm.com")
        new = [x for x in got if x["url"] not in seen]
        nxt, more = _page_meta(data)
        log.info("tikwm story page %s: %s items (%s new) next=%r more=%r keys=%s", page, len(got), len(new),
                 nxt, more, sorted(data)[:12] if isinstance(data, dict) else type(data).__name__)
        for x in new:
            seen.add(x["url"])
        items += new
        if not new or more is False or time.monotonic() - t0 > 14:
            break
        if nxt is None or nxt == cursor:
            nxt = len(items)                                   # no cursor given → offset-style probe
        cursor = nxt
        await asyncio.sleep(1.1)
    if not reached:
        return None
    items.sort(key=lambda x: x["ts"] or 0)                     # oldest → newest, like the app
    return items


def _shorten(o):
    if isinstance(o, str):
        return o if len(o) <= 70 else o[:67] + "…"
    if isinstance(o, dict):
        return {k: _shorten(v) for k, v in list(o.items())[:40]}
    if isinstance(o, list):
        return [_shorten(v) for v in o[:3]] + ([f"…+{len(o) - 3} more"] if len(o) > 3 else [])
    return o


async def story_debug(username: str) -> str:
    """Admin tool: the SHAPE of the provider's answer (keys, cursors, counts) — URLs are shortened."""
    out = [f"story debug @{username}"]
    cursor = None
    for page in range(3):
        params = {"unique_id": f"@{username}", "count": 30}
        if cursor is not None:
            params["cursor"] = cursor
        try:
            r = await http().get("https://www.tikwm.com/api/user/story", params=params, timeout=20)
            j = r.json()
        except Exception as e:
            out.append(f"\npage {page}: ERROR {e}")
            break
        data = j.get("data")
        out.append(f"\n── page {page}  params={params}\ncode={j.get('code')} msg={j.get('msg')!r}")
        if isinstance(data, dict):
            out.append("scalar fields: " + json.dumps(
                {k: _shorten(v) for k, v in data.items() if not isinstance(v, (list, dict))}, ensure_ascii=False))
            for k, v in data.items():
                if isinstance(v, (list, dict)):
                    out.append(f"{type(v).__name__} '{k}': {len(v)} entries")
        lst = _story_list(data)
        out.append(f"stories found: {len(lst)}")
        out.append("create_time values: " + ", ".join(
            str(_to_int(x.get("create_time") or x.get("createTime"))) for x in lst if isinstance(x, dict)))
        for n, it in enumerate(lst[:2]):
            out.append(f"item {n}: " + json.dumps(_shorten(it), ensure_ascii=False)[:1800])
        nxt, more = _page_meta(data)
        out.append(f"next_cursor={nxt!r} has_more={more!r} → parsed: "
                   f"{[(x['type'], x['ts']) for x in parse_story_items(data, 'https://www.tikwm.com')]}")
        if nxt is None:
            break
        cursor = nxt
        await asyncio.sleep(1.2)
    return "\n".join(out)


async def _story_via_custom(username: str) -> list | None:
    if not STORY_API_URL:
        return None
    try:
        headers = json.loads(STORY_API_HEADERS) if STORY_API_HEADERS else {}
        r = await http().get(STORY_API_URL.replace("{username}", username), headers=headers,
                             timeout=min(int(CFG.get("api_timeout", 40)), 20))
        return parse_story_items(r.json()) if r.status_code == 200 else None
    except Exception as e:
        log.info("custom story provider failed: %s", e)
        return None


async def fetch_story(username: str) -> list | None:
    """→ list of stories (maybe empty = none active) · None = every provider failed."""
    reached = False
    for fn in (_story_via_custom, _story_via_tikwm):
        res = await fn(username)
        if res:
            return res
        reached = reached or res == []
    return [] if reached else None


def story_when(ts: int) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ══════════════════════════════════════════════════════════════════════════════
# 6 · MEDIA: download bytes → upload to Telegram
# ══════════════════════════════════════════════════════════════════════════════
class TooBig(Exception):
    """File exceeds the limit Telegram allows bots to upload."""


async def download_bytes(url: str, max_bytes: int = TG_MAX_BYTES, timeout: float = 40.0) -> tuple[bytes, str] | None:
    """Stream `url` into memory. → (data, content_type) · None on failure · raises TooBig."""
    headers = {"User-Agent": UA, "Referer": "https://www.tiktok.com/", "Accept": "*/*"}

    async def _run():
        async with http().stream("GET", url, headers=headers,
                                 timeout=httpx.Timeout(timeout, connect=10.0)) as r:
            if r.status_code != 200:
                log.info("download %s → HTTP %s", url[:80], r.status_code)
                return None
            ctype = r.headers.get("content-type", "").lower()
            if ctype.startswith(("text/", "application/json")):
                return None
            cl = r.headers.get("content-length", "")
            if cl.isdigit() and int(cl) > max_bytes:
                raise TooBig
            buf = bytearray()
            async for chunk in r.aiter_bytes(65536):
                buf += chunk
                if len(buf) > max_bytes:
                    raise TooBig
            return (bytes(buf), ctype) if len(buf) > 1024 else None

    try:
        return await asyncio.wait_for(_run(), timeout=timeout + 15)
    except TooBig:
        raise
    except Exception as e:
        log.info("download failed %s: %s", url[:80], e)
        return None


async def fetch_video(media: dict) -> tuple[bytes | None, str | None]:
    """Try every candidate URL (HD first). → (bytes | None, direct_url_if_too_big | None)"""
    big = None
    for url, size in media["videos"]:
        if size and size > TG_MAX_BYTES:
            big = big or url
            continue
        try:
            res = await download_bytes(url)
        except TooBig:
            big = big or url
            continue
        if res:
            return res[0], big
    return None, big


async def fetch_images(urls: list, limit: int) -> list:
    sem = asyncio.Semaphore(6)

    async def one(u):
        async with sem:
            try:
                return await download_bytes(u, max_bytes=20_000_000, timeout=25)
            except TooBig:
                return None

    got = await asyncio.gather(*(one(u) for u in urls[:limit]))
    return [g for g in got if g]


def _ext(ctype: str, default: str) -> str:
    for needle, ext in (("jpeg", "jpg"), ("jpg", "jpg"), ("png", "png"), ("webp", "webp"),
                        ("mpeg", "mp3"), ("mp3", "mp3"), ("mp4", "mp4"), ("aac", "m4a"), ("m4a", "m4a")):
        if needle in ctype:
            return ext
    return default


def sniff_kind(data: bytes) -> str:
    """What the bytes REALLY are (a CDN link may hand back audio/other for a 'video' URL):
    jpg · png · webp · heic · video · audio · unknown."""
    h = data[:16]
    if h[:3] == b"\xff\xd8\xff":
        return "jpg"
    if h[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        return "webp"
    if h[4:8] == b"ftyp":
        brand = h[8:12]
        if brand in (b"M4A ", b"M4B ", b"F4A "):
            return "audio"
        if brand[:3] == b"hei" or brand in (b"mif1", b"msf1"):
            return "heic"
        return "video"
    if h[:4] == b"\x1aE\xdf\xa3":                       # webm / mkv
        return "video"
    if h[:3] == b"ID3" or (len(h) > 1 and h[0] == 0xFF and (h[1] & 0xE0) == 0xE0) or h[:4] == b"OggS":
        return "audio"
    return "unknown"


def safe_name(s: str, default: str = "tiktok") -> str:
    s = re.sub(r"[^\w\- ]+", "", s or "", flags=re.U).strip()[:40]
    return s or default


def build_caption(m: dict) -> str:
    title = esc(clip(m["title"], 200)) or "TikTok"
    stats = (f"👁 {fmt_num(m['views'])}   ❤️ {fmt_num(m['likes'])}   "
             f"💬 {fmt_num(m['comments'])}   🔁 {fmt_num(m['shares'])}")
    return (f"🎬 <b>{title}</b>\n👤 {esc(clip(m['creator'], 60))}\n\n"
            f"<blockquote>{stats}</blockquote>\n"
            f"⚡ <a href=\"https://t.me/{BOT_USERNAME}\">@{esc(BOT_USERNAME)}</a>")


def _valid_button_url(u: str) -> bool:
    return bool(u) and len(u) <= 500 and re.match(r"^https?://[^\s]+$", u) is not None


def result_kb(lang: str, m: dict, with_audio: bool, direct: str | None = None) -> Kb:
    rows = []
    top = []
    if with_audio and m.get("audio"):
        top.append(Btn(tx(lang, "b_audio"), callback_data=f"dl_audio_{m['key']}"))
    if _valid_button_url(m.get("src", "")):
        top.append(Btn(tx(lang, "b_orig"), url=m["src"]))
    if top:
        rows.append(top)
    if direct and _valid_button_url(direct):
        rows.append([Btn(tx(lang, "b_direct"), url=direct)])
    rows.append([Btn(tx(lang, "b_delete"), callback_data="close")])
    return Kb(rows)


# ── Telegram uploaders (all have generous timeouts: uploads are slow) ────────
_UP = dict(read_timeout=120, write_timeout=120, connect_timeout=20, pool_timeout=20)


async def send_video_file(ctx, chat_id: int, m: dict, data: bytes, kb: Kb) -> None:
    name = f"{safe_name(m['creator'])}_{m['key']}.mp4"
    try:
        await ctx.bot.send_video(
            chat_id, InputFile(data, filename=name), caption=build_caption(m),
            duration=m.get("duration") or None, supports_streaming=True, reply_markup=kb, **_UP,
        )
    except BadRequest as e:                       # e.g. codec/format rejected → send as a file
        log.info("send_video rejected (%s) → document fallback", e)
        await ctx.bot.send_document(chat_id, InputFile(data, filename=name),
                                    caption=build_caption(m), reply_markup=kb, **_UP)


async def send_photo_album(ctx, chat_id: int, m: dict, files: list) -> int:
    """Send photos as albums of ≤10. Returns how many were delivered."""
    sent = 0
    cap = build_caption(m)
    for start in range(0, len(files), 10):
        chunk = files[start:start + 10]
        items = []
        for i, (data, ctype) in enumerate(chunk):
            f = InputFile(data, filename=f"{m['key']}_{start + i + 1}.{_ext(ctype, 'jpg')}")
            if start == 0 and i == 0:
                items.append(InputMediaPhoto(f, caption=cap, parse_mode=ParseMode.HTML))
            else:
                items.append(InputMediaPhoto(f))
        try:
            await ctx.bot.send_media_group(chat_id, items, **_UP)
            sent += len(chunk)
        except BadRequest as e:
            log.info("album rejected (%s) → one by one", e)
            for i, (data, ctype) in enumerate(chunk):
                fn = f"{m['key']}_{start + i + 1}.{_ext(ctype, 'jpg')}"
                kw = dict(caption=cap) if (start == 0 and i == 0) else {}
                try:
                    if len(data) <= TG_PHOTO_MAX:
                        await ctx.bot.send_photo(chat_id, InputFile(data, filename=fn), **kw, **_UP)
                    else:
                        raise BadRequest("photo too large")
                except BadRequest:
                    try:
                        await ctx.bot.send_document(chat_id, InputFile(data, filename=fn), **kw, **_UP)
                    except TelegramError as e2:
                        log.info("photo lost: %s", e2)
                        continue
                sent += 1
        if start + 10 < len(files):
            await asyncio.sleep(0.6)
    return sent


async def send_audio_file(ctx, chat_id: int, s: dict, data: bytes, ctype: str, kb: Kb | None = None) -> None:
    ext = _ext(ctype, "mp3")
    title = clip(s.get("a_title") or s.get("title") or "TikTok", 60)
    fn = f"{safe_name(title, 'audio')}.{ext}"
    performer = clip(s.get("a_author") or s.get("creator") or "TikTok", 60)
    try:
        await ctx.bot.send_audio(chat_id, InputFile(data, filename=fn), title=title, performer=performer,
                                 caption=f"🎵 <a href=\"https://t.me/{BOT_USERNAME}\">@{esc(BOT_USERNAME)}</a>",
                                 reply_markup=kb, **_UP)
    except BadRequest:
        await ctx.bot.send_document(chat_id, InputFile(data, filename=fn), reply_markup=kb, **_UP)


async def send_avatar_photo(ctx, chat_id: int, lang: str, username: str, data: bytes, ctype: str,
                            kb: Kb | None = None) -> None:
    """Deliver a profile picture. HD avatars are usually a few hundred KB → send as photo,
    but fall back to a document if Telegram's photo pipeline rejects it (rare, large PNGs)."""
    ext = _ext(ctype, "jpg")
    fn = f"{safe_name(username, 'profile')}.{ext}"
    caption = tx(lang, "avatar_caption", user=esc(username), bot=esc(BOT_USERNAME))
    try:
        if len(data) <= TG_PHOTO_MAX:
            await ctx.bot.send_photo(chat_id, InputFile(data, filename=fn), caption=caption,
                                     reply_markup=kb, **_UP)
        else:
            raise BadRequest("avatar too large for sendPhoto")
    except BadRequest:
        await ctx.bot.send_document(chat_id, InputFile(data, filename=fn), caption=caption,
                                    reply_markup=kb, **_UP)


# ══════════════════════════════════════════════════════════════════════════════
# 7 · UI BUILDERS + ACCESS GATES
# ══════════════════════════════════════════════════════════════════════════════
def plain(text: str) -> str:
    """Strip HTML → plain text (callback-query alerts don't support markup)."""
    return html.unescape(re.sub(r"<[^>]+>", "", text or ""))


def back_row(lang: str, to: str = "main_menu_render") -> list:
    return [Btn(tx(lang, "b_back"), callback_data=to)]


def cancel_row(lang: str, to: str = "panel_unified") -> list:
    return [Btn(tx(lang, "b_cancel"), callback_data=to)]


def status_word(lang: str, on: bool) -> str:
    return tx(lang, "on" if on else "off")


def menu_view(uid: int, lang: str, name: str) -> tuple[str, Kb]:
    wm = CFG.get("welcome_msg", "")
    badge = badge_of(uid)
    text = (wm.replace("{name}", esc(name)).replace("{badge}", badge) if wm
            else tx(lang, "welcome", name=esc(name), badge=badge))
    rows = [
        [Btn(tx(lang, "b_dl"), callback_data="ask_link"),
         Btn(tx(lang, "b_avatar"), callback_data="ask_avatar")],
        [Btn(tx(lang, "b_story"), callback_data="ask_story")],
        [Btn(tx(lang, "b_profile"), callback_data="show_profile"),
         Btn(tx(lang, "b_vip"), callback_data="show_vip")],
        [Btn(tx(lang, "b_lang"), callback_data="show_settings"),
         Btn(tx(lang, "b_help"), callback_data="show_help")],
        [Btn(tx(lang, "b_channel"), url=CHANNEL_URL)],
    ]
    if is_admin(uid):
        rows.append([Btn(tx(lang, "b_panel"), callback_data="panel_unified")])
    return text, Kb(rows)


def lang_buttons(prefix: str) -> list:
    return [[Btn(LANG_NAMES[c], callback_data=f"{prefix}{c}") for c in ("ku", "en", "ar")]]


async def check_join(uid: int, ctx) -> tuple[bool, list]:
    if not channels_list:
        return True, []
    missing = []
    for ch in channels_list:
        try:
            m = await ctx.bot.get_chat_member(ch, uid)
            if m.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED) or \
               (m.status == ChatMemberStatus.RESTRICTED and getattr(m, "is_member", True) is False):
                missing.append(ch)
        except TelegramError as e:      # bot not admin / channel gone → fail open, but log it
            log.warning("check_join(%s) failed: %s", ch, e)
    return not missing, missing


def join_view(lang: str, missing: list) -> tuple[str, Kb]:
    rows = [[Btn(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in missing]
    rows.append([Btn(tx(lang, "b_joined"), callback_data="check_join_btn")])
    return tx(lang, "force_join"), Kb(rows)


async def gate_message(update: Update, ctx, uid: int, lang: str) -> bool:
    """True → user may continue. Otherwise the right notice was already sent."""
    msg = update.effective_message
    if is_blocked(uid):
        await msg.reply_text(tx(lang, "blocked_msg"))
        return False
    if CFG.get("maintenance") and not is_admin(uid):
        await msg.reply_text(tx(lang, "maintenance_msg", dev=esc(DEV)))
        return False
    ok, missing = await check_join(uid, ctx)
    if not ok and not bypass_join(uid):
        text, kb = join_view(lang, missing)
        await msg.reply_text(text, reply_markup=kb)
        return False
    return True


async def safe_edit(message, text: str, kb: Kb | None = None) -> None:
    try:
        await message.edit_text(text, reply_markup=kb)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            log.info("safe_edit: %s", e)
    except TelegramError as e:
        log.info("safe_edit: %s", e)


async def user_ids() -> list:
    """All user IDs via Firebase `shallow=true` (keys only, tiny payload)."""
    if not DB_URL:
        return []
    try:
        r = await http().get(_fb("users"), params={**_auth(), "shallow": "true"}, timeout=15)
        if r.status_code == 200 and isinstance(r.json(), dict):
            return [int(k) for k in r.json().keys() if str(k).isdigit()]
    except Exception as e:
        log.warning("user_ids failed: %s", e)
    return []


async def db_ping() -> tuple[bool, int]:
    """(reachable, milliseconds) — cheap shallow read used by /ping and the status page."""
    if not DB_URL:
        return False, 0
    t0 = time.perf_counter()
    try:
        r = await http().get(_fb("sys/cfg/total_dl"), params={**_auth(), "shallow": "true"}, timeout=8)
        return r.status_code == 200, int((time.perf_counter() - t0) * 1000)
    except Exception:
        return False, int((time.perf_counter() - t0) * 1000)


async def chat_action(ctx, chat_id: int, action: str) -> None:
    try:
        await ctx.bot.send_chat_action(chat_id, action)
    except TelegramError:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# 8 · COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud, lang = await ensure_user(update, ctx)
    if not await gate_message(update, ctx, uid, lang):
        return
    text, kb = menu_view(uid, lang, update.effective_user.first_name or "")
    await update.effective_message.reply_text(text, reply_markup=kb)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ud, lang = await ensure_user(update, ctx)
    await update.effective_message.reply_text(
        tx(lang, "help", dev=esc(DEV)), reply_markup=Kb([back_row(lang)]))


async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    ok, ms = await db_ping()
    await update.effective_message.reply_text(
        f"✅ <b>PONG</b>\n<blockquote>🗄 Firebase: {'✅' if ok else '❌'} · {ms} ms\n"
        f"👥 Admins: {len(admins_set)} · 💎 VIP: {len(vip_set)} · 🚫 {len(blocked_set)}</blockquote>")


# ══════════════════════════════════════════════════════════════════════════════
# 9 · CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════
class CB:
    """Per-callback helper: answers the query exactly once, edits safely."""

    def __init__(self, update: Update, ctx, lang: str):
        self.update, self.ctx, self.lang = update, ctx, lang
        self.q = update.callback_query
        self.uid = self.q.from_user.id
        self.name = self.q.from_user.first_name or ""
        self.answered = False

    async def answer(self, text: str | None = None, alert: bool = False) -> None:
        if self.answered:
            return
        self.answered = True
        try:
            await self.q.answer(plain(text)[:190] if text else None, show_alert=alert)
        except TelegramError:
            pass

    async def edit(self, text: str, kb: Kb | None = None) -> None:
        await safe_edit(self.q.message, text, kb)

    def t(self, key: str, **kw) -> str:
        return tx(self.lang, key, **kw)


def _tail_id(data: str) -> int | None:
    tail = data.rsplit("_", 1)[-1]
    return int(tail) if tail.lstrip("-").isdigit() else None


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ud, lang = await ensure_user(update, ctx)
    cb = CB(update, ctx, lang)
    try:
        await route(cb, update.callback_query.data or "")
    finally:
        await cb.answer()          # always stop the client-side spinner


async def route(cb: CB, data: str):
    uid, lang = cb.uid, cb.lang

    # ── gates ────────────────────────────────────────────────────────────────
    if is_blocked(uid):
        return await cb.answer(cb.t("blocked_msg"), True)
    if CFG.get("maintenance") and not is_admin(uid):
        return await cb.answer(cb.t("maintenance_msg", dev=DEV), True)
    if data == "noop":
        return

    # ── owner quick actions from the "new user" notification ─────────────────
    if data.startswith("quick_"):
        if not is_owner(uid):
            return
        _, action, raw = data.split("_", 2)
        tid = int(raw)
        await load_cfg(force=True)
        if action == "blk":
            if is_super(tid):
                return await cb.answer(cb.t("cant_touch"), True)
            blocked_set.add(tid); await save_sys("blocked")
            return await cb.answer(cb.t("act_blocked", id=tid), True)
        if action == "vip":
            await grant_vip(tid, True)
            return await cb.answer(cb.t("act_vip_added", id=tid), True)
        if action == "adm":
            admins_set.add(tid); await save_sys("admins")
            return await cb.answer(cb.t("act_adm_added", id=tid), True)
        if action == "inf":
            return await cb.answer(await userinfo_text(cb.lang, tid), True)
        return

    # ── user area ────────────────────────────────────────────────────────────
    if data in ("main_menu_render", "check_join_btn"):
        ok, _ = await check_join(uid, cb.ctx)
        if not ok and not bypass_join(uid):
            return await cb.answer(cb.t("not_joined"), True)
        text, kb = menu_view(uid, lang, cb.name)
        return await cb.edit(text, kb)

    if data == "close":
        try:
            await cb.q.message.delete()
        except TelegramError:
            pass
        return

    if data == "ask_link":
        await cb.answer()
        return await cb.q.message.reply_text(cb.t("ask_link_prompt"), reply_markup=ForceReply(selective=True))

    if data == "ask_avatar":
        await cb.answer()
        return await cb.q.message.reply_text(cb.t("ask_avatar_prompt"), reply_markup=ForceReply(selective=True))

    if data == "ask_story":
        await cb.answer()
        return await cb.q.message.reply_text(cb.t("ask_story_prompt"), reply_markup=ForceReply(selective=True))

    if data == "story_more":
        await cb.answer()
        s = await session_get(f"story_{uid}")
        items = s.get("items") if s else None
        if isinstance(items, dict):                      # Firebase may hand a list back as {"0":…, "1":…}
            items = [items[k] for k in sorted(items, key=lambda x: int(x))]
        if not items:
            return await cb.q.message.reply_text(cb.t("story_expired"))
        try:
            await cb.q.message.edit_reply_markup(reply_markup=None)    # a used button can't be tapped twice
        except TelegramError:
            pass
        s["items"] = items
        return await process_story(cb.update, cb.ctx, s.get("user", ""), cb.lang, time.monotonic(), resume=s)

    if data == "show_profile":
        ud = await db_get(f"users/{uid}") or {}
        text = cb.t("profile", id=uid, name=esc(cb.name),
                    user=f"@{esc(cb.q.from_user.username)}" if cb.q.from_user.username else "—",
                    rank=cb.t(f"rank_{rank_key(uid)}"), ulang=LANG_NAMES.get(lang, lang),
                    dl=fmt_num(ud.get("dl", 0)), date=esc(ud.get("date", "—")))
        return await cb.edit(text, Kb([back_row(lang)]))

    if data == "show_vip":
        return await cb.edit(cb.t("vip_info", dev=esc(DEV)), Kb([back_row(lang)]))

    if data == "show_help":
        return await cb.edit(cb.t("help", dev=esc(DEV)), Kb([back_row(lang)]))

    if data == "show_settings":
        return await cb.edit(f"{cb.t('lang_title')}\n\n{cb.t('lang_current', cur=LANG_NAMES.get(lang, '?'))}",
                             Kb(lang_buttons("set_lang_") + [back_row(lang)]))

    if data.startswith("set_lang_"):
        chosen = data[len("set_lang_"):]
        if chosen in L:
            await db_put(f"users/{uid}/lang", chosen)
            cb.lang = chosen
            text, kb = menu_view(uid, chosen, cb.name)
            await cb.answer(tx(chosen, "lang_saved"))
            return await cb.edit(text, kb)
        return

    if data.startswith("dl_audio_"):
        return await send_audio_from_session(cb, data[len("dl_audio_"):])

    # ── staff areas ──────────────────────────────────────────────────────────
    if is_admin(uid) and data != "noop":
        await set_wait_clear(uid)          # any navigation cancels a pending "type the ID" prompt
    if data == "panel_unified" or data.startswith("adm_"):
        return await route_admin(cb, data) if is_admin(uid) else await cb.answer(cb.t("no_perm"), True)
    if data.startswith(("sup_", "set_bot_lang_")):
        return await route_super(cb, data) if is_super(uid) else await cb.answer(cb.t("no_perm"), True)
    if data.startswith("own_"):
        return await route_owner(cb, data) if is_owner(uid) else await cb.answer(cb.t("no_perm"), True)


# ── audio on demand ──────────────────────────────────────────────────────────
async def send_audio_from_session(cb: CB, key: str):
    started = time.monotonic()
    s = await session_get(key)
    if not s or not s.get("audio"):
        return await cb.answer(cb.t("session_expired"), True)
    await cb.answer(plain(cb.t("st_audio", bar="")).strip())
    chat_id = cb.q.message.chat_id
    await chat_action(cb.ctx, chat_id, ChatAction.UPLOAD_VOICE)
    try:
        res = await download_bytes(s["audio"])
    except TooBig:
        res = None
    if not res:
        return await cb.ctx.bot.send_message(chat_id, cb.t("no_audio"))
    await send_audio_file(cb.ctx, chat_id, s, res[0], res[1], Kb([[Btn(cb.t("b_delete"), callback_data="close")]]))


# ── shared admin helpers ─────────────────────────────────────────────────────
async def user_exists(uid: int) -> bool:
    return await db_get(f"users/{uid}/date") is not None


async def grant_vip(tid: int, on: bool) -> None:
    await load_cfg(force=True)
    (vip_set.add if on else vip_set.discard)(tid)
    await save_sys("vips")
    if await user_exists(tid):
        await db_put(f"users/{tid}/vip", on)


async def userinfo_text(lang: str, tid: int) -> str:
    ud = await db_get(f"users/{tid}")
    if not isinstance(ud, dict):
        return tx(lang, "user_not_found")
    return tx(lang, "userinfo", name=esc(ud.get("name", "—")),
              user=f"@{esc(ud['user'])}" if ud.get("user") else "—", id=tid,
              rank=tx(lang, f"rank_{rank_key(tid)}"),
              blocked=tx(lang, "yes") if tid in blocked_set else tx(lang, "no"),
              lang=LANG_NAMES.get(ud.get("lang"), ud.get("lang", "—")),
              dl=fmt_num(ud.get("dl", 0)), date=esc(ud.get("date", "—")))


def confirm_kb(lang: str, yes_cb: str, no_cb: str) -> Kb:
    return Kb([[Btn(tx(lang, "b_confirm"), callback_data=yes_cb)], [Btn(tx(lang, "b_deny"), callback_data=no_cb)]])


async def list_menu(cb: CB, title_key: str, ids: list, back_to: str, extra_rows: list):
    """Render a removable list (admins / VIPs / super admins)."""
    lines = [f"• {await display_name(i)}" for i in ids]
    text = cb.t(title_key, count=len(ids)) + ("\n\n" + "\n".join(lines) if lines else "")
    await cb.edit(text, Kb(extra_rows + [back_row(cb.lang, back_to)]))


# ── ADMIN ────────────────────────────────────────────────────────────────────
async def show_panel(cb: CB):
    uid, lang = cb.uid, cb.lang
    n_users = len(await user_ids())
    rows = [
        [Btn(cb.t("b_adm_stats"), callback_data="adm_stats"),
         Btn(cb.t("b_adm_broadcast"), callback_data="adm_broadcast")],
        [Btn(cb.t("b_adm_block"), callback_data="adm_block"),
         Btn(cb.t("b_adm_unblock"), callback_data="adm_unblock")],
        [Btn(cb.t("b_adm_info"), callback_data="adm_userinfo")],
    ]
    if is_super(uid):
        rows.append([Btn("▬▬▬  🌌  ▬▬▬", callback_data="noop")])
        rows.append([Btn(cb.t("b_sup_admins"), callback_data="sup_admins"),
                     Btn(cb.t("b_sup_vip"), callback_data="sup_vips")])
        rows.append([Btn(cb.t("b_sup_channels"), callback_data="sup_channels"),
                     Btn(cb.t("b_sup_api"), callback_data="sup_api_settings")])
        rows.append([Btn(cb.t("b_sup_maint", status=status_word(lang, CFG.get("maintenance", False))),
                         callback_data="sup_toggle_maint")])
        rows.append([Btn(cb.t("b_sup_audio", status=status_word(lang, CFG.get("auto_audio", False))),
                         callback_data="sup_toggle_audio")])
        rows.append([Btn(cb.t("b_sup_botlang"), callback_data="sup_bot_lang")])
    if is_owner(uid):
        rows.append([Btn("▬▬▬  👑  ▬▬▬", callback_data="noop")])
        rows.append([Btn(cb.t("b_own_super"), callback_data="own_super_adms"),
                     Btn(cb.t("b_own_welcome"), callback_data="own_welcome")])
        rows.append([Btn(cb.t("b_own_reset"), callback_data="own_reset_stats"),
                     Btn(cb.t("b_own_backup"), callback_data="own_backup")])
    rows.append(back_row(lang))
    await cb.edit(cb.t("panel_title", users=fmt_num(n_users), vip=len(vip_set),
                       blocked=len(blocked_set), dl=fmt_num(CFG.get("total_dl", 0))), Kb(rows))


async def set_wait_clear(uid: int) -> None:
    if DB_URL:
        await db_del(f"wait/{uid}")


async def ask_input(cb: CB, state: str, text: str, back_to: str):
    await set_wait(cb.uid, state)
    await cb.edit(text, Kb([cancel_row(cb.lang, back_to)]))


async def route_admin(cb: CB, data: str):
    lang = cb.lang
    if data == "panel_unified":
        return await show_panel(cb)

    if data == "adm_stats":
        users = len(await user_ids())
        text = cb.t("adm_stats", users=fmt_num(users), vip=len(vip_set), blocked=len(blocked_set),
                    admins=len(admins_set), channels=len(channels_list), dl=fmt_num(CFG.get("total_dl", 0)),
                    maint=status_word(lang, CFG.get("maintenance", False)), api=esc(CFG.get("active_api", "auto")))
        return await cb.edit(text, Kb([[Btn(cb.t("b_refresh"), callback_data="adm_stats")], back_row(lang, "panel_unified")]))

    if data == "adm_broadcast":
        return await ask_input(cb, "broadcast", cb.t("adm_broadcast_ask"), "panel_unified")
    if data == "adm_block":
        return await ask_input(cb, "blk_add", cb.t("adm_block_ask", write_id=cb.t("write_id")), "panel_unified")
    if data == "adm_unblock":
        return await ask_input(cb, "blk_rm", cb.t("adm_unblock_ask", write_id=cb.t("write_id")), "panel_unified")
    if data == "adm_userinfo":
        return await ask_input(cb, "info", cb.t("adm_info_ask", write_id=cb.t("write_id")), "panel_unified")


# ── SUPER ────────────────────────────────────────────────────────────────────
async def route_super(cb: CB, data: str):
    lang = cb.lang

    if data == "sup_toggle_maint":
        await set_cfg(maintenance=not CFG.get("maintenance", False))
        return await show_panel(cb)

    if data == "sup_toggle_audio":
        await set_cfg(auto_audio=not CFG.get("auto_audio", False))
        return await show_panel(cb)

    if data == "sup_bot_lang":
        cur = LANG_NAMES.get(CFG.get("default_lang", "ku"), "?")
        return await cb.edit(f"{cb.t('bot_lang_title')}\n\n{cb.t('lang_current', cur=cur)}",
                             Kb(lang_buttons("set_bot_lang_") + [back_row(lang, "panel_unified")]))

    if data.startswith("set_bot_lang_"):
        chosen = data[len("set_bot_lang_"):]
        if chosen in L:
            await set_cfg(default_lang=chosen)
            await cb.answer(cb.t("bot_lang_saved", lang=LANG_NAMES[chosen]), True)
        return await show_panel(cb)

    if data == "sup_api_settings":
        act = CFG.get("active_api", "auto")
        mark = lambda k: "✅ " if act == k else ""
        return await cb.edit(cb.t("api_title"), Kb([
            [Btn(f"{mark('auto')}Auto (TikWM → Hyper)", callback_data="sup_setapi_auto")],
            [Btn(f"{mark('tikwm')}TikWM", callback_data="sup_setapi_tikwm")],
            [Btn(f"{mark('hyper')}Hyper", callback_data="sup_setapi_hyper")],
            back_row(lang, "panel_unified"),
        ]))

    if data.startswith("sup_setapi_"):
        choice = data[len("sup_setapi_"):]
        if choice in ("auto", "tikwm", "hyper"):
            await set_cfg(active_api=choice)
        return await route_super(cb, "sup_api_settings")

    # ── admins ───────────────────────────────────────────────────────────────
    if data == "sup_admins":
        await load_cfg(force=True)
        ids = sorted(admins_set - super_admins_set - {OWNER_ID})
        rows = [[Btn(cb.t("b_add"), callback_data="sup_add_adm"), Btn(cb.t("b_remove"), callback_data="sup_rm_adm_list")]]
        return await list_menu(cb, "sup_admins_title", ids, "panel_unified", rows)

    if data == "sup_add_adm":
        return await ask_input(cb, "adm_add", cb.t("sup_add_adm_ask", write_id=cb.t("write_id")), "sup_admins")

    if data == "sup_rm_adm_list":
        ids = sorted(admins_set - super_admins_set - {OWNER_ID})
        if not ids:
            return await cb.answer("—", True)
        rows = [[Btn(f"❌ {plain(await display_name(i))}", callback_data=f"sup_cf_adm_{i}")] for i in ids]
        return await cb.edit(cb.t("sup_admins_title", count=len(ids)), Kb(rows + [back_row(lang, "sup_admins")]))

    if data.startswith("sup_cf_adm_"):
        tid = _tail_id(data)
        return await cb.edit(cb.t("confirm_rm", what=await display_name(tid)),
                             confirm_kb(lang, f"sup_do_adm_{tid}", "sup_admins"))

    if data.startswith("sup_do_adm_"):
        tid = _tail_id(data)
        await load_cfg(force=True)
        if tid not in (OWNER_ID,) and tid not in super_admins_set:
            admins_set.discard(tid); await save_sys("admins")
        await cb.answer(cb.t("act_adm_removed", id=tid), True)
        return await route_super(cb, "sup_admins")

    # ── VIPs ─────────────────────────────────────────────────────────────────
    if data == "sup_vips":
        await load_cfg(force=True)
        ids = sorted(vip_set - super_admins_set - {OWNER_ID})
        rows = [[Btn(cb.t("b_add_vip"), callback_data="sup_add_vip"), Btn(cb.t("b_rm_vip"), callback_data="sup_rm_vip_list")]]
        return await list_menu(cb, "sup_vip_title", ids, "panel_unified", rows)

    if data == "sup_add_vip":
        return await ask_input(cb, "vip_add", cb.t("sup_add_vip_ask", write_id=cb.t("write_id")), "sup_vips")

    if data == "sup_rm_vip_list":
        ids = sorted(vip_set - super_admins_set - {OWNER_ID})
        if not ids:
            return await cb.answer(cb.t("sup_ch_empty"), True)
        rows = [[Btn(f"❌ {plain(await display_name(i))}", callback_data=f"sup_cf_vip_{i}")] for i in ids]
        return await cb.edit(cb.t("sup_vip_title", count=len(ids)), Kb(rows + [back_row(lang, "sup_vips")]))

    if data.startswith("sup_cf_vip_"):
        tid = _tail_id(data)
        return await cb.edit(cb.t("confirm_rm", what=await display_name(tid)),
                             confirm_kb(lang, f"sup_do_vip_{tid}", "sup_vips"))

    if data.startswith("sup_do_vip_"):
        tid = _tail_id(data)
        await grant_vip(tid, False)
        await cb.answer(cb.t("act_vip_removed", id=tid), True)
        return await route_super(cb, "sup_vips")

    # ── channels ─────────────────────────────────────────────────────────────
    if data == "sup_channels":
        await load_cfg(force=True)
        body = "\n".join(f"• {esc(c)}" for c in channels_list) or cb.t("sup_ch_empty")
        rows = [[Btn(cb.t("b_add"), callback_data="sup_add_ch"), Btn(cb.t("b_remove"), callback_data="sup_rm_ch_list")],
                back_row(lang, "panel_unified")]
        return await cb.edit(f"{cb.t('sup_ch_title', count=len(channels_list))}\n\n{body}", Kb(rows))

    if data == "sup_add_ch":
        return await ask_input(cb, "add_ch", cb.t("sup_add_ch_ask", write_ch=cb.t("write_ch")), "sup_channels")

    if data == "sup_rm_ch_list":
        if not channels_list:
            return await cb.answer(cb.t("sup_ch_empty"), True)
        rows = [[Btn(f"❌ {c}", callback_data=f"sup_cf_ch_{c}")] for c in channels_list]
        return await cb.edit(cb.t("sup_ch_remove_q"), Kb(rows + [back_row(lang, "sup_channels")]))

    if data.startswith("sup_cf_ch_"):
        ch = data[len("sup_cf_ch_"):]
        return await cb.edit(cb.t("confirm_rm", what=esc(ch)), confirm_kb(lang, f"sup_do_ch_{ch}", "sup_channels"))

    if data.startswith("sup_do_ch_"):
        ch = data[len("sup_do_ch_"):]
        await load_cfg(force=True)
        if ch in channels_list:
            channels_list.remove(ch); await save_sys("channels")
        return await route_super(cb, "sup_channels")


# ── OWNER ────────────────────────────────────────────────────────────────────
async def route_owner(cb: CB, data: str):
    lang = cb.lang

    if data == "own_super_adms":
        await load_cfg(force=True)
        ids = sorted(super_admins_set - {OWNER_ID})
        rows = [[Btn(cb.t("b_add"), callback_data="own_add_sup"), Btn(cb.t("b_remove"), callback_data="own_rm_sup_list")]]
        return await list_menu(cb, "own_super_title", ids, "panel_unified", rows)

    if data == "own_add_sup":
        return await ask_input(cb, "sup_add", cb.t("own_add_sup_ask", write_id=cb.t("write_id")), "own_super_adms")

    if data == "own_rm_sup_list":
        ids = sorted(super_admins_set - {OWNER_ID})
        if not ids:
            return await cb.answer("—", True)
        rows = [[Btn(f"❌ {plain(await display_name(i))}", callback_data=f"own_cf_sup_{i}")] for i in ids]
        return await cb.edit(cb.t("own_super_title", count=len(ids)), Kb(rows + [back_row(lang, "own_super_adms")]))

    if data.startswith("own_cf_sup_"):
        tid = _tail_id(data)
        return await cb.edit(cb.t("confirm_rm", what=await display_name(tid)),
                             confirm_kb(lang, f"own_do_sup_{tid}", "own_super_adms"))

    if data.startswith("own_do_sup_"):
        tid = _tail_id(data)
        await load_cfg(force=True)
        super_admins_set.discard(tid); await save_sys("super_admins")
        await cb.answer(cb.t("act_sup_removed", id=tid), True)
        return await route_owner(cb, "own_super_adms")

    if data == "own_welcome":
        rows = [[Btn(cb.t("b_clear"), callback_data="own_clear_welcome")], cancel_row(lang)]
        await set_wait(cb.uid, "set_welcome")
        return await cb.edit(cb.t("write_welcome"), Kb(rows))

    if data == "own_clear_welcome":
        await set_cfg(welcome_msg="")
        return await show_panel(cb)

    if data == "own_reset_stats":
        return await cb.edit(cb.t("reset_confirm"), confirm_kb(lang, "own_do_reset", "panel_unified"))

    if data == "own_do_reset":
        await set_cfg(total_dl=0, total_users=0)
        await cb.answer(cb.t("reset_done"), True)
        return await show_panel(cb)

    if data == "own_backup":
        await cb.answer(cb.t("backup_prep"))
        payload = {"time": now_str(), "cfg": CFG, "users": await all_users(),
                   "sys": {k: fn() for k, fn in _SYS_KEYS.items()}}
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        name = f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        await cb.ctx.bot.send_document(cb.uid, InputFile(raw, filename=name), **_UP)


# ══════════════════════════════════════════════════════════════════════════════
# 10 · ADMIN TEXT PROMPTS  (state lives in Firebase → works across serverless instances)
# ══════════════════════════════════════════════════════════════════════════════
_NEEDS = {  # prompt → minimum role
    "broadcast": is_admin, "blk_add": is_admin, "blk_rm": is_admin, "info": is_admin,
    "adm_add": is_super, "vip_add": is_super, "add_ch": is_super,
    "sup_add": is_owner, "set_welcome": is_owner,
}


async def _copy_one(ctx, target: int, msg) -> bool:
    for attempt in range(2):
        try:
            await ctx.bot.copy_message(chat_id=target, from_chat_id=msg.chat_id, message_id=msg.message_id)
            return True
        except RetryAfter as e:
            await asyncio.sleep(min(float(e.retry_after), 5.0))
        except TelegramError:
            return False
    return False


async def run_broadcast(ctx, msg, lang: str, started: float) -> None:
    targets = await user_ids()
    status = await msg.reply_text(tx(lang, "broadcast_start", total=len(targets)))
    ok = fail = done = 0
    BATCH = 20                                   # ≈ 20 msg/s, below Telegram's 30/s limit
    while done < len(targets) and deadline_left(started) > 6:
        batch = targets[done:done + BATCH]
        res = await asyncio.gather(*(_copy_one(ctx, t, msg) for t in batch))
        ok += sum(res); fail += len(res) - sum(res); done += len(batch)
        if (done // BATCH) % 5 == 0 and done < len(targets):
            await safe_edit(status, tx(lang, "broadcast_progress", done=done, total=len(targets)))
        await asyncio.sleep(1.0)
    left = len(targets) - done
    await safe_edit(status, tx(lang, "broadcast_partial", ok=ok, fail=fail, left=left) if left
                    else tx(lang, "broadcast_done", ok=ok, fail=fail))


async def handle_prompt(update: Update, ctx, state: str, lang: str, started: float) -> None:
    msg, uid = update.effective_message, update.effective_user.id
    txt = (msg.text or "").strip()
    need = _NEEDS.get(state)
    if not need or not need(uid):
        return

    if state == "broadcast":
        return await run_broadcast(ctx, msg, lang, started)

    if state == "set_welcome":
        await set_cfg(welcome_msg=msg.text_html or "")
        return await msg.reply_text(tx(lang, "welcome_set"))

    if state == "add_ch":
        ch = txt if txt.startswith("@") else ""
        if not re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{3,31}", ch):
            return await msg.reply_text(tx(lang, "act_ch_bad"))
        try:
            me = await ctx.bot.get_chat_member(ch, ctx.bot.id)
            good = me.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
        except TelegramError:
            good = False
        if not good:
            return await msg.reply_text(tx(lang, "ch_not_admin", ch=esc(ch)))
        await load_cfg(force=True)
        if ch not in channels_list:
            channels_list.append(ch); await save_sys("channels")
        return await msg.reply_text(tx(lang, "sup_ch_added", ch=esc(ch)))

    # ── everything below expects a numeric Telegram ID ───────────────────────
    if not txt.isdigit():
        return await msg.reply_text(tx(lang, "invalid_id"))
    tid = int(txt)
    await load_cfg(force=True)

    if state == "blk_add":
        if is_super(tid) or (is_admin(tid) and not is_super(uid)):
            return await msg.reply_text(tx(lang, "cant_touch"))
        blocked_set.add(tid); await save_sys("blocked")
        return await msg.reply_text(tx(lang, "act_blocked", id=tid))
    if state == "blk_rm":
        blocked_set.discard(tid); await save_sys("blocked")
        return await msg.reply_text(tx(lang, "act_unblocked", id=tid))
    if state == "info":
        return await msg.reply_text(await userinfo_text(lang, tid))
    if state == "adm_add":
        admins_set.add(tid); await save_sys("admins")
        return await msg.reply_text(tx(lang, "act_adm_added", id=tid))
    if state == "sup_add":
        super_admins_set.add(tid); admins_set.add(tid); await save_sys("super_admins", "admins")
        return await msg.reply_text(tx(lang, "act_sup_added", id=tid))
    if state == "vip_add":
        await grant_vip(tid, True)
        return await msg.reply_text(tx(lang, "act_vip_added", id=tid))


# ══════════════════════════════════════════════════════════════════════════════
# 11 · THE DOWNLOAD PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
_last_error_ping = 0.0


async def report_error(ctx, err: BaseException, where: str = "") -> None:
    """Log + tell the owner (max once a minute per instance, so we never spam)."""
    global _last_error_ping
    log.error("ERROR %s: %s\n%s", where, err, "".join(traceback.format_exception(err))[-1500:])
    if time.time() - _last_error_ping < 60:
        return
    _last_error_ping = time.time()
    try:
        await ctx.bot.send_message(
            OWNER_ID, f"⚠️ <b>Error</b> {esc(where)}\n<code>{esc(type(err).__name__)}: {esc(clip(str(err), 300))}</code>")
    except TelegramError:
        pass


async def process_link(update: Update, ctx, url: str, lang: str, started: float) -> None:
    msg, uid, chat_id = update.effective_message, update.effective_user.id, update.effective_chat.id

    if not await gate_message(update, ctx, uid, lang):
        return
    if not await acquire_lock(uid):
        return await msg.reply_text(tx(lang, "busy_msg"))

    status = None
    try:
        status = await msg.reply_text(tx(lang, "st_search", bar=bar(1)))
        media = await fetch_tiktok(url)
        if not media:
            return await safe_edit(status, tx(lang, "invalid_link"))

        # remember what the ".MP3" button needs (also acts as a tiny cache)
        if media["audio"]:
            await session_save(media["key"], {k: media[k] for k in ("audio", "a_title", "a_author", "title", "creator", "src")})

        await safe_edit(status, tx(lang, "st_download", bar=bar(3)))
        auto_audio = bool(CFG.get("auto_audio"))
        kb = result_kb(lang, media, with_audio=not auto_audio)
        delivered = False

        if media["images"]:                                            # ── photo post
            limit = int(CFG.get("vip_photos" if is_vip(uid) else "max_photos", 15))
            files = await fetch_images(media["images"], limit)
            if not files:
                return await safe_edit(status, tx(lang, "dl_fail"))
            await safe_edit(status, tx(lang, "st_upload", bar=bar(4)))
            await chat_action(ctx, chat_id, ChatAction.UPLOAD_PHOTO)
            n = await send_photo_album(ctx, chat_id, media, files)
            if n:
                await ctx.bot.send_message(chat_id, tx(lang, "photos_done", n=n), reply_markup=kb)
                delivered = True

        elif media["videos"]:                                          # ── video post
            data, big = await fetch_video(media)
            if data:
                await safe_edit(status, tx(lang, "st_upload", bar=bar(4)))
                await chat_action(ctx, chat_id, ChatAction.UPLOAD_VIDEO)
                await send_video_file(ctx, chat_id, media, data, kb)
                delivered = True
            elif big:                                                  # > 50 MB → link button
                await ctx.bot.send_message(chat_id, f"{build_caption(media)}\n\n{tx(lang, 'too_big')}",
                                           reply_markup=result_kb(lang, media, not auto_audio, direct=big))
                delivered = True

        elif media["audio"]:                                           # ── sound-only result
            auto_audio = True

        # optional automatic MP3 (toggle in the panel) — only if we still have time
        if auto_audio and media["audio"] and (not delivered or deadline_left(started) > 12):
            try:
                res = await download_bytes(media["audio"], timeout=max(10.0, min(30.0, deadline_left(started) - 8)))
            except TooBig:
                res = None
            if res:
                await send_audio_file(ctx, chat_id, media, res[0], res[1],
                                      Kb([[Btn(tx(lang, "b_delete"), callback_data="close")]]))
                delivered = True

        if not delivered:
            return await safe_edit(status, tx(lang, "dl_fail"))

        await db_incr("sys/cfg/total_dl")
        await db_incr(f"users/{uid}/dl")
        try:
            await status.delete()
        except TelegramError:
            pass

    except Exception as e:                                              # noqa: BLE001 — user gets a clean message
        await report_error(ctx, e, "process_link")
        if status:
            await safe_edit(status, tx(lang, "dl_fail"))
    finally:
        await release_lock(uid)


async def process_avatar(update: Update, ctx, username: str, lang: str, started: float) -> None:
    """Fetch and deliver a public TikTok account's HD profile picture."""
    msg, uid, chat_id = update.effective_message, update.effective_user.id, update.effective_chat.id

    if not await gate_message(update, ctx, uid, lang):
        return
    if not await acquire_lock(uid):
        return await msg.reply_text(tx(lang, "busy_msg"))

    status = None
    try:
        status = await msg.reply_text(tx(lang, "st_search", bar=bar(1)))
        info = await fetch_avatar(username)
        if not info:
            return await safe_edit(status, tx(lang, "no_avatar"))
        if info.get("private"):
            return await safe_edit(status, tx(lang, "private_account"))

        await safe_edit(status, tx(lang, "st_avatar", bar=bar(3)))
        try:
            res = await download_bytes(info["pic"], max_bytes=20_000_000, timeout=25)
        except TooBig:
            res = None
        if not res:
            return await safe_edit(status, tx(lang, "no_avatar"))

        await safe_edit(status, tx(lang, "st_upload", bar=bar(4)))
        await chat_action(ctx, chat_id, ChatAction.UPLOAD_PHOTO)
        await send_avatar_photo(ctx, chat_id, lang, info["user"], res[0], res[1],
                                Kb([[Btn(tx(lang, "b_delete"), callback_data="close")]]))

        await db_incr("sys/cfg/total_dl")
        await db_incr(f"users/{uid}/dl")
        try:
            await status.delete()
        except TelegramError:
            pass

    except Exception as e:                                              # noqa: BLE001
        await report_error(ctx, e, "process_avatar")
        if status:
            await safe_edit(status, tx(lang, "dl_fail"))
    finally:
        await release_lock(uid)


def story_kb(lang: str, left: int = 0) -> Kb:
    rows = []
    if left > 0:
        rows.append([Btn(tx(lang, "b_story_more", left=left), callback_data="story_more")])
    rows.append([Btn(tx(lang, "b_story_again"), callback_data="ask_story")])
    rows.append([Btn(tx(lang, "b_delete"), callback_data="close")])
    return Kb(rows)


async def _send_story_item(ctx, chat_id: int, username: str, lang: str, it: dict, i: int, total: int) -> bool:
    """Download ONE story item and upload it to Telegram → True when it was delivered."""
    await chat_action(ctx, chat_id, ChatAction.UPLOAD_VIDEO if it.get("type") == "video" else ChatAction.UPLOAD_PHOTO)
    try:
        res = await download_bytes(it["url"], max_bytes=TG_MAX_BYTES, timeout=30)
    except TooBig:
        res = None
    if not res:
        return False
    data, ctype = res
    kind = sniff_kind(data)
    if kind == "audio":                              # link gave only the music → show the picture instead
        res2 = None
        if it.get("cover"):
            try:
                res2 = await download_bytes(it["cover"], max_bytes=20_000_000, timeout=20)
            except TooBig:
                res2 = None
        if not res2 or sniff_kind(res2[0]) not in ("jpg", "png", "webp"):
            return False
        data, ctype = res2
        kind = sniff_kind(data)
    is_video = kind == "video" or (kind == "unknown" and it.get("type") == "video"
                                   and not ctype.startswith("image"))
    cap = tx(lang, "story_caption", user=esc(username), i=i, n=total,
             when=story_when(it.get("ts") or 0), bot=esc(BOT_USERNAME))
    name = f"{safe_name(username)}_story_{i}"
    try:
        if kind == "heic":                           # Telegram can't show HEIC as a photo
            await ctx.bot.send_document(chat_id, InputFile(data, filename=name + ".heic"), caption=cap, **_UP)
        elif is_video:
            try:
                await ctx.bot.send_video(chat_id, InputFile(data, filename=name + ".mp4"), caption=cap,
                                         duration=it.get("dur") or None, supports_streaming=True, **_UP)
            except BadRequest:
                await ctx.bot.send_document(chat_id, InputFile(data, filename=name + ".mp4"), caption=cap, **_UP)
        else:
            ext = kind if kind in ("jpg", "png", "webp") else _ext(ctype, "jpg")
            try:
                if len(data) > TG_PHOTO_MAX:
                    raise BadRequest("too large")
                await ctx.bot.send_photo(chat_id, InputFile(data, filename=f"{name}.{ext}"), caption=cap, **_UP)
            except BadRequest:
                await ctx.bot.send_document(chat_id, InputFile(data, filename=f"{name}.{ext}"), caption=cap, **_UP)
        return True
    except TelegramError as e:
        log.info("story item %s not sent: %s", i, e)
        return False


async def process_story(update: Update, ctx, username: str, lang: str, started: float,
                        resume: dict | None = None) -> None:
    """Secret story viewer: the bot (never the user's account) fetches the stories,
    so nothing is registered in the target's viewer list.
    A long list is sent in time-boxed batches; `resume` continues where the last batch stopped."""
    msg, uid, chat_id = update.effective_message, update.effective_user.id, update.effective_chat.id

    if not await gate_message(update, ctx, uid, lang):
        return
    if not await acquire_lock(uid):
        return await msg.reply_text(tx(lang, "busy_msg"))

    status = None
    try:
        if resume is None:
            status = await msg.reply_text(tx(lang, "st_story", bar=bar(1)))
            items = await fetch_story(username)
            if items is None:
                return await safe_edit(status, tx(lang, "story_unavailable"))
            if not items:
                return await safe_edit(status, tx(lang, "no_story", user=esc(username)), story_kb(lang))
            limit = STORY_MAX_VIP if is_vip(uid) else STORY_MAX
            items = items[-limit:]                       # newest N, oldest → newest like the app
            n_vid = sum(1 for x in items if x.get("type") == "video")
            await safe_edit(status, tx(lang, "story_header", user=esc(username), n=len(items),
                                       v=n_vid, p=len(items) - n_vid))
            idx = 0
        else:
            items, idx = resume["items"], int(resume.get("next") or 0)
        total = len(items)

        sent = 0
        while idx < total and deadline_left(started) >= 10:
            if await _send_story_item(ctx, chat_id, username, lang, items[idx], idx + 1, total):
                sent += 1
            idx += 1

        left = total - idx
        if left > 0:                                     # out of time → remember the rest for the button
            await session_save(f"story_{uid}", {"user": username, "items": items, "next": idx})
        if not sent and left <= 0:
            if status:
                return await safe_edit(status, tx(lang, "dl_fail"))
            return await msg.reply_text(tx(lang, "dl_fail"))

        await ctx.bot.send_message(
            chat_id,
            tx(lang, "story_partial", n=sent, left=left) if left > 0 else tx(lang, "story_done", n=sent),
            reply_markup=story_kb(lang, left))
        if resume is None and sent:
            await db_incr("sys/cfg/total_dl")
            await db_incr(f"users/{uid}/dl")      # the header card stays as a summary of the batch

    except Exception as e:                                              # noqa: BLE001
        await report_error(ctx, e, "process_story")
        if status:
            await safe_edit(status, tx(lang, "dl_fail"))
    finally:
        await release_lock(uid)


async def cmd_story(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    started = time.monotonic()
    ud, lang = await ensure_user(update, ctx)
    username = extract_username(" ".join(ctx.args or []))
    if not username:
        return await update.effective_message.reply_text(tx(lang, "ask_story_prompt"),
                                                         reply_markup=ForceReply(selective=True))
    await process_story(update, ctx, username, lang, started)


async def cmd_storydebug(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admins only: /storydebug @username → text file with the shape of the provider's answer."""
    ud, lang = await ensure_user(update, ctx)
    if not is_admin(update.effective_user.id):
        return
    username = extract_username(" ".join(ctx.args or []))
    if not username:
        return await update.effective_message.reply_text("/storydebug @username")
    text = await story_debug(username)
    await update.effective_message.reply_document(InputFile(text.encode("utf-8"), filename="story_debug.txt"))


def _is_story_reply(msg) -> bool:
    """True when the user is replying to the bot's 'send the username' story prompt."""
    r = getattr(msg, "reply_to_message", None)
    if not r or not r.from_user or not r.from_user.is_bot or not r.text:
        return False
    heads = {plain(tx(l, "ask_story_prompt")).split("\n")[0] for l in L}
    return r.text.split("\n")[0].strip() in heads


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    started = time.monotonic()
    msg = update.effective_message
    if not msg or not update.effective_user:
        return
    uid = update.effective_user.id
    private = update.effective_chat.type == "private"
    text = msg.text or msg.caption or ""
    url = extract_url(text)

    ud, lang = await ensure_user(update, ctx)

    if is_admin(uid) and private:                       # pending "type the ID" prompt?
        state = await pop_wait(uid)
        if state:
            return await handle_prompt(update, ctx, state, lang, started)

    if private and _is_story_reply(msg):                 # answer to the "secret story" prompt
        username = extract_username(text)
        if username:
            return await process_story(update, ctx, username, lang, started)
        return await msg.reply_text(tx(lang, "ask_story_prompt"), reply_markup=ForceReply(selective=True))

    if url:
        return await process_link(update, ctx, url, lang, started)

    # not a TikTok link — is it a @username? (private chats only)
    if private:
        username = extract_username(text)
        if username:
            return await process_avatar(update, ctx, username, lang, started)

    if not private:
        return                                          # ignore group chatter
    if await gate_message(update, ctx, uid, lang):
        await msg.reply_text(tx(lang, "not_link"))


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.error:
        await report_error(ctx, ctx.error, "handler")


# ══════════════════════════════════════════════════════════════════════════════
# 12 · TELEGRAM APPLICATION + FASTAPI WEBHOOK
# ══════════════════════════════════════════════════════════════════════════════
def build_application() -> Application:
    ptb = (
        ApplicationBuilder()
        .token(TOKEN)
        .updater(None)                                   # we feed updates ourselves
        .defaults(Defaults(parse_mode=ParseMode.HTML))
        .connect_timeout(15).read_timeout(30).write_timeout(30).pool_timeout(15)
        .build()
    )
    ptb.add_handler(CommandHandler(["start", "menu"], cmd_start))
    ptb.add_handler(CommandHandler("help", cmd_help))
    ptb.add_handler(CommandHandler("ping", cmd_ping))
    ptb.add_handler(CommandHandler("story", cmd_story))
    ptb.add_handler(CommandHandler("storydebug", cmd_storydebug))
    ptb.add_handler(CallbackQueryHandler(on_callback))
    ptb.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL, on_message))
    ptb.add_error_handler(on_error)
    return ptb


class _BotOnly:
    """Minimal stand-in for a PTB context (just `.bot`) used outside handlers."""
    def __init__(self, bot):
        self.bot = bot


_ptb: Application | None = None
_ptb_loop = None
_seen_updates: dict = {}


async def get_ptb() -> Application:
    """One Application per warm instance; rebuilt if the event loop changed."""
    global _ptb, _ptb_loop
    loop = asyncio.get_running_loop()
    if _ptb is None or _ptb_loop is not loop:
        _ptb = build_application()
        await _ptb.initialize()
        _ptb_loop = loop
    return _ptb


def _duplicate(update_id: int) -> bool:
    """Telegram re-sends an update if we answer too slowly; ignore repeats."""
    now = time.time()
    for k in [k for k, t in _seen_updates.items() if now - t > 300]:
        _seen_updates.pop(k, None)
    if update_id in _seen_updates:
        return True
    _seen_updates[update_id] = now
    return False


@app.post("/{full_path:path}")
async def webhook(req: Request, full_path: str = ""):
    if not TOKEN:
        return JSONResponse({"ok": False, "error": "BOT_TOKEN is missing"}, status_code=500)
    if WEBHOOK_SECRET:
        got = req.headers.get("x-telegram-bot-api-secret-token", "")
        if not hmac.compare_digest(got, WEBHOOK_SECRET):
            return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "bad json"}, status_code=400)

    async with new_client() as client:
        token = _http_ctx.set(client)
        try:
            ptb = await get_ptb()
            update = Update.de_json(body, ptb.bot)
            if update is None or _duplicate(update.update_id):
                return {"ok": True}
            await load_cfg()
            await ptb.process_update(update)
        except Exception as e:                            # never let Telegram see a 5xx → no retry storm
            log.error("WEBHOOK ERROR: %s", traceback.format_exc())
            try:
                ptb = await get_ptb()
                await report_error(_BotOnly(ptb.bot), e, "webhook")
            except Exception:
                pass
        finally:
            _http_ctx.reset(token)
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
# 13 · STATUS PAGE  (GET /)  — public overview, private diagnostics with ?key=
# ══════════════════════════════════════════════════════════════════════════════
_PAGE = """<!doctype html>
<html lang="ckb" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JackTik · Status</title>
<style>
:root{--bg:#0b0f1a;--card:#131a2b;--line:#1f2942;--tx:#e8ecf5;--mut:#8b97b5;--ok:#22c55e;--warn:#f59e0b;--bad:#ef4444;--acc:#ff6b35}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:radial-gradient(1200px 600px at 80% -10%,#1b2540 0,transparent 60%),var(--bg);
color:var(--tx);font-family:system-ui,-apple-system,"Segoe UI",Tahoma,Arial,sans-serif;display:flex;justify-content:center;padding:32px 16px}
.wrap{width:100%;max-width:640px}
.hero{text-align:center;margin-bottom:24px}
.logo{width:72px;height:72px;border-radius:22px;margin:0 auto 14px;display:grid;place-items:center;font-size:34px;
background:linear-gradient(135deg,#ff6b35,#ff2d75);box-shadow:0 12px 40px rgba(255,80,80,.35)}
h1{margin:0;font-size:26px;letter-spacing:.3px} .sub{color:var(--mut);margin-top:6px;font-size:14px}
.badge{display:inline-flex;gap:8px;align-items:center;margin-top:14px;padding:8px 16px;border-radius:999px;font-weight:600;font-size:14px}
.badge.ok{background:rgba(34,197,94,.12);color:var(--ok);border:1px solid rgba(34,197,94,.35)}
.badge.bad{background:rgba(239,68,68,.12);color:var(--bad);border:1px solid rgba(239,68,68,.35)}
.dot{width:9px;height:9px;border-radius:50%;background:currentColor;box-shadow:0 0 0 4px rgba(255,255,255,.06)}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:6px 18px;margin-top:16px}
.card h2{font-size:13px;color:var(--mut);font-weight:600;margin:14px 0 4px;text-transform:uppercase;letter-spacing:.8px}
.row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:13px 0;border-bottom:1px solid var(--line);font-size:15px}
.row:last-child{border-bottom:0} .row small{display:block;color:var(--mut);font-size:12px;margin-top:3px}
.pill{padding:4px 12px;border-radius:999px;font-size:12.5px;font-weight:700;white-space:nowrap}
.pill.ok{background:rgba(34,197,94,.14);color:var(--ok)} .pill.warn{background:rgba(245,158,11,.14);color:var(--warn)}
.pill.bad{background:rgba(239,68,68,.14);color:var(--bad)}
code{direction:ltr;unicode-bidi:embed;background:#0d1322;border:1px solid var(--line);padding:2px 8px;border-radius:8px;font-size:12.5px;color:#c9d3ee;word-break:break-all}
.foot{text-align:center;color:var(--mut);font-size:12.5px;margin:22px 0 8px}
.foot a{color:var(--acc);text-decoration:none}
</style></head><body><div class="wrap">
<div class="hero"><div class="logo">🎬</div><h1>JackTik Bot</h1>
<div class="sub">TikTok Downloader · Telegram · v15</div>
<div class="badge __BADGE__"><span class="dot"></span>__BADGE_TEXT__</div></div>
__BODY__
<div class="foot">Made with ♥ by <a href="https://t.me/__DEV__">__DEV_TXT__</a> · <a href="__CH__">Channel</a></div>
</div></body></html>"""


def _row(label: str, state: str, text: str, hint: str = "") -> str:
    h = f"<small>{esc(hint)}</small>" if hint else ""
    return (f'<div class="row"><div>{esc(label)}{h}</div>'
            f'<span class="pill {state}">{esc(text)}</span></div>')


@app.get("/{full_path:path}")
async def status_page(req: Request, full_path: str = ""):
    checks = [
        _row("BOT_TOKEN", "ok" if TOKEN else "bad", "✓ Set" if TOKEN else "✗ Missing", "" if TOKEN else "Vercel → Settings → Environment Variables"),
        _row("DB_URL", "ok" if DB_URL else "bad", "✓ Set" if DB_URL else "✗ Missing"),
        _row("DB_SECRET", "ok" if DB_SECRET else "warn", "✓ Set" if DB_SECRET else "Not set", "" if DB_SECRET else "Needed unless your database rules are public"),
        _row("WEBHOOK_SECRET", "ok" if WEBHOOK_SECRET else "warn", "✓ Enabled" if WEBHOOK_SECRET else "Recommended",
             "" if WEBHOOK_SECRET else "Without it anyone who knows the URL can forge updates"),
        _row("OWNER_ID", "ok" if OWNER_ID != 5977475208 else "warn", "✓ Custom" if OWNER_ID != 5977475208 else "Default",
             "" if OWNER_ID != 5977475208 else "Set your own Telegram ID — the default belongs to the original developer"),
    ]
    healthy = bool(TOKEN and DB_URL)
    body = f'<div class="card"><h2>Configuration</h2>{"".join(checks)}</div>'

    key = req.query_params.get("key", "")
    if WEBHOOK_SECRET and key and hmac.compare_digest(key, WEBHOOK_SECRET):      # private diagnostics
        rows = []
        async with new_client() as client:
            tok = _http_ctx.set(client)
            try:
                ok, ms = await db_ping()
                rows.append(_row("Firebase", "ok" if ok else "bad", f"{ms} ms" if ok else "Unreachable"))
                if TOKEN:
                    try:
                        ptb = await get_ptb()
                        wi = await ptb.bot.get_webhook_info()
                        rows.append(_row("Webhook", "ok" if wi.url else "bad", "Set" if wi.url else "Not set",
                                         (wi.url or "").split("?")[0]))
                        rows.append(_row("Pending updates", "ok" if wi.pending_update_count < 5 else "warn", str(wi.pending_update_count)))
                        if wi.last_error_message:
                            rows.append(_row("Last Telegram error", "bad", "!", f"{wi.last_error_message} · {wi.last_error_date}"))
                    except Exception as e:                                       # noqa: BLE001
                        rows.append(_row("Telegram API", "bad", "Error", str(e)[:160]))
            finally:
                _http_ctx.reset(tok)
        body += f'<div class="card"><h2>Diagnostics</h2>{"".join(rows)}</div>'
    elif WEBHOOK_SECRET:
        body += '<div class="card"><div class="row"><div>Diagnostics<small>Open this page with <code>?key=WEBHOOK_SECRET</code></small></div></div></div>'

    page = (_PAGE.replace("__BADGE__", "ok" if healthy else "bad")
                 .replace("__BADGE_TEXT__", "Operational" if healthy else "Setup incomplete")
                 .replace("__BODY__", body)
                 .replace("__DEV__", esc(DEV.lstrip("@"))).replace("__DEV_TXT__", esc(DEV))
                 .replace("__CH__", esc(CHANNEL_URL)))
    return HTMLResponse(page, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})
