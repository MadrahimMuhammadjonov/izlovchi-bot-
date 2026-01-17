#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import logging
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ============================================
# KONFIGURATSIYA
# ============================================
BOT_TOKEN = "8045123024:AAGdfjgOJAUosbf4SfUpmDQkh2qeGOirblc"
ADMIN_ID = 8228479175

API_ID = 36799342
API_HASH = "fcdf748b56fb519c6900d02e25ae2d62"
PHONE_NUMBER = "+998931317231"
SESSION_STRING = "1ApWapzMBu7wMtDnHS2BHSlKKIcR0O326szif2GpPek9MHzgLxHaafUzSGh864f--z_ImIsN8GkhzJY-T_TLRSyc2MdUBAX89sRsqUWumntyGQ1u0d0h3c0t0k_VSaqq3Mjjt401spd3TcLUgz8qb23Eh7PtVSvs1viHduuKXyExsUAkstyewIDamcQf2mlGQuoQiL5WBc63h5q6Roj-kff-xxr1TJB-3kag0XdKVKzS50xFWyXKBoixQ_XynUB1yk4qkaUbKv9ciCyZGy6yTRm3IgGk8Rb2BECId-p6fRR-jPsVemBhDZIOY2gwNNTrwty8I988h0lACcrT5Hyh9uX56KRlr8tc="

