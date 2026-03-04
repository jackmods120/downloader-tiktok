# ╔══════════════════════════════════════════════════════════════╗
# ║        JACKTIK DOWNLOADER — LEGENDARY EDITION v9.0          ║
# ║        Dev: @j4ck_721s  |  Built From Scratch               ║
# ╚══════════════════════════════════════════════════════════════╝

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
from telegram.error import BadRequest, Forbidden, RetryAfter

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════
TOKEN    = os.getenv("BOT_TOKEN")
DB_URL   = os.getenv("DB_URL")
DB_SEC   = os.getenv("DB_SECRET")
OWNER_ID = 5977475208
DEV      = "@j4ck_721s"
CH_URL   = "https://t.me/jack_721_mod"
API1     = "https://www.api.hyper-bd.site/Tiktok/?url="
API2     = "https://www.tikwm.com/api/?url="
BOOT     = time.time()
SES_TTL  = 600

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)
web = FastAPI()

# ══════════════════════════════════════════════════════════════
# GLOBALS
# ══════════════════════════════════════════════════════════════
ADMINS  : set  = {OWNER_ID}
CHANNELS: list = []
BLOCKED : set  = set()
VIPS    : set  = set()
WAITING : dict = {}   # uid -> state

CFG: dict = {
    "maintenance"  : False,
    "welcome_msg"  : "",
    "default_lang" : "ku",
    "photo_mode"   : "auto",
    "max_photos"   : 10,
    "api_timeout"  : 60,
    "vip_bypass"   : True,
    "admin_bypass" : True,
    "dl_total"     : 0,
    "dl_video"     : 0,
    "dl_audio"     : 0,
    "dl_photo"     : 0,
    "total_users"  : 0,
}

