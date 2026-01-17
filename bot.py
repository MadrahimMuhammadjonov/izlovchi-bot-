import asyncio
import sqlite3
import logging
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8045123024:AAGdfjgOJAUosbf4SfUpmDQkh2qeGOirblc"
ADMIN_ID = 7619928444
API_ID = 30858730
API_HASH = "25106c9d80e8d8354053c1da9391edb8"
SESSION_STRING = "1ApWapzMBu8a98LDOP5kboivlyYdjMNHKX821z6TX9MxWDmIOdtC1TcIaecFmEu8g2yBXJMfXKFlqzUjZrJY74OewDP3Far-nkfuVElEiop3xeMljhrkr6Ax8n80KeV1WI5dxxZUEo3wKj7umM-5YM3UuzL3SaddZw28Vc7mGLvfxo1T1Neu30uvkPn4NoFC0mty1dS7pNRTyIr_Af6GkcrhF0oCxXjpK_a3YuViqtw43GYk1QA33HgQu7o-AsIC-R5RDNEyTy2rWeNsqX1Y3J9V9pMu-rFDVwkUzNgZYx1YQrfqfYe6afGtBmUw_kkVkDU0aMRHoAXHEwHxsWNIpi6v-PYf1t4E="

# Shaxsiy guruh ID (ID manfiy bo'lishi va -100 bilan boshlanishi kerak)
PERSONAL_GROUP_ID = -1003267783623

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# --- DATABASE QISMI ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE)')
    c.execute('CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY, group_id INTEGER UNIQUE, group_name TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT)')
    conn.commit()
    conn.close()

def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute(query, params)
    res = c.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

