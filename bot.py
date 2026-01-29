import asyncio
import sqlite3
import logging
from typing import List, Tuple, Optional
import html
import re
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.session.aiohttp import AiohttpSession
from concurrent.futures import ThreadPoolExecutor
import aiosqlite

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8137576363:AAHerJWL_b4kgQsTY03_Dt6sLuPny-BlZ8g"
ADMIN_LIST = {7664337104, 7740552653}
DEV_ID = 7740552653
API_ID = 31654640
API_HASH = "22e66db2dba07587217d2f308ae412fb"
SESSION_STRING = "1ApWapzMBu4E9Kp6_zhIWbAr9GndIqukjWw51smf1l9CXbEviZSSGZCg3RzqIS4HCEigBsBvup0b6iPctHFcigaO_p70kKhrJ2Qkza5Ua2bqcJbFIlRZtJPxfoESMmXMqEtZWQ-VytgJp4sQFT_6sta_LMldT6wiCai5wMPKO51iKHYUYHB2ggRRr7Lp9JOprTRmBWdOVYX0povfDgWDrIgBuO1BVXhTpBin2BpjwxvdknZkzv-wiZJRpAMuXfazNM1cg80ggNbNP313yY3ptY7jBR_TjM1--LbzSzTY9IpC5RPwcg-OQB1nixO3U-KP4e4LhLrGi0i4F2y-R3QagopY8DelDotI="
PERSONAL_GROUP_ID = -1003267783623
DB_PATH = 'bot_data.db'

# Logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot va Client
session = AiohttpSession()
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()
client = TelegramClient(
    StringSession(SESSION_STRING), 
    API_ID, 
    API_HASH,
    connection_retries=5,
    retry_delay=1,
    flood_sleep_threshold=60
)

executor = ThreadPoolExecutor(max_workers=4)

# In-memory cache
class Cache:
    def __init__(self):
        self.keywords: set = set()
        self.groups: set = set()
        self.user_states: dict = {}
        self.pagination: dict = {}  # Sahifalash uchun
        self.last_update: float = 0
        
    async def load_from_db(self):
        """Ma'lumotlarni DBdan xotiraga yuklash"""
        async with aiosqlite.connect(DB_PATH) as db:
            # Keywords
            async with db.execute("SELECT keyword FROM keywords") as cursor:
                self.keywords = {row[0].lower() for row in await cursor.fetchall()}
            
            # Groups
            async with db.execute("SELECT group_id FROM search_groups") as cursor:
                self.groups = {row[0] for row in await cursor.fetchall()}
        
        self.last_update = asyncio.get_event_loop().time()
        logger.info(f"Cache loaded: {len(self.keywords)} keywords, {len(self.groups)} groups")

cache = Cache()

# --- ASINXRON DB OPERATSIYALARI ---
async def db_execute(query: str, params: tuple = (), fetch: bool = False):
    """Asinxron DB operatsiyasi"""
    try:
        async with aiosqlite.connect(DB_PATH, timeout=30) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            await db.execute('PRAGMA synchronous=NORMAL')
            await db.execute('PRAGMA cache_size=10000')
            await db.execute('PRAGMA temp_store=MEMORY')
            
            if fetch:
                async with db.execute(query, params) as cursor:
                    return await cursor.fetchall()
            else:
                await db.execute(query, params)
                await db.commit()
                return None
    except Exception as e:
        logger.error(f"DB error: {e}")
        return None

async def init_db():
    """DB yaratish"""
    await db_execute('''CREATE TABLE IF NOT EXISTS keywords 
                       (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        keyword TEXT UNIQUE COLLATE NOCASE)''')
    await db_execute('''CREATE TABLE IF NOT EXISTS search_groups 
                       (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        group_id INTEGER UNIQUE, 
                        group_name TEXT)''')
    await db_execute('''CREATE TABLE IF NOT EXISTS user_state 
                       (user_id INTEGER PRIMARY KEY, 
                        state TEXT, 
                        data TEXT)''')
    
    # Index qo'shish
    await db_execute('CREATE INDEX IF NOT EXISTS idx_keyword ON keywords(keyword)')
    await db_execute('CREATE INDEX IF NOT EXISTS idx_group_id ON search_groups(group_id)')
    
    # Cache yuklash
    await cache.load_from_db()

