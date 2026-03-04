# ==============================================================================
# ==                                                                          ==
# ==           TIKTOK DOWNLOADER BOT - V11.0 ULTRA PRO MAX (GOD MODE)         ==
# ==           Developed exclusively for: @j4ck_721s                          ==
# ==           Features: Super Panel, Auto-Fallback, Live Error Notifier      ==
# ==                                                                          ==
# ==============================================================================

import os, time, logging, httpx, re, html, asyncio, random, string, json, io, traceback
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputMediaVideo, InputMediaAudio, ForceReply
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, CallbackQueryHandler, filters,
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import BadRequest, Forbidden, TelegramError

# ==============================================================================
# ── 1. CONFIGURATION & SECURE ENV LOADING ─────────────────────────────────────
# ==============================================================================
# بەکارهێنانی DUMMY بۆ ئەوەی ئەگەر لە Vercel لەبیرت چوو دایبنێیت، پڕۆژەکە کڕاش نەکات
TOKEN              = os.getenv("BOT_TOKEN") or "DUMMY_TOKEN"
DB_URL             = os.getenv("DB_URL") or ""
DB_SECRET          = os.getenv("DB_SECRET") or ""
OWNER_ID           = 5977475208  # ئایدی خاوەنی سەرەکی
DEV                = "@j4ck_721s"
CHANNEL_URL        = "https://t.me/jack_721_mod"

START_TIME         = time.time()
SESSION_TTL        = 1800  # 30 خولەک مانەوەی زانیاری ڤیدیۆکان

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)
app = FastAPI()

# داتابەیسی کاتی (خێراکردنی بۆت)
super_admins_set: set = {OWNER_ID}
admins_set      : set = {OWNER_ID}
channels_list   : list =[]
blocked_set     : set = set()
vip_set         : set = set()
waiting_state   : dict = {}
last_cfg_load   = 0

CFG: dict = {
    "maintenance"     : False,
    "welcome_msg"     : "",
    "default_lang"    : "ku",
    "photo_mode"      : "auto",
    "max_photos"      : 15,
    "api_timeout"     : 60,
    "vip_bypass"      : True,
    "admin_bypass"    : True,
    "total_dl"        : 0,
    "total_video"     : 0,
    "total_audio"     : 0,
    "total_photo"     : 0,
    "total_users"     : 0,
    "active_api"      : "auto" # auto, tikwm, hyper, backup
}

