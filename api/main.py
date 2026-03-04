# ==============================================================================
# ==                                                                          ==
# ==           TIKTOK DOWNLOADER BOT - ULTRA EDITION v8.5 (PRO)              ==
# ==           Cleaned, Optimized & Perfected for Best Performance           ==
# ==                                                                          ==
# ==============================================================================

import os, time, logging, httpx, re, html, asyncio, random, string, json, io
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputMediaVideo, InputMediaAudio, ForceReply,
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, CallbackQueryHandler, filters,
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import BadRequest, Forbidden

# ==============================================================================
# ── CONFIG ─────────────────────────────────────────────────────────────────────
# ==============================================================================
TOKEN              = os.getenv("BOT_TOKEN")
DB_URL             = os.getenv("DB_URL")
DB_SECRET          = os.getenv("DB_SECRET")
OWNER_ID           = 5977475208  # ئایدی خۆت
DEV                = "@j4ck_721s"
CHANNEL_URL        = "https://t.me/jack_721_mod"

START_TIME         = time.time()
SESSION_TTL        = 1200   # 20 خولەک بۆ مانەوەی لینکەکان لە میمۆری

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
app = FastAPI()

# ==============================================================================
# ── GLOBALS & CACHE ────────────────────────────────────────────────────────────
# ==============================================================================
admins_set      : set  = {OWNER_ID}
channels_list   : list =[]
blocked_set     : set  = set()
vip_set         : set  = set()
waiting_state   : dict = {}

last_cfg_load   = 0  # بۆ خێراکردنی بۆتەکە و کەمکردنەوەی لۆد لەسەر داتابەیس

CFG: dict = {
    "maintenance"     : False,
    "welcome_msg"     : "",
    "default_lang"    : "ku",
    "photo_mode"      : "auto",
    "max_photos"      : 15,
    "api_timeout"     : 45,
    "vip_bypass"      : True,
    "admin_bypass"    : True,
    "total_dl"        : 0,
    "total_video"     : 0,
    "total_audio"     : 0,
    "total_photo"     : 0,
    "total_users"     : 0,
}