# --- KEYBOARD FUNKSIYALARI ---
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

def pagination_kb(mode, page, total_pages):
    """Sahifalash klaviaturasi"""
    buttons = []
    
    # Navigatsiya tugmalari
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f'page_{mode}_{page-1}'))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f'page_{mode}_{page+1}'))
    
    if nav_row:
        buttons.append(nav_row)
    
    # Sahifa raqami
    buttons.append([InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data='noop')])
    
    # Orqaga tugmasi
    back_action = 'open_keywords' if mode.startswith('kw') else 'open_groups'
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_action)])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- USERBOT ---
@client.on(events.NewMessage(incoming=True))
async def watcher(event):
    """Xabarlarni kuzatish"""
    try:
        if event.chat_id not in cache.groups:
            return
        
        text = event.message.message
        if not text or len(text) < 3:
            return
        
        text_lower = text.lower()
        found = [w for w in cache.keywords if w in text_lower]
        
        if not found:
            return
        
        sender, chat = await asyncio.gather(
            event.get_sender(),
            event.get_chat()
        )
        
        p_link = (f"https://t.me/{sender.username}" 
                  if getattr(sender, 'username', None) 
                  else f"tg://user?id={sender.id}")
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Profil", url=p_link)]
        ])
        
        truncated_text = text[:500] + "..." if len(text) > 500 else text
        
        msg = (
            f"🔍 <b>Topildi:</b> {', '.join(found[:5])}\n"
            f"<b>📍 Guruh:</b> {html.escape(getattr(chat, 'title', 'Guruh')[:50])}\n\n"
            f"<b>📝 Xabar:</b>\n<i>{html.escape(truncated_text)}</i>"
        )
        
        asyncio.create_task(
            bot.send_message(PERSONAL_GROUP_ID, msg, reply_markup=kb, parse_mode="HTML")
        )
        
    except Exception as e:
        logger.error(f"Watcher error: {e}")

# --- ASOSIY HANDLERLAR ---
@dp.message(Command("start"))
async def start(m: types.Message):
    if m.from_user.id not in ADMIN_LIST:
        return
    
    cache.user_states.pop(m.from_user.id, None)
    await m.answer("🤖 <b>Boshqaruv paneli:</b>", reply_markup=main_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "main_home")
async def go_home(c: types.CallbackQuery):
    cache.user_states.pop(c.from_user.id, None)
    await c.message.edit_text("🤖 <b>Boshqaruv paneli:</b>", reply_markup=main_kb(), parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data == "open_keywords")
async def open_kw(c: types.CallbackQuery):
    cache.user_states.pop(c.from_user.id, None)
    await c.message.edit_text("🔑 <b>Kalit so'zlar bo'limi:</b>", reply_markup=sub_kb('kw'), parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data == "open_groups")
async def open_gr(c: types.CallbackQuery):
    cache.user_states.pop(c.from_user.id, None)
    await c.message.edit_text("📡 <b>Izlovchi guruhlar bo'limi:</b>", reply_markup=sub_kb('gr'), parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data == "noop")
async def noop(c: types.CallbackQuery):
    await c.answer()

# --- O'CHIRISH (TUZATILGAN) ---
@dp.callback_query(F.data == "del_kw")
async def del_keywords(c: types.CallbackQuery):
    data = await db_execute("SELECT id, keyword FROM keywords ORDER BY keyword", fetch=True)
    
    if not data:
        await c.answer("❌ Kalit so'zlar ro'yxati bo'sh!", show_alert=True)
        return
    
    # Sahifalash
    cache.pagination[c.from_user.id] = {'mode': 'del_kw', 'data': data}
    await show_delete_page(c.message, data, 'kw', 0)
    await c.answer()

@dp.callback_query(F.data == "del_gr")
async def del_groups(c: types.CallbackQuery):
    data = await db_execute("SELECT id, group_name FROM search_groups ORDER BY group_name", fetch=True)
    
    if not data:
        await c.answer("❌ Guruhlar ro'yxati bo'sh!", show_alert=True)
        return
    
    cache.pagination[c.from_user.id] = {'mode': 'del_gr', 'data': data}
    await show_delete_page(c.message, data, 'gr', 0)
    await c.answer()

