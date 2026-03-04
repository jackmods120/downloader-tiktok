# ==============================================================================
# ==                                                                          ==
# ==           TIKTOK DOWNLOADER BOT - ULTRA EDITION v8.0                    ==
# ==           Dev: @j4ck_721s  |  Clean Build From Scratch                  ==
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
OWNER_ID           = 5977475208
DEV                = "@j4ck_721s"
CHANNEL_URL        = "https://t.me/jack_721_mod"

API_PRIMARY        = "https://www.api.hyper-bd.site/Tiktok/?url="
API_BACKUP         = "https://www.tikwm.com/api/?url="

START_TIME         = time.time()
SESSION_TTL        = 600   # چرکە

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
app = FastAPI()

# ==============================================================================
# ── GLOBALS ────────────────────────────────────────────────────────────────────
# ==============================================================================
admins_set      : set  = {OWNER_ID}
channels_list   : list = []
blocked_set     : set  = set()
vip_set         : set  = set()
waiting_state   : dict = {}   # uid -> state-string

CFG: dict = {
    "maintenance"     : False,
    "welcome_msg"     : "",
    "default_lang"    : "ku",
    "photo_mode"      : "auto",   # auto | force_photo | force_video
    "max_photos"      : 10,
    "api_timeout"     : 60,
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
# ────────────────────────────────── Kurdish ───────────────────────────────────
"ku": {
    "welcome"        : "👋 <b>سڵاو {name} {badge}</b>\n\n🤖 <b>بۆتی دابەزاندنی تیکتۆک</b>\n📥 ڤیدیۆ، وێنە و گۆرانی دابەزێنە\n\n{div}\n👇 <b>لینکەکە بنێرە:</b>",
    "help"           : "📚 <b>ڕێنمایی بەکارهێنان</b>\n\n1️⃣ لینکی تیکتۆک کۆپی بکە\n2️⃣ لێرە بینێرە\n3️⃣ جۆر هەڵبژێرە و دابەزێنە!\n\n🎥 ڤیدیۆ بێ لۆگۆ\n📸 وێنەکانی Slideshow\n🎵 گۆرانی MP3\n\n💎 VIP — بێ جۆین چەناڵ\n📩 پەیوەندی: {dev}",
    "profile"        : "👤 <b>پرۆفایل</b>\n\n🆔 {id}\n👤 {name}\n🔗 @{user}\n📅 {date}\n💎 VIP: {vip}\n📥 داونلۆد: {dl}",
    "vip_info"       : "💎 <b>بەشی VIP</b>\n\n✅ بێ جۆین چەناڵ\n✅ خێرایی زیاتر\n✅ داونلۆدی بێسنوور\n\n📩 پەیوەندی: {dev}",
    "lang_title"     : "🌍 <b>زمان هەڵبژێرە</b>",
    "force_join"     : "🔒 <b>جۆینی ناچاری</b>\nبۆ بەکارهێنان، تکایە جۆینی ئەم چەناڵانە بکە:",
    "processing"     : "🔍 داونلۆد دەستپێدەکات...",
    "found"          : "✅ <b>دۆزرایەوە!</b>\n\n📝 {title}\n👤 {owner}\n\n👁 {views}   ❤️ {likes}   💬 {comments}",
    "sending_photos" : "📸 وێنەکان دێن...",
    "blocked_msg"    : "⛔ ببورە، تۆ بلۆک کراویت.",
    "maintenance_msg": "🛠 بۆتەکە لە چاکسازیدایە. چاوەڕوان بە!",
    "session_expired": "⚠️ کاتەکەت تەواو بوو، لینکەکە دووبارە بنێرە.",
    "invalid_link"   : "❌ لینکەکە دروست نییە!",
    "dl_fail"        : "❌ هەڵەیەک ڕوویدا. دووبارە هەوڵبدەوە.",
    "no_photo"       : "❌ هیچ وێنەیەک نەدۆزرایەوە!",
    "no_video"       : "❌ ڤیدیۆ نەدۆزرایەوە!",
    "no_audio"       : "❌ گۆرانی نەدۆزرایەوە!",
    "admin_only"     : "⛔ تەنیا ئەدمین!",
    "owner_only"     : "⛔ تەنیا خاوەن!",
    "invalid_id"     : "❌ ئایدی دروست نییە!",
    "done"           : "✅ ئەنجامدرا!",
    "setting_saved"  : "✅ ذەخیرەکرا!",
    "user_not_found" : "⚠️ بەکارهێنەر نەدۆزرایەوە.",
    "broadcast_done" : "📢 برۆدکاست تەواو بوو\n✅ گەیشت: {ok}\n❌ نەگەیشت: {fail}",
    "no_users"       : "📭 هیچ بەکارهێنەرێک نییە.",
    "backup_caption" : "💾 بەکئەپ — {time}",
    "welcome_set"    : "✅ نامەی خۆشامەدێ ذەخیرەکرا.",
    "msg_sent"       : "✅ نامەکە نێردرا.",
    "write_msg"      : "✍️ نامەکەت بنووسە بۆ بەکارهێنەر {id}:",
    "write_welcome"  : "✍️ نامەی خۆشامەدێ بنووسە (HTML پشتگیری دەکرێت):\n{id} = ناو، {badge} = ئامانج",
    "confirm_del"    : "⚠️ دڵنیایت؟",
    "stats_reset"    : "✅ ئامارەکان ڕیسێت کران.",
    "users_deleted"  : "✅ هەموو بەکارهێنەرەکان سڕانەوە.",
    # Buttons
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
    "b_confirm"     : "✅ دڵنیام",
    "b_cancel"      : "❌ هەڵوەشاندنەوە",
    "b_joined"      : "✅ جۆینم کرد",
    "b_video"       : "🎥 ڤیدیۆ (بێ لۆگۆ)",
    "b_photos"      : "📸 وێنەکان ({n})",
    "b_audio"       : "🎵 گۆرانی (MP3)",
    "b_ku"          : "🔴🔆🟢 کوردی",
    "b_en"          : "🇺🇸 English",
    "b_ar"          : "🇸🇦 العربية",
    "badge_owner"   : "👑 خاوەن",
    "badge_admin"   : "⚡ ئەدمین",
    "badge_vip"     : "💎 VIP",
    "vip_yes"       : "بەڵێ 💎",
    "vip_no"        : "نەخێر",
},
# ────────────────────────────────── English ───────────────────────────────────
"en": {
    "welcome"        : "👋 <b>Hello {name} {badge}</b>\n\n🤖 <b>TikTok Downloader Bot</b>\n📥 Download videos, photos & audio\n\n{div}\n👇 <b>Send a link:</b>",
    "help"           : "📚 <b>How to Use</b>\n\n1️⃣ Copy TikTok link\n2️⃣ Send it here\n3️⃣ Choose format & download!\n\n🎥 Video without watermark\n📸 Slideshow photos\n🎵 Audio MP3\n\n💎 VIP — no channel join required\n📩 Contact: {dev}",
    "profile"        : "👤 <b>Profile</b>\n\n🆔 {id}\n👤 {name}\n🔗 @{user}\n📅 {date}\n💎 VIP: {vip}\n📥 Downloads: {dl}",
    "vip_info"       : "💎 <b>VIP Section</b>\n\n✅ No forced join\n✅ Faster downloads\n✅ Unlimited photos\n\n📩 Contact: {dev}",
    "lang_title"     : "🌍 <b>Select Language</b>",
    "force_join"     : "🔒 <b>Forced Join</b>\nTo use the bot, please join these channels:",
    "processing"     : "🔍 Processing...",
    "found"          : "✅ <b>Found!</b>\n\n📝 {title}\n👤 {owner}\n\n👁 {views}   ❤️ {likes}   💬 {comments}",
    "sending_photos" : "📸 Sending photos...",
    "blocked_msg"    : "⛔ Sorry, you are blocked.",
    "maintenance_msg": "🛠 Bot is under maintenance. Please wait!",
    "session_expired": "⚠️ Session expired. Please send the link again.",
    "invalid_link"   : "❌ Invalid link!",
    "dl_fail"        : "❌ An error occurred. Try again.",
    "no_photo"       : "❌ No photos found!",
    "no_video"       : "❌ Video not found!",
    "no_audio"       : "❌ Audio not found!",
    "admin_only"     : "⛔ Admins only!",
    "owner_only"     : "⛔ Owner only!",
    "invalid_id"     : "❌ Invalid ID!",
    "done"           : "✅ Done!",
    "setting_saved"  : "✅ Saved!",
    "user_not_found" : "⚠️ User not found.",
    "broadcast_done" : "📢 Broadcast done\n✅ Sent: {ok}\n❌ Failed: {fail}",
    "no_users"       : "📭 No users found.",
    "backup_caption" : "💾 Backup — {time}",
    "welcome_set"    : "✅ Welcome message saved.",
    "msg_sent"       : "✅ Message sent.",
    "write_msg"      : "✍️ Write your message to user {id}:",
    "write_welcome"  : "✍️ Write welcome message (HTML supported):\n{name} = name, {badge} = badge",
    "confirm_del"    : "⚠️ Are you sure?",
    "stats_reset"    : "✅ Stats reset.",
    "users_deleted"  : "✅ All users deleted.",
    "b_dl"          : "📥 Download",
    "b_profile"     : "👤 Profile",
    "b_vip"         : "💎 VIP",
    "b_settings"    : "⚙️ Settings",
    "b_help"        : "ℹ️ Help",
    "b_channel"     : "📢 Channel",
    "b_admin"       : "👑 Admin Panel",
    "b_owner"       : "🔱 Owner Panel",
    "b_back"        : "🔙 Back",
    "b_delete"      : "🗑 Delete",
    "b_refresh"     : "🔄 Refresh",
    "b_confirm"     : "✅ Confirm",
    "b_cancel"      : "❌ Cancel",
    "b_joined"      : "✅ I Joined",
    "b_video"       : "🎥 Video (No Watermark)",
    "b_photos"      : "📸 Photos ({n})",
    "b_audio"       : "🎵 Audio (MP3)",
    "b_ku"          : "🔴🔆🟢 کوردی",
    "b_en"          : "🇺🇸 English",
    "b_ar"          : "🇸🇦 العربية",
    "badge_owner"   : "👑 Owner",
    "badge_admin"   : "⚡ Admin",
    "badge_vip"     : "💎 VIP",
    "vip_yes"       : "Yes 💎",
    "vip_no"        : "No",
},
# ────────────────────────────────── Arabic ────────────────────────────────────
"ar": {
    "welcome"        : "👋 <b>أهلاً {name} {badge}</b>\n\n🤖 <b>بوت تحميل تيك توك</b>\n📥 حمّل فيديوهات وصوراً وصوتاً\n\n{div}\n👇 <b>أرسل الرابط:</b>",
    "help"           : "📚 <b>طريقة الاستخدام</b>\n\n1️⃣ انسخ رابط تيك توك\n2️⃣ أرسله هنا\n3️⃣ اختر الصيغة وحمّل!\n\n🎥 فيديو بدون علامة مائية\n📸 صور الشرائح\n🎵 صوت MP3\n\n💎 VIP — بدون اشتراك قنوات\n📩 تواصل: {dev}",
    "profile"        : "👤 <b>الملف الشخصي</b>\n\n🆔 {id}\n👤 {name}\n🔗 @{user}\n📅 {date}\n💎 VIP: {vip}\n📥 التنزيلات: {dl}",
    "vip_info"       : "💎 <b>قسم VIP</b>\n\n✅ بدون اشتراك إجباري\n✅ سرعة أكبر\n✅ تنزيل غير محدود\n\n📩 تواصل: {dev}",
    "lang_title"     : "🌍 <b>اختر اللغة</b>",
    "force_join"     : "🔒 <b>اشتراك إجباري</b>\nيرجى الانضمام لهذه القنوات:",
    "processing"     : "🔍 جاري المعالجة...",
    "found"          : "✅ <b>تم العثور عليه!</b>\n\n📝 {title}\n👤 {owner}\n\n👁 {views}   ❤️ {likes}   💬 {comments}",
    "sending_photos" : "📸 جاري إرسال الصور...",
    "blocked_msg"    : "⛔ عذراً، تم حظرك.",
    "maintenance_msg": "🛠 البوت في وضع الصيانة. يرجى الانتظار!",
    "session_expired": "⚠️ انتهت الجلسة. أرسل الرابط مجدداً.",
    "invalid_link"   : "❌ الرابط غير صالح!",
    "dl_fail"        : "❌ حدث خطأ. حاول مجدداً.",
    "no_photo"       : "❌ لا توجد صور!",
    "no_video"       : "❌ الفيديو غير موجود!",
    "no_audio"       : "❌ الصوت غير موجود!",
    "admin_only"     : "⛔ للمسؤولين فقط!",
    "owner_only"     : "⛔ للمالك فقط!",
    "invalid_id"     : "❌ معرف غير صالح!",
    "done"           : "✅ تم!",
    "setting_saved"  : "✅ تم الحفظ!",
    "user_not_found" : "⚠️ المستخدم غير موجود.",
    "broadcast_done" : "📢 اكتمل الإرسال\n✅ تم: {ok}\n❌ فشل: {fail}",
    "no_users"       : "📭 لا يوجد مستخدمون.",
    "backup_caption" : "💾 نسخ احتياطي — {time}",
    "welcome_set"    : "✅ تم حفظ رسالة الترحيب.",
    "msg_sent"       : "✅ تم إرسال الرسالة.",
    "write_msg"      : "✍️ اكتب رسالتك للمستخدم {id}:",
    "write_welcome"  : "✍️ اكتب رسالة الترحيب (HTML مدعوم):\n{name} = الاسم، {badge} = الشارة",
    "confirm_del"    : "⚠️ هل أنت متأكد؟",
    "stats_reset"    : "✅ تمت إعادة تعيين الإحصائيات.",
    "users_deleted"  : "✅ تم حذف جميع المستخدمين.",
    "b_dl"          : "📥 تحميل",
    "b_profile"     : "👤 الملف",
    "b_vip"         : "💎 VIP",
    "b_settings"    : "⚙️ الإعدادات",
    "b_help"        : "ℹ️ المساعدة",
    "b_channel"     : "📢 القناة",
    "b_admin"       : "👑 لوحة الأدمن",
    "b_owner"       : "🔱 لوحة المالك",
    "b_back"        : "🔙 رجوع",
    "b_delete"      : "🗑 حذف",
    "b_refresh"     : "🔄 تحديث",
    "b_confirm"     : "✅ تأكيد",
    "b_cancel"      : "❌ إلغاء",
    "b_joined"      : "✅ انضممت",
    "b_video"       : "🎥 فيديو (بدون علامة)",
    "b_photos"      : "📸 صور ({n})",
    "b_audio"       : "🎵 صوت (MP3)",
    "b_ku"          : "🔴🔆🟢 کوردی",
    "b_en"          : "🇺🇸 English",
    "b_ar"          : "🇸🇦 العربية",
    "badge_owner"   : "👑 المالك",
    "badge_admin"   : "⚡ مسؤول",
    "badge_vip"     : "💎 VIP",
    "vip_yes"       : "نعم 💎",
    "vip_no"        : "لا",
},
}

