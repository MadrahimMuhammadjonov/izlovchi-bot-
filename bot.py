import asyncio
import sqlite3
import logging
import html
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, UserAlreadyParticipant, PeerIdInvalid
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8137576363:AAHerJWL_b4kgQsTY03_Dt6sLuPny-BlZ8g"
ADMIN_LIST = [7664337104, 7740552653] 
API_ID = 31654640
API_HASH = "22e66db2dba07587217d2f308ae412fb"
PERSONAL_GROUP_ID = -1003267783623
# Session stringni tozalab oling
SESSION_STRING = "AgHjAvAApBR1KFpVkWFYH3zWlkpd14Odc2nUeBd6gWRBix_fmqCiD-1BFyNbWWQu_bd38KvaG3wtXpBFTP2ulvpYWQaLj6xFRZbpuaNJKlE8Utevn6PjxS06HNRUGh43d15y5iH3O6YE-G95cBqvW4A7S3LFRDnS6Ofk4hfh0dj-GC43wD_hqcBxws1Y0OQ7AernvFlFtk-Opw5O-b8vl7RKrPWcrrlXrBg4U2gT6lTHRe3MREkbZdGveG7lhVdQqrrY25EjtmDn2t-qjLpvZwQ81K-IsjnfYc8obkGogwwwSBq6Q5QqMwoOh8tUPUIEN4UB_n6czgEhA6DP8mEcYqBi7r7hqgAAAAFTaP8IAA"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Railway uchun eng barqaror sozlama
userbot = Client(
    "my_userbot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    session_string=SESSION_STRING.strip(), 
    in_memory=True  # Bu muhim!
)

# --- DATABASE ---
async def db_query(query, params=(), fetch=False):
    def _execute():
        with sqlite3.connect('bot_data.db', timeout=30) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch: return cursor.fetchall()
            conn.commit()
            return None
    return await asyncio.to_thread(_execute)

# --- USERBOT: XABARLARNI FILTRLASH (ENG ASOSIY QISM) ---
@userbot.on_message(filters.group & ~filters.service)
async def message_watcher(client, message):
    if not message.text: return
    
    try:
        # Peer xatosini butunlay chetlab o'tish uchun try-except ichiga olamiz
        try:
            chat_id = message.chat.id
        except Exception:
            return # Agar chat_id bo'lmasa, xabarni o'tkazib yuboramiz

        # Bazadagi guruhlarni tekshirish
        res_groups = await db_query("SELECT group_id FROM search_groups", fetch=True)
        active_ids = [g[0] for g in res_groups]
        
        # Agar guruh bazada bo'lmasa, tekshirib ham o'tirmaymiz
        if chat_id not in active_ids: return

        # Kalit so'zlarni olish
        res_keywords = await db_query("SELECT keyword FROM keywords", fetch=True)
        keywords = [k[0] for k in res_keywords]
        
        message_text = message.text.lower()
        found = [w for w in keywords if w.lower() in message_text]
        
        if found:
            # Ma'lumotlarni yig'ish (Xatolardan himoyalangan holda)
            u_name = html.escape(message.from_user.full_name if message.from_user else "Foydalanuvchi")
            u_id = message.from_user.id if message.from_user else "Noma'lum"
            g_title = html.escape(message.chat.title or "Noma'lum Guruh")
            
            report = (
                f"🎯 <b>Yangi xabar!</b>\n\n"
                f"🔑 <b>Kalit so'zlar:</b> {', '.join(found)}\n"
                f"👤 <b>Kimdan:</b> {u_name} (ID: <code>{u_id}</code>)\n"
                f"📍 <b>Guruh:</b> {g_title}\n"
                f"📝 <b>Xabar:</b>\n<i>{html.escape(message.text[:800])}</i>"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👤 Profil", url=f"tg://user?id={u_id}")
            ]])
            
            # Shaxsiy guruhga yuborish
            await bot.send_message(PERSONAL_GROUP_ID, report, reply_markup=kb, parse_mode="HTML")
            logging.info(f"✅ Topildi va yuborildi: {g_title}")

    except (PeerIdInvalid, KeyError):
        # Peer xatosi chiqsa, guruhni bir marta "resolve" qilishga urinib ko'ramiz
        try:
            await client.get_chat(message.chat.id)
        except:
            pass
    except Exception as e:
        logging.error(f"Watcher error: {e}")

# --- ADMIN PANEL (GURUH QO'SHISH LOGIKASI) ---
async def join_chat_logic(link):
    try:
        # Havolani aniqlash
        if "t.me/+" in link or "t.me/joinchat/" in link:
            chat = await userbot.join_chat(link)
        else:
            username = link.replace("https://t.me/", "").replace("@", "").strip()
            chat = await userbot.join_chat(username)
        return chat
    except UserAlreadyParticipant:
        # Agar allaqachon a'zo bo'lsak, chat ma'lumotlarini shunchaki olamiz
        try:
            return await userbot.get_chat(link.replace("https://t.me/", "").replace("@", "").strip())
        except:
            return None
    except Exception as e:
        logging.error(f"Join error: {e}")
        return None

@dp.message(F.text, F.from_user.id.in_(ADMIN_LIST))
async def handle_admin_input(m: types.Message):
    st = await db_query("SELECT state FROM user_state WHERE user_id=?", (m.from_user.id,), fetch=True)
    if not st: return
    
    state = st[0][0]
    if state == "adding_gr":
        wait_msg = await m.answer("⏳ Guruhga ulanilmoqda...")
        chat = await join_chat_logic(m.text.strip())
        
        if chat:
            await db_query("INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", (chat.id, chat.title))
            await wait_msg.edit_text(f"✅ Guruv ulandi: <b>{chat.title}</b>\nID: <code>{chat.id}</code>", parse_mode="HTML")
        else:
            await wait_msg.edit_text("❌ Guruh topilmadi yoki Userbot qo'shila olmadi. Havolani tekshiring.")
        await db_query("DELETE FROM user_state WHERE user_id=?", (m.from_user.id,))
    
    elif state == "adding_kw":
        # Kalit so'zlarni qo'shish qismi...
        words = [w.strip() for w in m.text.split(",") if w.strip()]
        for w in words: await db_query("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (w,))
        await m.answer(f"✅ {len(words)} ta so'z qo'shildi.")
        await db_query("DELETE FROM user_state WHERE user_id=?", (m.from_user.id,))

# --- QOLGAN STANDART FUNKSIYALAR ---
@dp.message(Command("start"))
async def start(m: types.Message):
    if m.from_user.id in ADMIN_LIST:
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data="add_gr"))
        kb.row(InlineKeyboardButton(text="➕ Kalit so'z qo'shish", callback_data="add_kw"))
        await m.answer("Panel:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("add_"))
async def add_callback(c: types.CallbackQuery):
    mode = c.data
    await db_query("REPLACE INTO user_state (user_id, state) VALUES (?, ?)", (c.from_user.id, mode))
    txt = "Link yuboring:" if mode == "add_gr" else "So'zlarni vergul bilan yuboring:"
    await c.message.answer(txt)
    await c.answer()

async def main():
    # Jadvallarni yaratish
    await db_query('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE)')
    await db_query('CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY, group_id INTEGER UNIQUE, group_name TEXT)')
    await db_query('CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT)')
    
    await userbot.start()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🚀 Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