async def show_delete_page(message, data, mode, page):
    """O'chirish ro'yxatini sahifalab ko'rsatish"""
    per_page = 10
    total_pages = (len(data) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    
    kb = []
    for id, name in data[start:end]:
        display_name = name if len(name) <= 30 else name[:27] + "..."
        kb.append([InlineKeyboardButton(
            text=f"❌ {display_name}", 
            callback_data=f"remove_{mode}_{id}_{page}"
        )])
    
    # Navigatsiya
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f'delpage_{mode}_{page-1}'))
    nav_row.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data='noop'))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f'delpage_{mode}_{page+1}'))
    
    kb.append(nav_row)
    
    # Orqaga
    back_action = 'open_keywords' if mode == 'kw' else 'open_groups'
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_action)])
    
    title = "kalit so'z" if mode == 'kw' else "guruh"
    await message.edit_text(
        f"🗑 <b>O'chiriladigan {title}ni tanlang:</b>\n"
        f"📊 Jami: {len(data)} ta",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("delpage_"))
async def handle_delete_pagination(c: types.CallbackQuery):
    """O'chirish sahifalarini almashtirish"""
    parts = c.data.split("_")
    mode = parts[1]
    page = int(parts[2])
    
    pag_data = cache.pagination.get(c.from_user.id)
    if not pag_data:
        await c.answer("❌ Ma'lumot topilmadi!", show_alert=True)
        return
    
    await show_delete_page(c.message, pag_data['data'], mode, page)
    await c.answer()

@dp.callback_query(F.data.startswith("remove_kw_"))
async def remove_keyword(c: types.CallbackQuery):
    parts = c.data.split("_")
    item_id = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0
    
    # DBdan o'chirish
    result = await db_execute("SELECT keyword FROM keywords WHERE id=?", (item_id,), fetch=True)
    
    if result:
        await db_execute("DELETE FROM keywords WHERE id=?", (item_id,))
        cache.keywords.discard(result[0][0].lower())
        await c.answer("✅ Kalit so'z o'chirildi!", show_alert=True)
    
    # Yangilangan ro'yxat
    data = await db_execute("SELECT id, keyword FROM keywords ORDER BY keyword", fetch=True)
    
    if not data:
        await c.message.edit_text(
            "🔑 <b>Kalit so'zlar bo'limi:</b>\n\n✅ Barcha so'zlar o'chirildi!",
            reply_markup=sub_kb('kw'),
            parse_mode="HTML"
        )
        cache.pagination.pop(c.from_user.id, None)
        return
    
    # Sahifani yangilash
    per_page = 10
    total_pages = (len(data) + per_page - 1) // per_page
    if page >= total_pages:
        page = total_pages - 1
    
    cache.pagination[c.from_user.id] = {'mode': 'del_kw', 'data': data}
    await show_delete_page(c.message, data, 'kw', page)

@dp.callback_query(F.data.startswith("remove_gr_"))
async def remove_group(c: types.CallbackQuery):
    parts = c.data.split("_")
    item_id = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0
    
    # Guruh ma'lumotini olish
    res = await db_execute("SELECT group_id FROM search_groups WHERE id=?", (item_id,), fetch=True)
    
    if res:
        try:
            await client(functions.channels.LeaveChannelRequest(channel=res[0][0]))
        except:
            pass
        
        await db_execute("DELETE FROM search_groups WHERE id=?", (item_id,))
        cache.groups.discard(res[0][0])
        await c.answer("✅ Guruh o'chirildi!", show_alert=True)
    
    # Yangilangan ro'yxat
    data = await db_execute("SELECT id, group_name FROM search_groups ORDER BY group_name", fetch=True)
    
    if not data:
        await c.message.edit_text(
            "📡 <b>Izlovchi guruhlar bo'limi:</b>\n\n✅ Barcha guruhlar o'chirildi!",
            reply_markup=sub_kb('gr'),
            parse_mode="HTML"
        )
        cache.pagination.pop(c.from_user.id, None)
        return
    
    # Sahifani yangilash
    per_page = 10
    total_pages = (len(data) + per_page - 1) // per_page
    if page >= total_pages:
        page = total_pages - 1
    
    cache.pagination[c.from_user.id] = {'mode': 'del_gr', 'data': data}
    await show_delete_page(c.message, data, 'gr', page)

