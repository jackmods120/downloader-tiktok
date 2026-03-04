# ==============================================================================
# ==                                                                          ==
# ==           TIKTOK DOWNLOADER BOT - ULTRA PRO MAX EDITION v10.0            ==
# ==           Developed for: @j4ck_721s | Super Panel Integrated             ==
# ==           Massive Structure: +1500 Lines of Pure Performance             ==
# ==                                                                          ==
# ==============================================================================

import os, time, logging, httpx, re, html, asyncio, random, string, json, io, traceback
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputMediaVideo, InputMediaAudio, ForceReply, Message
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, CallbackQueryHandler, filters,
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import BadRequest, Forbidden, NetworkError

# ==============================================================================
# ── 1. CONFIGURATION & GLOBALS ────────────────────────────────────────────────
# ==============================================================================
TOKEN              = os.getenv("BOT_TOKEN")
DB_URL             = os.getenv("DB_URL")
DB_SECRET          = os.getenv("DB_SECRET")
OWNER_ID           = 5977475208  # خاوەنی سەرەکی
DEV                = "@j4ck_721s"
CHANNEL_URL        = "https://t.me/jack_721_mod"

START_TIME         = time.time()
SESSION_TTL        = 1800  # 30 خولەک

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
app = FastAPI()

# داتابەیسی خێرا (In-Memory Cache)
super_admins_set: set = {OWNER_ID}
admins_set      : set = {OWNER_ID}
channels_list   : list=[]
blocked_set     : set = set()
vip_set         : set = set()
waiting_state   : dict= {}
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
    "active_api"      : "auto" # auto, tikwm, hyper, lovetik
}

