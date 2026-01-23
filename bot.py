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
SESSION_STRING = "AgHjAvAApBR1KFpVkWFYH3zWlkpd14Odc2nUeBd6gWRBix_fmqCiD-1BFyNbWWQu_bd38KvaG3wtXpBFTP2ulvpYWQaLj6xFRZbpuaNJKlE8Utevn6PjxS06HNRUGh43d15y5iH3O6YE-G95cBqvW4A7S3LFRDnS6Ofk4hfh0dj-GC43wD_hqcBxws1Y0OQ7AernvFlFtk-Opw5O-b8vl7RKrPWcrrlXrBg4U2gT6lTHRe3MREkbZdGveG7lhVdQqrrY25EjtmDn2t-qjLpvZwQ81K-IsjnfYc8obkGogwwwSBq6Q5QqMwoOh8tUPUIEN4UB_n6czgEhA6DP8mEcYqBi7r7hqgAAAAFTaP8IAA"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

userbot = Client(
    "my_userbot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    session_string=SESSION_STRING.strip(), 
    in_memory=True
)

# --- DB FUNKSIYALARI ---
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

# --- USERBOT: GURUHGA QO'SHILISH ---
async def join_chat_logic(link):
    try:
        clean = link.replace("https://t.me/", "").replace("t.me/", "").replace("@", "").strip()
        if "joinchat/" in clean or "+" in clean:
            invite_hash = clean.replace("joinchat/", "").replace("+", "")
            chat = await userbot.join_chat(invite_hash)
        else:
            chat = await userbot.join_chat(clean)
        return chat
    except UserAlreadyParticipant:
        return await userbot.get_chat(clean)
    except Exception as e:
        logging.error(f"Join error: {e}")
        try: return await userbot.get_chat(clean)
        except: return None

# --- USERBOT: XABARLARNI KUZATISH ---
@userbot.on_message(filters.group & ~filters.service)
async def message_watcher(client, message):
    if not message.text: return
    try:
        # 1. Izlovchi guruhlarni tekshirish
        res_groups = await db_query("SELECT group_id FROM search_groups", fetch=True)
        active_ids = [g[0] for g in res_groups]
        if message.chat.id not in active_ids: return

        # 2. Xatolarni oldini olish uchun majburiy "Peer Resolve"
        try:
            await client.resolve_peer(message.chat.id)
        except Exception:
            pass # Agar resolve bo'lmasa, Pyrogram o'zi ichki keshdan foydalanadi

        # 3. Kalit so'zlarni tekshirish
        res_keywords = await db_query("SELECT keyword FROM keywords", fetch=True)
        keywords = [k[0] for k in res_keywords]
        found = [w for w in keywords if w.lower() in message.text.lower()]
        
        if found:
            u_name = html.escape(message.from_user.full_name if message.from_user else "Foydalanuvchi")
            u_id = message.from_user.id if message.from_user else "Noma'lum"
            g_title = html.escape(message.chat.title or "Guruh")
            
            report = (
                f"🎯 <b>Yangi xabar topildi!</b>\n\n"
                f"🔑 <b>Kalit so'z:</b> {', '.join(found)}\n"
                f"👤 <b>Kimdan:</b> {u_name} (ID: <code>{u_id}</code>)\n"
                f"📍 <b>Guruh:</b> {g_title}\n"
                f"📝 <b>Xabar:</b>\n<i>{html.escape(message.text[:800])}</i>"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👤 Profilga o'tish", url=f"tg://user?id={u_id}")
            ]])
            
            # 4. Shaxsiy guruhga yuborish (Xato ehtimoli bilan)
            try:
                await bot.send_message(PERSONAL_GROUP_ID, report, reply_markup=kb, parse_mode="HTML")
                logging.info(f"✅ Xabar yuborildi: {g_title}")
            except Exception as e:
                logging.error(f"❌ Shaxsiy guruhga yuborishda xato: {e}")

    except Exception as e:
        logging.debug(f"Watcher error: {e}")

# --- ADMIN PANEL ---
def main_kb():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔑 Kalit so'zlar", callback_data='menu_kw'),
          InlineKeyboardButton(text="📡 Guruhlar", callback_data='menu_gr'))
    b.row(InlineKeyboardButton(text="⚙️ Holat", callback_data='sys_status'))
    return b.as_markup()

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    if m.from_user.id in ADMIN_LIST:
        await m.answer("🤖 <b>Asosiy menyu:</b>", reply_markup=main_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "home")
async def back_home(c: types.CallbackQuery):
    await db_query("DELETE FROM user_state WHERE user_id=?", (c.from_user.id,))
    await c.message.edit_text("🤖 <b>Asosiy menyu:</b>", reply_markup=main_kb(), parse_mode="HTML")

