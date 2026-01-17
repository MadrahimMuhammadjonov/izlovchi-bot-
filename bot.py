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

# Shaxsiy guruh ID (Manfiy bo'lishi va -100 bilan boshlanishi shart)
PERSONAL_GROUP_ID = -1003267783623

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# --- DATABASE ---
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
         InlineKeyboardButton(text="📋 Kalit so'zlar", callback_data='view_keywords')],
        [InlineKeyboardButton(text="🗑 Kalit so'zlarni o'chirish", callback_data='delete_keywords')],
        [InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data='add_search_group'),
         InlineKeyboardButton(text="📋 Guruhlar ro'yxati", callback_data='view_search_groups')],
        [InlineKeyboardButton(text="🗑 Guruhni o'chirish", callback_data='delete_search_group')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')]])

# --- BOT HANDLERLARI ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🤖 <b>Admin paneli:</b>", reply_markup=main_menu_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "back_menu")
async def back_menu(callback: types.CallbackQuery):
    db_query("DELETE FROM user_state WHERE user_id=?", (callback.from_user.id,))
    await callback.message.edit_text("🤖 <b>Admin paneli:</b>", reply_markup=main_menu_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "add_keyword")
async def add_keyword_call(callback: types.CallbackQuery):
    db_query("REPLACE INTO user_state VALUES (?, ?, ?)", (callback.from_user.id, 'waiting_keyword', ''))
    await callback.message.edit_text("📝 <b>Kalit so'z kiriting:</b>", reply_markup=back_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "view_keywords")
async def view_keywords(callback: types.CallbackQuery):
    kws = db_query("SELECT keyword FROM keywords", fetch=True)
    text = "📋 <b>Kalit so'zlar:</b>\n\n" + ("\n".join([f"• {html.escape(k[0])}" for k in kws]) if kws else "Bo'sh")
    await callback.message.edit_text(text, reply_markup=back_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "delete_keywords")
async def delete_keywords_menu(callback: types.CallbackQuery):
    kws = db_query("SELECT keyword FROM keywords", fetch=True)
    if not kws: return await callback.answer("Bo'sh")
    kb = [[InlineKeyboardButton(text=f"❌ {k[0]}", callback_data=f"delkw_{k[0]}")] for k in kws]
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")])
    await callback.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data.startswith("delkw_"))
async def del_keyword(callback: types.CallbackQuery):
    kw = callback.data.split("_", 1)[1]
    db_query("DELETE FROM keywords WHERE keyword=?", (kw,))
    await delete_keywords_menu(callback)

@dp.callback_query(F.data == "add_search_group")
async def add_group_call(callback: types.CallbackQuery):
    db_query("REPLACE INTO user_state VALUES (?, ?, ?)", (callback.from_user.id, 'waiting_group', ''))
    await callback.message.edit_text("📝 <b>Guruh havolasini yuboring:</b>", reply_markup=back_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "view_search_groups")
async def view_groups(callback: types.CallbackQuery):
    gps = db_query("SELECT group_name, group_id FROM search_groups", fetch=True)
    text = "📋 <b>Guruhlar:</b>\n\n" + ("\n".join([f"• {html.escape(g[0])}" for g in gps]) if gps else "Bo'sh")
    await callback.message.edit_text(text, reply_markup=back_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "delete_search_group")
async def delete_group_menu(callback: types.CallbackQuery):
    gps = db_query("SELECT group_name, group_id FROM search_groups", fetch=True)
    if not gps: return await callback.answer("Bo'sh")
    kb = [[InlineKeyboardButton(text=f"🗑 {g[0]}", callback_data=f"delgp_{g[1]}")] for g in gps]
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")])
    await callback.message.edit_text("🗑 <b>O'chirish:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data.startswith("delgp_"))
async def del_group(callback: types.CallbackQuery):
    gid = int(callback.data.split("_")[1])
    db_query("DELETE FROM search_groups WHERE group_id=?", (gid,))
    await delete_group_menu(callback)

@dp.message(F.text)
async def handle_text(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    state_data = db_query("SELECT state FROM user_state WHERE user_id=?", (message.from_user.id,), fetch=True)
    if not state_data: return
    state = state_data[0][0]

    if state == 'waiting_keyword':
        db_query("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (message.text.strip(),))
        await message.answer("✅ Qo'shildi", reply_markup=main_menu_keyboard())
        db_query("DELETE FROM user_state WHERE user_id=?", (message.from_user.id,))
    elif state == 'waiting_group':
        try:
            entity = await client.get_entity(message.text.strip())
            await client(functions.channels.JoinChannelRequest(channel=entity))
            db_query("INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", (entity.id if str(entity.id).startswith("-100") else int(f"-100{entity.id}"), entity.title))
            await message.answer("✅ Guruh qo'shildi", reply_markup=main_menu_keyboard())
            db_query("DELETE FROM user_state WHERE user_id=?", (message.from_user.id,))
        except Exception as e:
            await message.answer(f"❌ Xato: {e}", reply_markup=back_keyboard())

# --- USERBOT VA TUGMA LOGIKASI ---
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
            chat = await event.get_chat()
            sender = await event.get_sender()
            
            sender_name = html.escape(f"{sender.first_name or ''} {sender.last_name or ''}".strip())
            group_title = html.escape(getattr(chat, 'title', 'Noma`lum'))
            safe_text = html.escape(text[:800])
            
            report = (
                "🔍 <b>Yangi xabar!</b>\n\n"
                f"<b>📍 Guruh:</b> {group_title}\n"
                f"<b>👤 Kimdan:</b> {sender_name}\n"
                f"<b>🔑 Kalit so'z:</b> {', '.join(found)}\n\n"
                f"<b>📝 Xabar:</b>\n<i>{safe_text}</i>"
            )

            # --- TUGMA YARATISH ---
            # Agar username bo'lsa, t.me linki, bo'lmasa tg://user?id linki ishlatiladi
            profile_url = f"https://t.me/{sender.username}" if sender.username else f"tg://user?id={sender.id}"
            
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👤 Profilga o'tish", url=profile_url)
            ]])

            await bot.send_message(
                chat_id=PERSONAL_GROUP_ID, 
                text=report, 
                reply_markup=kb, 
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Xatolik: {e}")

async def main():
    init_db()
    await client.start()
    await asyncio.gather(dp.start_polling(bot), client.run_until_disconnected())

if __name__ == '__main__':
    asyncio.run(main())
