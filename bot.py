import asyncio
import sqlite3
import logging
import html
import os
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

# SESSKIYA KODI - Hech qanday bo'sh joysiz bir qatorda bo'lishi shart
SESSION_STRING = "1ApWapzMBu4E9Kp6_zhIWbAr9GndIqukjWw51smf1l9CXbEviZSSGZCg3RzqIS4HCEigBsBvup0b6iPctHFcigaO_p70kKhrJ2Qkza5Ua2bqcJbFIlRZtJPxfoESMmXMqEtZWQ-VytgJp4sQFT_6sta_LMldT6wiCai5wMPKO51iKHYUYHB2ggRRr7Lp9JOprTRmBWdOVYX0povfDgWDrIgBuO1BVXhTpBin2BpjwxvdknZkzv-wiZJRpAMuXfazNM1cg80ggNbNP313yY3ptY7jBR_TjM1--LbzSzTY9IpC5RPwcg-OQB1nixO3U-KP4e4LhLrGi0i4F2y-R3QagopY8DelDotI="

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Userbot: in_memory=True Railway-da sessiya fayli yaratmaslik uchun kerak
userbot = Client(
    "my_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING.strip(),
    in_memory=True
)

# --- DB OPERATSIYALARI ---
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

# --- USERBOT: XABARLARNI KUZATISH ---
@userbot.on_message(filters.group & ~filters.service)
async def message_watcher(client, message):
    try:
        if not message.text: return
        
        # Kuzatilayotgan guruhlar ro'yxati
        res_groups = await db_query("SELECT group_id FROM search_groups", fetch=True)
        active_groups = [g[0] for g in res_groups]
        if message.chat.id not in active_groups: return
        
        # Kalit so'zlarni tekshirish
        res_keywords = await db_query("SELECT keyword FROM keywords", fetch=True)
        keywords = [k[0] for k in res_keywords]
        found_words = [w for w in keywords if w.lower() in message.text.lower()]
        
        if found_words:
            u_name = html.escape(message.from_user.full_name if message.from_user else "Foydalanuvchi")
            u_id = message.from_user.id if message.from_user else "Noma'lum"
            g_title = html.escape(message.chat.title or "Guruh")
            
            report = (
                f"🎯 <b>Yangi xabar topildi!</b>\n\n"
                f"🔑 <b>Kalit so'z:</b> {', '.join(found_words)}\n"
                f"👤 <b>Kimdan:</b> {u_name} (ID: <code>{u_id}</code>)\n"
                f"📍 <b>Guruh:</b> {g_title}\n"
                f"📝 <b>Xabar:</b>\n<i>{html.escape(message.text[:800])}</i>"
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👤 Profilga o'tish", url=f"tg://user?id={u_id}")
            ]])
            
            await bot.send_message(PERSONAL_GROUP_ID, report, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Watcher xatosi: {e}")

# --- ADMIN PANEL ---
def get_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔑 Kalit so'zlar", callback_data='menu_kw'))
    builder.row(InlineKeyboardButton(text="📡 Izlovchi guruhlar", callback_data='menu_gr'))
    builder.row(InlineKeyboardButton(text="⚙️ Holat", callback_data='sys_status'))
    return builder.as_markup()

def get_sub_kb(mode):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Qo'shish", callback_data=f'add_{mode}'),
                InlineKeyboardButton(text="📋 Ro'yxat", callback_data=f'view_{mode}'))
    builder.row(InlineKeyboardButton(text="🗑 O'chirish", callback_data=f'del_{mode}'),
                InlineKeyboardButton(text="🔙 Orqaga", callback_data='home'))
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    if m.from_user.id in ADMIN_LIST:
        await db_query("DELETE FROM user_state WHERE user_id=?", (m.from_user.id,))
        await m.answer("🤖 <b>Boshqaruv Paneli:</b>", reply_markup=get_main_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "home")
async def back_home(c: types.CallbackQuery):
    await db_query("DELETE FROM user_state WHERE user_id=?", (c.from_user.id,))
    await c.message.edit_text("🤖 <b>Asosiy menyu:</b>", reply_markup=get_main_kb(), parse_mode="HTML")

@dp.callback_query(F.data.in_({"menu_kw", "menu_gr"}))
async def sub_menu(c: types.CallbackQuery):
    mode = 'kw' if c.data == "menu_kw" else 'gr'
    await c.message.edit_text(f"<b>{'🔑 So\'zlar' if mode=='kw' else '📡 Guruhlar'} bo'limi:</b>", reply_markup=get_sub_kb(mode), parse_mode="HTML")

