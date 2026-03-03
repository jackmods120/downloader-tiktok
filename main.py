import os
import time
import logging
import httpx
import re
import html
from fastapi import FastAPI, Request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaAudio,
    ForceReply
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from telegram.constants import ParseMode

# ⚠️ TOKEN و DB_URL پێویستە لە environment variables بێت — ئەمەیان بگۆڕە
TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://www.api.hyper-bd.site/Tiktok/?url="
CHANNEL_URL = "https://t.me/J4CK_721"
DB_URL = os.getenv("DB_URL")
DB_SECRET = os.getenv("DB_SECRET")

SESSION_EXPIRE = 600
API_TIMEOUT = 60

logging.basicConfig(level=logging.INFO)
app = FastAPI()

# ══════════════════════════════════════════
#   یارمەتیدەرەکان
# ══════════════════════════════════════════

def format_number(num):
    if not num:
        return "٠"
    num = int(num)
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(num)

def clean_title(title):
    if not title:
        return "ڤیدیۆی_تیکتۆک"
    safe_title = re.sub(r'[\\/*?:"<>|]', '', title)
    return safe_title[:50]

def process_caption(text):
    if not text:
        return ""
    text = re.sub(r'(@\w+|#\w+)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return html.escape(text)

def firebase_url(path: str):
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

# ══════════════════════════════════════════
#   Firebase داتابەیس
# ══════════════════════════════════════════

async def save_user_data(user_id: int, data: dict):
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        await client.put(firebase_url(f"users/{user_id}"), json=data)

async def get_user_data(user_id: int):
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        r = await client.get(firebase_url(f"users/{user_id}"))
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None
        if int(time.time()) - data.get("timestamp", 0) > SESSION_EXPIRE:
            return None
        return data

async def increment_downloads(user_id: int):
    """ژمارەی داگرتنەکانی بەکارهێنەر زیاد بکە"""
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            r = await client.get(firebase_url(f"stats/{user_id}"))
            stats = r.json() if r.status_code == 200 and r.json() else {"downloads": 0, "joined": int(time.time())}
            stats["downloads"] = stats.get("downloads", 0) + 1
            stats["last_active"] = int(time.time())
            await client.put(firebase_url(f"stats/{user_id}"), json=stats)
    except Exception:
        pass

async def get_global_stats():
    """ئامارە گشتیەکان وەربگرە"""
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            r = await client.get(firebase_url("stats"))
            all_stats = r.json()
            if not all_stats:
                return 0, 0
            total_users = len(all_stats)
            total_downloads = sum(v.get("downloads", 0) for v in all_stats.values() if isinstance(v, dict))
            return total_users, total_downloads
    except Exception:
        return 0, 0

# ══════════════════════════════════════════
#   فەرمانەکان
# ══════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = html.escape(user.first_name or "بەکارهێنەر")

    text = (
        f"<b>✨ بەخێربێیت، {first_name}!</b>\n\n"
        "🎯 <b>بۆتی داگرتنی تیکتۆک</b> — سێرکردنی ژیانی ئۆنلاین!\n\n"
        "─────────────────────\n"
        "🎥 <b>تاقیکردنەوەی ئەمەیان بکە:</b>\n"
        "├ 📲 لینکی تیکتۆک بنێرە\n"
        "├ 🎞 ڤیدیۆ بەبێ واتەرمارک داگرە\n"
        "├ 🎵 دەنگ بە کوالێتی بەرز داگرە\n"
        "└ 📊 ئامارەکانی ڤیدیۆ ببینە\n"
        "─────────────────────\n\n"
        "⬇️ <i>دووگمەی «داگرتن» بکە یان لینکەکەت ڕاستەوخۆ بنێرە!</i>"
    )
    keyboard = [
        [InlineKeyboardButton("📥 داگرتنی ڤیدیۆ", callback_data="cmd_download")],
        [
            InlineKeyboardButton("❓ یارمەتی", callback_data="cmd_help"),
            InlineKeyboardButton("📊 ئامار", callback_data="cmd_stats")
        ],
        [InlineKeyboardButton("🔥 کەناڵی نوێکردنەوە", url=CHANNEL_URL)]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard),
            reply_to_message_id=update.message.message_id
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 <b>چۆنیەتی بەکارهێنانی بۆت:</b>\n\n"
        "─────────────────────\n"
        "<b>١. لینک کۆپی بکە:</b>\n"
        "   ↳ بڕۆ بۆ تیکتۆک، ڤیدیۆکە بدۆزەرەوە، «هاوبەشکردن» کلیک بکە و لینکەکە کۆپی بکە.\n\n"
        "<b>٢. لینک بنێرە:</b>\n"
        "   ↳ لینکەکە ڕاستەوخۆ بنێرە بۆ ئەم چاتە.\n\n"
        "<b>٣. فۆرمات هەڵبژێرە:</b>\n"
        "   ↳ دیاری بکە ڤیدیۆ دەتەوێت یان دەنگ.\n\n"
        "<b>٤. داگرتن:</b>\n"
        "   ↳ چاوەڕوان بە و فایلەکەت ئامادە دەبێت!\n\n"
        "─────────────────────\n"
        "⚠️ <i>تێبینی: دڵنیا بە ڤیدیۆکە تایبەت نەبێت.</i>"
    )
    keyboard = [
        [
            InlineKeyboardButton("📥 داگرتنی ڤیدیۆ", callback_data="cmd_download"),
            InlineKeyboardButton("🔙 گەڕانەوە", callback_data="cmd_start")
        ]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard),
            reply_to_message_id=update.message.message_id
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیشاندانی ئامارەکانی بۆت"""
    total_users, total_downloads = await get_global_stats()
    text = (
        "📊 <b>ئامارەکانی بۆت:</b>\n\n"
        f"👥 کۆی بەکارهێنەران: <b>{format_number(total_users)}</b>\n"
        f"📥 کۆی داگرتنەکان: <b>{format_number(total_downloads)}</b>\n\n"
        "─────────────────────\n"
        "💪 <i>سوپاس بۆ بەکارهێنانی بۆتەکەمان!</i>"
    )
    keyboard = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="cmd_start")]]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ══════════════════════════════════════════
#   بەکارهێنانی دووگمەکان
# ══════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data == "cmd_start":
        await start_command(update, context)
        return

    if data == "cmd_help":
        await help_command(update, context)
        return

    if data == "cmd_stats":
        await stats_command(update, context)
        return

    if data == "cmd_download":
        await query.answer("تکایە لینکەکە بنێرە.", show_alert=False)
        await query.message.reply_text(
            "🔗 <b>لینکی تیکتۆکەکەت بنێرەم تا داگربێت:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True),
            reply_to_message_id=query.message.message_id
        )
        return

    if data == "close":
        await query.answer("داخرایەوە ✅", show_alert=False)
        await query.message.delete()
        return

    if data == "stat_show_all":
        user_data = await get_user_data(user_id)
        if not user_data:
            await query.answer("⚠️ کاتی دەمارە تەواو بووە، دووبارە لینکەکە بنێرە.", show_alert=True)
            return

        d = user_data["details"]
        stats_text = (
            "📊 ئامارەکانی ڤیدیۆ:\n\n"
            f"👁 بینینەکان: {format_number(d.get('views', 0))}\n"
            f"❤️ ئامۆژگارکردن: {format_number(d.get('like', 0))}\n"
            f"🔁 هاوبەشکردن: {format_number(d.get('share', 0))}\n"
            f"💬 لێدوانەکان: {format_number(d.get('comment', 0))}\n"
            f"⭐ پاشەکەوتکراو: {format_number(d.get('download', 0))}"
        )
        await query.answer(stats_text, show_alert=True)
        return

    if data.startswith("dl_"):
        action = data.split("_")[1]

        user_data = await get_user_data(user_id)
        if not user_data:
            await query.answer("⚠️ کاتی دەمارە تەواو بووە، دووبارە لینکەکە بنێرە.", show_alert=True)
            return

        details = user_data["details"]
        creator = user_data["creator"]
        raw_title = details.get('title', '')
        file_name_title = clean_title(raw_title)

        stats_keyboard = [
            [
                InlineKeyboardButton(f"👁 {format_number(details.get('views'))}", callback_data="stat_show_all"),
                InlineKeyboardButton(f"❤️ {format_number(details.get('like'))}", callback_data="stat_show_all")
            ],
            [
                InlineKeyboardButton(f"🔁 {format_number(details.get('share'))}", callback_data="stat_show_all"),
                InlineKeyboardButton(f"💬 {format_number(details.get('comment'))}", callback_data="stat_show_all")
            ]
        ]

        formatted_caption = (
            f"🎬 <b>{html.escape(file_name_title)}...</b>\n"
            f"👤 <b>{html.escape(creator)}</b>\n\n"
            f"🤖 <i>داگیرسێندراوە لە بۆتمان</i>"
        )

        if action == "video":
            await query.answer("ڤیدیۆکە داگیرسێندرێت...", show_alert=False)
            await query.message.edit_caption(
                caption="<b>⬇️ ڤیدیۆکە داگیرسێندرێت... تکایە چاوەڕوان بە.</b>",
                parse_mode=ParseMode.HTML
            )

            ctrl_buttons = [[
                InlineKeyboardButton("🎵 داگرتنی دەنگ", callback_data="dl_audio"),
                InlineKeyboardButton("❌ داخستن", callback_data="close")
            ]]
            full_keyboard = stats_keyboard + ctrl_buttons

            try:
                media = InputMediaVideo(
                    media=details["video"]["play"],
                    caption=formatted_caption,
                    parse_mode=ParseMode.HTML
                )
                await query.message.edit_media(media, reply_markup=InlineKeyboardMarkup(full_keyboard))
                await increment_downloads(user_id)
            except Exception:
                dl_button = [[InlineKeyboardButton("📥 داگرتنی ڤیدیۆ", url=details["video"]["play"])]]
                await query.message.edit_caption(
                    caption=f"<b>⚠️ ڤیدیۆکە زۆر گەورەیە، لە ئێرەوە داگرە:</b>\n\n{formatted_caption}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(dl_button)
                )

        if action == "audio":
            await query.answer("دەنگەکە داگیرسێندرێت...", show_alert=False)
            await query.message.edit_caption(
                caption="<b>⬇️ دەنگەکە داگیرسێندرێت... تکایە چاوەڕوان بە.</b>",
                parse_mode=ParseMode.HTML
            )

            ctrl_buttons = [[
                InlineKeyboardButton("🎥 داگرتنی ڤیدیۆ", callback_data="dl_video"),
                InlineKeyboardButton("❌ داخستن", callback_data="close")
            ]]
            full_keyboard = stats_keyboard + ctrl_buttons

            media = InputMediaAudio(
                media=details["audio"]["play"],
                caption=formatted_caption,
                parse_mode=ParseMode.HTML,
                title=file_name_title,
                performer=creator,
                filename=f"{file_name_title}.mp3"
            )

            try:
                await query.message.edit_media(media, reply_markup=InlineKeyboardMarkup(full_keyboard))
                await increment_downloads(user_id)
            except Exception:
                await query.message.edit_caption(
                    caption="❌ هەڵەیەک ڕوویدا لە بارکردنی دەنگ. دووبارە هەوڵ بدەرەوە.",
                    parse_mode=ParseMode.HTML
                )

# ══════════════════════════════════════════
#   مەسیجی ئاسایی (لینکی تیکتۆک)
# ══════════════════════════════════════════

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text_lower = update.message.text.lower()
    if "tiktok.com" not in text_lower and "vm.tiktok" not in text_lower:
        await update.message.reply_text(
            "⚠️ <b>تکایە لینکی تیکتۆک بنێرە.</b>\n\n"
            "نموونە: <code>https://www.tiktok.com/@user/video/123456</code>",
            parse_mode=ParseMode.HTML,
            reply_to_message_id=update.message.message_id
        )
        return

    url = update.message.text.strip()
    status_msg = await update.message.reply_text(
        "🔍 <b>گەڕان بۆ ڤیدیۆکەت... تکایە چاوەڕوان بە.</b>",
        parse_mode=ParseMode.HTML,
        reply_to_message_id=update.message.message_id
    )

    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            r = await client.get(API_URL + url)
            data = r.json()
            if not data.get("ok"):
                await status_msg.edit_text(
                    "❌ <b>هەڵە:</b> ڤیدیۆکە نەدۆزرایەوە یان تایبەتە.",
                    parse_mode=ParseMode.HTML
                )
                return

            video = data["data"]
            details = video["details"]

            await save_user_data(update.message.from_user.id, {
                "last_url": url,
                "creator": video["creator"],
                "details": details
            })

            safe_title = clean_title(details.get('title', ''))

            caption = (
                f"🎬 <b>{html.escape(safe_title)}...</b>\n"
                f"👤 <b>دروستکەر:</b> {html.escape(video['creator'])}\n"
                f"⏱ <b>ماوە:</b> {details.get('duration', 0)} چرکە\n\n"
                "📥 <i>فۆرماتێک هەڵبژێرە بۆ داگرتن:</i>"
            )

            keyboard = [
                [
                    InlineKeyboardButton("🎥 داگرتنی ڤیدیۆ", callback_data="dl_video"),
                    InlineKeyboardButton("🎵 داگرتنی دەنگ", callback_data="dl_audio")
                ],
                [
                    InlineKeyboardButton("📊 ئامارەکان", callback_data="stat_show_all"),
                    InlineKeyboardButton("❌ داخستن", callback_data="close")
                ]
            ]

            await status_msg.edit_media(
                InputMediaPhoto(details["cover"]["cover"], caption=caption, parse_mode=ParseMode.HTML),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logging.error(e)
            await status_msg.edit_text(
                "❌ <b>هەڵەیەک ڕوویدا. تکایە دووبارە هەوڵ بدەرەوە.</b>",
                parse_mode=ParseMode.HTML
            )

# ══════════════════════════════════════════
#   دامەزراندنی بۆت
# ══════════════════════════════════════════

ptb_app = ApplicationBuilder().token(TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CommandHandler("help", help_command))
ptb_app.add_handler(CommandHandler("stats", stats_command))
ptb_app.add_handler(CallbackQueryHandler(button_handler))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

@app.post("/")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, ptb_app.bot)
    async with ptb_app:
        await ptb_app.process_update(update)
    return {"ok": True}

@app.get("/")
async def health():
    return {"status": "active", "bot": "TikTok Downloader KU", "version": "2.0"}