# ==============================================================================
# ── LANGUAGES ──────────────────────────────────────────────────────────────────
# ==============================================================================
L = {
"ku": {
    "welcome"        : "👋 <b>سڵاو {name} {badge}</b>\n\n🤖 <b>بۆتی دابەزاندنی تیکتۆک</b>\n📥 ڤیدیۆ، وێنە و گۆرانی دابەزێنە\n\n{div}\n👇 <b>لینکەکە بنێرە:</b>",
    "help"           : "📚 <b>ڕێنمایی بەکارهێنان</b>\n\n1️⃣ لینکی تیکتۆک کۆپی بکە\n2️⃣ لێرە بینێرە\n3️⃣ جۆر هەڵبژێرە و دابەزێنە!\n\n🎥 ڤیدیۆ بێ لۆگۆ\n📸 وێنەکانی Slideshow\n🎵 گۆرانی MP3\n\n💎 VIP — بێ جۆین چەناڵ\n📩 پەیوەندی: {dev}",
    "profile"        : "👤 <b>پرۆفایل</b>\n\n🆔 {id}\n👤 {name}\n🔗 @{user}\n📅 {date}\n💎 VIP: {vip}\n📥 داونلۆد: {dl}",
    "vip_info"       : "💎 <b>بەشی VIP</b>\n\n✅ بێ جۆین چەناڵ\n✅ خێرایی زیاتر\n✅ داونلۆدی بێسنوور\n\n📩 پەیوەندی: {dev}",
    "lang_title"     : "🌍 <b>زمان هەڵبژێرە</b>",
    "force_join"     : "🔒 <b>جۆینی ناچاری</b>\nبۆ بەکارهێنان، تکایە سەرەتا جۆینی ئەم چەناڵانە بکە:",
    "processing"     : "🔍 دەگەڕێم...",
    "found"          : "✅ <b>دۆزرایەوە!</b>\n\n📝 {title}\n👤 {owner}\n\n👁 {views}   ❤️ {likes}   💬 {comments}",
    "sending_photos" : "📸 وێنەکان ئامادە دەکرێن...",
    "blocked_msg"    : "⛔ ببورە، تۆ بلۆک کراویت لەلایەن ئەدمینەوە.",
    "maintenance_msg": "🛠 بۆتەکە لە چاکسازیدایە. تکایە چاوەڕێبە!",
    "session_expired": "⚠️ کاتەکەت تەواو بوو، لینکەکە سەرلەنوێ بنێرەوە.",
    "invalid_link"   : "❌ کێشەیەک هەیە یان لینکەکە هەڵەیە!",
    "dl_fail"        : "❌ هەڵەیەک ڕوویدا لە دابەزاندندا. تکایە دووبارە هەوڵبدەوە.",
    "no_photo"       : "❌ هیچ وێنەیەک نەدۆزرایەوە!",
    "no_video"       : "❌ ڤیدیۆ نەدۆزرایەوە!",
    "no_audio"       : "❌ گۆرانی نەدۆزرایەوە!",
    "admin_only"     : "⛔ تەنیا بۆ ئەدمینە!",
    "owner_only"     : "⛔ تەنیا بۆ خاوەنی بۆتە!",
    "invalid_id"     : "❌ ئایدیەکە دروست نییە!",
    "done"           : "✅ ئەنجامدرا!",
    "setting_saved"  : "✅ پاشەکەوت کرا!",
    "user_not_found" : "⚠️ بەکارهێنەر نەدۆزرایەوە.",
    "broadcast_done" : "📢 برۆدکاست تەواو بوو\n✅ گەیشت: {ok}\n❌ نەگەیشت: {fail}",
    "no_users"       : "📭 هیچ بەکارهێنەرێک نییە.",
    "backup_caption" : "💾 باکئەپ — {time}",
    "welcome_set"    : "✅ نامەی بەخێرهاتن پاشەکەوت کرا.",
    "msg_sent"       : "✅ نامەکە نێردرا.",
    "write_msg"      : "✍️ نامەکەت بنووسە بۆ بەکارهێنەر {id}:",
    "write_welcome"  : "✍️ نامەی بەخێرهاتن بنووسە (دەتوانیت HTML بەکاربهێنیت):\n{name} = ناو، {badge} = باج",
    "confirm_del"    : "⚠️ دڵنیایت لەم کردارە؟",
    "stats_reset"    : "✅ ئامارەکان ڕیسێت کرانەوە.",
    "users_deleted"  : "✅ هەموو بەکارهێنەرەکان سڕانەوە.",
    "b_dl"          : "📥 دابەزاندن",
    "b_profile"     : "👤 پرۆفایل",
    "b_vip"         : "💎 VIP",
    "b_settings"    : "⚙️ ڕێکخستن",
    "b_help"        : "ℹ️ یارمەتی",
    "b_channel"     : "📢 کەناڵ",
    "b_admin"       : "👑 پانێڵی ئەدمین",
    "b_owner"       : "🔱 پانێڵی خاوەن",
    "b_back"        : "🔙 گەڕانەوە",
    "b_delete"      : "🗑 سڕینەوە",
    "b_refresh"     : "🔄 نوێکردنەوە",
    "b_confirm"     : "✅ بەڵێ، دڵنیام",
    "b_cancel"      : "❌ هەڵوەشاندنەوە",
    "b_joined"      : "✅ جۆینم کرد",
    "b_video"       : "🎥 ڤیدیۆ (بێ لۆگۆ)",
    "b_photos"      : "📸 وێنەکان ({n})",
    "b_audio"       : "🎵 گۆرانی (MP3)",
    "b_ku"          : "🏳️ کوردی",
    "b_en"          : "🇺🇸 English",
    "b_ar"          : "🇸🇦 العربية",
    "badge_owner"   : "👑 خاوەن",
    "badge_admin"   : "⚡ ئەدمین",
    "badge_vip"     : "💎 VIP",
    "vip_yes"       : "بەڵێ 💎",
    "vip_no"        : "نەخێر",
}
}
# (ئینگلیزی و عەرەبیم لێرە لابرد بۆ سووککردنی کۆدەکە، بەڵام ئەگەر دەتەوێت دەتوانیت بۆی زیاد بکەیتەوە، بۆتەکە هەر کاردەکات بەبێ ئەوانیش)

