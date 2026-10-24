# ╔══════════════════════════════════════════════════════════════════════════╗
# ║   JackTik  ·  TikTok Downloader Bot for Telegram                         ║
# ║   Version : v16.0 (Pro)         Stack : FastAPI · PTB 21 · Firebase      ║
# ║   Owner   : @j4ck_721s          Deploy: Vercel (Python serverless)       ║
# ╚══════════════════════════════════════════════════════════════════════════╝
"""
JackTik v16 — TikTok downloader bot (Telegram webhook, Vercel serverless).

What changed in v16 (stage 1)
  • Download quality per user (Settings): HD · Standard · Audio only.
  • Instant repeats: Telegram file_ids are cached in Firebase (fc/ + uc/), so a link that
    was already downloaded is re-sent in about a second — no API call, download or upload.
  • New buttons under every video: 🎞 GIF · 🧩 Sticker · 💬 Comments (top 50 + .txt file).
  • Optional packages:  imageio-ffmpeg  (trimmed silent GIF + animated sticker)  and  Pillow
    (static sticker fallback).  Without them the bot still runs; only those two degrade.

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
import base64
import hashlib
import hmac
import html
import importlib.util
import io
import json
import logging
import os
import re
import secrets
import shutil
import tempfile
import time
import traceback
import urllib.parse
import zlib
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
    InputMediaAudio,
    InputMediaPhoto,
    LabeledPrice,
    ReplyParameters,
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
    ChatMemberHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
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
CRON_SECRET    = os.getenv("CRON_SECRET", "").strip()         # protects /cron/follows (🔔 follow alerts)

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
LATEST_FREE       = 3                # latest videos per request for everyone
LATEST_VIP        = 12               # … for VIP

START_TIME     = time.time()
SESSION_TTL    = 3600                # seconds an audio/"again" session stays valid
WAIT_TTL       = 600                 # seconds an admin "type the ID" prompt stays valid
LOCK_TTL       = 90                  # seconds a per-user download lock lives
CFG_TTL        = 20                  # seconds between config reloads per instance
FUNC_BUDGET    = 52                  # seconds we allow ourselves (vercel maxDuration = 60)
TG_MAX_BYTES   = 49_000_000          # Telegram bot upload limit is 50 MB
TG_PHOTO_MAX   = 10_000_000          # photo limit for sendPhoto
COMMENTS_MAX   = 50                  # comments fetched per video
COMMENTS_SHOW  = 10                  # comments previewed in the chat message
GIF_SECONDS    = 10                  # longest GIF we make
STICKER_MAX    = 256_000             # Telegram video-sticker size limit
STICKER_RADIUS = 0.10                # rounded corners: radius = 10 % of the shorter side (matches the reference)
QUALITIES      = ("hd", "sd", "audio")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("jacktik")
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# In-memory cache of the shared config (reloaded from Firebase every CFG_TTL s)
super_admins_set: set  = {OWNER_ID}
admins_set:       set  = {OWNER_ID}
channels_list:    list = []
blocked_set:      set  = set()
vip_set:          set  = set()
vip_until:        dict = {}          # uid → epoch: temporary VIP earned through referrals
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
    "ref_on":       True,       # referral system (free VIP for invites)
    "ref_need":     5,          # invited users needed per reward
    "ref_days":     3,          # VIP days per reward
    "groups_on":    True,       # answer TikTok links posted in groups
    "stars_on":     False,      # sell VIP for Telegram Stars (turn on in the panel after checking prices)
    "stars_plans":  [[7, 50], [30, 150], [90, 400]],   # [days, Stars]
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
        "👤 پرۆفایل — یوزەرنەیمێک بنێرە بۆ کارتی پرۆفایل + وێنەی HD + ستۆری + ڤیدیۆکان\n"
        "🔥 دۆزینەوە — گەڕان لە تیکتۆک و ترێندی وڵاتان\n"
        "🕵️ ستۆری — دوگمەی <b>ستۆری نهێنی</b> دابگرە و یوزەرنەیمێک بنێرە\n"
        "🎞 GIF · 🧩 ستیکەر · 💬 کۆمێنت — دوگمەکانی ژێر ڤیدیۆکە\n"
        "🖼 ستیکەر — وێنە یان ڤیدیۆ بنێرە (ستیکەری جوڵاو)، یان پاکێجی خۆت دروست بکە\n"
        "📜 مێژوو · ⭐ دڵخواز — ڤیدیۆکانت بە یەک پەنجە دووبارە بنێرە\n"
        "🎁 بانگهێشت — هاوڕێ بهێنە و VIP وەربگرە\n"
        "⚙️ کوالێتی — لە ڕێکخستن HD / ئاسایی / تەنیا دەنگ هەڵبژێرە</blockquote>\n"
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
    "q_title": "🎞 <b>کوالێتی دابەزاندن</b>",
    "q_current": "🔵 ئێستا: {cur}",
    "q_hd": "🎬 HD — باشترین کوالێتی",
    "q_sd": "📱 ئاسایی — داتای کەمتر",
    "q_audio": "🎵 تەنیا دەنگ (MP3)",
    "qb_hd": "🎬 HD", "qb_sd": "📱 ئاسایی", "qb_audio": "🎵 دەنگ",
    "q_saved": "✅ کوالێتی گۆڕدرا",
    "b_gif": "🎞 GIF", "b_sticker": "🧩 ستیکەر", "b_comments": "💬 کۆمێنت",
    "st_gif": "🎞 <b>GIF ئامادە دەکرێت…</b>\n{bar}",
    "st_stk": "🧩 <b>ستیکەر ئامادە دەکرێت…</b>\n{bar}",
    "st_cmt": "💬 <b>کۆمێنتەکان دەهێنرێن…</b>\n{bar}",
    "gif_fail": "❌ نەتوانرا GIF دروست بکرێت. دووبارە هەوڵبدەرەوە.",
    "stk_fail": "❌ نەتوانرا ستیکەر دروست بکرێت.",
    "stk_static": "ℹ️ ستیکەری جوڵاو لەم سێرڤەرەدا بەردەست نییە، بۆیە ستیکەری وێنە نێردرا.",
    "cmt_title": "💬 <b>کۆمێنتەکان</b> · {n}",
    "cmt_file": "📄 هەموو {n} کۆمێنتەکە",
    "cmt_none": "💬 ئەم ڤیدیۆیە کۆمێنتی نییە یان نەتوانرا بهێنرێت.",
    "cmt_fail": "❌ نەتوانرا کۆمێنتەکان بهێنرێت.",
    "b_mkstk": "🖼 دروستکردنی ستیکەر",
    "ask_stk_prompt": "🖼 <b>دروستکردنی ستیکەر</b>\n\nوێنەیەک لە گەلەری مۆبایلەکەتەوە بنێرە، منیش دەیکەم بە ستیکەر 🧩\n\n💡 بۆ کوالێتی باشتر، وێنەکە وەک <b>فایل</b> بنێرە.",
    "st_mkstk": "🖼 <b>ستیکەرەکە ئامادە دەکرێت…</b>",
    "mkstk_fail": "❌ نەتوانرا ئەم وێنەیە بکرێت بە ستیکەر. وێنەیەکی تر تاقی بکەرەوە.",
    "mkstk_big": "⚠️ ئەم وێنەیە زۆر گەورەیە (زیاتر لە ٢٠MB).",
    "b_hist": "📜 مێژوو", "b_favs": "⭐ دڵخوازەکان", "b_ref": "🎁 بانگهێشت",
    "b_fav": "⭐ دڵخواز", "b_faved": "✅ دڵخوازە", "b_hist_clear": "🗑 پاککردنەوەی مێژوو",
    "hist_title": "📜 <b>مێژووی دابەزاندن</b> · {n}\n\nهەر یەکێکیان دابگرە بۆ ناردنەوەی 👇",
    "hist_empty": "📜 هێشتا هیچت دانەبەزاندووە.\nلینکی تیکتۆکێک بنێرە.",
    "favs_title": "⭐ <b>دڵخوازەکان</b> · {n}\n\nهەر یەکێکیان دابگرە بۆ ناردنەوەی 👇",
    "favs_empty": "⭐ لیستی دڵخوازەکان بەتاڵە.\nلە ژێر هەر ڤیدیۆیەک دوگمەی ⭐ دابگرە.",
    "hist_cleared": "🗑 مێژوو پاککرایەوە",
    "fav_added": "⭐ زیادکرا بۆ دڵخوازەکان",
    "fav_removed": "🗑 لە دڵخوازەکان لابرا",
    "fav_full": "⚠️ لیستی دڵخوازەکان پڕە ({n} دانە). یەکێک لابە.",
    "ref_info": "🎁 <b>هاوڕێکانت بانگهێشت بکە</b>\n\nهەر <b>{need}</b> کەس بە لینکی تۆوە بێن و یەک ڤیدیۆ دابەزێنن، <b>{days} ڕۆژ VIP</b> وەردەگریت 💎\n\n👥 بانگهێشتکراوان: <b>{cnt}</b>\n📊 بۆ خەڵاتی داهاتوو: <b>{left}</b> کەسی تر ماوە\n\n🔗 لینکی تایبەتی تۆ:\n<code>{link}</code>",
    "ref_vip_until": "💎 VIPەکەت تا <b>{until}</b> چالاکە",
    "ref_off": "🎁 سیستەمی بانگهێشتکردن ئێستا ناچالاکە.",
    "b_ref_share": "📤 ناردنی لینک بۆ هاوڕێکان",
    "ref_share_text": "🎬 باشترین بۆتی دابەزاندنی تیکتۆک، بێ لۆگۆ! لێرەوە دەست پێبکە:",
    "ref_progress": "👥 یەکێک بە لینکەکەتەوە هات و ڤیدیۆیەکی دابەزاند! ({cnt}/{need})",
    "ref_reward": "🎉 <b>پیرۆزە!</b> <b>{days} ڕۆژ VIP</b> وەرگرت 💎\nتا <b>{until}</b> چالاکە.",
    "b_sup_ref": "🎁 بانگهێشتکردن", "b_sup_groups": "👥 گرووپ: {status}",
    "b_ref_toggle": "🔘 بانگهێشتکردن: {status}",
    "sup_ref_title": "🎁 <b>ڕێکخستنی بانگهێشتکردن</b>\n\nدۆخ: {status}\n👥 ژمارەی بانگهێشتکراو بۆ خەڵات: <b>{need}</b>\n💎 ماوەی VIP: <b>{days}</b> ڕۆژ",
    "grp_welcome": "👋 سڵاو! من بۆتی دابەزاندنی تیکتۆکم.\n\nلینکی تیکتۆک لێرە بنێرە، ڤیدیۆکە بێ لۆگۆ دەنێرمەوە 🎬",
    "stk_menu_nopack": "🖼 <b>دروستکردنی ستیکەر</b>\n\nوێنەیەک لە گەلەریەکەتەوە بنێرە و دەیکەم بە ستیکەر 🧩\n🎞 ڤیدیۆیەکی کورت (تا ٣ چرکە) بنێرە و دەیکەم بە <b>ستیکەری جوڵاو</b>\n\n📦 دەتوانیت <b>پاکێجی ستیکەر</b> دروست بکەیت: هەموو ستیکەرەکانت دەچنە ناو یەک پاکێج و دەتوانیت لە تێلیگرام زیادی بکەیت.\n\n💡 بۆ کوالێتی باشتر، وێنەکە وەک <b>فایل</b> بنێرە.",
    "stk_menu_pack": "🖼 <b>دروستکردنی ستیکەر</b>\n\n📦 پاکێجی چالاک: <b>{title}</b> ({n}/120)\n\nهەر وێنەیەک بنێریت دەچێتە ناو ئەم پاکێجە 🧩\n🎞 ڤیدیۆ دەبێتە ستیکەری جوڵاو و دەچێتە ناو <b>پاکێجێکی جیاواز</b>، چونکە تێلیگرام ستیکەری وێنە و ڤیدیۆ تێکەڵ ناکات.\n💡 بۆ کوالێتی باشتر، وێنەکە وەک <b>فایل</b> بنێرە.",
    "stk_menu_pending": "🖼 <b>دروستکردنی ستیکەر</b>\n\n📦 پاکێجی نوێ: <b>{title}</b>\n\nیەکەم <b>وێنە یان ڤیدیۆ</b> بنێرە، پاکێجەکە پێی دروست دەکرێت (وێنە = پاکێجی ئاسایی، ڤیدیۆ = پاکێجی جوڵاو) 👇",
    "b_stk_new": "📦 پاکێجی نوێ", "b_stk_open": "🔗 کردنەوەی پاکێج", "b_stk_list": "📂 پاکێجەکانم",
    "stk_ask_title": "📦 <b>ناوی پاکێجەکە بنێرە</b>\n\nنموونە: <code>ستیکەرەکانی من</code>",
    "stk_title_ok": "✅ پاکێجی <b>{title}</b> ئامادەیە.\n\nئێستا یەکەم وێنە یان ڤیدیۆ بنێرە، پاکێجەکە پێی دروست دەکرێت 🖼",
    "stk_title_bad": "⚠️ ناوەکە دەبێت لە ١ بۆ ٦٠ پیت بێت. دووبارە بینێرە:",
    "stk_created": "🎉 <b>پاکێجەکەت دروست کرا!</b>\n📦 {title}\n\nدوگمەی خوارەوە دابگرە بۆ زیادکردنی بۆ تێلیگرام 👇",
    "stk_full": "⚠️ ئەم پاکێجە پڕە (١٢٠ ستیکەر). پاکێجێکی نوێ دروست بکە.",
    "stk_gone": "⚠️ ئەم پاکێجە لە تێلیگرام سڕاوەتەوە. پاکێجێکی نوێ دروست بکە.",
    "stk_list_title": "📂 <b>پاکێجەکانم</b>\n\nپاکێجی چالاک بە ✅ دیاری کراوە، هەر یەکێک دابگرە بۆ گۆڕین:",
    "stk_switched": "✅ پاکێجی چالاک گۆڕدرا",
    "stk_del_confirm": "⚠️ <b>دڵنیایت دەتەوێت ئەم پاکێجە بسڕیتەوە؟</b>\n\n📦 {title} ({n} ستیکەر)\n\nئەم کارە <b>ناگەڕێتەوە</b>: پاکێجەکە و هەموو ستیکەرەکانی لە تێلیگرام دەسڕدرێنەوە.",
    "b_stk_del_yes": "✅ بەڵێ، بیسڕەوە", "b_stk_del_no": "❌ نەخێر، گەڕانەوە",
    "stk_deleted": "🗑 پاکێجەکە سڕایەوە",
    "stk_del_fail": "❌ نەتوانرا پاکێجەکە بسڕدرێتەوە. دووبارە هەوڵبدەرەوە.",
    "stk_menu_vpack": "🎞 پاکێجی ستیکەری جوڵاو: <b>{title}</b> ({n}/120)",
    "vstk_noffmpeg": "⚠️ ستیکەری جوڵاو لەم سێرڤەرەدا بەردەست نییە (پێویستی بە ffmpeg هەیە).",
    "vstk_trim": "ℹ️ تێلیگرام تەنیا <b>٣ چرکە</b> بۆ ستیکەری جوڵاو ڕێگە دەدات، بۆیە سێ چرکەی یەکەمی ڤیدیۆکە بڕدرا.",
    "b_top": "🏆 باشترینەکان", "b_fwlist": "🔔 فۆڵۆکراوەکان",
    "lb_title": "🏆 <b>باشترین بانگهێشتکەران</b>\n<i>هەر کەسێک زیاتر هاوڕێ بهێنێت، پلەی بەرزتر دەبێت</i>",
    "lb_empty": "هێشتا کەس بانگهێشتی کەسی نەکردووە. یەکەم کەس بە! 🎁",
    "lb_you": "📍 پلەی تۆ: <b>#{rank}</b> — {n} بانگهێشتکراو",
    "lb_hidden": "🙈 ناوی شاراوە",
    "b_lb_hide": "🙈 ناوم بشارەوە", "b_lb_show": "👁 ناوم نیشان بدە",
    "lb_toast_hide": "🙈 ناوت شاردرایەوە", "lb_toast_show": "👁 ناوت نیشان دەدرێت",
    "stars_info": "⭐ <b>بە Telegram Stars بیکڕە</b> — یەکسەر چالاک دەبێت. هەر پلانێک بۆ ماوەیەکی دیاریکراوە و دەچێتە سەر VIPەکەی ئێستات.",
    "b_buy": "💎 {days} ڕۆژ — {stars} ⭐",
    "stars_off": "⚠️ کڕین ئێستا چالاک نییە.",
    "stars_changed": "نرخەکە گۆڕدراوە. تکایە پلانەکە دووبارە هەڵبژێرە.",
    "stars_thanks": "🎉 <b>سوپاس بۆ کڕینەکەت!</b>\n\n💎 {days} ڕۆژ VIP چالاک کرا\n📅 تا <b>{until}</b>",
    "inv_title": "💎 VIP — {days} ڕۆژ",
    "inv_desc": "{days} ڕۆژ VIP بۆ بۆتی دابەزاندنی تیکتۆک: ڤیدیۆی زیاتر و تایبەتمەندی تەواو.",
    "b_sup_stars": "💎 Stars: {status}", "b_stars_toggle": "🔘 کڕین بە Stars: {status}",
    "sup_stars_title": "💎 <b>ڕێکخستنی Telegram Stars</b>\n\nدۆخ: {status}\n💰 کۆی داهات: <b>{total}</b> ⭐\n\nنرخی هەر پلانێک بگۆڕە:",
    "fw_b_off": "🔔 فۆڵۆکردن", "fw_b_on": "✅ فۆڵۆ کراوە",
    "fw_on": "🔔 فۆڵۆ کرا! کاتێک ڤیدیۆی نوێ دابنێت ئاگادارت دەکەمەوە.",
    "fw_off": "🔕 فۆڵۆ لابرا",
    "fw_limit": "⚠️ گەیشتیتە سنووری فۆڵۆکردن ({n} ئەکاونت). VIP تا {vip} ئەکاونتی پێدەدات.",
    "fw_empty": "🔔 هێشتا هیچ ئەکاونتێکت فۆڵۆ نەکردووە.\nپرۆفایلی تیکتۆکێک بکەرەوە و 🔔 دابگرە.",
    "fw_list_title": "🔔 <b>فۆڵۆکراوەکانم</b> · {n}/{max}\n\nناوێک دابگرە بۆ دوایین ڤیدیۆکان، یان 🔕 بۆ لابردن:",
    "fw_new": "🔔 <b>@{user}</b> ڤیدیۆیەکی نوێی دانا!\n\n{title}",
    "fw_b_dl": "⬇️ دابەزاندن", "fw_b_stop": "🔕 ڕاگرتنی ئاگاداری",
    "stk_menu_tip": "🎨 دوای ناردنی وێنە یان ڤیدیۆ، شێوەی ستیکەرەکە هەڵدەبژێریت: قوژبن خڕ، چوارگۆشە یان بازنە.\n✍️ بۆ نووسین لەسەر ستیکەر، نووسینەکە وەک <b>کاپشنی</b> وێنەکە بنێرە.",
    "ss_ask": "🎨 <b>چ شێوەیەک دەتەوێت بۆ ستیکەرەکە؟</b>\n\n▭ <b>قوژبن خڕ</b> — ڕێژەی ڕەسەنی وێنەکە دەمێنێتەوە\n⬛ <b>چوارگۆشە</b> — ناوەڕاستی وێنەکە دەبڕدرێت بۆ چوارگۆشە\n⚪ <b>بازنە</b> — وەک وێنەی پرۆفایل",
    "ss_expired": "⌛ ئەم داواکارییە بەسەرچوو. وێنە یان ڤیدیۆکە دووبارە بنێرە.",
    "b_font_auto": "🔄 خۆکار", "b_font_ku": "🔤 کوردی", "b_font_en": "🔠 ئینگلیزی",
    "ss_font_hint": "🔤 <b>فۆنتی نووسینەکە</b> هەڵبژێرە: خۆکار، کوردی یان ئینگلیزی. پاشان شێوەکە.",
    "stk_font_missing": "ℹ️ فۆنتی هەڵبژێردراو هەندێک پیتی ئەم نووسینەی نییە، بۆیە فۆنتی ناوەکیی بۆتەکە بەکارهات.",
    "b_shape_round": "▭ قوژبن خڕ", "b_shape_sq": "⬛ چوارگۆشە", "b_shape_circle": "⚪ بازنە", "b_shape_cancel": "❌ هەڵوەشاندنەوە",
    "stk_text_unsupported": "ℹ️ نووسینی کوردی لەسەر ئەم سێرڤەرە پشتگیری ناکرێت، بۆیە ستیکەرەکە بێ نووسین دروست کرا.",
    "vstk_notext": "ℹ️ نووسین لەسەر ستیکەری جوڵاو پشتگیری ناکرێت (تەنیا لەسەر وێنە).",
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
    # ── edit audio title / artist ─────────────────────────────────────────────
    "b_aedit": "✏️ دەستکاری ناو",
    "b_aedit_title": "🎵 ناوی دەنگ", "b_aedit_perf": "👤 ناوی گۆرانیبێژ", "b_aedit_back": "↩️ گەڕانەوە",
    "ask_aedit_title": "✏️ <b>ناوی نوێی دەنگ بنووسە</b>\n\nئێستا: <code>{cur}</code>\n<i>(وەڵامی ئەم پەیامە بدەرەوە)</i>",
    "ask_aedit_perf": "✏️ <b>ناوی نوێی گۆرانیبێژ بنووسە</b>\n\nئێستا: <code>{cur}</code>\n<i>(وەڵامی ئەم پەیامە بدەرەوە)</i>",
    "aedit_done": "✅ <b>ناوەکان نوێ کرانەوە</b>\n🎵 {title}\n👤 {perf}",
    "aedit_fail": "❌ نەتوانرا ناوەکە بگۆڕدرێت. دووبارە دەنگەکە دابەزێنە و هەوڵبدەرەوە.",
    "aedit_expired": "⌛ کاتی دەستکاریکردنەکە بەسەرچوو. دووبارە دوگمەی ✏️ دابگرە.",
    "aedit_empty": "⚠️ ناوێکی ڕاست بنووسە (نووسین).",
    "aedit_noaudio": "ئەم فایلە وەک گۆرانی نەنێردراوە، ناتوانرێت ناوەکەی بگۆڕدرێت.",
    "aedit_same": "ℹ️ ئەمە هەمان ناوی ئێستایە.",
    # ── discover (search + trending) ──────────────────────────────────────────
    "b_disc_kurd": "🏔 ڤیدیۆی کوردی",
    "disc_kurd_title": "🏔 <b>ڤیدیۆی کوردی</b>\n\nبابەتێک هەڵبژێرە و باشترین ڤیدیۆکانی کوردستانت بۆ دێنم:",
    "b_disc": "🔥 دۆزینەوە", "b_disc_search": "🔍 گەڕان بە وشە", "b_disc_more": "➡️ زیاتر", "b_disc_new": "🔍 گەڕانی نوێ",
    "disc_title": "🔥 <b>دۆزینەوە</b>\n\nلە تیکتۆک بگەڕێ یان ڤیدیۆی ترێندی وڵاتێک ببینە، ئینجا هەر ڤیدیۆیەک هەڵبژێرە بۆ دابەزاندن.\n\n🌍 <b>ترێندی وڵات:</b>",
    "ask_search_prompt": "🔍 <b>گەڕان لە تیکتۆک</b>\n\nوشەیەک یان ناوێک بنووسە:\nنموونە: <code>football</code>",
    "st_disc": "🔎 <b>دەگەڕێم…</b>\n{bar}",
    "disc_res_search": "🔍 <b>«{q}»</b>", "disc_res_trend": "🔥 <b>ترێند {region}</b>",
    "disc_pick": "👇 ژمارەی ڤیدیۆکە هەڵبژێرە بۆ دابەزاندن",
    "disc_none": "📭 هیچ ئەنجامێک نەدۆزرایەوە.",
    "disc_fail": "⚠️ ناتوانرێت ئێستا ئەنجامەکان بهێنرێن. دواتر دووبارە هەوڵبدەرەوە.",
    "disc_expired": "⌛ ئەم لیستە کۆنە — دووبارە بگەڕێ.",
    # ── profile hub ───────────────────────────────────────────────────────────
    "profile_card": "👤 <b>{name}</b> {badge}\n<code>@{user}</code>{stats}{bio}\n\n⚡ <a href=\"https://t.me/{bot}\">@{bot}</a>",
    "pf_followers": "👥 فۆڵۆوەر", "pf_following": "➕ فۆڵۆو", "pf_likes": "❤️ لایک", "pf_videos": "🎬 ڤیدیۆ",
    "pf_b_vids": "🎬 دوایین ڤیدیۆکان", "pf_b_file": "📎 وێنە بە HD (فایل)", "pf_b_open": "🔗 پرۆفایل",
    "st_latest": "🎬 <b>دوایین ڤیدیۆکان دەهێنرێن…</b>\n{bar}",
    "latest_header": "🎬 <b>دوایین ڤیدیۆکانی @{user}</b>\n<blockquote>📥 {n} ڤیدیۆ دەنێردرێت</blockquote>",
    "latest_none": "📭 <b>@{user}</b> ڤیدیۆی نییە (یان تەنیا پۆستی وێنەی هەیە).",
    "latest_unavailable": "⚠️ ناتوانرێت ڤیدیۆکانی ئەم ئەکاونتە بهێنرێت. دواتر دووبارە هەوڵبدەرەوە.",
    "latest_done": "✅ <b>{n} ڤیدیۆ</b> نێردرا",
    "latest_partial": "⏱ کاتەکە تەواو بوو — <b>{n}</b> ڤیدیۆ نێردرا، <b>{left}</b> ماوە. دوگمەی خوارەوە دابگرە بۆ بەردەوامبوون.",
    "latest_vip_hint": "💎 بەکارهێنەری ئاسایی {free} ڤیدیۆ وەردەگرێت — بە <b>VIP</b> تا {vip} ڤیدیۆ.",
    "no_story": "📭 <b>@{user}</b> ئێستا ستۆری چالاکی نییە.\nستۆری تیکتۆک ٢٤ کاتژمێر دەمێنێتەوە.",
    "story_unavailable": "⚠️ ستۆری ئەم ئەکاونتە بەردەست نییە (ڕەنگە تایبەت بێت یان سەرچاوەکە پشتگیری نەکات).",
    "b_story": "🕵️ ستۆری نهێنی", "b_story_again": "🔄 ستۆری کەسێکی تر",
    # ── buttons ───────────────────────────────────────────────────────────────
    "b_dl": "📥 دابەزاندنی نوێ", "b_profile": "👤 پرۆفایل", "b_vip": "💎 VIP", "b_avatar": "🔎 پرۆفایلی تیکتۆک",
    "b_lang": "⚙️ ڕێکخستن", "b_help": "📖 ڕێنمایی", "b_channel": "📢 کەناڵی بۆت",
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
        "👤 Profile — send a username for a profile card + HD picture + stories + latest videos\n"
        "🔥 Discover — search TikTok or browse trending by country\n"
        "🕵️ Stories — tap <b>Secret story</b> and send a username\n"
        "🎞 GIF · 🧩 Sticker · 💬 Comments — buttons under the video\n"
        "🖼 Sticker — send a photo or a video (animated), or build your own pack\n"
        "📜 History · ⭐ Favorites — re-send your videos in one tap\n"
        "🎁 Invite — bring friends and earn VIP\n"
        "⚙️ Quality — pick HD / Standard / Audio only in Settings</blockquote>\n"
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
    "q_title": "🎞 <b>Download quality</b>",
    "q_current": "🔵 Current: {cur}",
    "q_hd": "🎬 HD — best quality",
    "q_sd": "📱 Standard — less data",
    "q_audio": "🎵 Audio only (MP3)",
    "qb_hd": "🎬 HD", "qb_sd": "📱 Standard", "qb_audio": "🎵 Audio",
    "q_saved": "✅ Quality changed",
    "b_gif": "🎞 GIF", "b_sticker": "🧩 Sticker", "b_comments": "💬 Comments",
    "st_gif": "🎞 <b>Making the GIF…</b>\n{bar}",
    "st_stk": "🧩 <b>Making the sticker…</b>\n{bar}",
    "st_cmt": "💬 <b>Fetching comments…</b>\n{bar}",
    "gif_fail": "❌ Could not make the GIF. Please try again.",
    "stk_fail": "❌ Could not make the sticker.",
    "stk_static": "ℹ️ Animated stickers are not available on this server, so a static sticker was sent.",
    "cmt_title": "💬 <b>Comments</b> · {n}",
    "cmt_file": "📄 All {n} comments",
    "cmt_none": "💬 This video has no comments, or they could not be loaded.",
    "cmt_fail": "❌ Could not fetch the comments.",
    "b_mkstk": "🖼 Make a sticker",
    "ask_stk_prompt": "🖼 <b>Make a sticker</b>\n\nSend a photo from your gallery and I'll turn it into a sticker 🧩\n\n💡 For better quality, send the photo as a <b>file</b>.",
    "st_mkstk": "🖼 <b>Making your sticker…</b>",
    "mkstk_fail": "❌ Could not turn this image into a sticker. Try another one.",
    "mkstk_big": "⚠️ This image is too large (over 20 MB).",
    "b_hist": "📜 History", "b_favs": "⭐ Favorites", "b_ref": "🎁 Invite",
    "b_fav": "⭐ Favorite", "b_faved": "✅ Saved", "b_hist_clear": "🗑 Clear history",
    "hist_title": "📜 <b>Download history</b> · {n}\n\nTap one to send it again 👇",
    "hist_empty": "📜 You haven't downloaded anything yet.\nSend a TikTok link.",
    "favs_title": "⭐ <b>Favorites</b> · {n}\n\nTap one to send it again 👇",
    "favs_empty": "⭐ Your favorites list is empty.\nTap ⭐ under any video to add it.",
    "hist_cleared": "🗑 History cleared",
    "fav_added": "⭐ Added to favorites",
    "fav_removed": "🗑 Removed from favorites",
    "fav_full": "⚠️ Favorites are full ({n} items). Remove one first.",
    "ref_info": "🎁 <b>Invite your friends</b>\n\nFor every <b>{need}</b> people who join with your link and download a video, you get <b>{days} days of VIP</b> 💎\n\n👥 Invited: <b>{cnt}</b>\n📊 Next reward: <b>{left}</b> more\n\n🔗 Your personal link:\n<code>{link}</code>",
    "ref_vip_until": "💎 Your VIP is active until <b>{until}</b>",
    "ref_off": "🎁 The invite system is currently off.",
    "b_ref_share": "📤 Share your link",
    "ref_share_text": "🎬 The best TikTok downloader bot — no watermark! Start here:",
    "ref_progress": "👥 Someone joined with your link and downloaded a video! ({cnt}/{need})",
    "ref_reward": "🎉 <b>Congratulations!</b> You earned <b>{days} days of VIP</b> 💎\nActive until <b>{until}</b>.",
    "b_sup_ref": "🎁 Invites", "b_sup_groups": "👥 Groups: {status}",
    "b_ref_toggle": "🔘 Invites: {status}",
    "sup_ref_title": "🎁 <b>Invite settings</b>\n\nStatus: {status}\n👥 Invites needed per reward: <b>{need}</b>\n💎 VIP length: <b>{days}</b> days",
    "grp_welcome": "👋 Hi! I'm a TikTok downloader bot.\n\nSend a TikTok link here and I'll reply with the video, no watermark 🎬",
    "stk_menu_nopack": "🖼 <b>Make a sticker</b>\n\nSend a photo from your gallery and I'll turn it into a sticker 🧩\n🎞 Send a short video (up to 3 s) and I'll turn it into an <b>animated sticker</b>\n\n📦 You can also create a <b>sticker pack</b>: your stickers go into one pack that you can add to Telegram.\n\n💡 For better quality, send the photo as a <b>file</b>.",
    "stk_menu_pack": "🖼 <b>Make a sticker</b>\n\n📦 Active pack: <b>{title}</b> ({n}/120)\n\nEvery photo you send is added to this pack 🧩\n🎞 A video becomes an animated sticker in a <b>separate pack</b>, because Telegram doesn't mix photo and video stickers.\n💡 For better quality, send the photo as a <b>file</b>.",
    "stk_menu_pending": "🖼 <b>Make a sticker</b>\n\n📦 New pack: <b>{title}</b>\n\nSend the first <b>photo or video</b> and the pack will be created with it (photo = normal pack, video = animated pack) 👇",
    "b_stk_new": "📦 New pack", "b_stk_open": "🔗 Open pack", "b_stk_list": "📂 My packs",
    "stk_ask_title": "📦 <b>Send a name for your pack</b>\n\nExample: <code>My stickers</code>",
    "stk_title_ok": "✅ Pack <b>{title}</b> is ready.\n\nNow send the first photo or video and the pack will be created with it 🖼",
    "stk_title_bad": "⚠️ The name must be 1–60 characters. Send it again:",
    "stk_created": "🎉 <b>Your pack is ready!</b>\n📦 {title}\n\nTap the button to add it to Telegram 👇",
    "stk_full": "⚠️ This pack is full (120 stickers). Create a new pack.",
    "stk_gone": "⚠️ This pack no longer exists on Telegram. Create a new pack.",
    "stk_list_title": "📂 <b>My packs</b>\n\nThe active pack is marked ✅ — tap one to switch:",
    "stk_switched": "✅ Active pack changed",
    "stk_del_confirm": "⚠️ <b>Are you sure you want to delete this pack?</b>\n\n📦 {title} ({n} stickers)\n\nThis <b>cannot be undone</b>: the pack and all its stickers will be deleted from Telegram.",
    "b_stk_del_yes": "✅ Yes, delete it", "b_stk_del_no": "❌ No, go back",
    "stk_deleted": "🗑 Pack deleted",
    "stk_del_fail": "❌ Could not delete the pack. Please try again.",
    "stk_menu_vpack": "🎞 Animated pack: <b>{title}</b> ({n}/120)",
    "vstk_noffmpeg": "⚠️ Animated stickers are not available on this server (ffmpeg is missing).",
    "vstk_trim": "ℹ️ Telegram only allows <b>3 seconds</b> for an animated sticker, so the first 3 seconds of your video were used.",
    "b_top": "🏆 Top inviters", "b_fwlist": "🔔 Following",
    "lb_title": "🏆 <b>Top inviters</b>\n<i>The more friends you bring, the higher you climb</i>",
    "lb_empty": "Nobody has invited anyone yet. Be the first! 🎁",
    "lb_you": "📍 Your rank: <b>#{rank}</b> — {n} invited",
    "lb_hidden": "🙈 Hidden name",
    "b_lb_hide": "🙈 Hide my name", "b_lb_show": "👁 Show my name",
    "lb_toast_hide": "🙈 Your name is hidden", "lb_toast_show": "👁 Your name is visible",
    "stars_info": "⭐ <b>Buy with Telegram Stars</b> — active instantly. Each plan lasts a fixed time and is added on top of your current VIP.",
    "b_buy": "💎 {days} days — {stars} ⭐",
    "stars_off": "⚠️ Purchases are not available right now.",
    "stars_changed": "The price has changed. Please pick the plan again.",
    "stars_thanks": "🎉 <b>Thank you for your purchase!</b>\n\n💎 {days} days of VIP activated\n📅 Until <b>{until}</b>",
    "inv_title": "💎 VIP — {days} days",
    "inv_desc": "{days} days of VIP for the TikTok downloader bot: more videos and every feature.",
    "b_sup_stars": "💎 Stars: {status}", "b_stars_toggle": "🔘 Selling with Stars: {status}",
    "sup_stars_title": "💎 <b>Telegram Stars settings</b>\n\nStatus: {status}\n💰 Total earned: <b>{total}</b> ⭐\n\nChange the price of each plan:",
    "fw_b_off": "🔔 Follow", "fw_b_on": "✅ Following",
    "fw_on": "🔔 Followed! I'll tell you when they post a new video.",
    "fw_off": "🔕 Unfollowed",
    "fw_limit": "⚠️ You reached the follow limit ({n} accounts). VIP allows up to {vip}.",
    "fw_empty": "🔔 You don't follow any account yet.\nOpen a TikTok profile and tap 🔔.",
    "fw_list_title": "🔔 <b>Following</b> · {n}/{max}\n\nTap a name for the latest videos, or 🔕 to unfollow:",
    "fw_new": "🔔 <b>@{user}</b> posted a new video!\n\n{title}",
    "fw_b_dl": "⬇️ Download", "fw_b_stop": "🔕 Stop alerts",
    "stk_menu_tip": "🎨 After you send a photo or video you choose the shape: rounded, square or circle.\n✍️ To put text on a sticker, send it as the photo's <b>caption</b>.",
    "ss_ask": "🎨 <b>Which shape do you want for the sticker?</b>\n\n▭ <b>Rounded</b> — keeps the photo's proportions\n⬛ <b>Square</b> — centre-cropped to a square\n⚪ <b>Circle</b> — like a profile picture",
    "ss_expired": "⌛ This request expired. Please send the photo or video again.",
    "b_font_auto": "🔄 Auto", "b_font_ku": "🔤 Kurdish", "b_font_en": "🔠 English",
    "ss_font_hint": "🔤 Pick the <b>font</b> for your text: Auto, Kurdish or English. Then the shape.",
    "stk_font_missing": "ℹ️ The chosen font doesn't have some letters of this text, so the bot's built-in font was used.",
    "b_shape_round": "▭ Rounded", "b_shape_sq": "⬛ Square", "b_shape_circle": "⚪ Circle", "b_shape_cancel": "❌ Cancel",
    "stk_text_unsupported": "ℹ️ Kurdish/Arabic text isn't supported on this server, so the sticker was made without text.",
    "vstk_notext": "ℹ️ Text on animated stickers is not supported (photos only).",
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
    # ── edit audio title / artist ─────────────────────────────────────────────
    "b_aedit": "✏️ Edit names",
    "b_aedit_title": "🎵 Sound title", "b_aedit_perf": "👤 Artist name", "b_aedit_back": "↩️ Back",
    "ask_aedit_title": "✏️ <b>Type the new sound title</b>\n\nCurrent: <code>{cur}</code>\n<i>(reply to this message)</i>",
    "ask_aedit_perf": "✏️ <b>Type the new artist name</b>\n\nCurrent: <code>{cur}</code>\n<i>(reply to this message)</i>",
    "aedit_done": "✅ <b>Names updated</b>\n🎵 {title}\n👤 {perf}",
    "aedit_fail": "❌ Couldn't change the name. Download the audio again and retry.",
    "aedit_expired": "⌛ This edit expired. Tap ✏️ again.",
    "aedit_empty": "⚠️ Please send a valid name (text).",
    "aedit_noaudio": "This file wasn't sent as audio, so its name can't be changed.",
    "aedit_same": "ℹ️ That is already the current name.",
    # ── discover (search + trending) ──────────────────────────────────────────
    "b_disc_kurd": "🏔 Kurdish videos",
    "disc_kurd_title": "🏔 <b>Kurdish videos</b>\n\nPick a topic and I will bring you the best videos from Kurdistan:",
    "b_disc": "🔥 Discover", "b_disc_search": "🔍 Search by keyword", "b_disc_more": "➡️ More", "b_disc_new": "🔍 New search",
    "disc_title": "🔥 <b>Discover</b>\n\nSearch TikTok or browse a country's trending videos, then pick any video to download.\n\n🌍 <b>Trending by country:</b>",
    "ask_search_prompt": "🔍 <b>Search TikTok</b>\n\nType a word or a name:\nExample: <code>football</code>",
    "st_disc": "🔎 <b>Searching…</b>\n{bar}",
    "disc_res_search": "🔍 <b>“{q}”</b>", "disc_res_trend": "🔥 <b>Trending {region}</b>",
    "disc_pick": "👇 Tap a number to download that video",
    "disc_none": "📭 Nothing found.",
    "disc_fail": "⚠️ Couldn't load results right now. Try again later.",
    "disc_expired": "⌛ This list is outdated — search again.",
    # ── profile hub ───────────────────────────────────────────────────────────
    "profile_card": "👤 <b>{name}</b> {badge}\n<code>@{user}</code>{stats}{bio}\n\n⚡ <a href=\"https://t.me/{bot}\">@{bot}</a>",
    "pf_followers": "👥 Followers", "pf_following": "➕ Following", "pf_likes": "❤️ Likes", "pf_videos": "🎬 Videos",
    "pf_b_vids": "🎬 Latest videos", "pf_b_file": "📎 HD picture (file)", "pf_b_open": "🔗 Profile",
    "st_latest": "🎬 <b>Fetching the latest videos…</b>\n{bar}",
    "latest_header": "🎬 <b>Latest videos of @{user}</b>\n<blockquote>📥 {n} videos on the way</blockquote>",
    "latest_none": "📭 <b>@{user}</b> has no videos (or only photo posts).",
    "latest_unavailable": "⚠️ Couldn't fetch this account's videos. Try again later.",
    "latest_done": "✅ <b>{n} videos</b> delivered",
    "latest_partial": "⏱ Time limit reached — <b>{n}</b> videos sent, <b>{left}</b> left. Tap the button below to continue.",
    "latest_vip_hint": "💎 Free users get {free} videos — <b>VIP</b> gets up to {vip}.",
    "no_story": "📭 <b>@{user}</b> has no active stories right now.\nTikTok stories last 24 hours.",
    "story_unavailable": "⚠️ This account's stories aren't available (it may be private, or the source doesn't support them).",
    "b_story": "🕵️ Secret story", "b_story_again": "🔄 Another story",
    "b_dl": "📥 New download", "b_profile": "👤 Profile", "b_vip": "💎 VIP", "b_avatar": "🔎 TikTok profile",
    "b_lang": "⚙️ Settings", "b_help": "📖 Help", "b_channel": "📢 Bot channel",
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
        "👤 الملف الشخصي — أرسل اسم مستخدم لبطاقة الحساب + صورة HD + القصص + آخر الفيديوهات\n"
        "🔥 اكتشف — ابحث في تيك توك أو تصفّح الرائج حسب البلد\n"
        "🕵️ القصص — اضغط <b>قصة سرية</b> وأرسل اسم مستخدم\n"
        "🎞 GIF · 🧩 ملصق · 💬 التعليقات — أزرار أسفل الفيديو\n"
        "🖼 ملصق — أرسل صورة أو فيديو (متحرك)، أو أنشئ حزمتك الخاصة\n"
        "📜 السجل · ⭐ المفضلة — أعد إرسال فيديوهاتك بضغطة واحدة\n"
        "🎁 دعوة — أحضر أصدقاءك واحصل على VIP\n"
        "⚙️ الجودة — اختر HD / عادية / صوت فقط من الإعدادات</blockquote>\n"
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
    "q_title": "🎞 <b>جودة التحميل</b>",
    "q_current": "🔵 الحالية: {cur}",
    "q_hd": "🎬 HD — أفضل جودة",
    "q_sd": "📱 عادية — بيانات أقل",
    "q_audio": "🎵 الصوت فقط (MP3)",
    "qb_hd": "🎬 HD", "qb_sd": "📱 عادية", "qb_audio": "🎵 صوت",
    "q_saved": "✅ تم تغيير الجودة",
    "b_gif": "🎞 GIF", "b_sticker": "🧩 ملصق", "b_comments": "💬 التعليقات",
    "st_gif": "🎞 <b>جارٍ تجهيز GIF…</b>\n{bar}",
    "st_stk": "🧩 <b>جارٍ تجهيز الملصق…</b>\n{bar}",
    "st_cmt": "💬 <b>جارٍ جلب التعليقات…</b>\n{bar}",
    "gif_fail": "❌ تعذّر إنشاء GIF. حاول مرة أخرى.",
    "stk_fail": "❌ تعذّر إنشاء الملصق.",
    "stk_static": "ℹ️ الملصق المتحرك غير متاح على هذا الخادم، لذلك أُرسل ملصق ثابت.",
    "cmt_title": "💬 <b>التعليقات</b> · {n}",
    "cmt_file": "📄 جميع التعليقات ({n})",
    "cmt_none": "💬 لا توجد تعليقات لهذا الفيديو أو تعذّر جلبها.",
    "cmt_fail": "❌ تعذّر جلب التعليقات.",
    "b_mkstk": "🖼 إنشاء ملصق",
    "ask_stk_prompt": "🖼 <b>إنشاء ملصق</b>\n\nأرسل صورة من معرض هاتفك وسأحوّلها إلى ملصق 🧩\n\n💡 لجودة أفضل، أرسل الصورة كـ<b>ملف</b>.",
    "st_mkstk": "🖼 <b>جارٍ تجهيز الملصق…</b>",
    "mkstk_fail": "❌ تعذّر تحويل هذه الصورة إلى ملصق. جرّب صورة أخرى.",
    "mkstk_big": "⚠️ هذه الصورة كبيرة جدًا (أكثر من 20 ميغابايت).",
    "b_hist": "📜 السجل", "b_favs": "⭐ المفضلة", "b_ref": "🎁 دعوة",
    "b_fav": "⭐ مفضلة", "b_faved": "✅ تم الحفظ", "b_hist_clear": "🗑 مسح السجل",
    "hist_title": "📜 <b>سجل التحميل</b> · {n}\n\nاضغط على أي عنصر لإرساله مجددًا 👇",
    "hist_empty": "📜 لم تقم بتحميل أي شيء بعد.\nأرسل رابط تيك توك.",
    "favs_title": "⭐ <b>المفضلة</b> · {n}\n\nاضغط على أي عنصر لإرساله مجددًا 👇",
    "favs_empty": "⭐ قائمة المفضلة فارغة.\nاضغط ⭐ أسفل أي فيديو لإضافته.",
    "hist_cleared": "🗑 تم مسح السجل",
    "fav_added": "⭐ أُضيف إلى المفضلة",
    "fav_removed": "🗑 أُزيل من المفضلة",
    "fav_full": "⚠️ قائمة المفضلة ممتلئة ({n} عنصر). احذف عنصرًا أولًا.",
    "ref_info": "🎁 <b>ادعُ أصدقاءك</b>\n\nلكل <b>{need}</b> أشخاص ينضمون عبر رابطك ويحمّلون فيديو، تحصل على <b>{days} أيام VIP</b> 💎\n\n👥 المدعوون: <b>{cnt}</b>\n📊 للمكافأة التالية: <b>{left}</b> آخرون\n\n🔗 رابطك الخاص:\n<code>{link}</code>",
    "ref_vip_until": "💎 اشتراك VIP فعّال حتى <b>{until}</b>",
    "ref_off": "🎁 نظام الدعوات متوقف حاليًا.",
    "b_ref_share": "📤 مشاركة الرابط",
    "ref_share_text": "🎬 أفضل بوت لتحميل تيك توك بدون علامة مائية! ابدأ من هنا:",
    "ref_progress": "👥 انضم شخص عبر رابطك وحمّل فيديو! ({cnt}/{need})",
    "ref_reward": "🎉 <b>مبروك!</b> حصلت على <b>{days} أيام VIP</b> 💎\nفعّال حتى <b>{until}</b>.",
    "b_sup_ref": "🎁 الدعوات", "b_sup_groups": "👥 المجموعات: {status}",
    "b_ref_toggle": "🔘 الدعوات: {status}",
    "sup_ref_title": "🎁 <b>إعدادات الدعوات</b>\n\nالحالة: {status}\n👥 عدد الدعوات لكل مكافأة: <b>{need}</b>\n💎 مدة VIP: <b>{days}</b> يوم",
    "grp_welcome": "👋 مرحبًا! أنا بوت تحميل تيك توك.\n\nأرسل رابط تيك توك هنا وسأرد بالفيديو بدون علامة مائية 🎬",
    "stk_menu_nopack": "🖼 <b>إنشاء ملصق</b>\n\nأرسل صورة من معرض هاتفك وسأحوّلها إلى ملصق 🧩\n🎞 أرسل فيديو قصيرًا (حتى 3 ثوانٍ) وسأحوّله إلى <b>ملصق متحرك</b>\n\n📦 يمكنك أيضًا إنشاء <b>حزمة ملصقات</b>: تذهب ملصقاتك إلى حزمة واحدة يمكنك إضافتها إلى تيليجرام.\n\n💡 لجودة أفضل، أرسل الصورة كـ<b>ملف</b>.",
    "stk_menu_pack": "🖼 <b>إنشاء ملصق</b>\n\n📦 الحزمة الحالية: <b>{title}</b> ({n}/120)\n\nكل صورة ترسلها تُضاف إلى هذه الحزمة 🧩\n🎞 يتحول الفيديو إلى ملصق متحرك في <b>حزمة منفصلة</b>، لأن تيليجرام لا يخلط ملصقات الصور والفيديو.\n💡 لجودة أفضل، أرسل الصورة كـ<b>ملف</b>.",
    "stk_menu_pending": "🖼 <b>إنشاء ملصق</b>\n\n📦 حزمة جديدة: <b>{title}</b>\n\nأرسل أول <b>صورة أو فيديو</b> وستُنشأ الحزمة به (صورة = حزمة عادية، فيديو = حزمة متحركة) 👇",
    "b_stk_new": "📦 حزمة جديدة", "b_stk_open": "🔗 فتح الحزمة", "b_stk_list": "📂 حزمي",
    "stk_ask_title": "📦 <b>أرسل اسمًا لحزمتك</b>\n\nمثال: <code>ملصقاتي</code>",
    "stk_title_ok": "✅ الحزمة <b>{title}</b> جاهزة.\n\nأرسل الآن أول صورة أو فيديو وستُنشأ الحزمة به 🖼",
    "stk_title_bad": "⚠️ يجب أن يكون الاسم من 1 إلى 60 حرفًا. أرسله مرة أخرى:",
    "stk_created": "🎉 <b>تم إنشاء حزمتك!</b>\n📦 {title}\n\nاضغط الزر لإضافتها إلى تيليجرام 👇",
    "stk_full": "⚠️ هذه الحزمة ممتلئة (120 ملصقًا). أنشئ حزمة جديدة.",
    "stk_gone": "⚠️ هذه الحزمة لم تعد موجودة في تيليجرام. أنشئ حزمة جديدة.",
    "stk_list_title": "📂 <b>حزمي</b>\n\nالحزمة الحالية معلّمة بـ ✅ — اضغط على أي حزمة للتبديل:",
    "stk_switched": "✅ تم تغيير الحزمة الحالية",
    "stk_del_confirm": "⚠️ <b>هل أنت متأكد أنك تريد حذف هذه الحزمة؟</b>\n\n📦 {title} ({n} ملصقًا)\n\nلا يمكن التراجع عن هذا: ستُحذف الحزمة وكل ملصقاتها من تيليجرام.",
    "b_stk_del_yes": "✅ نعم، احذفها", "b_stk_del_no": "❌ لا، رجوع",
    "stk_deleted": "🗑 تم حذف الحزمة",
    "stk_del_fail": "❌ تعذّر حذف الحزمة. حاول مرة أخرى.",
    "stk_menu_vpack": "🎞 الحزمة المتحركة: <b>{title}</b> ({n}/120)",
    "vstk_noffmpeg": "⚠️ الملصقات المتحركة غير متاحة على هذا الخادم (ffmpeg غير موجود).",
    "vstk_trim": "ℹ️ يسمح تيليجرام بـ<b>3 ثوانٍ</b> فقط للملصق المتحرك، لذلك استُخدمت أول 3 ثوانٍ من الفيديو.",
    "b_top": "🏆 الأفضل", "b_fwlist": "🔔 المتابَعون",
    "lb_title": "🏆 <b>أفضل الداعين</b>\n<i>كلما أحضرت أصدقاء أكثر ارتفع ترتيبك</i>",
    "lb_empty": "لم يدعُ أحد أحدًا بعد. كن الأول! 🎁",
    "lb_you": "📍 ترتيبك: <b>#{rank}</b> — {n} مدعو",
    "lb_hidden": "🙈 اسم مخفي",
    "b_lb_hide": "🙈 أخفِ اسمي", "b_lb_show": "👁 أظهر اسمي",
    "lb_toast_hide": "🙈 تم إخفاء اسمك", "lb_toast_show": "👁 اسمك ظاهر الآن",
    "stars_info": "⭐ <b>اشترِ بنجوم تيليجرام</b> — يتفعل فورًا. كل خطة لمدة محددة وتُضاف إلى VIP الحالي.",
    "b_buy": "💎 {days} أيام — {stars} ⭐",
    "stars_off": "⚠️ الشراء غير متاح حاليًا.",
    "stars_changed": "تغيّر السعر. يرجى اختيار الخطة مرة أخرى.",
    "stars_thanks": "🎉 <b>شكرًا على الشراء!</b>\n\n💎 تم تفعيل {days} أيام VIP\n📅 حتى <b>{until}</b>",
    "inv_title": "💎 VIP — {days} أيام",
    "inv_desc": "{days} أيام VIP لبوت تحميل تيك توك: فيديوهات أكثر وكل المزايا.",
    "b_sup_stars": "💎 النجوم: {status}", "b_stars_toggle": "🔘 البيع بالنجوم: {status}",
    "sup_stars_title": "💎 <b>إعدادات نجوم تيليجرام</b>\n\nالحالة: {status}\n💰 إجمالي الأرباح: <b>{total}</b> ⭐\n\nعدّل سعر كل خطة:",
    "fw_b_off": "🔔 متابعة", "fw_b_on": "✅ تتم المتابعة",
    "fw_on": "🔔 تمت المتابعة! سأخبرك عندما ينشر فيديو جديدًا.",
    "fw_off": "🔕 تم إلغاء المتابعة",
    "fw_limit": "⚠️ وصلت إلى حد المتابعة ({n} حسابات). VIP يتيح حتى {vip}.",
    "fw_empty": "🔔 لا تتابع أي حساب بعد.\nافتح ملف تيك توك واضغط 🔔.",
    "fw_list_title": "🔔 <b>المتابَعون</b> · {n}/{max}\n\nاضغط على اسم لأحدث الفيديوهات، أو 🔕 لإلغاء المتابعة:",
    "fw_new": "🔔 <b>@{user}</b> نشر فيديو جديدًا!\n\n{title}",
    "fw_b_dl": "⬇️ تحميل", "fw_b_stop": "🔕 إيقاف التنبيهات",
    "stk_menu_tip": "🎨 بعد إرسال صورة أو فيديو تختار الشكل: حواف مستديرة أو مربع أو دائرة.\n✍️ لكتابة نص على الملصق، أرسله كـ<b>تعليق</b> للصورة.",
    "ss_ask": "🎨 <b>ما الشكل الذي تريده للملصق؟</b>\n\n▭ <b>حواف مستديرة</b> — تبقى نسبة الصورة كما هي\n⬛ <b>مربع</b> — قص من الوسط إلى مربع\n⚪ <b>دائرة</b> — مثل صورة الملف الشخصي",
    "ss_expired": "⌛ انتهت صلاحية هذا الطلب. أرسل الصورة أو الفيديو مرة أخرى.",
    "b_font_auto": "🔄 تلقائي", "b_font_ku": "🔤 كردي", "b_font_en": "🔠 إنجليزي",
    "ss_font_hint": "🔤 اختر <b>خط</b> النص: تلقائي أو كردي أو إنجليزي. ثم الشكل.",
    "stk_font_missing": "ℹ️ الخط المختار لا يحتوي بعض أحرف هذا النص، لذلك استُخدم الخط المدمج في البوت.",
    "b_shape_round": "▭ حواف مستديرة", "b_shape_sq": "⬛ مربع", "b_shape_circle": "⚪ دائرة", "b_shape_cancel": "❌ إلغاء",
    "stk_text_unsupported": "ℹ️ النص الكردي/العربي غير مدعوم على هذا الخادم، لذلك أُنشئ الملصق بدون نص.",
    "vstk_notext": "ℹ️ النص على الملصقات المتحركة غير مدعوم (للصور فقط).",
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
    # ── edit audio title / artist ─────────────────────────────────────────────
    "b_aedit": "✏️ تعديل الأسماء",
    "b_aedit_title": "🎵 اسم الصوت", "b_aedit_perf": "👤 اسم الفنان", "b_aedit_back": "↩️ رجوع",
    "ask_aedit_title": "✏️ <b>اكتب اسم الصوت الجديد</b>\n\nالحالي: <code>{cur}</code>\n<i>(رُدّ على هذه الرسالة)</i>",
    "ask_aedit_perf": "✏️ <b>اكتب اسم الفنان الجديد</b>\n\nالحالي: <code>{cur}</code>\n<i>(رُدّ على هذه الرسالة)</i>",
    "aedit_done": "✅ <b>تم تحديث الأسماء</b>\n🎵 {title}\n👤 {perf}",
    "aedit_fail": "❌ تعذّر تغيير الاسم. حمّل الصوت مجدداً وحاول.",
    "aedit_expired": "⌛ انتهت صلاحية التعديل. اضغط ✏️ مجدداً.",
    "aedit_empty": "⚠️ أرسل اسماً صالحاً (نص).",
    "aedit_noaudio": "لم يُرسل هذا الملف كصوت لذا لا يمكن تغيير اسمه.",
    "aedit_same": "ℹ️ هذا هو الاسم الحالي بالفعل.",
    # ── discover (search + trending) ──────────────────────────────────────────
    "b_disc_kurd": "🏔 فيديوهات كردية",
    "disc_kurd_title": "🏔 <b>فيديوهات كردية</b>\n\nاختر موضوعاً وسأحضر لك أفضل الفيديوهات من كوردستان:",
    "b_disc": "🔥 اكتشف", "b_disc_search": "🔍 بحث بكلمة", "b_disc_more": "➡️ المزيد", "b_disc_new": "🔍 بحث جديد",
    "disc_title": "🔥 <b>اكتشف</b>\n\nابحث في تيك توك أو تصفّح الفيديوهات الرائجة في بلد ما، ثم اختر أي فيديو لتحميله.\n\n🌍 <b>الرائج حسب البلد:</b>",
    "ask_search_prompt": "🔍 <b>البحث في تيك توك</b>\n\nاكتب كلمة أو اسماً:\nمثال: <code>football</code>",
    "st_disc": "🔎 <b>جارٍ البحث…</b>\n{bar}",
    "disc_res_search": "🔍 <b>«{q}»</b>", "disc_res_trend": "🔥 <b>الرائج {region}</b>",
    "disc_pick": "👇 اضغط على رقم الفيديو لتحميله",
    "disc_none": "📭 لم يتم العثور على نتائج.",
    "disc_fail": "⚠️ تعذّر تحميل النتائج الآن. حاول لاحقاً.",
    "disc_expired": "⌛ هذه القائمة قديمة — ابحث من جديد.",
    # ── profile hub ───────────────────────────────────────────────────────────
    "profile_card": "👤 <b>{name}</b> {badge}\n<code>@{user}</code>{stats}{bio}\n\n⚡ <a href=\"https://t.me/{bot}\">@{bot}</a>",
    "pf_followers": "👥 المتابعون", "pf_following": "➕ يتابع", "pf_likes": "❤️ الإعجابات", "pf_videos": "🎬 الفيديوهات",
    "pf_b_vids": "🎬 آخر الفيديوهات", "pf_b_file": "📎 صورة HD (ملف)", "pf_b_open": "🔗 الحساب",
    "st_latest": "🎬 <b>جارٍ جلب آخر الفيديوهات…</b>\n{bar}",
    "latest_header": "🎬 <b>آخر فيديوهات @{user}</b>\n<blockquote>📥 {n} فيديو قيد الإرسال</blockquote>",
    "latest_none": "📭 <b>@{user}</b> ليس لديه فيديوهات (أو منشورات صور فقط).",
    "latest_unavailable": "⚠️ تعذّر جلب فيديوهات هذا الحساب. حاول لاحقاً.",
    "latest_done": "✅ تم إرسال <b>{n} فيديو</b>",
    "latest_partial": "⏱ انتهى الوقت — أُرسل <b>{n}</b> فيديو وتبقّى <b>{left}</b>. اضغط الزر أدناه للمتابعة.",
    "latest_vip_hint": "💎 المستخدم العادي يحصل على {free} فيديو — و<b>VIP</b> حتى {vip}.",
    "no_story": "📭 <b>@{user}</b> لا يملك قصصاً نشطة حالياً.\nقصص تيك توك تبقى 24 ساعة.",
    "story_unavailable": "⚠️ قصص هذا الحساب غير متاحة (ربما الحساب خاص أو المصدر لا يدعمها).",
    "b_story": "🕵️ قصة سرية", "b_story_again": "🔄 قصة أخرى",
    "b_dl": "📥 تحميل جديد", "b_profile": "👤 الملف الشخصي", "b_vip": "💎 VIP", "b_avatar": "🔎 حساب تيك توك",
    "b_lang": "⚙️ الإعدادات", "b_help": "📖 المساعدة", "b_channel": "📢 قناة البوت",
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
def is_vip(uid) -> bool:     return uid in vip_set or is_super(uid) or vip_until.get(uid, 0) > time.time()
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
    global super_admins_set, admins_set, channels_list, blocked_set, vip_set, vip_until, last_cfg_load
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
    vu = d.get("vip_until")
    if isinstance(vu, dict):
        now = time.time()
        vip_until = {int(k): int(v) for k, v in vu.items()
                     if str(k).isdigit() and isinstance(v, (int, float)) and v > now}
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
        ud["_new"] = True                                         # in-memory only: first contact (not saved)
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


# ── media cache (Telegram file_ids) + per-user quality ───────────────────────
_KEY_RE = re.compile(r"[A-Za-z0-9]{1,24}")


def safe_key(k) -> bool:
    """Media keys are digits (TikTok id) or a short hex hash — nothing else may reach a DB path."""
    return isinstance(k, str) and _KEY_RE.fullmatch(k) is not None


def _url_hash(url: str) -> str:
    return hashlib.md5(url.strip().encode()).hexdigest()[:20]


def bot_tag() -> str:
    return f"⚡ <a href=\"https://t.me/{BOT_USERNAME}\">@{esc(BOT_USERNAME)}</a>"


async def user_quality(uid: int) -> str:
    q = await db_get(f"users/{uid}/q")
    return q if q in QUALITIES else "hd"


async def cache_get(key: str) -> dict | None:
    if not safe_key(key):
        return None
    d = await db_get(f"fc/{key}")
    return d if isinstance(d, dict) and d.get("src") else None


async def remember_media(media: dict, url: str) -> None:
    """Store the (small) metadata of a result + a link→key map, so a repeated link is instant."""
    key = media.get("key")
    if not safe_key(key):
        return
    await db_patch(f"fc/{key}", {
        "key": key, "src": media.get("src") or url,
        "creator": clip(media.get("creator") or "", 80), "title": clip(media.get("title") or "", 300),
        "duration": _to_int(media.get("duration")),
        "views": _to_int(media.get("views")), "likes": _to_int(media.get("likes")),
        "comments": _to_int(media.get("comments")), "shares": _to_int(media.get("shares")),
        "hv": 1 if media.get("videos") else 0, "ha": 1 if media.get("audio") else 0,
        "ts": int(time.time()),
    })
    await db_put(f"uc/{_url_hash(url)}", key)


async def save_fid(key: str, field: str, sent, attr: str) -> None:
    """Remember the file_id Telegram gave us (video / audio / animation) → next time: no upload."""
    try:
        fid = getattr(getattr(sent, attr, None), "file_id", None)
        if fid and safe_key(key):
            await db_put(f"fc/{key}/{field}", fid)
    except Exception as e:                                   # noqa: BLE001 — caching is best effort
        log.info("save_fid failed: %s", e)


def media_from_cache(hit: dict) -> dict:
    return {
        "key": hit.get("key") or "", "src": hit.get("src") or "",
        "creator": hit.get("creator") or "TikTok", "title": hit.get("title") or "", "cover": "",
        "duration": _to_int(hit.get("duration")),
        "videos": [("cache", 0)] if hit.get("hv") else [],          # marker only: "this post has a video"
        "audio": "cache" if hit.get("ha") else "", "a_title": "", "a_author": "", "images": [],
        "views": _to_int(hit.get("views")), "likes": _to_int(hit.get("likes")),
        "comments": _to_int(hit.get("comments")), "shares": _to_int(hit.get("shares")),
    }


async def send_from_cache(ctx, chat_id: int, lang: str, url: str, quality: str) -> dict | None:
    """Repeated link → send by file_id (≈1 s, no API call, no download, no upload). None → do it the normal way."""
    key = await db_get(f"uc/{_url_hash(url)}")
    if not safe_key(key):
        return None
    hit = await cache_get(key)
    if not hit:
        return None
    m = media_from_cache(hit)
    auto = bool(CFG.get("auto_audio"))
    try:
        if quality == "audio" and hit.get("fid_a"):
            await ctx.bot.send_audio(chat_id, hit["fid_a"], caption=f"🎵 {bot_tag()}",
                                     reply_markup=audio_kb(lang), **_UP)
            return m
        if quality == "audio":
            return None
        fid = hit.get("fid_hd" if quality == "hd" else "fid_sd")          # exactly the quality the user chose
        if not fid or (auto and m["audio"] and not hit.get("fid_a")):
            return None
        await ctx.bot.send_video(chat_id, fid, caption=build_caption(m),
                                 reply_markup=result_kb(lang, m, with_audio=not auto), **_UP)
        if auto and hit.get("fid_a"):
            await ctx.bot.send_audio(chat_id, hit["fid_a"], caption=f"🎵 {bot_tag()}",
                                     reply_markup=audio_kb(lang), **_UP)
        return m
    except TelegramError as e:
        log.info("cache send failed (%s) → normal path", e)
        return None


async def count_download(uid: int, ctx=None) -> None:
    await db_incr("sys/cfg/total_dl")
    await db_incr(f"users/{uid}/dl")
    if ctx is not None and CFG.get("ref_on", True):                 # an invited user's first download pays the inviter
        try:
            await credit_referral(ctx, uid)
        except Exception as e:                                       # noqa: BLE001 — never block a download
            log.info("referral credit failed: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# 9c · REFERRAL (free VIP) · HISTORY · FAVORITES · GROUPS
# ══════════════════════════════════════════════════════════════════════════════
HIST_MAX, FAV_MAX, LIST_PAGE = 40, 60, 8


def ref_link(uid: int) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"


def fmt_ts(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


async def grant_temp_vip(uid: int, days: float) -> int:
    """Add `days` of VIP on top of what the user still has. → new expiry (epoch seconds)."""
    until = max(vip_until.get(uid, 0), int(time.time())) + int(days * 86400)
    vip_until[uid] = until
    await db_put(f"sys/vip_until/{uid}", until)
    return until


async def register_referral(new_uid: int, raw: str) -> None:
    """/start ref_<inviter> by a brand-new user → remembered; it counts after the first download."""
    if not CFG.get("ref_on", True) or not raw.isdigit():
        return
    inviter = int(raw)
    if inviter == new_uid or not await user_exists(inviter):
        return
    await db_put(f"users/{new_uid}/ref_by", inviter)


async def credit_referral(ctx, uid: int) -> None:
    """The invited user finished a first download → progress (or reward) for the inviter."""
    inviter = await db_get(f"users/{uid}/ref_by")
    if not isinstance(inviter, int):
        return
    await db_del(f"users/{uid}/ref_by")                        # one-shot: each invited user counts once
    await db_incr(f"users/{inviter}/ref_cnt")
    cnt = int(await db_get(f"users/{inviter}/ref_cnt", 0) or 0)
    done = int(await db_get(f"users/{inviter}/ref_done", 0) or 0)
    need = max(1, int(CFG.get("ref_need", 5)))
    days = max(1, int(CFG.get("ref_days", 3)))
    iud = await db_get(f"users/{inviter}") or {}
    lang = user_lang(iud)
    await db_put(f"lb/{inviter}", {"n": cnt, "name": clip(iud.get("name") or "", 20), "h": 1 if iud.get("hide_lb") else 0})
    if cnt // need > done:
        n = cnt // need - done
        until = await grant_temp_vip(inviter, days * n)
        await db_put(f"users/{inviter}/ref_done", cnt // need)
        text = tx(lang, "ref_reward", days=days * n, until=fmt_ts(until))
    else:
        text = tx(lang, "ref_progress", cnt=cnt % need, need=need)
    try:
        await ctx.bot.send_message(inviter, text)
    except TelegramError as e:
        log.info("referral notice failed: %s", e)


async def ref_view(uid: int, lang: str) -> tuple[str, Kb]:
    if not CFG.get("ref_on", True):
        return tx(lang, "ref_off"), Kb([back_row(lang)])
    ud = await db_get(f"users/{uid}")
    cnt = int((ud or {}).get("ref_cnt", 0) or 0)
    need = max(1, int(CFG.get("ref_need", 5)))
    days = max(1, int(CFG.get("ref_days", 3)))
    link = ref_link(uid)
    text = tx(lang, "ref_info", need=need, days=days, cnt=cnt, left=need - cnt % need, link=link)
    until = vip_until.get(uid, 0)
    if until > time.time():
        text += "\n\n" + tx(lang, "ref_vip_until", until=fmt_ts(until))
    share = (f"https://t.me/share/url?url={urllib.parse.quote(link)}"
             f"&text={urllib.parse.quote(tx(lang, 'ref_share_text'))}")
    return text, Kb([[Btn(tx(lang, "b_ref_share"), url=share)], back_row(lang)])


# ── history / favorites ──────────────────────────────────────────────────────
async def hist_add(uid: int, media: dict) -> None:
    key = media.get("key")
    if not safe_key(key):
        return
    try:
        await db_put(f"hist/{uid}/{key}", {"c": clip(media.get("creator") or "", 30),
                                           "t": clip(media.get("title") or "", 60),
                                           "ts": int(time.time()), "i": 1 if media.get("images") else 0})
    except Exception as e:                                           # noqa: BLE001 — history is best effort
        log.info("hist_add failed: %s", e)


async def _load_items(path: str, cap: int) -> list:
    d = await db_get(path)
    if not isinstance(d, dict):
        return []
    items = [(k, v) for k, v in d.items() if safe_key(k) and isinstance(v, dict)]
    items.sort(key=lambda kv: kv[1].get("ts", 0), reverse=True)
    for k, _ in items[cap:]:                                         # keep the list tidy
        await db_del(f"{path}/{k}")
    return items[:cap]


def _item_label(it: dict) -> str:
    text = f"{'🖼' if it.get('i') else '🎬'} {it.get('c') or 'TikTok'}"
    if it.get("t"):
        text += f" · {it['t']}"
    return clip(text, 40)


async def list_view(uid: int, lang: str, kind: str, page: int) -> tuple[str, Kb]:
    """kind: "hist" (download history) | "fav" (favorites)."""
    hist = kind == "hist"
    items = await _load_items(f"{'hist' if hist else 'fav'}/{uid}", HIST_MAX if hist else FAV_MAX)
    if not items:
        return tx(lang, "hist_empty" if hist else "favs_empty"), Kb([back_row(lang)])
    pages = -(-len(items) // LIST_PAGE)
    page = max(0, min(page, pages - 1))
    rows = [[Btn(_item_label(v), callback_data=f"rs_{k}")] for k, v in items[page * LIST_PAGE:(page + 1) * LIST_PAGE]]
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(Btn("◀️", callback_data=f"my_{kind}_{page - 1}"))
        nav.append(Btn(f"{page + 1}/{pages}", callback_data="noop"))
        if page < pages - 1:
            nav.append(Btn("▶️", callback_data=f"my_{kind}_{page + 1}"))
        rows.append(nav)
    if hist:
        rows.append([Btn(tx(lang, "b_hist_clear"), callback_data="hist_clr")])
    rows.append(back_row(lang))
    return tx(lang, "hist_title" if hist else "favs_title", n=len(items)), Kb(rows)


async def _mark_fav_button(cb: "CB", key: str, on: bool) -> None:
    try:
        old = cb.q.message.reply_markup.inline_keyboard
    except AttributeError:
        return
    rows = []
    for row in old:
        new = []
        for b in row:
            if b.callback_data == f"fav_{key}":
                new.append(Btn(cb.t("b_faved" if on else "b_fav"), callback_data=b.callback_data))
            elif b.callback_data:
                new.append(Btn(b.text, callback_data=b.callback_data))
            else:
                new.append(Btn(b.text, url=b.url))
        rows.append(new)
    try:
        await cb.q.message.edit_reply_markup(reply_markup=Kb(rows))
    except TelegramError:
        pass


async def toggle_fav(cb: "CB", key: str) -> None:
    if not safe_key(key):
        return await cb.answer()
    uid = cb.uid
    if await db_get(f"fav/{uid}/{key}") is not None:
        await db_del(f"fav/{uid}/{key}")
        await cb.answer(cb.t("fav_removed"))
        return await _mark_fav_button(cb, key, False)
    if len((await db_get(f"fav/{uid}")) or {}) >= FAV_MAX:
        return await cb.answer(cb.t("fav_full", n=FAV_MAX), True)
    hit = await cache_get(key) or {}
    await db_put(f"fav/{uid}/{key}", {"c": clip(hit.get("creator") or "TikTok", 30),
                                      "t": clip(hit.get("title") or "", 60), "ts": int(time.time()), "i": 0})
    await cb.answer(cb.t("fav_added"))
    await _mark_fav_button(cb, key, True)


# ── admin: referral settings ─────────────────────────────────────────────────
async def ref_admin_view(cb: "CB") -> None:
    need, days = int(CFG.get("ref_need", 5)), int(CFG.get("ref_days", 3))
    on = CFG.get("ref_on", True)
    rows = [
        [Btn(cb.t("b_ref_toggle", status=status_word(cb.lang, on)), callback_data="sup_ref_t")],
        [Btn("➖", callback_data="sup_ref_n-1"), Btn(f"👥 {need}", callback_data="noop"),
         Btn("➕", callback_data="sup_ref_n+1")],
        [Btn("-7", callback_data="sup_ref_d-7"), Btn("-1", callback_data="sup_ref_d-1"),
         Btn(f"💎 {days}d", callback_data="noop"),
         Btn("+1", callback_data="sup_ref_d+1"), Btn("+7", callback_data="sup_ref_d+7")],
        back_row(cb.lang, "panel_unified"),
    ]
    await cb.edit(cb.t("sup_ref_title", status=status_word(cb.lang, on), need=need, days=days), Kb(rows))


async def route_ref_admin(cb: "CB", data: str) -> None:
    if data == "sup_ref_t":
        await set_cfg(ref_on=not CFG.get("ref_on", True))
    elif data.startswith(("sup_ref_n", "sup_ref_d")):
        try:
            delta = int(data[len("sup_ref_n"):])
        except ValueError:
            return await cb.answer()
        if data.startswith("sup_ref_n"):
            await set_cfg(ref_need=max(1, min(100, int(CFG.get("ref_need", 5)) + delta)))
        else:
            await set_cfg(ref_days=max(1, min(365, int(CFG.get("ref_days", 3)) + delta)))
    await cb.answer()
    await ref_admin_view(cb)


# ── groups ───────────────────────────────────────────────────────────────────
class _ReplyBot:
    """In a group, every send to that chat becomes a reply to the user's link message."""
    _WRAP = {"send_video", "send_audio", "send_photo", "send_document", "send_animation",
             "send_media_group", "send_message"}

    def __init__(self, bot, chat_id: int, mid: int):
        self._bot, self._chat, self._mid = bot, chat_id, mid

    def __getattr__(self, name):
        fn = getattr(self._bot, name)
        if name not in self._WRAP:
            return fn

        async def call(*a, **k):
            target = a[0] if a else k.get("chat_id")
            if target == self._chat:
                k.setdefault("reply_parameters",
                             ReplyParameters(message_id=self._mid, allow_sending_without_reply=True))
            return await fn(*a, **k)
        return call