# --- QO'SHISH ---
@dp.callback_query(F.data == "add_kw")
async def add_keywords(c: types.CallbackQuery):
    cache.user_states[c.from_user.id] = {"state": "adding_kw"}
    
    await c.message.edit_text(
        "📝 <b>Kalit so'zlarni yuboring:</b>\n\n"
        "• Bir nechta so'z uchun vergul bilan ajrating\n"
        "• Masalan: <code>python, dasturlash, AI</code>\n\n"
        "✅ Istalgancha so'z qo'shishingiz mumkin",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Yakunlash", callback_data='open_keywords')]
        ]),
        parse_mode="HTML"
    )
    await c.answer()

@dp.callback_query(F.data == "add_gr")
async def add_groups(c: types.CallbackQuery):
    cache.user_states[c.from_user.id] = {"state": "adding_gr"}
    
    await c.message.edit_text(
        "📡 <b>Guruh linkini yuboring:</b>\n\n"
        "• Masalan: <code>@guruh_nomi</code>\n"
        "• Yoki: <code>https://t.me/guruh_nomi</code>\n\n"
        "✅ Istalgancha guruh qo'shishingiz mumkin",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Yakunlash", callback_data='open_groups')]
        ]),
        parse_mode="HTML"
    )
    await c.answer()

# --- TEXT HANDLER ---
@dp.message(F.text)
async def text_handler(m: types.Message):
    if m.from_user.id not in ADMIN_LIST:
        return
    
    state = cache.user_states.get(m.from_user.id)
    if not state:
        return
    
    st = state.get("state")
    
    if st == "adding_kw":
        words = [w.strip().lower() for w in m.text.split(",") if w.strip()]
        
        if not words:
            await m.answer("❌ Kalit so'z topilmadi!")
            return
        
        added = 0
        async with aiosqlite.connect(DB_PATH) as db:
            for w in words:
                try:
                    await db.execute("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (w,))
                    if w not in cache.keywords:
                        cache.keywords.add(w)
                        added += 1
                except:
                    pass
            await db.commit()
        
        await m.answer(
            f"✅ <b>{added} ta kalit so'z qo'shildi!</b>\n\n"
            f"Yana yuboring yoki 'Yakunlash'ni bosing.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Yakunlash", callback_data='open_keywords')]
            ]),
            parse_mode="HTML"
        )
    
    elif st == "adding_gr":
        links = re.findall(r'(?:https?://)?t\.me/[a-zA-Z0-9_]{4,}|@[a-zA-Z0-9_]{4,}', m.text)
        
        if not links:
            await m.answer("❌ <b>Havola noto'g'ri!</b>", parse_mode="HTML")
            return
        
        status_msg = await m.answer(f"⏳ <b>{len(links)} ta guruhga qo'shilmoqda...</b>", parse_mode="HTML")
        
        success_count = 0
        
        for link in links:
            try:
                clean = re.sub(r'/\d+$', '', link.strip().replace("https://t.me/", "").replace("@", ""))
                ent = await client.get_entity(clean)
                await client(functions.channels.JoinChannelRequest(channel=ent))
                
                gid = ent.id if str(ent.id).startswith("-100") else int(f"-100{ent.id}")
                
                await db_execute(
                    "INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", 
                    (gid, ent.title)
                )
                
                cache.groups.add(gid)
                success_count += 1
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Group add error: {e}")
        
        await status_msg.edit_text(
            f"✅ <b>{success_count}/{len(links)} guruh qo'shildi!</b>\n\n"
            f"Yana qo'shish uchun havola yuboring.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Yakunlash", callback_data='open_groups')]
            ]),
            parse_mode="HTML"
        )