# ══════════════════════════════════════════════════════════════
# LANGUAGES
# ══════════════════════════════════════════════════════════════
T = {
"ku": dict(
    welcome       ="╔══════════════════╗\n"
                   "  👋 <b>سڵاو {name} {badge}</b>\n"
                   "╚══════════════════╝\n\n"
                   "🤖 <b>JackTik — دابەزاندنەری تیکتۆک</b>\n\n"
                   "🎥 ڤیدیۆ بێ لۆگۆ\n"
                   "📸 وێنەکانی Slideshow\n"
                   "🎵 گۆرانی MP3\n\n"
                   "━━━━━━━━━━━━━━━━━━━\n"
                   "👇 لینکەکە بنێرە یان دوگمەیەک بەکاربهێنە:",
    help          ="📚 <b>ڕێنمایی بەکارهێنان</b>\n\n"
                   "<b>📱 چۆن دایبەزێنم؟</b>\n"
                   "1️⃣ لە تیکتۆک Share ← Copy Link\n"
                   "2️⃣ لینکەکە لێرە بنێرە\n"
                   "3️⃣ جۆر هەڵبژێرە و دابەزێنە!\n\n"
                   "<b>📥 چی دەنازانرێت؟</b>\n"
                   "🎥 ڤیدیۆ — بێ لۆگۆ\n"
                   "📸 Slideshow — هەموو وێنەکان\n"
                   "🎵 گۆرانی — MP3\n\n"
                   "💎 VIP بەکارهێنەرەکان بێ جۆین چەناڵ دەتوانن بەکاربێنن\n"
                   "📩 پەیوەندی: {dev}",
    profile       ="╔══════════════════╗\n"
                   "  👤 <b>پرۆفایل</b>\n"
                   "╚══════════════════╝\n\n"
                   "🆔 ئایدی: <code>{uid}</code>\n"
                   "👤 ناو: {name}\n"
                   "🔗 یوزەرنەیم: @{uname}\n"
                   "📅 تۆمار: {date}\n"
                   "💎 VIP: {vip}\n"
                   "📥 داونلۆد: {dl}",
    vip_page      ="╔══════════════════╗\n"
                   "  💎 <b>بەشی VIP</b>\n"
                   "╚══════════════════╝\n\n"
                   "✅ بێ جۆینی ناچاری چەناڵ\n"
                   "✅ خێرایی داونلۆدی زیاتر\n"
                   "✅ داونلۆدی بێسنووری وێنە\n"
                   "✅ گەیشتن بە تایبەتمەندییە تازەکان\n\n"
                   "💳 پەیوەندی بکە: {dev}",
    lang_prompt   ="🌍 <b>زمان هەڵبژێرە</b>",
    force_join    ="🔒 <b>جۆینی ناچاری</b>\n\nبۆ بەکارهێنانی بۆتەکە، تکایە جۆینی ئەم چەناڵانە بکە:",
    searching     ="⏳ <b>دەگەڕێم...</b>",
    found_video   ="✅ <b>دۆزرایەوە!</b>\n\n"
                   "📝 {title}\n"
                   "👤 {owner}\n\n"
                   "👁 <b>{views}</b>   ❤️ <b>{likes}</b>   💬 <b>{comments}</b>",
    found_photo   ="✅ <b>دۆزرایەوە! ({n} وێنە)</b>\n\n"
                   "📝 {title}\n"
                   "👤 {owner}\n\n"
                   "👁 <b>{views}</b>   ❤️ <b>{likes}</b>   💬 <b>{comments}</b>",
    sending_p     ="📸 <b>وێنەکان دێن... ({done}/{total})</b>",
    blocked       ="⛔ ببورە، تۆ بلۆک کراویت.",
    maintenance   ="🛠 بۆتەکە لە چاکسازیدایە. تکایە چاوەڕوان بە!",
    expired       ="⚠️ کاتەکەت تەواو بوو، لینکەکە دووبارە بنێرە.",
    bad_link      ="❌ لینکەکە دروست نییە!",
    dl_err        ="❌ هەڵەیەک ڕوویدا. دووبارە هەوڵبدەوە.",
    no_photo      ="❌ هیچ وێنەیەک نەدۆزرایەوە!",
    no_video      ="❌ ڤیدیۆ نەدۆزرایەوە!",
    no_audio      ="❌ گۆرانی نەدۆزرایەوە!",
    adm_only      ="⛔ تەنیا ئەدمین!",
    own_only      ="⛔ تەنیا خاوەن!",
    bad_id        ="❌ ئایدی دروست نییە!",
    saved         ="✅ ذەخیرەکرا!",
    not_found     ="⚠️ بەکارهێنەر نەدۆزرایەوە.",
    bc_done       ="📢 برۆدکاست تەواو بوو\n✅ گەیشت: <b>{ok}</b>\n❌ نەگەیشت: <b>{fail}</b>",
    no_users      ="📭 هیچ بەکارهێنەرێک نییە.",
    backup_cap    ="💾 <b>بەکئەپ</b>\n🕐 {t}",
    wm_saved      ="✅ نامەی خۆشامەدێ ذەخیرەکرا.",
    msg_sent      ="✅ نامەکە نێردرا.",
    sure          ="⚠️ <b>دڵنیایت؟</b>",
    st_reset      ="✅ ئامارەکان ڕیسێت کران.",
    u_deleted     ="✅ هەموو بەکارهێنەرەکان سڕانەوە.",
    write_wm      ="✍️ نامەی خۆشامەدێ بنووسە:\n<i>{{name}} = ناو، {{badge}} = ئامانج</i>",
    write_msg     ="✍️ نامەکەت بنووسە بۆ بەکارهێنەر <code>{uid}</code>:",
    # buttons
    B_DL    ="📥 دابەزاندن",   B_PROFILE="👤 پرۆفایل",
    B_VIP   ="💎 VIP",         B_SET    ="⚙️ ڕێکخستن",
    B_HELP  ="ℹ️ یارمەتی",     B_CH     ="📢 کەناڵ",
    B_ADMIN ="👑 پانێڵی ئەدمین",B_OWNER ="🔱 پانێڵی خاوەن",
    B_BACK  ="🔙 گەڕانەوە",    B_DEL   ="🗑 سڕینەوە",
    B_REF   ="🔄 نوێکردنەوە",  B_OK    ="✅ دڵنیام",
    B_NO    ="❌ هەڵوەشاندنەوە",B_JOIN  ="✅ جۆینم کرد",
    B_VID   ="🎥 ڤیدیۆ (بێ لۆگۆ)",
    B_PHO   ="📸 وێنەکان ({n} دانە)",
    B_AUD   ="🎵 گۆرانی (MP3)",
    B_KU    ="🔴🔆🟢 کوردی",   B_EN    ="🇺🇸 English",
    B_AR    ="🇸🇦 العربية",
    BADGE_O ="👑 خاوەن", BADGE_A="⚡ ئەدمین", BADGE_V="💎 VIP",
    VIP_Y   ="بەڵێ 💎",  VIP_N  ="نەخێر (Free)",
),
"en": dict(
    welcome       ="╔══════════════════╗\n"
                   "  👋 <b>Hello {name} {badge}</b>\n"
                   "╚══════════════════╝\n\n"
                   "🤖 <b>JackTik — TikTok Downloader</b>\n\n"
                   "🎥 Video without watermark\n"
                   "📸 Slideshow photos\n"
                   "🎵 Audio MP3\n\n"
                   "━━━━━━━━━━━━━━━━━━━\n"
                   "👇 Send a link or press a button:",
    help          ="📚 <b>How to Use</b>\n\n"
                   "<b>📱 How to download?</b>\n"
                   "1️⃣ TikTok → Share → Copy Link\n"
                   "2️⃣ Send the link here\n"
                   "3️⃣ Choose format and download!\n\n"
                   "<b>📥 What can I download?</b>\n"
                   "🎥 Video — no watermark\n"
                   "📸 Slideshow — all photos\n"
                   "🎵 Audio — MP3\n\n"
                   "💎 VIP users can skip channel join\n"
                   "📩 Contact: {dev}",
    profile       ="╔══════════════════╗\n"
                   "  👤 <b>Profile</b>\n"
                   "╚══════════════════╝\n\n"
                   "🆔 ID: <code>{uid}</code>\n"
                   "👤 Name: {name}\n"
                   "🔗 Username: @{uname}\n"
                   "📅 Joined: {date}\n"
                   "💎 VIP: {vip}\n"
                   "📥 Downloads: {dl}",
    vip_page      ="╔══════════════════╗\n"
                   "  💎 <b>VIP Section</b>\n"
                   "╚══════════════════╝\n\n"
                   "✅ No forced channel join\n"
                   "✅ Faster downloads\n"
                   "✅ Unlimited photo downloads\n"
                   "✅ Access to new features\n\n"
                   "💳 Contact: {dev}",
    lang_prompt   ="🌍 <b>Select Language</b>",
    force_join    ="🔒 <b>Forced Join</b>\n\nTo use the bot, please join these channels:",
    searching     ="⏳ <b>Searching...</b>",
    found_video   ="✅ <b>Found!</b>\n\n"
                   "📝 {title}\n"
                   "👤 {owner}\n\n"
                   "👁 <b>{views}</b>   ❤️ <b>{likes}</b>   💬 <b>{comments}</b>",
    found_photo   ="✅ <b>Found! ({n} photos)</b>\n\n"
                   "📝 {title}\n"
                   "👤 {owner}\n\n"
                   "👁 <b>{views}</b>   ❤️ <b>{likes}</b>   💬 <b>{comments}</b>",
    sending_p     ="📸 <b>Sending photos... ({done}/{total})</b>",
    blocked       ="⛔ Sorry, you are blocked.",
    maintenance   ="🛠 Bot is under maintenance. Please wait!",
    expired       ="⚠️ Session expired. Send the link again.",
    bad_link      ="❌ Invalid or blocked link!",
    dl_err        ="❌ An error occurred. Please try again.",
    no_photo      ="❌ No photos found!",
    no_video      ="❌ Video not found!",
    no_audio      ="❌ Audio not found!",
    adm_only      ="⛔ Admins only!",
    own_only      ="⛔ Owner only!",
    bad_id        ="❌ Invalid ID!",
    saved         ="✅ Saved!",
    not_found     ="⚠️ User not found.",
    bc_done       ="📢 Broadcast done\n✅ Sent: <b>{ok}</b>\n❌ Failed: <b>{fail}</b>",
    no_users      ="📭 No users found.",
    backup_cap    ="💾 <b>Backup</b>\n🕐 {t}",
    wm_saved      ="✅ Welcome message saved.",
    msg_sent      ="✅ Message sent.",
    sure          ="⚠️ <b>Are you sure?</b>",
    st_reset      ="✅ Stats reset.",
    u_deleted     ="✅ All users deleted.",
    write_wm      ="✍️ Write welcome message:\n<i>{{name}} = name, {{badge}} = badge</i>",
    write_msg     ="✍️ Write your message to user <code>{uid}</code>:",
    B_DL    ="📥 Download",    B_PROFILE="👤 Profile",
    B_VIP   ="💎 VIP",         B_SET    ="⚙️ Settings",
    B_HELP  ="ℹ️ Help",        B_CH     ="📢 Channel",
    B_ADMIN ="👑 Admin Panel", B_OWNER  ="🔱 Owner Panel",
    B_BACK  ="🔙 Back",        B_DEL    ="🗑 Delete",
    B_REF   ="🔄 Refresh",     B_OK     ="✅ Confirm",
    B_NO    ="❌ Cancel",       B_JOIN   ="✅ I Joined",
    B_VID   ="🎥 Video (No Watermark)",
    B_PHO   ="📸 Photos ({n})",
    B_AUD   ="🎵 Audio (MP3)",
    B_KU    ="🔴🔆🟢 کوردی",   B_EN    ="🇺🇸 English",
    B_AR    ="🇸🇦 العربية",
    BADGE_O ="👑 Owner", BADGE_A="⚡ Admin", BADGE_V="💎 VIP",
    VIP_Y   ="Yes 💎",   VIP_N  ="No (Free)",
),
"ar": dict(
    welcome       ="╔══════════════════╗\n"
                   "  👋 <b>أهلاً {name} {badge}</b>\n"
                   "╚══════════════════╝\n\n"
                   "🤖 <b>JackTik — محمّل تيك توك</b>\n\n"
                   "🎥 فيديو بدون علامة مائية\n"
                   "📸 صور الشرائح\n"
                   "🎵 الصوت MP3\n\n"
                   "━━━━━━━━━━━━━━━━━━━\n"
                   "👇 أرسل رابطاً أو اضغط زراً:",
    help          ="📚 <b>طريقة الاستخدام</b>\n\n"
                   "<b>📱 كيف أحمّل؟</b>\n"
                   "1️⃣ تيك توك → مشاركة → نسخ الرابط\n"
                   "2️⃣ أرسل الرابط هنا\n"
                   "3️⃣ اختر الصيغة وحمّل!\n\n"
                   "<b>📥 ماذا يمكن تحميله؟</b>\n"
                   "🎥 فيديو — بدون علامة\n"
                   "📸 شرائح — جميع الصور\n"
                   "🎵 صوت — MP3\n\n"
                   "💎 مستخدمو VIP لا يحتاجون للاشتراك\n"
                   "📩 تواصل: {dev}",
    profile       ="╔══════════════════╗\n"
                   "  👤 <b>الملف الشخصي</b>\n"
                   "╚══════════════════╝\n\n"
                   "🆔 المعرف: <code>{uid}</code>\n"
                   "👤 الاسم: {name}\n"
                   "🔗 اسم المستخدم: @{uname}\n"
                   "📅 التسجيل: {date}\n"
                   "💎 VIP: {vip}\n"
                   "📥 التنزيلات: {dl}",
    vip_page      ="╔══════════════════╗\n"
                   "  💎 <b>قسم VIP</b>\n"
                   "╚══════════════════╝\n\n"
                   "✅ بدون اشتراك إجباري\n"
                   "✅ سرعة تحميل أعلى\n"
                   "✅ تحميل صور غير محدود\n"
                   "✅ وصول لميزات جديدة\n\n"
                   "💳 تواصل: {dev}",
    lang_prompt   ="🌍 <b>اختر اللغة</b>",
    force_join    ="🔒 <b>اشتراك إجباري</b>\n\nللاستخدام يرجى الانضمام لهذه القنوات:",
    searching     ="⏳ <b>جاري البحث...</b>",
    found_video   ="✅ <b>تم العثور عليه!</b>\n\n"
                   "📝 {title}\n"
                   "👤 {owner}\n\n"
                   "👁 <b>{views}</b>   ❤️ <b>{likes}</b>   💬 <b>{comments}</b>",
    found_photo   ="✅ <b>تم العثور عليه! ({n} صورة)</b>\n\n"
                   "📝 {title}\n"
                   "👤 {owner}\n\n"
                   "👁 <b>{views}</b>   ❤️ <b>{likes}</b>   💬 <b>{comments}</b>",
    sending_p     ="📸 <b>جاري إرسال الصور... ({done}/{total})</b>",
    blocked       ="⛔ عذراً، تم حظرك.",
    maintenance   ="🛠 البوت في وضع الصيانة. يرجى الانتظار!",
    expired       ="⚠️ انتهت الجلسة. أرسل الرابط مجدداً.",
    bad_link      ="❌ الرابط غير صالح!",
    dl_err        ="❌ حدث خطأ. حاول مجدداً.",
    no_photo      ="❌ لا توجد صور!",
    no_video      ="❌ الفيديو غير موجود!",
    no_audio      ="❌ الصوت غير موجود!",
    adm_only      ="⛔ للمسؤولين فقط!",
    own_only      ="⛔ للمالك فقط!",
    bad_id        ="❌ معرف غير صالح!",
    saved         ="✅ تم الحفظ!",
    not_found     ="⚠️ المستخدم غير موجود.",
    bc_done       ="📢 اكتمل الإرسال\n✅ تم: <b>{ok}</b>\n❌ فشل: <b>{fail}</b>",
    no_users      ="📭 لا يوجد مستخدمون.",
    backup_cap    ="💾 <b>نسخة احتياطية</b>\n🕐 {t}",
    wm_saved      ="✅ تم حفظ رسالة الترحيب.",
    msg_sent      ="✅ تم إرسال الرسالة.",
    sure          ="⚠️ <b>هل أنت متأكد؟</b>",
    st_reset      ="✅ تمت إعادة تعيين الإحصائيات.",
    u_deleted     ="✅ تم حذف جميع المستخدمين.",
    write_wm      ="✍️ اكتب رسالة الترحيب:\n<i>{{name}} = الاسم، {{badge}} = الشارة</i>",
    write_msg     ="✍️ اكتب رسالتك للمستخدم <code>{uid}</code>:",
    B_DL    ="📥 تحميل",      B_PROFILE="👤 الملف",
    B_VIP   ="💎 VIP",         B_SET    ="⚙️ الإعدادات",
    B_HELP  ="ℹ️ مساعدة",     B_CH     ="📢 القناة",
    B_ADMIN ="👑 لوحة الأدمن", B_OWNER  ="🔱 لوحة المالك",
    B_BACK  ="🔙 رجوع",        B_DEL    ="🗑 حذف",
    B_REF   ="🔄 تحديث",       B_OK     ="✅ تأكيد",
    B_NO    ="❌ إلغاء",        B_JOIN   ="✅ انضممت",
    B_VID   ="🎥 فيديو (بدون علامة)",
    B_PHO   ="📸 صور ({n})",
    B_AUD   ="🎵 صوت (MP3)",
    B_KU    ="🔴🔆🟢 کوردی",   B_EN    ="🇺🇸 English",
    B_AR    ="🇸🇦 العربية",
    BADGE_O ="👑 المالك", BADGE_A="⚡ مسؤول", BADGE_V="💎 VIP",
    VIP_Y   ="نعم 💎",    VIP_N  ="لا (مجاني)",
),
}