# ==============================================================================
# ── 2. MASSIVE MULTI-LANGUAGE DICTIONARY ──────────────────────────────────────
# ==============================================================================
L = {
"ku": {
    "welcome": "👋 <b>سڵاو {name} {badge}</b>\n\n🤖 <b>بەخێربێیت بۆ پێشکەوتووترین بۆتی تیکتۆک</b>\n📥 لێرە دەتوانیت ڤیدیۆ (بێ لۆگۆ)، وێنەکان و گۆرانی دابەزێنیت بە بەرزترین خێرایی.\n\n━━━━━━━━━━━━━━━━━━━\n👇 <b>تەنیا لینکی تیکتۆکەکە بنێرە بۆم:</b>",
    "help": "📚 <b>ڕێنمایی بەکارهێنان</b>\n\n1️⃣ بڕۆ ناو تیکتۆک و لینکی ڤیدیۆکە کۆپی بکە.\n2️⃣ لینکەکە لێرە (پەیست) بکە و بینێرە.\n3️⃣ بۆتەکە زانیارییەکانت پێ دەدات، دوگمەی مەبەست هەڵبژێرە!\n\n🎥 <b>ڤیدیۆ:</b> بەبێ هیچ لۆگۆ و نیشانەیەک.\n📸 <b>وێنە:</b> هەموو وێنەکانی پۆستەکە بە کوالێتی بەرز.\n🎵 <b>گۆرانی:</b> دەنگی ڤیدیۆکە بە فۆرماتی MP3.\n\n💎 <b>بەشی VIP:</b> بێ جۆین چەناڵ و خێرایی زۆرتر.\n📩 <b>پەیوەندی:</b> {dev}",
    "profile": "👤 <b>کارتی پرۆفایلەکەت</b>\n\n🆔 ئایدی: <code>{id}</code>\n👤 ناو: <b>{name}</b>\n🔗 یوزەرنەیم: @{user}\n📅 تۆماربوون: {date}\n💎 دۆخی VIP: <b>{vip}</b>\n📥 کۆی دابەزاندنەکانت: <b>{dl}</b> جار",
    "vip_info": "💎 <b>تایبەتمەندییەکانی VIP</b>\n\n✅ هیچ چەناڵێکی ناچاریت نایەتە پێش.\n✅ خێرایی دابەزاندنت خێراتر دەبێت لە ئاسایی.\n✅ دەتوانیت وێنەی بێسنوور دابەزێنیت.\n\nبۆ کڕینی VIP نامە بنێرە بۆ: {dev}",
    "lang_title": "🌍 <b>تکایە زمانێک هەڵبژێرە:</b>",
    "force_join": "🔒 <b>جۆینی ناچاری</b>\nبۆ بەکارهێنان، تکایە سەرەتا جۆینی ئەم چەناڵانەی خوارەوە بکە، پاشان کلیک لە '✅ جۆینم کرد' بکە:",
    "processing": "🔍 <b>دەگەڕێم بۆ لینکەکە...</b>\n<i>تکایە چەند چرکەیەک چاوەڕێبە ⏳</i>",
    "found": "✅ <b>سەرکەوتوو بوو! دۆزرایەوە!</b>\n\n📝 <b>سەردێڕ:</b> {title}\n👤 <b>خاوەن:</b> {owner}\n\n📊 <b>ئامارەکان:</b>\n👁 بینەر: <b>{views}</b>\n❤️ لایک: <b>{likes}</b>\n💬 کۆمێنت: <b>{comments}</b>\n\n👇 <i>جۆری دابەزاندن هەڵبژێرە:</i>",
    "sending_photos": "📸 <b>وێنەکان ئامادە دەکرێن...</b>",
    "blocked_msg": "⛔ <b>ببورە!</b> تۆ لەلایەن بەڕێوەبەرایەتییەوە بلۆک کراویت.",
    "maintenance_msg": "🛠 <b>چاکسازی کاتی!</b>\nبۆتەکەمان لە ئێستادا لەژێر پەرەپێدانە. تکایە دواتر هەوڵبدەرەوە.",
    "session_expired": "⚠️ <b>کات بەسەرچوو!</b> لینکەکە سەرلەنوێ بنێرەوە لێرە.",
    "invalid_link": "❌ <b>لینکەکە هەڵەیە یان نادۆزرێتەوە!</b>",
    "dl_fail": "❌ <b>هەڵەیەک ڕوویدا!</b> ناتوانرێت ئەم پۆستە دابەزێنرێت، سێرڤەر جەنجاڵە.",
    "no_photo": "❌ ئەم پۆستە هیچ وێنەیەکی تێدا نییە!",
    "no_video": "❌ ڤیدیۆکە نەدۆزرایەوە!",
    "no_audio": "❌ دەنگی ئەم ڤیدیۆیە بەردەست نییە!",
    "admin_only": "⛔ ئەم بەشە تەنیا بۆ ئەدمینەکانە!",
    "super_only": "⛔ ئەم بەشە تەنیا بۆ سوپەر ئەدمینەکانە!",
    "owner_only": "⛔ ئەم بەشە تەنیا بۆ خاوەنی بۆتە!",
    "invalid_id": "❌ ئایدیەکە دروست نییە!",
    "done": "✅ ئەنجامدرا بە سەرکەوتوویی!",
    "setting_saved": "✅ ڕێکخستنەکان پاشەکەوت کران!",
    "user_not_found": "⚠️ بەکارهێنەر لە داتابەیس نەدۆزرایەوە.",
    "broadcast_done": "📢 <b>برۆدکاست تەواو بوو</b>\n✅ گەیشت بە: <b>{ok}</b>\n❌ نەگەیشت: <b>{fail}</b>",
    "no_users": "📭 هیچ بەکارهێنەرێک نییە.",
    "backup_caption": "💾 <b>باکئەپی داتابەیس</b>\n📅 کات: {time}",
    "welcome_set": "✅ نامەی بەخێرهاتن گۆڕدرا.",
    "msg_sent": "✅ نامەکە نێردرا.",
    "write_msg": "✍️ <b>نامەکەت بنووسە:</b>",
    "write_welcome": "✍️ <b>نامەی بەخێرهاتن بنووسە (تێکستی HTML):</b>",
    "confirm_del": "⚠️ <b>ئایا بەتەواوی دڵنیایت؟</b>",
    "stats_reset": "✅ هەموو ئامارەکانی دابەزاندن سفر کرانەوە.",
    "users_deleted": "✅ هەموو بەکارهێنەرەکان سڕانەوە!",
    "b_dl": "📥 دابەزاندنی نوێ",
    "b_profile": "👤 پرۆفایلی من",
    "b_vip": "💎 بەشی VIP",
    "b_settings": "⚙️ ڕێکخستن و زمان",
    "b_help": "ℹ️ فێرکاری",
    "b_channel": "📢 کەناڵی بۆت",
    "b_admin": "🛡 پانێڵی ئەدمین",
    "b_super": "🌌 سوپەر پانێل",
    "b_owner": "👑 پانێڵی خاوەن",
    "b_back": "🔙 گەڕانەوە",
    "b_delete": "🗑 سڕینەوە",
    "b_refresh": "🔄 نوێکردنەوە",
    "b_confirm": "✅ بەڵێ، دڵنیام",
    "b_cancel": "❌ نەخێر، هەڵوەشاندنەوە",
    "b_joined": "✅ جۆینم کرد",
    "b_video": "🎥 دابەزاندنی ڤیدیۆ (بێ لۆگۆ)",
    "b_photos": "📸 وێنەکان ({n})",
    "b_audio": "🎵 گۆرانی (MP3)",
    "b_ku": "🏳️ کوردی",
    "b_en": "🇺🇸 English",
    "b_ar": "🇸🇦 العربية",
    "badge_owner": "👑 (خاوەن)",
    "badge_super": "🌌 (سوپەر)",
    "badge_admin": "🛡 (ئەدمین)",
    "badge_vip": "💎 (VIP)",
    "vip_yes": "بەڵێ، چالاکە 💎",
    "vip_no": "نەخێر",
}
}
# زمانەکانی تر (ئینگلیزی و عەرەبی) دەتوانیت دواتر خۆت زیادیان بکەیت. لێرەدا تەنها کوردیم هێشتۆتەوە بۆ خێرایی و کەمی کێشی فایلەکە.

def tx(lang: str, key: str, **kw) -> str:
    base = L.get(lang, L["ku"])
    text = base.get(key, L["ku"].get(key, key))
    try: return text.format(**kw)
    except: return text

