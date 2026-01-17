import asyncio
import sqlite3
import logging
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
# O'zingizning ma'lumotlaringizni kiriting
BOT_TOKEN = "8045123024:AAGdfjgOJAUosbf4SfUpmDQkh2qeGOirblc"
ADMIN_ID = 8228479175
API_ID = 36799342
API_HASH = "fcdf748b56fb519c6900d02e25ae2d62"
# Yangi olingan Session Stringni bu yerga qo'ying:
SESSION_STRING = "1ApWapzMBu8a98LDOP5kboivlyYdjMNHKX821z6TX9MxWDmIOdtC1TcIaecFmEu8g2yBXJMfXKFlqzUjZrJY74OewDP3Far-nkfuVElEiop3xeMljhrkr6Ax8n80KeV1WI5dxxZUEo3wKj7umM-5YM3UuzL3SaddZw28Vc7mGLvfxo1T1Neu30uvkPn4NoFC0mty1dS7pNRTyIr_Af6GkcrhF0oCxXjpK_a3YuViqtw43GYk1QA33HgQu7o-AsIC-R5RDNEyTy2rWeNsqX1Y3J9V9pMu-rFDVwkUzNgZYx1YQrfqfYe6afGtBmUw_kkVkDU0aMRHoAXHEwHxsWNIpi6v-PYf1t4E=" 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def normalize_id(tg_id):
    s_id = str(tg_id)
    if s_id.startswith('-100'): return int(s_id)
    elif s_id.startswith('-'): return int(f"-100{s_id[1:]}")
    else: return int(f"-100{s_id}")

def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY AUTOINCREMENT, keyword TEXT UNIQUE)')
    c.execute('CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER UNIQUE, group_name TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS personal_group (id INTEGER PRIMARY KEY, group_id INTEGER, group_name TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT)')
    conn.commit()
    conn.close()

# DB Helper functions
def add_keyword(keyword):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    try: c.execute("INSERT INTO keywords (keyword) VALUES (?)", (keyword.lower(),)); conn.commit(); return True
    except: return False
    finally: conn.close()

def get_keywords():
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("SELECT keyword FROM keywords"); kws = [row[0] for row in c.fetchall()]; conn.close(); return kws

def delete_keyword(keyword):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("DELETE FROM keywords WHERE keyword=?", (keyword,)); conn.commit(); conn.close()

def add_search_group(group_id, group_name):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    try:
        norm_id = normalize_id(group_id)
        c.execute("INSERT INTO search_groups (group_id, group_name) VALUES (?, ?)", (norm_id, group_name))
        conn.commit(); return True
    except: return False
    finally: conn.close()

def get_search_groups():
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("SELECT group_id, group_name FROM search_groups"); gs = c.fetchall(); conn.close(); return gs

def delete_search_group(group_id):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("DELETE FROM search_groups WHERE group_id=?", (group_id,)); conn.commit(); conn.close()

def set_personal_group(group_id, group_name):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    norm_id = normalize_id(group_id)
    c.execute("DELETE FROM personal_group")
    c.execute("INSERT INTO personal_group (id, group_id, group_name) VALUES (1, ?, ?)", (norm_id, group_name))
    conn.commit(); conn.close()

def get_personal_group():
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("SELECT group_id, group_name FROM personal_group WHERE id=1"); res = c.fetchone(); conn.close(); return res

def set_user_state(user_id, state, data=""):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("REPLACE INTO user_state (user_id, state, data) VALUES (?, ?, ?)", (user_id, state, data))
    conn.commit(); conn.close()

def get_user_state(user_id):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("SELECT state, data FROM user_state WHERE user_id=?", (user_id,)); res = c.fetchone(); conn.close(); return res if res else (None, None)

def clear_user_state(user_id):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("DELETE FROM user_state WHERE user_id=?", (user_id,)); conn.commit(); conn.close()