def tx(lang: str, key: str, **kw) -> str:
    d = T.get(lang, T["ku"])
    v = d.get(key, T["ku"].get(key, key))
    try:    return v.format(**kw)
    except: return v

# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════
def rid(n=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

def clean(t: str) -> str:
    if not t: return "TikTok"
    return re.sub(r'[\\/*?:"<>|#@]', "", t)[:80].strip()

def fb(path: str) -> str:
    return f"{DB_URL}/{path}.json?auth={DB_SEC}"

def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def uptime() -> str:
    s = int(time.time() - BOOT)
    d, r = divmod(s, 86400); h, r = divmod(r, 3600); m, s = divmod(r, 60)
    return f"{d}d {h}h {m}m {s}s"

def fnum(n) -> str:
    try:
        n = int(n)
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return str(n)
    except: return "0"

def bk(lang, to="home"):
    return [[InlineKeyboardButton(tx(lang,"B_BACK"), callback_data=to)]]

# ══════════════════════════════════════════════════════════════
# SECURITY
# ══════════════════════════════════════════════════════════════
def is_owner(u): return u == OWNER_ID
def is_admin(u): return u in ADMINS or u == OWNER_ID
def is_vip(u):   return u in VIPS or u == OWNER_ID
def is_blk(u):   return u in BLOCKED
def can_skip(u): return (is_admin(u) and CFG["admin_bypass"]) or (is_vip(u) and CFG["vip_bypass"])

async def check_sub(uid, bot) -> tuple[bool, list]:
    if not CHANNELS: return True, []
    miss = []
    for ch in CHANNELS:
        try:
            m = await bot.get_chat_member(ch, uid)
            if m.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                miss.append(ch)
        except: pass
    return not miss, miss

# ══════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════
async def db_get(path):
    async with httpx.AsyncClient(timeout=12) as c:
        try:
            r = await c.get(fb(path))
            return r.json() if r.status_code == 200 else None
        except: return None

async def db_put(path, data):
    async with httpx.AsyncClient(timeout=12) as c:
        try: await c.put(fb(path), json=data)
        except: pass

async def db_del(path):
    async with httpx.AsyncClient(timeout=12) as c:
        try: await c.delete(fb(path))
        except: pass

async def cfg_load():
    global ADMINS, CHANNELS, BLOCKED, VIPS
    d = await db_get("sys")
    if d:
        ADMINS   = set(d.get("admins",   [OWNER_ID]))
        CHANNELS = d.get("channels", [])
        BLOCKED  = set(d.get("blocked",  []))
        VIPS     = set(d.get("vips",     []))
        CFG.update(d.get("cfg", {}))
        log.info("✅ Config loaded")

async def cfg_save():
    await db_put("sys", {
        "admins":   list(ADMINS),
        "channels": CHANNELS,
        "blocked":  list(BLOCKED),
        "vips":     list(VIPS),
        "cfg":      CFG,
    })

async def u_get(uid) -> dict | None:
    return await db_get(f"users/{uid}")

async def u_put(uid, data):
    await db_put(f"users/{uid}", data)

async def u_field(uid, k, v):
    await db_put(f"users/{uid}/{k}", v)

async def u_exists(uid) -> bool:
    return (await db_get(f"users/{uid}")) is not None

async def u_all_ids() -> list:
    d = await db_get("users")
    return [int(k) for k in d.keys()] if d else []

async def u_all() -> dict:
    return await db_get("users") or {}

async def u_del_all():
    await db_del("users")

async def ses_save(uid, data):
    data["_t"] = int(time.time())
    await db_put(f"ses/{uid}", data)

async def ses_get(uid) -> dict | None:
    d = await db_get(f"ses/{uid}")
    if d and int(time.time()) - d.get("_t", 0) <= SES_TTL:
        return d
    return None

async def get_lang(uid) -> str:
    v = await db_get(f"users/{uid}/lang")
    return str(v) if v else CFG.get("default_lang", "ku")

async def ping_owner(bot, user):
    try:
        await bot.send_message(
            OWNER_ID,
            f"🔔 <b>بەکارهێنەرێکی نوێ!</b>\n"
            f"👤 {html.escape(user.first_name)}\n"
            f"🆔 <code>{user.id}</code>\n"
            f"🔗 @{user.username or '—'}",
            parse_mode=ParseMode.HTML,
        )
    except: pass

# ══════════════════════════════════════════════════════════════
# TIKTOK API ENGINE
# ══════════════════════════════════════════════════════════════
def _clean_imgs(raw: list) -> list:
    out = []
    for x in raw:
        if isinstance(x, str) and x.startswith("http"):
            out.append(x)
        elif isinstance(x, dict):
            u = (
                (x.get("url_list") or [None])[0] or
                x.get("url") or x.get("download_url") or
                ((x.get("display_image") or {}).get("url_list") or [None])[0]
            )
            if u and str(u).startswith("http"):
                out.append(str(u))
    return out

async def api_fetch(url: str) -> dict | None:
    hdrs    = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    timeout = int(CFG.get("api_timeout", 60))

    async with httpx.AsyncClient(timeout=timeout, headers=hdrs, follow_redirects=True) as c:
        # ── Primary ──────────────────────────────────────────────────────────
        try:
            r = await c.get(API1 + url)
            if r.status_code == 200:
                d = r.json()
                if d.get("ok") or d.get("status") == "success":
                    log.info("✅ API1 ok")
                    return {"src": "primary", "raw": d}
        except Exception as e:
            log.warning(f"API1 fail: {e}")

        # ── Backup ───────────────────────────────────────────────────────────
        try:
            r = await c.get(API2 + url)
            if r.status_code == 200:
                raw = r.json()
                if raw.get("code") == 0 and raw.get("data"):
                    d    = raw["data"]
                    imgs = _clean_imgs(d.get("images", []))
                    norm = {
                        "ok": True,
                        "data": {
                            "creator": d.get("author", {}).get("nickname", "Unknown"),
                            "details": {
                                "title" : d.get("title", ""),
                                "cover" : {"cover": d.get("cover", "")},
                                "images": imgs,
                                "video" : {
                                    "play"  : d.get("play", ""),
                                    "wmplay": d.get("wmplay", ""),
                                },
                                "audio" : {"play": d.get("music", "")},
                                "stats" : {
                                    "views"   : d.get("play_count",    0),
                                    "likes"   : d.get("digg_count",    0),
                                    "comments": d.get("comment_count", 0),
                                },
                            },
                        },
                    }
                    log.info(f"✅ API2 ok | imgs={len(imgs)}")
                    return {"src": "backup", "raw": norm}
        except Exception as e:
            log.warning(f"API2 fail: {e}")

    return None

def api_parse(raw: dict) -> tuple[str, dict, list]:
    d       = raw.get("data", {})
    creator = d.get("creator", "Unknown")
    details = d.get("details", {})
    imgs    = _clean_imgs(
        details.get("images") or
        details.get("image_list") or
        d.get("images") or []
    )
    log.info(f"🖼 imgs={len(imgs)}")
    return creator, details, imgs

def is_photo(imgs: list) -> bool:
    m = CFG.get("photo_mode", "auto")
    if m == "force_video": return False
    if m == "force_photo": return True
    return len(imgs) > 0

def get_cover(details: dict, imgs: list, photo_post: bool) -> str:
    if photo_post and imgs:
        return imgs[0]
    cd = details.get("cover", {})
    if isinstance(cd, dict):
        return cd.get("cover") or cd.get("origin_cover") or cd.get("dynamic_cover") or ""
    return str(cd) if cd else ""

# ══════════════════════════════════════════════════════════════
# INLINE NUMPAD
# ══════════════════════════════════════════════════════════════
def numpad(act: str, buf: str = "") -> InlineKeyboardMarkup:
    disp = f"📟  <code>{buf}</code>" if buf else "📟  —"
    rows = [
        [InlineKeyboardButton(str(n), callback_data=f"np_{act}_{n}") for n in [1,2,3]],
        [InlineKeyboardButton(str(n), callback_data=f"np_{act}_{n}") for n in [4,5,6]],
        [InlineKeyboardButton(str(n), callback_data=f"np_{act}_{n}") for n in [7,8,9]],
        [
            InlineKeyboardButton("⌫",  callback_data=f"np_{act}_back"),
            InlineKeyboardButton("0",  callback_data=f"np_{act}_0"),
            InlineKeyboardButton("✅", callback_data=f"np_{act}_ok"),
        ],
        [InlineKeyboardButton("❌ Cancel / هەڵوەشاندنەوە", callback_data="np_x")],
    ]
    return InlineKeyboardMarkup(rows)

def chpad() -> InlineKeyboardMarkup:
    alpha = "abcdefghijklmnopqrstuvwxyz"
    rows  = []
    for i in range(0, len(alpha), 5):
        rows.append([InlineKeyboardButton(c, callback_data=f"cp_{c}") for c in alpha[i:i+5]])
    rows.append([InlineKeyboardButton(str(n), callback_data=f"cp_{n}") for n in range(0,5)])
    rows.append([InlineKeyboardButton(str(n), callback_data=f"cp_{n}") for n in range(5,10)])
    rows.append([
        InlineKeyboardButton("_",  callback_data="cp__"),
        InlineKeyboardButton(".",  callback_data="cp_."),
        InlineKeyboardButton("⌫", callback_data="cp_back"),
        InlineKeyboardButton("✅ OK", callback_data="cp_ok"),
    ])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="np_x")])
    return InlineKeyboardMarkup(rows)