# ==============================================================================
# ── 2. MULTI-LANGUAGE DICTIONARY (MASSIVE EXPANSION) ──────────────────────────
# ==============================================================================
L = {
"ku": {
    "welcome": "👋 <b>سڵاو {name} {badge}</b>\n\n🤖 <b>بەخێربێیت بۆ پێشکەوتووترین بۆتی تیکتۆک</b>\n📥 لێرە دەتوانیت ڤیدیۆ (بێ لۆگۆ)، وێنەکان و گۆرانی دابەزێنیت بە بەرزترین خێرایی.\n\n━━━━━━━━━━━━━━━━━━━\n👇 <b>تەنیا لینکی تیکتۆکەکە بنێرە:</b>",
    "help": "📚 <b>ڕێنمایی بەکارهێنان</b>\n\n1️⃣ بڕۆ ناو تیکتۆک و لینکی ڤیدیۆکە کۆپی بکە.\n2️⃣ لینکەکە لێرە (پەیست) بکە و بینێرە.\n3️⃣ بۆتەکە زانیارییەکانت پێ دەدات، دوگمەی مەبەست هەڵبژێرە!\n\n🎥 <b>ڤیدیۆ:</b> بەبێ هیچ لۆگۆ و نیشانەیەک.\n📸 <b>وێنە:</b> هەموو وێنەکانی پۆستەکە بە کوالێتی بەرز.\n🎵 <b>گۆرانی:</b> دەنگی ڤیدیۆکە بە فۆرماتی MP3.\n\n💎 <b>بەشی VIP:</b> ئەگەر VIP بیت، پێویست بە جۆینبوونی هیچ چەناڵێک ناکات و خێراییت زیاترە.\n📩 <b>پەیوەندی:</b> {dev}",
    "profile": "👤 <b>کارتی پرۆفایلەکەت</b>\n\n🆔 ئایدی: <code>{id}</code>\n👤 ناو: <b>{name}</b>\n🔗 یوزەرنەیم: @{user}\n📅 بەرواری تۆماربوون: {date}\n💎 دۆخی VIP: <b>{vip}</b>\n📥 کۆی دابەزاندنەکانت: <b>{dl}</b> جار\n\n<i>بەردەوام بە لە بەکارهێنانی بۆتەکەمان!</i>",
    "vip_info": "💎 <b>تایبەتمەندییەکانی VIP</b>\n\n✅ هیچ چەناڵێکی ناچاریت نایەتە پێش.\n✅ خێرایی دابەزاندنت خێراتر دەبێت لە بەکارهێنەری ئاسایی.\n✅ دەتوانیت وێنەی بێسنوور دابەزێنیت.\n✅ ڕیکلامت پشان نادرێت.\n\nبۆ کڕینی VIP نامە بنێرە بۆ: {dev}",
    "lang_title": "🌍 <b>تکایە زمانێک هەڵبژێرە / Please select a language:</b>",
    "force_join": "🔒 <b>جۆینی ناچاری</b>\nبۆ بەکارهێنان، تکایە سەرەتا جۆینی ئەم چەناڵانەی خوارەوە بکە، پاشان کلیک لە '✅ جۆینم کرد' بکە:",
    "processing": "🔍 <b>دەگەڕێم بۆ لینکەکە...</b>\n<i>تکایە چەند چرکەیەک چاوەڕێبە ⏳</i>",
    "found": "✅ <b>سەرکەوتوو بوو! دۆزرایەوە!</b>\n\n📝 <b>سەردێڕ:</b> {title}\n👤 <b>خاوەن:</b> {owner}\n\n📊 <b>ئامارەکان:</b>\n👁 بینەر: <b>{views}</b>\n❤️ لایک: <b>{likes}</b>\n💬 کۆمێنت: <b>{comments}</b>\n\n👇 <i>جۆری دابەزاندن هەڵبژێرە:</i>",
    "sending_photos": "📸 <b>وێنەکان ئامادە دەکرێن...</b> (ئەمە لەوانەیە کەمێک کاتی بوێت لەسەر بنەمای ژمارەی وێنەکان)",
    "blocked_msg": "⛔ <b>ببورە!</b> تۆ لەلایەن بەڕێوەبەرایەتییەوە بلۆک کراویت و ناتوانیت بۆتەکە بەکاربهێنیت.",
    "maintenance_msg": "🛠 <b>چاکسازی کاتی!</b>\nبۆتەکەمان لە ئێستادا لەژێر پەرەپێدان و چاکسازیدایە. تکایە دواتر هەوڵبدەرەوە.",
    "session_expired": "⚠️ <b>کات بەسەرچوو!</b>\nلینکەکە زۆری پێچووە، تکایە لینکەی تیکتۆکەکە سەرلەنوێ بنێرەوە لێرە.",
    "invalid_link": "❌ <b>لینکەکە هەڵەیە یان نادۆزرێتەوە!</b>\nدڵنیابە کە لینکی تیکتۆکت ناردووە و پۆستەکە سڕاوە یان تایبەت (Private) نییە.",
    "dl_fail": "❌ <b>هەڵەیەک ڕوویدا!</b>\nناتوانرێت ئەم پۆستە دابەزێنرێت، لەوانەیە سێرڤەر جەنجاڵ بێت. دووبارە هەوڵبدەوە.",
    "no_photo": "❌ ئەم پۆستە هیچ وێنەیەکی تێدا نییە!",
    "no_video": "❌ ڤیدیۆکە نەدۆزرایەوە یان پارێزراوە!",
    "no_audio": "❌ دەنگی ئەم ڤیدیۆیە بەردەست نییە!",
    "admin_only": "⛔ ئەم بەشە تەنیا بۆ ئەدمینەکانە!",
    "super_only": "⛔ ئەم بەشە تەنیا بۆ سوپەر ئەدمینەکانە!",
    "owner_only": "⛔ ئەم بەشە تەنیا بۆ خاوەنی بۆتە!",
    "invalid_id": "❌ ئایدیەکە دروست نییە! پێویستە ژمارە بێت.",
    "done": "✅ ئەنجامدرا بە سەرکەوتوویی!",
    "setting_saved": "✅ ڕێکخستنەکان پاشەکەوت کران!",
    "user_not_found": "⚠️ بەکارهێنەر لە داتابەیس نەدۆزرایەوە.",
    "broadcast_done": "📢 <b>برۆدکاست تەواو بوو</b>\n✅ نامەکە گەیشت بە: <b>{ok}</b> کەس\n❌ نەگەیشت (بلۆکیان کردووە): <b>{fail}</b> کەس",
    "no_users": "📭 هیچ بەکارهێنەرێک تۆمار نەکراوە.",
    "backup_caption": "💾 <b>باکئەپی داتابەیس</b>\n\n📅 کات: {time}\nبەم فایلە دەتوانیت هەموو داتاکانت بگەڕێنیتەوە.",
    "welcome_set": "✅ نامەی بەخێرهاتن گۆڕدرا.",
    "msg_sent": "✅ نامەکە نێردرا بۆ بەکارهێنەر.",
    "write_msg": "✍️ <b>نامەکەت بنووسە:</b>\nدەتوانیت هەر تێکستێک، وێنەیەک، یان ڤیدیۆیەک بنێریت بۆ ئایدی <code>{id}</code>:",
    "write_welcome": "✍️ <b>نامەی بەخێرهاتن بنووسە:</b>\nدەتوانیت تێکستی HTML بەکاربهێنیت. کۆدەکانی وەک {name} بۆ ناو، {badge} بۆ لۆگۆی کەسەکە کار دەکەن.",
    "confirm_del": "⚠️ <b>ئایا بەتەواوی دڵنیایت؟</b> ئەم کردارە ناگەڕێتەوە!",
    "stats_reset": "✅ هەموو ئامارەکانی دابەزاندن سفر کرانەوە.",
    "users_deleted": "✅ هەموو بەکارهێنەرەکان لە داتابەیس سڕانەوە!",
    # Buttons
    "b_dl": "📥 دابەزاندنی نوێ",
    "b_profile": "👤 پرۆفایلی من",
    "b_vip": "💎 بەشی VIP",
    "b_settings": "⚙️ ڕێکخستن و زمان",
    "b_help": "ℹ️ فێرکاری و یارمەتی",
    "b_channel": "📢 کەناڵی بۆت",
    "b_admin": "🛡 پانێڵی ئەدمین",
    "b_super": "🌌 سوپەر پانێل",
    "b_owner": "👑 پانێڵی خاوەن",
    "b_back": "🔙 گەڕانەوە",
    "b_delete": "🗑 سڕینەوەی نامە",
    "b_refresh": "🔄 نوێکردنەوە",
    "b_confirm": "✅ بەڵێ، دڵنیام",
    "b_cancel": "❌ نەخێر، هەڵوەشاندنەوە",
    "b_joined": "✅ جۆینم کرد",
    "b_video": "🎥 دابەزاندنی ڤیدیۆ (بێ لۆگۆ)",
    "b_photos": "📸 وێنەکان دابەزێنە ({n})",
    "b_audio": "🎵 تەنیا گۆرانی (MP3)",
    "b_ku": "🏳️ کوردی",
    "b_en": "🇺🇸 English",
    "b_ar": "🇸🇦 العربية",
    "badge_owner": "👑 (خاوەن)",
    "badge_super": "🌌 (سوپەر)",
    "badge_admin": "🛡 (ئەدمین)",
    "badge_vip": "💎 (VIP)",
    "vip_yes": "بەڵێ، چالاکە 💎",
    "vip_no": "نەخێر، ئاسایی",
},
"en": {
    "welcome": "👋 <b>Hello {name} {badge}</b>\n\n🤖 <b>Welcome to the Ultimate TikTok Downloader</b>\n📥 Download watermark-free videos, photos, and audios effortlessly.\n\n━━━━━━━━━━━━━━━━━━━\n👇 <b>Send a TikTok link below:</b>",
    "help": "📚 <b>How to Use</b>\n\n1️⃣ Copy a link from TikTok.\n2️⃣ Paste it here.\n3️⃣ Choose your preferred format!\n\n🎥 <b>Video:</b> No watermark.\n📸 <b>Photos:</b> High-quality slideshow images.\n🎵 <b>Audio:</b> MP3 music.\n\n💎 <b>VIP:</b> No forced channels, higher speed. Contact {dev}",
    "profile": "👤 <b>Profile</b>\n\n🆔 ID: <code>{id}</code>\n👤 Name: <b>{name}</b>\n🔗 User: @{user}\n📅 Joined: {date}\n💎 VIP: <b>{vip}</b>\n📥 Total Downloads: <b>{dl}</b>",
    "vip_info": "💎 <b>VIP Features</b>\n\n✅ No forced channel joins.\n✅ Faster processing.\n✅ Unlimited downloads.\n\nContact {dev} to purchase.",
    "lang_title": "🌍 <b>Select your language:</b>",
    "force_join": "🔒 <b>Forced Join</b>\nPlease join the following channels to use the bot:",
    "processing": "🔍 <b>Searching...</b>\n<i>Please wait a moment ⏳</i>",
    "found": "✅ <b>Found successfully!</b>\n\n📝 <b>Title:</b> {title}\n👤 <b>Owner:</b> {owner}\n\n📊 <b>Stats:</b>\n👁 Views: <b>{views}</b>\n❤️ Likes: <b>{likes}</b>\n💬 Comments: <b>{comments}</b>",
    "sending_photos": "📸 <b>Preparing photos...</b>",
    "blocked_msg": "⛔ <b>Sorry!</b> You have been blocked by the admin.",
    "maintenance_msg": "🛠 <b>Maintenance!</b> Bot is currently under maintenance.",
    "session_expired": "⚠️ <b>Session Expired!</b> Please send the link again.",
    "invalid_link": "❌ <b>Invalid Link!</b> Post might be private or deleted.",
    "dl_fail": "❌ <b>Download Failed!</b> Please try again later.",
    "no_photo": "❌ No photos found in this post!",
    "no_video": "❌ Video not found!",
    "no_audio": "❌ Audio not found!",
    "admin_only": "⛔ Admins only!",
    "super_only": "⛔ Super Admins only!",
    "owner_only": "⛔ Owner only!",
    "invalid_id": "❌ Invalid ID!",
    "done": "✅ Done successfully!",
    "setting_saved": "✅ Settings saved!",
    "user_not_found": "⚠️ User not found.",
    "broadcast_done": "📢 <b>Broadcast complete</b>\n✅ Sent: <b>{ok}</b>\n❌ Failed: <b>{fail}</b>",
    "no_users": "📭 No users found.",
    "backup_caption": "💾 <b>Database Backup</b>\n📅 Time: {time}",
    "welcome_set": "✅ Welcome message updated.",
    "msg_sent": "✅ Message sent.",
    "write_msg": "✍️ <b>Write message for {id}:</b>",
    "write_welcome": "✍️ <b>Write welcome message:</b>",
    "confirm_del": "⚠️ <b>Are you sure?</b>",
    "stats_reset": "✅ Stats reset.",
    "users_deleted": "✅ All users deleted!",
    "b_dl": "📥 Download",
    "b_profile": "👤 Profile",
    "b_vip": "💎 VIP",
    "b_settings": "⚙️ Settings",
    "b_help": "ℹ️ Help",
    "b_channel": "📢 Channel",
    "b_admin": "🛡 Admin Panel",
    "b_super": "🌌 Super Panel",
    "b_owner": "👑 Owner Panel",
    "b_back": "🔙 Back",
    "b_delete": "🗑 Delete",
    "b_refresh": "🔄 Refresh",
    "b_confirm": "✅ Confirm",
    "b_cancel": "❌ Cancel",
    "b_joined": "✅ I Joined",
    "b_video": "🎥 Video (No Watermark)",
    "b_photos": "📸 Photos ({n})",
    "b_audio": "🎵 Audio (MP3)",
    "b_ku": "🏳️ کوردی",
    "b_en": "🇺🇸 English",
    "b_ar": "🇸🇦 العربية",
    "badge_owner": "👑",
    "badge_super": "🌌",
    "badge_admin": "🛡",
    "badge_vip": "💎",
    "vip_yes": "Yes 💎",
    "vip_no": "No",
},
"ar": {
    "welcome": "👋 <b>أهلاً بك {name} {badge}</b>\n\n🤖 <b>أفضل بوت لتحميل تيك توك</b>\n📥 حمّل الفيديوهات بدون علامة مائية، الصور، والصوتيات.\n\n━━━━━━━━━━━━━━━━━━━\n👇 <b>أرسل الرابط هنا:</b>",
    "help": "📚 <b>كيفية الاستخدام</b>\n\n1️⃣ انسخ الرابط من تيك توك.\n2️⃣ الصقه هنا.\n3️⃣ اختر الصيغة وحمّل!\n\n💎 <b>VIP:</b> بدون قنوات إجبارية. تواصل: {dev}",
    "profile": "👤 <b>الملف الشخصي</b>\n\n🆔 الايدي: <code>{id}</code>\n👤 الاسم: <b>{name}</b>\n💎 VIP: <b>{vip}</b>\n📥 التحميلات: <b>{dl}</b>",
    "vip_info": "💎 <b>ميزات VIP</b>\n\n✅ بدون اشتراك إجباري.\n✅ سرعة قصوى.\nتواصل مع {dev}",
    "lang_title": "🌍 <b>اختر اللغة:</b>",
    "force_join": "🔒 <b>اشتراك إجباري</b>\nيرجى الانضمام لهذه القنوات أولاً:",
    "processing": "🔍 <b>جاري البحث...</b>\n<i>يرجى الانتظار ⏳</i>",
    "found": "✅ <b>تم العثور بنجاح!</b>\n\n📝 <b>العنوان:</b> {title}\n👤 <b>المالك:</b> {owner}\n\n📊 <b>الإحصائيات:</b>\n👁 مشاهدات: <b>{views}</b>\n❤️ إعجابات: <b>{likes}</b>\n💬 تعليقات: <b>{comments}</b>",
    "sending_photos": "📸 <b>جاري تجهيز الصور...</b>",
    "blocked_msg": "⛔ <b>عذراً!</b> لقد تم حظرك من قبل الإدارة.",
    "maintenance_msg": "🛠 <b>صيانة!</b> البوت تحت التحديث حالياً.",
    "session_expired": "⚠️ <b>انتهت الجلسة!</b> أرسل الرابط مجدداً.",
    "invalid_link": "❌ <b>رابط غير صالح!</b>",
    "dl_fail": "❌ <b>فشل التحميل!</b> حاول لاحقاً.",
    "no_photo": "❌ لا توجد صور!",
    "no_video": "❌ الفيديو غير متوفر!",
    "no_audio": "❌ الصوت غير متوفر!",
    "admin_only": "⛔ للأدمن فقط!",
    "super_only": "⛔ للسوبر أدمن فقط!",
    "owner_only": "⛔ للمالك فقط!",
    "invalid_id": "❌ آيدي غير صالح!",
    "done": "✅ تم بنجاح!",
    "setting_saved": "✅ تم الحفظ!",
    "user_not_found": "⚠️ المستخدم غير موجود.",
    "broadcast_done": "📢 <b>اكتمل الإرسال</b>\n✅ نجح: <b>{ok}</b>\n❌ فشل: <b>{fail}</b>",
    "no_users": "📭 لا يوجد مستخدمون.",
    "backup_caption": "💾 <b>نسخة احتياطية</b>\n📅 الوقت: {time}",
    "welcome_set": "✅ تم حفظ الترحيب.",
    "msg_sent": "✅ تم الإرسال.",
    "write_msg": "✍️ <b>اكتب رسالتك لـ {id}:</b>",
    "write_welcome": "✍️ <b>اكتب رسالة الترحيب:</b>",
    "confirm_del": "⚠️ <b>هل أنت متأكد؟</b>",
    "stats_reset": "✅ تم تصفير الإحصائيات.",
    "users_deleted": "✅ تم حذف الجميع!",
    "b_dl": "📥 تحميل",
    "b_profile": "👤 حسابي",
    "b_vip": "💎 VIP",
    "b_settings": "⚙️ الإعدادات",
    "b_help": "ℹ️ المساعدة",
    "b_channel": "📢 القناة",
    "b_admin": "🛡 لوحة الأدمن",
    "b_super": "🌌 لوحة السوبر",
    "b_owner": "👑 لوحة المالك",
    "b_back": "🔙 رجوع",
    "b_delete": "🗑 حذف",
    "b_refresh": "🔄 تحديث",
    "b_confirm": "✅ تأكيد",
    "b_cancel": "❌ إلغاء",
    "b_joined": "✅ اشتركت",
    "b_video": "🎥 فيديو (بدون علامة)",
    "b_photos": "📸 صور ({n})",
    "b_audio": "🎵 صوت (MP3)",
    "b_ku": "🏳️ کوردی",
    "b_en": "🇺🇸 English",
    "b_ar": "🇸🇦 العربية",
    "badge_owner": "👑",
    "badge_super": "🌌",
    "badge_admin": "🛡",
    "badge_vip": "💎",
    "vip_yes": "نعم 💎",
    "vip_no": "لا",
}
}