class _ReplyCtx:
    def __init__(self, ctx, chat_id: int, mid: int):
        self._ctx = ctx
        self.bot = _ReplyBot(ctx.bot, chat_id, mid)

    def __getattr__(self, name):
        return getattr(self._ctx, name)


async def on_my_chat_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """The bot was added to / removed from a group."""
    ev = update.my_chat_member
    if not ev or ev.chat.type not in ("group", "supergroup"):
        return
    old, new = ev.old_chat_member.status, ev.new_chat_member.status
    gone = (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)
    if new in gone:
        await db_del(f"groups/{ev.chat.id}")
        return
    if old in gone and new in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR):
        await db_put(f"groups/{ev.chat.id}", {"title": clip(ev.chat.title or "", 60), "ts": int(time.time())})
        if CFG.get("groups_on", True):
            lang = CFG.get("default_lang", "ku")
            try:
                await ctx.bot.send_message(ev.chat.id, tx(lang if lang in L else "ku", "grp_welcome"))
            except TelegramError:
                pass


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
    def _cands(order: tuple) -> list:
        out: list = []
        for key, skey in order:
            u = abs_url(d.get(key), base)
            if u and u not in [c[0] for c in out]:
                out.append((u, _to_int(d.get(skey))))
        return out

    cands    = _cands((("hdplay", "hd_size"), ("play", "size"), ("wmplay", "wm_size")))    # HD first
    cands_sd = _cands((("play", "size"), ("hdplay", "hd_size"), ("wmplay", "wm_size")))    # standard first
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
        "videos_sd": cands_sd,
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