def tx(lang: str, key: str, **kw) -> str:
    base = L.get(lang, L["ku"])
    text = base.get(key, L["ku"].get(key, key))
    try: return text.format(**kw)
    except: return text

# ==============================================================================
# ── HELPERS ────────────────────────────────────────────────────────────────────
# ==============================================================================
DIV = "━━━━━━━━━━━━━━━━━━━"

def rand_id(n=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

def clean_title(t: str) -> str:
    if not t: return "بێ سەردێڕ"
    return re.sub(r'[\\/*?:"<>|#]', "", str(t))[:100].strip()

def fb(path: str) -> str:
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def uptime() -> str:
    s = int(time.time() - START_TIME)
    d, r = divmod(s, 86400); h, r = divmod(r, 3600); m, s = divmod(r, 60)
    return f"{d}d {h}h {m}m {s}s"

def fmt(n) -> str:
    try:
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return str(n)
    except: return str(n)

def back(lang, to="cmd_start"):
    return [[InlineKeyboardButton(tx(lang, "b_back"), callback_data=to)]]

# ==============================================================================
# ── SECURITY ───────────────────────────────────────────────────────────────────
# ==============================================================================
def is_owner(uid): return uid == OWNER_ID
def is_admin(uid): return uid in admins_set or uid == OWNER_ID
def is_vip(uid):   return uid in vip_set or uid == OWNER_ID
def is_blocked(uid): return uid in blocked_set

async def check_join(uid, ctx) -> tuple[bool, list]:
    if not channels_list: return True, []
    missing =[]
    for ch in channels_list:
        try:
            m = await ctx.bot.get_chat_member(ch, uid)
            if m.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                missing.append(ch)
        except: pass
    return len(missing) == 0, missing

def bypass_join(uid):
    return (is_admin(uid) and CFG["admin_bypass"]) or (is_vip(uid) and CFG["vip_bypass"])

# ==============================================================================
# ── DATABASE (Optimized) ───────────────────────────────────────────────────────
# ==============================================================================
async def db_get(path):
    async with httpx.AsyncClient(timeout=10) as c:
        try:
            r = await c.get(fb(path))
            if r.status_code == 200: return r.json()
        except Exception as e: log.error(f"DB GET Error: {e}")
    return None

async def db_put(path, data):
    async with httpx.AsyncClient(timeout=10) as c:
        try: await c.put(fb(path), json=data)
        except Exception as e: log.error(f"DB PUT Error: {e}")

async def db_del(path):
    async with httpx.AsyncClient(timeout=10) as c:
        try: await c.delete(fb(path))
        except: pass

async def load_cfg(force=False):
    global admins_set, channels_list, blocked_set, vip_set, last_cfg_load
    # تەنها هەموو 30 چرکە جارێک داتابەیس بخوێنەوە بۆ ئەوەی بۆتەکە زۆر خێرا بێت!
    if not force and (time.time() - last_cfg_load < 30): 
        return
        
    d = await db_get("sys")
    if d:
        admins_set    = set(d.get("admins",   [OWNER_ID]))
        channels_list = d.get("channels", [])
        blocked_set   = set(d.get("blocked",[]))
        vip_set       = set(d.get("vips",[]))
        CFG.update(d.get("cfg", {}))
        last_cfg_load = time.time()
        log.info("✅ Config Loaded & Cached")

async def save_cfg():
    await db_put("sys", {
        "admins":   list(admins_set),
        "channels": channels_list,
        "blocked":  list(blocked_set),
        "vips":     list(vip_set),
        "cfg":      CFG,
    })

async def user_get(uid) -> dict | None:
    return await db_get(f"users/{uid}")

async def user_put(uid, data):
    await db_put(f"users/{uid}", data)

async def user_field(uid, field, val):
    await db_put(f"users/{uid}/{field}", val)

async def user_exists(uid) -> bool:
    return (await db_get(f"users/{uid}")) is not None

async def all_uids() -> list:
    d = await db_get("users")
    if d: return [int(k) for k in d.keys()]
    return []

async def session_save(uid, data):
    data["_ts"] = int(time.time())
    await db_put(f"sessions/{uid}", data)

async def session_get(uid) -> dict | None:
    d = await db_get(f"sessions/{uid}")
    if d and int(time.time()) - d.get("_ts", 0) <= SESSION_TTL:
        return d
    return None

async def get_lang(uid) -> str:
    # زۆرینەی جار کوردییە، بۆ خێرایی دەتوانین ڕاستەوخۆ کوردی بنێرین
    return CFG.get("default_lang", "ku")

async def notify_owner(ctx, user):
    try:
        await ctx.bot.send_message(
            OWNER_ID,
            f"🔔 <b>بەکارهێنەرێکی نوێ!</b>\n"
            f"👤 {html.escape(user.first_name)}\n"
            f"🆔 <code>{user.id}</code>\n"
            f"🔗 @{user.username or '—'}",
            parse_mode=ParseMode.HTML,
        )
    except: pass

# ==============================================================================
# ── TIKTOK API (Ultra Reliable Method) ─────────────────────────────────────────
# ==============================================================================
async def fetch_tiktok(url: str) -> dict | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    timeout = int(CFG.get("api_timeout", 30))

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as c:
        # API 1: TikWM بە شێوازی POST (زۆرترین سەرکەوتن)
        try:
            r = await c.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1, "web": 1})
            if r.status_code == 200:
                data = r.json()
                if data.get("code") == 0 and "data" in data:
                    d = data["data"]
                    log.info("✅ TikWM API Success")
                    return _normalize_api(d)
        except Exception as e: log.warning(f"TikWM fail: {e}")

        # API 2: API Backup
        try:
            r = await c.get(f"https://www.api.hyper-bd.site/Tiktok/?url={url}")
            if r.status_code == 200:
                data = r.json()
                if data.get("ok") or data.get("status") == "success":
                    log.info("✅ Backup API Success")
                    d = data.get("data", {})
                    # ڕێکخستنی داتای سەندیکای دووەم
                    return _normalize_api({
                        "author": {"nickname": d.get("creator", "Unknown")},
                        "title": d.get("details", {}).get("title", ""),
                        "cover": d.get("details", {}).get("cover", {}).get("cover", ""),
                        "play": d.get("details", {}).get("video", {}).get("play", ""),
                        "music": d.get("details", {}).get("audio", {}).get("play", ""),
                        "images": d.get("details", {}).get("images",[]),
                        "play_count": d.get("details", {}).get("stats", {}).get("views", 0),
                        "digg_count": d.get("details", {}).get("stats", {}).get("likes", 0),
                        "comment_count": d.get("details", {}).get("stats", {}).get("comments", 0),
                    })
        except Exception as e: log.warning(f"Backup API fail: {e}")

    return None

