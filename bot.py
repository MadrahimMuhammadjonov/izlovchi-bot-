import asyncio
import sqlite3
import logging
import html
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8045123024:AAGdfjgOJAUosbf4SfUpmDQkh2qeGOirblc"
ADMIN_ID = 7619928444
API_ID = 30858730
API_HASH = "25106c9d80e8d8354053c1da9391edb8"
SESSION_STRING = "1ApWapzMBu8a98LDOP5kboivlyYdjMNHKX821z6TX9MxWDmIOdtC1TcIaecFmEu8g2yBXJMfXKFlqzUjZrJY74OewDP3Far-nkfuVElEiop3xeMljhrkr6Ax8n80KeV1WI5dxxZUEo3wKj7umM-5YM3UuzL3SaddZw28Vc7mGLvfxo1T1Neu30uvkPn4NoFC0mty1dS7pNRTyIr_Af6GkcrhF0oCxXjpK_a3YuViqtw43GYk1QA33HgQu7o-AsIC-R5RDNEyTy2rWeNsqX1Y3J9V9pMu-rFDVwkUzNgZYx1YQrfqfYe6afGtBmUw_kkVkDU0aMRHoAXHEwHxsWNIpi6v-PYf1t4E="
PERSONAL_GROUP_ID = -1003267783623

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# --- DB ---
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

# --- ADMIN PANEL KEYBOARD ---
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="➕ Kalit so'z qo'shish", callback_data='add_keyword'),
         InlineKeyboardButton(text="📋 Kalit so'zlar", callback_data='view_keywords')],
        [InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data='add_search_group'),
         InlineKeyboardButton(text="📋 Guruhlar", callback_data='view_search_groups')],
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data='back')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- USERBOT HANDLER ---
@client.on(events.NewMessage)
async def userbot_handler(event):
    try:
        search_groups = [g[0] for g in db_query("SELECT group_id FROM search_groups", fetch=True)]
        if event.chat_id not in search_groups: return

        text = event.message.message
        if not text: return

        keywords = [k[0] for k in db_query("SELECT keyword FROM keywords", fetch=True)]
        found = [kw for kw in keywords if kw.lower() in text.lower()]

        if found:
            sender = await event.get_sender()
            chat = await event.get_chat()
            
            user_id = sender.id
            # Username bo'lsa t.me, bo'lmasa ID orqali link yaratamiz
            profile_url = f"https://t.me/{sender.username}" if sender.username else f"tg://user?id={user_id}"
            
            sender_name = html.escape(f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Foydalanuvchi")
            group_title = html.escape(getattr(chat, 'title', 'Guruh'))
            safe_text = html.escape(text[:900])
            
            report = (
                "🔍 <b>Yangi xabar aniqlandi!</b>\n\n"
                f"<b>📍 Guruh:</b> {group_title}\n"
                f"<b>👤 Kimdan:</b> {sender_name}\n"
                f"<b>🔑 Kalit so'z:</b> {', '.join(found)}\n\n"
                f"<b>📝 Xabar:</b>\n<i>{safe_text}</i>"
            )

            # --- TUGMA LOGIKASI ---
            # Aynan siz aytgan havola tugmachaga joylandi
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👤 Profilga o'tish", url=profile_url)
            ]])

            try:
                await bot.send_message(
                    chat_id=PERSONAL_GROUP_ID,
                    text=report,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception as e:
                # Agar tugma hali ham xato bersa (bot tanimasa), 
                # xabar matniga ID ni bosiladigan qilib qo'shadi
                report += f"\n\n🔗 <a href='{profile_url}'>Profilga havola</a>"
                await bot.send_message(chat_id=PERSONAL_GROUP_ID, text=report, parse_mode="HTML")
                logger.error(f"Tugma xatosi: {e}")

    except Exception as e:
        logger.error(f"Xatolik: {e}")

# --- BOT HANDLERS ---
@dp.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🤖 <b>Boshqaruv paneli:</b>", reply_markup=main_menu_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "back")
async def back(callback: types.CallbackQuery):
    db_query("DELETE FROM user_state WHERE user_id=?", (callback.from_user.id,))
    await callback.message.edit_text("🤖 <b>Boshqaruv paneli:</b>", reply_markup=main_menu_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "add_keyword")
async def add_kw(callback: types.CallbackQuery):
    db_query("REPLACE INTO user_state VALUES (?, ?, ?)", (callback.from_user.id, 'waiting_keyword', ''))
    await callback.message.edit_text("📝 Kalit so'zni kiriting:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back")]]))

@dp.callback_query(F.data == "add_search_group")
async def add_gp(callback: types.CallbackQuery):
    db_query("REPLACE INTO user_state VALUES (?, ?, ?)", (callback.from_user.id, 'waiting_group', ''))
    await callback.message.edit_text("📝 Guruh linkini kiriting:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="back")]]))

@dp.message(F.text)
async def admin_text(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    state = db_query("SELECT state FROM user_state WHERE user_id=?", (message.from_user.id,), fetch=True)
    if not state: return
    
    cmd = state[0][0]
    if cmd == 'waiting_keyword':
        db_query("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (message.text.strip(),))
        await message.answer("✅ Kalit so'z saqlandi", reply_markup=main_menu_keyboard())
    elif cmd == 'waiting_group':
        try:
            entity = await client.get_entity(message.text.strip())
            await client(functions.channels.JoinChannelRequest(channel=entity))
            g_id = entity.id if str(entity.id).startswith("-100") else int(f"-100{entity.id}")
            db_query("INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", (g_id, entity.title))
            await message.answer(f"✅ {entity.title} qo'shildi", reply_markup=main_menu_keyboard())
        except Exception as e:
            await message.answer(f"❌ Xato: {e}")
    db_query("DELETE FROM user_state WHERE user_id=?", (message.from_user.id,))

# --- RUN ---
async def main():
    init_db()
    await client.start()
    await asyncio.gather(dp.start_polling(bot), client.run_until_disconnected())

if __name__ == '__main__':
    asyncio.run(main())
