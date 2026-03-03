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

# زانیاری خاوەن
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
            channel_username = channel.replace('@', '') if channel.startswith('@') else channel
            member = await context.bot.get_chat_member(chat_id=f"@{channel_username}", user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                not_joined.append(channel)
        except Exception:
            pass 
    
    return len(not_joined) == 0, not_joined

# --- داتابەیس (Firebase) ---
async def save_user_data(user_id: int, data: dict):
    data["timestamp"] = int(time.time())
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        await client.put(firebase_url(f"users/{user_id}"), json=data)

# فەنکشنێک بۆ پشکنین کە ئایا یوزەر کۆنە یان نوێ (بەبێ سەیرکردنی کات)
async def is_user_exist(user_id: int):
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        r = await client.get(firebase_url(f"users/{user_id}"))
        # ئەگەر داتا هەبوو (واتە NULL نەبوو)، کەواتە یوزەرەکە کۆنە
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
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=msg, parse_mode=ParseMode.HTML)
    except:
        pass

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
            InlineKeyboardButton("📢 ناردنی گشتی", callback_data="admin_broadcast_ask")
        ],
        [
            InlineKeyboardButton("📢 چەناڵەکان", callback_data="manage_channels_menu"),
            InlineKeyboardButton("👥 ئەدمینەکان", callback_data="manage_admins_menu")
        ],
        [InlineKeyboardButton("🔙 گەڕانەوە", callback_data="cmd_start")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------------- فەرمانەکان ---------------- #
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name
    
    if is_blocked(user_id):
        await update.message.reply_text("⛔ <b>تۆ بلۆک کراویت.</b>", parse_mode=ParseMode.HTML)
        return

    # --- پشکنینی یوزەری نوێ ---
    # تەنها ئەگەر ئەدمین نەبوو و لە داتابەیس نەبوو
    if not is_admin(user_id):
        user_exists = await is_user_exist(user_id)
        if not user_exists:
            # یوزەری نوێیە: ئاگادارکردنەوە بنێرە و تۆماری بکە
            asyncio.create_task(notify_admin_new_user(context, user))
            await save_user_data(user_id, {"joined": True, "name": first_name})

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
    
    admin_tag = "👑" if is_owner(user_id) else ("⚡" if is_admin(user_id) else "")
    
    text = (
        f"╔═══════════════════╗\n"
        f"   👋 <b>بەخێربێیت {html.escape(first_name)} {admin_tag}</b>\n"
        f"╚═══════════════════╝\n\n"
        f"🤖 <b>من باشترین بۆتی تیکتۆکم!</b>\n\n"
        f"📥 دەتوانیت ڤیدیۆ و وێنەکان دابەزێنیت:\n"
        f"   • 🎥 بێ لۆگۆ (No Watermark)\n"
        f"   • 📸 وێنە (Slideshow)\n"
        f"   • 🎵 گۆرانی (MP3)\n\n"
        f"👇 <b>لینک بنێرە یان دوگمە دابگرە:</b>"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user_id))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(user_id))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📚 <b>ڕێنمایی:</b> لینکەکەت کۆپی بکە و لێرە بنێرە."
    keyboard = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="cmd_start")]]
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- بەڕێوەبردنی دوگمەکان ---------------- #
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    # --- دوگمە گشتییەکان ---
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
            await query.answer("⚠️ کاتەکەت بەسەرچوو.", show_alert=True)
            return
        
        d = user_data["details"]
        creator = user_data["creator"]
        title = clean_title(d.get('title', ''))
        
        caption = (
            f"🎬 <b>{html.escape(title)}</b>\n"
            f"👤 <b>{html.escape(creator)}</b>\n"
            f"🤖 <b>@{context.bot.username}</b>"
        )
        buttons = [[InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]]
        
        try:
            if action == "video":
                await query.answer("⏳ ناردنی ڤیدیۆ...", show_alert=False)
                media = InputMediaVideo(media=d["video"]["play"], caption=caption, parse_mode=ParseMode.HTML)
                await query.message.edit_media(media, reply_markup=InlineKeyboardMarkup(buttons))
            
            elif action == "photos":
                await query.answer("⏳ ناردنی وێنەکان...", show_alert=False)
                images = d.get("images", [])
                if not images:
                    await query.answer("❌ هیچ وێنەیەک نییە.", show_alert=True)
                    return
                
                media_group = [InputMediaPhoto(media=img) for img in images[:10]]
                media_group[0].caption = caption
                media_group[0].parse_mode = ParseMode.HTML
                
                await query.message.delete()
                await context.bot.send_media_group(chat_id=user_id, media=media_group)
                
            elif action == "audio":
                await query.answer("⏳ ناردنی گۆرانی...", show_alert=False)
                media = InputMediaAudio(media=d["audio"]["play"], caption=caption, parse_mode=ParseMode.HTML, title=title, performer=creator)
                await query.message.edit_media(media, reply_markup=InlineKeyboardMarkup(buttons))

        except Exception as e:
            dl_url = d["video"]["play"] if action != "audio" else d["audio"]["play"]
            link_btn = [[InlineKeyboardButton("🔗 دابەزاندن بە لینک", url=dl_url)], [InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]]
            await query.message.edit_caption("⚠️ <b>قەبارەی گەورەیە، بە لینک دایبەزێنە.</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(link_btn))
        return

    # --- بەشی ئەدمین ---
    if not is_admin(user_id):
        await query.answer("⛔ تەنیا ئەدمین!", show_alert=True)
        return

    if data == "admin_panel":
        text = "👑 <b>پانێڵی ئەدمین</b>\n\nتکایە هەڵبژێرە:"
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_keyboard(user_id))
    
    elif data == "admin_stats":
        text = (
            f"📊 <b>ئامارەکان:</b>\n\n"
            f"👥 ئەدمینەکان: {len(admins_list)}\n"
            f"📢 چەناڵەکان: {len(forced_channels)}\n"
            f"🕐 {get_current_time()}"
        )
        back = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel")]]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(back))

    elif data == "admin_broadcast_ask":
        await query.message.reply_text(
            "📢 <b>تکایە ئەو پەیامە بنێرە کە دەتەوێت بۆ هەمووانی بنێریت:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        )

    # --- بەڕێوەبردنی ئەدمینەکان ---
    elif data == "manage_admins_menu":
        if not is_owner(user_id):
            await query.answer("⛔ تەنیا خاوەن!", show_alert=True)
            return
        keyboard = [
            [InlineKeyboardButton("➕ زیادکردنی ئەدمین", callback_data="add_admin_ask")],
            [InlineKeyboardButton("📋 لیستی ئەدمینەکان (سڕینەوە)", callback_data="list_admins")],
            [InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel")]
        ]
        await query.edit_message_text("👥 <b>بەڕێوەبردنی ئەدمینەکان</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "add_admin_ask":
        await query.message.reply_text(
            "🆔 <b>تکایە ئایدی ئەو کەسە بنێرە کە دەتەوێت بیکەیت بە ئەدمین:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        )

    elif data == "list_admins":
        keyboard = []
        for admin in admins_list:
            keyboard.append([InlineKeyboardButton(f"👤 ID: {admin}", callback_data=f"sel_admin_{admin}")])
        keyboard.append([InlineKeyboardButton("🔙 گەڕانەوە", callback_data="manage_admins_menu")])
        await query.edit_message_text("📋 <b>لیستی ئەدمینەکان:</b>\nکلیک لە ئایدی بکە بۆ سڕینەوە.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("sel_admin_"):
        target_id = int(data.split("_")[2])
        if target_id == OWNER_ID:
            await query.answer("⚠️ خاوەن ناسڕدرێتەوە!", show_alert=True)
            return
        
        keyboard = [
            [InlineKeyboardButton("🗑 بەڵێ، بیسڕەوە", callback_data=f"del_admin_{target_id}")],
            [InlineKeyboardButton("❌ نەخێر", callback_data="list_admins")]
        ]
        await query.edit_message_text(f"⚠️ <b>ئایە دڵنیایت ئەدمینی {target_id} دەسڕیتەوە؟</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_admin_"):
        target_id = int(data.split("_")[2])
        if target_id in admins_list:
            admins_list.remove(target_id)
            await query.answer("✅ سڕایەوە!", show_alert=True)
            keyboard = []
            for admin in admins_list:
                keyboard.append([InlineKeyboardButton(f"👤 ID: {admin}", callback_data=f"sel_admin_{admin}")])
            keyboard.append([InlineKeyboardButton("🔙 گەڕانەوە", callback_data="manage_admins_menu")])
            await query.edit_message_text("✅ <b>ئەدمینەکە سڕایەوە.</b>\nلیستی نوێ:", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("⚠️ ئەم ئەدمینە بوونی نەماوە.", show_alert=True)

    # --- بەڕێوەبردنی چەناڵەکان ---
    elif data == "manage_channels_menu":
        keyboard = [
            [InlineKeyboardButton("➕ زیادکردنی چەناڵ", callback_data="add_channel_ask")],
            [InlineKeyboardButton("📋 لیستی چەناڵەکان (سڕینەوە)", callback_data="list_channels")],
            [InlineKeyboardButton("🔙 گەڕانەوە", callback_data="admin_panel")]
        ]
        await query.edit_message_text("📢 <b>بەڕێوەبردنی چەناڵەکان</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "add_channel_ask":
        await query.message.reply_text(
            "📢 <b>تکایە یوزەری چەناڵەکە بنێرە (@username):</b>\nدڵنیابە بۆتەکە لەوێ ئەدمینە.",
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True)
        )

    elif data == "list_channels":
        if not forced_channels:
            keyboard = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="manage_channels_menu")]]
            await query.edit_message_text("❌ <b>هیچ چەناڵێک نییە.</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = []
        for ch in forced_channels:
            keyboard.append([InlineKeyboardButton(f"📢 {ch}", callback_data=f"sel_channel_{ch}")])
        keyboard.append([InlineKeyboardButton("🔙 گەڕانەوە", callback_data="manage_channels_menu")])
        await query.edit_message_text("📋 <b>لیستی چەناڵەکان:</b>\nکلیک لە چەناڵ بکە بۆ سڕینەوە.", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("sel_channel_"):
        target_ch = data.replace("sel_channel_", "")
        keyboard = [
            [InlineKeyboardButton("🗑 بەڵێ، بیسڕەوە", callback_data=f"del_channel_{target_ch}")],
            [InlineKeyboardButton("❌ نەخێر", callback_data="list_channels")]
        ]
        await query.edit_message_text(f"⚠️ <b>ئایە چەناڵی {target_ch} دەسڕیتەوە؟</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_channel_"):
        target_ch = data.replace("del_channel_", "")
        if target_ch in forced_channels:
            forced_channels.remove(target_ch)
            await query.answer("✅ سڕایەوە!", show_alert=True)
            if not forced_channels:
                keyboard = [[InlineKeyboardButton("🔙 گەڕانەوە", callback_data="manage_channels_menu")]]
                await query.edit_message_text("✅ <b>سڕایەوە. ئێستا لیست بەتاڵە.</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                keyboard = []
                for ch in forced_channels:
                    keyboard.append([InlineKeyboardButton(f"📢 {ch}", callback_data=f"sel_channel_{ch}")])
                keyboard.append([InlineKeyboardButton("🔙 گەڕانەوە", callback_data="manage_channels_menu")])
                await query.edit_message_text("✅ <b>چەناڵەکە سڕایەوە.</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("⚠️ بوونی نەماوە.", show_alert=True)

# ---------------- وەرگرتنی نامەکان ---------------- #
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text: return
    user_id = update.effective_user.id
    msg_text = update.message.text.strip()
    
    # --- پشکنینی Reply (بۆ وەڵامدانەوەی پرسیارەکانی بۆت) ---
    if update.message.reply_to_message and update.message.reply_to_message.from_user.is_bot:
        original_text = update.message.reply_to_message.text
        
        # 1. زیادکردنی ئەدمین
        if "تکایە ئایدی ئەو کەسە بنێرە" in original_text:
            if not is_owner(user_id): return
            try:
                new_id = int(msg_text)
                admins_list.add(new_id)
                await update.message.reply_text(f"✅ <b>پیرۆزە!</b> ئایدی {new_id} کرا بە ئەدمین.", parse_mode=ParseMode.HTML)
            except:
                await update.message.reply_text("❌ <b>هەڵە!</b> تکایە تەنها ژمارە بنێرە.", parse_mode=ParseMode.HTML)
            return

        # 2. زیادکردنی چەناڵ
        if "تکایە یوزەری چەناڵەکە بنێرە" in original_text:
            if not is_admin(user_id): return
            ch_name = msg_text if msg_text.startswith("@") else f"@{msg_text}"
            if ch_name not in forced_channels:
                forced_channels.append(ch_name)
                await update.message.reply_text(f"✅ <b>سەرکەوتوو بوو!</b> چەناڵی {ch_name} زیادکرا.", parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text("⚠️ ئەم چەناڵە پێشتر هەیە.", parse_mode=ParseMode.HTML)
            return

        # 3. ناردنی گشتی
        if "تکایە ئەو پەیامە بنێرە" in original_text:
            if not is_admin(user_id): return
            await update.message.reply_text(f"✅ <b>پەیامەکەت نێردرا:</b>\n\n{msg_text}", parse_mode=ParseMode.HTML)
            return

    # --- بەشی داونلۆدی تیکتۆک ---
    if is_blocked(user_id): return
    if "tiktok.com" not in msg_text: return 

    if not is_admin(user_id) and forced_channels:
        is_sub, _ = await check_user_subscription(user_id, context)
        if not is_sub:
            await update.message.reply_text("⚠️ تکایە سەرەتا جۆینی چەناڵەکان بکە (بنێرە /start)")
            return

    status_msg = await update.message.reply_text("<b>🔍 دەگەڕێم بەدوای لینکەکەدا...</b>", parse_mode=ParseMode.HTML)

    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        try:
            r = await client.get(API_URL + msg_text)
            res = r.json()
            
            if not res.get("ok"):
                await status_msg.edit_text("<b>❌ نەدۆزرایەوە!</b>")
                return

            video = res["data"]
            details = video["details"]
            
            # پشکنین بۆ ئەوەی بزانین وێنەیە (Slideshow) یان ڤیدیۆ
            images = details.get("images")
            is_slideshow = images and len(images) > 0
            
            # سەیڤکردنی داتا
            await save_user_data(user_id, {"creator": video["creator"], "details": details})

            title = clean_title(details.get('title', ''))
            
            caption = (
                f"╔═══════════════════╗\n"
                f"   ✅ <b>دۆزرایەوە!</b>\n"
                f"╚═══════════════════╝\n\n"
                f"📝 <b>ناونیشان:</b> {html.escape(title)}\n"
                f"👤 <b>خاوەن:</b> {html.escape(video['creator'])}\n\n"
                f"📊 <b>ئامارەکان:</b>\n"
                f"👁 {format_number(details.get('views'))} | ❤️ {format_number(details.get('like'))}\n\n"
                f"👇 <b>فۆرماتێک هەڵبژێرە:</b>"
            )

            # گۆڕینی دوگمەکان بەپێی جۆری پۆستەکە
            if is_slideshow:
                keyboard = [
                    [InlineKeyboardButton(f"📸 وێنەکان ({len(images)})", callback_data="dl_photos")],
                    [InlineKeyboardButton("🎵 گۆرانی (MP3)", callback_data="dl_audio")],
                    [InlineKeyboardButton("🗑 سڕینەوە", callback_data="close")]
                ]
            else:
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
    return {"status": "active", "version": "Ultimate 3.0"}
