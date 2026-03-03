import os
import time
import logging
import httpx
import re
import html
import asyncio
import random
import string
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

OWNER_ID = 5977475208 
admins_list = {OWNER_ID} 
forced_channels = []  
blocked_users = set()

SESSION_EXPIRE = 600
API_TIMEOUT = 60
START_TIME = time.time()

logging.basicConfig(level=logging.INFO)
app = FastAPI()

# ---------------- فەنکشنە یارمەتیدەرەکان ---------------- #
def get_random_id(length=4):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

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

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    return user_id in admins_list or user_id == OWNER_ID

def is_blocked(user_id):
    return user_id in blocked_users

# ---------------- داتابەیس ---------------- #
async def load_settings():
    global admins_list, forced_channels, blocked_users
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            r = await client.get(firebase_url("bot_settings"))
            if r.status_code == 200 and r.json():
                data = r.json()
                admins_list = set(data.get("admins", [OWNER_ID]))
                forced_channels = data.get("channels", [])
                blocked_users = set(data.get("blocked", []))
        except: pass

async def save_settings():
    settings = {"admins": list(admins_list), "channels": forced_channels, "blocked": list(blocked_users)}
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try: await client.put(firebase_url("bot_settings"), json=settings)
        except: pass

async def save_user_data(user_id: int, data: dict):
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        await client.put(firebase_url(f"users/{user_id}"), json=data)

async def is_user_exist(user_id: int):
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        r = await client.get(firebase_url(f"users/{user_id}"))
        return r.status_code == 200 and r.json() is not None

async def get_user_data(user_id: int):
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        r = await client.get(firebase_url(f"users/{user_id}"))
        if r.status_code != 200: return None
        data = r.json()
        if not data or int(time.time()) - data.get("timestamp", 0) > SESSION_EXPIRE: return None
        return data

# --- ناردنی ئاگادارکردنەوە بۆ ئەدمین ---
async def notify_admin_new_user(context, user):
    msg = (
        f"🔔 <b>بەکارهێنەرێکی نوێ هات!</b>\n\n"
        f"👤 <b>ناو:</b> {html.escape(user.first_name)}\n"
        f"🆔 <b>ئایدی:</b> <code>{user.id}</code>\n"
        f"🔗 <b>یوزەر:</b> @{user.username if user.username else 'نییە'}\n"
        f"🕐 <b>کات:</b> {get_current_time()}"
    )
    try: await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode=ParseMode.HTML)
    except: pass

# --- پشکنینی جۆینی ناچاری ---
async def check_user_subscription(user_id, context):
    if not forced_channels: return True, []
    not_joined = []
    for channel in forced_channels:
        try:
            ch = channel.replace('@', '')
            member = await context.bot.get_chat_member(chat_id=f"@{ch}", user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                not_joined.append(channel)
        except: pass
    return len(not_joined) == 0, not_joined

# --- کیبۆردەکان ---
def get_main_keyboard(user_id):
    keyboard = [[InlineKeyboardButton("📥 دابەزاندنی ڤیدیۆ", callback_data="cmd_download")],[
            InlineKeyboardButton("ℹ️ ڕێنمایی", callback_data="cmd_help"),
            InlineKeyboardButton("📢 کەناڵی بۆت", url=CHANNEL_URL)
        ]]
    if is_admin(user_id): keyboard.append([InlineKeyboardButton("👑 پانێڵی ئەدمین", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 ئامارەکان", callback_data="admin_stats"), InlineKeyboardButton("📢 ناردنی گشتی", callback_data="admin_broadcast_ask")],
        [InlineKeyboardButton("📢 چەناڵەکان", callback_data="manage_channels_menu"), InlineKeyboardButton("👥 ئەدمینەکان", callback_data="manage_admins_menu")],
        [InlineKeyboardButton("🔙 گەڕانەوە", callback_data="cmd_start")]
    ])

# ---------------- فەرمانەکان ---------------- #
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_blocked(user.id): return
    
    if not is_admin(user.id):
        if not await is_user_exist(user.id):
            asyncio.create_task(notify_admin_new_user(context, user))
            await save_user_data(user.id, {"joined": True, "name": user.first_name})

    is_sub, not_joined = await check_user_subscription(user.id, context)
    if not is_sub and not is_admin(user.id):
        text = "<b>⚠️ تکایە سەرەتا جۆینی ئەم چەناڵانە بکە:</b>"
        keyboard = [[InlineKeyboardButton(f"📢 جۆین {ch}", url=f"https://t.me/{ch.replace('@','')}") for ch in not_joined]]
        keyboard.append([InlineKeyboardButton("✅ جۆینم کرد", callback_data="check_sub_start")])
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    admin_tag = "👑" if is_owner(user.id) else ("⚡" if is_admin(user.id) else "")
    text = (f"╔═══════════════════╗\n   👋 <b>بەخێربێیت {html.escape(user.first_name)} {admin_tag}</b>\n╚═══════════════════╝\n\n"
            f"🤖 <b>من بۆتێکی پێشکەوتووم بۆ دابەزاندنی تیکتۆک!</b>\n\n"
            f"📥 دەتوانیت ڤیدیۆ و وێنەکان (Slideshow) دابەزێنیت.\n\n"
            f"👇 <b>لینک بنێرە یان دوگمە دابگرە:</b>")
    
    if update.callback_query: await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user.id))
    else: await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user.id))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📚 <b>ڕێنمایی:</b> لینکەکە لێرە بنێرە و هەڵبژێرە ڤیدیۆ یان گۆرانی.")