# ── profile hub (info card) + latest videos ───────────────────────────────────
def _stat(st, *keys):
    """First present numeric stat among `keys` (None when the provider doesn't give it)."""
    if isinstance(st, dict):
        for k in keys:
            if st.get(k) not in (None, ""):
                return _to_int(st[k])
    return None


async def _profile_via_tikwm(username: str) -> dict | None:
    t = min(int(CFG.get("api_timeout", 40)), 20)
    try:
        r = await http().get("https://www.tikwm.com/api/user/info",
                             params={"unique_id": f"@{username}"}, timeout=t)
        j = r.json()
    except Exception as e:
        log.warning("tikwm profile failed: %s", e)
        return None
    data = j.get("data") if j.get("code") == 0 else None
    u = data.get("user") if isinstance(data, dict) else None
    if not isinstance(u, dict) or not u:
        return None
    handle = u.get("uniqueId") or username
    if u.get("privateAccount"):
        return {"private": True, "user": handle}
    st = data.get("stats") or data.get("statsV2") or {}
    return {
        "private": False, "user": handle, "name": u.get("nickname") or "",
        "bio": (u.get("signature") or "").strip(), "verified": bool(u.get("verified")),
        "pic": abs_url(u.get("avatarLarger") or u.get("avatarMedium") or u.get("avatarThumb"),
                       "https://www.tikwm.com"),
        "followers": _stat(st, "followerCount"), "following": _stat(st, "followingCount"),
        "likes": _stat(st, "heartCount", "heart"), "videos": _stat(st, "videoCount"),
    }


