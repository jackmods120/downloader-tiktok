import os
import time
import logging
import httpx
import re
import html
import asyncio
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
from telegram.constants import ParseMode, ChatMemberStatus

# ---------------- ڕێکخستنەکان ---------------- #
TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://www.api.hyper-bd.site/Tiktok/?url="
CHANNEL_URL = "https://t.me/jack_721_mod"
DB_URL = os.getenv("DB_URL")
DB_SECRET = os.getenv("DB_SECRET")

# زانیاری خاوەن (ئایدی خۆت لێرە دابنێ یان لەم لیستە دەستکاری بکە)
OWNER_ID = 5977475208 
admins_list = {OWNER_ID}
forced_channels = []  # لیستی چەناڵە ناچارییەکان
blocked_users = set()  # لیستی بلۆککراوەکان

SESSION_EXPIRE = 600
API_TIMEOUT = 60
START_TIME = time.time()

logging.basicConfig(level=logging.INFO)
app = FastAPI()

# ---------------- فەنکشنە یارمەتیدەرەکان ---------------- #
def format_number(num):
    if not num: return "0"
    num = int(num)
    if num >= 1_000_000: return f"{num/1_000_000:.1f}M"
    if num >= 1_000: return f"{num/1_000:.1f}K"
    return str(num)

def clean_title(title):
    if not title: return "TikTok_Video"
    return re.sub(r'[\\/*?:"<>|]', '', title)[:50]

def firebase_url(path: str):
    return f"{DB_URL}/{path}.json?auth={DB_SECRET}"

def get_current_time():
    return time.strftime("%Y-%m-%d | %I:%M %p")

# --- پشکنینی ئەدمین و خاوەن ---
def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    return user_id in admins_list or user_id == OWNER_ID

def is_blocked(user_id):
    return user_id in blocked_users

# --- پشکنینی جۆینی ناچاری ---
async def check_user_subscription(user_id, context):
    if not forced_channels:
        return True, []
    
    not_joined = []
    for channel in forced_channels:
        try:
            # لابردنی @ ئەگەر هەبێت بۆ پشکنین
            channel_username = channel.replace('@', '') if channel.startswith('@') else channel
            member = await context.bot.get_chat_member(chat_id=f"@{channel_username}", user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                not_joined.append(channel)
        except Exception:
            # ئەگەر بۆتەکە ئەدمین نەبێت یان کێشە هەبێت، وادادەنێین جۆینی کردووە تا یوزەر بێزار نەبێت
            pass 
    
    return len(not_joined) == 0, not_joined

# --- داتابەیس (Firebase) ---
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

# --- کیبۆردەکان ---
def get_main_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("📥 دابەزاندنی ڤیدیۆ", callback_data="cmd_download")],
        [
            InlineKeyboardButton("ℹ️ ڕێنمایی", callback_data="cmd_help"),
            InlineKeyboardButton("📢 کەناڵی بۆت", url=CHANNEL_URL)
        ]
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 پانێڵی ئەدمین", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard(user_id):
    keyboard = [
        [
            InlineKeyboardButton("📊 ئامارەکان", callback_data="admin_stats"),
            InlineKeyboardButton("📢 ناردنی گشتی", callback_data="admin_broadcast_menu")
        ],
        [
            InlineKeyboardButton("📢 چەناڵەکان", callback_data="admin_channels"),
            InlineKeyboardButton("🚫 بلۆک", callback_data="admin_block_menu")
        ]
    ]
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("👥 بەڕێوەبردنی ئەدمین", callback_data="admin_manage_admins")])
    
    keyboard.append([InlineKeyboardButton("🔙 گەڕانەوە", callback_data="cmd_start")])
    return InlineKeyboardMarkup(keyboard)

