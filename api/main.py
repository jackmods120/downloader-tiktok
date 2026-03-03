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

# --- زانیارییەکان ---
TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://www.api.hyper-bd.site/Tiktok/?url="
CHANNEL_URL = "https://t.me/jack_721_mod"  # لێرە لینکی کەناڵی خۆت دابنێ
DB_URL = os.getenv("DB_URL")
DB_SECRET = os.getenv("DB_SECRET")

SESSION_EXPIRE = 600  # کاتی مانەوەی زانیارییەکان (١٠ خولەک)
API_TIMEOUT = 60

logging.basicConfig(level=logging.INFO)
app = FastAPI()

# --- فەنکشنە یاریدەدەرەکان ---
def format_number(num):
    """ژمارەکان کورت دەکاتەوە (١٠٠٠ -> 1K)"""
    if not num: return "0"
    num = int(num)
    if num >= 1_000_000: return f"{num/1_000_000:.1f}M"
    if num >= 1_000: return f"{num/1_000:.1f}K"
    return str(num)

def clean_title(title):
    """ناونیشانەکە پاک دەکاتەوە لە هێمای زیادە"""
    if not title: return "TikTok_Video"
    safe_title = re.sub(r'[\\/*?:"<>|]', '', title)
    return safe_title[:50]

def firebase_url(path: str):
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

async def save_user_data(user_id: int, data: dict):
    """زانیاری بەکارهێنەر کاتی سەیڤ دەکات"""
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        await client.put(firebase_url(f"users/{user_id}"), json=data)

async def get_user_data(user_id: int):
    """وەرگرتنەوەی زانیارییەکان"""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        r = await client.get(firebase_url(f"users/{user_id}"))
        if r.status_code != 200: return None
        data = r.json()
        if not data or int(time.time()) - data.get("timestamp", 0) > SESSION_EXPIRE: return None
        return data

# --- فەرمانەکان (Commands) ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>👋 سڵاو بەڕێزم! بەخێربێیت بۆ بۆتی تیکتۆک.</b>\n\n"
        "من دەتوانم ڤیدیۆکانی تیکتۆک بەبێ لۆگۆ (Watermark) و بە کوالێتی بەرز بۆت دابەزێنم.\n\n"
        "<b>🚀 تایبەتمەندییەکان:</b>\n"
        "🎥 دابەزاندنی ڤیدیۆ بەبێ لۆگۆ\n"
        "🎵 دابەزاندنی گۆرانی (MP3)\n"
        "📊 پیشاندانی ئامارەکان (لایک و ڤیو)\n\n"
        "👇 <b>بۆ دەستپێکردن لینکێک بنێرە یان دوگمەی خوارەوە دابگرە:</b>"
    )
    keyboard = [
        [InlineKeyboardButton("📥 دابەزاندنی ڤیدیۆ", callback_data="cmd_download")],
        [InlineKeyboardButton("ℹ️ ڕێنمایی", callback_data="cmd_help"), InlineKeyboardButton("📢 کەناڵی بۆت", url=CHANNEL_URL)]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>📚 ڕێنمایی بەکارهێنان:</b>\n\n"
        "1️⃣ بڕۆ ناو تیکتۆک و لینکەکە کۆپی بکە (Copy Link).\n"
        "2️⃣ لینکەکە بنێرە بۆ ئەم بۆتە.\n"
        "3️⃣ هەڵبژێرە کە ڤیدیۆت دەوێت یان گۆرانی.\n\n"
        "<i>تێبینی: دڵنیابە لەوەی ئەکاونتەکە پرایڤت (Private) نییە.</i>"
    )
    keyboard = [[InlineKeyboardButton("📥 ئێستا دایبەزێنە", callback_data="cmd_download"), InlineKeyboardButton("🔙 گەڕانەوە", callback_data="cmd_start")]]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

