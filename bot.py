import asyncio
import sqlite3
import logging
import re
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Konfiguratsiya
BOT_TOKEN = "8045123024:AAGdfjgOJAUosbf4SfUpmDQkh2qeGOirblc"
ADMIN_ID = 8228479175
API_ID = 36799342
API_HASH = "fcdf748b56fb519c6900d02e25ae2d62"
SESSION_STRING = "1ApWapzMBu7wMtDnHS2BHSlKKIcR0O326szif2GpPek9MHzgLxHaafUzSGh864f--z_ImIsN8GkhzJY-T_TLRSyc2MdUBAX89sRsqUWumntyGQ1u0d0h3c0t0k_VSaqq3Mjjt401spd3TcLUgz8qb23Eh7PtVSvs1viHduuKXyExsUAkstyewIDamcQf2mlGQuoQiL5WBc63h5q6Roj-kff-xxr1TJB-3kag0XdKVKzS50xFWyXKBoixQ_XynUB1yk4qkaUbKv9ciCyZGy6yTRm3IgGk8Rb2BECId-p6fRR-jPsVemBhDZIOY2gwNNTrwty8I988h0lACcrT5Hyh9uX56KRlr8tc="

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ID formatlash funksiyasi
def normalize_id(tg_id):
    """Telethon ID-ni Bot API formatiga o'tkazish"""
    s_id = str(tg_id)
    if s_id.startswith('-100'):
        return int(s_id)
    elif s_id.startswith('-'):
        # Agar shunchaki - bo'lsa, bu oddiy guruh, lekin ko'pincha superguruhlar ishlatiladi
        # Superguruhlar uchun -100 prefiksi kerak
        return int(f"-100{s_id[1:]}")
    else:
        # Musbat ID bo'lsa (superguruh ID-si Telethon'da musbat bo'lishi mumkin)
        return int(f"-100{s_id}")

