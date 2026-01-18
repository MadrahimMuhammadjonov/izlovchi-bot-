import asyncio
import sqlite3
import logging
import html
import re
import os
from telethon import TelegramClient, events, functions, errors
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8137576363:AAHnsJSkK5oNtGBUX8FDC7OHtYevB2xeMgQ"
ADMIN_LIST = [7664337104, 7740552653]  # Ikkala admin ID raqami
DEV_ID = 7740552653                 # Dasturchi ID (bog'lanish uchun)

API_ID = 31654640
API_HASH = "22e66db2dba07587217d2f308ae412fb"
SESSION_STRING = "1ApWapzMBu4E9Kp6_zhIWbAr9GndIqukjWw51smf1l9CXbEviZSSGZCg3RzqIS4HCEigBsBvup0b6iPctHFcigaO_p70kKhrJ2Qkza5Ua2bqcJbFIlRZtJPxfoESMmXMqEtZWQ-VytgJp4sQFT_6sta_LMldT6wiCai5wMPKO51iKHYUYHB2ggRRr7Lp9JOprTRmBWdOVYX0povfDgWDrIgBuO1BVXhTpBin2BpjwxvdknZkzv-wiZJRpAMuXfazNM1cg80ggNbNP313yY3ptY7jBR_TjM1--LbzSzTY9IpC5RPwcg-OQB1nixO3U-KP4e4LhLrGi0i4F2y-R3QagopY8DelDotI="

# Topilgan xabarlar yuboriladigan guruh ID
PERSONAL_GROUP_ID = -1003267783623

logging.basicConfig(level=logging.ERROR)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# --- DATABASE ---
def init_db():
    with sqlite3.connect('bot_data.db') as conn:
        c = conn.cursor()
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE)')
        c.execute('CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY, group_id INTEGER UNIQUE, group_name TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT)')
        conn.commit()

def db_query(query, params=(), fetch=False):
    with sqlite3.connect('bot_data.db') as conn:
        c = conn.cursor()
        c.execute(query, params)
        if fetch: return c.fetchall()
        conn.commit()
        return None

# --- KEYBOARDS ---
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Kalit so'zlar", callback_data='keyword_menu')],
        [InlineKeyboardButton(text="📡 Izlovchi guruhlar", callback_data='search_group_menu')],
        [InlineKeyboardButton(text="⚙️ Tizim holati", callback_data='check_status')]
    ])

def sub_menu(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qo'shish", callback_data=f'add_{prefix}')],
        [InlineKeyboardButton(text="📋 Ro'yxat", callback_data=f'view_{prefix}')],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f'del_menu_{prefix}')],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data='back_main')]
    ])

# Oddiy foydalanuvchilar uchun "Dasturchiga bog'lanish" tugmasi
def contact_dev_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💻 Dasturchiga bog'lanish", url=f"tg://user?id={DEV_ID}")]
    ])

# --- USERBOT HANDLER ---
@client.on(events.NewMessage)
async def handle_new_message(event):
    try:
        s_groups = [g[0] for g in db_query("SELECT group_id FROM search_groups", fetch=True)]
        if event.chat_id not in s_groups: return
        
        keywords = [k[0] for k in db_query("SELECT keyword FROM keywords", fetch=True)]
        text = event.message.message
        if not text: return
        
        found = [kw for kw in keywords if kw.lower() in text.lower()]
        if found:
            sender = await event.get_sender()
            chat = await event.get_chat()
            g_name = html.escape(getattr(chat, 'title', 'Guruh'))
            s_name = html.escape(f"{getattr(sender, 'first_name', '')} {getattr(sender, 'last_name', '')}".strip() or "User")
            p_url = f"https://t.me/{sender.username}" if getattr(sender, 'username', None) else f"tg://user?id={sender.id}"
            
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👤 Profil", url=p_url)]])
            report = f"🔍 <b>Topildi:</b> {', '.join(found)}\n<b>📍 Guruh:</b> {g_name}\n<b>👤 User:</b> {s_name}\n\n<b>📝 Xabar:</b>\n<i>{html.escape(text[:800])}</i>"
            await bot.send_message(chat_id=PERSONAL_GROUP_ID, text=report, reply_markup=kb, parse_mode="HTML")
    except: pass

# --- BOT HANDLERS ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id in ADMIN_LIST:
        await message.answer("🤖 <b>Asosiy boshqaruv menyusi:</b>", reply_markup=main_menu(), parse_mode="HTML")
    else:
        await message.answer(
            "⚠️ <b>Ushbu botdan faqat adminlar foydalana oladi!</b>\n"
            "Botdan foydalanish huquqini olish uchun dasturchiga murojaat qiling.", 
            reply_markup=contact_dev_kb(), 
            parse_mode="HTML"
        )