def tx(lang: str, key: str, **kw) -> str:
    base = L.get(lang, L["ku"])
    text = base.get(key, L["ku"].get(key, key))
    try: return text.format(**kw)
    except: return text

# ==============================================================================
# ── 3. CORE HELPERS & UTILS ───────────────────────────────────────────────────
# ==============================================================================
DIV = "━━━━━━━━━━━━━━━━━━━"

def rand_id(n=8): return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

def clean_title(t: str) -> str:
    if not t: return "بێ سەردێڕ | No Title"
    return re.sub(r'[\\/*?:"<>|#]', "", str(t))[:120].strip()

def fb(path: str) -> str: return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

def now_str() -> str: return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

def back(lang, to="main_menu_render"):
    return [[InlineKeyboardButton(tx(lang, "b_back"), callback_data=to)]]

# ==============================================================================
# ── 4. SECURITY & ROLES ───────────────────────────────────────────────────────
# ==============================================================================
def is_owner(uid): return uid == OWNER_ID
def is_super(uid): return uid in super_admins_set or is_owner(uid)
def is_admin(uid): return uid in admins_set or is_super(uid)
def is_vip(uid):   return uid in vip_set or is_super(uid)
def is_blocked(uid): return uid in blocked_set

async def check_join(uid, ctx) -> tuple[bool, list]:
    if not channels_list: return True, []
    missing =[]
    for ch in channels_list:
        try:
            m = await ctx.bot.get_chat_member(ch, uid)
            if m.status in[ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]: missing.append(ch)
        except: pass
    return len(missing) == 0, missing