# --- KLAVIATURALAR ---
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="➕ Kalit so'z qo'shish", callback_data='add_keyword'),
         InlineKeyboardButton(text="🗑 O'chirish", callback_data='delete_keywords')],
        [InlineKeyboardButton(text="📋 Kalit so'zlar", callback_data='view_keywords')],
        [InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data='add_search_group'),
         InlineKeyboardButton(text="🗑 Guruhni o'chirish", callback_data='delete_search_group')],
        [InlineKeyboardButton(text="📋 Guruhlar ro'yxati", callback_data='view_search_groups')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')]])

# --- BOT HANDLERLARI ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🤖 Boshqaruv paneli:", reply_markup=main_menu_keyboard())

@dp.callback_query(F.data == "back_menu")
async def back_menu(callback: types.CallbackQuery):
    db_query("DELETE FROM user_state WHERE user_id=?", (callback.from_user.id,))
    await callback.message.edit_text("🤖 Boshqaruv paneli:", reply_markup=main_menu_keyboard())

@dp.callback_query(F.data == "add_keyword")
async def add_keyword_call(callback: types.CallbackQuery):
    db_query("REPLACE INTO user_state VALUES (?, ?, ?)", (callback.from_user.id, 'waiting_keyword', ''))
    await callback.message.edit_text("📝 Yangi kalit so'z kiriting:", reply_markup=back_keyboard())

@dp.callback_query(F.data == "view_keywords")
async def view_keywords(callback: types.CallbackQuery):
    kws = db_query("SELECT keyword FROM keywords", fetch=True)
    text = "📋 Kalit so'zlar:\n\n" + ("\n".join([f"• {k[0]}" for k in kws]) if kws else "Bo'sh")
    await callback.message.edit_text(text, reply_markup=back_keyboard())

@dp.callback_query(F.data == "delete_keywords")
async def delete_keywords_menu(callback: types.CallbackQuery):
    kws = db_query("SELECT keyword FROM keywords", fetch=True)
    if not kws:
        return await callback.answer("Kalit so'zlar yo'q")
    
    kb = [[InlineKeyboardButton(text=f"❌ {k[0]}", callback_data=f"delkw_{k[0]}")] for k in kws]
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")])
    await callback.message.edit_text("O'chirish uchun tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("delkw_"))
async def del_keyword(callback: types.CallbackQuery):
    kw = callback.data.split("_")[1]
    db_query("DELETE FROM keywords WHERE keyword=?", (kw,))
    await callback.answer(f"'{kw}' o'chirildi")
    await delete_keywords_menu(callback)

@dp.callback_query(F.data == "add_search_group")
async def add_group_call(callback: types.CallbackQuery):
    db_query("REPLACE INTO user_state VALUES (?, ?, ?)", (callback.from_user.id, 'waiting_group', ''))
    await callback.message.edit_text("📝 Guruh havolasini yoki ID sini yuboring:\n(Masalan: @guruh_link yoki -100...)", reply_markup=back_keyboard())

@dp.callback_query(F.data == "view_search_groups")
async def view_groups(callback: types.CallbackQuery):
    gps = db_query("SELECT group_name, group_id FROM search_groups", fetch=True)
    text = "📋 Izlovchi guruhlar:\n\n" + ("\n".join([f"• {g[0]} (`{g[1]}`)" for g in gps]) if gps else "Bo'sh")
    await callback.message.edit_text(text, reply_markup=back_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "delete_search_group")
async def delete_group_menu(callback: types.CallbackQuery):
    gps = db_query("SELECT group_name, group_id FROM search_groups", fetch=True)
    if not gps:
        return await callback.answer("Guruhlar yo'q")
    
    kb = [[InlineKeyboardButton(text=f"🗑 {g[0]}", callback_data=f"delgp_{g[1]}")] for g in gps]
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")])
    await callback.message.edit_text("O'chirish uchun tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("delgp_"))
async def del_group(callback: types.CallbackQuery):
    gid = callback.data.split("_")[1]
    db_query("DELETE FROM search_groups WHERE group_id=?", (gid,))
    await callback.answer("Guruh o'chirildi")
    await delete_group_menu(callback)

@dp.message(F.text)
async def handle_text(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    state_data = db_query("SELECT state FROM user_state WHERE user_id=?", (message.from_user.id,), fetch=True)
    if not state_data: return
    state = state_data[0][0]

    if state == 'waiting_keyword':
        db_query("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (message.text.strip(),))
        await message.answer(f"✅ '{message.text}' qo'shildi", reply_markup=main_menu_keyboard())
        db_query("DELETE FROM user_state WHERE user_id=?", (message.from_user.id,))

    elif state == 'waiting_group':
        input_data = message.text.strip()
        msg = await message.answer("⏳ Userbot guruhga qo'shilmoqda...")
        try:
            # Userbot orqali guruhga qo'shilish
            entity = await client.get_entity(input_data)
            await client(functions.channels.JoinChannelRequest(channel=entity))
            
            group_id = entity.id
            if not str(group_id).startswith("-100"):
                group_id = int(f"-100{group_id}")
            
            title = getattr(entity, 'title', 'Guruh')
            db_query("INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", (group_id, title))
            
            await msg.edit_text(f"✅ '{title}' muvaffaqiyatli qo'shildi va Userbot a'zo bo'ldi.", reply_markup=main_menu_keyboard())
            db_query("DELETE FROM user_state WHERE user_id=?", (message.from_user.id,))
        except Exception as e:
            await msg.edit_text(f"❌ Xatolik: {e}", reply_markup=back_keyboard())

# --- USERBOT QISMI ---
@client.on(events.NewMessage)
async def userbot_handler(event):
    try:
        # Guruh IDlarini bazadan olish
        search_groups = [g[0] for g in db_query("SELECT group_id FROM search_groups", fetch=True)]
        if event.chat_id not in search_groups:
            return

        text = event.message.message
        if not text: return

        # Kalit so'zlarni tekshirish
        keywords = [k[0] for k in db_query("SELECT keyword FROM keywords", fetch=True)]
        found = [kw for kw in keywords if kw.lower() in text.lower()]

        if found:
            chat = await event.get_chat()
            sender = await event.get_sender()
            
            sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
            username = f"@{sender.username}" if sender.username else "Username yo'q"
            
            report = (
                "🔍 **Yangi natija!**\n\n"
                f"📍 Guruh: {getattr(chat, 'title', 'Noma`lum')}\n"
                f"👤 Kimdan: {sender_name} ({username})\n"
                f"🔑 So'z: {', '.join(found)}\n"
                f"📝 Xabar: {text[:500]}..."
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👤 Profilga o'tish", url=f"tg://user?id={sender.id}")
            ]])

            await bot.send_message(PERSONAL_GROUP_ID, report, reply_markup=kb, parse_mode="Markdown")
            logger.info(f"Topildi: {found}")

    except Exception as e:
        logger.error(f"Userbot xatosi: {e}")

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    init_db()
    logger.info("Botlar ishga tushmoqda...")
    await client.start()
    
    # Userbot va Aiogramni birga ishlatish
    await asyncio.gather(
        dp.start_polling(bot),
        client.run_until_disconnected()
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi")