# ══════════════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    uid   = user.id
    is_cb = bool(update.callback_query)
    lang  = await get_lang(uid)

    async def reply(txt, kb):
        mu = InlineKeyboardMarkup(kb)
        if is_cb:
            try:   await update.callback_query.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=mu)
            except BadRequest:
                   await update.callback_query.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=mu)
        else:
            await update.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=mu)

    if is_blk(uid):
        await reply(tx(lang, "blocked"), bk(lang)); return

    if CFG["maintenance"] and not is_admin(uid):
        await reply(tx(lang, "maintenance"), bk(lang)); return

    # Register new user
    if not is_admin(uid) and not await u_exists(uid):
        asyncio.create_task(ping_owner(ctx.bot, user))
        CFG["total_users"] = CFG.get("total_users", 0) + 1
        await u_put(uid, {
            "name": user.first_name,
            "uname": user.username or "",
            "date": now(),
            "vip": False,
            "lang": CFG.get("default_lang", "ku"),
            "dl": 0,
        })

    # Join check
    joined, miss = await check_sub(uid, ctx.bot)
    if not joined and not can_skip(uid):
        kb  = [[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in miss]
        kb += [[InlineKeyboardButton(tx(lang, "B_JOIN"), callback_data="sub_check")]]
        await reply(tx(lang, "force_join"), kb); return

    # Badge
    if is_owner(uid):   badge = tx(lang, "BADGE_O")
    elif is_admin(uid): badge = tx(lang, "BADGE_A")
    elif is_vip(uid):   badge = tx(lang, "BADGE_V")
    else:               badge = ""

    wm = CFG.get("welcome_msg", "")
    if wm and not is_admin(uid):
        txt = wm.replace("{name}", html.escape(user.first_name)).replace("{badge}", badge)
    else:
        txt = tx(lang, "welcome", name=html.escape(user.first_name), badge=badge)

    kb = [
        [InlineKeyboardButton(tx(lang,"B_DL"), callback_data="ask_link")],
        [
            InlineKeyboardButton(tx(lang,"B_PROFILE"), callback_data="pg_profile"),
            InlineKeyboardButton(tx(lang,"B_VIP"),     callback_data="pg_vip"),
        ],
        [
            InlineKeyboardButton(tx(lang,"B_SET"),  callback_data="pg_settings"),
            InlineKeyboardButton(tx(lang,"B_HELP"), callback_data="pg_help"),
        ],
        [InlineKeyboardButton(tx(lang,"B_CH"), url=CH_URL)],
    ]
    if is_admin(uid): kb.append([InlineKeyboardButton(tx(lang,"B_ADMIN"), callback_data="adm_home")])
    if is_owner(uid): kb.append([InlineKeyboardButton(tx(lang,"B_OWNER"), callback_data="own_home")])
    await reply(txt, kb)

# ══════════════════════════════════════════════════════════════
# CALLBACK ROUTER
# ══════════════════════════════════════════════════════════════
async def on_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    d    = q.data
    uid  = q.from_user.id
    lang = await get_lang(uid)
    await q.answer()

    # ── Navigation ────────────────────────────────────────────────────────────
    if d in ("home", "sub_check"):
        await cmd_start(update, ctx); return

    if d == "ask_link":
        await q.message.reply_text(
            "🔗 لینکی تیکتۆکەکە بنێرە:" if lang == "ku"
            else "🔗 Send TikTok link:" if lang == "en"
            else "🔗 أرسل رابط تيك توك:",
            reply_markup=ForceReply(selective=True),
        ); return

    if d == "close":
        try: await q.message.delete()
        except: pass
        return

    # ── Pages ─────────────────────────────────────────────────────────────────
    if d == "pg_profile":
        ud = await u_get(uid) or {}
        await q.edit_message_text(
            tx(lang, "profile",
               uid=f"<code>{uid}</code>",
               name=html.escape(q.from_user.first_name),
               uname=q.from_user.username or "—",
               date=ud.get("date","—"),
               vip=tx(lang,"VIP_Y") if is_vip(uid) else tx(lang,"VIP_N"),
               dl=ud.get("dl",0),
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(bk(lang)),
        ); return

    if d == "pg_vip":
        await q.edit_message_text(
            tx(lang, "vip_page", dev=DEV),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(bk(lang)),
        ); return

    if d == "pg_help":
        await q.edit_message_text(
            tx(lang, "help", dev=DEV),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(bk(lang)),
        ); return

    if d == "pg_settings":
        kb = [
            [InlineKeyboardButton(tx(lang,"B_KU"), callback_data="lng_ku")],
            [InlineKeyboardButton(tx(lang,"B_EN"), callback_data="lng_en")],
            [InlineKeyboardButton(tx(lang,"B_AR"), callback_data="lng_ar")],
            *bk(lang),
        ]
        await q.edit_message_text(
            tx(lang, "lang_prompt"),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if d.startswith("lng_"):
        nl = d[4:]
        await u_field(uid, "lang", nl)
        await q.answer(f"✅ {nl.upper()}", show_alert=True)
        await cmd_start(update, ctx); return

    # ── Download ───────────────────────────────────────────────────────────────
    if d.startswith("dl_"):
        act  = d[3:]
        sess = await ses_get(uid)
        if not sess:
            await q.answer(tx(lang, "expired"), show_alert=True); return

        creator = sess.get("creator", "")
        details = sess.get("details", {})
        imgs    = sess.get("imgs", [])
        title   = clean(details.get("title", ""))
        cap     = (
            f"🎬 <b>{html.escape(title)}</b>\n"
            f"👤 <b>{html.escape(str(creator))}</b>\n\n"
            f"🤖 @{ctx.bot.username}"
        )
        del_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang,"B_DEL"), callback_data="close")]])

        # Photos ──────────────────────────────────────────────────────────────
        if act == "photo":
            if not imgs:
                await q.answer(tx(lang,"no_photo"), show_alert=True); return

            CFG["dl_total"] = CFG.get("dl_total",0)+1
            CFG["dl_photo"] = CFG.get("dl_photo",0)+1
            await cfg_save()
            ud = await u_get(uid) or {}
            await u_field(uid, "dl", ud.get("dl",0)+1)

            try: await q.message.delete()
            except: pass

            max_p   = int(CFG.get("max_photos", 10))
            to_send = imgs[:max_p]
            total   = len(to_send)
            chunks  = [to_send[i:i+10] for i in range(0, total, 10)]
            wait    = await ctx.bot.send_message(uid, tx(lang,"sending_p",done=0,total=total), parse_mode=ParseMode.HTML)
            sent    = 0

            for chunk in chunks:
                mg = [InputMediaPhoto(u) for u in chunk]
                if sent == 0:
                    mg[0].caption    = cap
                    mg[0].parse_mode = ParseMode.HTML
                try:
                    await ctx.bot.send_media_group(uid, mg)
                    sent += len(chunk)
                    try: await wait.edit_text(tx(lang,"sending_p",done=sent,total=total), parse_mode=ParseMode.HTML)
                    except: pass
                except Exception as e:
                    log.error(f"media_group: {e}")
                    for u in chunk:
                        try:
                            await ctx.bot.send_photo(uid, u, caption=cap if sent==0 else "", parse_mode=ParseMode.HTML)
                            sent += 1
                        except Exception as e2:
                            log.error(f"send_photo: {e2}")
                await asyncio.sleep(0.6)

            try: await wait.delete()
            except: pass
            if not sent:
                links = "\n".join([f"🖼 <a href='{u}'>وێنەی {i+1}</a>" for i,u in enumerate(to_send[:10])])
                await ctx.bot.send_message(uid, f"⚠️ لینکەکان:\n{links}", parse_mode=ParseMode.HTML)

        # Video ───────────────────────────────────────────────────────────────
        elif act == "video":
            vurl = details.get("video",{}).get("play","") or details.get("video",{}).get("wmplay","")
            if not vurl:
                await q.answer(tx(lang,"no_video"), show_alert=True); return

            CFG["dl_total"] = CFG.get("dl_total",0)+1
            CFG["dl_video"] = CFG.get("dl_video",0)+1
            await cfg_save()
            ud = await u_get(uid) or {}
            await u_field(uid, "dl", ud.get("dl",0)+1)

            try:
                await q.message.edit_media(
                    InputMediaVideo(vurl, caption=cap, parse_mode=ParseMode.HTML),
                    reply_markup=del_kb,
                )
            except Exception as e:
                log.error(f"edit_media video: {e}")
                try: await q.message.delete()
                except: pass
                try:
                    await ctx.bot.send_video(uid, vurl, caption=cap, parse_mode=ParseMode.HTML, reply_markup=del_kb)
                except:
                    await ctx.bot.send_message(uid, f"📥 <a href='{vurl}'>داونلۆد</a>", parse_mode=ParseMode.HTML)

        # Audio ───────────────────────────────────────────────────────────────
        elif act == "audio":
            aurl = details.get("audio",{}).get("play","") or details.get("audio",{}).get("music","")
            if not aurl:
                await q.answer(tx(lang,"no_audio"), show_alert=True); return

            CFG["dl_total"] = CFG.get("dl_total",0)+1
            CFG["dl_audio"] = CFG.get("dl_audio",0)+1
            await cfg_save()
            ud = await u_get(uid) or {}
            await u_field(uid, "dl", ud.get("dl",0)+1)

            try:
                await q.message.edit_media(
                    InputMediaAudio(aurl, caption=cap, parse_mode=ParseMode.HTML,
                                    title=f"{DEV}-{rid()}", performer=DEV),
                    reply_markup=del_kb,
                )
            except Exception as e:
                log.error(f"edit_media audio: {e}")
                try: await q.message.delete()
                except: pass
                try:
                    await ctx.bot.send_audio(uid, aurl, caption=cap, parse_mode=ParseMode.HTML,
                                             title=f"{DEV}-{rid()}", performer=DEV, reply_markup=del_kb)
                except:
                    await ctx.bot.send_message(uid, f"🎵 <a href='{aurl}'>داونلۆد</a>", parse_mode=ParseMode.HTML)
        return

    # ══════════════════════════════════════════════════════════
    # ADMIN PANEL
    # ══════════════════════════════════════════════════════════
    if not is_admin(uid):
        await q.answer(tx(lang,"adm_only"), show_alert=True); return

    # Home
    if d == "adm_home":
        uids = await u_all_ids()
        mn   = "🔴 ON" if CFG["maintenance"] else "🟢 OFF"
        kb = [
            [InlineKeyboardButton("📊 ئامار",        callback_data="adm_stats"),
             InlineKeyboardButton("📢 برۆدکاست",     callback_data="adm_bc")],
            [InlineKeyboardButton("📢 چەناڵەکان",    callback_data="adm_chs"),
             InlineKeyboardButton("🚫 بلۆکەکان",     callback_data="adm_blk")],
            [InlineKeyboardButton("💎 VIP",           callback_data="adm_vip"),
             InlineKeyboardButton(f"🛠 چاکسازی:{mn}", callback_data="adm_maint")],
            [InlineKeyboardButton("👤 زانیاری کەس",  callback_data="adm_uinfo"),
             InlineKeyboardButton("✉️ نامە بنێرە",    callback_data="adm_umsg")],
            *bk(lang),
        ]
        await q.edit_message_text(
            f"👑 <b>پانێڵی ئەدمین</b>\n\n"
            f"👥 بەکارهێنەر: <b>{len(uids)}</b> | 🛠 {mn}\n"
            f"📥 داونلۆد: <b>{fnum(CFG.get('dl_total',0))}</b>\n"
            f"🕐 {now()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if d == "adm_stats":
        uids = await u_all_ids()
        await q.edit_message_text(
            f"📊 <b>ئامار</b>\n\n"
            f"👥 بەکارهێنەر: <b>{len(uids)}</b>\n"
            f"💎 VIP: <b>{len(VIPS)}</b>\n"
            f"⚡ ئەدمین: <b>{len(ADMINS)}</b>\n"
            f"🚫 بلۆک: <b>{len(BLOCKED)}</b>\n"
            f"📢 چەناڵ: <b>{len(CHANNELS)}</b>\n\n"
            f"📥 کۆی داونلۆد: <b>{fnum(CFG.get('dl_total',0))}</b>\n"
            f"🎥 ڤیدیۆ: <b>{fnum(CFG.get('dl_video',0))}</b>\n"
            f"🎵 گۆرانی: <b>{fnum(CFG.get('dl_audio',0))}</b>\n"
            f"📸 وێنە: <b>{fnum(CFG.get('dl_photo',0))}</b>\n\n"
            f"⏱ Uptime: {uptime()}\n🕐 {now()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tx(lang,"B_REF"), callback_data="adm_stats")],
                *bk(lang,"adm_home"),
            ]),
        ); return

    if d == "adm_maint":
        if not is_owner(uid):
            await q.answer(tx(lang,"own_only"), show_alert=True); return
        CFG["maintenance"] = not CFG["maintenance"]
        await cfg_save()
        await q.answer(f"🛠 {'ON 🔴' if CFG['maintenance'] else 'OFF 🟢'}", show_alert=True)
        q.data = "adm_home"; await on_cb(update, ctx); return

    # Broadcast
    if d == "adm_bc":
        kb = [
            [InlineKeyboardButton("📢 هەمووان",   callback_data="bc_all"),
             InlineKeyboardButton("💎 VIP",        callback_data="bc_vip")],
            [InlineKeyboardButton("🆓 Free",        callback_data="bc_free"),
             InlineKeyboardButton("✅ ئەنبلۆک",    callback_data="bc_noblk")],
            *bk(lang,"adm_home"),
        ]
        await q.edit_message_text(
            "📢 <b>برۆدکاست</b>\n\nکێ دەوێیت پێبگات؟",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if d.startswith("bc_"):
        WAITING[uid] = f"bc_{d[3:]}"
        await q.edit_message_text(
            "✍️ نامەکەت بنێرە (هەر جۆرێک):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ هەڵوەشاندنەوە", callback_data="adm_bc")
            ]]),
        ); return

    # Channels
    if d == "adm_chs":
        cl = "\n".join(f"• <code>{c}</code>" for c in CHANNELS) or "📭 هیچ چەناڵێک نییە"
        kb = [
            [InlineKeyboardButton("➕ زیادکردن",  callback_data="ch_add"),
             InlineKeyboardButton("➖ لابردن",    callback_data="ch_rm")],
            *bk(lang,"adm_home"),
        ]
        await q.edit_message_text(
            f"📢 <b>چەناڵەکان</b>\n\n{cl}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if d == "ch_add":
        ctx.user_data["ch_buf"] = "@"
        await q.edit_message_text(
            "📢 ناوی چەناڵ داخڵ بکە:\n<code>@</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=chpad(),
        ); return

    if d == "ch_rm":
        if not CHANNELS:
            await q.answer("📭 هیچ چەناڵێک نییە!", show_alert=True); return
        kb  = [[InlineKeyboardButton(f"❌ {c}", callback_data=f"chdel_{c}")] for c in CHANNELS]
        kb += bk(lang,"adm_chs")
        await q.edit_message_text("چەناڵێک هەڵبژێرە:",
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if d.startswith("chdel_"):
        ch = d[6:]
        if ch in CHANNELS: CHANNELS.remove(ch)
        await cfg_save()
        await q.edit_message_text(f"✅ لابرا: <code>{ch}</code>",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(bk(lang,"adm_chs"))); return

    # Block
    if d == "adm_blk":
        bl = "\n".join(f"• <code>{x}</code>" for x in BLOCKED) or "📭 بلۆک نییە"
        kb = [
            [InlineKeyboardButton("🚫 بلۆک",   callback_data="blk_add"),
             InlineKeyboardButton("✅ ئەنبلۆک", callback_data="blk_rm")],
            *bk(lang,"adm_home"),
        ]
        await q.edit_message_text(f"🚫 <b>بلۆک کراوەکان</b>\n\n{bl}",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if d == "blk_add":
        ctx.user_data.update({"np_act":"blk_add","np_buf":""})
        await q.edit_message_text("🚫 ئایدی داخڵ بکە:",
                                  reply_markup=numpad("blk_add","")); return

    if d == "blk_rm":
        ctx.user_data.update({"np_act":"blk_rm","np_buf":""})
        await q.edit_message_text("✅ ئایدی داخڵ بکە:",
                                  reply_markup=numpad("blk_rm","")); return

    # VIP
    if d == "adm_vip":
        vl = "\n".join(f"• <code>{x}</code>" for x in VIPS) or "📭 VIP نییە"
        kb = [
            [InlineKeyboardButton("➕ زیادکردن", callback_data="vip_add"),
             InlineKeyboardButton("➖ لابردن",   callback_data="vip_rm")],
            *bk(lang,"adm_home"),
        ]
        await q.edit_message_text(f"💎 <b>VIP</b>\n\n{vl}",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if d == "vip_add":
        ctx.user_data.update({"np_act":"vip_add","np_buf":""})
        await q.edit_message_text("💎 ئایدی داخڵ بکە:",
                                  reply_markup=numpad("vip_add","")); return

    if d == "vip_rm":
        ctx.user_data.update({"np_act":"vip_rm","np_buf":""})
        await q.edit_message_text("➖ ئایدی داخڵ بکە:",
                                  reply_markup=numpad("vip_rm","")); return

    if d == "adm_uinfo":
        ctx.user_data.update({"np_act":"uinfo","np_buf":""})
        await q.edit_message_text("👤 ئایدی داخڵ بکە:",
                                  reply_markup=numpad("uinfo","")); return

    if d == "adm_umsg":
        ctx.user_data.update({"np_act":"umsg","np_buf":""})
        await q.edit_message_text("✉️ ئایدی داخڵ بکە:",
                                  reply_markup=numpad("umsg","")); return

    # Quick actions (from user info card)
    if d.startswith("qa_"):
        parts = d.split("_")
        act2  = parts[1]
        tid   = int(parts[2])
        if act2 == "blk":
            if tid in BLOCKED: BLOCKED.discard(tid); await q.answer(f"✅ ئەنبلۆک: {tid}", show_alert=True)
            else:               BLOCKED.add(tid);    await q.answer(f"🚫 بلۆک: {tid}",    show_alert=True)
            await cfg_save()
        elif act2 == "vip":
            if tid in VIPS:
                VIPS.discard(tid); await u_field(tid,"vip",False); await q.answer(f"VIP لابرا: {tid}", show_alert=True)
            else:
                VIPS.add(tid);    await u_field(tid,"vip",True);  await q.answer(f"VIP زیادکرا: {tid}", show_alert=True)
            await cfg_save()
        elif act2 == "msg":
            WAITING[uid] = f"sendmsg_{tid}"
            await q.message.reply_text(
                tx(lang,"write_msg",uid=f"<code>{tid}</code>"),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌",callback_data="np_x")]]),
            )
        return

    # ══════════════════════════════════════════════════════════
    # OWNER PANEL
    # ══════════════════════════════════════════════════════════
    if not is_owner(uid):
        await q.answer(tx(lang,"own_only"), show_alert=True); return

    if d == "own_home":
        kb = [
            [InlineKeyboardButton("👥 ئەدمینەکان",       callback_data="own_admins"),
             InlineKeyboardButton("📊 ئاماری پێشکەوتوو", callback_data="own_adv")],
            [InlineKeyboardButton("⚙️ ڕێکخستن",          callback_data="own_cfg"),
             InlineKeyboardButton("📝 نامەی خۆشامەدێ",   callback_data="own_wm")],
            [InlineKeyboardButton("💾 بەکئەپ",            callback_data="own_bak"),
             InlineKeyboardButton("📋 لیستی بەکارهێنەر", callback_data="own_lst")],
            [InlineKeyboardButton("🗑 ڕیسێتی ئامار",     callback_data="own_rst_st"),
             InlineKeyboardButton("☢️ سڕینەوەی بەکارهێنەر",callback_data="own_rst_u")],
            [InlineKeyboardButton("🔧 تاقیکردنەوەی API", callback_data="own_api"),
             InlineKeyboardButton("🌐 زمانی پێشواز",      callback_data="own_deflng")],
            [InlineKeyboardButton("📈 ریپۆرتی ڕۆژانە",   callback_data="own_rep"),
             InlineKeyboardButton("📣 بڕۆدکاست",         callback_data="adm_bc")],
            *bk(lang),
        ]
        await q.edit_message_text(
            f"🔱 <b>پانێڵی خاوەن</b>\n\n"
            f"👑 <code>{OWNER_ID}</code>\n"
            f"⏱ {uptime()} | 🕐 {now()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb),
        ); return

    if d == "own_admins":
        al = "\n".join(f"• <code>{x}</code>" for x in ADMINS if x != OWNER_ID) or "📭 هیچ ئەدمینێک نییە"
        kb = [
            [InlineKeyboardButton("➕ زیادکردن", callback_data="adm_add"),
             InlineKeyboardButton("➖ لابردن",   callback_data="adm_rm")],
            *bk(lang,"own_home"),
        ]
        await q.edit_message_text(f"👥 <b>ئەدمینەکان</b>\n\n{al}",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    if d == "adm_add":
        ctx.user_data.update({"np_act":"adm_add","np_buf":""})
        await q.edit_message_text("➕ ئایدی داخڵ بکە:",
                                  reply_markup=numpad("adm_add","")); return

    if d == "adm_rm":
        ctx.user_data.update({"np_act":"adm_rm","np_buf":""})
        await q.edit_message_text("➖ ئایدی داخڵ بکە:",
                                  reply_markup=numpad("adm_rm","")); return

    if d == "own_adv":
        all_d  = await u_all()
        tot_dl = sum(v.get("dl",0) for v in all_d.values() if isinstance(v,dict))
        await q.edit_message_text(
            f"📊 <b>ئاماری پێشکەوتوو</b>\n\n"
            f"👥 کۆی گشتی: <b>{len(all_d)}</b>\n"
            f"💎 VIP: <b>{len(VIPS)}</b>\n"
            f"⚡ ئەدمین: <b>{len(ADMINS)}</b>\n"
            f"🚫 بلۆک: <b>{len(BLOCKED)}</b>\n"
            f"📢 چەناڵ: <b>{len(CHANNELS)}</b>\n\n"
            f"📥 داونلۆد (سیستەم): <b>{fnum(CFG.get('dl_total',0))}</b>\n"
            f"📥 داونلۆد (بەکارهێنەر): <b>{fnum(tot_dl)}</b>\n"
            f"🎥 ڤیدیۆ: <b>{fnum(CFG.get('dl_video',0))}</b>\n"
            f"🎵 گۆرانی: <b>{fnum(CFG.get('dl_audio',0))}</b>\n"
            f"📸 وێنە: <b>{fnum(CFG.get('dl_photo',0))}</b>\n\n"
            f"📸 Photo Mode: <b>{CFG.get('photo_mode','auto')}</b>\n"
            f"📸 Max Photos: <b>{CFG.get('max_photos',10)}</b>\n"
            f"⏱ API Timeout: <b>{CFG.get('api_timeout',60)}s</b>\n"
            f"💎 VIP Bypass: {'✅' if CFG.get('vip_bypass') else '❌'}\n"
            f"⚡ Admin Bypass: {'✅' if CFG.get('admin_bypass') else '❌'}\n\n"
            f"⏱ Uptime: {uptime()} | 🕐 {now()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄", callback_data="own_adv")],
                *bk(lang,"own_home"),
            ]),
        ); return

    if d == "own_cfg":
        kb = [
            [InlineKeyboardButton(
                f"🛠 چاکسازی: {'🔴 ON' if CFG['maintenance'] else '🟢 OFF'}",
                callback_data="cfg_maint")],
            [InlineKeyboardButton(
                f"📸 Photo Mode: {CFG.get('photo_mode','auto')}",
                callback_data="cfg_pm")],
            [InlineKeyboardButton(
                f"💎 VIP Bypass: {'✅' if CFG.get('vip_bypass') else '❌'}",
                callback_data="cfg_vbp")],
            [InlineKeyboardButton(
                f"⚡ Admin Bypass: {'✅' if CFG.get('admin_bypass') else '❌'}",
                callback_data="cfg_abp")],
            [InlineKeyboardButton(
                f"📸 Max Photos: {CFG.get('max_photos',10)}",
                callback_data="cfg_maxp")],
            [InlineKeyboardButton(
                f"⏱ API Timeout: {CFG.get('api_timeout',60)}s",
                callback_data="cfg_tout")],
            *bk(lang,"own_home"),
        ]
        await q.edit_message_text("⚙️ <b>ڕێکخستنی بۆت</b>",
                                  parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    for ci, ck, cv in [
        ("cfg_maint", "maintenance",  None),
        ("cfg_vbp",   "vip_bypass",   None),
        ("cfg_abp",   "admin_bypass", None),
    ]:
        if d == ci:
            CFG[ck] = not CFG.get(ck, True)
            await cfg_save()
            await q.answer(f"{ck} → {'ON' if CFG[ck] else 'OFF'}", show_alert=True)
            q.data = "own_cfg"; await on_cb(update, ctx); return

    if d == "cfg_pm":
        modes = ["auto","force_photo","force_video"]
        CFG["photo_mode"] = modes[(modes.index(CFG.get("photo_mode","auto"))+1)%3]
        await cfg_save()
        await q.answer(f"Photo Mode → {CFG['photo_mode']}", show_alert=True)
        q.data = "own_cfg"; await on_cb(update, ctx); return

    if d == "cfg_maxp":
        ctx.user_data.update({"np_act":"set_maxp","np_buf":""})
        await q.edit_message_text(f"📸 Max: {CFG.get('max_photos',10)}\nژمارەی نوێ:",
                                  reply_markup=numpad("set_maxp","")); return

    if d == "cfg_tout":
        ctx.user_data.update({"np_act":"set_tout","np_buf":""})
        await q.edit_message_text(f"⏱ Timeout: {CFG.get('api_timeout',60)}s\nچرکەی نوێ:",
                                  reply_markup=numpad("set_tout","")); return

    if d == "own_wm":
        WAITING[uid] = "set_wm"
        cur = CFG.get("welcome_msg","") or "<i>(بەکارنەهاتوو)</i>"
        await q.edit_message_text(
            f"📝 <b>ئێستا:</b>\n{cur}\n\n{tx(lang,'write_wm')}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 سڕینەوە", callback_data="wm_clear")],
                *bk(lang,"own_home"),
            ]),
        ); return

    if d == "wm_clear":
        CFG["welcome_msg"] = ""; await cfg_save()
        await q.edit_message_text("✅ سڕایەوە.",
                                  reply_markup=InlineKeyboardMarkup(bk(lang,"own_home"))); return

    if d == "own_bak":
        await q.answer("⏳...", show_alert=False)
        all_d = await u_all()
        bio = io.BytesIO(json.dumps({
            "time":now(), "cfg":CFG,
            "admins":list(ADMINS), "channels":CHANNELS,
            "blocked":list(BLOCKED), "vips":list(VIPS),
            "total_users":len(all_d),
        }, ensure_ascii=False, indent=2).encode())
        bio.name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            await ctx.bot.send_document(uid, bio,
                caption=tx(lang,"backup_cap",t=now()), parse_mode=ParseMode.HTML)
        except Exception as e:
            await q.message.reply_text(f"❌ {e}")
        return

    if d == "own_lst":
        all_d = await u_all()
        if not all_d: await q.answer(tx(lang,"no_users"),show_alert=True); return
        lines = []
        for uid2, info in list(all_d.items())[:50]:
            if not isinstance(info,dict): continue
            vm = "💎" if info.get("vip") else ""
            bm = "🚫" if int(uid2) in BLOCKED else ""
            nm = html.escape(str(info.get("name","?")))[:18]
            lines.append(f"{vm}{bm} <code>{uid2}</code> {nm}")
        tot  = len(all_d)
        text = f"📋 <b>لیستی بەکارهێنەرەکان ({tot})</b>\n\n" + "\n".join(lines)
        if tot > 50: text += f"\n<i>...و {tot-50} کەسی تر</i>"
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(bk(lang,"own_home"))); return

    for rst_d, rst_cb, rst_k, rst_fn in [
        ("own_rst_st","own_rst_st_do","confirm_stats",  "stats"),
        ("own_rst_u", "own_rst_u_do", "confirm_users",  "users"),
    ]:
        if d == rst_d:
            kb = [[InlineKeyboardButton(tx(lang,"B_OK"), callback_data=rst_cb),
                   InlineKeyboardButton(tx(lang,"B_NO"), callback_data="own_home")]]
            await q.edit_message_text(tx(lang,"sure"), parse_mode=ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(kb)); return

    if d == "own_rst_st_do":
        for k in ("dl_total","dl_video","dl_audio","dl_photo"): CFG[k] = 0
        await cfg_save()
        await q.edit_message_text(tx(lang,"st_reset"), parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(bk(lang,"own_home"))); return

    if d == "own_rst_u_do":
        await u_del_all()
        await q.edit_message_text(tx(lang,"u_deleted"), parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(bk(lang,"own_home"))); return

    if d == "own_api":
        await q.answer("⏳...", show_alert=False)
        res = await api_fetch("https://www.tiktok.com/@tiktok/video/6584647400055385349")
        st  = f"✅ کار دەکات — Source: {res.get('src')}" if res else "❌ کار ناکات!"
        await q.edit_message_text(f"{st}\n🕐 {now()}", parse_mode=ParseMode.HTML,
                                  reply_markup=InlineKeyboardMarkup(bk(lang,"own_home"))); return

    if d == "own_deflng":
        kb = [
            [InlineKeyboardButton(tx(lang,"B_KU"), callback_data="dfl_ku")],
            [InlineKeyboardButton(tx(lang,"B_EN"), callback_data="dfl_en")],
            [InlineKeyboardButton(tx(lang,"B_AR"), callback_data="dfl_ar")],
            *bk(lang,"own_home"),
        ]
        await q.edit_message_text("🌐 زمانی پێشواز هەڵبژێرە:",
                                  reply_markup=InlineKeyboardMarkup(kb)); return

    for dl in ("ku","en","ar"):
        if d == f"dfl_{dl}":
            CFG["default_lang"] = dl; await cfg_save()
            await q.answer(f"✅ {dl.upper()}", show_alert=True)
            q.data = "own_home"; await on_cb(update, ctx); return

    if d == "own_rep":
        uids = await u_all_ids()
        await q.edit_message_text(
            f"📈 <b>ریپۆرتی ڕۆژانە</b>\n\n"
            f"🕐 {now()}\n━━━━━━━━━━━━━━━━━━━\n"
            f"👥 بەکارهێنەر: <b>{len(uids)}</b>\n"
            f"📥 داونلۆد: <b>{fnum(CFG.get('dl_total',0))}</b>\n"
            f"🎥 ڤیدیۆ: <b>{fnum(CFG.get('dl_video',0))}</b>\n"
            f"📸 وێنە: <b>{fnum(CFG.get('dl_photo',0))}</b>\n"
            f"🎵 گۆرانی: <b>{fnum(CFG.get('dl_audio',0))}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💎 VIP: <b>{len(VIPS)}</b>\n"
            f"🚫 بلۆک: <b>{len(BLOCKED)}</b>\n"
            f"⚡ ئەدمین: <b>{len(ADMINS)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Uptime: {uptime()}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄",callback_data="own_rep")],
                *bk(lang,"own_home"),
            ]),
        ); return