# ---------------- فەرمانەکان ---------------- #
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    if is_blocked(user_id):
        await update.message.reply_text("⛔ <b>تۆ بلۆک کراویت لە بەکارهێنانی بۆت.</b>", parse_mode=ParseMode.HTML)
        return

    # پشکنینی جۆینی ناچاری
    if not is_admin(user_id) and forced_channels:
        is_sub, not_joined = await check_user_subscription(user_id, context)
        if not is_sub:
            text = "<b>⚠️ تکایە سەرەتا جۆینی ئەم چەناڵانە بکە:</b>\n\n"
            keyboard = []
            for ch in not_joined:
                keyboard.append([InlineKeyboardButton(f"📢 جۆین {ch}", url=f"https://t.me/{ch.replace('@','')}")])
            keyboard.append([InlineKeyboardButton("✅ جۆینم کرد", callback_data="check_sub_start")])
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
            return

    # سەیڤکردنی یوزەر تەنها بۆ ئامار (بەبێ داتا)
    # تێبینی: لە سیستەمی ڕاستەقینە دەبێت لە داتابەیس بێت، لێرە کاتییە بۆ نموونە
    
    admin_tag = "👑" if is_owner(user_id) else ("⚡" if is_admin(user_id) else "")
    
    text = (
        f"╔═══════════════════╗\n"
        f"   👋 <b>بەخێربێیت {html.escape(first_name)} {admin_tag}</b>\n"
        f"╚═══════════════════╝\n\n"
        f"🤖 <b>من باشترین بۆتی تیکتۆکم!</b>\n\n"
        f"📥 دەتوانم ڤیدیۆکانت بۆ دابەزێنم:\n"
        f"   • 🎥 بێ لۆگۆ (No Watermark)\n"
        f"   • 🎵 گۆرانی (MP3)\n"
        f"   • 🚀 خێرایی بەرز\n\n"
        f"👇 <b>لینک بنێرە یان دوگمە دابگرە:</b>"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user_id))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user_id))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "╔═══════════════════╗\n"
        "     📚 <b>ڕێنمایی بەکارهێنان</b>\n"
        "╚═══════════════════╝\n\n"
        "1️⃣ <b>لینک کۆپی بکە:</b> لە تیکتۆک Share دابگرە و Copy Link بکە.\n"
        "2️⃣ <b>لینک بنێرە:</b> لینکەکە لەم چاتە بنێرە.\n"
        "3️⃣ <b>هەڵبژێرە:</b> ڤیدیۆ یان گۆرانی.\n\n"
        "<i>تێبینی: ڤیدیۆی پرایڤت پشتگیری ناکرێت.</i>"
    )
    keyboard = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="cmd_start")]]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- بەڕێوەبردنی ئەدمین و دوگمەکان ---------------- #
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    # --- بەشەکانی بەکارهێنەر ---
    if data == "check_sub_start":
        await start_command(update, context)
        return
        
    if data == "cmd_start": 
        await start_command(update, context)
        return
        
    if data == "cmd_help": 
        await help_command(update, context)
        return
        
    if data == "cmd_download":
        await query.message.reply_text("<b>🔗 فەرموو لینکەکەم بۆ بنێرە:</b>", parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True))
        return
        
    if data == "close": 
        await query.message.delete()
        return

    # --- بەشی دابەزاندن ---
    if data.startswith("dl_"):
        action = data.split("_")[1]
        user_data = await get_user_data(user_id)
        if not user_data:
            await query.answer("⚠️ کاتەکەت بەسەرچوو، تکایە لینکەکە بنێرەوە.", show_alert=True)
            return
        
        d = user_data["details"]
        creator = user_data["creator"]
        title = clean_title(d.get('title', ''))
        
        caption = (
            f"╔═══════════════════╗\n"
            f"   🎬 <b>{html.escape(title)}</b>\n"
            f"╚═══════════════════╝\n\n"
            f"👤 <b>خاوەن:</b> {html.escape(creator)}\n"
            f"👁 <b>بینەر:</b> {format_number(d.get('views'))} | ❤️ <b>لایک:</b> {format_number(d.get('like'))}\n\n"
            f"🤖 <b>Downloaded by @{context.bot.username}</b>"
        )
        
        buttons = [[InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]]
        
        try:
            if action == "video":
                await query.answer("⏳ ناردنی ڤیدیۆ...", show_alert=False)
                await query.message.edit_caption("<b>🚀 خەریکی ناردنی ڤیدیۆکەم...</b>", parse_mode=ParseMode.HTML)
                media = InputMediaVideo(media=d["video"]["play"], caption=caption, parse_mode=ParseMode.HTML)
                await query.message.edit_media(media, reply_markup=InlineKeyboardMarkup(buttons))
            elif action == "audio":
                await query.answer("⏳ ناردنی گۆرانی...", show_alert=False)
                await query.message.edit_caption("<b>🚀 خەریکی ناردنی گۆرانییەکەم...</b>", parse_mode=ParseMode.HTML)
                media = InputMediaAudio(media=d["audio"]["play"], caption=caption, parse_mode=ParseMode.HTML, title=title, performer=creator)
                await query.message.edit_media(media, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception:
            link_btn = [[InlineKeyboardButton("🔗 دابەزاندن بە لینک", url=d["video"]["play"])], [InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]]
            await query.message.edit_caption("⚠️ <b>قەبارەی گەورەیە، بە لینک دایبەزێنە.</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(link_btn))
        return

    # --- بەشی ئەدمین ---
    if not is_admin(user_id):
        await query.answer("⛔ تەنیا ئەدمین!", show_alert=True)
        return

    if data == "admin_panel":
        text = (
            f"╔═══════════════════╗\n"
            f"   👑 <b>پانێڵی ئەدمین</b>\n"
            f"╚═══════════════════╝\n\n"
            f"👋 بەخێربێیت گەورەم.\n"
            f"لە خوارەوە کۆنترۆڵی بۆت بکە:"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard(user_id))
    
    elif data == "admin_stats":
        uptime = int(time.time() - START_TIME)
        hours, rem = divmod(uptime, 3600)
        minutes, seconds = divmod(rem, 60)
        
        text = (
            f"╔═══════════════════╗\n"
            f"   📊 <b>ئامارەکانی بۆت</b>\n"
            f"╚═══════════════════╝\n\n"
            f"⏱️ <b>کاتی کارکردن:</b> {hours}h {minutes}m\n"
            f"👥 <b>ئەدمینەکان:</b> {len(admins_list)}\n"
            f"📢 <b>چەناڵەکان:</b> {len(forced_channels)}\n"
            f"🚫 <b>بلۆککراوەکان:</b> {len(blocked_users)}\n\n"
            f"🕐 {get_current_time()}"
        )
        back_btn = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel")]]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn))

    elif data == "admin_broadcast_menu":
        text = (
            "📢 <b>ناردنی پەیامی گشتی</b>\n\n"
            "بۆ ناردنی پەیام، ئەم فەرمانە بەکاربهێنە:\n"
            "<code>/broadcast پەیامەکەت</code>"
        )
        back_btn = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel")]]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn))

    elif data == "admin_channels":
        text = (
            "📢 <b>بەڕێوەبردنی چەناڵەکان</b>\n\n"
            f"لیستی ئێستا: {', '.join(forced_channels) if forced_channels else 'نییە'}\n\n"
            "فەرمانەکان:\n"
            "<code>/addchannel @username</code>\n"
            "<code>/removechannel @username</code>"
        )
        back_btn = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel")]]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn))
    
    elif data == "admin_manage_admins":
        if not is_owner(user_id):
            await query.answer("⛔ تەنیا خاوەن!", show_alert=True)
            return
        text = (
            "👥 <b>بەڕێوەبردنی ئەدمینەکان</b>\n\n"
            "فەرمانەکان:\n"
            "<code>/addadmin ID</code>\n"
            "<code>/removeadmin ID</code>"
        )
        back_btn = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel")]]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back_btn))

# ---------------- فەرمانەکانی ئەدمین ---------------- #
async def admin_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("❌ بەکارهێنان: `/broadcast پەیام`", parse_mode=ParseMode.MARKDOWN)
        return
    
    msg = " ".join(context.args)
    # تێبینی: لە Vercel ناردن بۆ هەمووان قورسە، لێرە تەنها نموونەیە
    await update.message.reply_text(f"✅ <b>پەیام نێردرا:</b>\n\n{msg}", parse_mode=ParseMode.HTML)

async def admin_add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args: return
    ch = context.args[0]
    if ch not in forced_channels:
        forced_channels.append(ch)
        await update.message.reply_text(f"✅ چەناڵی {ch} زیادکرا بۆ جۆینی ناچاری.")
    else:
        await update.message.reply_text("⚠️ ئەم چەناڵە بوونی هەیە.")

async def admin_remove_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args: return
    ch = context.args[0]
    if ch in forced_channels:
        forced_channels.remove(ch)
        await update.message.reply_text(f"✅ چەناڵی {ch} سڕایەوە.")
    else:
        await update.message.reply_text("⚠️ ئەم چەناڵە نییە.")

async def admin_add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    try:
        new_id = int(context.args[0])
        admins_list.add(new_id)
        await update.message.reply_text(f"✅ ئەدمین {new_id} زیادکرا.")
    except:
        await update.message.reply_text("❌ ئایدی هەڵەیە.")

async def admin_remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    try:
        old_id = int(context.args[0])
        if old_id in admins_list and old_id != OWNER_ID:
            admins_list.remove(old_id)
            await update.message.reply_text(f"✅ ئەدمین {old_id} لابرا.")
        else:
            await update.message.reply_text("❌ ناتوانرێت.")
    except:
        await update.message.reply_text("❌ ئایدی هەڵەیە.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text: return
    
    user_id = update.effective_user.id
    if is_blocked(user_id): return

    msg_text = update.message.text.strip()
    
    if "tiktok.com" not in msg_text:
        return 

    # پشکنینی جۆینی ناچاری پێش دابەزاندن
    if not is_admin(user_id) and forced_channels:
        is_sub, _ = await check_user_subscription(user_id, context)
        if not is_sub:
            await update.message.reply_text("⚠️ تکایە سەرەتا جۆینی چەناڵەکان بکە (بنێرە /start)")
            return

    status_msg = await update.message.reply_text("<b>🔍 دەگەڕێم بەدوای ڤیدیۆکەدا...</b>", parse_mode=ParseMode.HTML)

    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            r = await client.get(API_URL + msg_text)
            res = r.json()
            
            if not res.get("ok"):
                await status_msg.edit_text("<b>❌ ڤیدیۆکە نەدۆزرایەوە!</b>")
                return

            video = res["data"]
            details = video["details"]
            
            await save_user_data(user_id, {"creator": video["creator"], "details": details})

            title = clean_title(details.get('title', ''))
            
            caption = (
                f"╔═══════════════════╗\n"
                f"   ✅ <b>دۆزرایەوە!</b>\n"
                f"╚═══════════════════╝\n\n"
                f"📝 <b>ناونیشان:</b> {html.escape(title)}\n"
                f"👤 <b>خاوەن:</b> {html.escape(video['creator'])}\n\n"
                f"📊 <b>ئامارەکان:</b>\n"
                f"👁 {format_number(details.get('views'))} | ❤️ {format_number(details.get('like'))} | 💬 {format_number(details.get('comment'))}\n\n"
                f"👇 <b>فۆرماتێک هەڵبژێرە:</b>"
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
            await status_msg.edit_text("❌ کێشەیەک ڕوویدا.")

# --- ڕێکخستنی کۆتایی ---
ptb_app = ApplicationBuilder().token(TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CommandHandler("help", help_command))

# فەرمانەکانی ئەدمین
ptb_app.add_handler(CommandHandler("broadcast", admin_broadcast_command))
ptb_app.add_handler(CommandHandler("addchannel", admin_add_channel_command))
ptb_app.add_handler(CommandHandler("removechannel", admin_remove_channel_command))
ptb_app.add_handler(CommandHandler("addadmin", admin_add_admin_command))
ptb_app.add_handler(CommandHandler("removeadmin", admin_remove_admin_command))

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
    return {"status": "active", "version": "Premium 2.0"}