@dp.callback_query(F.data.in_({"menu_kw", "menu_gr"}))
async def sub_menu(c: types.CallbackQuery):
    mode = 'kw' if c.data == "menu_kw" else 'gr'
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Qo'shish", callback_data=f'add_{mode}'),
           InlineKeyboardButton(text="📋 Ro'yxat", callback_data=f'view_{mode}'))
    kb.row(InlineKeyboardButton(text="🗑 O'chirish", callback_data=f'del_{mode}'),
           InlineKeyboardButton(text="🔙 Orqaga", callback_data='home'))
    await c.message.edit_text(f"<b>{'🔑 So\'z' if mode=='kw' else '📡 Guruh'} sozlamalari:</b>", reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("add_"))
async def start_add(c: types.CallbackQuery):
    mode = "adding_kw" if c.data == "add_kw" else "adding_gr"
    await db_query("REPLACE INTO user_state (user_id, state) VALUES (?, ?)", (c.from_user.id, mode))
    txt = "📝 So'zlarni vergul bilan yuboring:" if mode == "adding_kw" else "📡 Guruh linkini yuboring (Userbot qo'shiladi):"
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="home")]]))

@dp.message(F.text)
async def handle_admin_text(m: types.Message):
    if m.from_user.id not in ADMIN_LIST: return
    st = await db_query("SELECT state FROM user_state WHERE user_id=?", (m.from_user.id,), fetch=True)
    if not st: return
    
    state = st[0][0]
    if state == "adding_kw":
        for w in m.text.split(","): await db_query("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (w.strip(),))
        await m.answer("✅ Saqlandi.", reply_markup=main_kb())
    elif state == "adding_gr":
        wait = await m.answer("⏳ Userbot guruhga qo'shilmoqda...")
        chat = await join_chat_logic(m.text.strip())
        if chat:
            await db_query("INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", (chat.id, chat.title))
            await wait.edit_text(f"✅ Guruh qo'shildi: <b>{chat.title}</b>", parse_mode="HTML", reply_markup=main_kb())
        else:
            await wait.edit_text("❌ Guruhga kirib bo'lmadi.", reply_markup=main_kb())
    
    await db_query("DELETE FROM user_state WHERE user_id=?", (m.from_user.id,))

@dp.callback_query(F.data.startswith("view_"))
async def view_items(c: types.CallbackQuery):
    mode = c.data.split("_")[1]
    table, col = ("keywords", "keyword") if mode == "kw" else ("search_groups", "group_name")
    data = await db_query(f"SELECT {col} FROM {table}", fetch=True)
    txt = "📋 <b>Ro'yxat:</b>\n\n" + "\n".join([f"• {html.escape(str(x[0]))}" for x in data]) if data else "Bo'sh"
    await c.message.edit_text(txt, reply_markup=main_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("del_"))
async def delete_menu(c: types.CallbackQuery):
    mode = c.data.split("_")[1]
    table, col = ("keywords", "keyword") if mode == "kw" else ("search_groups", "group_name")
    data = await db_query(f"SELECT id, {col} FROM {table}", fetch=True)
    builder = InlineKeyboardBuilder()
    for x in data: builder.row(InlineKeyboardButton(text=f"🗑 {x[1]}", callback_data=f"rm_{mode}_{x[0]}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"menu_{mode}"))
    await c.message.edit_text("O'chirish:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("rm_"))
async def process_rm(c: types.CallbackQuery):
    _, mode, i_id = c.data.split("_")
    await db_query(f"DELETE FROM {'keywords' if mode=='kw' else 'search_groups'} WHERE id=?", (i_id,))
    await c.answer("O'chirildi")
    await delete_menu(c)

@dp.callback_query(F.data == "sys_status")
async def sys_status(c: types.CallbackQuery):
    k = (await db_query("SELECT COUNT(*) FROM keywords", fetch=True))[0][0]
    g = (await db_query("SELECT COUNT(*) FROM search_groups", fetch=True))[0][0]
    await c.message.edit_text(f"⚙️ <b>Holat:</b>\n\n🔑 So'zlar: {k}\n📡 Guruhlar: {g}\n✅ Tizim: Faol", reply_markup=main_kb(), parse_mode="HTML")

async def main():
    await db_query('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE)')
    await db_query('CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY, group_id INTEGER UNIQUE, group_name TEXT)')
    await db_query('CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT)')
    try:
        await userbot.start()
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("🚀 Tizim muvaffaqiyatli ishga tushdi!")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"START ERROR: {e}")

if __name__ == '__main__':
    asyncio.run(main())