# --- بەڕێوەبردنی دوگمەکان ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data == "cmd_start": await start_command(update, context)
    elif data == "cmd_help": await help_command(update, context)
    elif data == "cmd_download":
        await query.message.reply_text("<b>🔗 فەرموو لینکەکەم بۆ بنێرە:</b>", parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True))
    elif data == "close": 
        await query.answer("داخرا 🗑")
        await query.message.delete()
    
    elif data.startswith("dl_"):
        action = data.split("_")[1]
        user_data = await get_user_data(user_id)
        
        if not user_data:
            await query.answer("⚠️ کاتەکەت بەسەرچوو، تکایە لینکەکە بنێرەوە.", show_alert=True)
            return
        
        d = user_data["details"]
        creator = user_data["creator"]
        title = clean_title(d.get('title', ''))
        
        # دروستکردنی کەپشنێکی جوان
        caption = (
            f"🎬 <b>{html.escape(title)}</b>\n\n"
            f"👤 <b>خاوەنی ڤیدیۆ:</b> {html.escape(creator)}\n"
            f"👁 <b>بینەر:</b> {format_number(d.get('views'))} | ❤️ <b>لایک:</b> {format_number(d.get('like'))}\n"
            f"🤖 <i>Downloaded by @{context.bot.username}</i>"
        )

        buttons = [[InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]]

        try:
            if action == "video":
                await query.answer("⏳ کەمێک بۆستە، ڤیدیۆکە دەنێردرێت...", show_alert=False)
                await query.message.edit_caption("<b>🚀 خەریکی ناردنی ڤیدیۆکەم...</b>", parse_mode=ParseMode.HTML)
                
                media = InputMediaVideo(media=d["video"]["play"], caption=caption, parse_mode=ParseMode.HTML)
                await query.message.edit_media(media, reply_markup=InlineKeyboardMarkup(buttons))
            
            elif action == "audio":
                await query.answer("⏳ کەمێک بۆستە، گۆرانییەکە دەنێردرێت...", show_alert=False)
                await query.message.edit_caption("<b>🚀 خەریکی ناردنی گۆرانییەکەم...</b>", parse_mode=ParseMode.HTML)
                
                media = InputMediaAudio(media=d["audio"]["play"], caption=caption, parse_mode=ParseMode.HTML, title=title, performer=creator)
                await query.message.edit_media(media, reply_markup=InlineKeyboardMarkup(buttons))
        
        except Exception as e:
            # ئەگەر قەبارەی ڤیدیۆکە گەورە بوو یان کێشە هەبوو
            link_btn = [[InlineKeyboardButton("🔗 دابەزاندن بە لینک", url=d["video"]["play"])], [InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]]
            await query.message.edit_caption(
                caption=f"⚠️ <b>نەتوانرا ڤیدیۆکە ڕاستەوخۆ بنێردرێت (قەبارەی گەورەیە).</b>\nتکایە لە ڕێگەی لینکەکەوە دایبەزێنە.\n\n{caption}",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(link_btn)
            )

# --- وەرگرتنی نامە و لینک ---
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text: return
    
    msg_text = update.message.text.strip()
    
    # پشکنین بۆ ئەوەی بزانین لینکەکە تیکتۆکە یان نا
    if "tiktok.com" not in msg_text:
        return # ئەگەر تیکتۆک نەبوو وەڵام ناداتەوە (بۆ ئەوەی لە گرووپ بێزارکەر نەبێت)

    status_msg = await update.message.reply_text("<b>🔍 دەگەڕێم بەدوای ڤیدیۆکەدا، تکایە بۆستە...</b>", parse_mode=ParseMode.HTML, reply_to_message_id=update.message.message_id)

    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            r = await client.get(API_URL + msg_text)
            res = r.json()
            
            if not res.get("ok"):
                await status_msg.edit_text("<b>❌ ڤیدیۆکە نەدۆزرایەوە!</b>\nدڵنیابەوە لینکەکە ڕاستە یان ڤیدیۆکە سڕاوەتەوە.")
                return

            video = res["data"]
            details = video["details"]
            
            # سەیڤکردنی زانیاری بۆ بەکارهێنان لە دوگمەکان
            await save_user_data(update.message.from_user.id, {"creator": video["creator"], "details": details})

            title = clean_title(details.get('title', ''))
            
            caption = (
                f"✅ <b>ڤیدیۆکە دۆزرایەوە!</b>\n\n"
                f"📝 <b>ناونیشان:</b> {html.escape(title)}\n"
                f"👤 <b>خاوەن:</b> {html.escape(video['creator'])}\n\n"
                f"📊 <b>ئامارەکان:</b>\n"
                f"👁 {format_number(details.get('views'))} | ❤️ {format_number(details.get('like'))} | 💬 {format_number(details.get('comment'))}\n\n"
                "👇 <b>فۆرماتێک هەڵبژێرە بۆ دابەزاندن:</b>"
            )

            keyboard = [
                [InlineKeyboardButton("🎥 ڤیدیۆ (بێ لۆگۆ)", callback_data="dl_video")],
                [InlineKeyboardButton("🎵 گۆرانی (MP3)", callback_data="dl_audio")],
                [InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]
            ]

            await status_msg.edit_media(
                InputMediaPhoto(details["cover"]["cover"], caption=caption, parse_mode=ParseMode.HTML), 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logging.error(f"Error: {e}")
            await status_msg.edit_text("❌ کێشەیەک ڕوویدا، تکایە دواتر هەوڵ بدەرەوە.")

# --- ڕێکخستنی بۆت ---
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
    return {"status": "active", "dev": "Kurdish Developer"}