# Keyboards
def main_menu():
    kb = [
        [InlineKeyboardButton(text="➕ Kalit so'z", callback_data='add_keyword'), InlineKeyboardButton(text="📋 Ro'yxat", callback_data='view_keywords')],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data='delete_keywords')],
        [InlineKeyboardButton(text="➕ Izlovchi guruh", callback_data='add_search_group'), InlineKeyboardButton(text="📋 Guruhlar", callback_data='view_search_groups')],
        [InlineKeyboardButton(text="🗑 Guruhni o'chirish", callback_data='delete_search_group')],
        [InlineKeyboardButton(text="➕ Shaxsiy guruh", callback_data='add_personal_group'), InlineKeyboardButton(text="📋 Ko'rish", callback_data='view_personal_group')],
        [InlineKeyboardButton(text="🗑 Shaxsiy guruhni o'chirish", callback_data='delete_personal_group')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# Handlers
@dp.message(Command("start"))
async def start(m: types.Message):
    if m.from_user.id == ADMIN_ID:
        await m.answer("🤖 Boshqaruv paneli:", reply_markup=main_menu())

@dp.callback_query(F.data == "back_menu")
async def back(c: types.CallbackQuery):
    clear_user_state(c.from_user.id)
    await c.message.edit_text("🤖 Boshqaruv paneli:", reply_markup=main_menu())

@dp.callback_query(F.data == "add_keyword")
async def add_kw_btn(c: types.CallbackQuery):
    set_user_state(c.from_user.id, 'waiting_keyword')
    await c.message.edit_text("📝 Kalit so'z yuboring:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')]]))

@dp.callback_query(F.data == "view_keywords")
async def view_kw(c: types.CallbackQuery):
    kws = get_keywords()
    txt = "📋 Kalit so'zlar:\n\n" + "\n".join([f"• {k}" for k in kws]) if kws else "Bo'sh"
    await c.message.edit_text(txt, reply_markup=main_menu())

@dp.callback_query(F.data == "add_search_group")
async def add_sg_btn(c: types.CallbackQuery):
    set_user_state(c.from_user.id, 'waiting_search_group')
    await c.message.edit_text("📝 Guruh ID yoki linkini yuboring:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')]]))

@dp.callback_query(F.data == "add_personal_group")
async def add_pg_btn(c: types.CallbackQuery):
    set_user_state(c.from_user.id, 'waiting_personal_group')
    await c.message.edit_text("📝 Shaxsiy guruh ID yoki linkini yuboring:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_menu')]]))

@dp.message(F.text)
async def msg_handler(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    st, dt = get_user_state(m.from_user.id)
    if st == 'waiting_keyword':
        if add_keyword(m.text.strip()): await m.answer(f"✅ '{m.text}' qo'shildi", reply_markup=main_menu())
        else: await m.answer("❌ Xato yoki mavjud", reply_markup=main_menu())
        clear_user_state(m.from_user.id)
    elif st in ['waiting_search_group', 'waiting_personal_group']:
        target = 'process_search_group' if st == 'waiting_search_group' else 'process_personal_group'
        set_user_state(m.from_user.id, target, m.text.strip())
        await m.answer("⏳ Tekshirilmoqda...")

# Userbot
async def userbot_task():
    if not SESSION_STRING:
        logger.error("❌ SESSION_STRING bo'sh! Iltimos, sessiya oling.")
        await bot.send_message(ADMIN_ID, "❌ Userbot ishga tushmadi: SESSION_STRING kiritilmagan!")
        return

    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.start()
        me = await client.get_me()
        logger.info(f"✅ Userbot @{me.username} sifatida ulandi")
        
        @client.on(events.NewMessage())
        async def handler(event):
            try:
                norm_chat_id = normalize_id(event.chat_id)
                s_groups = get_search_groups()
                if norm_chat_id not in [g[0] for g in s_groups]: return
                
                msg = event.message.message
                if not msg: return
                
                kws = get_keywords()
                found = [k for k in kws if k.lower() in msg.lower()]
                if not found: return
                
                pg = get_personal_group()
                if not pg: return
                
                sender = await event.get_sender()
                name = f"{getattr(sender, 'first_name', '')} {getattr(sender, 'last_name', '')}".strip()
                user = f"@{sender.username}" if hasattr(sender, 'username') and sender.username else "Yo'q"
                
                chat = await event.get_chat()
                g_name = getattr(chat, 'title', "Guruh")
                
                text = f"🔍 Topildi!\n📍 Guruh: {g_name}\n👤 Kimdan: {name} ({user})\n🔑 Kalit: {', '.join(found)}\n\n💬 Xabar:\n{msg}"
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👤 Profil", url=f"tg://user?id={sender.id}")]])
                
                await bot.send_message(pg[0], text, reply_markup=kb)
            except Exception as e: logger.error(f"Handler error: {e}")
            
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Userbot error: {e}")
        await bot.send_message(ADMIN_ID, f"❌ Userbotda xatolik: {e}\n\nEhtimol SESSION_STRING noto'g'ri.")

async def group_processor():
    while True:
        try:
            conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
            c.execute("SELECT user_id, state, data FROM user_state WHERE state LIKE 'process_%'")
            pending = c.fetchall(); conn.close()
            
            if pending and SESSION_STRING:
                client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
                await client.start()
                for uid, st, data in pending:
                    try:
                        if data.replace('-', '').isdigit(): ent = await client.get_entity(int(data))
                        else: ent = await client.get_entity(data.replace('@', '').replace('https://t.me/', ''))
                        
                        if st == 'process_search_group':
                            if add_search_group(ent.id, getattr(ent, 'title', 'Guruh')):
                                await bot.send_message(uid, f"✅ Guruh qo'shildi: {getattr(ent, 'title', ent.id)}", reply_markup=main_menu())
                        else:
                            set_personal_group(ent.id, getattr(ent, 'title', 'Guruh'))
                            await bot.send_message(uid, f"✅ Shaxsiy guruh o'rnatildi: {getattr(ent, 'title', ent.id)}", reply_markup=main_menu())
                        clear_user_state(uid)
                    except Exception as e:
                        await bot.send_message(uid, f"❌ Topilmadi: {e}", reply_markup=main_menu())
                        clear_user_state(uid)
                await client.disconnect()
        except: pass
        await asyncio.sleep(5)

async def main():
    init_db()
    asyncio.create_task(group_processor())
    asyncio.create_task(userbot_task())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
