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

# زانیارییەکان لە Environment Variables وەردەگیرێن
TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://www.api.hyper-bd.site/Tiktok/?url="
CHANNEL_URL = "https://t.me/jack_721_mod"
DB_URL = os.getenv("DB_URL")
DB_SECRET = os.getenv("DB_SECRET")

SESSION_EXPIRE = 600
API_TIMEOUT = 60

logging.basicConfig(level=logging.INFO)
app = FastAPI()

# --- Functions ---
def format_number(num):
    if not num: return "0"
    num = int(num)
    if num >= 1_000_000: return f"{num/1_000_000:.1f}M"
    if num >= 1_000: return f"{num/1_000:.1f}K"
    return str(num)

def clean_title(title):
    if not title: return "TikTok_Video"
    return re.sub(r'[\\/*?:"<>|]', '', title)[:50]

def process_caption(text):
    if not text: return ""
    text = re.sub(r'(@\w+|#\w+)', '', text)
    return html.escape(re.sub(r'\s+', ' ', text).strip())

def firebase_url(path: str):
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

async def save_user_data(user_id: int, data: dict):
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        await client.put(firebase_url(f"users/{user_id}"), json=data)

async def get_user_data(user_id: int):
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        r = await client.get(firebase_url(f"users/{user_id}"))
        if r.status_code != 200: return None
        data = r.json()
        if not data or int(time.time()) - data.get("timestamp", 0) > SESSION_EXPIRE: return None
        return data

# --- Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>👋 Welcome to Premium TikTok Downloader!</b>\n\n"
        "I can download No-Watermark videos and HQ audio.\n\n"
        "Tap <b>Download Now</b> to begin."
    )
    keyboard = [[InlineKeyboardButton("📥 Download Tiktok Video", callback_data="cmd_download")],
                [InlineKeyboardButton("❓ Help", callback_data="cmd_help"), InlineKeyboardButton("🔥 Update", url=CHANNEL_URL)]]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "<b>📚 How to use:</b>\n1. Copy TikTok link.\n2. Paste it here.\n3. Choose Video or Audio."
    keyboard = [[InlineKeyboardButton("📥 Download Now", callback_data="cmd_download"), InlineKeyboardButton("🔙 Back", callback_data="cmd_start")]]
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data == "cmd_start": await start_command(update, context)
    elif data == "cmd_help": await help_command(update, context)
    elif data == "cmd_download":
        await query.message.reply_text("<b>🔗 Please send me the TikTok URL.</b>", parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True))
    elif data == "close": await query.message.delete()
    elif data.startswith("dl_"):
        action = data.split("_")[1]
        user_data = await get_user_data(user_id)
        if not user_data:
            await query.answer("⚠️ Session expired.", show_alert=True)
            return
        
        d, creator = user_data["details"], user_data["creator"]
        title = clean_title(d.get('title', ''))
        caption = f"🎬 <b>{html.escape(title)}</b>\n👤 <b>{html.escape(creator)}</b>"

        if action == "video":
            media = InputMediaVideo(media=d["video"]["play"], caption=caption, parse_mode=ParseMode.HTML)
            await query.message.edit_media(media)
        elif action == "audio":
            media = InputMediaAudio(media=d["audio"]["play"], caption=caption, parse_mode=ParseMode.HTML)
            await query.message.edit_media(media)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text or "tiktok.com" not in update.message.text: return
    
    status_msg = await update.message.reply_text("<b>🔍 Searching...</b>", parse_mode=ParseMode.HTML)
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            r = await client.get(API_URL + update.message.text.strip())
            res = r.json()
            if not res.get("ok"):
                await status_msg.edit_text("❌ Video not found.")
                return

            video = res["data"]
            await save_user_data(update.message.from_user.id, {"creator": video["creator"], "details": video["details"]})

            caption = f"🎬 <b>{html.escape(clean_title(video['details'].get('title', '')))}</b>\n👤 <b>User:</b> {video['creator']}"
            keyboard = [[InlineKeyboardButton("🎥 Video", callback_data="dl_video"), InlineKeyboardButton("🎵 Audio", callback_data="dl_audio")],
                        [InlineKeyboardButton("❌ Close", callback_data="close")]]

            await status_msg.edit_media(InputMediaPhoto(video["details"]["cover"]["cover"], caption=caption, parse_mode=ParseMode.HTML), 
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await status_msg.edit_text("❌ Error occurred.")

# --- Setup Bot ---
ptb_app = ApplicationBuilder().token(TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CommandHandler("help", help_command))
ptb_app.add_handler(CallbackQueryHandler(button_handler))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

@app.post("/api/main")
async def webhook(req: Request):
    if not ptb_app.running:
        await ptb_app.initialize()
    
    data = await req.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"ok": True}

@app.get("/api/main")
async def health():
    return {"status": "active"}