# ══════════════════════════════════════════════════════════════
# NUMPAD HANDLER
# ══════════════════════════════════════════════════════════════
async def on_np(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    d    = q.data
    uid  = q.from_user.id
    lang = await get_lang(uid)
    await q.answer()

    if d == "np_x":
        ctx.user_data.pop("np_act", None)
        ctx.user_data.pop("np_buf", None)
        ctx.user_data.pop("ch_buf", None)
        try: await q.message.delete()
        except: pass
        return

    # Channel pad
    if d.startswith("cp_"):
        key = d[3:]
        buf = ctx.user_data.get("ch_buf", "@")
        if key == "back":
            buf = buf[:-1] if len(buf) > 1 else buf
        elif key == "ok":
            ch = buf if buf.startswith("@") else f"@{buf}"
            if len(ch) < 3: await q.answer("❌ کورتە!", show_alert=True); return
            ctx.user_data.pop("ch_buf", None)
            if ch not in CHANNELS: CHANNELS.append(ch)
            await cfg_save()
            await q.edit_message_text(f"✅ زیادکرا: <code>{ch}</code>",
                                      parse_mode=ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(bk(lang,"adm_chs"))); return
        else:
            if len(buf) < 33: buf += key
        ctx.user_data["ch_buf"] = buf
        try:
            await q.edit_message_text(f"📢 ناو: <code>{buf}</code>",
                                      parse_mode=ParseMode.HTML, reply_markup=chpad())
        except: pass
        return

    # Numpad
    if d.startswith("np_"):
        parts = d.split("_", 2)
        if len(parts) < 3: return
        act, key = parts[1], parts[2]
        buf = ctx.user_data.get("np_buf", "")

        if key == "back":
            buf = buf[:-1]
        elif key == "ok":
            if not buf.isdigit(): await q.answer(tx(lang,"bad_id"),show_alert=True); return
            tid = int(buf)
            ctx.user_data.pop("np_buf",  None)
            ctx.user_data.pop("np_act",  None)

            # Execute action
            if act == "blk_add":
                BLOCKED.add(tid); await cfg_save()
                await q.edit_message_text(f"🚫 بلۆک کرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(bk(lang,"adm_blk")))

            elif act == "blk_rm":
                BLOCKED.discard(tid); await cfg_save()
                await q.edit_message_text(f"✅ ئەنبلۆک کرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(bk(lang,"adm_blk")))

            elif act == "vip_add":
                VIPS.add(tid); await cfg_save(); await u_field(tid,"vip",True)
                await q.edit_message_text(f"💎 VIP زیادکرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(bk(lang,"adm_vip")))

            elif act == "vip_rm":
                VIPS.discard(tid); await cfg_save(); await u_field(tid,"vip",False)
                await q.edit_message_text(f"➖ VIP لابرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(bk(lang,"adm_vip")))

            elif act == "adm_add":
                if not is_owner(uid): await q.answer(tx(lang,"own_only"),show_alert=True); return
                ADMINS.add(tid); await cfg_save()
                await q.edit_message_text(f"⚡ ئەدمین زیادکرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(bk(lang,"own_admins")))

            elif act == "adm_rm":
                if not is_owner(uid): await q.answer(tx(lang,"own_only"),show_alert=True); return
                if tid == OWNER_ID:   await q.answer("⛔ ناتوانیت خاوەنەکە لابەری!",show_alert=True); return
                ADMINS.discard(tid); await cfg_save()
                await q.edit_message_text(f"➖ ئەدمین لابرا: <code>{tid}</code>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(bk(lang,"own_admins")))

            elif act == "uinfo":
                ud = await u_get(tid)
                if not ud:
                    await q.edit_message_text(tx(lang,"not_found"),
                        reply_markup=InlineKeyboardMarkup(bk(lang,"adm_home"))); return
                vs = "✅" if tid in VIPS or ud.get("vip") else "❌"
                bs = "✅" if tid in BLOCKED else "❌"
                await q.edit_message_text(
                    f"👤 <b>زانیاری بەکارهێنەر</b>\n\n"
                    f"🆔 <code>{tid}</code>\n"
                    f"👤 {html.escape(str(ud.get('name','?')))}\n"
                    f"🔗 @{ud.get('uname','—')}\n"
                    f"📅 {ud.get('date','—')}\n"
                    f"💎 VIP: {vs} | 🚫 بلۆک: {bs}\n"
                    f"📥 داونلۆد: {ud.get('dl',0)}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🚫/✅ بلۆک", callback_data=f"qa_blk_{tid}"),
                         InlineKeyboardButton("💎 VIP",      callback_data=f"qa_vip_{tid}")],
                        [InlineKeyboardButton("✉️ نامە",     callback_data=f"qa_msg_{tid}")],
                        *bk(lang,"adm_home"),
                    ]),
                )

            elif act == "umsg":
                WAITING[uid] = f"sendmsg_{tid}"
                await q.edit_message_text(tx(lang,"write_msg",uid=f"<code>{tid}</code>"),
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌",callback_data="np_x")]]))

            elif act == "set_maxp":
                v = min(max(tid,1),30)
                CFG["max_photos"] = v; await cfg_save()
                await q.edit_message_text(f"✅ Max Photos: <b>{v}</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(bk(lang,"own_cfg")))

            elif act == "set_tout":
                v = max(tid,10)
                CFG["api_timeout"] = v; await cfg_save()
                await q.edit_message_text(f"✅ Timeout: <b>{v}s</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(bk(lang,"own_cfg")))
            return
        else:
            if len(buf) < 15: buf += key

        ctx.user_data["np_buf"] = buf
        labels = {
            "blk_add":"🚫 بلۆک","blk_rm":"✅ ئەنبلۆک",
            "vip_add":"💎 VIP+","vip_rm":"➖ VIP-",
            "adm_add":"⚡ ئەدمین+","adm_rm":"➖ ئەدمین-",
            "uinfo":"👤","umsg":"✉️",
            "set_maxp":"📸 Max","set_tout":"⏱ Timeout",
        }
        disp = f"<code>{buf}</code>" if buf else "<i>—</i>"
        try:
            await q.edit_message_text(
                f"{labels.get(act,'📟')}\n\n📟 {disp}",
                parse_mode=ParseMode.HTML,
                reply_markup=numpad(act, buf),
            )
        except: pass

# ══════════════════════════════════════════════════════════════
# MESSAGE HANDLER
# ══════════════════════════════════════════════════════════════
async def on_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid  = update.effective_user.id
    lang = await get_lang(uid)
    msg  = update.message

    # Admin waiting states
    if is_admin(uid) and uid in WAITING:
        state = WAITING.pop(uid)
        txt   = (msg.text or "").strip()

        # Broadcast
        if state.startswith("bc_"):
            bt       = state[3:]
            all_list = await u_all_ids()
            targets  = []
            for u2 in all_list:
                if bt == "all":                            targets.append(u2)
                elif bt == "vip"   and u2 in VIPS:         targets.append(u2)
                elif bt == "free"  and u2 not in VIPS:     targets.append(u2)
                elif bt == "noblk" and u2 not in BLOCKED:  targets.append(u2)
            ok = fail = 0
            st = await msg.reply_text(f"⏳ بۆ <b>{len(targets)}</b> کەس...", parse_mode=ParseMode.HTML)
            for i, tu in enumerate(targets):
                try:
                    await ctx.bot.copy_message(tu, msg.chat_id, msg.message_id)
                    ok += 1; await asyncio.sleep(0.04)
                    if i % 50 == 0 and i:
                        try: await st.edit_text(f"⏳ {i}/{len(targets)}...")
                        except: pass
                except (Forbidden, BadRequest): fail += 1
                except RetryAfter as e: await asyncio.sleep(e.retry_after); fail += 1
                except: fail += 1; await asyncio.sleep(1)
            await st.edit_text(tx(lang,"bc_done",ok=ok,fail=fail), parse_mode=ParseMode.HTML)
            return

        if state == "set_wm":
            CFG["welcome_msg"] = msg.text or ""; await cfg_save()
            await msg.reply_text(tx(lang,"wm_saved")); return

        if state.startswith("sendmsg_"):
            tid = int(state[8:])
            try:
                await ctx.bot.copy_message(tid, msg.chat_id, msg.message_id)
                await msg.reply_text(tx(lang,"msg_sent"))
            except Exception as e:
                await msg.reply_text(f"❌ {e}")
            return

    # Basic checks
    if not msg.text: return
    txt = msg.text.strip()
    if is_blk(uid): return
    if CFG["maintenance"] and not is_admin(uid):
        await msg.reply_text(tx(lang,"maintenance"), parse_mode=ParseMode.HTML); return

    # TikTok link check
    if not any(x in txt for x in ("tiktok.com","vm.tiktok","vt.tiktok")): return

    # Join check
    joined, miss = await check_sub(uid, ctx.bot)
    if not joined and not can_skip(uid):
        kb  = [[InlineKeyboardButton(f"📢 {c}", url=f"https://t.me/{c.lstrip('@')}")] for c in miss]
        kb += [[InlineKeyboardButton(tx(lang,"B_JOIN"), callback_data="sub_check")]]
        await msg.reply_text(tx(lang,"force_join"), parse_mode=ParseMode.HTML,
                             reply_markup=InlineKeyboardMarkup(kb)); return

    # Fetch
    status = await msg.reply_text(tx(lang,"searching"), parse_mode=ParseMode.HTML)
    try:
        res = await api_fetch(txt)
        if not res:
            await status.edit_text(tx(lang,"bad_link"), parse_mode=ParseMode.HTML); return

        creator, details, imgs = api_parse(res["raw"])
        photo_post = is_photo(imgs)

        # Save session
        await ses_save(uid, {"creator":creator,"details":details,"imgs":imgs})

        # Stats
        stats    = details.get("stats", {})
        title    = clean(details.get("title","") or "")
        views    = fnum(stats.get("views",0)    or stats.get("play_count",0))
        likes    = fnum(stats.get("likes",0)    or stats.get("digg_count",0))
        comments = fnum(stats.get("comments",0) or stats.get("comment_count",0))

        # Caption
        if photo_post:
            caption = tx(lang,"found_photo",
                title=html.escape(title), owner=html.escape(str(creator)),
                views=views, likes=likes, comments=comments, n=len(imgs),
            )
        else:
            caption = tx(lang,"found_video",
                title=html.escape(title), owner=html.escape(str(creator)),
                views=views, likes=likes, comments=comments,
            )

        # Keyboard
        if photo_post:
            kb = [
                [InlineKeyboardButton(tx(lang,"B_PHO",n=len(imgs)), callback_data="dl_photo")],
                [InlineKeyboardButton(tx(lang,"B_AUD"),              callback_data="dl_audio")],
                [InlineKeyboardButton(tx(lang,"B_DEL"),              callback_data="close")],
            ]
        else:
            kb = [
                [InlineKeyboardButton(tx(lang,"B_VID"), callback_data="dl_video")],
                [InlineKeyboardButton(tx(lang,"B_AUD"), callback_data="dl_audio")],
                [InlineKeyboardButton(tx(lang,"B_DEL"), callback_data="close")],
            ]

        cover  = get_cover(details, imgs, photo_post)
        markup = InlineKeyboardMarkup(kb)

        if cover and cover.startswith("http"):
            try:
                await status.edit_media(
                    InputMediaPhoto(cover, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=markup,
                )
            except Exception as e:
                log.warning(f"edit_media: {e}")
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
        log.error(f"main error: {e}")
        try: await status.edit_text(tx(lang,"dl_err"), parse_mode=ParseMode.HTML)
        except: pass

# ══════════════════════════════════════════════════════════════
# BOT SETUP
# ══════════════════════════════════════════════════════════════
ptb = ApplicationBuilder().token(TOKEN).build()
ptb.add_handler(CommandHandler(["start","menu"], cmd_start))
ptb.add_handler(CommandHandler("help",           lambda u,c: on_cb(u,c)))
ptb.add_handler(CallbackQueryHandler(on_np,   pattern=r"^(np_|cp_)"))
ptb.add_handler(CallbackQueryHandler(on_cb))
ptb.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_msg))

@web.post("/api/main")
async def webhook(req: Request):
    if not ptb.running: await ptb.initialize()
    await cfg_load()
    body = await req.json()
    await ptb.process_update(Update.de_json(body, ptb.bot))
    return {"ok": True}

@web.get("/api/main")
async def health():
    return {"status":"active","uptime":uptime(),"time":now()}