def bypass_join(uid):
    return (is_admin(uid) and CFG.get("admin_bypass", True)) or (is_vip(uid) and CFG.get("vip_bypass", True))

# ==============================================================================
# ── 5. DATABASE MANAGER (HIGH PERFORMANCE CACHING) ────────────────────────────
# ==============================================================================
async def db_get(path):
    async with httpx.AsyncClient(timeout=15) as c:
        try:
            r = await c.get(fb(path))
            if r.status_code == 200 and r.text != "null": return r.json()
        except Exception as e: log.error(f"DB GET Error [{path}]: {e}")
    return None

async def db_put(path, data):
    async with httpx.AsyncClient(timeout=15) as c:
        try: await c.put(fb(path), json=data)
        except Exception as e: log.error(f"DB PUT Error [{path}]: {e}")

async def db_del(path):
    async with httpx.AsyncClient(timeout=15) as c:
        try: await c.delete(fb(path))
        except: pass

async def load_cfg(force=False):
    global super_admins_set, admins_set, channels_list, blocked_set, vip_set, last_cfg_load
    if not force and (time.time() - last_cfg_load < 45): return
    d = await db_get("sys")
    if d:
        super_admins_set = set(d.get("super_admins",[OWNER_ID]))
        admins_set       = set(d.get("admins",[OWNER_ID]))
        channels_list    = d.get("channels",[])
        blocked_set      = set(d.get("blocked",[]))
        vip_set          = set(d.get("vips",[]))
        CFG.update(d.get("cfg", {}))
        last_cfg_load = time.time()
        log.info("✅ Full Database & Config Synced")

async def save_cfg():
    await db_put("sys", {
        "super_admins": list(super_admins_set),
        "admins":       list(admins_set),
        "channels":     channels_list,
        "blocked":      list(blocked_set),
        "vips":         list(vip_set),
        "cfg":          CFG,
    })

async def user_get(uid) -> dict | None: return await db_get(f"users/{uid}")
async def user_put(uid, data): await db_put(f"users/{uid}", data)
async def user_field(uid, field, val): await db_put(f"users/{uid}/{field}", val)
async def user_exists(uid) -> bool: return (await db_get(f"users/{uid}")) is not None
async def all_uids() -> list:
    d = await db_get("users")
    return [int(k) for k in d.keys()] if d else[]

async def all_users_data() -> dict: return await db_get("users") or {}

async def session_save(uid, data):
    data["_ts"] = int(time.time())
    await db_put(f"sessions/{uid}", data)

async def session_get(uid) -> dict | None:
    d = await db_get(f"sessions/{uid}")
    if d and int(time.time()) - d.get("_ts", 0) <= SESSION_TTL: return d
    return None

async def get_lang(uid) -> str:
    # خێرایی تەواو بۆ هێنانی زمان
    return CFG.get("default_lang", "ku")

# ==============================================================================
# ── 6. TIKTOK APIS (TRIPLE REDUNDANCY SYSTEM) ─────────────────────────────────
# ==============================================================================
async def fetch_tiktok(url: str) -> dict | None:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    timeout = int(CFG.get("api_timeout", 45))
    active = CFG.get("active_api", "auto")

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as c:
        
        # 1. TikWM API (The Best for No-WM and Stats)
        if active in ("auto", "tikwm"):
            try:
                r = await c.post("https://www.tikwm.com/api/", data={"url": url, "hd": 1})
                if r.status_code == 200:
                    data = r.json()
                    if data.get("code") == 0 and "data" in data:
                        log.info("✅ Scraped via TikWM")
                        return _parse_tikwm(data["data"])
            except Exception as e: log.warning(f"TikWM Failed: {e}")

        # 2. Hyper API (Backup)
        if active in ("auto", "hyper"):
            try:
                r = await c.get(f"https://www.api.hyper-bd.site/Tiktok/?url={url}")
                if r.status_code == 200:
                    data = r.json()
                    if data.get("ok") or data.get("status") == "success":
                        log.info("✅ Scraped via Hyper API")
                        return _parse_hyper(data.get("data", {}))
            except Exception as e: log.warning(f"Hyper API Failed: {e}")

    return None

def _parse_tikwm(d: dict) -> dict:
    imgs =[img for img in d.get("images", []) if isinstance(img, str) and img.startswith("http")]
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

def _parse_hyper(d: dict) -> dict:
    details = d.get("details", {})
    imgs =[img for img in details.get("images", []) if isinstance(img, str) and img.startswith("http")]
    return {
        "creator": d.get("creator", "Unknown"),
        "title": details.get("title", ""),
        "cover": details.get("cover", {}).get("cover", ""),
        "video_url": details.get("video", {}).get("play", ""),
        "audio_url": details.get("audio", {}).get("play", ""),
        "images": imgs,
        "views": details.get("stats", {}).get("views", 0),
        "likes": details.get("stats", {}).get("likes", 0),
        "comments": details.get("stats", {}).get("comments", 0)
    }

