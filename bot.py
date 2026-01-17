import asyncio
import sqlite3
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Konfiguratsiya
BOT_TOKEN = "8045123024:AAGdfjgOJAUosbf4SfUpmDQkh2qeGOirblc"
ADMIN_ID = 7619928444
API_ID = 30858730
API_HASH = "25106c9d80e8d8354053c1da9391edb8"
SESSION_STRING = "1ApWapzMBu8a98LDOP5kboivlyYdjMNHKX821z6TX9MxWDmIOdtC1TcIaecFmEu8g2yBXJMfXKFlqzUjZrJY74OewDP3Far-nkfuVElEiop3xeMljhrkr6Ax8n80KeV1WI5dxxZUEo3wKj7umM-5YM3UuzL3SaddZw28Vc7mGLvfxo1T1Neu30uvkPn4NoFC0mty1dS7pNRTyIr_Af6GkcrhF0oCxXjpK_a3YuViqtw43GYk1QA33HgQu7o-AsIC-R5RDNEyTy2rWeNsqX1Y3J9V9pMu-rFDVwkUzNgZYx1YQrfqfYe6afGtBmUw_kkVkDU0aMRHoAXHEwHxsWNIpi6v-PYf1t4E="

# Shaxsiy guruh ID (fixed)
PERSONAL_GROUP_ID = -1003267783623

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Database yaratish
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS keywords
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, keyword TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS search_groups
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER UNIQUE, group_name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_state
                 (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT)''')
    conn.commit()
    conn.close()

# Database funksiyalari
def add_keyword(keyword):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO keywords (keyword) VALUES (?)", (keyword,))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

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
        c.execute("INSERT INTO search_groups (group_id, group_name) VALUES (?, ?)", (group_id, group_name))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

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

# Asosiy menyu (personal group tugmalari olib tashlandi)
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="➕ Kalit so'z qo'shish", callback_data='add_keyword')],
        [InlineKeyboardButton(text="📋 Kalit so'zlarni ko'rish", callback_data='view_keywords')],
        [InlineKeyboardButton(text="🗑 Kalit so'zlarni o'chirish", callback_data='delete_keywords')],
        [InlineKeyboardButton(text="➕ Izlovchi guruh qo'shish", callback_data='add_search_group')],
        [InlineKeyboardButton(text="📋 Izlovchi guruhlarni ko'rish", callback_data='view_search_groups')],
        [InlineKeyboardButton(text="🗑 Izlovchi guruhni o'chirish", callback_data='delete_search_group')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Bot handlerlari
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        await message.answer(
            "🤖 Assalomu alaykum, Admin!\n\nIzlovchi bot boshqaruv paneli:",
            reply_markup=main_menu_keyboard()
        )
    else:
        await message.answer("❌ Kechirasiz, ushbu botdan faqat adminlar foydalana oladi.")

@dp.callback_query(F.data == "add_keyword")
async def add_keyword_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    set_user_state(callback.from_user.id, 'waiting_keyword')
    await callback.message.answer("📝 Yangi kalit so'z kiriting:")
    await callback.answer()

@dp.callback_query(F.data == "view_keywords")
async def view_keywords_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    keywords = get_keywords()
    if keywords:
        text = "📋 Kalit so'zlar ro'yxati:\n\n" + "\n".join([f"• {kw}" for kw in keywords])
    else:
        text = "❌ Hozircha kalit so'zlar yo'q."
    await callback.message.answer(text, reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "delete_keywords")
async def delete_keywords_menu(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    keywords = get_keywords()
    if keywords:
        keyboard = [[InlineKeyboardButton(text=kw, callback_data=f'del_kw_{kw}')] for kw in keywords]
        keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')])
        await callback.message.answer("🗑 O'chirish uchun kalit so'zni tanlang:",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    else:
        await callback.message.answer("❌ O'chiriladigan kalit so'zlar yo'q.", reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("del_kw_"))
async def delete_keyword_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    keyword = callback.data.replace('del_kw_', '')
    delete_keyword(keyword)
    await callback.message.answer(f"✅ '{keyword}' o'chirildi!", reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "add_search_group")
async def add_search_group_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    set_user_state(callback.from_user.id, 'waiting_search_group')
    await callback.message.answer("📝 Izlovchi guruh ID yoki havolasini yuboring:")
    await callback.answer()

@dp.callback_query(F.data == "view_search_groups")
async def view_search_groups_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    groups = get_search_groups()
    if groups:
        text = "📋 Izlovchi guruhlar ro'yxati:\n\n" + "\n".join([f"• {name} (ID: {gid})" for gid, name in groups])
    else:
        text = "❌ Hozircha izlovchi guruhlar yo'q."
    await callback.message.answer(text, reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "delete_search_group")
async def delete_search_group_menu(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    groups = get_search_groups()
    if groups:
        keyboard = [[InlineKeyboardButton(text=name, callback_data=f'del_sg_{gid}')] for gid, name in groups]
        keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')])
        await callback.message.answer("🗑 O'chirish uchun guruhni tanlang:",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    else:
        await callback.message.answer("❌ O'chiriladigan guruhlar yo'q.", reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("del_sg_"))
async def delete_search_group_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    group_id = int(callback.data.replace('del_sg_', ''))
    delete_search_group(group_id)
    await callback.message.answer("✅ Guruh o'chirildi!", reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "back_menu")
async def back_menu_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.answer("🤖 Boshqaruv paneli:", reply_markup=main_menu_keyboard())
    await callback.answer()

@dp.message(F.text)
async def message_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return

    state, data = get_user_state(user_id)

    if state == 'waiting_keyword':
        keyword = message.text.strip()
        if add_keyword(keyword):
            await message.answer(f"✅ Kalit so'z '{keyword}' qo'shildi!", reply_markup=main_menu_keyboard())
        else:
            await message.answer("❌ Bu kalit so'z allaqachon mavjud!", reply_markup=main_menu_keyboard())
        clear_user_state(user_id)

    elif state == 'waiting_search_group':
        text = message.text.strip()
        try:
            if text.startswith('https://t.me/') or text.startswith('@'):
                group_username = text.replace('https://t.me/', '').replace('@', '')
                await message.answer("⏳ Guruh ma'lumotlari olinmoqda...")
                set_user_state(user_id, 'process_search_group', group_username)
            else:
                group_id = int(text)
                await message.answer("⏳ Guruh ma'lumotlari olinmoqda...")
                set_user_state(user_id, 'process_search_group', str(group_id))
        except:
            await message.answer("❌ Noto'g'ri format! Qaytadan urinib ko'ring:", reply_markup=main_menu_keyboard())
            clear_user_state(user_id)

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
                chat = await event.get_chat()
                chat_id = event.chat_id

                search_groups = get_search_groups()
                group_ids = [g[0] for g in search_groups]

                if chat_id not in group_ids:
                    return

                message_text = event.message.message
                if not message_text:
                    return

                keywords = get_keywords()
                found_keywords = [kw for kw in keywords if kw.lower() in message_text.lower()]
                if not found_keywords:
                    return

                sender = await event.get_sender()
                sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                sender_username = f"@{sender.username}" if sender.username else "Username yo'q"
                sender_id = sender.id

                group_name = chat.title if hasattr(chat, 'title') else "Noma'lum guruh"

                notification = (
                    "🔍 Yangi kalit so'z topildi!\n\n"
                    f"📍 Guruh: {group_name}\n"
                    f"👤 Foydalanuvchi: {sender_name} ({sender_username})\n"
                    f"🔑 Kalit so'z(lar): {', '.join(found_keywords)}\n\n"
                    f"💬 Xabar:\n{message_text}"
                )

                keyboard = [[InlineKeyboardButton(text="👤 Profilga o'tish", url=f"tg://user?id={sender_id}")]]

                await bot.send_message(
                    chat_id=PERSONAL_GROUP_ID,
                    text=notification,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
                )
                logger.info(f"✅ Xabar yuborildi: {found_keywords}")
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

            for user_id, state, data in pending:
                try:
                    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
                    await client.start()

                    if data.isdigit() or data.startswith('-'):
                        entity = await client.get_entity(int(data))
                    else:
                        entity = await client.get_entity(data)

                    group_id = entity.id
                    group_name = entity.title if hasattr(entity, 'title') else str(entity.id)

                    if state == 'process_search_group':
                        if add_search_group(group_id, group_name):
                            await bot.send_message(
                                user_id,
                                f"✅ Izlovchi guruh '{group_name}' qo'shildi!",
                                reply_markup=main_menu_keyboard()
                            )
                        else:
                            await bot.send_message(
                                user_id,
                                "❌ Bu guruh allaqachon mavjud!",
                                reply_markup=main_menu_keyboard()
                            )

                    clear_user_state(user_id)
                    await client.disconnect()

                except Exception as e:
                    await bot.send_message(
                        user_id,
                        f"❌ Xatolik: {str(e)}",
                        reply_markup=main_menu_keyboard()
                    )
                    clear_user_state(user_id)
        except Exception as e:
            logger.error(f"Check groups error: {e}")

        await asyncio.sleep(2)

# Asosiy dastur
async def main():
    logger.info("🚀 Bot ishga tushmoqda...")
    init_db()

    asyncio.create_task(check_pending_groups())
    logger.info("✅ Guruh processor ishga tushdi")

    asyncio.create_task(userbot_main())
    logger.info("✅ Userbot ishga tushmoqda...")

    logger.info("✅ Bot tayyor")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("✅ Bot to'xtatildi")