# Logging sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# DATABASE KLASSI
# ============================================
class Database:
    def __init__(self, db_name='bot_data.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE NOT NULL,
                group_name TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS personal_group (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT UNIQUE NOT NULL,
                group_name TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def add_keyword(self, keyword):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO keywords (keyword) VALUES (?)', (keyword,))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_keywords(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, keyword FROM keywords')
        keywords = cursor.fetchall()
        conn.close()
        return keywords
    
    def delete_keyword(self, keyword_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM keywords WHERE id = ?', (keyword_id,))
        conn.commit()
        conn.close()
    
    def add_search_group(self, group_id, group_name):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO search_groups (group_id, group_name) VALUES (?, ?)', 
                         (str(group_id), group_name))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_search_groups(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, group_id, group_name FROM search_groups')
        groups = cursor.fetchall()
        conn.close()
        return groups
    
    def delete_search_group(self, group_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM search_groups WHERE id = ?', (group_id,))
        conn.commit()
        conn.close()
    
    def add_personal_group(self, group_id, group_name):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM personal_group')
            cursor.execute('INSERT INTO personal_group (group_id, group_name) VALUES (?, ?)', 
                         (str(group_id), group_name))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
    
    def get_personal_group(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT group_id, group_name FROM personal_group LIMIT 1')
        group = cursor.fetchone()
        conn.close()
        return group
    
    def delete_personal_group(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM personal_group')
        conn.commit()
        conn.close()

# Database instance
db = Database()

# ============================================
# BOT QISMI
# ============================================
WAITING_KEYWORD = "waiting_keyword"
WAITING_SEARCH_GROUP = "waiting_search_group"
WAITING_PERSONAL_GROUP = "waiting_personal_group"

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("➕ Kalit so'z qo'shish", callback_data='add_keyword')],
        [InlineKeyboardButton("📋 Kalit so'zlarni ko'rish", callback_data='view_keywords')],
        [InlineKeyboardButton("🗑 Kalit so'zlarni o'chirish", callback_data='delete_keyword')],
        [InlineKeyboardButton("➕ Izlovchi guruh qo'shish", callback_data='add_search_group')],
        [InlineKeyboardButton("📋 Izlovchi guruhlarni ko'rish", callback_data='view_search_groups')],
        [InlineKeyboardButton("🗑 Izlovchi guruhni o'chirish", callback_data='delete_search_group')],
        [InlineKeyboardButton("➕ Shaxsiy guruh qo'shish", callback_data='add_personal_group')],
        [InlineKeyboardButton("📋 Shaxsiy guruhni ko'rish", callback_data='view_personal_group')],
        [InlineKeyboardButton("🗑 Shaxsiy guruhni o'chirish", callback_data='delete_personal_group')],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text(
            "👋 Assalomu alaykum!\n\n"
            "⚠️ Ushbu botdan faqat adminlar foydalana oladi."
        )
        return
    
    await update.message.reply_text(
        "👋 Assalomu alaykum, Admin!\n\n"
        "Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=get_main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    data = query.data
    
    if data == 'add_keyword':
        context.user_data['state'] = WAITING_KEYWORD
        await query.edit_message_text("📝 Yangi kalit so'z kiriting:\n\nBekor qilish uchun /cancel yuboring")
    
    elif data == 'view_keywords':
        keywords = db.get_keywords()
        text = "📋 Kalit so'zlar ro'yxati:\n\n" if keywords else "❌ Hozircha kalit so'zlar yo'q"
        if keywords:
            for idx, (kid, keyword) in enumerate(keywords, 1):
                text += f"{idx}. {keyword}\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]))
    
    elif data == 'delete_keyword':
        keywords = db.get_keywords()
        if keywords:
            keyboard = [[InlineKeyboardButton(f"🗑 {kw}", callback_data=f'del_kw_{kid}')] for kid, kw in keywords]
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')])
            await query.edit_message_text("O'chirish uchun kalit so'zni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("❌ Hozircha kalit so'zlar yo'q", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]))
    
    elif data.startswith('del_kw_'):
        db.delete_keyword(int(data.split('_')[2]))
        await query.edit_message_text("✅ Kalit so'z o'chirildi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]))
    
    elif data == 'add_search_group':
        context.user_data['state'] = WAITING_SEARCH_GROUP
        await query.edit_message_text("📝 Izlovchi guruh ID yoki havolasini yuboring:\n\nBekor qilish uchun /cancel yuboring")
    
    elif data == 'view_search_groups':
        groups = db.get_search_groups()
        text = "📋 Izlovchi guruhlar ro'yxati:\n\n" if groups else "❌ Hozircha izlovchi guruhlar yo'q"
        if groups:
            for idx, (gid, group_id, group_name) in enumerate(groups, 1):
                text += f"{idx}. {group_name}\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]))
    
    elif data == 'delete_search_group':
        groups = db.get_search_groups()
        if groups:
            keyboard = [[InlineKeyboardButton(f"🗑 {gname}", callback_data=f'del_sg_{gid}')] for gid, _, gname in groups]
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')])
            await query.edit_message_text("O'chirish uchun guruhni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("❌ Hozircha izlovchi guruhlar yo'q", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]))
    
    elif data.startswith('del_sg_'):
        db.delete_search_group(int(data.split('_')[2]))
        await query.edit_message_text("✅ Izlovchi guruh o'chirildi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]))
    
    elif data == 'add_personal_group':
        context.user_data['state'] = WAITING_PERSONAL_GROUP
        await query.edit_message_text("📝 Shaxsiy guruh ID yoki havolasini yuboring:\n\nBekor qilish uchun /cancel yuboring")
    
    elif data == 'view_personal_group':
        group = db.get_personal_group()
        text = f"📋 Shaxsiy guruh:\n\n{group[1]}" if group else "❌ Shaxsiy guruh o'rnatilmagan"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]))
    
    elif data == 'delete_personal_group':
        db.delete_personal_group()
        await query.edit_message_text("✅ Shaxsiy guruh o'chirildi!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]))
    
    elif data == 'back_to_menu':
        await query.edit_message_text("👋 Assalomu alaykum, Admin!\n\nQuyidagi menyudan kerakli bo'limni tanlang:", reply_markup=get_main_menu())

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    state = context.user_data.get('state')
    text = update.message.text
    
    if state == WAITING_KEYWORD:
        msg = f"✅ Kalit so'z qo'shildi: {text}" if db.add_keyword(text) else "❌ Bu kalit so'z allaqachon mavjud!"
        await update.message.reply_text(msg, reply_markup=get_main_menu())
        context.user_data['state'] = None
    
    elif state == WAITING_SEARCH_GROUP:
        try:
            group_identifier = text if text.startswith(('https://t.me/', '@')) else int(text)
            try:
                chat = await context.bot.get_chat(group_identifier)
                group_id, group_name = chat.id, chat.title or chat.username or str(chat.id)
                msg = f"✅ Izlovchi guruh qo'shildi: {group_name}" if db.add_search_group(group_id, group_name) else "❌ Bu guruh allaqachon mavjud!"
                await update.message.reply_text(msg, reply_markup=get_main_menu())
            except Exception as e:
                await update.message.reply_text(f"❌ Guruhni topib bo'lmadi. Botni guruhga qo'shganingizga ishonch hosil qiling.\nXatolik: {str(e)}", reply_markup=get_main_menu())
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri format! Guruh ID yoki havolasini yuboring.", reply_markup=get_main_menu())
        context.user_data['state'] = None
    
    elif state == WAITING_PERSONAL_GROUP:
        try:
            group_identifier = text if text.startswith(('https://t.me/', '@')) else int(text)
            try:
                chat = await context.bot.get_chat(group_identifier)
                group_id, group_name = chat.id, chat.title or chat.username or str(chat.id)
                msg = f"✅ Shaxsiy guruh o'rnatildi: {group_name}" if db.add_personal_group(group_id, group_name) else "❌ Xatolik yuz berdi!"
                await update.message.reply_text(msg, reply_markup=get_main_menu())
            except Exception as e:
                await update.message.reply_text(f"❌ Guruhni topib bo'lmadi. Botni guruhga qo'shganingizga ishonch hosil qiling.\nXatolik: {str(e)}", reply_markup=get_main_menu())
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri format! Guruh ID yoki havolasini yuboring.", reply_markup=get_main_menu())
        context.user_data['state'] = None

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    context.user_data['state'] = None
    await update.message.reply_text("❌ Bekor qilindi", reply_markup=get_main_menu())

# ============================================
# USERBOT QISMI
# ============================================
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def check_keywords(text):
    if not text:
        return []
    
    keywords = db.get_keywords()
    found_keywords = []
    text_lower = text.lower()
    
    for kid, keyword in keywords:
        if keyword.lower() in text_lower:
            found_keywords.append(keyword)
    
    return found_keywords

async def send_to_personal_group(message_text, group_name, user_id, user_name, user_username, message_link):
    personal_group = db.get_personal_group()
    
    if not personal_group:
        logger.warning("Shaxsiy guruh o'rnatilmagan!")
        return
    
    group_id = int(personal_group[0])
    
    text = f"🔍 <b>Kalit so'z topildi!</b>\n\n"
    text += f"👥 <b>Guruh:</b> {group_name}\n"
    text += f"👤 <b>Foydalanuvchi:</b> {user_name}"
    
    if user_username:
        text += f" (@{user_username})\n"
    else:
        text += "\n"
    
    text += f"\n📝 <b>Xabar:</b>\n{message_text}\n"
    
    if message_link:
        text += f"\n🔗 <a href='{message_link}'>Xabarga o'tish</a>"
    
    keyboard = {
        'inline_keyboard': [[
            {'text': '👤 Profilga o\'tish', 'url': f'tg://user?id={user_id}'}
        ]]
    }
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': group_id,
        'text': text,
        'parse_mode': 'HTML',
        'reply_markup': keyboard,
        'disable_web_page_preview': True
    }
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            logger.info(f"Xabar yuborildi: {user_name} ({group_name})")
        else:
            logger.error(f"Xabar yuborilmadi: {response.text}")
    except Exception as e:
        logger.error(f"Xatolik: {e}")

@client.on(events.NewMessage())
async def handle_new_message(event):
    try:
        search_groups = db.get_search_groups()
        
        if not search_groups:
            return
        
        chat = await event.get_chat()
        chat_id = str(event.chat_id)
        
        is_monitored = False
        group_name = ""
        
        for gid, group_id, gname in search_groups:
            if group_id == chat_id or group_id == str(chat.id):
                is_monitored = True
                group_name = gname
                break
        
        if not is_monitored:
            return
        
        message_text = event.message.message
        
        if not message_text:
            return
        
        found_keywords = check_keywords(message_text)
        
        if not found_keywords:
            return
        
        sender = await event.get_sender()
        user_id = sender.id
        user_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        if not user_name:
            user_name = "Noma'lum"
        user_username = sender.username
        
        message_link = None
        try:
            if hasattr(chat, 'username') and chat.username:
                message_link = f"https://t.me/{chat.username}/{event.message.id}"
            elif hasattr(event.message, 'id'):
                message_link = f"https://t.me/c/{str(chat.id)[4:]}/{event.message.id}"
        except:
            pass
        
        logger.info(f"Kalit so'z topildi: {found_keywords} - {user_name} ({group_name})")
        await send_to_personal_group(
            message_text,
            group_name,
            user_id,
            user_name,
            user_username,
            message_link
        )
        
    except Exception as e:
        logger.error(f"Xatolik yuz berdi: {e}")

# ============================================
# ASOSIY FUNKSIYA
# ============================================
async def main():
    # Bot application
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("cancel", cancel))
    bot_app.add_handler(CallbackQueryHandler(button_handler))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("Bot va Userbot ishga tushirilmoqda...")
    
    # Userbotni ishga tushirish
    await client.start(phone=PHONE_NUMBER)
    logger.info("Userbot muvaffaqiyatli ishga tushdi!")
    
    search_groups = db.get_search_groups()
    logger.info(f"Izlovchi guruhlar soni: {len(search_groups)}")
    
    for gid, group_id, group_name in search_groups:
        logger.info(f"Kuzatilayotgan guruh: {group_name} ({group_id})")
    
    # Botni parallel ravishda ishga tushirish
    async with bot_app:
        await bot_app.start()
        logger.info("Bot muvaffaqiyatli ishga tushdi!")
        
        # Ikkalasini parallel ishlash
        await asyncio.gather(
            bot_app.updater.start_polling(allowed_updates=Update.ALL_TYPES),
            client.run_until_disconnected()
        )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot va Userbot to'xtatildi")