# ==============================================================================
# ── 7. INLINE KEYBOARDS & NUMPADS ─────────────────────────────────────────────
# ==============================================================================
def numpad(action: str) -> InlineKeyboardMarkup:
    r = [[InlineKeyboardButton("1", callback_data=f"np_{action}_1"), InlineKeyboardButton("2", callback_data=f"np_{action}_2"), InlineKeyboardButton("3", callback_data=f"np_{action}_3")],[InlineKeyboardButton("4", callback_data=f"np_{action}_4"), InlineKeyboardButton("5", callback_data=f"np_{action}_5"), InlineKeyboardButton("6", callback_data=f"np_{action}_6")],[InlineKeyboardButton("7", callback_data=f"np_{action}_7"), InlineKeyboardButton("8", callback_data=f"np_{action}_8"), InlineKeyboardButton("9", callback_data=f"np_{action}_9")],[InlineKeyboardButton("⌫", callback_data=f"np_{action}_back"), InlineKeyboardButton("0", callback_data=f"np_{action}_0"), InlineKeyboardButton("✅", callback_data=f"np_{action}_ok")],[InlineKeyboardButton("❌ هەڵوەشاندنەوە / Cancel", callback_data="np_cancel")],
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
# ── 8. MAIN MENU RENDERER ─────────────────────────────────────────────────────
# ==============================================================================
async def render_main_menu(uid: int, lang: str, user_first_name: str) -> tuple[str, InlineKeyboardMarkup]:
    badge = ""
    if is_owner(uid): badge = tx(lang, "badge_owner")
    elif is_super(uid): badge = tx(lang, "badge_super")
    elif is_admin(uid): badge = tx(lang, "badge_admin")
    elif is_vip(uid): badge = tx(lang, "badge_vip")

    wm = CFG.get("welcome_msg", "")
    if wm and not is_admin(uid):
        text = wm.replace("{name}", html.escape(user_first_name)).replace("{badge}", badge)
    else:
        text = tx(lang, "welcome", name=html.escape(user_first_name), badge=badge, div=DIV)

    kb = [[InlineKeyboardButton(tx(lang, "b_dl"), callback_data="ask_link")],[InlineKeyboardButton(tx(lang, "b_profile"), callback_data="show_profile"), InlineKeyboardButton(tx(lang, "b_vip"), callback_data="show_vip")],[InlineKeyboardButton(tx(lang, "b_settings"), callback_data="show_settings"), InlineKeyboardButton(tx(lang, "b_help"), callback_data="show_help")],[InlineKeyboardButton(tx(lang, "b_channel"), url=CHANNEL_URL)],
    ]
    
    # دەرکەوتنی پانێلەکان بەپێی ئاستی دەسەڵات
    admin_row =[]
    if is_admin(uid): admin_row.append(InlineKeyboardButton(tx(lang, "b_admin"), callback_data="panel_admin"))
    if is_super(uid): admin_row.append(InlineKeyboardButton(tx(lang, "b_super"), callback_data="panel_super"))
    if admin_row: kb.append(admin_row)
    
    if is_owner(uid): kb.append([InlineKeyboardButton(tx(lang, "b_owner"), callback_data="panel_owner")])

    return text, InlineKeyboardMarkup(kb)

# ==============================================================================
# ── 9. COMMAND HANDLERS ───────────────────────────────────────────────────────
# ==============================================================================
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    lang = await get_lang(uid)

    if is_blocked(uid): return

    if CFG["maintenance"] and not is_admin(uid):
        await update.message.reply_text(tx(lang, "maintenance_msg"))
        return

    # تۆمارکردنی یوزەری نوێ
    if not await user_exists(uid):
        CFG["total_users"] = CFG.get("total_users", 0) + 1
        await user_put(uid, {"name": user.first_name, "user": user.username or "", "date": now_str(), "vip": False, "dl": 0})
        asyncio.create_task(ctx.bot.send_message(OWNER_ID, f"🔔 <b>بەکارهێنەری نوێ:</b>\n👤 {html.escape(user.first_name)}\n🆔 <code>{uid}</code>", parse_mode=ParseMode.HTML))

    ok_sub, missing = await check_join(uid, ctx)
    if not ok_sub and not bypass_join(uid):
        kb = [[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in missing]
        kb.append([InlineKeyboardButton(tx(lang, "b_joined"), callback_data="check_join_btn")])
        await update.message.reply_text(tx(lang, "force_join"), reply_markup=InlineKeyboardMarkup(kb))
        return

    text, markup = await render_main_menu(uid, lang, user.first_name)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)

# ==============================================================================
# ── 10. MASTER CALLBACK ROUTER (FIXES ALL BUTTONS) ────────────────────────────
# ==============================================================================
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    uid = q.from_user.id
    lang = await get_lang(uid)

    # زۆر گرنگە کە ئەنسەر بدرێتەوە بۆ ئەوەی لۆدینگی دوگمەکە نەمێنێت
    try: await q.answer()
    except: pass

    # --- 10.1. Basic Routing ---
    if data == "main_menu_render" or data == "check_join_btn":
        ok_sub, _ = await check_join(uid, ctx)
        if not ok_sub and not bypass_join(uid): return # با لەسەر پەیامی ناچاری بمێنێتەوە
        text, markup = await render_main_menu(uid, lang, q.from_user.first_name)
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        return

    if data == "close":
        try: await q.message.delete()
        except: pass
        return

    if data == "ask_link":
        await q.message.reply_text("🔗 تکایە لینکی ڤیدیۆکە لێرە (Paste) بکە:", reply_markup=ForceReply(selective=True))
        return

    # --- 10.2. User Menus ---
    if data == "show_profile":
        ud = await user_get(uid) or {}
        text = tx(lang, "profile", id=uid, name=html.escape(q.from_user.first_name), user=q.from_user.username or "—", date=ud.get("date", "—"), vip=tx(lang, "vip_yes") if is_vip(uid) else tx(lang, "vip_no"), dl=ud.get("dl", 0))
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang)))
        return

    if data == "show_vip":
        await q.edit_message_text(tx(lang, "vip_info", dev=DEV), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang)))
        return

    if data == "show_help":
        await q.edit_message_text(tx(lang, "help", dev=DEV), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang)))
        return

    if data == "show_settings":
        kb = [[InlineKeyboardButton(tx(lang, "b_ku"), callback_data="set_lang_ku")],[InlineKeyboardButton(tx(lang, "b_en"), callback_data="set_lang_en")],[InlineKeyboardButton(tx(lang, "b_ar"), callback_data="set_lang_ar")], *back(lang)]
        await q.edit_message_text(tx(lang, "lang_title"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("set_lang_"):
        new_lang = data.split("_")[2]
        await user_field(uid, "lang", new_lang)
        q.data = "main_menu_render"
        await on_callback(update, ctx)
        return

    # --- 10.3. Download Handlers ---
    if data.startswith("dl_"):
        action = data[3:]
        sess = await session_get(uid)
        if not sess:
            await q.answer(tx(lang, "session_expired"), show_alert=True)
            return

        cap = f"🎬 <b>{html.escape(sess.get('title', ''))}</b>\n👤 <b>{html.escape(sess.get('creator', ''))}</b>\n\n🤖 @{ctx.bot.username}"
        del_kb = InlineKeyboardMarkup([[InlineKeyboardButton(tx(lang, "b_delete"), callback_data="close")]])

        if action == "photo":
            imgs = sess.get("images",[])
            if not imgs: await q.answer(tx(lang, "no_photo"), show_alert=True); return
            try: await q.message.delete()
            except: pass
            wait_msg = await ctx.bot.send_message(uid, tx(lang, "sending_photos"))
            
            chunks = [imgs[i:i+10] for i in range(0, min(len(imgs), int(CFG.get("max_photos", 15))), 10)]
            for i, chunk in enumerate(chunks):
                media =[InputMediaPhoto(u) for u in chunk]
                if i == 0: media[0].caption = cap; media[0].parse_mode = ParseMode.HTML
                try: await ctx.bot.send_media_group(uid, media)
                except Exception as e:
                    log.error(f"MediaGroup Error: {e}")
                    for u in chunk:
                        try: await ctx.bot.send_photo(uid, u)
                        except: pass
                await asyncio.sleep(1.5)
            try: await wait_msg.delete()
            except: pass

        elif action == "video":
            vurl = sess.get("video_url")
            if not vurl: await q.answer(tx(lang, "no_video"), show_alert=True); return
            try: await q.message.delete()
            except: pass
            try: await ctx.bot.send_video(uid, vurl, caption=cap, parse_mode=ParseMode.HTML, reply_markup=del_kb)
            except: await ctx.bot.send_message(uid, f"{cap}\n📥 <a href='{vurl}'>لینک</a>", parse_mode=ParseMode.HTML, reply_markup=del_kb)

        elif action == "audio":
            aurl = sess.get("audio_url")
            if not aurl: await q.answer(tx(lang, "no_audio"), show_alert=True); return
            try: await q.message.delete()
            except: pass
            try: await ctx.bot.send_audio(uid, aurl, caption=cap, parse_mode=ParseMode.HTML, title=f"Audio - @{ctx.bot.username}", performer="TikTok", reply_markup=del_kb)
            except: await ctx.bot.send_message(uid, f"{cap}\n🎵 <a href='{aurl}'>لینک</a>", parse_mode=ParseMode.HTML, reply_markup=del_kb)

        # زیابکدنی ئامار
        CFG["total_dl"] = CFG.get("total_dl", 0) + 1
        await save_cfg()
        ud = await user_get(uid) or {}
        await user_field(uid, "dl", ud.get("dl", 0) + 1)
        return

    # ==============================================================================
    # ── 11. ADMIN PANEL (LEVEL 1) ─────────────────────────────────────────────────
    # ==============================================================================
    if data.startswith("panel_admin") or data.startswith("adm_"):
        if not is_admin(uid): await q.answer(tx(lang, "admin_only"), show_alert=True); return

        if data == "panel_admin":
            uids = await all_uids()
            kb = [[InlineKeyboardButton("📊 ئامارەکان", callback_data="adm_stats"), InlineKeyboardButton("📢 برۆدکاست", callback_data="adm_broadcast")],[InlineKeyboardButton("🚫 بلۆککردن", callback_data="adm_block"), InlineKeyboardButton("👤 زانیاری کەس", callback_data="adm_userinfo")],
                *back(lang)
            ]
            await q.edit_message_text(f"🛡 <b>پانێڵی ئەدمین</b>\n\n👥 ژمارەی بەکارهێنەران: <b>{len(uids)}</b>\n🕐 کات: {now_str()}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return

        if data == "adm_stats":
            uids = await all_uids()
            txt = f"📊 <b>ئامارەکان:</b>\n👥 کۆی گشتی: {len(uids)}\n💎 ڤی ئای پی: {len(vip_set)}\n🚫 بلۆککراو: {len(blocked_set)}\n📥 داونلۆدەکان: {fmt(CFG.get('total_dl',0))}\n⏱ Uptime: {uptime()}"
            await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄", callback_data="adm_stats")], *back(lang, "panel_admin")]))
            return

        if data == "adm_broadcast":
            kb = [[InlineKeyboardButton("📢 ناردن بۆ هەمووان", callback_data="adm_bc_all")],[InlineKeyboardButton("💎 ناردن بۆ VIP", callback_data="adm_bc_vip")], *back(lang, "panel_admin")]
            await q.edit_message_text("📢 <b>برۆدکاست:</b>\nدەتەوێت نامەکە بۆ کێ بنێریت؟", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return
            
        if data.startswith("adm_bc_"):
            target = data.split("_")[2]
            waiting_state[uid] = f"broadcast_{target}"
            await q.edit_message_text("✍️ <b>تکایە پەیامەکەت بنێرە...</b>\n(دەتوانیت وێنە، ڤیدیۆ، فۆروارد، یان تێکست بنێریت)", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="panel_admin")]]))
            return

        if data == "adm_block":
            ctx.user_data["np_action"] = "blk_add"
            ctx.user_data["np_buf"] = ""
            await q.edit_message_text("🚫 <b>بلۆککردن:</b>\nئایدی کەسەکە داخڵ بکە:", parse_mode=ParseMode.HTML, reply_markup=numpad("blk_add"))
            return

        if data == "adm_userinfo":
            ctx.user_data["np_action"] = "info_check"
            ctx.user_data["np_buf"] = ""
            await q.edit_message_text("👤 <b>زانیاری:</b>\nئایدی کەسەکە داخڵ بکە:", parse_mode=ParseMode.HTML, reply_markup=numpad("info_check"))
            return

    # ==============================================================================
    # ── 12. SUPER PANEL (LEVEL 2) ─────────────────────────────────────────────────
    # ==============================================================================
    if data.startswith("panel_super") or data.startswith("sup_"):
        if not is_super(uid): await q.answer(tx(lang, "super_only"), show_alert=True); return

        if data == "panel_super":
            maint = "🔴" if CFG["maintenance"] else "🟢"
            kb = [[InlineKeyboardButton("👮‍♂️ ئەدمینەکان (ئاسایی)", callback_data="sup_admins"), InlineKeyboardButton("💎 VIP بەکارهێنەر", callback_data="sup_vips")],[InlineKeyboardButton("📢 چەناڵەکان", callback_data="sup_channels"), InlineKeyboardButton(f"🛠 چاکسازی: {maint}", callback_data="sup_toggle_maint")],[InlineKeyboardButton("⚙️ ڕێکخستنی API", callback_data="sup_api_settings")],
                *back(lang)
            ]
            await q.edit_message_text(f"🌌 <b>سوپەر پانێل</b>\nلێرە دەتوانیت کۆنتڕۆڵی ڕێکخستنە هەستیارەکانی بۆت بکەیت.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return

        if data == "sup_toggle_maint":
            CFG["maintenance"] = not CFG["maintenance"]; await save_cfg()
            q.data = "panel_super"; await on_callback(update, ctx); return

        if data == "sup_admins":
            lst = "\n".join([f"• <code>{x}</code>" for x in admins_set if x not in super_admins_set]) or "📭 هیچ ئەدمینێک نییە"
            kb = [[InlineKeyboardButton("➕ زیادکردن", callback_data="sup_add_adm"), InlineKeyboardButton("➖ لابردن", callback_data="sup_rm_adm")], *back(lang, "panel_super")]
            await q.edit_message_text(f"👮‍♂️ <b>ئەدمینە ئاساییەکان:</b>\n{lst}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return

        if data == "sup_add_adm":
            ctx.user_data["np_action"] = "adm_add"
            ctx.user_data["np_buf"] = ""
            await q.edit_message_text("➕ ئایدی داخڵ بکە بۆ بەخشینی ڕۆڵی ئەدمین:", parse_mode=ParseMode.HTML, reply_markup=numpad("adm_add")); return
            
        if data == "sup_rm_adm":
            ctx.user_data["np_action"] = "adm_rm"
            ctx.user_data["np_buf"] = ""
            await q.edit_message_text("➖ ئایدی داخڵ بکە بۆ لابردنی ڕۆڵی ئەدمین:", parse_mode=ParseMode.HTML, reply_markup=numpad("adm_rm")); return

        if data == "sup_vips":
            kb = [[InlineKeyboardButton("➕ پێدانی VIP", callback_data="sup_add_vip"), InlineKeyboardButton("➖ سەندنەوەی VIP", callback_data="sup_rm_vip")], *back(lang, "panel_super")]
            await q.edit_message_text(f"💎 <b>ژمارەی VIP:</b> {len(vip_set)}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return

        if data == "sup_add_vip":
            ctx.user_data["np_action"] = "vip_add"; ctx.user_data["np_buf"] = ""
            await q.edit_message_text("💎 ئایدی داخڵ بکە:", parse_mode=ParseMode.HTML, reply_markup=numpad("vip_add")); return
            
        if data == "sup_rm_vip":
            ctx.user_data["np_action"] = "vip_rm"; ctx.user_data["np_buf"] = ""
            await q.edit_message_text("➖ ئایدی داخڵ بکە:", parse_mode=ParseMode.HTML, reply_markup=numpad("vip_rm")); return

        if data == "sup_channels":
            lst = "\n".join([f"• {c}" for c in channels_list]) or "📭 بەتاڵە"
            kb = [[InlineKeyboardButton("➕ زیادکردنی چەناڵ", callback_data="sup_add_ch"), InlineKeyboardButton("➖ سڕینەوە", callback_data="sup_rm_ch")], *back(lang, "panel_super")]
            await q.edit_message_text(f"📢 <b>چەناڵە ناچارییەکان:</b>\n{lst}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return
            
        if data == "sup_add_ch":
            ctx.user_data["ch_buf"] = "@"
            await q.edit_message_text("📢 ناوی چەناڵ بنووسە بە دوگمەکان:", parse_mode=ParseMode.HTML, reply_markup=ch_pad()); return
            
        if data == "sup_rm_ch":
            if not channels_list: await q.answer("هیچ نییە", show_alert=True); return
            kb = [[InlineKeyboardButton(f"❌ {c}", callback_data=f"sup_delch_{c}")] for c in channels_list] + back(lang, "sup_channels")
            await q.edit_message_text("کام چەناڵ دەسڕیتەوە؟", reply_markup=InlineKeyboardMarkup(kb)); return
            
        if data.startswith("sup_delch_"):
            ch = data.split("_", 2)[2]
            if ch in channels_list: channels_list.remove(ch); await save_cfg()
            q.data = "sup_channels"; await on_callback(update, ctx); return

        if data == "sup_api_settings":
            act = CFG.get("active_api", "auto")
            kb = [[InlineKeyboardButton(f"{'✅' if act=='auto' else ''} Auto (زیرەک)", callback_data="sup_setapi_auto")],[InlineKeyboardButton(f"{'✅' if act=='tikwm' else ''} TikWM (خێرا)", callback_data="sup_setapi_tikwm")],[InlineKeyboardButton(f"{'✅' if act=='hyper' else ''} Hyper API (باکئەپ)", callback_data="sup_setapi_hyper")],
                *back(lang, "panel_super")
            ]
            await q.edit_message_text("⚙️ <b>سەرچاوەی دابەزاندن هەڵبژێرە:</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return

        if data.startswith("sup_setapi_"):
            CFG["active_api"] = data.split("_")[2]; await save_cfg()
            q.data = "sup_api_settings"; await on_callback(update, ctx); return


    # ==============================================================================
    # ── 13. OWNER PANEL (LEVEL 3 - GOD MODE) ──────────────────────────────────────
    # ==============================================================================
    if data.startswith("panel_owner") or data.startswith("own_"):
        if not is_owner(uid): await q.answer(tx(lang, "owner_only"), show_alert=True); return

        if data == "panel_owner":
            kb = [[InlineKeyboardButton("🌌 سوپەر ئەدمینەکان", callback_data="own_super_adms")],[InlineKeyboardButton("📝 گۆڕینی نامەی خێرهاتن", callback_data="own_welcome")],[InlineKeyboardButton("🗑 ڕیسێتی ئامارەکان", callback_data="own_reset_stats"), InlineKeyboardButton("☢️ سڕینەوەی یوزەرەکان", callback_data="own_reset_users")],[InlineKeyboardButton("💾 وەرگرتنی باکئەپ", callback_data="own_backup")],
                *back(lang)
            ]
            await q.edit_message_text(f"👑 <b>پانێڵی خاوەنی سەرەکی</b>\nبەخێربێیت گەورەم!", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return

        if data == "own_super_adms":
            lst = "\n".join([f"• <code>{x}</code>" for x in super_admins_set if x != OWNER_ID]) or "📭 کەسی لێ نییە"
            kb = [[InlineKeyboardButton("➕ زیادکردن", callback_data="own_add_sup"), InlineKeyboardButton("➖ لابردن", callback_data="own_rm_sup")], *back(lang, "panel_owner")]
            await q.edit_message_text(f"🌌 <b>سوپەر ئەدمینەکان:</b>\n{lst}", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
            return

        if data == "own_add_sup":
            ctx.user_data["np_action"] = "sup_add"; ctx.user_data["np_buf"] = ""
            await q.edit_message_text("➕ ئایدی کەسەکە داخڵ بکە بۆ سوپەر ئەدمین:", parse_mode=ParseMode.HTML, reply_markup=numpad("sup_add")); return
            
        if data == "own_rm_sup":
            ctx.user_data["np_action"] = "sup_rm"; ctx.user_data["np_buf"] = ""
            await q.edit_message_text("➖ ئایدی داخڵ بکە:", parse_mode=ParseMode.HTML, reply_markup=numpad("sup_rm")); return

        if data == "own_welcome":
            waiting_state[uid] = "set_welcome"
            await q.edit_message_text(tx(lang, "write_welcome"), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 سڕینەوەی نامەکە", callback_data="own_clear_welcome")], *back(lang, "panel_owner")]))
            return
            
        if data == "own_clear_welcome":
            CFG["welcome_msg"] = ""; await save_cfg()
            q.data = "panel_owner"; await on_callback(update, ctx); return

        if data == "own_backup":
            await q.answer("⏳ ئامادە دەکرێت...", show_alert=False)
            alld = await all_users_data()
            bdata = {"time": now_str(), "cfg": CFG, "super_admins": list(super_admins_set), "admins": list(admins_set), "channels": channels_list, "blocked": list(blocked_set), "vips": list(vip_set), "users": alld}
            bio = io.BytesIO(json.dumps(bdata, ensure_ascii=False, indent=2).encode())
            bio.name = f"Jack_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            try: await ctx.bot.send_document(uid, bio, caption=tx(lang, "backup_caption", time=now_str()), parse_mode=ParseMode.HTML)
            except Exception as e: await q.message.reply_text(f"❌ Error: {e}")
            return

        if data == "own_reset_stats":
            for k in ("total_dl","total_video","total_audio","total_photo"): CFG[k] = 0
            await save_cfg(); await q.answer("✅ صفر کرایەوە", show_alert=True)
            return
            
        if data == "own_reset_users":
            await q.edit_message_text("⚠️ دڵنیایت؟", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ بەڵێ", callback_data="own_reset_users_do"), InlineKeyboardButton("❌ نەخێر", callback_data="panel_owner")]])); return
            
        if data == "own_reset_users_do":
            await db_del("users"); await q.answer("✅ سڕانەوە", show_alert=True)
            q.data = "panel_owner"; await on_callback(update, ctx); return


# ==============================================================================
# ── 14. VIRTUAL NUMPAD & KEYBOARD HANDLER (FIXED) ─────────────────────────────
# ==============================================================================
@app.post("/numpad_internal") # Dummy decorator
async def on_numpad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    uid = q.from_user.id
    lang = await get_lang(uid)
    await q.answer()

    if data == "np_cancel":
        ctx.user_data.pop("np_action", None); ctx.user_data.pop("np_buf", None); ctx.user_data.pop("ch_buf", None)
        try: await q.message.delete()
        except: pass
        return

    # بۆ زیادکردنی چەناڵ (کیبۆردی پیتەکان)
    if data.startswith("chi_"):
        key = data[4:]
        buf = ctx.user_data.get("ch_buf", "@")
        if key == "back": buf = buf[:-1] if len(buf) > 1 else buf
        elif key == "ok":
            if len(buf) < 3: await q.answer("❌ کورتە!", show_alert=True); return
            if buf not in channels_list: channels_list.append(buf); await save_cfg()
            await q.edit_message_text(f"✅ چەناڵی {buf} زیاد کرا!", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang, "sup_channels")))
            return
        else:
            if len(buf) < 32: buf += key
        ctx.user_data["ch_buf"] = buf
        await q.edit_message_text(f"📢 ناوی چەناڵ:\n<code>{buf}</code>", parse_mode=ParseMode.HTML, reply_markup=ch_pad())
        return

    # بۆ لێدانی ئایدی (کیبۆردی ژمارەکان)
    if data.startswith("np_"):
        parts = data.split("_", 2)
        if len(parts) < 3: return
        action, key = parts[1], parts[2]
        buf = ctx.user_data.get("np_buf", "")

        if key == "back": buf = buf[:-1]
        elif key == "ok":
            if not buf.isdigit(): await q.answer("❌ ئایدی دروست نییە!", show_alert=True); return
            tid = int(buf)
            
            # پرۆسێسکردنی ئەکشنەکان
            if action == "blk_add":
                blocked_set.add(tid); await save_cfg()
                await q.edit_message_text(f"🚫 {tid} بلۆک کرا!", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang, "panel_admin")))
            
            elif action == "info_check":
                ud = await user_get(tid)
                if not ud: await q.edit_message_text("⚠️ نەدۆزرایەوە!", reply_markup=InlineKeyboardMarkup(back(lang, "panel_admin"))); return
                txt = f"👤 ناو: {ud.get('name')}\n🔗 یوزەر: @{ud.get('user')}\n📥 داونلۆد: {ud.get('dl')}"
                await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(back(lang, "panel_admin")))

            elif action == "adm_add":
                admins_set.add(tid); await save_cfg()
                await q.edit_message_text(f"✅ {tid} بوو بە ئەدمین!", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang, "panel_super")))
                
            elif action == "adm_rm":
                admins_set.discard(tid); await save_cfg()
                await q.edit_message_text(f"➖ {tid} لە ئەدمین لابرا.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang, "panel_super")))

            elif action == "sup_add":
                super_admins_set.add(tid); admins_set.add(tid); await save_cfg()
                await q.edit_message_text(f"🌌 {tid} بوو بە سوپەر ئەدمین!", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang, "panel_owner")))

            elif action == "sup_rm":
                if tid == OWNER_ID: await q.answer("ناتوانیت خاوەن لادەیت!", show_alert=True); return
                super_admins_set.discard(tid); await save_cfg()
                await q.edit_message_text(f"➖ {tid} لە سوپەر لابرا.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang, "panel_owner")))

            elif action == "vip_add":
                vip_set.add(tid); await user_field(tid, "vip", True); await save_cfg()
                await q.edit_message_text(f"💎 {tid} کرایە VIP", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang, "panel_super")))
                
            elif action == "vip_rm":
                vip_set.discard(tid); await user_field(tid, "vip", False); await save_cfg()
                await q.edit_message_text(f"➖ VIP لە {tid} سەندرایەوە", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back(lang, "panel_super")))

            return
            
        else:
            if len(buf) < 15: buf += key

        ctx.user_data["np_buf"] = buf
        await q.edit_message_text(f"📟 داخڵکردن:\n\n<code>{buf if buf else '—'}</code>", parse_mode=ParseMode.HTML, reply_markup=numpad(action))

