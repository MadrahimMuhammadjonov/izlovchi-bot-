import asyncio
import sqlite3
import logging
import sys
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramConflictError

# ==========================================================
# 1. KONFIGURATSIYA (O'zingizning ma'lumotlaringizni kiriting)
# ==========================================================
BOT_TOKEN = "8045123024:AAGdfjgOJAUosbf4SfUpmDQkh2qeGOirblc"
ADMIN_ID = 8228479175
API_ID = 36799342
API_HASH = "fcdf748b56fb519c6900d02e25ae2d62"
SESSION_STRING = "1ApWapzMBu7wMtDnHS2BHSlKKIcR0O326szif2GpPek9MHzgLxHaafUzSGh864f--z_ImIsN8GkhzJY-T_TLRSyc2MdUBAX89sRsqUWumntyGQ1u0d0h3c0t0k_VSaqq3Mjjt401spd3TcLUgz8qb23Eh7PtVSvs1viHduuKXyExsUAkstyewIDamcQf2mlGQuoQiL5WBc63h5q6Roj-kff-xxr1TJB-3kag0XdKVKzS50xFWyXKBoixQ_XynUB1yk4qkaUbKv9ciCyZGy6yTRm3IgGk8Rb2BECId-p6fRR-jPsVemBhDZIOY2gwNNTrwty8I988h0lACcrT5Hyh9uX56KRlr8tc="

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Bot va Dispatcher obyektlari
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================================
# 2. MA'LUMOTLAR BAZASI BILAN ISHLASH
# ==========================================================
class Database:
    def __init__(self, db_name='bot_data.db'):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY AUTOINCREMENT, keyword TEXT UNIQUE)')
            c.execute('CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER UNIQUE, group_name TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS personal_group (id INTEGER PRIMARY KEY, group_id INTEGER, group_name TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT)')
            conn.commit()

    def add_keyword(self, keyword):
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.cursor().execute("INSERT INTO keywords (keyword) VALUES (?)", (keyword.lower(),))
                conn.commit()
                return True
        except: return False

    def get_keywords(self):
        with sqlite3.connect(self.db_name) as conn:
            return [row[0] for row in conn.cursor().execute("SELECT keyword FROM keywords").fetchall()]

    def delete_keyword(self, keyword):
        with sqlite3.connect(self.db_name) as conn:
            conn.cursor().execute("DELETE FROM keywords WHERE keyword=?", (keyword,))
            conn.commit()

    def add_search_group(self, group_id, group_name):
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.cursor().execute("INSERT OR REPLACE INTO search_groups (group_id, group_name) VALUES (?, ?)", (group_id, group_name))
                conn.commit()
                return True
        except: return False

    def get_search_groups(self):
        with sqlite3.connect(self.db_name) as conn:
            return conn.cursor().execute("SELECT group_id, group_name FROM search_groups").fetchall()

    def delete_search_group(self, group_id):
        with sqlite3.connect(self.db_name) as conn:
            conn.cursor().execute("DELETE FROM search_groups WHERE group_id=?", (group_id,))
            conn.commit()

    def set_personal_group(self, group_id, group_name):
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM personal_group")
            c.execute("INSERT INTO personal_group (id, group_id, group_name) VALUES (1, ?, ?)", (group_id, group_name))
            conn.commit()

    def get_personal_group(self):
        with sqlite3.connect(self.db_name) as conn:
            return conn.cursor().execute("SELECT group_id, group_name FROM personal_group WHERE id=1").fetchone()

    def set_state(self, user_id, state, data=""):
        with sqlite3.connect(self.db_name) as conn:
            conn.cursor().execute("REPLACE INTO user_state (user_id, state, data) VALUES (?, ?, ?)", (user_id, state, data))
            conn.commit()

    def get_state(self, user_id):
        with sqlite3.connect(self.db_name) as conn:
            res = conn.cursor().execute("SELECT state, data FROM user_state WHERE user_id=?", (user_id,)).fetchone()
            return res if res else (None, None)

    def clear_state(self, user_id):
        with sqlite3.connect(self.db_name) as conn:
            conn.cursor().execute("DELETE FROM user_state WHERE user_id=?", (user_id,))
            conn.commit()

db = Database()