async def fetch_profile(username: str) -> dict | None:
    """Card data → {'private': True, 'user'} | full dict | picture-only fallback | None."""
    p = await _profile_via_tikwm(username)
    if p:
        return p
    r = await _avatar_via_scrape(username)
    if r:
        return {"private": False, "user": username, "name": "", "bio": "", "verified": False,
                "pic": r.get("pic", ""), "followers": None, "following": None, "likes": None, "videos": None}
    return None


def profile_card(lang: str, p: dict) -> str:
    rows = [f"{tx(lang, label)}: <b>{fmt_num(p[key])}</b>"
            for key, label in (("followers", "pf_followers"), ("following", "pf_following"),
                               ("likes", "pf_likes"), ("videos", "pf_videos"))
            if p.get(key) is not None]
    stats = "\n<blockquote>" + "\n".join(rows) + "</blockquote>" if rows else ""
    bio = f"\n\n📝 <i>{esc(clip(p['bio'], 220))}</i>" if p.get("bio") else ""
    return tx(lang, "profile_card", name=esc(clip(p.get("name") or p["user"], 60)),
              badge="✔️" if p.get("verified") else "", user=esc(p["user"]), stats=stats, bio=bio,
              bot=esc(BOT_USERNAME))


def profile_kb(lang: str, user: str, followed: bool = False) -> Kb:
    rows = []
    if user.isascii() and len(user) <= 24:            # callback_data is limited to 64 bytes
        rows.append([Btn(tx(lang, "b_story"), callback_data=f"pf_s_{user}"),
                     Btn(tx(lang, "pf_b_vids"), callback_data=f"pf_v_{user}")])
        rows.append([Btn(tx(lang, "pf_b_file"), callback_data=f"pf_f_{user}"),
                     Btn(tx(lang, "pf_b_open"), url=f"https://www.tiktok.com/@{user}")])
        if _USER_RE.fullmatch(user):
            rows.append([Btn(tx(lang, "fw_b_on" if followed else "fw_b_off"), callback_data=f"fw_{user}")])
    rows.append([Btn(tx(lang, "b_delete"), callback_data="close")])
    return Kb(rows)


async def fetch_latest(username: str, n: int) -> list | None:
    """Newest `n` VIDEO posts as normalised media dicts · [] = none · None = provider failure."""
    t = min(int(CFG.get("api_timeout", 40)), 20)
    try:
        r = await http().get("https://www.tikwm.com/api/user/posts",
                             params={"unique_id": f"@{username}", "count": 30, "cursor": 0}, timeout=t)
        j = r.json()
    except Exception as e:
        log.info("tikwm posts failed: %s", e)
        return None
    if j.get("code") != 0 or not isinstance(j.get("data"), dict):
        return None
    vids = [d for d in (j["data"].get("videos") or []) if isinstance(d, dict)]
    vids.sort(key=lambda d: _to_int(d.get("create_time") or d.get("createTime")), reverse=True)  # pinned posts lead otherwise
    out = []
    for d in vids:
        d = dict(d)
        d.setdefault("id", d.get("video_id"))
        if d.get("images"):
            continue                                   # photo post: its `play` link is only the music
        m = parse_tikwm(d, f"https://www.tiktok.com/@{username}/video/{d.get('id')}")
        if m["videos"]:
            out.append(m)
        if len(out) >= n:
            break
    return out


# ── discover: keyword search + country trending ───────────────────────────────
DISC_REGIONS = (("🇮🇶", "IQ"), ("🇸🇦", "SA"), ("🇦🇪", "AE"), ("🇹🇷", "TR"), ("🇺🇸", "US"), ("🇬🇧", "GB"))
DISC_PAGE = 10
_DISC_ERR = {"msg": ""}
# (label per language, search keywords)
_KURD_ANY = re.compile(r"[ڕڵۆێۊ]|کورد|kurd|erbil|hewler|hawler|duhok|dohuk|slemani|sulaym|هەولێر|سلێمانی|دهۆک|کەرکووک|kirkuk|zakho|زاخۆ", re.I)
KURD_TOPICS = (
    ({"ku": "🏔 هەموو ڤیدیۆی کوردی", "en": "🏔 All Kurdish videos", "ar": "🏔 كل الفيديوهات الكردية"}, r""),
    ({"ku": "🎤 گۆرانی", "en": "🎤 Songs", "ar": "🎤 أغاني"}, r"گۆرانی|گورانی|ستران|song|music|singer|ئاواز|دەنگ"),
    ({"ku": "😂 کۆمیدی", "en": "😂 Comedy", "ar": "😂 كوميديا"}, r"کۆمیدی|پێکەنین|comedy|funny|😂|🤣|گاڵتە"),
    ({"ku": "💃 هەڵپەڕکێ", "en": "💃 Dance", "ar": "💃 رقص"}, r"هەڵپەڕکێ|هەلپەرکێ|halparke|govend|dance|dabke|💃"),
    ({"ku": "🏙 هەولێر", "en": "🏙 Erbil", "ar": "🏙 أربيل"}, r"هەولێر|erbil|hewler|hawler"),
    ({"ku": "🏙 سلێمانی", "en": "🏙 Sulaymaniyah", "ar": "🏙 السليمانية"}, r"سلێمانی|slemani|sulaym"),
    ({"ku": "🏙 دهۆک", "en": "🏙 Duhok", "ar": "🏙 دهوك"}, r"دهۆک|duhok|dohuk|zakho|زاخۆ"),
    ({"ku": "🌄 سروشت", "en": "🌄 Nature", "ar": "🌄 طبيعة"}, r"سروشت|nature|چیا|کێو|mountain|🌄|🏔|⛰"),
)


async def fetch_discover(kind: str, q: str = "", region: str = "US", cursor: int = 0):
    """→ (items | None, next_cursor). Items: {'url','title','creator','views','likes'}; None = provider failure."""
    t = 10
    ckey = "dq_" + hashlib.md5(f"{q.lower()}|{cursor}".encode()).hexdigest()[:14]
    if kind == "search":
        hit = await session_get(ckey)
        if hit and time.time() - hit.get("_ts", 0) < 600 and hit.get("items"):
            return _as_list(hit["items"]), _to_int(hit.get("next"))
        base = "https://www.tikwm.com/api/feed/search"
        p = {"keywords": q, "count": DISC_PAGE, "cursor": cursor, "web": 1, "hd": 1}
        attempts = [("post", {"data": p}), ("get", {"params": p}), ("post", {"params": p})]
    else:
        base = "https://www.tikwm.com/api/feed/list"
        attempts = [("get", {"params": {"region": region, "count": DISC_PAGE}})]
    j = None
    for n, (meth, kw) in enumerate(attempts):
        for retry in (0, 1):
            try:
                r = await getattr(http(), meth)(base, timeout=t, **kw)
                j = r.json()
            except Exception as e:
                log.info("discover %s failed: %s", meth, e)
                j = None
                break
            msg_ = str(j.get("msg") or "").lower() if isinstance(j, dict) else ""
            if isinstance(j, dict) and j.get("code") != 0 and "limit" in msg_ and not retry:
                await asyncio.sleep(1.3)                # provider allows ~1 request / second
                continue
            break
        ok = isinstance(j, dict) and j.get("code") == 0 and (
            isinstance(j.get("data"), list) or (isinstance(j.get("data"), dict) and j["data"].get("videos")))
        if ok:
            break
        log.info("discover %s %s → code=%s msg=%s", kind, meth, (j or {}).get("code") if isinstance(j, dict) else None,
                 (j or {}).get("msg") if isinstance(j, dict) else None)
        if n + 1 < len(attempts):
            await asyncio.sleep(1.2)
    if not isinstance(j, dict) or j.get("code") != 0:
        _DISC_ERR["msg"] = f"{kind}: code={j.get('code') if isinstance(j, dict) else None} msg={j.get('msg') if isinstance(j, dict) else 'no/invalid response'}"
        if kind == "search":                               # last resort: hashtag (challenge) videos
            items = await _fetch_challenge(q, t)
            if items:
                return items, 0
        return None, 0
    data = j.get("data")
    vids = data if isinstance(data, list) else (data.get("videos") if isinstance(data, dict) else None)
    if not isinstance(vids, list):
        return None, 0
    items = []
    for d in vids:
        if not isinstance(d, dict):
            continue
        au = d.get("author") if isinstance(d.get("author"), dict) else {}
        user, vid = au.get("unique_id") or au.get("uniqueId"), d.get("video_id") or d.get("id")
        if not user or not vid:
            continue
        items.append({"url": f"https://www.tiktok.com/@{user}/video/{vid}", "title": d.get("title") or "",
                      "creator": au.get("nickname") or user, "views": _to_int(d.get("play_count")),
                      "likes": _to_int(d.get("digg_count"))})
    nxt = _to_int(data.get("cursor")) if isinstance(data, dict) else 0
    if kind == "search" and items:
        await session_save(ckey, {"items": items, "next": nxt})
    return items, nxt


def _disc_items(vids) -> list:
    items = []
    for d in vids or []:
        if not isinstance(d, dict):
            continue
        au = d.get("author") if isinstance(d.get("author"), dict) else {}
        user, vid = au.get("unique_id") or au.get("uniqueId"), d.get("video_id") or d.get("id")
        if user and vid:
            items.append({"url": f"https://www.tiktok.com/@{user}/video/{vid}", "title": d.get("title") or "",
                          "creator": au.get("nickname") or user, "views": _to_int(d.get("play_count")),
                          "likes": _to_int(d.get("digg_count"))})
    return items


async def _fetch_challenge(q: str, t: int) -> list:
    """Hashtag fallback: find the #tag matching the keyword, return its videos."""
    try:
        r = await http().post("https://www.tikwm.com/api/challenge/search", data={"keywords": q, "count": 1, "cursor": 0}, timeout=t)
        d = (r.json() or {}).get("data") or {}
        lst = d.get("challenge_list") or d.get("challenges") or (d if isinstance(d, list) else [])
        cid = (lst[0].get("id") or lst[0].get("cid")) if lst and isinstance(lst[0], dict) else None
        if not cid:
            return []
        await asyncio.sleep(1.2)
        r = await http().get("https://www.tikwm.com/api/challenge/posts", params={"challenge_id": cid, "count": DISC_PAGE, "cursor": 0}, timeout=t)
        d = (r.json() or {}).get("data")
        return _disc_items(d if isinstance(d, list) else (d or {}).get("videos"))[:DISC_PAGE]
    except Exception as e:
        log.info("challenge fallback failed: %s", e)
        return []


KURD_POOL_FRESH = 600      # seconds a cached pool is served without touching the provider
KURD_POOL_MAX = 150


def _as_list(x) -> list:
    if isinstance(x, dict):                           # Firebase may hand a list back as {"0":…, "1":…}
        x = [x[k] for k in sorted(x, key=lambda k: int(k) if str(k).isdigit() else 0)]
    return [i for i in (x or []) if isinstance(i, dict)]


async def fetch_kurdish(topic: int, budget: float = 22.0) -> list | None:
    """Kurdish videos from the IQ trending feed (keeps Kurdish letters / words). The pool is cached and
    SHARED by all users, so most taps answer instantly; a refresh is time-boxed to `budget` seconds."""
    t0 = time.monotonic()
    cached = await session_get("kurd_pool") or {}
    pool = _as_list(cached.get("items"))
    fresh = time.time() - cached.get("_ts", 0) < KURD_POOL_FRESH and len(pool) >= DISC_PAGE
    ok = bool(pool)
    if not fresh:
        seen = {it.get("url") for it in pool}
        new, calls = 0, 0
        while time.monotonic() - t0 < budget and calls < 6 and new < 40:
            if calls:
                await asyncio.sleep(1.05)             # provider allows ~1 request / second
            calls += 1
            try:
                r = await http().get("https://www.tikwm.com/api/feed/list", params={"region": "IQ", "count": 20}, timeout=8)
                j = r.json()
            except Exception as e:
                log.info("kurdish feed failed: %s", e)
                continue
            if isinstance(j, dict) and j.get("code") == 0:
                ok = True
                d = j.get("data")
                for it in _disc_items(d if isinstance(d, list) else (d or {}).get("videos")):
                    if it["url"] not in seen and _KURD_ANY.search(f"{it['title']} {it['creator']}"):
                        seen.add(it["url"]); pool.insert(0, it); new += 1
        if new or not cached:
            pool = pool[:KURD_POOL_MAX]
            await session_save("kurd_pool", {"items": pool})
    if not ok:
        return None
    pat = KURD_TOPICS[topic][1] if 0 <= topic < len(KURD_TOPICS) else ""
    if pat:
        rx = re.compile(pat, re.I)
        pool = sorted(pool, key=lambda it: 0 if rx.search(f"{it['title']} {it['creator']}") else 1)
    return pool[:DISC_PAGE]


def disc_menu_view(lang: str) -> tuple[str, Kb]:
    rows = [[Btn(tx(lang, "b_disc_search"), callback_data="disc_search")]]
    flags = [Btn(f"{f} {c}", callback_data=f"disc_t_{c}") for f, c in DISC_REGIONS]
    rows += [flags[i:i + 3] for i in range(0, len(flags), 3)]
    rows.append([Btn(tx(lang, "b_disc_kurd"), callback_data="disc_kurd")])
    rows.append(back_row(lang))
    return tx(lang, "disc_title"), Kb(rows)


def kurd_menu_view(lang: str) -> tuple[str, Kb]:
    btns = [Btn(lbl.get(lang) or lbl["en"], callback_data=f"disc_k_{i}") for i, (lbl, _) in enumerate(KURD_TOPICS)]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    rows.append([Btn(tx(lang, "b_disc_search"), callback_data="disc_search")])
    rows.append(back_row(lang, "ask_disc"))
    return tx(lang, "disc_kurd_title"), Kb(rows)


def disc_kb(lang: str, tok: str, n: int, more: bool) -> Kb:
    nums = [Btn(str(i + 1), callback_data=f"dv_{tok}_{i}") for i in range(n)]
    rows = [nums[i:i + 5] for i in range(0, len(nums), 5)]
    tail = []
    if more:
        tail.append(Btn(tx(lang, "b_disc_more"), callback_data="disc_p"))
    tail.append(Btn(tx(lang, "b_disc_new"), callback_data="disc_search"))
    rows.append(tail)
    rows.append([Btn(tx(lang, "b_delete"), callback_data="close")])
    return Kb(rows)