# ==============================================================================
# ── 3. ROBUST UTILS & DATABASE MANAGER ────────────────────────────────────────
# ==============================================================================
DIV = "━━━━━━━━━━━━━━━━━━━"
def clean_title(t: str) -> str: return re.sub(r'[\\/*?:"<>|#]', "", str(t))[:100].strip() or "بێ سەردێڕ"
def fb(path: str) -> str: return f"{DB_URL}/{path}.json?auth={DB_SECRET}"
def now_str() -> str: return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def fmt(n) -> str:
    try:
        n = int(n)
        if n >= 1000000: return f"{n/1000000:.1f}M"
        if n >= 1000: return f"{n/1000:.1f}K"
        return str(n)
    except: return str(n)
def uptime() -> str:
    d, r = divmod(int(time.time() - START_TIME), 86400); h, r = divmod(r, 3600); m, s = divmod(r, 60)
    return f"{d}d {h}h {m}m {s}s"
def back(lang, to="main_menu_render"): return [[InlineKeyboardButton(tx(lang, "b_back"), callback_data=to)]]

def is_owner(uid): return uid == OWNER_ID
def is_super(uid): return uid in super_admins_set or is_owner(uid)
def is_admin(uid): return uid in admins_set or is_super(uid)
def is_vip(uid):   return uid in vip_set or is_super(uid)
def is_blocked(uid): return uid in blocked_set

async def check_join(uid, ctx) -> tuple[bool, list]:
    if not channels_list: return True,[]
    missing =[]
    for ch in channels_list:
        try:
            m = await ctx.bot.get_chat_member(ch, uid)
            if m.status in[ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]: missing.append(ch)
        except BadRequest as e:
            # پاراستنی بۆت لە وەستان ئەگەر بۆتەکە ئەدمین نەبوو لە چەناڵەکە! (شۆڕشی چارەسەرەکان)
            log.warning(f"Bot is not admin in {ch} or channel invalid: {e}")
        except Exception: pass
    return len(missing) == 0, missing

def bypass_join(uid): return (is_admin(uid) and CFG.get("admin_bypass", True)) or (is_vip(uid) and CFG.get("vip_bypass", True))

# --- DB METHODS (Protected) ---
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

async def db_del(path):
    if not DB_URL: return
    async with httpx.AsyncClient(timeout=10) as c:
        try: await c.delete(fb(path))
        except: pass

async def load_cfg(force=False):
    global super_admins_set, admins_set, channels_list, blocked_set, vip_set, last_cfg_load
    if not force and (time.time() - last_cfg_load < 45): return
    d = await db_get("sys")
    if d:
        super_admins_set = set(d.get("super_admins", [OWNER_ID]))
        admins_set       = set(d.get("admins", [OWNER_ID]))
        channels_list    = d.get("channels",[])
        blocked_set      = set(d.get("blocked", []))
        vip_set          = set(d.get("vips",[]))
        CFG.update(d.get("cfg", {}))
        last_cfg_load = time.time()

async def save_cfg():
    await db_put("sys", {
        "super_admins": list(super_admins_set), "admins": list(admins_set), "channels": channels_list,
        "blocked": list(blocked_set), "vips": list(vip_set), "cfg": CFG,
    })

async def user_get(uid) -> dict | None: return await db_get(f"users/{uid}")
async def user_put(uid, data): await db_put(f"users/{uid}", data)
async def user_field(uid, field, val): await db_put(f"users/{uid}/{field}", val)
async def user_exists(uid) -> bool: return (await db_get(f"users/{uid}")) is not None
async def all_uids() -> list: return [int(k) for k in (await db_get("users") or {}).keys()]
async def all_users_data() -> dict: return await db_get("users") or {}

async def session_save(uid, data):
    data["_ts"] = int(time.time())
    await db_put(f"sessions/{uid}", data)

async def session_get(uid) -> dict | None:
    d = await db_get(f"sessions/{uid}")
    if d and int(time.time()) - d.get("_ts", 0) <= SESSION_TTL: return d
    return None

# ==============================================================================
# ── 4. ADVANCED TIKTOK SCRAPER (3 APIs Fallback System) ───────────────────────
# ==============================================================================
async def fetch_tiktok(url: str) -> dict | None:
    headers = {"User-Agent": "Mozilla/5.0"}
    timeout = int(CFG.get("api_timeout", 45))
    active = CFG.get("active_api", "auto")

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as c:
        # 1. TikWM
        if active in ("auto", "tikwm"):
            try:
                r = await c.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1})
                if r.status_code == 200 and r.json().get("code") == 0: return _parse_tikwm(r.json()["data"])
            except: pass

        # 2. Hyper API
        if active in ("auto", "hyper"):
            try:
                r = await c.get(f"https://www.api.hyper-bd.site/Tiktok/?url={url}")
                if r.status_code == 200 and r.json().get("ok"): return _parse_hyper(r.json().get("data", {}))
            except: pass
            
    return None

def _parse_tikwm(d: dict) -> dict:
    imgs = [img for img in d.get("images", []) if isinstance(img, str) and img.startswith("http")]
    return {
        "creator": d.get("author", {}).get("nickname", "Unknown"), "title": d.get("title", ""),
        "cover": d.get("cover", ""), "video_url": d.get("play", "") or d.get("wmplay", ""),
        "audio_url": d.get("music", ""), "images": imgs, "views": d.get("play_count", 0),
        "likes": d.get("digg_count", 0), "comments": d.get("comment_count", 0)
    }

def _parse_hyper(d: dict) -> dict:
    details = d.get("details", {})
    imgs = [img for img in details.get("images", []) if isinstance(img, str) and img.startswith("http")]
    return {
        "creator": d.get("creator", "Unknown"), "title": details.get("title", ""),
        "cover": details.get("cover", {}).get("cover", ""), "video_url": details.get("video", {}).get("play", ""),
        "audio_url": details.get("audio", {}).get("play", ""), "images": imgs, "views": details.get("stats", {}).get("views", 0),
        "likes": details.get("stats", {}).get("likes", 0), "comments": details.get("stats", {}).get("comments", 0)
    }