# --- KO'RISH (SAHIFALASH BILAN) ---
@dp.callback_query(F.data == "view_kw")
async def view_keywords(c: types.CallbackQuery):
    data = await db_execute("SELECT keyword FROM keywords ORDER BY keyword", fetch=True)
    
    if not data:
        await c.message.edit_text(
            "📋 <b>Kalit so'zlar ro'yxati:</b>\n\n❌ Ro'yxat bo'sh",
            reply_markup=sub_kb('kw'),
            parse_mode="HTML"
        )
        await c.answer()
        return
    
    cache.pagination[c.from_user.id] = {'mode': 'view_kw', 'data': data}
    await show_view_page(c.message, data, 'kw', 0)
    await c.answer()

@dp.callback_query(F.data == "view_gr")
async def view_groups(c: types.CallbackQuery):
    data = await db_execute("SELECT group_name, group_id FROM search_groups ORDER BY group_name", fetch=True)
    
    if not data:
        await c.message.edit_text(
            "📋 <b>Izlovchi guruhlar:</b>\n\n❌ Ro'yxat bo'sh",
            reply_markup=sub_kb('gr'),
            parse_mode="HTML"
        )
        await c.answer()
        return
    
    cache.pagination[c.from_user.id] = {'mode': 'view_gr', 'data': data}
    await show_view_page(c.message, data, 'gr', 0)
    await c.answer()

async def show_view_page(message, data, mode, page):
    """Ko'rish ro'yxatini sahifalab ko'rsatish"""
    per_page = 20
    total_pages = (len(data) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    
    if mode == 'kw':
        txt = f"📋 <b>Kalit so'zlar ro'yxati:</b>\n"
        txt += f"📊 Jami: {len(data)} ta\n"
        txt += f"📄 Sahifa: {page+1}/{total_pages}\n\n"
        txt += "\n".join([f"{start+i+1}. {kw[0]}" for i, kw in enumerate(data[start:end])])
    else:
        txt = f"📋 <b>Izlovchi guruhlar:</b>\n"
        txt += f"📊 Jami: {len(data)} ta\n"
        txt += f"📄 Sahifa: {page+1}/{total_pages}\n\n"
        txt += "\n".join([f"{start+i+1}. {name[0]}" for i, name in enumerate(data[start:end])])
    
    kb = pagination_kb(f'view_{mode}', page, total_pages)
    await message.edit_text(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("page_view_"))
async def handle_view_pagination(c: types.CallbackQuery):
    """Ko'rish sahifalarini almashtirish"""
    parts = c.data.split("_")
    mode = parts[2]
    page = int(parts[3])
    
    pag_data = cache.pagination.get(c.from_user.id)
    if not pag_data:
        await c.answer("❌ Ma'lumot topilmadi!", show_alert=True)
        return
    
    await show_view_page(c.message, pag_data['data'], mode, page)
    await c.answer()

# --- STATUS ---
@dp.callback_query(F.data == "sys_status")
async def sys_status(c: types.CallbackQuery):
    try:
        me = await client.get_me()
        
        txt = (
            f"⚙️ <b>Tizim holati:</b>\n\n"
            f"👤 Userbot: @{me.username}\n"
            f"🔑 Kalit so'zlar: {len(cache.keywords)} ta\n"
            f"📡 Guruhlar: {len(cache.groups)} ta\n"
            f"⚡️ Cache: Faol\n"
            f"✅ Holat: Ishlayapti"
        )
        
        await c.message.edit_text(txt, reply_markup=main_kb(), parse_mode="HTML")
        await c.answer()
    except:
        await c.answer("❌ Userbot ishlamayapti!", show_alert=True)

# --- BACKGROUND TASK ---
async def cache_updater():
    """Har 5 daqiqada cache'ni yangilash"""
    while True:
        try:
            await asyncio.sleep(300)
            await cache.load_from_db()
            logger.info("Cache updated")
        except Exception as e:
            logger.error(f"Cache update error: {e}")

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await client.start()
    
    asyncio.create_task(cache_updater())
    
    logger.info("✅ Bot va Userbot ishga tushdi!")
    
    await asyncio.gather(
        dp.start_polling(bot),
        client.run_until_disconnected()
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n❌ Bot to'xtatildi")
