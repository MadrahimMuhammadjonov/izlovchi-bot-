import asyncio
import sqlite3
import logging
import html
from pyrogram import Client, filters
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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

# --- DB OPERATSIYALARI ---
def db_op(query, params=(), fetch=False):
    with sqlite3.connect('bot_data.db', timeout=30, check_same_thread=False) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch: return cursor.fetchall()
        conn.commit()
    return None

def init_db():
    db_op('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE)')
    db_op('CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY, group_id INTEGER UNIQUE, group_name TEXT)')
    db_op('CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT)')

# --- XABARLARNI KUZATISH ---
@app.on_message(filters.group)
async def watcher(client, message):
    if not message.text: return
    groups = [g[0] for g in db_op("SELECT group_id FROM search_groups", fetch=True)]
    if message.chat.id not in groups: return
    
    words = [k[0] for k in db_op("SELECT keyword FROM keywords", fetch=True)]
    found = [w for w in words if w.lower() in message.text.lower()]
    
    if found:
        user_id = message.from_user.id if message.from_user else "noma'lum"
        p_link = f"tg://user?id={user_id}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👤 Profil", url=p_link)]])
        
        txt = (f"🔍 <b>Topildi:</b> {', '.join(found)}\n"
               f"<b>📍 Guruh:</b> {html.escape(message.chat.title or 'Guruh')}\n\n"
               f"<b>📝 Xabar:</b>\n<i>{html.escape(message.text[:800])}</i>")
        await bot.send_message(PERSONAL_GROUP_ID, txt, reply_markup=kb, parse_mode="HTML")

# --- KLAVIATURALAR ---
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Kalit so'zlar", callback_data='open_keywords')],
        [InlineKeyboardButton(text="📡 Izlovchi guruhlar", callback_data='open_groups')],
        [InlineKeyboardButton(text="⚙️ Tizim holati", callback_data='sys_status')]
    ])

def sub_kb(mode):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qo'shish", callback_data=f'add_{mode}')],
        [InlineKeyboardButton(text="📋 Ro'yxat", callback_data=f'view_{mode}')],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f'del_{mode}')],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data='main_home')]
    ])

# --- ADMIN HANDLERLARI ---
@dp.message(Command("start"))
async def start(m: types.Message):
    if m.from_user.id in ADMIN_LIST:
        db_op("DELETE FROM user_state WHERE user_id=?", (m.from_user.id,))
        await m.answer("🤖 <b>Boshqaruv paneli:</b>", reply_markup=main_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "main_home")
async def go_home(c: types.CallbackQuery):
    db_op("DELETE FROM user_state WHERE user_id=?", (c.from_user.id,))
    await c.message.edit_text("🤖 <b>Boshqaruv paneli:</b>", reply_markup=main_kb(), parse_mode="HTML")

@dp.callback_query(F.data.in_({"open_keywords", "open_groups"}))
async def open_sections(c: types.CallbackQuery):
    mode = 'kw' if c.data == "open_keywords" else 'gr'
    title = "🔑 Kalit so'zlar" if mode == 'kw' else "📡 Guruhlar"
    await c.message.edit_text(f"<b>{title} bo'limi:</b>", reply_markup=sub_kb(mode), parse_mode="HTML")

@dp.callback_query(F.data.in_({"add_kw", "add_gr"}))
async def add_start(c: types.CallbackQuery):
    mode = "adding_kw" if c.data == "add_kw" else "adding_gr"
    db_op("REPLACE INTO user_state VALUES (?, ?, ?)", (c.from_user.id, mode, ""))
    
    if mode == "adding_kw":
        txt = "📝 <b>Kalit so'zlarni kiritish rejimi:</b>\n\nSo'zlarni vergul bilan yuboring. Bo'lgach '🔙 Orqaga' tugmasini bosing."
    else:
        txt = "📡 <b>Guruhlarni kiritish rejimi:</b>\n\nGuruh linkini yoki @username yuboring. Har bir yuborilgan guruh darhol qo'shiladi. Bo'lgach '🔙 Orqaga' tugmasini bosing."
        
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data='open_groups' if mode=="adding_gr" else 'open_keywords')]]), parse_mode="HTML")