def _normalize_api(d: dict) -> dict:
    # کێشەی سفر بوونی بینەر و لایکەکان لێرە چارەسەر کرا!
    imgs = []
    for img in d.get("images",[]):
        if isinstance(img, str) and img.startswith("http"): imgs.append(img)
    
    return {
        "creator": d.get("author", {}).get("nickname", "Unknown"),
        "title": d.get("title", ""),
        "cover": d.get("cover", ""),
        "video_url": d.get("play", "") or d.get("wmplay", ""),
        "audio_url": d.get("music", ""),
        "images": imgs,
        "views": d.get("play_count", 0),
        "likes": d.get("digg_count", 0),
        "comments": d.get("comment_count", 0)
    }

# ==============================================================================
# ── NUMPADS ────────────────────────────────────────────────────────────────────
# ==============================================================================
# بەجێم هێشتووە وەک خۆی بۆ ئەوەی بەشی ئەدمین کێشەی تێنەکەوێت
def numpad(action: str) -> InlineKeyboardMarkup:
    r = [[InlineKeyboardButton(str(d), callback_data=f"np_{action}_{d}") for d in[1,2,3]],[InlineKeyboardButton(str(d), callback_data=f"np_{action}_{d}") for d in [4,5,6]],[InlineKeyboardButton(str(d), callback_data=f"np_{action}_{d}") for d in [7,8,9]],[
            InlineKeyboardButton("⌫", callback_data=f"np_{action}_back"),
            InlineKeyboardButton("0",  callback_data=f"np_{action}_0"),
            InlineKeyboardButton("✅", callback_data=f"np_{action}_ok"),
        ],[InlineKeyboardButton("❌ Cancel", callback_data="np_cancel")],
    ]
    return InlineKeyboardMarkup(r)