@dp.callback_query(F.data == "back_main")
async def back_main(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_LIST: return
    db_query("DELETE FROM user_state WHERE user_id=?", (callback.from_user.id,))
    await callback.message.edit_text("🤖 <b>Asosiy boshqaruv menyusi:</b>", reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query(F.data.in_({"keyword_menu", "search_group_menu"}))
async def show_menus(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_LIST: return
    prefix = callback.data.replace("_menu", "")
    await callback.message.edit_text(f"<b>{prefix.capitalize()} boshqaruv bo'limi:</b>", reply_markup=sub_menu(prefix), parse_mode="HTML")

@dp.callback_query(F.data.startswith("add_"))
async def add_start(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_LIST: return
    prefix = callback.data.replace("add_", "")
    db_query("REPLACE INTO user_state VALUES (?, ?, ?)", (callback.from_user.id, f"wait_{prefix}", ""))
    txt = "📝 Kalit so'zlarni vergul bilan yuboring:" if prefix == "keyword" else "📡 Guruh havolalarini yuboring (@guruh yoki t.me/guruh):"
    await callback.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data=f'{prefix}_menu')]]))

async def process_groups(message, links):
    success, failed = 0, []
    total = len(links)
    status_msg = await message.answer(f"⏳ Jarayon boshlandi: 0/{total}")

    for i, link in enumerate(links):
        try:
            # Havolani tozalash (post ID va keraksiz belgilardan)
            clean_link = re.sub(r'/\d+$', '', link.strip().replace("https://t.me/", "").replace("@", ""))
            entity = await client.get_entity(clean_link)
            
            # Guruhga qo'shilish
            await client(functions.channels.JoinChannelRequest(channel=entity))
            
            # ID formatini to'g'rilash
            eid = entity.id if str(entity.id).startswith("-100") else int(f"-100{entity.id}")
            db_query("INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", (eid, entity.title))
            success += 1
        except Exception as e:
            failed.append(f"{link} ({str(e)})")

        # Har bir guruhdan so'ng 5 soniya kutish (Conflict va Flood oldini olish uchun)
        await asyncio.sleep(5)
        try:
            await status_msg.edit_text(f"📊 Jarayon: {i+1}/{total}\n✅ Qo'shildi: {success}\n❌ Xato: {len(failed)}")
        except: pass
            
    final = f"🏁 <b>Jarayon yakunlandi!</b>\n\n✅ Muvaffaqiyatli: {success}\n❌ Xato: {len(failed)}"
    if failed: final += "\n\n<b>Xatoliklar ro'yxati:</b>\n" + "\n".join(failed[:5])
    await message.answer(final, reply_markup=sub_menu("search_group"), parse_mode="HTML")

@dp.message(F.text)
async def handle_input(message: types.Message):
    if message.from_user.id not in ADMIN_LIST: return
    state_res = db_query("SELECT state FROM user_state WHERE user_id=?", (message.from_user.id,), fetch=True)
    if not state_res: return
    state = state_res[0][0]

    if state == "wait_keyword":
        kws = [k.strip() for k in message.text.split(",") if k.strip()]
        for k in kws: db_query("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (k,))
        await message.answer(f"✅ {len(kws)} ta so'z saqlandi.", reply_markup=sub_menu("keyword"))
        db_query("DELETE FROM user_state WHERE user_id=?", (message.from_user.id,))
    
    elif state == "wait_search_group":
        links = re.findall(r'(?:https?://)?t\.me/[a-zA-Z0-9_]{4,}|@[a-zA-Z0-9_]{4,}', message.text)
        if not links:
            return await message.answer("❌ Yaroqli havola topilmadi! Iltimos, @guruh yoki t.me/guruh ko'rinishida yuboring.")
        db_query("DELETE FROM user_state WHERE user_id=?", (message.from_user.id,))
        asyncio.create_task(process_groups(message, links))

@dp.callback_query(F.data == "check_status")
async def check_status(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_LIST: return
    try:
        me = await client.get_me()
        k_count = db_query("SELECT COUNT(*) FROM keywords", fetch=True)[0][0]
        g_count = db_query("SELECT COUNT(*) FROM search_groups", fetch=True)[0][0]
        txt = f"⚙️ <b>Tizim holati:</b>\n👤 Userbot: @{me.username}\n🔑 So'zlar: {k_count}\n📡 Guruhlar: {g_count}"
        await callback.message.edit_text(txt, reply_markup=main_menu(), parse_mode="HTML")
    except:
        await callback.answer("Userbot bilan aloqa yo'q!")

async def main():
    init_db()
    # Railway'da conflict bo'lmasligi uchun pollingni tozalash
    await bot.delete_webhook(drop_pending_updates=True)
    await client.start()
    print("Bot va Userbot Railway'da muvaffaqiyatli ishga tushdi...")
    await asyncio.gather(dp.start_polling(bot), client.run_until_disconnected())

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