async def process_discover(update: Update, ctx, lang: str, kind: str, q: str = "", region: str = "US",
                           cursor: int = 0) -> None:
    msg, uid = update.effective_message, update.effective_user.id
    if not await gate_message(update, ctx, uid, lang):
        return
    status = await msg.reply_text(tx(lang, "st_disc", bar=bar(2)))
    try:
        try:
            if kind == "kurd":
                ti = int(q) if q.isdigit() and int(q) < len(KURD_TOPICS) else 0
                items, nxt = await asyncio.wait_for(fetch_kurdish(ti), 40), 0
            else:
                items, nxt = await asyncio.wait_for(fetch_discover(kind, q, region, cursor), 40)
        except asyncio.TimeoutError:                        # never leave the "searching…" bar hanging
            items, nxt = None, 0
            _DISC_ERR["msg"] = f"{kind}: timeout"
        if items is None:
            note = f"\n\n<code>{esc(_DISC_ERR['msg'][:160])}</code>" if is_admin(uid) and _DISC_ERR["msg"] else ""
            return await safe_edit(status, tx(lang, "disc_fail") + note)
        if not items:
            return await safe_edit(status, tx(lang, "disc_none"))
        tok = os.urandom(2).hex()
        await session_save(f"disc_{uid}", {"tok": tok, "kind": kind, "q": q, "region": region,
                                           "cursor": nxt, "items": items})
        if kind == "kurd":
            lbl = KURD_TOPICS[ti][0]
            head = f"<b>{lbl.get(lang) or lbl['en']}</b>"
        elif kind == "search":
            head = tx(lang, "disc_res_search", q=esc(clip(q, 40)))
        else:
            head = tx(lang, "disc_res_trend", region=esc(region))
        lines = [f"<b>{i + 1}.</b> {esc(clip(it['title'] or it['creator'], 55))}\n"
                 f"      👤 {esc(clip(it['creator'], 24))} · ▶️ {fmt_num(it['views'])} · ❤️ {fmt_num(it['likes'])}"
                 for i, it in enumerate(items)]
        text = head + "\n\n" + "\n".join(lines) + "\n\n" + tx(lang, "disc_pick")
        await safe_edit(status, text, disc_kb(lang, tok, len(items), kind in ("trend", "kurd") or (kind == "search" and nxt > 0)))
    except Exception as e:                                              # noqa: BLE001
        await report_error(ctx, e, "process_discover")
        await safe_edit(status, tx(lang, "disc_fail"))


def _is_search_reply(msg) -> bool:
    """True when the user is replying to the bot's 'type a keyword' search prompt."""
    r = getattr(msg, "reply_to_message", None)
    if not r or not r.from_user or not r.from_user.is_bot or not r.text:
        return False
    heads = {plain(tx(l, "ask_search_prompt")).split("\n")[0] for l in L}
    return r.text.split("\n")[0].strip() in heads


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


async def fetch_video(media: dict, quality: str = "hd") -> tuple[bytes | None, str | None]:
    """Try every candidate URL (HD first, or standard first when quality == "sd").
    → (bytes | None, direct_url_if_too_big | None)"""
    big = None
    cands = (media.get("videos_sd") or media["videos"]) if quality == "sd" else media["videos"]
    for url, size in cands:
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
    stats = (f"👁 {fmt_num(m['views'])}\n❤️ {fmt_num(m['likes'])}\n"
             f"💬 {fmt_num(m['comments'])}\n🔁 {fmt_num(m['shares'])}")
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
    extra = []
    key = str(m.get("key") or "")
    if safe_key(key) and _valid_button_url(m.get("src", "")):
        if m.get("videos"):
            extra += [Btn(tx(lang, "b_gif"), callback_data=f"dl_gif_{key}"),
                      Btn(tx(lang, "b_sticker"), callback_data=f"dl_stk_{key}")]
        extra.append(Btn(tx(lang, "b_comments"), callback_data=f"dl_cmt_{key}"))
    if extra:
        rows.append(extra)
    last = [Btn(tx(lang, "b_delete"), callback_data="close")]
    if safe_key(key):
        last.insert(0, Btn(tx(lang, "b_fav"), callback_data=f"fav_{key}"))
    rows.append(last)
    return Kb(rows)


# ── Telegram uploaders (all have generous timeouts: uploads are slow) ────────
_UP = dict(read_timeout=120, write_timeout=120, connect_timeout=20, pool_timeout=20)


async def send_video_file(ctx, chat_id: int, m: dict, data: bytes, kb: Kb):
    """Upload a video; returns the sent Message (its file_id is cached by the caller)."""
    name = f"{safe_name(m['creator'])}_{m['key']}.mp4"
    try:
        return await ctx.bot.send_video(
            chat_id, InputFile(data, filename=name), caption=build_caption(m),
            duration=m.get("duration") or None, supports_streaming=True, reply_markup=kb, **_UP,
        )
    except BadRequest as e:                       # e.g. codec/format rejected → send as a file
        log.info("send_video rejected (%s) → document fallback", e)
        return await ctx.bot.send_document(chat_id, InputFile(data, filename=name),
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


def audio_kb(lang: str) -> Kb:
    return Kb([[Btn(tx(lang, "b_aedit"), callback_data="aedit")],
               [Btn(tx(lang, "b_delete"), callback_data="close")]])


def aedit_menu_kb(lang: str) -> Kb:
    return Kb([[Btn(tx(lang, "b_aedit_title"), callback_data="aedit_t"),
                Btn(tx(lang, "b_aedit_perf"), callback_data="aedit_p")],
               [Btn(tx(lang, "b_aedit_back"), callback_data="aedit_x")]])


async def send_audio_file(ctx, chat_id: int, s: dict, data: bytes, ctype: str, kb: Kb | None = None):
    ext = _ext(ctype, "mp3")
    title = clip(s.get("a_title") or s.get("title") or "TikTok", 60)
    fn = f"{safe_name(title, 'audio')}.{ext}"
    performer = clip(s.get("a_author") or s.get("creator") or "TikTok", 60)
    try:
        return await ctx.bot.send_audio(chat_id, InputFile(data, filename=fn), title=title, performer=performer,
                                        caption=f"🎵 {bot_tag()}", reply_markup=kb, **_UP)
    except BadRequest:
        return await ctx.bot.send_document(chat_id, InputFile(data, filename=fn), reply_markup=kb, **_UP)


async def send_avatar_photo(ctx, chat_id: int, lang: str, username: str, data: bytes, ctype: str,
                            kb: Kb | None = None, caption: str | None = None) -> None:
    """Deliver a profile picture. HD avatars are usually a few hundred KB → send as photo,
    but fall back to a document if Telegram's photo pipeline rejects it (rare, large PNGs)."""
    ext = _ext(ctype, "jpg")
    fn = f"{safe_name(username, 'profile')}.{ext}"
    caption = caption or tx(lang, "avatar_caption", user=esc(username), bot=esc(BOT_USERNAME))
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
        [Btn(tx(lang, "b_story"), callback_data="ask_story"),
         Btn(tx(lang, "b_disc"), callback_data="ask_disc")],
        [Btn(tx(lang, "b_mkstk"), callback_data="ask_sticker"),
         Btn(tx(lang, "b_ref"), callback_data="show_ref")],
        [Btn(tx(lang, "b_hist"), callback_data="my_hist_0"),
         Btn(tx(lang, "b_favs"), callback_data="my_fav_0")],
        [Btn(tx(lang, "b_fwlist"), callback_data="fw_list"),
         Btn(tx(lang, "b_top"), callback_data="show_top")],
        [Btn(tx(lang, "b_profile"), callback_data="show_profile"),
         Btn(tx(lang, "b_vip"), callback_data="show_vip")],
        [Btn(tx(lang, "b_lang"), callback_data="show_settings"),
         Btn(tx(lang, "b_help"), callback_data="show_help")],
        [Btn(tx(lang, "b_channel"), url=CHANNEL_URL)],
    ]
    if is_admin(uid):
        rows.append([Btn(tx(lang, "b_panel"), callback_data="panel_unified")])
    return text, Kb(rows)


async def settings_view(uid: int, lang: str) -> tuple[str, Kb]:
    """Language + download quality."""
    q = await user_quality(uid)
    text = (f"{tx(lang, 'lang_title')}\n\n{tx(lang, 'lang_current', cur=LANG_NAMES.get(lang, '?'))}\n\n"
            f"{tx(lang, 'q_title')}\n{tx(lang, 'q_current', cur=tx(lang, 'q_' + q))}")
    qrow = [Btn(("✅ " if q == c else "") + tx(lang, "qb_" + c), callback_data=f"set_q_{c}") for c in QUALITIES]
    return text, Kb(lang_buttons("set_lang_") + [qrow, back_row(lang)])


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
    arg = (ctx.args[0] if getattr(ctx, "args", None) else "") or ""
    if arg.startswith("ref_") and ud.get("_new"):                    # came through someone's invite link
        await register_referral(uid, arg[4:])
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

    if data == "ask_sticker":
        await cb.answer()
        text, kb = await stk_menu_view(uid, lang)
        return await cb.edit(text, kb)

    if data == "stk_new":
        await cb.answer()
        return await cb.q.message.reply_text(cb.t("stk_ask_title"), reply_markup=ForceReply(selective=True))

    if data == "stk_list":
        await cb.answer()
        text, kb = await stk_list_view(uid, lang)
        return await cb.edit(text, kb)

    if data.startswith("stk_use_"):
        hx = data[len("stk_use_"):]
        packs = await stk_packs(uid)
        if _HEX_RE.fullmatch(hx) and hx in packs:
            await db_put(f"stk/{uid}/{_active_key(packs[hx])}", hx)
            await db_del(f"stk/{uid}/pending")
            await cb.answer(cb.t("stk_switched"))
        else:
            await cb.answer()
        text, kb = await stk_list_view(uid, lang)
        return await cb.edit(text, kb)

    if data.startswith("stk_del_"):                                      # step 1: ask "are you sure?"
        hx = data[len("stk_del_"):]
        p = (await stk_packs(uid)).get(hx) if _HEX_RE.fullmatch(hx) else None
        await cb.answer()
        if not p:
            text, kb = await stk_list_view(uid, lang)
            return await cb.edit(text, kb)
        return await cb.edit(cb.t("stk_del_confirm", title=esc(p["title"]), n=int(p.get("n", 0))),
                             Kb([[Btn(cb.t("b_stk_del_yes"), callback_data=f"stk_delyes_{hx}")],
                                 [Btn(cb.t("b_stk_del_no"), callback_data="stk_list")]]))

    if data.startswith("stk_delyes_"):                                   # step 2: really delete
        hx = data[len("stk_delyes_"):]
        packs = await stk_packs(uid)
        p = packs.get(hx) if _HEX_RE.fullmatch(hx) else None             # only the user's own packs
        if p:
            try:
                await cb.ctx.bot.delete_sticker_set(p["name"])
            except TelegramError as e:
                if not any(w in str(e).lower() for w in ("stickerset_invalid", "invalid", "not found")):
                    await report_error(cb.ctx, e, "stk_delete")
                    return await cb.answer(cb.t("stk_del_fail"), True)    # (already gone in Telegram → just clean up)
            await db_del(f"stkpacks/{uid}/{hx}")
            akey = _active_key(p)
            if (await stk_state(uid)).get(akey) == hx:
                rest = {k: v for k, v in packs.items() if k != hx and _fmt_of(v) == _fmt_of(p)}
                if rest:
                    await db_put(f"stk/{uid}/{akey}", max(rest, key=lambda k: rest[k].get("ts", 0)))
                else:
                    await db_del(f"stk/{uid}/{akey}")
            await cb.answer(cb.t("stk_deleted"))
        else:
            await cb.answer()
        text, kb = await stk_list_view(uid, lang)
        return await cb.edit(text, kb)

    if data == "ask_avatar":
        await cb.answer()
        return await cb.q.message.reply_text(cb.t("ask_avatar_prompt"), reply_markup=ForceReply(selective=True))

    if data == "aedit":                                  # open the 2-button menu under an audio message
        if not cb.q.message.audio:
            return await cb.answer(cb.t("aedit_noaudio"), True)
        await cb.answer()
        try:
            await cb.q.message.edit_reply_markup(reply_markup=aedit_menu_kb(lang))
        except TelegramError:
            pass
        return

    if data == "aedit_x":
        await cb.answer()
        try:
            await cb.q.message.edit_reply_markup(reply_markup=audio_kb(lang))
        except TelegramError:
            pass
        return

    if data in ("aedit_t", "aedit_p"):
        m = cb.q.message
        a = m.audio
        if not a:
            return await cb.answer(cb.t("aedit_noaudio"), True)
        await cb.answer()
        field = "title" if data == "aedit_t" else "performer"
        cur = (a.title if field == "title" else a.performer) or ""
        await session_save(f"aedit_{uid}", {"chat": m.chat_id, "mid": m.message_id, "field": field,
                                            "file_id": a.file_id, "dur": a.duration or 0,
                                            "title": a.title or "", "performer": a.performer or ""})
        try:
            await m.edit_reply_markup(reply_markup=audio_kb(lang))
        except TelegramError:
            pass
        return await m.reply_text(cb.t("ask_aedit_title" if field == "title" else "ask_aedit_perf",
                                       cur=esc(clip(cur, 80))), reply_markup=ForceReply(selective=True))

    if data.startswith("pf_"):                           # profile-hub buttons: pf_<s|v|f>_<username>
        parts = data.split("_", 2)
        if len(parts) == 3 and re.fullmatch(r"[\w.]{1,24}", parts[2]):
            act, user = parts[1], parts[2]
            if act == "f":
                return await send_profile_file(cb, user)
            await cb.answer()
            if act == "s":
                return await process_story(cb.update, cb.ctx, user, lang, time.monotonic())
            if act == "v":
                return await process_latest(cb.update, cb.ctx, user, lang, time.monotonic())
        return

    if data == "latest_more":
        await cb.answer()
        s = await session_get(f"latest_{uid}")
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
        return await process_latest(cb.update, cb.ctx, s.get("user", ""), lang, time.monotonic(), resume=s)

    if data == "ask_disc":
        await cb.answer()
        text, kb = disc_menu_view(lang)
        return await cb.edit(text, kb)

    if data == "disc_kurd":
        await cb.answer()
        text, kb = kurd_menu_view(lang)
        return await cb.edit(text, kb)

    if data.startswith("disc_k_") and data[7:].isdigit() and int(data[7:]) < len(KURD_TOPICS):
        await cb.answer()
        return await process_discover(cb.update, cb.ctx, lang, "kurd", q=data[7:])

    if data == "disc_search":
        await cb.answer()
        return await cb.q.message.reply_text(cb.t("ask_search_prompt"), reply_markup=ForceReply(selective=True))

    if data.startswith("disc_t_") and re.fullmatch(r"[A-Z]{2}", data[7:]):
        await cb.answer()
        return await process_discover(cb.update, cb.ctx, lang, "trend", region=data[7:])

    if data in ("disc_p", ) or data.startswith("dv_"):
        s = await session_get(f"disc_{uid}")
        items = s.get("items") if s else None
        if isinstance(items, dict):
            items = [items[k] for k in sorted(items, key=lambda x: int(x))]
        if data == "disc_p":
            await cb.answer()
            if not s:
                return await cb.q.message.reply_text(cb.t("disc_expired"))
            try:
                await cb.q.message.edit_reply_markup(reply_markup=None)
            except TelegramError:
                pass
            return await process_discover(cb.update, cb.ctx, lang, s.get("kind", "search"), s.get("q", ""),
                                          s.get("region", "US"), int(s.get("cursor") or 0))
        parts = data.split("_")
        try:
            tok, i = parts[1], int(parts[2])
        except (IndexError, ValueError):
            return await cb.answer()
        if not s or not items or s.get("tok") != tok or not (0 <= i < len(items)):
            return await cb.answer(cb.t("disc_expired"), True)
        await cb.answer()
        return await process_link(cb.update, cb.ctx, items[i]["url"], lang, time.monotonic())

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
        text, kb = await vip_view(uid, lang)
        return await cb.edit(text, kb)

    if data.startswith("buy_"):                                          # 💎 pay with Telegram Stars
        tail = data[len("buy_"):]
        return await send_stars_invoice(cb, int(tail) if tail.isdigit() else -1)

    if data == "show_top":                                               # 🏆 best inviters
        text, kb = await lb_view(uid, lang)
        return await cb.edit(text, kb)

    if data == "lb_hide":
        hide = await lb_toggle_hide(uid)
        await cb.answer(cb.t("lb_toast_hide" if hide else "lb_toast_show"))
        text, kb = await lb_view(uid, lang)
        return await cb.edit(text, kb)

    if data == "fw_list":                                                # 🔔 followed accounts
        await cb.answer()
        text, kb = await follow_list_view(uid, lang)
        return await cb.edit(text, kb)

    if data.startswith(("fwx_", "fwu_")):
        user = data[len("fwx_"):]
        if _USER_RE.fullmatch(user):
            await follow_remove(uid, user)
        await cb.answer(cb.t("fw_off"))
        if data.startswith("fwx_"):
            text, kb = await follow_list_view(uid, lang)
            return await cb.edit(text, kb)
        return

    if data.startswith("fw_"):
        return await toggle_follow(cb, data[len("fw_"):])

    if data.startswith("ss_"):                                           # 🎨 sticker shape chosen
        return await choose_shape(cb, data)

    if data == "show_ref":
        text, kb = await ref_view(uid, lang)
        return await cb.edit(text, kb)

    if data.startswith(("my_hist_", "my_fav_")):
        tail = data.rsplit("_", 1)[1]
        text, kb = await list_view(uid, lang, "hist" if data.startswith("my_hist_") else "fav",
                                   int(tail) if tail.isdigit() else 0)
        return await cb.edit(text, kb)

    if data == "hist_clr":
        await db_del(f"hist/{uid}")
        await cb.answer(cb.t("hist_cleared"))
        text, kb = await list_view(uid, lang, "hist", 0)
        return await cb.edit(text, kb)

    if data.startswith("fav_"):
        return await toggle_fav(cb, data[len("fav_"):])

    if data.startswith("rs_"):                                       # send a history / favorite item again
        hit = await cache_get(data[len("rs_"):])
        if not hit or not hit.get("src"):
            return await cb.answer(cb.t("session_expired"), True)
        await cb.answer()
        return await process_link(cb.update, cb.ctx, hit["src"], lang, time.monotonic())

    if data == "show_help":
        return await cb.edit(cb.t("help", dev=esc(DEV)), Kb([back_row(lang)]))

    if data == "show_settings":
        text, kb = await settings_view(uid, lang)
        return await cb.edit(text, kb)

    if data.startswith("set_q_"):
        q = data[len("set_q_"):]
        if q in QUALITIES:
            await db_put(f"users/{uid}/q", q)
            await cb.answer(cb.t("q_saved"))
            text, kb = await settings_view(uid, lang)
            return await cb.edit(text, kb)
        return

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

    if data.startswith(("dl_gif_", "dl_stk_", "dl_cmt_")):
        return await send_extra(cb, data)

    # ── staff areas ──────────────────────────────────────────────────────────
    if is_admin(uid) and data != "noop":
        await set_wait_clear(uid)          # any navigation cancels a pending "type the ID" prompt
    if data == "panel_unified" or data.startswith("adm_"):
        return await route_admin(cb, data) if is_admin(uid) else await cb.answer(cb.t("no_perm"), True)
    if data.startswith(("sup_", "set_bot_lang_")):
        return await route_super(cb, data) if is_super(uid) else await cb.answer(cb.t("no_perm"), True)
    if data.startswith("own_"):
        return await route_owner(cb, data) if is_owner(uid) else await cb.answer(cb.t("no_perm"), True)


# ══════════════════════════════════════════════════════════════════════════════
# 9b · EXTRAS under a result:  GIF · sticker · comments   (+ ffmpeg helpers)
# ══════════════════════════════════════════════════════════════════════════════
_FF_UNSET = object()
_ff_path = _FF_UNSET


def ffmpeg_path() -> str | None:
    """System ffmpeg, or the one bundled by the optional `imageio-ffmpeg` package."""
    global _ff_path
    if _ff_path is _FF_UNSET:
        p = shutil.which("ffmpeg")
        if not p:
            try:
                import imageio_ffmpeg                                   # type: ignore
                p = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:                                           # noqa: BLE001
                p = None
        _ff_path = p
    return _ff_path


async def run_ffmpeg(args: list, data: bytes, out_ext: str, timeout: float = 30.0, extra: list | None = None) -> bytes | None:
    exe = ffmpeg_path()
    if not exe:
        return None
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in.mp4"), os.path.join(d, f"out.{out_ext}")
        with open(src, "wb") as f:
            f.write(data)
        more: list = []
        for n, (pre, blob) in enumerate(extra or []):                    # e.g. a looped PNG mask as input #1
            path = os.path.join(d, f"extra{n}.png")
            with open(path, "wb") as f:
                f.write(blob)
            more += [*pre, "-i", path]
        proc = await asyncio.create_subprocess_exec(
            exe, "-y", "-v", "error", "-i", src, *more, *args, dst,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            log.info("ffmpeg timed out")
            return None
        if proc.returncode != 0 or not os.path.exists(dst):
            log.info("ffmpeg failed: %s", (err or b"")[-300:])
            return None
        with open(dst, "rb") as f:
            return f.read()


async def to_gif_mp4(data: bytes) -> bytes | None:
    """Telegram 'GIF' = silent looping MP4. Trim + shrink it (needs ffmpeg)."""
    out = await run_ffmpeg(
        ["-t", str(GIF_SECONDS), "-an", "-vf", "scale='min(480,iw)':-2,fps=24",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart"], data, "mp4", 35)
    return out if out and len(out) <= TG_MAX_BYTES else None


async def to_sticker_webm(data: bytes, shape: str = "round") -> bytes | None:
    """Telegram video sticker: WEBM/VP9, ≤3 s, one side exactly 512 px, ≤256 KB, no audio (needs ffmpeg)."""
    pre = "crop='min(iw,ih)':'min(iw,ih)'," if shape in ("sq", "circle") else ""     # centre square crop
    alpha = {"round": _round_alpha_expr, "circle": _circle_alpha_expr}.get(shape)
    geq = f",geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='{alpha()}'" if alpha else ""     # square → no mask
    mask = _circle_mask_png() if shape == "circle" else None
    for crf, fps in ((34, 30), (42, 24), (50, 20), (58, 15)):
        scale = f"scale=512:512:force_original_aspect_ratio=decrease,fps={fps}"
        if mask:                                                         # circle: alphamerge with a looped mask image
            graph = ["-filter_complex", f"[0:v]{pre}{scale},format=yuv420p[v];[1:v]format=gray[m];[v][m]alphamerge[out]",
                     "-map", "[out]"]
            extra = [(["-loop", "1"], mask)]
        else:
            graph = ["-vf", pre + scale + ",format=yuva420p" + geq]
            extra = None
        out = await run_ffmpeg(
            ["-t", "2.9", "-an", *graph,
             "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", str(crf),
             "-deadline", "realtime", "-cpu-used", "5", "-row-mt", "1", "-auto-alt-ref", "0"],
            data, "webm", 25, extra)
        if out and len(out) <= STICKER_MAX:
            return out
    return None


_CIRCLE_MASK = None


def _circle_mask_png(size: int = 512) -> bytes | None:
    """512×512 anti-aliased circle (white inside) — fed to ffmpeg's alphamerge. None when Pillow is missing."""
    global _CIRCLE_MASK
    if _CIRCLE_MASK is None:
        try:
            from PIL import Image, ImageDraw                            # type: ignore
            k = 4
            m = Image.new("L", (size * k, size * k), 0)
            ImageDraw.Draw(m).ellipse((0, 0, size * k - 1, size * k - 1), fill=255)
            buf = io.BytesIO()
            m.resize((size, size), Image.LANCZOS).save(buf, "PNG")
            _CIRCLE_MASK = buf.getvalue()
        except Exception as e:                                          # noqa: BLE001
            log.info("circle mask failed: %s", e)
            _CIRCLE_MASK = b""
    return _CIRCLE_MASK or None


def _circle_alpha_expr() -> str:
    """ffmpeg geq expression → alpha 0 outside the inscribed circle (anti-aliased edge)."""
    r = "(min(W,H)/2)"
    return f"clip(255*({r}+0.5-hypot(X+0.5-W/2,Y+0.5-H/2)),0,255)"


def _round_alpha_expr() -> str:
    """ffmpeg geq expression → alpha 0 outside a rounded rectangle (anti-aliased edge)."""
    r = f"{STICKER_RADIUS}*min(W,H)"
    return (f"st(0,abs(X+0.5-W/2)-(W/2-{r}));st(1,abs(Y+0.5-H/2)-(H/2-{r}));"
            f"if(gt(ld(0),0)*gt(ld(1),0),clip(255*({r}+0.5-hypot(ld(0),ld(1))),0,255),255)")


def _static_sticker(img: bytes, shape: str = "round", text: str = "", font_choice: str = "auto") -> bytes | None:
    """Fallback when ffmpeg is missing: the video cover as a static 512 px WEBP sticker (needs Pillow)."""
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageOps          # type: ignore
        src = Image.open(io.BytesIO(img))
        try:
            src.draft("RGB", (1024, 1024))                              # JPEG: decode small → low memory
        except Exception:                                               # noqa: BLE001
            pass
        base = ImageOps.exif_transpose(src).convert("RGBA")
        im = (ImageOps.fit(base, (512, 512), Image.LANCZOS) if shape in ("sq", "circle")
              else ImageOps.contain(base, (512, 512)))
        layer = _caption_layer(im.size, text, shape, font_choice) if text else None
        if layer is not None:                                           # caption text under the rounded mask
            im = Image.alpha_composite(im, layer)
        w, h = im.size
        if shape != "sq":                                               # a plain square keeps its sharp corners
            k = 4                                                       # supersample → smooth edge
            mask = Image.new("L", (w * k, h * k), 0)
            if shape == "circle":
                ImageDraw.Draw(mask).ellipse((0, 0, w * k - 1, h * k - 1), fill=255)
            else:
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * k - 1, h * k - 1),
                                                       radius=int(min(w, h) * STICKER_RADIUS * k), fill=255)
            mask = mask.resize((w, h), Image.LANCZOS)
            im.putalpha(ImageChops.multiply(im.getchannel("A"), mask))
        for q in (90, 75, 60, 45):                                      # sticker limit: 512 KB
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=q, method=4)
            if len(buf.getvalue()) <= 512_000:
                return buf.getvalue()
        return None
    except Exception as e:                                              # noqa: BLE001
        log.info("static sticker failed: %s", e)
        return None


