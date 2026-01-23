import asyncio
import sqlite3
import logging
import html
import re
import os
from telegram.client import Telegram
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

# TDLib Klientini sozlash
tg = Telegram(
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    database_encryption_key='changeme_secret_123',
    files_directory='tdlib_session'
)

# --- DB OPERATSIYALARI ---
def db_op(query, params=(), fetch=False):
    with sqlite3.connect('bot_data.db', timeout=30, check_same_thread=False) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch:
            return cursor.fetchall()
        conn.commit()
    return None

def init_db():
    db_op('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE)')
    db_op('CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY, group_id INTEGER UNIQUE, group_name TEXT)')
    db_op('CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT)')

# --- USERBOT (TDLib XABARLARNI KUZATISH) ---
def update_handler(update):
    if 'message' not in update:
        return
    
    msg_data = update['message']
    chat_id = msg_data.get('chat_id')
    
    # Guruh bazada borligini tekshirish
    res = db_op("SELECT group_id FROM search_groups WHERE group_id=?", (chat_id,), fetch=True)
    if not res:
        return

    content = msg_data.get('content', {})
    text = ""
    if content.get('@type') == 'messageText':
        text = content['text'].get('text', "")
    
    if text:
        words = [k[0] for k in db_op("SELECT keyword FROM keywords", fetch=True)]
        found = [w for w in words if w.lower() in text.lower()]
        
        if found:
            sender_id = msg_data.get('sender_id', {}).get('user_id', "noma'lum")
            p_link = f"tg://user?id={sender_id}"
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👤 Profil", url=p_link)]])
            
            report = (f"🔍 <b>Topildi:</b> {', '.join(found)}\n"
                      f"<b>📍 Guruh ID:</b> <code>{chat_id}</code>\n\n"
                      f"<b>📝 Xabar:</b>\n<i>{html.escape(text[:800])}</i>")
            
            asyncio.run_coroutine_threadsafe(
                bot.send_message(PERSONAL_GROUP_ID, report, reply_markup=kb, parse_mode="HTML"),
                loop
            )

# --- ASOSIY MENYULAR ---
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

# --- AIOGRAM HANDLERLARI ---
@dp.message(Command("start"))
async def start(m: types.Message):
    if m.from_user.id in ADMIN_LIST:
        db_op("DELETE FROM user_state WHERE user_id=?", (m.from_user.id,))
        await m.answer("🤖 <b>TDLib Boshqaruv paneli:</b>", reply_markup=main_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "main_home")
async def go_home(c: types.CallbackQuery):
    db_op("DELETE FROM user_state WHERE user_id=?", (c.from_user.id,))
    await c.message.edit_text("🤖 <b>Boshqaruv paneli:</b>", reply_markup=main_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "open_keywords")
async def open_kw(c: types.CallbackQuery):
    await c.message.edit_text("🔑 <b>Kalit so'zlar bo'limi:</b>", reply_markup=sub_kb('kw'), parse_mode="HTML")

@dp.callback_query(F.data == "open_groups")
async def open_gr(c: types.CallbackQuery):
    await c.message.edit_text("📡 <b>Izlovchi guruhlar bo'limi:</b>", reply_markup=sub_kb('gr'), parse_mode="HTML")

# --- QO'SHISH AMALLARI ---
@dp.callback_query(F.data.in_({"add_kw", "add_gr"}))
async def add_start(c: types.CallbackQuery):
    mode = "adding_kw" if c.data == "add_kw" else "adding_gr"
    db_op("REPLACE INTO user_state VALUES (?, ?, ?)", (c.from_user.id, mode, ""))
    txt = "📝 Kalit so'zlarni vergul bilan yuboring:" if mode == "adding_kw" else "📡 Guruh linkini yoki @username yuboring:"
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data='main_home')]]))

@dp.message(F.text)
async def handle_text(m: types.Message):
    if m.from_user.id not in ADMIN_LIST: return
    st_res = db_op("SELECT state FROM user_state WHERE user_id=?", (m.from_user.id,), fetch=True)
    if not st_res: return
    
    state = st_res[0][0]
    if state == "adding_kw":
        words = [w.strip() for w in m.text.split(",") if w.strip()]
        for w in words: db_op("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (w,))
        await m.answer(f"✅ {len(words)} ta so'z qo'shildi!", reply_markup=sub_kb('kw'))
    
    elif state == "adding_gr":
        link = m.text.strip().replace("@", "").replace("https://t.me/", "").split("/")[0]
        try:
            res = tg.call_method('searchPublicChat', {'username': link})
            res.wait()
            chat = res.update
            tg.call_method('joinChat', {'chat_id': chat['id']}).wait()
            db_op("INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", (chat['id'], chat['title']))
            await m.answer(f"✅ Qo'shildi: {chat['title']}", reply_markup=sub_kb('gr'))
        except Exception as e:
            await m.answer(f"❌ Xato: {e}")
    db_op("DELETE FROM user_state WHERE user_id=?", (m.from_user.id,))

# --- KO'RISH VA O'CHIRISH ---
@dp.callback_query(F.data.startswith("view_"))
async def view_list(c: types.CallbackQuery):
    mode = c.data.split("_")[1]
    if mode == "kw":
        data = db_op("SELECT keyword FROM keywords", fetch=True)
        txt = "📋 <b>Kalit so'zlar:</b>\n\n" + "\n".join([f"• {x[0]}" for x in data]) if data else "❌ Ro'yxat bo'sh"
    else:
        data = db_op("SELECT group_name, group_id FROM search_groups", fetch=True)
        txt = "📋 <b>Guruhlar:</b>\n\n" + "\n".join([f"• {x[0]} (<code>{x[1]}</code>)" for x in data]) if data else "❌ Ro'yxat bo'sh"
    await c.message.edit_text(txt, reply_markup=sub_kb(mode), parse_mode="HTML")

@dp.callback_query(F.data.startswith("del_"))
async def del_list(c: types.CallbackQuery):
    mode = c.data.split("_")[1]
    table = "keywords" if mode == "kw" else "search_groups"
    col = "keyword" if mode == "kw" else "group_name"
    data = db_op(f"SELECT id, {col} FROM {table}", fetch=True)
    
    if not data:
        await c.answer("O'chirish uchun ma'lumot yo'q!")
        return

    kb = []
    for item_id, name in data:
        kb.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"rm_{mode}_{item_id}")])
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=f'open_{"keywords" if mode=="kw" else "groups"}')])
    
    await c.message.edit_text("🗑 O'chirishni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("rm_"))
async def remove_item(c: types.CallbackQuery):
    _, mode, item_id = c.data.split("_")
    table = "keywords" if mode == "kw" else "search_groups"
    db_op(f"DELETE FROM {table} WHERE id=?", (item_id,))
    await c.answer("O'chirildi!")
    await go_home(c)

@dp.callback_query(F.data == "sys_status")
async def status(c: types.CallbackQuery):
    k = db_op("SELECT COUNT(*) FROM keywords", fetch=True)[0][0]
    g = db_op("SELECT COUNT(*) FROM search_groups", fetch=True)[0][0]
    await c.message.edit_text(f"⚙️ <b>Status:</b>\n\n🔑 So'zlar: {k}\n📡 Guruhlar: {g}\n✅ TDLib: Faol", reply_markup=main_kb(), parse_mode="HTML")

# --- ISHGA TUSHIRISH ---
async def main():
    global loop
    loop = asyncio.get_running_loop()
    init_db()
    tg.login()
    tg.add_handler(update_handler)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