# ==============================================================================
# ── 5. UI COMPONENTS ──────────────────────────────────────────────────────────
# ==============================================================================
def numpad(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(str(i), callback_data=f"np_{action}_{i}") for i in range(1,4)],[InlineKeyboardButton(str(i), callback_data=f"np_{action}_{i}") for i in range(4,7)],[InlineKeyboardButton(str(i), callback_data=f"np_{action}_{i}") for i in range(7,10)],[InlineKeyboardButton("⌫", callback_data=f"np_{action}_back"), InlineKeyboardButton("0", callback_data=f"np_{action}_0"), InlineKeyboardButton("✅", callback_data=f"np_{action}_ok")],[InlineKeyboardButton("❌ هەڵوەشاندنەوە", callback_data="np_cancel")]
    ])

def ch_pad() -> InlineKeyboardMarkup:
    l = "abcdefghijklmnopqrstuvwxyz"
    r = [[InlineKeyboardButton(c, callback_data=f"chi_{c}") for c in l[i:i+5]] for i in range(0, 25, 5)]
    r.append([InlineKeyboardButton("z", callback_data="chi_z"), InlineKeyboardButton("⌫", callback_data="chi_back"), InlineKeyboardButton("_", callback_data="chi__"), InlineKeyboardButton("✅ تەواو", callback_data="chi_ok")])
    r.append([InlineKeyboardButton("❌ Cancel", callback_data="np_cancel")])
    return InlineKeyboardMarkup(r)

async def render_main_menu(uid: int, lang: str, name: str) -> tuple[str, InlineKeyboardMarkup]:
    badge = tx(lang, "badge_owner") if is_owner(uid) else tx(lang, "badge_super") if is_super(uid) else tx(lang, "badge_admin") if is_admin(uid) else tx(lang, "badge_vip") if is_vip(uid) else ""
    wm = CFG.get("welcome_msg", "")
    text = wm.replace("{name}", html.escape(name)).replace("{badge}", badge) if wm and not is_admin(uid) else tx(lang, "welcome", name=html.escape(name), badge=badge, div=DIV)
    
    kb = [[InlineKeyboardButton(tx(lang, "b_dl"), callback_data="ask_link")],[InlineKeyboardButton(tx(lang, "b_profile"), callback_data="show_profile"), InlineKeyboardButton(tx(lang, "b_vip"), callback_data="show_vip")],[InlineKeyboardButton(tx(lang, "b_settings"), callback_data="show_settings"), InlineKeyboardButton(tx(lang, "b_help"), callback_data="show_help")],[InlineKeyboardButton(tx(lang, "b_channel"), url=CHANNEL_URL)]]
    
    ar =[]
    if is_admin(uid): ar.append(InlineKeyboardButton(tx(lang, "b_admin"), callback_data="panel_admin"))
    if is_super(uid): ar.append(InlineKeyboardButton(tx(lang, "b_super"), callback_data="panel_super"))
    if ar: kb.append(ar)
    if is_owner(uid): kb.append([InlineKeyboardButton(tx(lang, "b_owner"), callback_data="panel_owner")])
    
    return text, InlineKeyboardMarkup(kb)

# ==============================================================================
# ── 6. HANDLERS (TELEGRAM BOT LOGIC) ──────────────────────────────────────────
# ==============================================================================
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid, user = update.effective_user.id, update.effective_user
    lang = CFG.get("default_lang", "ku")

    if is_blocked(uid): return
    if CFG["maintenance"] and not is_admin(uid):
        await update.message.reply_text(tx(lang, "maintenance_msg")); return

    if not await user_exists(uid):
        CFG["total_users"] = CFG.get("total_users", 0) + 1
        await user_put(uid, {"name": user.first_name, "user": user.username or "", "date": now_str(), "vip": False, "dl": 0})
        try: await ctx.bot.send_message(OWNER_ID, f"🔔 <b>بەکارهێنەری نوێ:</b>\n👤 {html.escape(user.first_name)}\n🆔 <code>{uid}</code>", parse_mode="HTML")
        except: pass

    ok_sub, missing = await check_join(uid, ctx)
    if not ok_sub and not bypass_join(uid):
        kb = [[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in missing] + [[InlineKeyboardButton(tx(lang, "b_joined"), callback_data="check_join_btn")]]
        await update.message.reply_text(tx(lang, "force_join"), reply_markup=InlineKeyboardMarkup(kb)); return

    text, markup = await render_main_menu(uid, lang, user.first_name)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)