async def fetch_comments(src: str, limit: int = COMMENTS_MAX) -> list | None:
    """Top comments of a video (TikWM). → list (maybe empty) · None on failure."""
    t = min(int(CFG.get("api_timeout", 40)), 20)
    for attempt in range(3):
        try:
            r = await http().post("https://www.tikwm.com/api/comment/list/",
                                  data={"url": src, "count": limit, "cursor": 0}, timeout=t)
            j = r.json()
        except Exception as e:                                          # noqa: BLE001
            log.warning("comments attempt %s failed: %s", attempt + 1, e)
            await asyncio.sleep(0.8)
            continue
        if j.get("code") == 0 and isinstance(j.get("data"), dict):
            out = []
            for c in j["data"].get("comments") or []:
                if not isinstance(c, dict):
                    continue
                text = (c.get("text") or "").strip()
                if not text:
                    continue
                u = c.get("user") if isinstance(c.get("user"), dict) else {}
                out.append({"user": u.get("nickname") or u.get("unique_id") or "—",
                            "handle": u.get("unique_id") or "", "text": text,
                            "likes": _to_int(c.get("digg_count")), "replies": _to_int(c.get("reply_total"))})
            return out
        msg = str(j.get("msg", "")).lower()
        if "limit" in msg or "second" in msg:
            await asyncio.sleep(1.3)
            continue
        log.info("comments rejected: %s", msg)
        return None
    return None


def comments_preview(lang: str, items: list) -> str:
    text = tx(lang, "cmt_title", n=len(items))
    for i, c in enumerate(items[:COMMENTS_SHOW], 1):
        likes = f" · ❤️ {fmt_num(c['likes'])}" if c["likes"] else ""
        block = f"\n\n<b>{i}. {esc(clip(c['user'], 30))}</b>{likes}\n{esc(clip(c['text'], 260))}"
        if len(text) + len(block) > 3700:
            break
        text += block
    return text


def comments_txt(items: list) -> str:
    out = []
    for i, c in enumerate(items, 1):
        who = c["user"] + (f" (@{c['handle']})" if c["handle"] else "")
        out.append(f"#{i}  {who}  ·  ❤ {c['likes']}  ·  ↩ {c['replies']}\n{c['text']}\n")
    return "\n".join(out)


_TT_HOST = re.compile(r"^https?://([\w-]+\.)*tiktok\.com/", re.I)


def _src_from_markup(message) -> str | None:
    """The 'original link' button of the result message IS the TikTok link → no storage needed."""
    try:
        for row in message.reply_markup.inline_keyboard:
            for b in row:
                if b.url and _TT_HOST.match(b.url):
                    return b.url
    except AttributeError:
        pass
    return None


async def _src_for(cb: "CB", key: str) -> str | None:
    src = _src_from_markup(cb.q.message)
    if src:
        return src
    hit = await cache_get(key)
    if hit:
        return hit.get("src")
    s = await session_get(key)
    return s.get("src") if s else None


def _close_kb(lang: str) -> Kb:
    return Kb([[Btn(tx(lang, "b_delete"), callback_data="close")]])


async def _extra_gif(ctx, chat_id: int, lang: str, key: str, src: str) -> None:
    fid = await db_get(f"fc/{key}/fid_gif")
    if isinstance(fid, str) and fid:                                    # sent before → instant
        try:
            await ctx.bot.send_animation(chat_id, fid, caption=bot_tag(), reply_markup=_close_kb(lang), **_UP)
            return
        except TelegramError as e:
            log.info("cached gif failed (%s) → rebuild", e)
    await chat_action(ctx, chat_id, ChatAction.UPLOAD_VIDEO)
    m = await fetch_tiktok(src)
    if not m or not m["videos"]:
        raise RuntimeError("no video for gif")
    data, _ = await fetch_video(m, "sd")                                # smaller file is plenty for a GIF
    if not data:
        raise RuntimeError("gif download failed")
    data = await to_gif_mp4(data) or data                               # silent + trimmed when ffmpeg exists
    sent = await ctx.bot.send_animation(chat_id, InputFile(data, filename=f"{key}.mp4"),
                                        caption=bot_tag(), reply_markup=_close_kb(lang), **_UP)
    await save_fid(key, "fid_gif", sent, "animation")


async def _extra_sticker(ctx, chat_id: int, lang: str, key: str, src: str, uid: int = 0) -> None:
    await chat_action(ctx, chat_id, ChatAction.UPLOAD_VIDEO)
    m = await fetch_tiktok(src)
    if not m:
        raise RuntimeError("sticker: no media")
    if m["videos"] and ffmpeg_path():
        data, _ = await fetch_video(m, "sd")
        webm = await to_sticker_webm(data) if data else None
        if webm:
            if uid:
                return await deliver_sticker(ctx, uid, chat_id, lang, webm, "video")
            await ctx.bot.send_sticker(chat_id, InputFile(webm, filename="sticker.webm"),
                                       reply_markup=_close_kb(lang), **_UP)
            return
    cover = None
    for u in [m.get("cover")] + list(m.get("images") or [])[:1]:         # static fallback: cover / first photo
        if u:
            try:
                cover = await download_bytes(u, max_bytes=20_000_000, timeout=20)
            except TooBig:
                cover = None
            if cover:
                break
    webp = await asyncio.to_thread(_static_sticker, cover[0]) if cover else None
    if not webp:
        raise RuntimeError("sticker needs `imageio-ffmpeg` (animated) or `Pillow` (static) in requirements.txt")
    await ctx.bot.send_sticker(chat_id, InputFile(webp, filename="sticker.webp"),
                               reply_markup=_close_kb(lang), **_UP)
    await ctx.bot.send_message(chat_id, tx(lang, "stk_static"))


async def _extra_comments(ctx, chat_id: int, lang: str, key: str, src: str) -> None:
    await chat_action(ctx, chat_id, ChatAction.TYPING)
    items = await fetch_comments(src)
    if items is None:
        raise RuntimeError("comments failed")
    if not items:
        await ctx.bot.send_message(chat_id, tx(lang, "cmt_none"), reply_markup=_close_kb(lang))
        return
    await ctx.bot.send_message(chat_id, comments_preview(lang, items), reply_markup=_close_kb(lang))
    await ctx.bot.send_document(chat_id, InputFile(comments_txt(items).encode("utf-8"), filename=f"comments_{key}.txt"),
                                caption=tx(lang, "cmt_file", n=len(items)), **_UP)


# ── sticker packs (the "Make a sticker" section) ─────────────────────────────
_HEX_RE = re.compile(r"[0-9a-f]{6}")
PACK_MAX = 120                                  # static packs hold up to 120 stickers
STK_EMOJI = "🤎"


def pack_url(name: str) -> str:
    return f"https://t.me/addstickers/{name}"


async def stk_state(uid: int) -> dict:
    d = await db_get(f"stk/{uid}")
    return d if isinstance(d, dict) else {}


async def stk_packs(uid: int) -> dict:
    d = await db_get(f"stkpacks/{uid}")
    return {k: v for k, v in d.items() if _HEX_RE.fullmatch(k) and isinstance(v, dict) and v.get("name")} \
        if isinstance(d, dict) else {}


def _fmt_of(p: dict) -> str:
    return "video" if p.get("f") == "video" else "static"


def _active_key(fmt_or_pack) -> str:
    """Telegram never mixes photo and video stickers in one pack → each format has its own active pack."""
    fmt = fmt_or_pack if isinstance(fmt_or_pack, str) else _fmt_of(fmt_or_pack)
    return "vactive" if fmt == "video" else "active"


async def stk_menu_view(uid: int, lang: str) -> tuple[str, Kb]:
    st, packs = await stk_state(uid), await stk_packs(uid)
    act, vact = packs.get(st.get("active", "")), packs.get(st.get("vactive", ""))
    rows = []
    if st.get("pending"):
        text = tx(lang, "stk_menu_pending", title=esc(st["pending"]))
    else:
        text = (tx(lang, "stk_menu_pack", title=esc(act["title"]), n=int(act.get("n", 0)))
                if act else tx(lang, "stk_menu_nopack"))
        if vact:
            text += "\n\n" + tx(lang, "stk_menu_vpack", title=esc(vact["title"]), n=int(vact.get("n", 0)))
        text += "\n\n" + tx(lang, "stk_menu_tip")
        for p in (act, vact):
            if p:
                rows.append([Btn(clip(f"{'🎞' if _fmt_of(p) == 'video' else '🖼'} {p['title']}", 30),
                                 url=pack_url(p["name"]))])
    new_row = [Btn(tx(lang, "b_stk_new"), callback_data="stk_new")]
    if packs:
        new_row.append(Btn(tx(lang, "b_stk_list"), callback_data="stk_list"))
    rows += [new_row, back_row(lang)]
    return text, Kb(rows)


async def stk_list_view(uid: int, lang: str) -> tuple[str, Kb]:
    st, packs = await stk_state(uid), await stk_packs(uid)
    if not packs:
        return await stk_menu_view(uid, lang)
    rows = []
    for hx, p in sorted(packs.items(), key=lambda kv: kv[1].get("ts", 0), reverse=True)[:8]:
        mark = "✅" if st.get(_active_key(p)) == hx else "⚪"
        icon = "🎞" if _fmt_of(p) == "video" else "🖼"
        rows.append([Btn(clip(f"{mark}{icon} {p.get('title', '')} ({int(p.get('n', 0))})", 28), callback_data=f"stk_use_{hx}"),
                     Btn("🔗", url=pack_url(p["name"])),
                     Btn("🗑", callback_data=f"stk_del_{hx}")])
    rows += [[Btn(tx(lang, "b_stk_new"), callback_data="stk_new")], back_row(lang, "ask_sticker")]
    return tx(lang, "stk_list_title"), Kb(rows)


def _input_sticker(data: bytes, fmt: str = "static"):
    """InputSticker across PTB versions (Bot API ≥ 7.2 wants the `format`)."""
    from telegram import InputSticker                                   # type: ignore
    # A *named file-like object*: PTB attaches it to the request. (A ready-made InputFile is passed through
    # un-attached → Telegram answers "field sticker must be of type string".)
    f = io.BytesIO(data)
    f.name = "sticker.webm" if fmt == "video" else "sticker.webp"
    try:
        return InputSticker(sticker=f, emoji_list=[STK_EMOJI], format=fmt)
    except TypeError:
        return InputSticker(sticker=f, emoji_list=[STK_EMOJI])


async def _pack_create(ctx, uid: int, name: str, title: str, data: bytes, fmt: str = "static") -> None:
    try:
        await ctx.bot.create_new_sticker_set(user_id=uid, name=name, title=title,
                                             stickers=[_input_sticker(data, fmt)])
    except TypeError:                                                   # older PTB: separate sticker_format
        await ctx.bot.create_new_sticker_set(user_id=uid, name=name, title=title,
                                             stickers=[_input_sticker(data, fmt)], sticker_format=fmt)


async def _pack_add(ctx, uid: int, name: str, data: bytes, fmt: str = "static") -> None:
    await ctx.bot.add_sticker_to_set(user_id=uid, name=name, sticker=_input_sticker(data, fmt))


def _pack_kb(lang: str, name: str | None, extra: list | None = None) -> Kb:
    rows = []
    if name:
        rows.append([Btn(tx(lang, "b_stk_open"), url=pack_url(name))])
    rows += (extra or []) + [[Btn(tx(lang, "b_delete"), callback_data="close")]]
    return Kb(rows)


async def deliver_sticker(ctx, uid: int, chat_id: int, lang: str, data: bytes, fmt: str = "static") -> None:
    """Send the sticker (photo → WEBP "static", video → WEBM "video") and put it into the user's pack of that
    format — creating the pack with the first sticker when the user has just named a new one."""
    ext, akey = ("webm" if fmt == "video" else "webp"), _active_key(fmt)
    st, packs = await stk_state(uid), await stk_packs(uid)
    new_btn = [[Btn(tx(lang, "b_stk_new"), callback_data="stk_new")]]
    f = lambda: InputFile(data, filename=f"sticker.{ext}")              # noqa: E731 — fresh upload object per send

    if st.get("pending"):                                               # first sticker → create the pack
        hx = secrets.token_hex(3)
        name, title = f"s{uid}_{hx}_by_{BOT_USERNAME}", st["pending"]
        await _pack_create(ctx, uid, name, title, data, fmt)
        await db_put(f"stkpacks/{uid}/{hx}", {"name": name, "title": title, "n": 1, "ts": int(time.time()), "f": fmt})
        await db_put(f"stk/{uid}/{akey}", hx)
        await db_del(f"stk/{uid}/pending")
        await ctx.bot.send_sticker(chat_id, f(), reply_markup=_pack_kb(lang, name), **_UP)
        await ctx.bot.send_message(chat_id, tx(lang, "stk_created", title=esc(title)),
                                   reply_markup=Kb([[Btn(tx(lang, "b_stk_open"), url=pack_url(name))]]))
        return

    hx = st.get(akey, "")
    act = packs.get(hx)
    if act and _fmt_of(act) == fmt:
        if int(act.get("n", 0)) >= PACK_MAX:
            return await ctx.bot.send_message(chat_id, tx(lang, "stk_full"), reply_markup=Kb(new_btn))
        try:
            await _pack_add(ctx, uid, act["name"], data, fmt)
        except BadRequest as e:
            msg = str(e).lower()
            if "too_much" in msg or "too much" in msg:
                await db_put(f"stkpacks/{uid}/{hx}/n", PACK_MAX)
                return await ctx.bot.send_message(chat_id, tx(lang, "stk_full"), reply_markup=Kb(new_btn))
            if "stickerset_invalid" in msg or "invalid" in msg or "not found" in msg:   # deleted inside Telegram
                await db_del(f"stkpacks/{uid}/{hx}")
                await db_del(f"stk/{uid}/{akey}")
                return await ctx.bot.send_message(chat_id, tx(lang, "stk_gone"), reply_markup=Kb(new_btn))
            raise
        await db_incr(f"stkpacks/{uid}/{hx}/n")
        return await ctx.bot.send_sticker(chat_id, f(), reply_markup=_pack_kb(lang, act["name"]), **_UP)

    await ctx.bot.send_sticker(chat_id, f(), reply_markup=_pack_kb(lang, None, new_btn), **_UP)   # single sticker, no pack


def _video_file(msg) -> tuple[str, int, int] | None:
    """(file_id, size, seconds) of a gallery video / GIF / round video / video sent as a file."""
    for attr in ("video", "animation", "video_note"):
        o = getattr(msg, attr, None)
        if o:
            d = getattr(o, "duration", 0) or 0
            return o.file_id, o.file_size or 0, int(d.total_seconds()) if hasattr(d, "total_seconds") else int(d)
    d = getattr(msg, "document", None)
    if d and (getattr(d, "mime_type", None) or "").lower().startswith("video/"):
        return d.file_id, d.file_size or 0, 0
    return None


def _is_stk_title_reply(msg) -> bool:
    """True when the user is answering the 'send a name for your pack' prompt."""
    r = getattr(msg, "reply_to_message", None)
    if not r or not r.from_user or not r.from_user.is_bot or not r.text:
        return False
    heads = {plain(tx(l, "stk_ask_title")).split("\n")[0] for l in L}
    return r.text.split("\n")[0].strip() in heads


# ══════════════════════════════════════════════════════════════════════════════
# 9d · LEADERBOARD · STARS (paid VIP) · FOLLOW ACCOUNTS · STICKER OPTIONS (crop + caption text)
# ══════════════════════════════════════════════════════════════════════════════
MEDALS = ("🥇", "🥈", "🥉")
FOLLOW_MAX, FOLLOW_MAX_VIP = 5, 20
_USER_RE = re.compile(r"[A-Za-z0-9_.]{1,24}")


# ── 🏆 leaderboard of the best inviters ──────────────────────────────────────
async def lb_view(uid: int, lang: str) -> tuple[str, Kb]:
    d = await db_get("lb")
    ranked = sorted(((int(k), v) for k, v in d.items() if str(k).isdigit() and isinstance(v, dict)),
                    key=lambda kv: -int(kv[1].get("n", 0))) if isinstance(d, dict) else []
    lines = []
    for i, (u, v) in enumerate(ranked[:10], 1):
        name = tx(lang, "lb_hidden") if v.get("h") else esc(clip(v.get("name") or "—", 20))
        lines.append(f"{MEDALS[i - 1] if i <= 3 else f'{i}.'} {name} — <b>{int(v.get('n', 0))}</b>{' ⬅️' if u == uid else ''}")
    text = tx(lang, "lb_title") + "\n\n" + ("\n".join(lines) if lines else tx(lang, "lb_empty"))
    mine = next(((i, v) for i, (u, v) in enumerate(ranked, 1) if u == uid), None)
    if mine and mine[0] > 10:
        text += "\n\n" + tx(lang, "lb_you", rank=mine[0], n=int(mine[1].get("n", 0)))
    hidden = bool(await db_get(f"users/{uid}/hide_lb"))
    return text, Kb([[Btn(tx(lang, "b_ref"), callback_data="show_ref")],
                     [Btn(tx(lang, "b_lb_show" if hidden else "b_lb_hide"), callback_data="lb_hide")],
                     back_row(lang)])


async def lb_toggle_hide(uid: int) -> bool:
    hide = not bool(await db_get(f"users/{uid}/hide_lb"))
    await db_put(f"users/{uid}/hide_lb", 1 if hide else 0)
    if await db_get(f"lb/{uid}") is not None:
        await db_put(f"lb/{uid}/h", 1 if hide else 0)
    return hide


# ── 💎 paid VIP with Telegram Stars (currency "XTR") ─────────────────────────
def stars_plans() -> list:
    """[(days, stars), …] from the admin config (validated)."""
    raw = CFG.get("stars_plans")
    out = []
    for p in (raw.values() if isinstance(raw, dict) else raw) or []:
        if isinstance(p, dict):
            p = [p.get("0"), p.get("1")]
        try:
            days, price = int(p[0]), int(p[1])
        except (TypeError, ValueError, IndexError):
            continue
        if days >= 1 and 1 <= price <= 2500:
            out.append((days, price))
    return out[:4] or [(7, 50), (30, 150), (90, 400)]


async def vip_view(uid: int, lang: str) -> tuple[str, Kb]:
    text = tx(lang, "vip_info", dev=esc(DEV))
    until = vip_until.get(uid, 0)
    if until > time.time():
        text += "\n\n" + tx(lang, "ref_vip_until", until=fmt_ts(until))
    rows = []
    if CFG.get("stars_on", False):
        text += "\n\n" + tx(lang, "stars_info")
        rows += [[Btn(tx(lang, "b_buy", days=d, stars=s), callback_data=f"buy_{i}")] for i, (d, s) in enumerate(stars_plans())]
    rows.append(back_row(lang))
    return text, Kb(rows)


async def send_stars_invoice(cb: "CB", idx: int) -> None:
    plans = stars_plans()
    if not CFG.get("stars_on", False) or not 0 <= idx < len(plans):
        return await cb.answer(cb.t("stars_off"), True)
    days, stars = plans[idx]
    await cb.answer()
    title = cb.t("inv_title", days=days)
    await cb.ctx.bot.send_invoice(chat_id=cb.q.message.chat_id, title=title,
                                  description=cb.t("inv_desc", days=days), payload=f"vip_{days}_{stars}",
                                  provider_token="", currency="XTR",                       # Stars: no provider token
                                  prices=[LabeledPrice(label=title, amount=stars)])


async def on_pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Telegram asks 'may I charge?' — answer within 10 s, no database work."""
    q = update.pre_checkout_query
    ok = False
    try:
        kind, days, stars = q.invoice_payload.split("_")
        ok = (kind == "vip" and bool(CFG.get("stars_on", False)) and q.currency == "XTR"
              and (int(days), int(stars)) in stars_plans() and int(q.total_amount) == int(stars))
    except (ValueError, AttributeError):
        ok = False
    lang = CFG.get("default_lang", "ku")
    await q.answer(ok=ok, error_message=None if ok else tx(lang if lang in L else "ku", "stars_changed"))


async def on_paid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Stars arrived → VIP days on top of whatever the user still has. Idempotent per charge id."""
    msg, uid = update.effective_message, update.effective_user.id
    sp = msg.successful_payment
    charge = str(sp.telegram_payment_charge_id)
    ck = hashlib.md5(charge.encode()).hexdigest()[:20]
    if await db_get(f"pay/{ck}") is not None:
        return
    try:
        days = int(sp.invoice_payload.split("_")[1])
    except (ValueError, IndexError):
        days = 0
    stars = int(sp.total_amount)
    await db_put(f"pay/{ck}", {"c": charge, "u": uid, "d": days, "s": stars, "ts": int(time.time())})   # record first
    until = await grant_temp_vip(uid, days) if days > 0 else 0
    await db_incr("sys/cfg/stars_total", stars)
    await db_incr(f"users/{uid}/stars", stars)
    lang = user_lang(await db_get(f"users/{uid}"))
    await msg.reply_text(tx(lang, "stars_thanks", days=days, until=fmt_ts(until) if until else "—"))
    try:
        await ctx.bot.send_message(OWNER_ID, f"💰 <b>+{stars} ⭐</b> · VIP {days}d\nuser: <code>{uid}</code>\n"
                                             f"charge: <code>{esc(charge)}</code>")
    except TelegramError:
        pass