def tx(lang: str, key: str, **kw) -> str:
    base = L.get(lang, L["ku"])
    text = base.get(key, L["ku"].get(key, key))
    try:
        return text.format(**kw)
    except:
        return text

# ==============================================================================
# ── HELPERS ────────────────────────────────────────────────────────────────────
# ==============================================================================
DIV = "━━━━━━━━━━━━━━━━━━━"

def rand_id(n=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

def clean_title(t: str) -> str:
    if not t: return "TikTok"
    return re.sub(r'[\\/*?:"<>|#]', "", t)[:80].strip()

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
    missing = []
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
# ── DATABASE ───────────────────────────────────────────────────────────────────
# ==============================================================================
async def db_get(path):
    async with httpx.AsyncClient(timeout=15) as c:
        try:
            r = await c.get(fb(path))
            if r.status_code == 200: return r.json()
        except: pass
    return None

async def db_put(path, data):
    async with httpx.AsyncClient(timeout=15) as c:
        try: await c.put(fb(path), json=data)
        except: pass

async def db_del(path):
    async with httpx.AsyncClient(timeout=15) as c:
        try: await c.delete(fb(path))
        except: pass

async def load_cfg():
    global admins_set, channels_list, blocked_set, vip_set
    d = await db_get("sys")
    if d:
        admins_set    = set(d.get("admins",   [OWNER_ID]))
        channels_list = d.get("channels", [])
        blocked_set   = set(d.get("blocked",  []))
        vip_set       = set(d.get("vips",     []))
        CFG.update(d.get("cfg", {}))
        log.info("✅ Config loaded")

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

async def all_users() -> dict:
    return await db_get("users") or {}

async def users_del():
    await db_del("users")

async def session_save(uid, data):
    data["_ts"] = int(time.time())
    await db_put(f"sessions/{uid}", data)

async def session_get(uid) -> dict | None:
    d = await db_get(f"sessions/{uid}")
    if d and int(time.time()) - d.get("_ts", 0) <= SESSION_TTL:
        return d
    return None

async def get_lang(uid) -> str:
    v = await db_get(f"users/{uid}/lang")
    return str(v) if v else CFG.get("default_lang", "ku")

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
# ── TIKTOK API ─────────────────────────────────────────────────────────────────
# ==============================================================================
async def fetch_tiktok(url: str) -> dict | None:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    timeout = int(CFG.get("api_timeout", 60))

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as c:
        # Primary API
        try:
            r = await c.get(API_PRIMARY + url)
            if r.status_code == 200:
                d = r.json()
                if d.get("ok") or d.get("status") == "success":
                    log.info("✅ Primary API ok")
                    return {"src": "primary", "data": d}
        except Exception as e:
            log.warning(f"Primary API fail: {e}")

        # Backup API
        try:
            r = await c.get(API_BACKUP + url)
            if r.status_code == 200:
                raw = r.json()
                if raw.get("code") == 0 and raw.get("data"):
                    d   = raw["data"]
                    imgs = _clean_images(d.get("images", []))
                    normalized = {
                        "ok": True,
                        "data": {
                            "creator": d.get("author", {}).get("nickname", "Unknown"),
                            "details": {
                                "title" : d.get("title", ""),
                                "cover" : {"cover": d.get("cover", "")},
                                "images": imgs,
                                "video" : {"play": d.get("play", ""), "wmplay": d.get("wmplay", "")},
                                "audio" : {"play": d.get("music", "")},
                                "stats" : {
                                    "views"   : d.get("play_count",    0),
                                    "likes"   : d.get("digg_count",    0),
                                    "comments": d.get("comment_count", 0),
                                },
                            },
                        },
                    }
                    log.info(f"✅ Backup API ok | images: {len(imgs)}")
                    return {"src": "backup", "data": normalized}
        except Exception as e:
            log.warning(f"Backup API fail: {e}")

    return None

def _clean_images(raw: list) -> list:
    out = []
    for img in raw:
        if isinstance(img, str) and img.startswith("http"):
            out.append(img)
        elif isinstance(img, dict):
            u = (
                (img.get("url_list") or [None])[0] or
                img.get("url") or
                img.get("download_url") or
                ((img.get("display_image") or {}).get("url_list") or [None])[0]
            )
            if u and isinstance(u, str) and u.startswith("http"):
                out.append(u)
    return out

def parse_response(raw: dict) -> tuple[str, dict, list]:
    data    = raw.get("data", {})
    creator = data.get("creator", "Unknown")
    details = data.get("details", {})
    imgs    = _clean_images(
        details.get("images") or
        details.get("image_list") or
        data.get("images") or []
    )
    log.info(f"🖼 images parsed: {len(imgs)}")
    return creator, details, imgs

def is_photo_post(imgs: list) -> bool:
    mode = CFG.get("photo_mode", "auto")
    if mode == "force_video": return False
    if mode == "force_photo": return True
    return len(imgs) > 0

# ==============================================================================
# ── NUMPAD (Inline ID input) ───────────────────────────────────────────────────
# ==============================================================================
def numpad(action: str) -> InlineKeyboardMarkup:
    r = [
        [InlineKeyboardButton(str(d), callback_data=f"np_{action}_{d}") for d in [1,2,3]],
        [InlineKeyboardButton(str(d), callback_data=f"np_{action}_{d}") for d in [4,5,6]],
        [InlineKeyboardButton(str(d), callback_data=f"np_{action}_{d}") for d in [7,8,9]],
        [
            InlineKeyboardButton("⌫", callback_data=f"np_{action}_back"),
            InlineKeyboardButton("0",  callback_data=f"np_{action}_0"),
            InlineKeyboardButton("✅", callback_data=f"np_{action}_ok"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="np_cancel")],
    ]
    return InlineKeyboardMarkup(r)

def ch_pad() -> InlineKeyboardMarkup:
    letters = "abcdefghijklmnopqrstuvwxyz"
    rows = []
    for i in range(0, len(letters), 5):
        rows.append([InlineKeyboardButton(c, callback_data=f"chi_{c}") for c in letters[i:i+5]])
    rows.append([
        InlineKeyboardButton("0", callback_data="chi_0"),
        InlineKeyboardButton("1", callback_data="chi_1"),
        InlineKeyboardButton("2", callback_data="chi_2"),
        InlineKeyboardButton("3", callback_data="chi_3"),
        InlineKeyboardButton("4", callback_data="chi_4"),
    ])
    rows.append([
        InlineKeyboardButton("5", callback_data="chi_5"),
        InlineKeyboardButton("6", callback_data="chi_6"),
        InlineKeyboardButton("7", callback_data="chi_7"),
        InlineKeyboardButton("8", callback_data="chi_8"),
        InlineKeyboardButton("9", callback_data="chi_9"),
    ])
    rows.append([
        InlineKeyboardButton("_", callback_data="chi__"),
        InlineKeyboardButton(".", callback_data="chi_."),
        InlineKeyboardButton("⌫", callback_data="chi_back"),
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

    async def reply(text, kb):
        mu = InlineKeyboardMarkup(kb)
        if is_cb:
            try:   await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=mu)
            except BadRequest: await update.callback_query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=mu)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=mu)

    if is_blocked(uid):
        await reply(tx(lang, "blocked_msg"), back(lang))
        return

    if CFG["maintenance"] and not is_admin(uid):
        await reply(tx(lang, "maintenance_msg"), back(lang))
        return

    # Register
    if not is_admin(uid) and not await user_exists(uid):
        asyncio.create_task(notify_owner(ctx, user))
        CFG["total_users"] = CFG.get("total_users", 0) + 1
        await user_put(uid, {
            "name": user.first_name,
            "user": user.username or "",
            "date": now_str(),
            "vip" : False,
            "lang": CFG.get("default_lang", "ku"),
            "dl"  : 0,
        })

    # Join check
    ok_sub, missing = await check_join(uid, ctx)
    if not ok_sub and not bypass_join(uid):
        kb  = [[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in missing]
        kb += [[InlineKeyboardButton(tx(lang, "b_joined"), callback_data="check_join")]]
        await reply(tx(lang, "force_join"), kb)
        return

    # Badge
    if is_owner(uid):   badge = tx(lang, "badge_owner")
    elif is_admin(uid): badge = tx(lang, "badge_admin")
    elif is_vip(uid):   badge = tx(lang, "badge_vip")
    else:               badge = ""

    # Welcome text
    wm = CFG.get("welcome_msg", "")
    if wm and not is_admin(uid):
        text = wm.replace("{name}", html.escape(user.first_name)).replace("{badge}", badge)
    else:
        text = tx(lang, "welcome", name=html.escape(user.first_name), badge=badge, div=DIV)

    kb = [
        [InlineKeyboardButton(tx(lang, "b_dl"), callback_data="ask_link")],
        [
            InlineKeyboardButton(tx(lang, "b_profile"),  callback_data="show_profile"),
            InlineKeyboardButton(tx(lang, "b_vip"),      callback_data="show_vip"),
        ],
        [
            InlineKeyboardButton(tx(lang, "b_settings"), callback_data="show_settings"),
            InlineKeyboardButton(tx(lang, "b_help"),     callback_data="show_help"),
        ],
        [InlineKeyboardButton(tx(lang, "b_channel"), url=CHANNEL_URL)],
    ]
    if is_admin(uid): kb.append([InlineKeyboardButton(tx(lang, "b_admin"), callback_data="admin_home")])
    if is_owner(uid): kb.append([InlineKeyboardButton(tx(lang, "b_owner"), callback_data="owner_home")])

    await reply(text, kb)

# ==============================================================================
# ── CALLBACK HANDLER ───────────────────────────────────────────────────────────
# ==============================================================================
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    uid  = q.from_user.id
    lang = await get_lang(uid)
    await q.answer()

    # ── Navigation ────────────────────────────────────────────────────────────
    if data in ("cmd_start", "check_join"):
        await cmd_start(update, ctx); return

    if data == "ask_link":
        await q.message.reply_text(
            "🔗 لینکی تیکتۆکەکە بنێرە:",
            reply_markup=ForceReply(selective=True)
        ); return

    if data == "close":
        try: await q.message.delete()
        except: pass
        return

    # ── Profile ───────────────────────────────────────────────────────────────
    if data == "show_profile":
        ud   = await user_get(uid) or {}
        text = tx(lang, "profile",
            id   = f"<code>{uid}</code>",
            name = html.escape(q.from_user.first_name),
            user = q.from_user.username or "—",
            date = ud.get("date", "—"),
            vip  = tx(lang, "vip_yes") if is_vip(uid) else tx(lang, "vip_no"),
            dl   = ud.get("dl", 0),
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(back(lang))); return

    if data == "show_vip":
        await q.edit_message_text(tx(lang, "vip_info", dev=DEV),
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(back(lang))); return

    if data == "show_help":
        await q.edit_message_text(tx(lang, "help", dev=DEV),
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(back(lang))); return

    # ── Language settings ──────────────────────────────────────────────────────
    if data == "show_settings":
        kb = [
            [InlineKeyboardButton(tx(lang, "b_ku"), callback_data="lang_ku")],
            [InlineKeyboardButton(tx(lang, "b_en"), callback_data="lang_en")],
            [InlineKeyboardButton(tx(lang, "b_ar"), callback_data="lang_ar")],
            *back(lang),
        ]
        await q.edit_message_text(tx(lang, "lang_title"),
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if data.startswith("lang_"):
        nl = data[5:]
        await user_field(uid, "lang", nl)
        await q.answer(f"✅ {nl.upper()}", show_alert=True)
        await cmd_start(update, ctx); return

    # ── Download ───────────────────────────────────────────────────────────────
    if data.startswith("dl_"):
        action = data[3:]
        sess   = await session_get(uid)
        if not sess:
            await q.answer(tx(lang, "session_expired"), show_alert=True); return

        creator = sess.get("creator", "")
        details = sess.get("details", {})
        images  = sess.get("images",  [])
        title   = clean_title(details.get("title", ""))
        cap     = f"🎬 <b>{html.escape(title)}</b>\n👤 <b>{html.escape(str(creator))}</b>\n\n🤖 @{ctx.bot.username}"
        del_kb  = InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_delete"), callback_data="close")]])

        # Photos
        if action == "photo":
            if not images:
                await q.answer(tx(lang, "no_photo"), show_alert=True); return
            CFG["total_dl"]    = CFG.get("total_dl",    0) + 1
            CFG["total_photo"] = CFG.get("total_photo", 0) + 1
            await save_cfg()
            ud = await user_get(uid) or {}
            await user_field(uid, "dl", ud.get("dl", 0) + 1)

            try: await q.message.delete()
            except: pass

            wait = await ctx.bot.send_message(uid, tx(lang, "sending_photos"), parse_mode=ParseMode.HTML)
            max_p = int(CFG.get("max_photos", 10))
            chunks = [images[i:i+10] for i in range(0, min(len(images), max_p), 10)]
            sent = False
            for chunk in chunks:
                mg = [InputMediaPhoto(u) for u in chunk]
                if not sent:
                    mg[0].caption    = cap
                    mg[0].parse_mode = ParseMode.HTML
                try:
                    await ctx.bot.send_media_group(uid, mg)
                    sent = True
                except Exception as e:
                    log.error(f"media_group fail: {e}")
                    for u in chunk:
                        try:
                            await ctx.bot.send_photo(uid, u, caption=cap if not sent else "", parse_mode=ParseMode.HTML)
                            sent = True
                        except Exception as e2:
                            log.error(f"send_photo fail: {e2}")
                await asyncio.sleep(0.5)
            try: await wait.delete()
            except: pass
            if not sent:
                links = "\n".join([f"🖼 <a href='{u}'>وێنەی {i+1}</a>" for i,u in enumerate(images[:10])])
                await ctx.bot.send_message(uid, f"⚠️ لینکەکان:\n{links}", parse_mode=ParseMode.HTML)

        # Video
        elif action == "video":
            vurl = details.get("video", {}).get("play") or details.get("video", {}).get("wmplay") or ""
            if not vurl:
                await q.answer(tx(lang, "no_video"), show_alert=True); return
            CFG["total_dl"]    = CFG.get("total_dl",    0) + 1
            CFG["total_video"] = CFG.get("total_video", 0) + 1
            await save_cfg()
            ud = await user_get(uid) or {}
            await user_field(uid, "dl", ud.get("dl", 0) + 1)
            try:
                await q.message.edit_media(
                    InputMediaVideo(vurl, caption=cap, parse_mode=ParseMode.HTML),
                    reply_markup=del_kb,
                )
            except Exception as e:
                log.error(f"edit_media video fail: {e}")
                try: await q.message.delete()
                except: pass
                try:
                    await ctx.bot.send_video(uid, vurl, caption=cap, parse_mode=ParseMode.HTML, reply_markup=del_kb)
                except:
                    await ctx.bot.send_message(uid, f"📥 <a href='{vurl}'>داونلۆد</a>", parse_mode=ParseMode.HTML)

        # Audio
        elif action == "audio":
            aurl = details.get("audio", {}).get("play") or details.get("audio", {}).get("music") or ""
            if not aurl:
                await q.answer(tx(lang, "no_audio"), show_alert=True); return
            CFG["total_dl"]    = CFG.get("total_dl",    0) + 1
            CFG["total_audio"] = CFG.get("total_audio", 0) + 1
            await save_cfg()
            ud = await user_get(uid) or {}
            await user_field(uid, "dl", ud.get("dl", 0) + 1)
            try:
                await q.message.edit_media(
                    InputMediaAudio(aurl, caption=cap, parse_mode=ParseMode.HTML,
                                    title=f"{DEV}-{rand_id()}", performer=DEV),
                    reply_markup=del_kb,
                )
            except Exception as e:
                log.error(f"edit_media audio fail: {e}")
                try: await q.message.delete()
                except: pass
                try:
                    await ctx.bot.send_audio(uid, aurl, caption=cap, parse_mode=ParseMode.HTML,
                                             title=f"{DEV}-{rand_id()}", performer=DEV, reply_markup=del_kb)
                except:
                    await ctx.bot.send_message(uid, f"🎵 <a href='{aurl}'>داونلۆد</a>", parse_mode=ParseMode.HTML)
        return

    # ==========================================================================
    # ── ADMIN PANEL ────────────────────────────────────────────────────────────
    # ==========================================================================
    if not is_admin(uid):
        await q.answer(tx(lang, "admin_only"), show_alert=True); return

    if data == "admin_home":
        uids = await all_uids()
        maint = "🔴 ON" if CFG["maintenance"] else "🟢 OFF"
        kb = [
            [InlineKeyboardButton("📊 ئامار",         callback_data="adm_stats"),
             InlineKeyboardButton("📢 برۆدکاست",      callback_data="adm_bc_menu")],
            [InlineKeyboardButton("📢 چەناڵ",         callback_data="adm_channels"),
             InlineKeyboardButton("🚫 بلۆک",           callback_data="adm_block_menu")],
            [InlineKeyboardButton("💎 VIP",            callback_data="adm_vip_menu"),
             InlineKeyboardButton(f"🛠 چاکسازی: {maint}", callback_data="adm_toggle_maint")],
            [InlineKeyboardButton("👤 زانیاری کەس",   callback_data="adm_userinfo"),
             InlineKeyboardButton("✉️ نامە بنێرە",     callback_data="adm_sendmsg")],
            *back(lang),
        ]
        await q.edit_message_text(
            f"👑 <b>پانێڵی ئەدمین</b>\n\n👥 بەکارهێنەر: <b>{len(uids)}</b>\n🛠 چاکسازی: <b>{maint}</b>\n🕐 {now_str()}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb),
        ); return

    # Stats
    if data == "adm_stats":
        uids = await all_uids()
        text = (
            f"📊 <b>ئاماری بۆت</b>\n\n"
            f"👥 بەکارهێنەر: <b>{len(uids)}</b>\n"
            f"💎 VIP: <b>{len(vip_set)}</b>\n"
            f"⚡ ئەدمین: <b>{len(admins_set)}</b>\n"
            f"🚫 بلۆک: <b>{len(blocked_set)}</b>\n"
            f"📢 چەناڵ: <b>{len(channels_list)}</b>\n\n"
            f"📥 داونلۆدی کۆ: <b>{fmt(CFG.get('total_dl',0))}</b>\n"
            f"🎥 ڤیدیۆ: <b>{fmt(CFG.get('total_video',0))}</b>\n"
            f"🎵 گۆرانی: <b>{fmt(CFG.get('total_audio',0))}</b>\n"
            f"📸 وێنە: <b>{fmt(CFG.get('total_photo',0))}</b>\n\n"
            f"⏱ Uptime: {uptime()}\n🕐 {now_str()}"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 نوێکردنەوە", callback_data="adm_stats")],
                *back(lang, "admin_home"),
            ])
        ); return

    # Maintenance toggle
    if data == "adm_toggle_maint":
        if not is_owner(uid):
            await q.answer(tx(lang, "owner_only"), show_alert=True); return
        CFG["maintenance"] = not CFG["maintenance"]
        await save_cfg()
        await q.answer(f"🛠 {'ON 🔴' if CFG['maintenance'] else 'OFF 🟢'}", show_alert=True)
        q.data = "admin_home"
        await on_callback(update, ctx); return

    # Broadcast menu
    if data == "adm_bc_menu":
        kb = [
            [InlineKeyboardButton("📢 هەمووان",    callback_data="bc_all"),
             InlineKeyboardButton("💎 تەنیا VIP",  callback_data="bc_vip")],
            [InlineKeyboardButton("🆓 Free",        callback_data="bc_free"),
             InlineKeyboardButton("✅ ئەنبلۆک",     callback_data="bc_noblk")],
            *back(lang, "admin_home"),
        ]
        await q.edit_message_text("📢 <b>برۆدکاست</b>\n\nکێ دەوێیت پێبگات?",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if data.startswith("bc_"):
        bt = data[3:]
        waiting_state[uid] = f"broadcast_{bt}"
        await q.edit_message_text(
            f"📢 ✍️ نامەکەت بنێرە (هەر جۆر):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ هەڵوەشاندنەوە", callback_data="adm_bc_menu")
            ]])
        ); return

    # Channel management
    if data == "adm_channels":
        ch_text = "\n".join([f"• <code>{c}</code>" for c in channels_list]) or "📭 هیچ چەناڵێک نییە"
        kb = [
            [InlineKeyboardButton("➕ زیادکردن",  callback_data="ch_add"),
             InlineKeyboardButton("➖ لابردن",    callback_data="ch_rm_list")],
            *back(lang, "admin_home"),
        ]
        await q.edit_message_text(f"📢 <b>چەناڵەکان</b>\n\n{ch_text}",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if data == "ch_add":
        ctx.user_data["ch_buf"] = "@"
        await q.edit_message_text("📢 ناوی چەناڵ داخڵ بکە:\n<code>@</code>",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=ch_pad()); return

    if data == "ch_rm_list":
        if not channels_list:
            await q.answer("📭 هیچ چەناڵێک نییە!", show_alert=True); return
        kb  = [[InlineKeyboardButton(f"❌ {c}", callback_data=f"ch_del_{c}")] for c in channels_list]
        kb += back(lang, "adm_channels")
        await q.edit_message_text("چەناڵێک هەڵبژێرە بۆ لابردن:",
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if data.startswith("ch_del_"):
        ch = data[7:]
        if ch in channels_list: channels_list.remove(ch)
        await save_cfg()
        await q.edit_message_text(f"✅ لابرا: <code>{ch}</code>", parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(back(lang, "adm_channels"))); return

    # Block menu
    if data == "adm_block_menu":
        blist = "\n".join([f"• <code>{x}</code>" for x in blocked_set]) or "📭 بلۆک نییە"
        kb = [
            [InlineKeyboardButton("🚫 بلۆک",    callback_data="blk_add_np"),
             InlineKeyboardButton("✅ ئەنبلۆک",  callback_data="blk_rm_np")],
            *back(lang, "admin_home"),
        ]
        await q.edit_message_text(f"🚫 <b>بلۆک کراوەکان</b>\n\n{blist}",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if data == "blk_add_np":
        ctx.user_data["np_action"] = "blk_add"
        ctx.user_data["np_buf"]    = ""
        await q.edit_message_text("🚫 ئایدی داخڵ بکە:", reply_markup=numpad("blk_add")); return

    if data == "blk_rm_np":
        ctx.user_data["np_action"] = "blk_rm"
        ctx.user_data["np_buf"]    = ""
        await q.edit_message_text("✅ ئایدی داخڵ بکە:", reply_markup=numpad("blk_rm")); return

    # VIP menu
    if data == "adm_vip_menu":
        vlist = "\n".join([f"• <code>{x}</code>" for x in vip_set]) or "📭 VIP نییە"
        kb = [
            [InlineKeyboardButton("➕ زیادکردن", callback_data="vip_add_np"),
             InlineKeyboardButton("➖ لابردن",   callback_data="vip_rm_np")],
            *back(lang, "admin_home"),
        ]
        await q.edit_message_text(f"💎 <b>VIP بەکارهێنەرەکان</b>\n\n{vlist}",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if data == "vip_add_np":
        ctx.user_data["np_action"] = "vip_add"
        ctx.user_data["np_buf"]    = ""
        await q.edit_message_text("💎 ئایدی داخڵ بکە:", reply_markup=numpad("vip_add")); return

    if data == "vip_rm_np":
        ctx.user_data["np_action"] = "vip_rm"
        ctx.user_data["np_buf"]    = ""
        await q.edit_message_text("➖ ئایدی داخڵ بکە:", reply_markup=numpad("vip_rm")); return

    # User info
    if data == "adm_userinfo":
        ctx.user_data["np_action"] = "userinfo"
        ctx.user_data["np_buf"]    = ""
        await q.edit_message_text("👤 ئایدی داخڵ بکە:", reply_markup=numpad("userinfo")); return

    # Send msg
    if data == "adm_sendmsg":
        ctx.user_data["np_action"] = "sendmsg_id"
        ctx.user_data["np_buf"]    = ""
        await q.edit_message_text("✉️ ئایدی داخڵ بکە:", reply_markup=numpad("sendmsg_id")); return

    # Quick actions
    if data.startswith("qa_blk_"):
        tid = int(data[7:])
        if tid in blocked_set: blocked_set.discard(tid); msg = f"✅ ئەنبلۆک: <code>{tid}</code>"
        else: blocked_set.add(tid); msg = f"🚫 بلۆک: <code>{tid}</code>"
        await save_cfg()
        await q.answer(msg.replace("<code>","").replace("</code>",""), show_alert=True)
        return

    if data.startswith("qa_vip_"):
        tid = int(data[7:])
        if tid in vip_set:
            vip_set.discard(tid); await user_field(tid, "vip", False)
            await q.answer(f"VIP لابرا: {tid}", show_alert=True)
        else:
            vip_set.add(tid); await user_field(tid, "vip", True)
            await q.answer(f"VIP زیادکرا: {tid}", show_alert=True)
        await save_cfg(); return

    if data.startswith("qa_msg_"):
        tid = int(data[7:])
        waiting_state[uid] = f"sendmsg_send_{tid}"
        await q.message.reply_text(tx(lang, "write_msg", id=f"<code>{tid}</code>"),
                                   parse_mode=ParseMode.HTML,
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("❌", callback_data="np_cancel")
                                   ]])); return

    # ==========================================================================
    # ── OWNER PANEL ────────────────────────────────────────────────────────────
    # ==========================================================================
    if not is_owner(uid):
        await q.answer(tx(lang, "owner_only"), show_alert=True); return

    if data == "owner_home":
        kb = [
            [InlineKeyboardButton("👥 ئەدمینەکان",        callback_data="own_admins"),
             InlineKeyboardButton("📊 ئاماری پێشکەوتوو",  callback_data="own_adv_stats")],
            [InlineKeyboardButton("⚙️ ڕێکخستن",           callback_data="own_settings"),
             InlineKeyboardButton("📝 نامەی خۆشامەدێ",     callback_data="own_welcome")],
            [InlineKeyboardButton("💾 بەکئەپ",             callback_data="own_backup"),
             InlineKeyboardButton("📋 لیستی بەکارهێنەر",  callback_data="own_list_users")],
            [InlineKeyboardButton("🗑 ڕیسێتی ئامار",      callback_data="own_reset_stats"),
             InlineKeyboardButton("☢️ سڕینەوەی بەکارهێنەر",callback_data="own_reset_users")],
            [InlineKeyboardButton("📣 بڕۆدکاست",          callback_data="adm_bc_menu"),
             InlineKeyboardButton("🔧 تاقیکردنەوەی API",  callback_data="own_test_api")],
            [InlineKeyboardButton("🌐 زمانی پێشواز",       callback_data="own_def_lang"),
             InlineKeyboardButton("📈 ریپۆرت",            callback_data="own_report")],
            *back(lang),
        ]
        await q.edit_message_text(
            f"🔱 <b>پانێڵی خاوەن</b>\n\n👑 <code>{OWNER_ID}</code>\n⏱ {uptime()}\n🕐 {now_str()}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb),
        ); return

    # Admins management
    if data == "own_admins":
        adm_list = "\n".join([f"• <code>{x}</code>" for x in admins_set if x != OWNER_ID]) or "📭 هیچ ئەدمینێک نییە"
        kb = [
            [InlineKeyboardButton("➕ زیادکردن", callback_data="adm_add_np"),
             InlineKeyboardButton("➖ لابردن",   callback_data="adm_rm_np")],
            *back(lang, "owner_home"),
        ]
        await q.edit_message_text(f"👥 <b>ئەدمینەکان</b>\n\n{adm_list}",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if data == "adm_add_np":
        ctx.user_data["np_action"] = "adm_add"
        ctx.user_data["np_buf"]    = ""
        await q.edit_message_text("➕ ئایدی داخڵ بکە:", reply_markup=numpad("adm_add")); return

    if data == "adm_rm_np":
        ctx.user_data["np_action"] = "adm_rm"
        ctx.user_data["np_buf"]    = ""
        await q.edit_message_text("➖ ئایدی داخڵ بکە:", reply_markup=numpad("adm_rm")); return

    # Advanced stats
    if data == "own_adv_stats":
        all_d   = await all_users()
        tot_dl  = sum(v.get("dl",0) for v in all_d.values() if isinstance(v,dict))
        text = (
            f"📊 <b>ئاماری پێشکەوتوو</b>\n\n"
            f"👥 کۆی گشتی: <b>{len(all_d)}</b>\n"
            f"💎 VIP: <b>{len(vip_set)}</b>\n"
            f"⚡ ئەدمین: <b>{len(admins_set)}</b>\n"
            f"🚫 بلۆک: <b>{len(blocked_set)}</b>\n"
            f"📢 چەناڵ: <b>{len(channels_list)}</b>\n\n"
            f"📥 داونلۆدی کۆ (سیستەم): <b>{fmt(CFG.get('total_dl',0))}</b>\n"
            f"📥 داونلۆدی کۆ (بەکارهێنەر): <b>{fmt(tot_dl)}</b>\n"
            f"🎥 ڤیدیۆ: <b>{fmt(CFG.get('total_video',0))}</b>\n"
            f"🎵 گۆرانی: <b>{fmt(CFG.get('total_audio',0))}</b>\n"
            f"📸 وێنە: <b>{fmt(CFG.get('total_photo',0))}</b>\n\n"
            f"📸 Photo Mode: {CFG.get('photo_mode','auto')}\n"
            f"📸 Max Photos: {CFG.get('max_photos',10)}\n"
            f"⏱ API Timeout: {CFG.get('api_timeout',60)}s\n"
            f"💎 VIP Bypass: {'✅' if CFG.get('vip_bypass') else '❌'}\n"
            f"⚡ Admin Bypass: {'✅' if CFG.get('admin_bypass') else '❌'}\n\n"
            f"⏱ Uptime: {uptime()}\n🕐 {now_str()}"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄", callback_data="own_adv_stats")],
                *back(lang, "owner_home"),
            ])
        ); return

    # Bot settings
    if data == "own_settings":
        kb = [
            [InlineKeyboardButton(
                f"🛠 چاکسازی: {'🔴' if CFG['maintenance'] else '🟢'}",
                callback_data="own_tog_maint")],
            [InlineKeyboardButton(
                f"📸 Photo Mode: {CFG.get('photo_mode','auto')}",
                callback_data="own_tog_photo_mode")],
            [InlineKeyboardButton(
                f"💎 VIP Bypass: {'✅' if CFG.get('vip_bypass') else '❌'}",
                callback_data="own_tog_vip_bypass")],
            [InlineKeyboardButton(
                f"⚡ Admin Bypass: {'✅' if CFG.get('admin_bypass') else '❌'}",
                callback_data="own_tog_adm_bypass")],
            [InlineKeyboardButton(
                f"📸 Max Photos: {CFG.get('max_photos',10)}",
                callback_data="own_set_max_photos")],
            [InlineKeyboardButton(
                f"⏱ API Timeout: {CFG.get('api_timeout',60)}s",
                callback_data="own_set_api_timeout")],
            *back(lang, "owner_home"),
        ]
        await q.edit_message_text("⚙️ <b>ڕێکخستنی بۆت</b>",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if data == "own_tog_maint":
        CFG["maintenance"] = not CFG["maintenance"]
        await save_cfg(); await q.answer(f"🛠 {'ON' if CFG['maintenance'] else 'OFF'}", show_alert=True)
        q.data = "own_settings"; await on_callback(update, ctx); return

    if data == "own_tog_photo_mode":
        modes = ["auto", "force_photo", "force_video"]
        CFG["photo_mode"] = modes[(modes.index(CFG.get("photo_mode","auto")) + 1) % len(modes)]
        await save_cfg(); await q.answer(f"Photo Mode → {CFG['photo_mode']}", show_alert=True)
        q.data = "own_settings"; await on_callback(update, ctx); return

    if data == "own_tog_vip_bypass":
        CFG["vip_bypass"] = not CFG.get("vip_bypass", True)
        await save_cfg(); await q.answer(f"VIP Bypass → {'ON' if CFG['vip_bypass'] else 'OFF'}", show_alert=True)
        q.data = "own_settings"; await on_callback(update, ctx); return

    if data == "own_tog_adm_bypass":
        CFG["admin_bypass"] = not CFG.get("admin_bypass", True)
        await save_cfg(); await q.answer(f"Admin Bypass → {'ON' if CFG['admin_bypass'] else 'OFF'}", show_alert=True)
        q.data = "own_settings"; await on_callback(update, ctx); return

    if data == "own_set_max_photos":
        ctx.user_data["np_action"] = "set_max_photos"
        ctx.user_data["np_buf"]    = ""
        await q.edit_message_text(f"📸 Max Photos ئێستا: {CFG.get('max_photos',10)}\nژمارەی نوێ:",
                                  reply_markup=numpad("set_max_photos")); return

    if data == "own_set_api_timeout":
        ctx.user_data["np_action"] = "set_api_timeout"
        ctx.user_data["np_buf"]    = ""
        await q.edit_message_text(f"⏱ Timeout ئێستا: {CFG.get('api_timeout',60)}s\nچرکەی نوێ:",
                                  reply_markup=numpad("set_api_timeout")); return

    # Welcome message
    if data == "own_welcome":
        waiting_state[uid] = "set_welcome"
        cur = CFG.get("welcome_msg","") or "<i>(بەکارنەهاتوو)</i>"
        await q.edit_message_text(
            f"📝 <b>ئێستا:</b>\n{cur}\n\n{tx(lang,'write_welcome',id='{name}',badge='{badge}')}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 سڕینەوە", callback_data="own_clear_welcome")],
                *back(lang, "owner_home"),
            ])
        ); return

    if data == "own_clear_welcome":
        CFG["welcome_msg"] = ""; await save_cfg()
        await q.edit_message_text("✅ سڕایەوە.",
                                  reply_markup=InlineKeyboardMarkup(back(lang, "owner_home"))); return

    # Backup
    if data == "own_backup":
        await q.answer("⏳ ئامادەدەکرێت...", show_alert=False)
        all_d = await all_users()
        bdata = {
            "time"    : now_str(),
            "cfg"     : CFG,
            "admins"  : list(admins_set),
            "channels": channels_list,
            "blocked" : list(blocked_set),
            "vips"    : list(vip_set),
            "users"   : len(all_d),
        }
        bio = io.BytesIO(json.dumps(bdata, ensure_ascii=False, indent=2).encode())
        bio.name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            await ctx.bot.send_document(uid, bio, caption=tx(lang,"backup_caption",time=now_str()),
                                        parse_mode=ParseMode.HTML)
        except Exception as e:
            await q.message.reply_text(f"❌ {e}")
        return

    # List users
    if data == "own_list_users":
        all_d = await all_users()
        if not all_d:
            await q.answer(tx(lang,"no_users"), show_alert=True); return
        lines = []
        for uid2, info in list(all_d.items())[:50]:
            if not isinstance(info, dict): continue
            vm = "💎" if info.get("vip") else ""
            bm = "🚫" if int(uid2) in blocked_set else ""
            nm = html.escape(str(info.get("name","?")))[:18]
            lines.append(f"{vm}{bm} <code>{uid2}</code> {nm}")
        tot  = len(all_d)
        text = f"📋 <b>لیستی بەکارهێنەرەکان ({tot})</b>\n\n" + "\n".join(lines)
        if tot > 50: text += f"\n<i>...و {tot-50} کەسی تر</i>"
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(back(lang,"owner_home"))); return

    # Reset stats
    if data == "own_reset_stats":
        kb = [[InlineKeyboardButton(tx(lang,"b_confirm"), callback_data="own_reset_stats_do"),
               InlineKeyboardButton(tx(lang,"b_cancel"),  callback_data="owner_home")]]
        await q.edit_message_text(tx(lang,"confirm_del"), parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if data == "own_reset_stats_do":
        for k in ("total_dl","total_video","total_audio","total_photo"):
            CFG[k] = 0
        await save_cfg()
        await q.edit_message_text(tx(lang,"stats_reset"), parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(back(lang,"owner_home"))); return

    # Reset users
    if data == "own_reset_users":
        kb = [[InlineKeyboardButton(tx(lang,"b_confirm"), callback_data="own_reset_users_do"),
               InlineKeyboardButton(tx(lang,"b_cancel"),  callback_data="owner_home")]]
        await q.edit_message_text(tx(lang,"confirm_del"), parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if data == "own_reset_users_do":
        await users_del()
        await q.edit_message_text(tx(lang,"users_deleted"), parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(back(lang,"owner_home"))); return

    # Test API
    if data == "own_test_api":
        await q.answer("⏳...", show_alert=False)
        res = await fetch_tiktok("https://www.tiktok.com/@tiktok/video/6584647400055385349")
        t2  = f"✅ کار دەکات! Source: {res.get('src')}" if res else "❌ کار ناکات!"
        await q.edit_message_text(f"{t2}\n🕐 {now_str()}", parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(back(lang,"owner_home"))); return

    # Default lang
    if data == "own_def_lang":
        kb = [
            [InlineKeyboardButton(tx(lang,"b_ku"), callback_data="own_deflang_ku")],
            [InlineKeyboardButton(tx(lang,"b_en"), callback_data="own_deflang_en")],
            [InlineKeyboardButton(tx(lang,"b_ar"), callback_data="own_deflang_ar")],
            *back(lang, "owner_home"),
        ]
        await q.edit_message_text("🌐 زمانی پێشواز هەڵبژێرە:",
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    for dl in ("ku","en","ar"):
        if data == f"own_deflang_{dl}":
            CFG["default_lang"] = dl; await save_cfg()
            await q.answer(f"✅ {dl.upper()}", show_alert=True)
            q.data = "owner_home"; await on_callback(update, ctx); return

    # Daily report
    if data == "own_report":
        uids = await all_uids()
        text = (
            f"📈 <b>ریپۆرتی ڕۆژانە</b>\n\n"
            f"🕐 {now_str()}\n{DIV}\n"
            f"👥 بەکارهێنەر: <b>{len(uids)}</b>\n"
            f"📥 کۆی داونلۆد: <b>{fmt(CFG.get('total_dl',0))}</b>\n"
            f"🎥 ڤیدیۆ: <b>{fmt(CFG.get('total_video',0))}</b>\n"
            f"📸 وێنە: <b>{fmt(CFG.get('total_photo',0))}</b>\n"
            f"🎵 گۆرانی: <b>{fmt(CFG.get('total_audio',0))}</b>\n"
            f"{DIV}\n"
            f"💎 VIP: <b>{len(vip_set)}</b>\n"
            f"🚫 بلۆک: <b>{len(blocked_set)}</b>\n"
            f"⚡ ئەدمین: <b>{len(admins_set)}</b>\n"
            f"{DIV}\n⏱ Uptime: {uptime()}"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄", callback_data="own_report")],
                *back(lang, "owner_home"),
            ])
        ); return

# ==============================================================================
# ── NUMPAD HANDLER ─────────────────────────────────────────────────────────────
# ==============================================================================
async def on_numpad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    uid  = q.from_user.id
    lang = await get_lang(uid)
    await q.answer()

    # Cancel
    if data == "np_cancel":
        ctx.user_data.pop("np_action", None)
        ctx.user_data.pop("np_buf",    None)
        ctx.user_data.pop("ch_buf",    None)
        try: await q.message.delete()
        except: pass
        return

    # Channel input
    if data.startswith("chi_"):
        key = data[4:]
        buf = ctx.user_data.get("ch_buf", "@")
        if key == "back":
            buf = buf[:-1] if len(buf) > 1 else buf
        elif key == "ok":
            ch = buf if buf.startswith("@") else f"@{buf}"
            if len(ch) < 3:
                await q.answer("❌ کورتە!", show_alert=True); return
            ctx.user_data.pop("ch_buf", None)
            if ch not in channels_list: channels_list.append(ch)
            await save_cfg()
            await q.edit_message_text(f"✅ زیادکرا: <code>{ch}</code>",
                                      parse_mode=ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(back(lang,"adm_channels"))); return
        else:
            if len(buf) < 33: buf += key
        ctx.user_data["ch_buf"] = buf
        try:
            await q.edit_message_text(f"📢 ناوی چەناڵ:\n<code>{buf}</code>",
                                      parse_mode=ParseMode.HTML,
                                      reply_markup=ch_pad())
        except: pass
        return

    # Numpad
    if data.startswith("np_"):
        parts = data.split("_", 2)
        if len(parts) < 3: return
        action, key = parts[1], parts[2]
        buf = ctx.user_data.get("np_buf", "")

        if key == "back":
            buf = buf[:-1]
        elif key == "ok":
            if not buf.isdigit():
                await q.answer("❌ ئایدی دروست نییە!", show_alert=True); return
            tid = int(buf)
            ctx.user_data.pop("np_buf",    None)
            ctx.user_data.pop("np_action", None)

            go_back = "admin_home"

            if action == "blk_add":
                blocked_set.add(tid); await save_cfg()
                await q.edit_message_text(f"🚫 بلۆک کرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(back(lang,"adm_block_menu")))

            elif action == "blk_rm":
                blocked_set.discard(tid); await save_cfg()
                await q.edit_message_text(f"✅ ئەنبلۆک کرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(back(lang,"adm_block_menu")))

            elif action == "vip_add":
                vip_set.add(tid); await save_cfg(); await user_field(tid,"vip",True)
                await q.edit_message_text(f"💎 VIP زیادکرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(back(lang,"adm_vip_menu")))

            elif action == "vip_rm":
                vip_set.discard(tid); await save_cfg(); await user_field(tid,"vip",False)
                await q.edit_message_text(f"➖ VIP لابرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(back(lang,"adm_vip_menu")))

            elif action == "adm_add":
                if not is_owner(uid):
                    await q.answer(tx(lang,"owner_only"), show_alert=True); return
                admins_set.add(tid); await save_cfg()
                await q.edit_message_text(f"⚡ ئەدمین زیادکرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(back(lang,"own_admins")))

            elif action == "adm_rm":
                if not is_owner(uid):
                    await q.answer(tx(lang,"owner_only"), show_alert=True); return
                if tid == OWNER_ID:
                    await q.answer("⛔ ناتوانیت خاوەنەکە لابەری!", show_alert=True); return
                admins_set.discard(tid); await save_cfg()
                await q.edit_message_text(f"➖ ئەدمین لابرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(back(lang,"own_admins")))

            elif action == "userinfo":
                ud = await user_get(tid)
                if not ud:
                    await q.edit_message_text(tx(lang,"user_not_found"),
                        reply_markup=InlineKeyboardMarkup(back(lang,"admin_home"))); return
                vip_s = "✅" if tid in vip_set or ud.get("vip") else "❌"
                blk_s = "✅" if tid in blocked_set else "❌"
                await q.edit_message_text(
                    f"👤 <b>زانیاری بەکارهێنەر</b>\n\n"
                    f"🆔 <code>{tid}</code>\n"
                    f"👤 {html.escape(str(ud.get('name','?')))}\n"
                    f"🔗 @{ud.get('user','—')}\n"
                    f"📅 {ud.get('date','—')}\n"
                    f"💎 VIP: {vip_s}\n"
                    f"🚫 بلۆک: {blk_s}\n"
                    f"📥 داونلۆد: {ud.get('dl',0)}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🚫/✅ بلۆک", callback_data=f"qa_blk_{tid}"),
                         InlineKeyboardButton("💎 VIP",      callback_data=f"qa_vip_{tid}")],
                        [InlineKeyboardButton("✉️ نامە",     callback_data=f"qa_msg_{tid}")],
                        *back(lang, "admin_home"),
                    ])
                )

            elif action == "sendmsg_id":
                waiting_state[uid] = f"sendmsg_send_{tid}"
                await q.edit_message_text(tx(lang,"write_msg",id=f"<code>{tid}</code>"),
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("❌", callback_data="np_cancel")
                    ]]))

            elif action == "set_max_photos":
                v = min(max(tid, 1), 30)
                CFG["max_photos"] = v; await save_cfg()
                await q.edit_message_text(f"✅ Max Photos: <b>{v}</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(back(lang,"own_settings")))

            elif action == "set_api_timeout":
                v = max(tid, 10)
                CFG["api_timeout"] = v; await save_cfg()
                await q.edit_message_text(f"✅ API Timeout: <b>{v}s</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(back(lang,"own_settings")))
            return
        else:
            if len(buf) < 15: buf += key

        ctx.user_data["np_buf"] = buf
        titles = {
            "blk_add":"🚫 بلۆک","blk_rm":"✅ ئەنبلۆک",
            "vip_add":"💎 VIP+","vip_rm":"➖ VIP-",
            "adm_add":"⚡ ئەدمین+","adm_rm":"➖ ئەدمین-",
            "userinfo":"👤 ئایدی","sendmsg_id":"✉️ ئایدی",
            "set_max_photos":"📸 Max","set_api_timeout":"⏱ Timeout",
        }
        disp = f"<code>{buf}</code>" if buf else "<i>—</i>"
        try:
            await q.edit_message_text(
                f"{titles.get(action,'📟')}\n\n📟 {disp}",
                parse_mode=ParseMode.HTML,
                reply_markup=numpad(action),
            )
        except: pass

# ==============================================================================
# ── MESSAGE HANDLER ─────────────────────────────────────────────────────────────
# ==============================================================================
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid  = update.effective_user.id
    lang = await get_lang(uid)
    msg  = update.message

    # ── Admin waiting state ────────────────────────────────────────────────────
    if is_admin(uid) and uid in waiting_state:
        state = waiting_state.pop(uid)
        txt   = (msg.text or "").strip()

        # Broadcast
        if state.startswith("broadcast_"):
            bt       = state[10:]
            all_uids_list = await all_uids()
            targets  = []
            for u2 in all_uids_list:
                if bt == "all":                               targets.append(u2)
                elif bt == "vip"   and u2 in vip_set:         targets.append(u2)
                elif bt == "free"  and u2 not in vip_set:     targets.append(u2)
                elif bt == "noblk" and u2 not in blocked_set: targets.append(u2)
            ok = fail = 0
            st = await msg.reply_text(f"⏳ بۆ {len(targets)} کەس...", parse_mode=ParseMode.HTML)
            for i, tu in enumerate(targets):
                try:
                    await ctx.bot.copy_message(tu, msg.chat_id, msg.message_id)
                    ok += 1; await asyncio.sleep(0.04)
                    if i % 50 == 0 and i:
                        try: await st.edit_text(f"⏳ {i}/{len(targets)}...")
                        except: pass
                except (Forbidden, BadRequest): fail += 1
                except: fail += 1; await asyncio.sleep(1)
            await st.edit_text(tx(lang,"broadcast_done",ok=ok,fail=fail), parse_mode=ParseMode.HTML)
            return

        if state == "set_welcome":
            CFG["welcome_msg"] = msg.text or ""; await save_cfg()
            await msg.reply_text(tx(lang,"welcome_set")); return

        if state.startswith("sendmsg_send_"):
            tid = int(state.split("_")[-1])
            try:
                await ctx.bot.copy_message(tid, msg.chat_id, msg.message_id)
                await msg.reply_text(tx(lang,"msg_sent"))
            except Exception as e:
                await msg.reply_text(f"❌ {e}")
            return

    # ── Block / maintenance checks ────────────────────────────────────────────
    if not msg.text: return
    txt = msg.text.strip()
    if is_blocked(uid): return
    if CFG["maintenance"] and not is_admin(uid):
        await msg.reply_text(tx(lang,"maintenance_msg"), parse_mode=ParseMode.HTML); return

    # ── TikTok link detection ─────────────────────────────────────────────────
    if not any(x in txt for x in ("tiktok.com","vm.tiktok","vt.tiktok")): return

    # Join check
    ok_sub, missing = await check_join(uid, ctx)
    if not ok_sub and not bypass_join(uid):
        kb  = [[InlineKeyboardButton(f"📢 {c}", url=f"https://t.me/{c.lstrip('@')}")] for c in missing]
        kb += [[InlineKeyboardButton(tx(lang,"b_joined"), callback_data="check_join")]]
        await msg.reply_text(tx(lang,"force_join"), parse_mode=ParseMode.HTML,
                             reply_markup=InlineKeyboardMarkup(kb)); return

    # Process
    status = await msg.reply_text(tx(lang,"processing"), parse_mode=ParseMode.HTML)

    try:
        res = await fetch_tiktok(txt)
        if not res:
            await status.edit_text(tx(lang,"invalid_link"), parse_mode=ParseMode.HTML); return

        creator, details, images = parse_response(res["data"])
        photo_post = is_photo_post(images)

        # Save session
        await session_save(uid, {
            "creator": creator,
            "details": details,
            "images" : images,
        })

        # Caption text
        title    = clean_title(details.get("title","") or "")
        stats    = details.get("stats", {})
        views    = fmt(stats.get("views",0)    or stats.get("play_count",0))
        likes    = fmt(stats.get("likes",0)    or stats.get("digg_count",0))
        comments = fmt(stats.get("comments",0) or stats.get("comment_count",0))

        caption = tx(lang, "found",
            title    = html.escape(title),
            owner    = html.escape(str(creator)),
            views    = views,
            likes    = likes,
            comments = comments,
        )

        # Keyboard
        if photo_post:
            kb = [
                [InlineKeyboardButton(tx(lang,"b_photos",n=len(images)), callback_data="dl_photo")],
                [InlineKeyboardButton(tx(lang,"b_audio"),                callback_data="dl_audio")],
                [InlineKeyboardButton(tx(lang,"b_delete"),               callback_data="close")],
            ]
        else:
            kb = [
                [InlineKeyboardButton(tx(lang,"b_video"),  callback_data="dl_video")],
                [InlineKeyboardButton(tx(lang,"b_audio"),  callback_data="dl_audio")],
                [InlineKeyboardButton(tx(lang,"b_delete"), callback_data="close")],
            ]

        # Cover image
        if photo_post and images:
            cover = images[0]
        else:
            cd = details.get("cover", {})
            if isinstance(cd, dict):
                cover = cd.get("cover") or cd.get("origin_cover") or cd.get("dynamic_cover") or ""
            else:
                cover = str(cd) if cd else ""

        markup = InlineKeyboardMarkup(kb)

        if cover and cover.startswith("http"):
            try:
                await status.edit_media(
                    InputMediaPhoto(cover, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=markup,
                )
            except Exception as e:
                log.warning(f"edit_media fail: {e}")
                try:
                    await status.edit_text(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
                except:
                    await msg.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
                    try: await status.delete()
                    except: pass
        else:
            try:
                await status.edit_text(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
            except:
                await msg.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
                try: await status.delete()
                except: pass

    except Exception as e:
        log.error(f"Download error: {e}")
        try: await status.edit_text(tx(lang,"dl_fail"), parse_mode=ParseMode.HTML)
        except: pass

# ==============================================================================
# ── APP SETUP ──────────────────────────────────────────────────────────────────
# ==============================================================================
ptb = ApplicationBuilder().token(TOKEN).build()
ptb.add_handler(CommandHandler(["start","menu"], cmd_start))
ptb.add_handler(CommandHandler("help",           lambda u,c: on_callback(u,c) or None))
ptb.add_handler(CallbackQueryHandler(on_numpad,  pattern=r"^(np_|chi_)"))
ptb.add_handler(CallbackQueryHandler(on_callback))
ptb.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))

@app.post("/api/main")
async def webhook(req: Request):
    if not ptb.running: await ptb.initialize()
    await load_cfg()
    body = await req.json()
    await ptb.process_update(Update.de_json(body, ptb.bot))
    return {"ok": True}

@app.get("/api/main")
async def health():
    return {"status": "active", "uptime": uptime(), "time": now_str()}