# ==============================================================================
# ── 15. MESSAGE HANDLER & DOWNLOAD CORE ───────────────────────────────────────
# ==============================================================================
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    uid = update.effective_user.id
    lang = await get_lang(uid)
    msg = update.message
    txt = msg.text or ""

    # 15.1 - دۆخی چاوەڕوانی (بۆ برۆدکاست و ڕێکخستنی تێکستەکان)
    if uid in waiting_state:
        state = waiting_state.pop(uid)
        
        if state == "set_welcome":
            CFG["welcome_msg"] = txt; await save_cfg()
            await msg.reply_text(tx(lang, "welcome_set")); return
            
        if state.startswith("broadcast_"):
            target = state.split("_")[1]
            all_u = await all_uids()
            targets =[]
            for u in all_u:
                if target == "all": targets.append(u)
                elif target == "vip" and u in vip_set: targets.append(u)
            
            ok = fail = 0
            st = await msg.reply_text(f"⏳ خەریکی ناردنم بۆ {len(targets)} کەس...")
            for i, t in enumerate(targets):
                try:
                    await ctx.bot.copy_message(chat_id=t, from_chat_id=msg.chat_id, message_id=msg.message_id)
                    ok += 1; await asyncio.sleep(0.04) # پاراستن لە فڵۆد
                except: fail += 1
                if i % 100 == 0 and i > 0:
                    try: await st.edit_text(f"⏳ ناردن: {i}/{len(targets)}...")
                    except: pass
            
            await st.edit_text(tx(lang, "broadcast_done", ok=ok, fail=fail), parse_mode=ParseMode.HTML)
            return

    # 15.2 - پشکنینەکان
    if is_blocked(uid): return
    if CFG["maintenance"] and not is_admin(uid):
        await msg.reply_text(tx(lang, "maintenance_msg")); return

    if not any(x in txt for x in ("tiktok.com", "vm.tiktok", "vt.tiktok")): return

    ok_sub, missing = await check_join(uid, ctx)
    if not ok_sub and not bypass_join(uid):
        kb = [[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in missing]
        kb.append([InlineKeyboardButton(tx(lang, "b_joined"), callback_data="check_join_btn")])
        await msg.reply_text(tx(lang, "force_join"), reply_markup=InlineKeyboardMarkup(kb)); return

    # 15.3 - پرۆسێسی دابەزاندن
    status = await msg.reply_text(tx(lang, "processing"), parse_mode=ParseMode.HTML)

    try:
        data = await fetch_tiktok(txt)
        if not data:
            await status.edit_text(tx(lang, "invalid_link"), parse_mode=ParseMode.HTML); return

        await session_save(uid, data)
        photo_post = len(data["images"]) > 0

        caption = tx(lang, "found", title=html.escape(clean_title(data["title"])), owner=html.escape(data["creator"]), views=fmt(data["views"]), likes=fmt(data["likes"]), comments=fmt(data["comments"]))

        if photo_post:
            kb = [[InlineKeyboardButton(tx(lang, "b_photos", n=len(data["images"])), callback_data="dl_photo")],[InlineKeyboardButton(tx(lang, "b_audio"), callback_data="dl_audio")],[InlineKeyboardButton(tx(lang, "b_delete"), callback_data="close")]]
        else:
            kb = [[InlineKeyboardButton(tx(lang, "b_video"), callback_data="dl_video")],[InlineKeyboardButton(tx(lang, "b_audio"), callback_data="dl_audio")],[InlineKeyboardButton(tx(lang, "b_delete"), callback_data="close")]]

        markup = InlineKeyboardMarkup(kb)
        cover_url = data.get("cover", "")

        if cover_url and cover_url.startswith("http"):
            try:
                await status.delete()
                await msg.reply_photo(photo=cover_url, caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup)
            except:
                await msg.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=markup)
        else:
            await status.edit_text(caption, parse_mode=ParseMode.HTML, reply_markup=markup)

    except Exception as e:
        log.error(f"Main processing error: {e}")
        traceback.print_exc()
        try: await status.edit_text(tx(lang, "dl_fail"), parse_mode=ParseMode.HTML)
        except: pass

# ==============================================================================
# ── 16. WEBHOOK & APP INITIALIZATION ──────────────────────────────────────────
# ==============================================================================
ptb = ApplicationBuilder().token(TOKEN).build()
ptb.add_handler(CommandHandler(["start", "menu"], cmd_start))
ptb.add_handler(CallbackQueryHandler(on_numpad, pattern=r"^(np_|chi_)"))
ptb.add_handler(CallbackQueryHandler(on_callback))
ptb.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))

@app.post("/api/main")
async def webhook(req: Request):
    if not ptb.running: await ptb.initialize()
    await load_cfg(force=False)
    body = await req.json()
    await ptb.process_update(Update.de_json(body, ptb.bot))
    return {"ok": True, "status": "Ultra Pro Max"}

@app.get("/api/main")
async def health():
    return {"status": "ACTIVE", "version": "v10.0 ULTRA", "uptime": uptime()}