async def cmd_refund(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/refund <charge_id> — owner only. Needs python-telegram-bot ≥ 21.4 (refund_star_payment)."""
    uid = update.effective_user.id
    if not is_super(uid):
        return
    args = getattr(ctx, "args", None) or []
    if len(args) != 1:
        return await update.effective_message.reply_text("Usage: <code>/refund CHARGE_ID</code>")
    rec = await db_get(f"pay/{hashlib.md5(args[0].encode()).hexdigest()[:20]}")
    if not isinstance(rec, dict):
        return await update.effective_message.reply_text("❌ Payment not found.")
    if not hasattr(ctx.bot, "refund_star_payment"):
        return await update.effective_message.reply_text("⚠️ Refunds need <code>python-telegram-bot&gt;=21.4</code> in requirements.txt.")
    await ctx.bot.refund_star_payment(user_id=int(rec["u"]), telegram_payment_charge_id=rec["c"])
    u = int(rec["u"])
    left = max(int(time.time()), vip_until.get(u, 0) - int(rec.get("d", 0)) * 86400)       # take the VIP days back
    vip_until[u] = left
    await db_put(f"sys/vip_until/{u}", left)
    await db_del(f"pay/{hashlib.md5(args[0].encode()).hexdigest()[:20]}")
    await db_incr("sys/cfg/stars_total", -int(rec.get("s", 0)))
    await update.effective_message.reply_text(f"✅ Refunded {int(rec.get('s', 0))} ⭐ to <code>{u}</code>.")


async def stars_admin_view(cb: "CB") -> None:
    plans, on = stars_plans(), CFG.get("stars_on", False)
    total = int(await db_get("sys/cfg/stars_total", 0) or 0)
    rows = [[Btn(cb.t("b_stars_toggle", status=status_word(cb.lang, on)), callback_data="sup_stars_t")]]
    for i, (days, price) in enumerate(plans):
        rows.append([Btn("-50", callback_data=f"sup_stars_p{i}-50"), Btn("-10", callback_data=f"sup_stars_p{i}-10"),
                     Btn(f"{days}d · {price}⭐", callback_data="noop"),
                     Btn("+10", callback_data=f"sup_stars_p{i}+10"), Btn("+50", callback_data=f"sup_stars_p{i}+50")])
    rows.append(back_row(cb.lang, "panel_unified"))
    await cb.edit(cb.t("sup_stars_title", status=status_word(cb.lang, on), total=total), Kb(rows))


async def route_stars_admin(cb: "CB", data: str) -> None:
    if data == "sup_stars_t":
        await set_cfg(stars_on=not CFG.get("stars_on", False))
    elif data.startswith("sup_stars_p"):
        rest = data[len("sup_stars_p"):]
        try:
            i, delta = int(rest[0]), int(rest[1:])
        except (ValueError, IndexError):
            return await cb.answer()
        plans = stars_plans()
        if 0 <= i < len(plans):
            plans[i] = (plans[i][0], max(1, min(2500, plans[i][1] + delta)))
            await set_cfg(stars_plans=[[d, s] for d, s in plans])
    await cb.answer()
    await stars_admin_view(cb)


# ── 🔔 follow TikTok accounts → a notice when they post ──────────────────────
def _ukey(user: str) -> str:
    return user.lower().replace(".", "~")                      # Firebase keys cannot contain "."


async def is_following(uid: int, user: str) -> bool:
    return await db_get(f"follow/{uid}/{_ukey(user)}") is not None


async def follow_add(uid: int, user: str) -> str:
    """→ "ok" | "exists" | "limit" """
    mine = await db_get(f"follow/{uid}")
    mine = mine if isinstance(mine, dict) else {}
    uk = _ukey(user)
    if uk in mine:
        return "exists"
    if len(mine) >= (FOLLOW_MAX_VIP if is_vip(uid) else FOLLOW_MAX):
        return "limit"
    await db_put(f"follow/{uid}/{uk}", int(time.time()))
    await db_put(f"fsub/{uk}/{uid}", 1)
    if await db_get(f"fmeta/{uk}") is None:                       # baseline NOW → only later videos are announced
        items = await fetch_latest(user, 1)
        last = max((int(m["key"]) for m in items or [] if str(m["key"]).isdigit()), default=0)
        await db_put(f"fmeta/{uk}", {"last": last, "chk": int(time.time()), "u": user})
    return "ok"


async def follow_remove(uid: int, user: str) -> None:
    uk = _ukey(user)
    await db_del(f"follow/{uid}/{uk}")
    await db_del(f"fsub/{uk}/{uid}")
    if not await db_get(f"fsub/{uk}"):
        await db_del(f"fmeta/{uk}")


async def drop_user_follows(uid: int) -> None:
    """The user blocked the bot → stop watching for them."""
    mine = await db_get(f"follow/{uid}")
    for uk in (mine if isinstance(mine, dict) else {}):
        await db_del(f"fsub/{uk}/{uid}")
        if not await db_get(f"fsub/{uk}"):
            await db_del(f"fmeta/{uk}")
    await db_del(f"follow/{uid}")


async def follow_list_view(uid: int, lang: str) -> tuple[str, Kb]:
    mine = await db_get(f"follow/{uid}")
    if not isinstance(mine, dict) or not mine:
        return tx(lang, "fw_empty"), Kb([back_row(lang)])
    rows = []
    for uk, ts in sorted(mine.items(), key=lambda kv: -int(kv[1] or 0)):
        user = uk.replace("~", ".")
        rows.append([Btn(clip(f"@{user}", 28), callback_data=f"pf_v_{user}"), Btn("🔕", callback_data=f"fwx_{user}")])
    rows.append(back_row(lang))
    return tx(lang, "fw_list_title", n=len(mine), max=FOLLOW_MAX_VIP if is_vip(uid) else FOLLOW_MAX), Kb(rows)


async def _relabel_button(cb: "CB", callback_data: str, text: str) -> None:
    try:
        old = cb.q.message.reply_markup.inline_keyboard
    except AttributeError:
        return
    rows = [[Btn(text, callback_data=b.callback_data) if b.callback_data == callback_data
             else (Btn(b.text, callback_data=b.callback_data) if b.callback_data else Btn(b.text, url=b.url))
             for b in row] for row in old]
    try:
        await cb.q.message.edit_reply_markup(reply_markup=Kb(rows))
    except TelegramError:
        pass


async def toggle_follow(cb: "CB", user: str) -> None:
    if not _USER_RE.fullmatch(user):
        return await cb.answer()
    if await is_following(cb.uid, user):
        await follow_remove(cb.uid, user)
        await cb.answer(cb.t("fw_off"))
        return await _relabel_button(cb, f"fw_{user}", cb.t("fw_b_off"))
    res = await follow_add(cb.uid, user)
    if res == "limit":
        return await cb.answer(cb.t("fw_limit", n=FOLLOW_MAX, vip=FOLLOW_MAX_VIP), True)
    await cb.answer(cb.t("fw_on"))
    await _relabel_button(cb, f"fw_{user}", cb.t("fw_b_on"))


async def notify_follow(ctx, uid: int, lang: str, user: str, m: dict) -> bool:
    """One 'new video' notice. False when the user blocked the bot."""
    text = tx(lang, "fw_new", user=esc(user), title=esc(clip(m.get("title") or "", 150)))
    kb = Kb([[Btn(tx(lang, "fw_b_dl"), callback_data=f"rs_{m['key']}"), Btn(tx(lang, "pf_b_open"), url=m["src"])],
             [Btn(tx(lang, "fw_b_stop"), callback_data=f"fwu_{user}")]])
    try:
        if m.get("cover"):
            try:
                await ctx.bot.send_photo(uid, m["cover"], caption=text, reply_markup=kb)
                return True
            except Forbidden:
                raise
            except TelegramError:                                  # cover link refused → plain message
                pass
        await ctx.bot.send_message(uid, text, reply_markup=kb)
        return True
    except Forbidden:
        return False
    except TelegramError as e:
        log.info("follow notice failed for %s: %s", uid, e)
        return True


async def run_follow_checks(ctx, budget: float = 40.0) -> dict:
    """Called by the cron endpoint: look at the accounts that were checked longest ago, announce new videos."""
    t0 = time.monotonic()
    stats = {"accounts": 0, "new_videos": 0, "notices": 0}
    meta = await db_get("fmeta")
    if not isinstance(meta, dict):
        return stats
    langs: dict = {}
    for uk, mt in sorted(meta.items(), key=lambda kv: int((kv[1] or {}).get("chk", 0) or 0)):
        if time.monotonic() - t0 > budget - 8:
            break
        subs = await db_get(f"fsub/{uk}")
        if not isinstance(subs, dict) or not subs:
            await db_del(f"fmeta/{uk}")
            continue
        user = (mt or {}).get("u") or uk.replace("~", ".")
        items = await fetch_latest(user, 5)
        await db_put(f"fmeta/{uk}/chk", int(time.time()))
        await asyncio.sleep(1.1)                                   # TikWM: about one request per second
        stats["accounts"] += 1
        ids = {int(m["key"]): m for m in items or [] if str(m["key"]).isdigit()}
        if not ids:
            continue
        last = int((mt or {}).get("last", 0) or 0)
        newest = max(ids)
        if last == 0:                                              # first look → remember, announce nothing
            await db_put(f"fmeta/{uk}/last", newest)
            continue
        fresh = [ids[i] for i in sorted(ids) if i > last][-3:]     # oldest first, at most 3 per account per run
        if not fresh:
            continue
        await db_put(f"fmeta/{uk}/last", newest)
        for m in fresh:
            await remember_media(m, m["src"])                      # so the ⬇️ button can find the link later
            stats["new_videos"] += 1
            for s in list(subs):
                s = int(s)
                if s not in langs:
                    langs[s] = user_lang(await db_get(f"users/{s}"))
                if await notify_follow(ctx, s, langs[s], user, m):
                    stats["notices"] += 1
                else:
                    await drop_user_follows(s)
                    subs.pop(str(s), None)
                await asyncio.sleep(0.05)
    return stats


# ── ✂️ sticker options: square crop + caption text ───────────────────────────
_FONT_RAW = None
_TXT_ENGINE = None
_RTL_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


def text_engine() -> str:
    """How Kurdish/Arabic text can be drawn here: 'raqm' (Pillow + libraqm) · 'reshape' (arabic-reshaper + python-bidi) · 'plain'."""
    global _TXT_ENGINE
    if _TXT_ENGINE is None:
        _TXT_ENGINE = "plain"
        try:
            from PIL import features                               # type: ignore
            if features.check("raqm"):
                _TXT_ENGINE = "raqm"
        except Exception:                                          # noqa: BLE001
            pass
        if _TXT_ENGINE == "plain":
            try:
                import arabic_reshaper                             # type: ignore  # noqa: F401
                import bidi                                        # type: ignore  # noqa: F401
                _TXT_ENGINE = "reshape"
            except Exception:                                      # noqa: BLE001
                pass
    return _TXT_ENGINE


_CUSTOM_FONTS: dict = {}                                           # "kurdish" / "english" → (bytes | None, path | None)


def _custom_font(kind: str) -> tuple:
    """kurdish.ttf / english.ttf uploaded next to this file (or in /fonts, the repo root, …). Name case is ignored."""
    if kind not in _CUSTOM_FONTS:
        here, found = os.path.dirname(os.path.abspath(__file__)), (None, None)
        dirs = [here, os.path.join(here, "fonts"), os.path.dirname(here), os.path.join(os.path.dirname(here), "fonts"),
                os.getcwd(), os.path.join(os.getcwd(), "fonts"), os.path.join(os.getcwd(), "api"),
                "/var/task", "/var/task/api", "/var/task/fonts"]
        for d in dirs:
            try:
                for fn in os.listdir(d):
                    if fn.lower() in (f"{kind}.ttf", f"{kind}.otf"):
                        path = os.path.join(d, fn)
                        with open(path, "rb") as f:
                            found = (f.read(), path)
                        break
            except OSError:
                continue
            if found[0]:
                break
        _CUSTOM_FONTS[kind] = found
    return _CUSTOM_FONTS[kind]


def fonts_status() -> str:
    parts = []
    for kind in ("kurdish", "english"):
        data, path = _custom_font(kind)
        parts.append(f"{kind} ✓ {os.path.basename(path)}" if data else f"{kind} ✗ (built-in)")
    return " · ".join(parts)


def _builtin_font() -> bytes:
    global _FONT_RAW
    if _FONT_RAW is None:
        _FONT_RAW = zlib.decompress(base64.b64decode(_FONT_Z))
    return _FONT_RAW


def _covers(raw: bytes, text: str) -> bool:
    """Does this font really have a glyph for every character? (a missing glyph draws a box or nothing)"""
    from PIL import Image, ImageDraw, ImageFont                    # type: ignore
    f = ImageFont.truetype(io.BytesIO(raw), 48, layout_engine=ImageFont.Layout.BASIC)

    def draw(ch: str):
        im = Image.new("L", (110, 110), 0)
        ImageDraw.Draw(im).text((20, 10), ch, font=f, fill=255)
        return im.getbbox(), im.tobytes()

    notdef = draw("\uffff")[1]
    for c in set(text):
        if c.isspace() or c in "\u200c\u200d\u200e\u200f":
            continue
        box, data = draw(c)
        if box is None or data == notdef:
            return False
    return True


def _font_kind(rtl: bool, choice: str = "auto") -> str:
    """choice: "auto" (by script) · "ku" (always kurdish.ttf) · "en" (always english.ttf)"""
    return {"ku": "kurdish", "en": "english"}.get(choice) or ("kurdish" if rtl else "english")


def font_fallback(text: str, choice: str = "auto") -> bool:
    """True when the user's font for this choice exists but cannot draw every letter (the built-in font is used instead)."""
    text = " ".join(text.split())[:80]
    raw = _custom_font(_font_kind(bool(_RTL_RE.search(text)), choice))[0]
    if not raw or not text:
        return False
    try:
        return not _covers(raw, _shape(text, text_engine())[0])
    except Exception:                                              # noqa: BLE001
        return True


def _font_source(text: str, engine: str, rtl: bool, choice: str = "auto") -> bytes:
    """The user's font for this caption when it covers every letter, else the built-in one."""
    raw = _custom_font(_font_kind(rtl, choice))[0]
    if raw:
        try:
            if _covers(raw, _shape(text, engine)[0]):
                return raw
            log.info("custom %s font lacks glyphs for this caption → built-in font", _font_kind(rtl, choice))
        except Exception as e:                                      # noqa: BLE001 — a broken font file must not break stickers
            log.info("custom font unusable: %s", e)
    return _builtin_font()


def _font(size: int, engine: str, raw: bytes | None = None):
    from PIL import ImageFont                                      # type: ignore
    layout = ImageFont.Layout.RAQM if engine == "raqm" else ImageFont.Layout.BASIC
    return ImageFont.truetype(io.BytesIO(raw or _builtin_font()), size, layout_engine=layout)


def _shape(line: str, engine: str) -> tuple:
    rtl = bool(_RTL_RE.search(line))
    if engine == "raqm":
        return line, ({"direction": "rtl", "language": "ckb"} if rtl else {})
    if engine == "reshape" and rtl:
        import arabic_reshaper                                     # type: ignore
        try:
            from bidi.algorithm import get_display                 # type: ignore
        except ImportError:
            from bidi import get_display                           # type: ignore
        return get_display(arabic_reshaper.reshape(line)), {}
    return line, {}


def text_supported(text: str) -> bool:
    return not (text and _RTL_RE.search(text) and text_engine() == "plain")


def _caption_layer(size: tuple, text: str, shape: str = "round", font_choice: str = "auto"):
    """Transparent RGBA layer with the caption at the bottom: white text, black outline, ≤ 3 lines."""
    from PIL import Image, ImageDraw                               # type: ignore
    text = " ".join(text.split())[:80]
    if not text or not text_supported(text):
        return None
    engine = text_engine()
    w, h = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lines: list = []
    raw = _font_source(text, engine, bool(_RTL_RE.search(text)), font_choice)
    for fs in range(max(28, w // 7), 23, -4):
        font, sw = _font(fs, engine, raw), max(2, fs // 12)
        maxw = int(w * 0.66) if shape == "circle" else w - 2 * (sw + 14)     # a circle is narrow near the bottom
        lines, cur = [], ""
        for word in text.split():
            trial = (cur + " " + word).strip()
            s, kw = _shape(trial, engine)
            if cur and d.textlength(s, font=font, **kw) > maxw:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        if cur:
            lines.append(cur)
        widest = max(d.textlength(_shape(l, engine)[0], font=font, **_shape(l, engine)[1]) for l in lines)
        if len(lines) <= 3 and widest <= maxw:
            break
    lh = int(fs * 1.3)
    y = h - (int(h * 0.17) if shape == "circle" else 18) - lh * len(lines)
    for i, line in enumerate(lines):
        s, kw = _shape(line, engine)
        d.text((w / 2, y + i * lh), s, font=font, fill=(255, 255, 255, 255), stroke_width=sw,
               stroke_fill=(0, 0, 0, 255), anchor="ma", **kw)
    return layer



def _photo_file(msg) -> tuple[str, int] | None:
    """(file_id, size) of a gallery photo, or of an image sent as a file; None otherwise."""
    if getattr(msg, "photo", None):
        ph = msg.photo[-1]
        return ph.file_id, ph.file_size or 0
    d = getattr(msg, "document", None)
    mime = (getattr(d, "mime_type", None) or "").lower()
    if d and mime.startswith("image/") and mime != "image/gif":
        return d.file_id, d.file_size or 0
    return None


# ── 🎨 sticker shape: ask first (rounded · square · circle), then build ──────
SHAPES = ("round", "sq", "circle")


def _shape_kb(lang: str, mid: int, with_font: bool, ft: str) -> Kb:
    rows = [[Btn(tx(lang, "b_shape_round"), callback_data=f"ss_round_{mid}"),
             Btn(tx(lang, "b_shape_sq"), callback_data=f"ss_sq_{mid}"),
             Btn(tx(lang, "b_shape_circle"), callback_data=f"ss_circle_{mid}")]]
    if with_font:                                                      # which font draws the caption?
        rows.append([Btn(("✅ " if ft == code else "") + tx(lang, key), callback_data=f"ss_f{code}_{mid}")
                     for code, key in (("auto", "b_font_auto"), ("ku", "b_font_ku"), ("en", "b_font_en"))])
    rows.append([Btn(tx(lang, "b_shape_cancel"), callback_data=f"ss_x_{mid}")])
    return Kb(rows)


async def ask_sticker_shape(update: Update, ctx, lang: str, kind: str) -> None:
    """A photo / video arrived → remember it and ask which shape the sticker should have."""
    msg, uid = update.effective_message, update.effective_user.id
    if not await gate_message(update, ctx, uid, lang):
        return
    seconds = 0
    if kind == "video":
        fid, size, seconds = _video_file(msg)
        if not ffmpeg_path():
            return await msg.reply_text(tx(lang, "vstk_noffmpeg"))
    else:
        fid, size = _photo_file(msg)
    if size > 20_000_000:                                              # bots can download up to 20 MB
        return await msg.reply_text(tx(lang, "mkstk_big"))
    mid = int(getattr(msg, "message_id", 0) or 0)
    old = await db_get(f"stkq/{uid}")                                  # forget questions nobody answered for an hour
    if isinstance(old, dict):
        for k, v in list(old.items()):
            if not isinstance(v, dict) or int(v.get("ts", 0)) < int(time.time()) - 3600:
                await db_del(f"stkq/{uid}/{k}")
    caption = clip((getattr(msg, "caption", None) or "").strip(), 80)
    await db_put(f"stkq/{uid}/{mid}", {"k": kind, "f": fid, "s": seconds, "ts": int(time.time()), "c": caption, "ft": "auto"})
    text = tx(lang, "ss_ask") + (("\n\n" + tx(lang, "ss_font_hint")) if caption and kind == "photo" else "")
    await msg.reply_text(text, reply_markup=_shape_kb(lang, mid, bool(caption) and kind == "photo", "auto"))


async def process_photo_sticker(update: Update, ctx, lang: str) -> None:
    await ask_sticker_shape(update, ctx, lang, "photo")


async def process_video_sticker(update: Update, ctx, lang: str) -> None:
    await ask_sticker_shape(update, ctx, lang, "video")


async def _build_sticker(ctx, uid: int, chat_id: int, lang: str, rec: dict, shape: str) -> str | None:
    """Download the user's media, render it in the chosen shape, deliver it. → None, or the key of an error text."""
    video = rec.get("k") == "video"
    await chat_action(ctx, chat_id, ChatAction.UPLOAD_VIDEO if video else ChatAction.UPLOAD_PHOTO)
    if not video and not importlib.util.find_spec("PIL"):
        raise RuntimeError("Pillow is missing — add `Pillow` to requirements.txt")
    tg_file = await ctx.bot.get_file(rec["f"])
    raw = bytes(await tg_file.download_as_bytearray())
    caption = (rec.get("c") or "").strip()
    if video:
        webm = await to_sticker_webm(raw, shape)
        if not webm:
            return "stk_fail"
        await deliver_sticker(ctx, uid, chat_id, lang, webm, "video")
        if int(rec.get("s", 0)) > 3:
            await ctx.bot.send_message(chat_id, tx(lang, "vstk_trim"))
        if caption:
            await ctx.bot.send_message(chat_id, tx(lang, "vstk_notext"))
        return None
    font_choice = rec.get("ft") if rec.get("ft") in ("auto", "ku", "en") else "auto"
    webp = await asyncio.to_thread(_static_sticker, raw, shape, caption, font_choice)
    if not webp:
        return "mkstk_fail"
    await deliver_sticker(ctx, uid, chat_id, lang, webp)
    if caption and not text_supported(caption):
        await ctx.bot.send_message(chat_id, tx(lang, "stk_text_unsupported"))
    elif caption and font_fallback(caption, font_choice):               # their font lacks some letters → say so
        await ctx.bot.send_message(chat_id, tx(lang, "stk_font_missing"))
    return None


async def choose_shape(cb: "CB", data: str) -> None:
    """ss_<round|sq|circle|x>_<message id> — the user answered the shape question."""
    parts = data.split("_", 2)
    if len(parts) != 3 or parts[1] not in SHAPES + ("x", "fauto", "fku", "fen") or not parts[2].isdigit():
        return await cb.answer()
    shape, mid, uid, lang = parts[1], parts[2], cb.uid, cb.lang
    path, msg = f"stkq/{uid}/{mid}", cb.q.message
    if shape.startswith("f"):                                          # 🔤 font row: remember the choice, mark it ✅
        if not isinstance(await db_get(path), dict):
            return await cb.answer(cb.t("ss_expired"), True)
        ft = shape[1:]
        await db_put(f"{path}/ft", ft)
        await cb.answer()
        try:
            await msg.edit_reply_markup(reply_markup=_shape_kb(lang, int(mid), True, ft))
        except TelegramError:                                          # same choice tapped again → nothing changes
            pass
        return
    if shape == "x":                                                   # cancelled
        await db_del(path)
        await cb.answer()
        try:
            await msg.delete()
        except TelegramError:
            pass
        return
    rec = await db_get(path)
    if not isinstance(rec, dict):
        return await cb.answer(cb.t("ss_expired"), True)
    if not await acquire_lock(uid):
        return await cb.answer(cb.t("busy_msg"), True)
    err = None
    try:
        await cb.answer()
        await safe_edit(msg, tx(lang, "st_mkstk"))                    # replaces the question (buttons disappear)
        err = await _build_sticker(cb.ctx, uid, msg.chat_id, lang, rec, shape)
    except Exception as e:                                              # noqa: BLE001 — user gets a clean message
        await report_error(cb.ctx, e, "sticker_shape")
        err = "stk_fail" if rec.get("k") == "video" else "mkstk_fail"
    finally:
        await release_lock(uid)
    await db_del(path)
    if err:
        return await safe_edit(msg, tx(lang, err))
    try:
        await msg.delete()
    except TelegramError:
        pass


async def send_extra(cb: "CB", data: str) -> None:
    """dl_gif_<key> · dl_stk_<key> · dl_cmt_<key>"""
    parts = data.split("_", 2)
    if len(parts) != 3 or parts[1] not in ("gif", "stk", "cmt") or not safe_key(parts[2]):
        return await cb.answer()
    kind, key = parts[1], parts[2]
    src = await _src_for(cb, key)
    if not src:
        return await cb.answer(cb.t("session_expired"), True)
    if not await acquire_lock(cb.uid):
        return await cb.answer(cb.t("busy_msg"), True)
    chat_id = cb.q.message.chat_id
    try:
        await cb.answer(plain(cb.t(f"st_{kind}", bar="")).strip())
        if kind == "stk":
            await _extra_sticker(cb.ctx, chat_id, cb.lang, key, src, cb.uid)
        else:
            await {"gif": _extra_gif, "cmt": _extra_comments}[kind](cb.ctx, chat_id, cb.lang, key, src)
    except Exception as e:                                              # noqa: BLE001 — user gets a clean message
        await report_error(cb.ctx, e, f"extra_{kind}")
        try:
            await cb.ctx.bot.send_message(chat_id, cb.t(f"{kind}_fail"))
        except TelegramError:
            pass
    finally:
        await release_lock(cb.uid)


# ── audio on demand ──────────────────────────────────────────────────────────
async def send_audio_from_session(cb: CB, key: str):
    chat_id = cb.q.message.chat_id
    if not safe_key(key):
        return await cb.answer()
    fid = await db_get(f"fc/{key}/fid_a")                               # sent before → instant
    if isinstance(fid, str) and fid:
        await cb.answer()
        try:
            return await cb.ctx.bot.send_audio(chat_id, fid, caption=f"🎵 {bot_tag()}",
                                               reply_markup=audio_kb(cb.lang), **_UP)
        except TelegramError as e:
            log.info("cached audio failed (%s) → rebuild", e)
    s = await session_get(key)
    if not s or not s.get("audio"):                                     # session gone → rebuild from the link
        src = await _src_for(cb, key)
        m = await fetch_tiktok(src) if src else None
        if m and m["audio"]:
            s = {k: m[k] for k in ("audio", "a_title", "a_author", "title", "creator", "src")}
    if not s or not s.get("audio"):
        return await cb.answer(cb.t("session_expired"), True)
    await cb.answer(plain(cb.t("st_audio", bar="")).strip())
    await chat_action(cb.ctx, chat_id, ChatAction.UPLOAD_VOICE)
    try:
        res = await download_bytes(s["audio"])
    except TooBig:
        res = None
    if not res:
        return await cb.ctx.bot.send_message(chat_id, cb.t("no_audio"))
    sent = await send_audio_file(cb.ctx, chat_id, s, res[0], res[1], audio_kb(cb.lang))
    await save_fid(key, "fid_a", sent, "audio")


# ── shared admin helpers ─────────────────────────────────────────────────────
async def user_exists(uid: int) -> bool:
    return await db_get(f"users/{uid}/date") is not None


async def grant_vip(tid: int, on: bool) -> None:
    await load_cfg(force=True)
    (vip_set.add if on else vip_set.discard)(tid)
    await save_sys("vips")
    if not on:                                                    # removing VIP also ends a referral VIP
        vip_until.pop(tid, None)
        await db_del(f"sys/vip_until/{tid}")
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
        rows.append([Btn(cb.t("b_sup_ref"), callback_data="sup_ref"),
                     Btn(cb.t("b_sup_groups", status=status_word(lang, CFG.get("groups_on", True))),
                         callback_data="sup_toggle_groups")])
        rows.append([Btn(cb.t("b_sup_stars", status=status_word(lang, CFG.get("stars_on", False))),
                         callback_data="sup_stars")])
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

    if data == "sup_toggle_groups":
        await set_cfg(groups_on=not CFG.get("groups_on", True))
        return await show_panel(cb)

    if data == "sup_ref":
        return await ref_admin_view(cb)
    if data == "sup_stars":
        return await stars_admin_view(cb)
    if data.startswith("sup_stars_"):
        return await route_stars_admin(cb, data)
    if data.startswith("sup_ref_"):
        return await route_ref_admin(cb, data)

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

    if update.effective_chat.type != "private":                       # groups: answer as a reply to the link
        ctx = _ReplyCtx(ctx, chat_id, msg.message_id)

    status = None
    try:
        quality = await user_quality(uid)
        status = await msg.reply_text(tx(lang, "st_search", bar=bar(1)))

        # ⚡ repeated link → Telegram already holds the file: send it by file_id (no API call / download / upload)
        cached = await send_from_cache(ctx, chat_id, lang, url, quality)
        if cached:
            await count_download(uid, ctx)
            await hist_add(uid, cached)
            try:
                await status.delete()
            except TelegramError:
                pass
            return

        media = await fetch_tiktok(url)
        if not media:
            return await safe_edit(status, tx(lang, "invalid_link"))

        try:                                                           # metadata + link map for the cache
            await remember_media(media, url)
        except Exception as e:                                         # noqa: BLE001 — never block a download
            log.info("remember_media failed: %s", e)

        # remember what the ".MP3" button needs
        if media["audio"]:
            await session_save(media["key"], {k: media[k] for k in ("audio", "a_title", "a_author", "title", "creator", "src")})

        await safe_edit(status, tx(lang, "st_download", bar=bar(3)))
        auto_audio = bool(CFG.get("auto_audio"))
        audio_only = quality == "audio" and bool(media["audio"]) and not media["images"]
        kb = result_kb(lang, media, with_audio=not auto_audio)
        delivered = False

        async def send_video_now(q: str) -> bool:
            data, big = await fetch_video(media, q)
            if data:
                await safe_edit(status, tx(lang, "st_upload", bar=bar(4)))
                await chat_action(ctx, chat_id, ChatAction.UPLOAD_VIDEO)
                sent = await send_video_file(ctx, chat_id, media, data, kb)
                await save_fid(media["key"], "fid_sd" if q == "sd" else "fid_hd", sent, "video")
                return True
            if big:                                                    # > 50 MB → link button
                await ctx.bot.send_message(chat_id, f"{build_caption(media)}\n\n{tx(lang, 'too_big')}",
                                           reply_markup=result_kb(lang, media, not auto_audio, direct=big))
                return True
            return False

        if audio_only:                                                 # quality = "audio only" → MP3 instead of video
            auto_audio = True

        elif media["images"]:                                          # ── photo post
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
            delivered = await send_video_now(quality)

        elif media["audio"]:                                           # ── sound-only result
            auto_audio = True

        # automatic MP3 (panel toggle, or the user's "audio only" quality) — only if we still have time
        if auto_audio and media["audio"] and (not delivered or deadline_left(started) > 12):
            try:
                res = await download_bytes(media["audio"], timeout=max(10.0, min(30.0, deadline_left(started) - 8)))
            except TooBig:
                res = None
            if res:
                sent_a = await send_audio_file(ctx, chat_id, media, res[0], res[1], audio_kb(lang))
                await save_fid(media["key"], "fid_a", sent_a, "audio")
                delivered = True

        if audio_only and not delivered and media["videos"]:           # MP3 failed → fall back to the video
            delivered = await send_video_now("hd")

        if not delivered:
            return await safe_edit(status, tx(lang, "dl_fail"))

        await count_download(uid, ctx)
        await hist_add(uid, media)
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
    """Profile hub: HD picture + info card (followers, likes, bio …) with buttons for the secret
    stories, the latest videos and the picture as an uncompressed file."""
    msg, uid, chat_id = update.effective_message, update.effective_user.id, update.effective_chat.id

    if not await gate_message(update, ctx, uid, lang):
        return
    if not await acquire_lock(uid):
        return await msg.reply_text(tx(lang, "busy_msg"))

    status = None
    try:
        status = await msg.reply_text(tx(lang, "st_search", bar=bar(1)))
        info = await fetch_profile(username)
        if not info:
            return await safe_edit(status, tx(lang, "no_avatar"))
        if info.get("private"):
            return await safe_edit(status, tx(lang, "private_account"))

        followed = bool(_USER_RE.fullmatch(info["user"])) and await is_following(uid, info["user"])
        card, kb = profile_card(lang, info), profile_kb(lang, info["user"], followed)
        await safe_edit(status, tx(lang, "st_avatar", bar=bar(3)))
        res = None
        if info.get("pic"):
            try:
                res = await download_bytes(info["pic"], max_bytes=20_000_000, timeout=25)
            except TooBig:
                res = None
        if res:
            await safe_edit(status, tx(lang, "st_upload", bar=bar(4)))
            await chat_action(ctx, chat_id, ChatAction.UPLOAD_PHOTO)
            await send_avatar_photo(ctx, chat_id, lang, info["user"], res[0], res[1], kb, caption=card)
        else:                                            # no picture → the card alone is still useful
            await ctx.bot.send_message(chat_id, card, reply_markup=kb)

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


async def send_profile_file(cb: "CB", username: str) -> None:
    """The profile picture as a FILE — Telegram doesn't recompress it."""
    await cb.answer(plain(cb.t("st_avatar", bar="")).strip())
    chat_id = cb.q.message.chat_id
    info = await fetch_profile(username)
    res = None
    if info and not info.get("private") and info.get("pic"):
        try:
            res = await download_bytes(info["pic"], max_bytes=20_000_000, timeout=25)
        except TooBig:
            res = None
    if not res:
        return await cb.ctx.bot.send_message(chat_id, cb.t("no_avatar"))
    await chat_action(cb.ctx, chat_id, ChatAction.UPLOAD_DOCUMENT)
    kind = sniff_kind(res[0])
    ext = kind if kind in ("jpg", "png", "webp") else _ext(res[1], "jpg")
    await cb.ctx.bot.send_document(
        chat_id, InputFile(res[0], filename=f"{safe_name(info['user'], 'profile')}_HD.{ext}"),
        caption=tx(cb.lang, "avatar_caption", user=esc(info["user"]), bot=esc(BOT_USERNAME)),
        reply_markup=Kb([[Btn(cb.t("b_delete"), callback_data="close")]]), **_UP)


def latest_kb(lang: str, left: int = 0) -> Kb:
    rows = []
    if left > 0:
        rows.append([Btn(tx(lang, "b_story_more", left=left), callback_data="latest_more")])
    rows.append([Btn(tx(lang, "b_delete"), callback_data="close")])
    return Kb(rows)


async def _send_latest_item(ctx, chat_id: int, lang: str, m: dict) -> bool:
    """Download + upload ONE video of the batch → True when something was delivered."""
    await chat_action(ctx, chat_id, ChatAction.UPLOAD_VIDEO)
    data, big = await fetch_video(m)
    if data and sniff_kind(data) != "video":             # a 'video' link that serves audio / junk
        data = None
    try:
        if data:
            await send_video_file(ctx, chat_id, m, data, result_kb(lang, m, False))
            return True
        if big and _valid_button_url(big):                # > 50 MB → link button
            await ctx.bot.send_message(chat_id, f"{build_caption(m)}\n\n{tx(lang, 'too_big')}",
                                       reply_markup=result_kb(lang, m, False, direct=big))
            return True
    except TelegramError as e:
        log.info("latest video not sent: %s", e)
    return False


async def process_latest(update: Update, ctx, username: str, lang: str, started: float,
                         resume: dict | None = None) -> None:
    """Latest videos of an account — LATEST_FREE for everyone, LATEST_VIP for VIP — sent in
    time-boxed batches; `resume` continues where the last batch stopped."""
    msg, uid, chat_id = update.effective_message, update.effective_user.id, update.effective_chat.id

    if not await gate_message(update, ctx, uid, lang):
        return
    if not await acquire_lock(uid):
        return await msg.reply_text(tx(lang, "busy_msg"))

    status = None
    try:
        if resume is None:
            status = await msg.reply_text(tx(lang, "st_latest", bar=bar(1)))
            items = await fetch_latest(username, LATEST_VIP if is_vip(uid) else LATEST_FREE)
            if items is None:
                return await safe_edit(status, tx(lang, "latest_unavailable"))
            if not items:
                return await safe_edit(status, tx(lang, "latest_none", user=esc(username)))
            await safe_edit(status, tx(lang, "latest_header", user=esc(username), n=len(items)))
            idx = 0
        else:
            items, idx = resume["items"], int(resume.get("next") or 0)
        total = len(items)

        sent = 0
        while idx < total and deadline_left(started) >= 14:      # videos are heavy → bigger safety margin
            if await _send_latest_item(ctx, chat_id, lang, items[idx]):
                sent += 1
            idx += 1

        left = total - idx
        if left > 0:                                     # out of time → remember the rest for the button
            await session_save(f"latest_{uid}", {"user": username, "items": items, "next": idx})
        if not sent and left <= 0:
            if status:
                return await safe_edit(status, tx(lang, "dl_fail"))
            return await msg.reply_text(tx(lang, "dl_fail"))

        text = tx(lang, "latest_partial", n=sent, left=left) if left > 0 else tx(lang, "latest_done", n=sent)
        if left <= 0 and not is_vip(uid) and total >= LATEST_FREE:
            text += "\n\n" + tx(lang, "latest_vip_hint", free=LATEST_FREE, vip=LATEST_VIP)
        await ctx.bot.send_message(chat_id, text, reply_markup=latest_kb(lang, left))
        if resume is None and sent:
            await db_incr("sys/cfg/total_dl")
            await db_incr(f"users/{uid}/dl")

    except Exception as e:                                              # noqa: BLE001
        await report_error(ctx, e, "process_latest")
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


def tag_mp3(data: bytes, title: str, performer: str) -> bytes:
    """Write title + artist into the file's OWN ID3v2.3 tag, so players and saved copies show the
    new names too (Telegram's own display comes from the send parameters). MP3 only; any other
    format — or anything unexpected — is returned untouched."""
    try:
        if data[:3] == b"ID3" and len(data) > 10:
            size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
            audio = data[10 + size + (10 if data[5] & 0x10 else 0):]       # drop the old ID3v2 tag
        else:
            audio = data
        if not (len(audio) > 2 and audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0):
            return data                                                      # not MP3 frames
        def frame(fid: bytes, text: str) -> bytes:
            body = b"\x01" + text.encode("utf-16") + b"\x00\x00"             # UTF-16 (BOM) + terminator
            return fid + len(body).to_bytes(4, "big") + b"\x00\x00" + body
        frames = frame(b"TIT2", title) + frame(b"TPE1", performer)
        n = len(frames)
        sync = bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])
        return b"ID3\x03\x00\x00" + sync + frames + audio
    except Exception:                                                        # noqa: BLE001
        return data


def _aedit_field(msg) -> str | None:
    """'title' / 'performer' when the user is replying to one of the bot's 'type the new name' prompts."""
    r = getattr(msg, "reply_to_message", None)
    if not r or not r.from_user or not r.from_user.is_bot or not r.text:
        return None
    head = r.text.split("\n")[0].strip()
    for key, field in (("ask_aedit_title", "title"), ("ask_aedit_perf", "performer")):
        if head in {plain(tx(l, key, cur="")).split("\n")[0] for l in L}:
            return field
    return None


async def handle_audio_edit(update: Update, ctx, field: str, text: str, lang: str) -> None:
    """The user's reply to an 'edit name' prompt → the SAME audio message is re-published
    in place with the new title / artist (falls back to send-new + delete-old)."""
    msg, uid = update.effective_message, update.effective_user.id
    if not await gate_message(update, ctx, uid, lang):
        return
    value = clip(" ".join((text or "").split()), 60)
    if not value:
        return await msg.reply_text(tx(lang, "aedit_empty"))
    s = await session_get(f"aedit_{uid}")
    if not s or s.get("field") != field or not s.get("file_id"):
        return await msg.reply_text(tx(lang, "aedit_expired"))
    if value == (s.get(field) or ""):
        return await msg.reply_text(tx(lang, "aedit_same"))

    chat_id, mid = int(s["chat"]), int(s["mid"])
    title = value if field == "title" else (s.get("title") or "TikTok")
    perf = value if field == "performer" else (s.get("performer") or "TikTok")
    try:
        f = await ctx.bot.get_file(s["file_id"])
        data = bytes(await f.download_as_bytearray())
    except Exception as e:                                                   # noqa: BLE001
        log.info("audio edit: cannot fetch the file: %s", e)
        return await msg.reply_text(tx(lang, "aedit_fail"))

    data = tag_mp3(data, title, perf)
    is_m4a = data[4:8] == b"ftyp"
    fn = f"{safe_name(title, 'audio')}.{'m4a' if is_m4a else 'mp3'}"
    caption = f"🎵 <a href=\"https://t.me/{BOT_USERNAME}\">@{esc(BOT_USERNAME)}</a>"
    try:
        await ctx.bot.edit_message_media(
            chat_id=chat_id, message_id=mid,
            media=InputMediaAudio(InputFile(data, filename=fn), caption=caption, parse_mode=ParseMode.HTML,
                                  title=title, performer=perf, duration=_to_int(s.get("dur")) or None),
            reply_markup=audio_kb(lang), **_UP)
    except TelegramError as e:
        log.info("audio edit: edit_message_media failed (%s) → re-sending", e)
        try:
            await send_audio_file(ctx, chat_id, {"a_title": title, "a_author": perf}, data,
                                  "audio/mp4" if is_m4a else "audio/mpeg", audio_kb(lang))
            try:
                await ctx.bot.delete_message(chat_id, mid)
            except TelegramError:
                pass
        except TelegramError as e2:
            log.info("audio edit: re-send failed: %s", e2)
            return await msg.reply_text(tx(lang, "aedit_fail"))

    await ctx.bot.send_message(chat_id, tx(lang, "aedit_done", title=esc(title), perf=esc(perf)),
                               reply_parameters=ReplyParameters(message_id=mid, allow_sending_without_reply=True))
    for m_id in (msg.message_id, getattr(msg.reply_to_message, "message_id", None)):   # tidy the chat
        if m_id:
            try:
                await ctx.bot.delete_message(chat_id, m_id)
            except TelegramError:
                pass


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

    if not private and (not url or not CFG.get("groups_on", True)):
        return                                           # groups: only TikTok links matter — no DB work for chatter

    ud, lang = await ensure_user(update, ctx)

    if is_admin(uid) and private:                       # pending "type the ID" prompt?
        state = await pop_wait(uid)
        if state:
            return await handle_prompt(update, ctx, state, lang, started)

    if private:
        fld = _aedit_field(msg)                          # answer to an "edit audio name" prompt
        if fld:
            return await handle_audio_edit(update, ctx, fld, text, lang)

    if private and _is_search_reply(msg):                # answer to the "search TikTok" prompt
        q = text.strip()
        if q and not q.startswith("/"):
            return await process_discover(update, ctx, lang, "search", q=q[:60])
        return await msg.reply_text(tx(lang, "ask_search_prompt"), reply_markup=ForceReply(selective=True))

    if private and _is_stk_title_reply(msg):             # answer to the "name your sticker pack" prompt
        title = (msg.text or "").strip()
        if not title or title.startswith("/") or len(title) > 60:
            return await msg.reply_text(tx(lang, "stk_title_bad"), reply_markup=ForceReply(selective=True))
        await db_put(f"stk/{uid}/pending", title)
        return await msg.reply_text(tx(lang, "stk_title_ok", title=esc(title)))

    if private and _is_story_reply(msg):                 # answer to the "secret story" prompt
        username = extract_username(text)
        if username:
            return await process_story(update, ctx, username, lang, started)
        return await msg.reply_text(tx(lang, "ask_story_prompt"), reply_markup=ForceReply(selective=True))

    if private and not url and _video_file(msg):         # a video / GIF → animated sticker
        return await process_video_sticker(update, ctx, lang)

    if private and not url and _photo_file(msg):         # a photo / image file → sticker
        return await process_photo_sticker(update, ctx, lang)

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
    ptb.add_handler(CommandHandler("start", cmd_start))
    ptb.add_handler(CallbackQueryHandler(on_callback))
    ptb.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    ptb.add_handler(CommandHandler("refund", cmd_refund))
    ptb.add_handler(PreCheckoutQueryHandler(on_pre_checkout))
    ptb.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_paid))
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