@dp.message(F.text)
async def handle_text(m: types.Message):
    if m.from_user.id not in ADMIN_LIST: return
    state_res = db_op("SELECT state FROM user_state WHERE user_id=?", (m.from_user.id,), fetch=True)
    if not state_res: return
    
    state = state_res[0][0]
    
    if state == "adding_kw":
        words = [w.strip() for w in m.text.split(",") if w.strip()]
        new_count = 0
        for w in words:
            db_op("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (w,))
            new_count += 1
        await m.answer(f"✅ {new_count} ta so'z qo'shildi. Yana yuborishingiz mumkin (yoki 'Orqaga' bosing).")
    
    elif state == "adding_gr":
        link = m.text.strip().replace("@", "").replace("https://t.me/", "").split("/")[0]
        try:
            chat = await app.get_chat(link)
            db_op("INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", (chat.id, chat.title))
            await m.answer(f"✅ Guruh qo'shildi: <b>{chat.title}</b>\nNavbatdagisini yuboring...", parse_mode="HTML")
        except Exception as e:
            await m.answer(f"❌ Xatolik: {e}\nBoshqa link yuborib ko'ring.")

# --- RO'YXAT VA O'CHIRISH ---
@dp.callback_query(F.data.startswith("view_"))
async def view_list(c: types.CallbackQuery):
    mode = c.data.split("_")[1]
    table = "keywords" if mode == "kw" else "search_groups"
    col = "keyword" if mode == "kw" else "group_name"
    data = db_op(f"SELECT {col} FROM {table}", fetch=True)
    txt = f"📋 <b>{'So\'zlar' if mode=='kw' else 'Guruhlar'}:</b>\n\n"
    txt += "\n".join([f"• {html.escape(str(x[0]))}" for x in data]) if data else "❌ Ro'yxat bo'sh"
    await c.message.edit_text(txt, reply_markup=sub_kb(mode), parse_mode="HTML")

@dp.callback_query(F.data.startswith("del_"))
async def del_list(c: types.CallbackQuery):
    mode = c.data.split("_")[1]
    table = "keywords" if mode == "kw" else "search_groups"
    col = "keyword" if mode == "kw" else "group_name"
    data = db_op(f"SELECT id, {col} FROM {table}", fetch=True)
    if not data: return await c.answer("O'chirishga narsa yo'q")
    
    kb = [[InlineKeyboardButton(text=f"🗑 {x[1]}", callback_data=f"rm_{mode}_{x[0]}")] for x in data]
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"open_{'keywords' if mode=='kw' else 'groups'}")])
    await c.message.edit_text("O'chirish uchun tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("rm_"))
async def remove_item(c: types.CallbackQuery):
    _, mode, item_id = c.data.split("_")
    table = "keywords" if mode == "kw" else "search_groups"
    db_op(f"DELETE FROM {table} WHERE id=?", (item_id,))
    await c.answer("O'chirildi!")
    # O'chirilgandan so'ng yangilangan ro'yxatga qaytish
    await view_list(c)

@dp.callback_query(F.data == "sys_status")
async def status(c: types.CallbackQuery):
    k = db_op("SELECT COUNT(*) FROM keywords", fetch=True)[0][0]
    g = db_op("SELECT COUNT(*) FROM search_groups", fetch=True)[0][0]
    txt = f"⚙️ <b>Status:</b>\n\n🔑 So'zlar: {k}\n📡 Guruhlar: {g}\n✅ Holat: Faol"
    await c.message.edit_text(txt, reply_markup=main_kb(), parse_mode="HTML")

# --- ISHGA TUSHIRISH ---
async def main():
    init_db()
    await app.start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
