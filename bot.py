import asyncio
import sqlite3
import logging
import html
from pyrogram import Client, filters
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

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- ASINXRON DB FUNKSIYALARI ---
async def db_query(query, params=(), fetch=False):
    return await asyncio.to_thread(_db_execute, query, params, fetch)

def _db_execute(query, params, fetch):
    with sqlite3.connect('bot_data.db', timeout=30) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch: return cursor.fetchall()
        conn.commit()
    return None

async def init_db():
    await db_query('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE)')
    await db_query('CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY, group_id INTEGER UNIQUE, group_name TEXT)')
    await db_query('CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT)')

# --- USERBOT: XABARLARNI KUZATISH ---
@app.on_message(filters.group)
async def message_watcher(client, message):
    if not message.text: return
    
    # Guruhlarni bazadan olish
    res_groups = await db_query("SELECT group_id FROM search_groups", fetch=True)
    active_groups = [g[0] for g in res_groups]
    if message.chat.id not in active_groups: return
    
    # Kalit so'zlarni tekshirish
    res_keywords = await db_query("SELECT keyword FROM keywords", fetch=True)
    keywords = [k[0] for k in res_keywords]
    found_words = [w for w in keywords if w.lower() in message.text.lower()]
    
    if found_words:
        sender_id = message.from_user.id if message.from_user else "noma'lum"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="👤 Profil", url=f"tg://user?id={sender_id}")
        ]])
        
        report = (f"🔍 <b>Topildi:</b> {', '.join(found_words)}\n"
                  f"<b>📍 Guruh:</b> {html.escape(message.chat.title or 'Guruh')}\n\n"
                  f"<b>📝 Xabar:</b>\n<i>{html.escape(message.text[:800])}</i>")
        
        try:
            await bot.send_message(PERSONAL_GROUP_ID, report, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Guruhga yuborishda xato: {e}")

# --- KLAVIATURALAR ---
def get_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔑 Kalit so'zlar", callback_data='menu_kw'))
    builder.row(InlineKeyboardButton(text="📡 Izlovchi guruhlar", callback_data='menu_gr'))
    builder.row(InlineKeyboardButton(text="⚙️ Tizim holati", callback_data='sys_status'))
    return builder.as_markup()

def get_sub_kb(mode):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Qo'shish", callback_data=f'add_{mode}'),
        InlineKeyboardButton(text="📋 Ro'yxat", callback_data=f'view_{mode}')
    )
    builder.row(
        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f'del_{mode}'),
        InlineKeyboardButton(text="🔙 Orqaga", callback_data='home')
    )
    return builder.as_markup()

# --- ADMIN HANDLERLARI ---
@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    if m.from_user.id in ADMIN_LIST:
        await db_query("DELETE FROM user_state WHERE user_id=?", (m.from_user.id,))
        await m.answer("🤖 <b>TDLib Boshqaruv Paneli</b>", reply_markup=get_main_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "home")
async def back_home(c: types.CallbackQuery):
    await db_query("DELETE FROM user_state WHERE user_id=?", (c.from_user.id,))
    await c.message.edit_text("🤖 <b>Boshqaruv Paneli</b>", reply_markup=get_main_kb(), parse_mode="HTML")

@dp.callback_query(F.data.in_({"menu_kw", "menu_gr"}))
async def sub_menu(c: types.CallbackQuery):
    mode = 'kw' if c.data == "menu_kw" else 'gr'
    title = "🔑 Kalit so'zlar" if mode == 'kw' else "📡 Guruhlar"
    await c.message.edit_text(f"<b>{title} bo'limi:</b>", reply_markup=get_sub_kb(mode), parse_mode="HTML")