# ---------------- بەڕێوەبردنی دوگمەکان ---------------- #
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if data == "check_sub_start": await start_command(update, context); return
    if data == "cmd_start": await start_command(update, context); return
    if data == "cmd_help": await help_command(update, context); return
    if data == "cmd_download": await query.message.reply_text("<b>🔗 فەرموو لینکەکە بنێرە:</b>", parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True)); return
    if data == "close": await query.message.delete(); return

    if data.startswith("dl_"):
        action = data.split("_")[1]
        user_data = await get_user_data(user_id)
        if not user_data: await query.answer("⚠️ کاتەکەت بەسەرچوو.", show_alert=True); return
        
        d = user_data["details"]
        creator = user_data["creator"]
        title = clean_title(d.get('title', ''))
        images = d.get("images", [])
        
        caption = (f"🎬 <b>{html.escape(title)}</b>\n👤 <b>{html.escape(creator)}</b>\n\n🤖 <b>@{context.bot.username}</b>")
        
        try:
            # ئەگەر داوای ڤیدیۆ کرا بەڵام وێنە بوو، یان داوای وێنە کرا
            if action == "photos" or (action == "video" and images):
                await query.answer("⏳ ناردنی وێنەکان...", show_alert=False)
                if not images: await query.answer("❌ هیچ وێنەیەک نییە.", show_alert=True); return
                
                media_group = [InputMediaPhoto(media=img) for img in images[:10]]
                media_group[0].caption = caption
                media_group[0].parse_mode = ParseMode.HTML
                await query.message.delete()
                await context.bot.send_media_group(chat_id=user_id, media=media_group)
            
            elif action == "video":
                await query.answer("⏳ ناردنی ڤیدیۆ...", show_alert=False)
                await query.message.edit_caption("<b>🚀 خەریکی ناردنی ڤیدیۆکەم...</b>", parse_mode=ParseMode.HTML)
                await query.message.edit_media(InputMediaVideo(media=d["video"]["play"], caption=caption, parse_mode=ParseMode.HTML))
            
            elif action == "audio":
                await query.answer("⏳ ناردنی گۆرانی...", show_alert=False)
                music_name = f"@j4ck_721s-{get_random_id()}"
                await query.message.edit_caption("<b>🚀 خەریکی ناردنی گۆرانییەکەم...</b>", parse_mode=ParseMode.HTML)
                await query.message.edit_media(InputMediaAudio(media=d["audio"]["play"], caption=caption, parse_mode=ParseMode.HTML, title=music_name, performer="@j4ck_721s"))

        except:
            link = d["video"]["play"] if not images else images[0]
            await query.message.edit_caption(f"⚠️ <b>هەڵەیەک ڕوویدا، دایبەزێنە: <a href='{link}'>لێرە</a></b>", parse_mode=ParseMode.HTML)
        return

    # --- پانێڵی ئەدمین ---
    if not is_admin(user_id): return
    if data == "admin_panel": await query.edit_message_text("👑 <b>پانێڵی ئەدمین</b>", parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard())
    elif data == "admin_stats":
        text = f"📊 <b>ئامارەکان:</b>\n👥 ئەدمین: {len(admins_list)}\n📢 چەناڵ: {len(forced_channels)}\n🕐 {get_current_time()}"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel")]]))
    elif data == "manage_admins_menu":
        if not is_owner(user_id): await query.answer("⛔ تەنیا خاوەن!", show_alert=True); return
        kb = [[InlineKeyboardButton("➕ زیادکردن", callback_data="add_admin_ask")], [InlineKeyboardButton(f"👤 {a}", callback_data=f"sel_admin_{a}") for a in admins_list if a != OWNER_ID], [InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel")]]
        await query.edit_message_text("👥 <b>بەڕێوەبردنی ئەدمینەکان</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("del_admin_"):
        target = int(data.split("_")[2])
        if target in admins_list: admins_list.remove(target); await save_settings(); await query.answer("✅ سڕایەوە")
        await query.edit_message_text("✅ <b>سڕایەوە.</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="manage_admins_menu")]]))

# ---------------- وەرگرتنی نامەکان ---------------- #
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text: return
    user_id = update.effective_user.id
    msg = update.message.text.strip()
    
    if update.message.reply_to_message and update.message.reply_to_message.from_user.is_bot:
        if "تکایە ئایدی ئەو کەسە بنێرە" in update.message.reply_to_message.text:
            try: admins_list.add(int(msg)); await save_settings(); await update.message.reply_text(f"✅ {msg} بوو بە ئەدمین.")
            except: await update.message.reply_text("❌ تەنها ژمارە بنێرە.")
            return
        if "تکایە یوزەری چەناڵەکە بنێرە" in update.message.reply_to_message.text:
            ch = msg if msg.startswith("@") else f"@{msg}"
            if ch not in forced_channels: forced_channels.append(ch); await save_settings(); await update.message.reply_text(f"✅ {ch} زیادکرا.")
            return

    if is_blocked(user_id) or "tiktok.com" not in msg: return 
    
    is_sub, _ = await check_user_subscription(user_id, context)
    if not is_sub and not is_admin(user_id): await update.message.reply_text("⚠️ تکایە جۆینی چەناڵەکان بکە (/start)"); return

    status_msg = await update.message.reply_text("<b>🔍 چاوەڕێ بکە...</b>", parse_mode=ParseMode.HTML)
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            r = await client.get(API_URL + msg)
            res = r.json()
            if not res.get("ok"): await status_msg.edit_text("❌ نەدۆزرایەوە!"); return
            
            video = res["data"]; details = video["details"]; images = details.get("images", [])
            await save_user_data(user_id, {"creator": video["creator"], "details": details})
            
            caption = (f"🎬 <b>{html.escape(clean_title(details.get('title')))}</b>\n👤 <b>{html.escape(video['creator'])}</b>\n\n🤖 <b>@{context.bot.username}</b>")
            
            if images:
                kb = [[InlineKeyboardButton(f"📸 وێنەکان ({len(images)})", callback_data="dl_photos")], [InlineKeyboardButton("🎵 گۆرانی", callback_data="dl_audio")], [InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]]
            else:
                kb = [[InlineKeyboardButton("🎥 ڤیدیۆ", callback_data="dl_video")], [InlineKeyboardButton("🎵 گۆرانی", callback_data="dl_audio")], [InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]]
            
            await status_msg.edit_media(InputMediaPhoto(details["cover"]["cover"], caption=caption, parse_mode=ParseMode.HTML), reply_markup=InlineKeyboardMarkup(kb))
        except: await status_msg.edit_text("❌ کێشەیەک ڕوویدا.")

# --- ڕێکخستنی کۆتایی ---
ptb_app = ApplicationBuilder().token(TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CallbackQueryHandler(button_handler))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

@app.post("/api/main")
async def webhook(req: Request):
    if not ptb_app.running: await ptb_app.initialize()
    await load_settings()
    data = await req.json()
    await ptb_app.process_update(Update.de_json(data, ptb_app.bot))
    return {"ok": True}

@app.get("/api/main")
async def health(): return {"status": "active"}