# ==========================================================
# 3. YORDAMCHI FUNKSIYALAR
# ==========================================================
def normalize_id(tg_id):
    """Telethon ID-ni Bot API formatiga o'tkazish"""
    s_id = str(tg_id)
    if s_id.startswith('-100'): return int(s_id)
    elif s_id.startswith('-'): return int(f"-100{s_id[1:]}")
    else: return int(f"-100{s_id}")

def get_main_menu():
    kb = [
        [InlineKeyboardButton(text="➕ Kalit so'z", callback_data='add_kw'), InlineKeyboardButton(text="📋 Ro'yxat", callback_data='view_kw')],
        [InlineKeyboardButton(text="➕ Izlovchi guruh", callback_data='add_sg'), InlineKeyboardButton(text="📋 Guruhlar", callback_data='view_sg')],
        [InlineKeyboardButton(text="➕ Shaxsiy guruh", callback_data='add_pg'), InlineKeyboardButton(text="📋 Ko'rish", callback_data='view_pg')],
        [InlineKeyboardButton(text="🗑 Tozalash", callback_data='clear_all')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_main')]])

# ==========================================================
# 4. BOT HANDLERLARI (AIOGRAM)
# ==========================================================
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    await m.answer("🤖 **Izlovchi Bot Boshqaruv Paneli**\n\nBarcha tizimlar 100% ishchi holatda.", 
                   reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "back_main")
async def cb_back(c: types.CallbackQuery):
    db.clear_state(c.from_user.id)
    await c.message.edit_text("🤖 **Boshqaruv Paneli**", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "add_kw")
async def cb_add_kw(c: types.CallbackQuery):
    db.set_state(c.from_user.id, 'wait_kw')
    await c.message.edit_text("📝 **Yangi kalit so'z yuboring:**", reply_markup=get_back_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "view_kw")
async def cb_view_kw(c: types.CallbackQuery):
    kws = db.get_keywords()
    txt = "📋 **Kalit so'zlar ro'yxati:**\n\n" + "\n".join([f"• `{k}`" for k in kws]) if kws else "❌ Ro'yxat bo'sh."
    await c.message.edit_text(txt, reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "add_sg")
async def cb_add_sg(c: types.CallbackQuery):
    db.set_state(c.from_user.id, 'wait_sg')
    await c.message.edit_text("📝 **Izlovchi guruh ID yoki linkini yuboring:**", reply_markup=get_back_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "view_sg")
async def cb_view_sg(c: types.CallbackQuery):
    sgs = db.get_search_groups()
    txt = "📋 **Izlovchi guruhlar:**\n\n" + "\n".join([f"• {n} (`{i}`)" for i, n in sgs]) if sgs else "❌ Guruhlar yo'q."
    await c.message.edit_text(txt, reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "add_pg")
async def cb_add_pg(c: types.CallbackQuery):
    db.set_state(c.from_user.id, 'wait_pg')
    await c.message.edit_text("📝 **Shaxsiy guruh ID yoki linkini yuboring:**", reply_markup=get_back_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "view_pg")
async def cb_view_pg(c: types.CallbackQuery):
    pg = db.get_personal_group()
    txt = f"📋 **Shaxsiy guruh:**\n\n• {pg[1]} (`{pg[0]}`)" if pg else "❌ O'rnatilmagan."
    await c.message.edit_text(txt, reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.message(F.text)
async def handle_all_text(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    state, _ = db.get_state(m.from_user.id)
    
    if state == 'wait_kw':
        if db.add_keyword(m.text.strip()):
            await m.answer(f"✅ Kalit so'z `{m.text}` qo'shildi.", reply_markup=get_main_menu(), parse_mode="Markdown")
        else:
            await m.answer("❌ Bu kalit so'z allaqachon mavjud.", reply_markup=get_main_menu())
        db.clear_state(m.from_user.id)
        
    elif state in ['wait_sg', 'wait_pg']:
        target = 'process_sg' if state == 'wait_sg' else 'process_pg'
        db.set_state(m.from_user.id, target, m.text.strip())
        await m.answer("⏳ Guruh ma'lumotlari tekshirilmoqda...")

# ==========================================================
# 5. USERBOT VA GURUH PROTSESSORI (TELETHON)
# ==========================================================
async def userbot_engine():
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.start()
        me = await client.get_me()
        logger.info(f"✅ Userbot @{me.username} sifatida ulandi")
        
        @client.on(events.NewMessage())
        async def message_handler(event):
            try:
                # Guruhni tekshirish
                norm_chat_id = normalize_id(event.chat_id)
                search_groups = [g[0] for g in db.get_search_groups()]
                
                if norm_chat_id not in search_groups: return
                
                # Kalit so'zlarni tekshirish
                msg_text = event.message.message
                if not msg_text: return
                
                keywords = db.get_keywords()
                found = [k for k in keywords if k.lower() in msg_text.lower()]
                if not found: return
                
                # Shaxsiy guruhni olish
                pg = db.get_personal_group()
                if not pg: return
                
                # Ma'lumotlarni yig'ish
                sender = await event.get_sender()
                sender_name = f"{getattr(sender, 'first_name', '')} {getattr(sender, 'last_name', '')}".strip()
                sender_user = f"@{sender.username}" if hasattr(sender, 'username') and sender.username else "Username yo'q"
                
                chat = await event.get_chat()
                group_name = getattr(chat, 'title', "Guruh")
                
                # Hisobot tayyorlash
                report = (
                    f"🎯 **Kalit so'z topildi!**\n\n"
                    f"📍 **Guruh:** {group_name}\n"
                    f"👤 **Foydalanuvchi:** {sender_name} ({sender_user})\n"
                    f"🔑 **Kalit so'zlar:** {', '.join(found)}\n\n"
                    f"💬 **Xabar:**\n{msg_text[:1000]}"
                )
                
                kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👤 Profilga o'tish", url=f"tg://user?id={sender.id}")]])
                
                # Shaxsiy guruhga yuborish
                await bot.send_message(pg[0], report, reply_markup=kb, parse_mode="Markdown")
                logger.info(f"✅ Hisobot yuborildi: {pg[0]}")
                
            except Exception as e:
                logger.error(f"Userbot handler xatosi: {e}")

        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Userbot ishga tushishida xato: {e}")
        await bot.send_message(ADMIN_ID, f"❌ Userbot xatosi: {e}")

async def group_manager():
    """Guruhlarni qo'shishni boshqaruvchi fon vazifasi"""
    while True:
        try:
            with sqlite3.connect('bot_data.db') as conn:
                pending = conn.cursor().execute("SELECT user_id, state, data FROM user_state WHERE state LIKE 'process_%'").fetchall()
            
            if pending:
                client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
                await client.start()
                for uid, st, data in pending:
                    try:
                        # Entity olish
                        if data.replace('-', '').isdigit(): ent = await client.get_entity(int(data))
                        else: ent = await client.get_entity(data.replace('@', '').replace('https://t.me/', ''))
                        
                        norm_id = normalize_id(ent.id)
                        title = getattr(ent, 'title', 'Guruh')
                        
                        if 'sg' in st:
                            db.add_search_group(norm_id, title)
                            await bot.send_message(uid, f"✅ **Izlovchi guruh qo'shildi:**\n{title} (`{norm_id}`)", parse_mode="Markdown", reply_markup=get_main_menu())
                        else:
                            db.set_personal_group(norm_id, title)
                            await bot.send_message(uid, f"✅ **Shaxsiy guruh o'rnatildi:**\n{title} (`{norm_id}`)", parse_mode="Markdown", reply_markup=get_main_menu())
                        
                        db.clear_state(uid)
                    except Exception as e:
                        await bot.send_message(uid, f"❌ **Guruh topilmadi:** {e}", reply_markup=get_main_menu())
                        db.clear_state(uid)
                await client.disconnect()
        except: pass
        await asyncio.sleep(5)

# ==========================================================
# 6. ASOSIY ISHGA TUSHIRISH
# ==========================================================
async def main():
    logger.info("🚀 Bot ishga tushmoqda...")
    
    # Webhookni tozalash (Conflict oldini olish uchun)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Fon vazifalarini ishga tushirish
    asyncio.create_task(group_manager())
    asyncio.create_task(userbot_engine())
    
    # Pollingni boshlash
    logger.info("✅ Bot tayyor!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Bot to'xtatildi.")