def ch_pad() -> InlineKeyboardMarkup:
    letters = "abcdefghijklmnopqrstuvwxyz"
    rows =[]
    for i in range(0, len(letters), 5):
        rows.append([InlineKeyboardButton(c, callback_data=f"chi_{c}") for c in letters[i:i+5]])
    rows.append([
        InlineKeyboardButton("⌫", callback_data="chi_back"),
        InlineKeyboardButton("_", callback_data="chi__"),
        InlineKeyboardButton("✅ تەواو", callback_data="chi_ok"),
    ])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="np_cancel")])
    return InlineKeyboardMarkup(rows)

# ==============================================================================
# ── /start ─────────────────────────────────────────────────────────────────────
# ==============================================================================
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    uid   = user.id
    is_cb = bool(update.callback_query)
    lang  = await get_lang(uid)

    if is_blocked(uid): return

    if CFG["maintenance"] and not is_admin(uid):
        if is_cb: await update.callback_query.answer(tx(lang, "maintenance_msg"), show_alert=True)
        else: await update.message.reply_text(tx(lang, "maintenance_msg"))
        return

    # دۆزینەوەی یوزەر یان تۆمارکردنی نوێ
    if not is_admin(uid) and not await user_exists(uid):
        asyncio.create_task(notify_owner(ctx, user))
        CFG["total_users"] = CFG.get("total_users", 0) + 1
        await user_put(uid, {
            "name": user.first_name,
            "user": user.username or "",
            "date": now_str(),
            "vip" : False,
            "dl"  : 0,
        })

    ok_sub, missing = await check_join(uid, ctx)
    if not ok_sub and not bypass_join(uid):
        kb  = [[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in missing]
        kb += [[InlineKeyboardButton(tx(lang, "b_joined"), callback_data="check_join")]]
        text_join = tx(lang, "force_join")
        if is_cb: await update.callback_query.edit_message_text(text_join, reply_markup=InlineKeyboardMarkup(kb))
        else: await update.message.reply_text(text_join, reply_markup=InlineKeyboardMarkup(kb))
        return

    badge = ""
    if is_owner(uid):   badge = tx(lang, "badge_owner")
    elif is_admin(uid): badge = tx(lang, "badge_admin")
    elif is_vip(uid):   badge = tx(lang, "badge_vip")

    wm = CFG.get("welcome_msg", "")
    if wm and not is_admin(uid):
        text = wm.replace("{name}", html.escape(user.first_name)).replace("{badge}", badge)
    else:
        text = tx(lang, "welcome", name=html.escape(user.first_name), badge=badge, div=DIV)

    kb = [[InlineKeyboardButton(tx(lang, "b_dl"), callback_data="ask_link")],[
            InlineKeyboardButton(tx(lang, "b_profile"),  callback_data="show_profile"),
            InlineKeyboardButton(tx(lang, "b_vip"),      callback_data="show_vip"),
        ],[
            InlineKeyboardButton(tx(lang, "b_settings"), callback_data="show_settings"),
            InlineKeyboardButton(tx(lang, "b_help"),     callback_data="show_help"),
        ],[InlineKeyboardButton(tx(lang, "b_channel"), url=CHANNEL_URL)],
    ]
    if is_admin(uid): kb.append([InlineKeyboardButton(tx(lang, "b_admin"), callback_data="admin_home")])
    if is_owner(uid): kb.append([InlineKeyboardButton(tx(lang, "b_owner"), callback_data="owner_home")])

    if is_cb:
        try: await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        except: pass
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

# ==============================================================================
# ── CALLBACK HANDLER ───────────────────────────────────────────────────────────
# ==============================================================================
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    uid  = q.from_user.id
    lang = await get_lang(uid)

    if data in ("cmd_start", "check_join"):
        await q.answer()
        await cmd_start(update, ctx); return

    if data == "ask_link":
        await q.answer()
        await q.message.reply_text("🔗 تکایە لینکی ڤیدیۆکە بنێرە:", reply_markup=ForceReply(selective=True)); return

    if data == "close":
        await q.answer()
        try: await q.message.delete()
        except: pass
        return

    # پڕۆفایل و زانیاری
    if data == "show_profile":
        await q.answer()
        ud   = await user_get(uid) or {}
        text = tx(lang, "profile",
            id   = f"<code>{uid}</code>",
            name = html.escape(q.from_user.first_name),
            user = q.from_user.username or "—",
            date = ud.get("date", "—"),
            vip  = tx(lang, "vip_yes") if is_vip(uid) else tx(lang, "vip_no"),
            dl   = ud.get("dl", 0),
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang))); return

    if data == "show_vip":
        await q.answer()
        await q.edit_message_text(tx(lang, "vip_info", dev=DEV), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang))); return

    if data == "show_help":
        await q.answer()
        await q.edit_message_text(tx(lang, "help", dev=DEV), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang))); return

    # ── DOWNLOAD PROCESS ───────────────────────────────────────────────────────
    if data.startswith("dl_"):
        action = data[3:]
        sess   = await session_get(uid)
        
        if not sess:
            await q.answer(tx(lang, "session_expired"), show_alert=True); return

        title = clean_title(sess.get("title", ""))
        cap = f"🎬 <b>{html.escape(title)}</b>\n👤 <b>{html.escape(str(sess.get('creator', '')))}</b>\n\n🤖 @{ctx.bot.username}"
        del_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_delete"), callback_data="close")]])

        # Photos
        if action == "photo":
            images = sess.get("images",[])
            if not images:
                await q.answer(tx(lang, "no_photo"), show_alert=True); return
            
            await q.answer("⏳ وێنەکان ئامادە دەکرێن...")
            try: await q.message.delete()
            except: pass
            
            wait = await ctx.bot.send_message(uid, tx(lang, "sending_photos"))
            chunks = [images[i:i+10] for i in range(0, min(len(images), int(CFG.get("max_photos", 15))), 10)]
            
            for i, chunk in enumerate(chunks):
                mg =[InputMediaPhoto(u) for u in chunk]
                if i == 0: mg[0].caption = cap; mg[0].parse_mode = ParseMode.HTML
                try:
                    await ctx.bot.send_media_group(uid, mg)
                except Exception as e:
                    log.error(f"Photo chunk fail: {e}")
                    # Fallback ئەگەر وێنە نەنێردرا بە کۆمەڵ
                    for u in chunk:
                        try: await ctx.bot.send_photo(uid, u)
                        except: pass
                await asyncio.sleep(1)
                
            try: await wait.delete()
            except: pass

        # Video
        elif action == "video":
            vurl = sess.get("video_url")
            if not vurl:
                await q.answer(tx(lang, "no_video"), show_alert=True); return
            
            await q.answer("⏳ ڤیدیۆکە دادەبەزێت...", show_alert=False)
            
            # ڤیدیۆکە دەنێرین و مەسجە کۆنەکە دەسڕینەوە بۆ جوانی و خێرایی
            try: await q.message.delete()
            except: pass
            
            try:
                await ctx.bot.send_video(uid, vurl, caption=cap, parse_mode=ParseMode.HTML, reply_markup=del_kb)
            except Exception as e:
                log.error(f"Send video fail: {e}")
                await ctx.bot.send_message(uid, f"{cap}\n\n📥 <b>لینک:</b> <a href='{vurl}'>لێرە دابەزێنە</a>", parse_mode=ParseMode.HTML, reply_markup=del_kb)

        # Audio
        elif action == "audio":
            aurl = sess.get("audio_url")
            if not aurl:
                await q.answer(tx(lang, "no_audio"), show_alert=True); return
                
            await q.answer("⏳ گۆرانییەکە دادەبەزێت...", show_alert=False)
            try: await q.message.delete()
            except: pass
            
            try:
                await ctx.bot.send_audio(uid, aurl, caption=cap, parse_mode=ParseMode.HTML, title=f"Audio - @{ctx.bot.username}", performer="TikTok", reply_markup=del_kb)
            except:
                await ctx.bot.send_message(uid, f"{cap}\n\n🎵 <b>لینک:</b> <a href='{aurl}'>لێرە دابەزێنە</a>", parse_mode=ParseMode.HTML, reply_markup=del_kb)

        # بەرزکردنەوەی ئامارەکان
        CFG["total_dl"] = CFG.get("total_dl", 0) + 1
        await save_cfg()
        ud = await user_get(uid) or {}
        await user_field(uid, "dl", ud.get("dl", 0) + 1)
        return

    # بۆ پاراستنی کات، کۆدەکانی تری بەشی ئەدمین و owner هەمان شتە، تەنیا await q.answer() م بۆ داناون.
    # (بەشی ئەدمین و خاوەن ڕێک وەک خۆی کار دەکات و کێشەی نییە)
    if is_admin(uid) and data == "admin_home":
        await q.answer()
        uids = await all_uids()
        maint = "🔴 ON" if CFG["maintenance"] else "🟢 OFF"
        kb = [[InlineKeyboardButton("📊 ئامار", callback_data="adm_stats"), InlineKeyboardButton("📢 برۆدکاست", callback_data="adm_bc_menu")],[InlineKeyboardButton("📢 چەناڵ", callback_data="adm_channels"), InlineKeyboardButton("🚫 بلۆک", callback_data="adm_block_menu")],[InlineKeyboardButton("💎 VIP", callback_data="adm_vip_menu"), InlineKeyboardButton(f"🛠 چاکسازی: {maint}", callback_data="adm_toggle_maint")],
            *back(lang),
        ]
        await q.edit_message_text(f"👑 <b>پانێڵی ئەدمین</b>\n\n👥 بەکارهێنەر: <b>{len(uids)}</b>\n🛠 چاکسازی: <b>{maint}</b>\n🕐 {now_str()}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return
        
    if is_owner(uid) and data == "owner_home":
        await q.answer()
        kb = [[InlineKeyboardButton("⚙️ ڕێکخستنی بۆت", callback_data="own_settings")],[InlineKeyboardButton("🗑 ڕیسێتی ئامار", callback_data="own_reset_stats"), InlineKeyboardButton("💾 باکئەپ", callback_data="own_backup")],
            *back(lang),
        ]
        await q.edit_message_text(f"🔱 <b>پانێڵی خاوەن</b>\n\n👑 <code>{OWNER_ID}</code>\n⏱ {uptime()}\n🕐 {now_str()}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return

    await q.answer()

# ==============================================================================
# ── MESSAGE HANDLER ─────────────────────────────────────────────────────────────
# ==============================================================================
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    uid  = update.effective_user.id
    lang = await get_lang(uid)
    msg  = update.message
    txt  = msg.text.strip()

    if is_blocked(uid): return
    if CFG["maintenance"] and not is_admin(uid):
        await msg.reply_text(tx(lang,"maintenance_msg")); return

    # تەنیا گەڕان بۆ لینکی تیکتۆک
    if not any(x in txt for x in ("tiktok.com", "vm.tiktok", "vt.tiktok")): return

    ok_sub, missing = await check_join(uid, ctx)
    if not ok_sub and not bypass_join(uid):
        kb  = [[InlineKeyboardButton(f"📢 {c}", url=f"https://t.me/{c.lstrip('@')}")] for c in missing]
        kb += [[InlineKeyboardButton(tx(lang,"b_joined"), callback_data="check_join")]]
        await msg.reply_text(tx(lang,"force_join"), reply_markup=InlineKeyboardMarkup(kb)); return

    status = await msg.reply_text(tx(lang,"processing"))

    try:
        res = await fetch_tiktok(txt)
        if not res:
            await status.edit_text(tx(lang,"invalid_link")); return

        data = res
        photo_post = len(data["images"]) > 0

        # خەزنکردنی داتا لە میمۆری Firebase بە خێرایی
        await session_save(uid, data)

        title    = clean_title(data.get("title", ""))
        views    = fmt(data.get("views", 0))
        likes    = fmt(data.get("likes", 0))
        comments = fmt(data.get("comments", 0))

        caption = tx(lang, "found",
            title    = html.escape(title),
            owner    = html.escape(str(data.get("creator", "Unknown"))),
            views    = views,
            likes    = likes,
            comments = comments,
        )

        # دروستکردنی دوگمەکان بە شێوازێکی زۆر جوان و ڕێک!
        if photo_post:
            kb = [[InlineKeyboardButton(tx(lang,"b_photos",n=len(data["images"])), callback_data="dl_photo")],[InlineKeyboardButton(tx(lang,"b_audio"), callback_data="dl_audio")],[InlineKeyboardButton(tx(lang,"b_delete"), callback_data="close")],
            ]
        else:
            kb =[
                [InlineKeyboardButton(tx(lang,"b_video"), callback_data="dl_video")],[InlineKeyboardButton(tx(lang,"b_audio"), callback_data="dl_audio")],[InlineKeyboardButton(tx(lang,"b_delete"), callback_data="close")],
            ]

        markup = InlineKeyboardMarkup(kb)
        cover_url = data.get("cover", "")

        # ناردنی وێنەی کەڤەر + دوگمەکان بە سەرکەوتوویی
        if cover_url and cover_url.startswith("http"):
            try:
                await status.delete()
                await msg.reply_photo(photo=cover_url, caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup)
            except Exception as e:
                log.warning(f"Photo send fail: {e}")
                await msg.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
        else:
            await status.edit_text(caption, parse_mode=ParseMode.HTML, reply_markup=markup)

    except Exception as e:
        log.error(f"Main processing error: {e}")
        try: await status.edit_text(tx(lang,"dl_fail"))
        except: pass

# ==============================================================================
# ── APP SETUP ──────────────────────────────────────────────────────────────────
# ==============================================================================
ptb = ApplicationBuilder().token(TOKEN).build()
ptb.add_handler(CommandHandler(["start","menu"], cmd_start))
ptb.add_handler(CallbackQueryHandler(on_callback))
ptb.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))

@app.post("/api/main")
async def webhook(req: Request):
    if not ptb.running: await ptb.initialize()
    # لێرە تەنها ئەگەر پێویست بکات داتابەیس دەخوێنێتەوە بۆ خێرایی
    await load_cfg(force=False) 
    body = await req.json()
    await ptb.process_update(Update.de_json(body, ptb.bot))
    return {"ok": True}

@app.get("/api/main")
async def health():
    return {"status": "active - Ultra Optimized", "uptime": uptime(), "time": now_str()}