@app.get("/cron/follows")
async def cron_follows(req: Request):
    """Called by a scheduler (Vercel Cron or any free pinger): announce new videos of followed accounts."""
    if not CRON_SECRET:
        return JSONResponse({"ok": False, "error": "CRON_SECRET is not set"}, status_code=403)
    try:
        allowed = (hmac.compare_digest(req.headers.get("authorization", ""), f"Bearer {CRON_SECRET}")
                   or hmac.compare_digest(req.query_params.get("key", ""), CRON_SECRET))
    except TypeError:
        allowed = False
    if not allowed:
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    async with new_client() as client:
        token = _http_ctx.set(client)
        try:
            ptb = await get_ptb()
            await load_cfg()
            stats = await run_follow_checks(_BotOnly(ptb.bot))
        except Exception as e:                                          # noqa: BLE001
            log.error("CRON ERROR: %s", traceback.format_exc())
            return JSONResponse({"ok": False, "error": str(e)[:200]}, status_code=500)
        finally:
            _http_ctx.reset(token)
    return {"ok": True, **stats}


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
        _row("ffmpeg", "ok" if ffmpeg_path() else "warn", "✓ Found" if ffmpeg_path() else "Missing",
             "" if ffmpeg_path() else "Add imageio-ffmpeg to requirements.txt (short GIF + animated sticker)"),
        _row("Pillow", "ok" if importlib.util.find_spec("PIL") else "warn",
             "✓ Found" if importlib.util.find_spec("PIL") else "Missing",
             "" if importlib.util.find_spec("PIL") else "Add Pillow to requirements.txt (static sticker fallback)"),
        _row("CRON_SECRET", "ok" if CRON_SECRET else "warn", "✓ Set" if CRON_SECRET else "Not set",
             "" if CRON_SECRET else "Needed for 🔔 follow alerts (/cron/follows)"),
        _row("Sticker fonts", "ok" if all(_custom_font(k)[0] for k in ("kurdish", "english")) else "warn", fonts_status(),
             "" if all(_custom_font(k)[0] for k in ("kurdish", "english")) else "Optional: upload kurdish.ttf and english.ttf next to the Python file"),
        _row("Kurdish text on stickers", "ok" if text_engine() != "plain" else "warn", text_engine(),
             "" if text_engine() != "plain" else "Add arabic-reshaper and python-bidi to requirements.txt"),
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


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDED FONT — DejaVu Sans Bold (free licence), subset to Latin + Arabic-script letters, zlib + base64.
# Used only for the caption text on photo stickers.
# ══════════════════════════════════════════════════════════════════════════════
_FONT_Z = "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"