@dp.callback_query(F.data.startswith("add_"))
async def start_adding(c: types.CallbackQuery):
    mode = "adding_kw" if c.data == "add_kw" else "adding_gr"
    await db_query("REPLACE INTO user_state (user_id, state) VALUES (?, ?)", (c.from_user.id, mode))
    txt = "📝 So'zlarni vergul bilan yuboring:" if mode == "adding_kw" else "📡 Guruh havolasini yuboring (@username yoki link):"
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="home")]]))

@dp.message(F.text)
async def handle_input(m: types.Message):
    if m.from_user.id not in ADMIN_LIST: return
    res = await db_query("SELECT state FROM user_state WHERE user_id=?", (m.from_user.id,), fetch=True)
    if not res: return
    
    state = res[0][0]
    if state == "adding_kw":
        words = [w.strip() for w in m.text.split(",") if w.strip()]
        for w in words: await db_query("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (w,))
        await m.answer(f"✅ {len(words)} ta so'z qo'shildi.", reply_markup=get_main_kb())
    elif state == "adding_gr":
        try:
            chat = await userbot.get_chat(m.text.strip())
            await db_query("INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", (chat.id, chat.title))
            await m.answer(f"✅ Guruh qo'shildi: {chat.title}", reply_markup=get_main_kb())
        except Exception as e:
            await m.answer(f"❌ Xato: {e}\nGuruhni qo'shish uchun userbot u yerda a'zo bo'lishi kerak.")
    await db_query("DELETE FROM user_state WHERE user_id=?", (m.from_user.id,))

@dp.callback_query(F.data.startswith("view_"))
async def view_items(c: types.CallbackQuery):
    mode = c.data.split("_")[1]
    table = "keywords" if mode == "kw" else "search_groups"
    col = "keyword" if mode == "kw" else "group_name"
    data = await db_query(f"SELECT {col} FROM {table}", fetch=True)
    txt = f"📋 <b>Ro'yxat:</b>\n\n" + "\n".join([f"• {html.escape(str(x[0]))}" for x in data]) if data else "❌ Hozircha bo'sh"
    await c.message.edit_text(txt, reply_markup=get_sub_kb(mode), parse_mode="HTML")

@dp.callback_query(F.data.startswith("del_"))
async def delete_menu(c: types.CallbackQuery):
    mode = c.data.split("_")[1]
    table = "keywords" if mode == "kw" else "search_groups"
    col = "keyword" if mode == "kw" else "group_name"
    data = await db_query(f"SELECT id, {col} FROM {table}", fetch=True)
    builder = InlineKeyboardBuilder()
    for x in data: builder.row(InlineKeyboardButton(text=f"🗑 {x[1]}", callback_data=f"rm_{mode}_{x[0]}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"menu_{mode}"))
    await c.message.edit_text("O'chirish uchun tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("rm_"))
async def process_rm(c: types.CallbackQuery):
    _, mode, i_id = c.data.split("_")
    await db_query(f"DELETE FROM {'keywords' if mode=='kw' else 'search_groups'} WHERE id=?", (i_id,))
    await c.answer("O'chirildi")
    await delete_menu(c)

@dp.callback_query(F.data == "sys_status")
async def system_status(c: types.CallbackQuery):
    k = (await db_query("SELECT COUNT(*) FROM keywords", fetch=True))[0][0]
    g = (await db_query("SELECT COUNT(*) FROM search_groups", fetch=True))[0][0]
    await c.message.edit_text(f"⚙️ <b>Holat:</b>\n\n🔑 So'zlar: {k}\n📡 Guruhlar: {g}\n✅ Userbot: Faol", reply_markup=get_main_kb(), parse_mode="HTML")

# --- ISHGA TUSHIRISH ---
async def main():
    # Jadvallarni yaratish
    await db_query('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE)')
    await db_query('CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY, group_id INTEGER UNIQUE, group_name TEXT)')
    await db_query('CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT)')
    
    try:
        logging.info("Sessiya tekshirilmoqda...")
        await userbot.start()
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("🚀 Tizim muvaffaqiyatli ishga tushdi!")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ ISHGA TUSHIRISHDA XATO: {e}")

if __name__ == '__main__':
    asyncio.run(main())