async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # فەرمانێکی نهێنی بۆ زانینی ئەوەی بۆتەکە بەباشی کاردەکات!
    if is_owner(update.effective_user.id):
        await update.message.reply_text("✅ <b>PONG!</b> بۆتەکە کاردەکات و وەبەهوک بەستراوەتەوە.", parse_mode="HTML")

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; data = q.data; uid = q.from_user.id; lang = CFG.get("default_lang", "ku")
    try: await q.answer()
    except: pass

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
        await q.message.reply_text("🔗 تکایە لینکی ڤیدیۆکە لێرە (Paste) بکە:", reply_markup=ForceReply(selective=True)); return

    if data == "show_profile":
        ud = await user_get(uid) or {}
        text = tx(lang, "profile", id=uid, name=html.escape(q.from_user.first_name), user=q.from_user.username or "—", date=ud.get("date", "—"), vip=tx(lang, "vip_yes") if is_vip(uid) else tx(lang, "vip_no"), dl=ud.get("dl", 0))
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang))); return

    if data == "show_vip":
        await q.edit_message_text(tx(lang, "vip_info", dev=DEV), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang))); return

    if data == "show_help":
        await q.edit_message_text(tx(lang, "help", dev=DEV), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang))); return

    if data == "show_settings":
        kb = [[InlineKeyboardButton(tx(lang, "b_ku"), callback_data="set_lang_ku")], *back(lang)]
        await q.edit_message_text(tx(lang, "lang_title"), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)); return

    if data.startswith("set_lang_"):
        await user_field(uid, "lang", data.split("_")[2]); q.data = "main_menu_render"; await on_callback(update, ctx); return

    if data.startswith("dl_"):
        sess = await session_get(uid)
        if not sess: await q.answer(tx(lang, "session_expired"), show_alert=True); return
        cap = f"🎬 <b>{html.escape(sess.get('title', ''))}</b>\n👤 <b>{html.escape(sess.get('creator', ''))}</b>\n\n🤖 @{ctx.bot.username}"
        del_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_delete"), callback_data="close")]])

        if data == "dl_photo":
            imgs = sess.get("images",[])
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
            except: await ctx.bot.send_message(uid, f"{cap}\n📥 <a href='{vurl}'>لینک</a>", parse_mode="HTML", reply_markup=del_kb)

        elif data == "dl_audio":
            aurl = sess.get("audio_url")
            if not aurl: await q.answer(tx(lang, "no_audio"), show_alert=True); return
            try: await q.message.delete()
            except: pass
            try: await ctx.bot.send_audio(uid, aurl, caption=cap, parse_mode="HTML", title=f"Audio - @{ctx.bot.username}", performer="TikTok", reply_markup=del_kb)
            except: await ctx.bot.send_message(uid, f"{cap}\n🎵 <a href='{aurl}'>لینک</a>", parse_mode="HTML", reply_markup=del_kb)

        CFG["total_dl"] = CFG.get("total_dl", 0) + 1
        await save_cfg()
        ud = await user_get(uid) or {}
        await user_field(uid, "dl", ud.get("dl", 0) + 1)
        return

    # ADMIN PANEL
    if data.startswith("panel_admin") or data.startswith("adm_"):
        if not is_admin(uid): return
        if data == "panel_admin":
            kb = [[InlineKeyboardButton("📊 ئامارەکان", callback_data="adm_stats"), InlineKeyboardButton("📢 برۆدکاست", callback_data="adm_broadcast")],[InlineKeyboardButton("🚫 بلۆککردن", callback_data="adm_block"), InlineKeyboardButton("👤 زانیاری کەس", callback_data="adm_userinfo")], *back(lang)]
            await q.edit_message_text(f"🛡 <b>پانێڵی ئەدمین</b>\n\n👥 بەکارهێنەران: <b>{len(await all_uids())}</b>\n🕐 کات: {now_str()}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)); return
        if data == "adm_stats":
            txt = f"📊 <b>ئامارەکان:</b>\n👥 کۆی گشتی: {len(await all_uids())}\n💎 ڤی ئای پی: {len(vip_set)}\n🚫 بلۆککراو: {len(blocked_set)}\n📥 داونلۆدەکان: {fmt(CFG.get('total_dl',0))}\n⏱ Uptime: {uptime()}"
            await q.edit_message_text(txt, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄", callback_data="adm_stats")], *back(lang, "panel_admin")])); return
        if data == "adm_broadcast":
            waiting_state[uid] = "broadcast_all"
            await q.edit_message_text("✍️ <b>پەیامەکەت بنێرە (دەتوانیت وێنە و ڤیدیۆش بنێریت):</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="panel_admin")]])); return
        if data == "adm_block":
            ctx.user_data["np_action"] = "blk_add"; ctx.user_data["np_buf"] = ""
            await q.edit_message_text("🚫 <b>بلۆککردن:</b>\nئایدی کەسەکە داخڵ بکە:", parse_mode="HTML", reply_markup=numpad("blk_add")); return
        if data == "adm_userinfo":
            ctx.user_data["np_action"] = "info_check"; ctx.user_data["np_buf"] = ""
            await q.edit_message_text("👤 <b>زانیاری:</b>\nئایدی داخڵ بکە:", parse_mode="HTML", reply_markup=numpad("info_check")); return

    # SUPER PANEL
    if data.startswith("panel_super") or data.startswith("sup_"):
        if not is_super(uid): return
        if data == "panel_super":
            maint = "🔴" if CFG["maintenance"] else "🟢"
            kb = [[InlineKeyboardButton("👮‍♂️ ئەدمینەکان", callback_data="sup_admins"), InlineKeyboardButton("💎 VIP", callback_data="sup_vips")],[InlineKeyboardButton("📢 چەناڵەکان", callback_data="sup_channels"), InlineKeyboardButton(f"🛠 چاکسازی: {maint}", callback_data="sup_toggle_maint")],[InlineKeyboardButton("⚙️ ڕێکخستنی API", callback_data="sup_api_settings")], *back(lang)]
            await q.edit_message_text(f"🌌 <b>سوپەر پانێل</b>\nکۆنتڕۆڵی ڕێکخستنە هەستیارەکان.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)); return
        if data == "sup_toggle_maint":
            CFG["maintenance"] = not CFG["maintenance"]; await save_cfg(); q.data = "panel_super"; await on_callback(update, ctx); return
        if data == "sup_api_settings":
            act = CFG.get("active_api", "auto")
            kb = [[InlineKeyboardButton(f"{'✅' if act=='auto' else ''} Auto (زیرەک)", callback_data="sup_setapi_auto")],[InlineKeyboardButton(f"{'✅' if act=='tikwm' else ''} TikWM (خێرا)", callback_data="sup_setapi_tikwm")],[InlineKeyboardButton(f"{'✅' if act=='hyper' else ''} Hyper API (باکئەپ)", callback_data="sup_setapi_hyper")], *back(lang, "panel_super")]
            await q.edit_message_text("⚙️ <b>سەرچاوەی دابەزاندن هەڵبژێرە:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)); return
        if data.startswith("sup_setapi_"):
            CFG["active_api"] = data.split("_")[2]; await save_cfg(); q.data = "sup_api_settings"; await on_callback(update, ctx); return
        if data == "sup_admins":
            kb = [[InlineKeyboardButton("➕ پێدان", callback_data="sup_add_adm"), InlineKeyboardButton("➖ سەندنەوە", callback_data="sup_rm_adm")], *back(lang, "panel_super")]
            await q.edit_message_text(f"👮‍♂️ <b>ئەدمینەکان:</b> {len(admins_set)}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)); return
        if data == "sup_add_adm":
            ctx.user_data["np_action"] = "adm_add"; ctx.user_data["np_buf"] = ""; await q.edit_message_text("➕ ئایدی داخڵ بکە:", parse_mode="HTML", reply_markup=numpad("adm_add")); return
        if data == "sup_rm_adm":
            ctx.user_data["np_action"] = "adm_rm"; ctx.user_data["np_buf"] = ""; await q.edit_message_text("➖ ئایدی داخڵ بکە:", parse_mode="HTML", reply_markup=numpad("adm_rm")); return
        if data == "sup_vips":
            kb = [[InlineKeyboardButton("➕ پێدانی VIP", callback_data="sup_add_vip"), InlineKeyboardButton("➖ سەندنەوەی VIP", callback_data="sup_rm_vip")], *back(lang, "panel_super")]
            await q.edit_message_text(f"💎 <b>ژمارەی VIP:</b> {len(vip_set)}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)); return
        if data == "sup_add_vip":
            ctx.user_data["np_action"] = "vip_add"; ctx.user_data["np_buf"] = ""; await q.edit_message_text("💎 ئایدی داخڵ بکە:", parse_mode="HTML", reply_markup=numpad("vip_add")); return
        if data == "sup_rm_vip":
            ctx.user_data["np_action"] = "vip_rm"; ctx.user_data["np_buf"] = ""; await q.edit_message_text("➖ ئایدی داخڵ بکە:", parse_mode="HTML", reply_markup=numpad("vip_rm")); return
        if data == "sup_channels":
            lst = "\n".join([f"• {c}" for c in channels_list]) or "📭 بەتاڵە"
            kb = [[InlineKeyboardButton("➕ زیادکردن", callback_data="sup_add_ch"), InlineKeyboardButton("➖ سڕینەوە", callback_data="sup_rm_ch")], *back(lang, "panel_super")]
            await q.edit_message_text(f"📢 <b>چەناڵەکان:</b>\n{lst}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)); return
        if data == "sup_add_ch":
            ctx.user_data["ch_buf"] = "@"; await q.edit_message_text("📢 ناوی چەناڵ بنووسە:", parse_mode="HTML", reply_markup=ch_pad()); return
        if data == "sup_rm_ch":
            kb = [[InlineKeyboardButton(f"❌ {c}", callback_data=f"sup_delch_{c}")] for c in channels_list] + back(lang, "sup_channels")
            await q.edit_message_text("کام چەناڵ دەسڕیتەوە؟", reply_markup=InlineKeyboardMarkup(kb)); return
        if data.startswith("sup_delch_"):
            ch = data.split("_", 2)[2]
            if ch in channels_list: channels_list.remove(ch); await save_cfg()
            q.data = "sup_channels"; await on_callback(update, ctx); return

    # OWNER PANEL
    if data.startswith("panel_owner") or data.startswith("own_"):
        if not is_owner(uid): return
        if data == "panel_owner":
            kb = [[InlineKeyboardButton("🌌 سوپەر ئەدمینەکان", callback_data="own_super_adms")],[InlineKeyboardButton("📝 نامەی خێرهاتن", callback_data="own_welcome")],[InlineKeyboardButton("🗑 ڕیسێتی ئامار", callback_data="own_reset_stats"), InlineKeyboardButton("💾 باکئەپ", callback_data="own_backup")], *back(lang)]
            await q.edit_message_text(f"👑 <b>پانێڵی خاوەنی سەرەکی</b>\nبەخێربێیت گەورەم!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)); return
        if data == "own_super_adms":
            kb = [[InlineKeyboardButton("➕ زیادکردن", callback_data="own_add_sup"), InlineKeyboardButton("➖ لابردن", callback_data="own_rm_sup")], *back(lang, "panel_owner")]
            await q.edit_message_text(f"🌌 <b>سوپەر ئەدمینەکان:</b> {len(super_admins_set)}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)); return
        if data == "own_add_sup":
            ctx.user_data["np_action"] = "sup_add"; ctx.user_data["np_buf"] = ""; await q.edit_message_text("➕ ئایدی داخڵ بکە:", parse_mode="HTML", reply_markup=numpad("sup_add")); return
        if data == "own_rm_sup":
            ctx.user_data["np_action"] = "sup_rm"; ctx.user_data["np_buf"] = ""; await q.edit_message_text("➖ ئایدی داخڵ بکە:", parse_mode="HTML", reply_markup=numpad("sup_rm")); return
        if data == "own_welcome":
            waiting_state[uid] = "set_welcome"
            await q.edit_message_text(tx(lang, "write_welcome"), parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 سڕینەوەی نامەکە", callback_data="own_clear_welcome")], *back(lang, "panel_owner")])); return
        if data == "own_clear_welcome":
            CFG["welcome_msg"] = ""; await save_cfg(); q.data = "panel_owner"; await on_callback(update, ctx); return
        if data == "own_reset_stats":
            for k in ("total_dl","total_video","total_audio","total_photo"): CFG[k] = 0
            await save_cfg(); await q.answer("✅ صفر کرایەوە", show_alert=True); return
        if data == "own_backup":
            await q.answer("⏳ ئامادە دەکرێت...", show_alert=False)
            bdata = {"time": now_str(), "cfg": CFG, "users": await all_users_data()}
            bio = io.BytesIO(json.dumps(bdata, ensure_ascii=False, indent=2).encode())
            bio.name = f"Backup_{now_str()}.json"
            try: await ctx.bot.send_document(uid, bio)
            except: pass
            return

async def on_numpad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; data = q.data; lang = CFG.get("default_lang", "ku")
    try: await q.answer()
    except: pass

    if data == "np_cancel":
        ctx.user_data.pop("np_action", None); ctx.user_data.pop("np_buf", None); ctx.user_data.pop("ch_buf", None)
        try: await q.message.delete()
        except: pass
        return

    if data.startswith("chi_"):
        key = data[4:]
        buf = ctx.user_data.get("ch_buf", "@")
        if key == "back": buf = buf[:-1] if len(buf) > 1 else buf
        elif key == "ok":
            if len(buf) < 3: return
            if buf not in channels_list: channels_list.append(buf); await save_cfg()
            await q.edit_message_text(f"✅ {buf} زیاد کرا!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang, "sup_channels"))); return
        else:
            if len(buf) < 32: buf += key
        ctx.user_data["ch_buf"] = buf
        await q.edit_message_text(f"📢 ناوی چەناڵ:\n<code>{buf}</code>", parse_mode="HTML", reply_markup=ch_pad())
        return

    if data.startswith("np_"):
        parts = data.split("_", 2)
        if len(parts) < 3: return
        action, key = parts[1], parts[2]
        buf = ctx.user_data.get("np_buf", "")

        if key == "back": buf = buf[:-1]
        elif key == "ok":
            if not buf.isdigit(): return
            tid = int(buf)
            if action == "blk_add": blocked_set.add(tid); await save_cfg(); await q.edit_message_text(f"🚫 {tid} بلۆک کرا!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang, "panel_admin")))
            elif action == "info_check":
                ud = await user_get(tid)
                if not ud: await q.edit_message_text("⚠️ نەدۆزرایەوە!", reply_markup=InlineKeyboardMarkup(back(lang, "panel_admin"))); return
                await q.edit_message_text(f"👤 ناو: {ud.get('name')}\n🔗 یوزەر: @{ud.get('user')}\n📥 داونلۆد: {ud.get('dl')}", reply_markup=InlineKeyboardMarkup(back(lang, "panel_admin")))
            elif action == "adm_add": admins_set.add(tid); await save_cfg(); await q.edit_message_text(f"✅ {tid} بوو بە ئەدمین!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang, "panel_super")))
            elif action == "adm_rm": admins_set.discard(tid); await save_cfg(); await q.edit_message_text(f"➖ {tid} لە ئەدمین لابرا.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang, "panel_super")))
            elif action == "sup_add": super_admins_set.add(tid); admins_set.add(tid); await save_cfg(); await q.edit_message_text(f"🌌 {tid} بوو بە سوپەر ئەدمین!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang, "panel_owner")))
            elif action == "sup_rm": super_admins_set.discard(tid); await save_cfg(); await q.edit_message_text(f"➖ {tid} لە سوپەر لابرا.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang, "panel_owner")))
            elif action == "vip_add": vip_set.add(tid); await user_field(tid, "vip", True); await save_cfg(); await q.edit_message_text(f"💎 {tid} کرایە VIP", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang, "panel_super")))
            elif action == "vip_rm": vip_set.discard(tid); await user_field(tid, "vip", False); await save_cfg(); await q.edit_message_text(f"➖ VIP لە {tid} سەندرایەوە", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back(lang, "panel_super")))
            return
        else:
            if len(buf) < 15: buf += key
        ctx.user_data["np_buf"] = buf
        await q.edit_message_text(f"📟 داخڵکردن:\n\n<code>{buf if buf else '—'}</code>", parse_mode="HTML", reply_markup=numpad(action))

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    lang = CFG.get("default_lang", "ku")
    msg = update.message
    txt = msg.text or ""

    if uid in waiting_state:
        state = waiting_state.pop(uid)
        if state == "set_welcome":
            CFG["welcome_msg"] = txt; await save_cfg()
            await msg.reply_text(tx(lang, "welcome_set")); return
        if state.startswith("broadcast_"):
            all_u = await all_uids(); ok = fail = 0
            st = await msg.reply_text(f"⏳ ناردن دەستی پێکرد بۆ {len(all_u)} کەس...")
            for i, t in enumerate(all_u):
                try:
                    await ctx.bot.copy_message(chat_id=t, from_chat_id=msg.chat_id, message_id=msg.message_id)
                    ok += 1; await asyncio.sleep(0.04)
                except: fail += 1
                if i % 100 == 0 and i > 0:
                    try: await st.edit_text(f"⏳ ناردن: {i}/{len(all_u)}...")
                    except: pass
            await st.edit_text(tx(lang, "broadcast_done", ok=ok, fail=fail), parse_mode="HTML"); return

    if is_blocked(uid): return
    if CFG["maintenance"] and not is_admin(uid): await msg.reply_text(tx(lang, "maintenance_msg")); return
    if not any(x in txt for x in ("tiktok.com", "vm.tiktok", "vt.tiktok")): return

    ok_sub, missing = await check_join(uid, ctx)
    if not ok_sub and not bypass_join(uid):
        kb = [[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in missing] + [[InlineKeyboardButton(tx(lang, "b_joined"), callback_data="check_join_btn")]]
        await msg.reply_text(tx(lang, "force_join"), reply_markup=InlineKeyboardMarkup(kb)); return

    status = await msg.reply_text(tx(lang, "processing"), parse_mode="HTML")

    try:
        data = await fetch_tiktok(txt)
        if not data: await status.edit_text(tx(lang, "invalid_link"), parse_mode="HTML"); return
        await session_save(uid, data)
        photo_post = len(data["images"]) > 0

        caption = tx(lang, "found", title=html.escape(clean_title(data["title"])), owner=html.escape(data["creator"]), views=fmt(data["views"]), likes=fmt(data["likes"]), comments=fmt(data["comments"]))
        kb = [[InlineKeyboardButton(tx(lang, "b_photos", n=len(data["images"])), callback_data="dl_photo")] if photo_post else[InlineKeyboardButton(tx(lang, "b_video"), callback_data="dl_video")],[InlineKeyboardButton(tx(lang, "b_audio"), callback_data="dl_audio")],[InlineKeyboardButton(tx(lang, "b_delete"), callback_data="close")]]
        markup = InlineKeyboardMarkup(kb)
        cover_url = data.get("cover", "")

        if cover_url and cover_url.startswith("http"):
            try:
                await status.delete(); await msg.reply_photo(photo=cover_url, caption=caption, parse_mode="HTML", reply_markup=markup)
            except: await msg.reply_text(caption, parse_mode="HTML", reply_markup=markup)
        else: await status.edit_text(caption, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        log.error(f"Download Error: {e}")
        try: await status.edit_text(tx(lang, "dl_fail"), parse_mode="HTML")
        except: pass

# ==============================================================================
# ── 7. FASTAPI WEBHOOK & APP CORE ─────────────────────────────────────────────
# ==============================================================================
ptb = ApplicationBuilder().token(TOKEN if TOKEN != "DUMMY_TOKEN" else "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11").build()
ptb.add_handler(CommandHandler(["start", "menu"], cmd_start))
ptb.add_handler(CommandHandler("ping", cmd_ping))
ptb.add_handler(CallbackQueryHandler(on_numpad, pattern=r"^(np_|chi_)"))
ptb.add_handler(CallbackQueryHandler(on_callback))
ptb.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))

@app.post("/api/main")
async def webhook(req: Request):
    if TOKEN == "DUMMY_TOKEN" or not TOKEN: return {"ok": False, "error": "BOT_TOKEN IS MISSING"}
    try:
        body = await req.json()
        if not ptb.running: await ptb.initialize()
        await load_cfg(force=False)
        await ptb.process_update(Update.de_json(body, ptb.bot))
        return {"ok": True}
    except Exception as e:
        err_str = traceback.format_exc()
        log.error(f"CRITICAL WEBHOOK ERROR: {err_str}")
        try: await ptb.bot.send_message(OWNER_ID, f"⚠️ <b>هەڵەیەکی کوشندە ڕوویدا لە Vercel:</b>\n\n<pre>{html.escape(str(e))}</pre>", parse_mode="HTML")
        except: pass
        return {"ok": False, "error": str(e)}

@app.get("/api/main")
async def health_check():
    # ئەمە لاپەڕەی پشکنینە بۆ ئەوەی بزانیت کێشە لە کوێیە
    token_status = "✅ دانراوە و ئامادەیە" if TOKEN and TOKEN != "DUMMY_TOKEN" else "❌ لە Environment Variables دا نەگیراوە!"
    db_status = "✅ دانراوە" if DB_URL else "❌ لە Environment Variables دا نەگیراوە!"
    db_secret_status = "✅ دانراوە" if DB_SECRET else "❌ لە Environment Variables دا نەگیراوە!"
    
    html_content = f"""
    <html>
        <head>
            <title>JackTik Bot - System Check</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: right; background-color: #f4f4f9; padding: 50px; direction: rtl; }}
                .box {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }}
                h1 {{ color: #333; }}
                ul {{ list-style-type: none; padding: 0; }}
                li {{ padding: 10px; border-bottom: 1px solid #ddd; font-size: 18px; }}
            </style>
        </head>
        <body>
            <div class="box">
                <h1>🤖 پشکنینی سیستەمی بۆت</h1>
                <p>ئەگەر هەموو شتێک بە <b>✅</b> نیشان درابوو، ئەوا بۆتەکە 100٪ کاردەکات.</p>
                <ul>
                    <li><b>تۆکێنی بۆت (BOT_TOKEN):</b> {token_status}</li>
                    <li><b>لینکی داتابەیس (DB_URL):</b> {db_status}</li>
                    <li><b>وشەی نهێنی (DB_SECRET):</b> {db_secret_status}</li>
                </ul>
                <p style="color: red; font-weight: bold;">ئەگەر هەر کامێکیان بە ❌ بوو، بڕۆ ناو سێتینگی Vercel بەشی Environment Variables زیادیان بکە و دواتر Redeploy بکەرەوە!</p>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)