# Database yaratish
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS keywords
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, keyword TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS search_groups
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER UNIQUE, group_name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS personal_group
                 (id INTEGER PRIMARY KEY, group_id INTEGER, group_name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_state
                 (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT)''')
    conn.commit()
    conn.close()

# Database funksiyalari
def add_keyword(keyword):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO keywords (keyword) VALUES (?)", (keyword.lower(),))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def get_keywords():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT keyword FROM keywords")
    keywords = [row[0] for row in c.fetchall()]
    conn.close()
    return keywords

def delete_keyword(keyword):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("DELETE FROM keywords WHERE keyword=?", (keyword,))
    conn.commit()
    conn.close()

def add_search_group(group_id, group_name):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    try:
        norm_id = normalize_id(group_id)
        c.execute("INSERT INTO search_groups (group_id, group_name) VALUES (?, ?)", (norm_id, group_name))
        conn.commit()
        logger.info(f"Guruh qo'shildi: {group_name} (ID: {norm_id})")
        return True
    except Exception as e:
        logger.error(f"Guruh qo'shishda xato: {e}")
        return False
    finally:
        conn.close()

def get_search_groups():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT group_id, group_name FROM search_groups")
    groups = c.fetchall()
    conn.close()
    return groups

def delete_search_group(group_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("DELETE FROM search_groups WHERE group_id=?", (group_id,))
    conn.commit()
    conn.close()

def set_personal_group(group_id, group_name):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    norm_id = normalize_id(group_id)
    c.execute("DELETE FROM personal_group")
    c.execute("INSERT INTO personal_group (id, group_id, group_name) VALUES (1, ?, ?)", (norm_id, group_name))
    conn.commit()
    conn.close()
    logger.info(f"Shaxsiy guruh o'rnatildi: {group_name} (ID: {norm_id})")

def get_personal_group():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT group_id, group_name FROM personal_group WHERE id=1")
    result = c.fetchone()
    conn.close()
    return result

def delete_personal_group():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("DELETE FROM personal_group")
    conn.commit()
    conn.close()

def set_user_state(user_id, state, data=""):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("REPLACE INTO user_state (user_id, state, data) VALUES (?, ?, ?)", (user_id, state, data))
    conn.commit()
    conn.close()

def get_user_state(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT state, data FROM user_state WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result if result else (None, None)

def clear_user_state(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("DELETE FROM user_state WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# Asosiy menyu
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="➕ Kalit so'z qo'shish", callback_data='add_keyword')],
        [InlineKeyboardButton(text="📋 Kalit so'zlarni ko'rish", callback_data='view_keywords')],
        [InlineKeyboardButton(text="🗑 Kalit so'zlarni o'chirish", callback_data='delete_keywords')],
        [InlineKeyboardButton(text="➕ Izlovchi guruh qo'shish", callback_data='add_search_group')],
        [InlineKeyboardButton(text="📋 Izlovchi guruhlarni ko'rish", callback_data='view_search_groups')],
        [InlineKeyboardButton(text="🗑 Izlovchi guruhni o'chirish", callback_data='delete_search_group')],
        [InlineKeyboardButton(text="➕ Shaxsiy guruh qo'shish", callback_data='add_personal_group')],
        [InlineKeyboardButton(text="📋 Shaxsiy guruhni ko'rish", callback_data='view_personal_group')],
        [InlineKeyboardButton(text="🗑 Shaxsiy guruhni o'chirish", callback_data='delete_personal_group')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Bot handlerlari
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "🤖 Assalomu alaykum, Admin!\n\nIzlovchi bot boshqaruv paneli:",
            reply_markup=main_menu_keyboard()
        )
    else:
        await message.answer("❌ Kechirasiz, ushbu botdan faqat adminlar foydalana oladi.")

@dp.callback_query(F.data == "add_keyword")
async def add_keyword_handler(callback: types.CallbackQuery):
    set_user_state(callback.from_user.id, 'waiting_keyword')
    await callback.message.edit_text("📝 Yangi kalit so'z kiriting:", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')]]))
    await callback.answer()

@dp.callback_query(F.data == "view_keywords")
async def view_keywords_handler(callback: types.CallbackQuery):
    keywords = get_keywords()
    text = "📋 Kalit so'zlar ro'yxati:\n\n" + "\n".join([f"• {kw}" for kw in keywords]) if keywords else "❌ Hozircha kalit so'zlar yo'q."
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "delete_keywords")
async def delete_keywords_menu(callback: types.CallbackQuery):
    keywords = get_keywords()
    if keywords:
        keyboard = [[InlineKeyboardButton(text=f"❌ {kw}", callback_data=f'del_kw_{kw}')] for kw in keywords]
        keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')])
        await callback.message.edit_text("🗑 O'chirish uchun kalit so'zni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    else:
        await callback.message.edit_text("❌ O'chiriladigan kalit so'zlar yo'q.", reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("del_kw_"))
async def delete_keyword_handler(callback: types.CallbackQuery):
    keyword = callback.data.replace('del_kw_', '')
    delete_keyword(keyword)
    await callback.answer(f"✅ '{keyword}' o'chirildi!")
    await delete_keywords_menu(callback)

@dp.callback_query(F.data == "add_search_group")
async def add_search_group_handler(callback: types.CallbackQuery):
    set_user_state(callback.from_user.id, 'waiting_search_group')
    await callback.message.edit_text("📝 Izlovchi guruh ID yoki havolasini yuboring:", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')]]))
    await callback.answer()

@dp.callback_query(F.data == "view_search_groups")
async def view_search_groups_handler(callback: types.CallbackQuery):
    groups = get_search_groups()
    text = "📋 Izlovchi guruhlar ro'yxati:\n\n" + "\n".join([f"• {name} (ID: {gid})" for gid, name in groups]) if groups else "❌ Hozircha izlovchi guruhlar yo'q."
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "delete_search_group")
async def delete_search_group_menu(callback: types.CallbackQuery):
    groups = get_search_groups()
    if groups:
        keyboard = [[InlineKeyboardButton(text=f"❌ {name}", callback_data=f'del_sg_{gid}')] for gid, name in groups]
        keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')])
        await callback.message.edit_text("🗑 O'chirish uchun guruhni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    else:
        await callback.message.edit_text("❌ O'chiriladigan guruhlar yo'q.", reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("del_sg_"))
async def delete_search_group_handler(callback: types.CallbackQuery):
    group_id = int(callback.data.replace('del_sg_', ''))
    delete_search_group(group_id)
    await callback.answer("✅ Guruh o'chirildi!")
    await delete_search_group_menu(callback)

@dp.callback_query(F.data == "add_personal_group")
async def add_personal_group_handler(callback: types.CallbackQuery):
    set_user_state(callback.from_user.id, 'waiting_personal_group')
    await callback.message.edit_text("📝 Shaxsiy guruh ID yoki havolasini yuboring:", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')]]))
    await callback.answer()

@dp.callback_query(F.data == "view_personal_group")
async def view_personal_group_handler(callback: types.CallbackQuery):
    group = get_personal_group()
    text = f"📋 Shaxsiy guruh:\n\n• {group[1]} (ID: {group[0]})" if group else "❌ Shaxsiy guruh o'rnatilmagan."
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "delete_personal_group")
async def delete_personal_group_handler(callback: types.CallbackQuery):
    delete_personal_group()
    await callback.answer("✅ Shaxsiy guruh o'chirildi!")
    await callback.message.edit_text("✅ Shaxsiy guruh o'chirildi!", reply_markup=main_menu_keyboard())

@dp.callback_query(F.data == "back_menu")
async def back_menu_handler(callback: types.CallbackQuery):
    clear_user_state(callback.from_user.id)
    await callback.message.edit_text("🤖 Boshqaruv paneli:", reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.message(F.text)
async def message_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID: return
    
    state, data = get_user_state(user_id)
    if not state: return

    if state == 'waiting_keyword':
        keyword = message.text.strip()
        if add_keyword(keyword):
            await message.answer(f"✅ Kalit so'z '{keyword}' qo'shildi!", reply_markup=main_menu_keyboard())
        else:
            await message.answer("❌ Bu kalit so'z allaqachon mavjud!", reply_markup=main_menu_keyboard())
        clear_user_state(user_id)
    
    elif state in ['waiting_search_group', 'waiting_personal_group']:
        text = message.text.strip()
        target_state = 'process_search_group' if state == 'waiting_search_group' else 'process_personal_group'
        set_user_state(user_id, target_state, text)
        await message.answer(f"⏳ Guruh ma'lumotlari tekshirilmoqda...")

# Userbot funksiyalari
async def userbot_main():
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.start()
        me = await client.get_me()
        logger.info(f"✅ Userbot @{me.username} sifatida ulandi")
        
        @client.on(events.NewMessage())
        async def handler(event):
            try:
                chat_id = event.chat_id
                # Telethon ID-ni normalize qilish
                norm_chat_id = normalize_id(chat_id)
                
                search_groups = get_search_groups()
                # Hammasini normalize qilingan holda tekshiramiz
                group_ids = [g[0] for g in search_groups]
                
                if norm_chat_id not in group_ids:
                    return
                
                message_text = event.message.message
                if not message_text: return
                
                keywords = get_keywords()
                found_keywords = [kw for kw in keywords if kw.lower() in message_text.lower()]
                if not found_keywords: return
                
                logger.info(f"🎯 Kalit so'z topildi: {found_keywords} (Guruh: {norm_chat_id})")
                
                personal_group = get_personal_group()
                if not personal_group:
                    logger.warning("⚠️ Shaxsiy guruh o'rnatilmagan!")
                    return
                
                sender = await event.get_sender()
                sender_name = f"{getattr(sender, 'first_name', '')} {getattr(sender, 'last_name', '')}".strip()
                sender_username = f"@{sender.username}" if hasattr(sender, 'username') and sender.username else "Username yo'q"
                sender_id = sender.id if sender else 0
                
                chat = await event.get_chat()
                group_name = getattr(chat, 'title', "Noma'lum guruh")
                
                notification = f"🔍 Yangi kalit so'z topildi!\n\n"
                notification += f"📍 Guruh: {group_name}\n"
                notification += f"👤 Foydalanuvchi: {sender_name} ({sender_username})\n"
                notification += f"🔑 Kalit so'z(lar): {', '.join(found_keywords)}\n\n"
                notification += f"💬 Xabar:\n{message_text}"
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👤 Profilga o'tish", url=f"tg://user?id={sender_id}")]])
                
                try:
                    await bot.send_message(chat_id=personal_group[0], text=notification, reply_markup=keyboard)
                    logger.info(f"✅ Xabar shaxsiy guruhga ({personal_group[0]}) yuborildi")
                except Exception as e:
                    logger.error(f"❌ Shaxsiy guruhga yuborishda xato: {e}")
                    await bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Shaxsiy guruhga yuborib bo'lmadi (ID: {personal_group[0]}).\n\nXatolik: {e}\n\n{notification}")

            except Exception as e:
                logger.error(f"Userbot handler xatosi: {e}")
        
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Userbot xatosi: {e}")

async def check_pending_groups():
    while True:
        try:
            conn = sqlite3.connect('bot_data.db')
            c = conn.cursor()
            c.execute("SELECT user_id, state, data FROM user_state WHERE state LIKE 'process_%'")
            pending = c.fetchall()
            conn.close()
            
            if pending:
                client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
                await client.start()
                
                for user_id, state, data in pending:
                    try:
                        # ID yoki username orqali entity olish
                        if data.replace('-', '').isdigit():
                            entity = await client.get_entity(int(data))
                        else:
                            # @ belgisini olib tashlash
                            clean_data = data.replace('@', '').replace('https://t.me/', '')
                            entity = await client.get_entity(clean_data)
                        
                        group_id = entity.id
                        group_name = getattr(entity, 'title', str(group_id))
                        
                        if state == 'process_search_group':
                            if add_search_group(group_id, group_name):
                                await bot.send_message(user_id, f"✅ Izlovchi guruh '{group_name}' qo'shildi!", reply_markup=main_menu_keyboard())
                            else:
                                await bot.send_message(user_id, "❌ Bu guruh allaqachon mavjud!", reply_markup=main_menu_keyboard())
                        
                        elif state == 'process_personal_group':
                            set_personal_group(group_id, group_name)
                            await bot.send_message(user_id, f"✅ Shaxsiy guruh '{group_name}' o'rnatildi!", reply_markup=main_menu_keyboard())
                        
                        clear_user_state(user_id)
                    except Exception as e:
                        logger.error(f"Guruhni topishda xato: {e}")
                        await bot.send_message(user_id, f"❌ Guruhni topib bo'lmadi: {str(e)}", reply_markup=main_menu_keyboard())
                        clear_user_state(user_id)
                
                await client.disconnect()
        except Exception as e:
            logger.error(f"Check groups error: {e}")
        
        await asyncio.sleep(3)

async def main():
    init_db()
    asyncio.create_task(check_pending_groups())
    asyncio.create_task(userbot_main())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
