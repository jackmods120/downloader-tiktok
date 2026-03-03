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

TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://www.api.hyper-bd.site/Tiktok/?url="
CHANNEL_URL = "https://t.me/Hyper_10_Squad"
DB_URL = os.getenv("DB_URL")
DB_SECRET = os.getenv("DB_SECRET")

SESSION_EXPIRE = 600
API_TIMEOUT = 60

logging.basicConfig(level=logging.INFO)
app = FastAPI()

def format_number(num):
    if not num:
        return "0"
    num = int(num)
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(num)

def clean_title(title):
    if not title:
        return "TikTok_Video"
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

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>👋 Welcome to the Premium TikTok Downloader!</b>\n\n"
        "I can help you download No-Watermark videos and High-Quality audio from TikTok instantly.\n\n"
        "<b>🚀 Features:</b>\n"
        "├ 🎥 <i>Watermark-free Videos</i>\n"
        "├ 🎵 <i>HQ Audio with Metadata</i>\n"
        "└ ⚡ <i>Fast Processing</i>\n\n"
        "Tap <b>Download Now</b> to begin or <b>Help</b> for instructions."
    )
    keyboard = [
        [InlineKeyboardButton("📥 Download Tiktok Video", callback_data="cmd_download")],
        [
            InlineKeyboardButton("❓ Help", callback_data="cmd_help"),
            InlineKeyboardButton("🔥 Update", url=CHANNEL_URL)
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>📚 How to use this Bot:</b>\n\n"
        "<b>1. Copy Link:</b>\n"
        "Go to TikTok, find the video you want, click 'Share', and copy the link.\n\n"
        "<b>2. Send Link:</b>\n"
        "Paste the link directly into this chat, or click the 'Download Now' button below.\n\n"
        "<b>3. Download:</b>\n"
        "Choose between Video or Audio format. You can also view live statistics like Views, Likes, and Shares.\n\n"
        "<i>Note: Make sure the video is not private.</i>"
    )
    keyboard = [
        [
            InlineKeyboardButton("📥 Download Video", callback_data="cmd_download"),
            InlineKeyboardButton("🔙 Back", callback_data="cmd_start")
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

    if data == "cmd_download":
        await query.answer("Please send the link.", show_alert=False)
        await query.message.reply_text(
            "<b>🔗 Please send me the TikTok URL you want to download.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True),
            reply_to_message_id=query.message.message_id
        )
        return

    if data == "close":
        await query.answer("Closed", show_alert=False)
        await query.message.delete()
        return

    if data == "stat_show_all":
        user_data = await get_user_data(user_id)
        if not user_data:
            await query.answer("⚠️ Session expired.", show_alert=False)
            return
        
        d = user_data["details"]
        stats_text = (
            f"📊 Video Statistics:\n\n"
            f"👁 Views: {d.get('views', 0)}\n"
            f"❤️ Likes: {d.get('like', 0)}\n"
            f"🔁 Shares: {d.get('share', 0)}\n"
            f"💬 Comments: {d.get('comment', 0)}\n"
            f"⭐ Saved: {d.get('download', 0)}"
        )
        await query.answer(stats_text, show_alert=True) 
        return

    if data.startswith("dl_"):
        action = data.split("_")[1]
        
        user_data = await get_user_data(user_id)
        if not user_data:
            await query.answer("⚠️ Session expired. Send link again.", show_alert=False)
            return

        details = user_data["details"]
        creator = user_data["creator"]
        raw_title = details.get('title', '')
        file_name_title = clean_title(raw_title)
        clean_caption_str = process_caption(raw_title)

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
        )

        if action == "video":
            await query.answer("Downloading Video...", show_alert=False)
            await query.message.edit_caption(
                caption="<b>⬇️ Downloading Video... Please wait.</b>",
                parse_mode=ParseMode.HTML
            )

            ctrl_buttons = [
                [InlineKeyboardButton("🎵 Down Audio", callback_data="dl_audio"), InlineKeyboardButton("❌ Close", callback_data="close")]
            ]
            full_keyboard = stats_keyboard + ctrl_buttons

            try:
                media = InputMediaVideo(
                    media=details["video"]["play"],
                    caption=formatted_caption,
                    parse_mode=ParseMode.HTML
                )
                await query.message.edit_media(media, reply_markup=InlineKeyboardMarkup(full_keyboard))
            except Exception:
                dl_button = [[InlineKeyboardButton("📥 Download Source File", url=details["video"]["play"])]]
                await query.message.edit_caption(
                    caption=f"<b>⚠️ Video too large.</b>\n\n{formatted_caption}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(dl_button)
                )

        if action == "audio":
            await query.answer("Downloading Audio...", show_alert=False)
            await query.message.edit_caption(
                caption="<b>⬇️ Downloading Audio... Please wait.</b>",
                parse_mode=ParseMode.HTML
            )
            
            ctrl_buttons = [
                [InlineKeyboardButton("🎥 Down Video", callback_data="dl_video"), InlineKeyboardButton("❌ Close", callback_data="close")]
            ]
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
            except Exception:
                await query.message.edit_caption(caption="❌ Failed to upload audio.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    if "tiktok.com" not in update.message.text:
        return

    url = update.message.text.strip()
    status_msg = await update.message.reply_text(
        "<b>🔍 Searching for your video... Please wait.</b>",
        parse_mode=ParseMode.HTML,
        reply_to_message_id=update.message.message_id
    )

    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            r = await client.get(API_URL + url)
            data = r.json()
            if not data.get("ok"):
                await status_msg.edit_text("<b>❌ Error:</b> Video not found or private.")
                return

            video = data["data"]
            details = video["details"]

            await save_user_data(update.message.from_user.id, {
                "last_url": url,
                "creator": video["creator"],
                "details": details
            })

            clean_caption_str = process_caption(details.get('title', ''))
            safe_title = clean_title(details.get('title', ''))
            
            caption = (
                f"🎬 <b>{html.escape(safe_title)}...</b>\n"
                f"👤 <b>User:</b> {html.escape(video['creator'])}\n"
                f"⏱ <b>Duration:</b> {details.get('duration', 0)}s\n\n"
                "👉 <i>Choose a format to download:</i>"
            )

            keyboard = [[
                InlineKeyboardButton("🎥 Down Video", callback_data="dl_video"),
                InlineKeyboardButton("🎵 Down Audio", callback_data="dl_audio")
            ], [
                InlineKeyboardButton("❌ Close", callback_data="close")
            ]]

            await status_msg.edit_media(
                InputMediaPhoto(details["cover"]["cover"], caption=caption, parse_mode=ParseMode.HTML),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logging.error(e)
            await status_msg.edit_text("<b>❌ An error occurred. Please try again later.</b>", parse_mode=ParseMode.HTML)

ptb_app = ApplicationBuilder().token(TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CommandHandler("help", help_command))
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
    return {"status": "active"}