@dp.callback_query(F.data.in_({"add_kw", "add_gr"}))
async def start_adding(c: types.CallbackQuery):
    mode = "adding_kw" if c.data == "add_kw" else "adding_gr"
    await db_query("REPLACE INTO user_state (user_id, state) VALUES (?, ?)", (c.from_user.id, mode))
    
    # Orqaga tugmasi doim bo'lishi uchun:
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="home")
    ]])
    
    txt = "📝 Kalit so'zlarni yuboring (vergul bilan):" if mode == "adding_kw" else "📡 Guruh linki yoki @username yuboring:"
    await c.message.edit_text(txt, reply_markup=back_kb)

@dp.message(F.text)
async def handle_admin_input(m: types.Message):
    if m.from_user.id not in ADMIN_LIST: return
    state_res = await db_query("SELECT state FROM user_state WHERE user_id=?", (m.from_user.id,), fetch=True)
    if not state_res: return
    
    state = state_res[0][0]
    back_btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="home")]])

    if state == "adding_kw":
        words = [w.strip() for w in m.text.split(",") if w.strip()]
        for w in words: await db_query("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (w,))
        await m.answer(f"✅ {len(words)} ta so'z qo'shildi. Yana yuborishingiz mumkin:", reply_markup=back_btn)
    
    elif state == "adding_gr":
        link = m.text.strip().replace("@", "").replace("https://t.me/", "").split("/")[0]
        try:
            chat = await app.get_chat(link)
            await db_query("INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", (chat.id, chat.title))
            await m.answer(f"✅ Guruh qo'shildi: <b>{chat.title}</b>\nNavbatdagisini yuboring:", reply_markup=back_btn, parse_mode="HTML")
        except Exception as e:
            await m.answer(f"❌ Xato: {e}\nLinkni tekshirib qayta yuboring:", reply_markup=back_btn)

@dp.callback_query(F.data.startswith("view_"))
async def view_items(c: types.CallbackQuery):
    mode = c.data.split("_")[1]
    table = "keywords" if mode == "kw" else "search_groups"
    col = "keyword" if mode == "kw" else "group_name"
    data = await db_query(f"SELECT {col} FROM {table}", fetch=True)
    
    txt = f"📋 <b>{'Ro\'yxat'}:</b>\n\n"
    txt += "\n".join([f"• {html.escape(str(x[0]))}" for x in data]) if data else "❌ Hozircha bo'sh"
    await c.message.edit_text(txt, reply_markup=get_sub_kb(mode), parse_mode="HTML")

@dp.callback_query(F.data.startswith("del_"))
async def delete_menu(c: types.CallbackQuery):
    mode = c.data.split("_")[1]
    table = "keywords" if mode == "kw" else "search_groups"
    col = "keyword" if mode == "kw" else "group_name"
    data = await db_query(f"SELECT id, {col} FROM {table}", fetch=True)
    
    builder = InlineKeyboardBuilder()
    for x in data:
        builder.row(InlineKeyboardButton(text=f"🗑 {x[1]}", callback_data=f"rm_{mode}_{x[0]}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"menu_{'kw' if mode=='kw' else 'gr'}"))
    
    await c.message.edit_text("O'chirish uchun tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("rm_"))
async def process_delete(c: types.CallbackQuery):
    _, mode, item_id = c.data.split("_")
    table = "keywords" if mode == "kw" else "search_groups"
    await db_query(f"DELETE FROM {table} WHERE id=?", (item_id,))
    await c.answer("O'chirildi")
    await delete_menu(c)

@dp.callback_query(F.data == "sys_status")
async def system_status(c: types.CallbackQuery):
    k = (await db_query("SELECT COUNT(*) FROM keywords", fetch=True))[0][0]
    g = (await db_query("SELECT COUNT(*) FROM search_groups", fetch=True))[0][0]
    txt = f"⚙️ <b>Tizim Holati:</b>\n\n🔑 Kalit so'zlar: {k}\n📡 Guruhlar: {g}\n✅ Bot holati: Faol"
    await c.message.edit_text(txt, reply_markup=get_main_kb(), parse_mode="HTML")

async def main():
    await init_db()
    await app.start()
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
