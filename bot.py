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
ADMIN_LIST = {7664337104, 7740552653}  # Set for O(1) lookup
DEV_ID = 7740552653
API_ID = 31654640
API_HASH = "22e66db2dba07587217d2f308ae412fb"
SESSION_STRING = "1ApWapzMBu4E9Kp6_zhIWbAr9GndIqukjWw51smf1l9CXbEviZSSGZCg3RzqIS4HCEigBsBvup0b6iPctHFcigaO_p70kKhrJ2Qkza5Ua2bqcJbFIlRZtJPxfoESMmXMqEtZWQ-VytgJp4sQFT_6sta_LMldT6wiCai5wMPKO51iKHYUYHB2ggRRr7Lp9JOprTRmBWdOVYX0povfDgWDrIgBuO1BVXhTpBin2BpjwxvdknZkzv-wiZJRpAMuXfazNM1cg80ggNbNP313yY3ptY7jBR_TjM1--LbzSzTY9IpC5RPwcg-OQB1nixO3U-KP4e4LhLrGi0i4F2y-R3QagopY8DelDotI="
PERSONAL_GROUP_ID = -1003267783623
DB_PATH = 'bot_data.db'

# Logging optimizatsiyasi
logging.basicConfig(
    level=logging.WARNING,  # INFO o'rniga WARNING (kamroq log)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot va Client optimizatsiya bilan
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

# Thread pool executor for blocking operations
executor = ThreadPoolExecutor(max_workers=4)

# In-memory cache
class Cache:
    def __init__(self):
        self.keywords: set = set()
        self.groups: set = set()
        self.user_states: dict = {}
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
            
            async with db.execute(query, params) as cursor:
                if fetch:
                    return await cursor.fetchall()
            await db.commit()
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
    
    # Index qo'shish - tezlik uchun
    await db_execute('CREATE INDEX IF NOT EXISTS idx_keyword ON keywords(keyword)')
    await db_execute('CREATE INDEX IF NOT EXISTS idx_group_id ON search_groups(group_id)')
    
    # Cache yuklash
    await cache.load_from_db()

# --- ASOSIY MENYU ---
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

# --- USERBOT OPTIMIZATSIYA (IN-MEMORY CACHE) ---
@client.on(events.NewMessage(incoming=True))
async def watcher(event):
    """Xabarlarni kuzatish - maksimal tezlik"""
    try:
        # Guruh tekshiruvi (O(1) - set ishlatilgan)
        if event.chat_id not in cache.groups:
            return
        
        text = event.message.message
        if not text or len(text) < 3:  # Juda qisqa xabarlarni o'tkazib yuborish
            return
        
        text_lower = text.lower()
        
        # Kalit so'zlarni tekshirish (O(n) lekin set bo'yicha tez)
        found = [w for w in cache.keywords if w in text_lower]
        
        if not found:
            return
        
        # Asinxron ravishda ma'lumot olish va yuborish
        sender, chat = await asyncio.gather(
            event.get_sender(),
            event.get_chat()
        )
        
        # Profile link
        p_link = (f"https://t.me/{sender.username}" 
                  if getattr(sender, 'username', None) 
                  else f"tg://user?id={sender.id}")
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Profil", url=p_link)]
        ])
        
        # Xabarni qisqartirish
        truncated_text = text[:500] + "..." if len(text) > 500 else text
        
        msg = (
            f"🔍 <b>Topildi:</b> {', '.join(found[:5])}\n"  # Maksimal 5 ta kalit so'z
            f"<b>📍 Guruh:</b> {html.escape(getattr(chat, 'title', 'Guruh')[:50])}\n\n"
            f"<b>📝 Xabar:</b>\n<i>{html.escape(truncated_text)}</i>"
        )
        
        # Fire-and-forget - javobni kutmasdan yuborish
        asyncio.create_task(
            bot.send_message(PERSONAL_GROUP_ID, msg, reply_markup=kb, parse_mode="HTML")
        )
        
    except Exception as e:
        logger.error(f"Watcher error: {e}")

# --- HANDLERLAR ---
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

# --- O'CHIRISH (CACHE BILAN) ---
@dp.callback_query(F.data == "del_kw")
async def del_keywords(c: types.CallbackQuery):
    data = await db_execute("SELECT id, keyword FROM keywords", fetch=True)
    
    if not data:
        await c.answer("❌ Kalit so'zlar ro'yxati bo'sh!", show_alert=True)
        return
    
    kb = [[InlineKeyboardButton(text=f"❌ {kw}", callback_data=f"remove_kw_{id}")] 
          for id, kw in data[:50]]  # Maksimal 50 ta ko'rsatish
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data='open_keywords')])
    
    await c.message.edit_text(
        "🗑 <b>O'chiriladigan kalit so'zni tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await c.answer()

@dp.callback_query(F.data == "del_gr")
async def del_groups(c: types.CallbackQuery):
    data = await db_execute("SELECT id, group_name FROM search_groups", fetch=True)
    
    if not data:
        await c.answer("❌ Guruhlar ro'yxati bo'sh!", show_alert=True)
        return
    
    kb = [[InlineKeyboardButton(text=f"❌ {name[:30]}", callback_data=f"remove_gr_{id}")] 
          for id, name in data[:50]]
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data='open_groups')])
    
    await c.message.edit_text(
        "🗑 <b>O'chiriladigan guruhni tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await c.answer()

@dp.callback_query(F.data.startswith("remove_kw_"))
async def remove_keyword(c: types.CallbackQuery):
    item_id = c.data.split("_")[2]
    
    # DBdan o'chirish
    result = await db_execute("DELETE FROM keywords WHERE id=? RETURNING keyword", (item_id,), fetch=True)
    
    if result:
        # Cache'dan o'chirish
        cache.keywords.discard(result[0][0].lower())
        await c.answer("✅ Kalit so'z o'chirildi!", show_alert=True)
    
    # Yangilangan ro'yxat
    data = await db_execute("SELECT id, keyword FROM keywords", fetch=True)
    
    if not data:
        await c.message.edit_text(
            "🔑 <b>Kalit so'zlar bo'limi:</b>\n\n✅ Barcha so'zlar o'chirildi!",
            reply_markup=sub_kb('kw'),
            parse_mode="HTML"
        )
        return
    
    kb = [[InlineKeyboardButton(text=f"❌ {kw}", callback_data=f"remove_kw_{id}")] 
          for id, kw in data[:50]]
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data='open_keywords')])
    
    await c.message.edit_text(
        "🗑 <b>O'chiriladigan kalit so'zni tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("remove_gr_"))
async def remove_group(c: types.CallbackQuery):
    item_id = c.data.split("_")[2]
    
    # Guruh ma'lumotini olish
    res = await db_execute("SELECT group_id FROM search_groups WHERE id=?", (item_id,), fetch=True)
    
    if res:
        try:
            # Asinxron ravishda guruhdan chiqish
            await client(functions.channels.LeaveChannelRequest(channel=res[0][0]))
        except:
            pass
        
        # DBdan o'chirish
        await db_execute("DELETE FROM search_groups WHERE id=?", (item_id,))
        
        # Cache'dan o'chirish
        cache.groups.discard(res[0][0])
    
    await c.answer("✅ Guruh o'chirildi!", show_alert=True)
    
    # Yangilangan ro'yxat
    data = await db_execute("SELECT id, group_name FROM search_groups", fetch=True)
    
    if not data:
        await c.message.edit_text(
            "📡 <b>Izlovchi guruhlar bo'limi:</b>\n\n✅ Barcha guruhlar o'chirildi!",
            reply_markup=sub_kb('gr'),
            parse_mode="HTML"
        )
        return
    
    kb = [[InlineKeyboardButton(text=f"❌ {name[:30]}", callback_data=f"remove_gr_{id}")] 
          for id, name in data[:50]]
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data='open_groups')])
    
    await c.message.edit_text(
        "🗑 <b>O'chiriladigan guruhni tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )

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

# --- TEXT HANDLER (BATCH INSERT) ---
@dp.message(F.text)
async def text_handler(m: types.Message):
    if m.from_user.id not in ADMIN_LIST:
        return
    
    state = cache.user_states.get(m.from_user.id)
    if not state:
        return
    
    st = state.get("state")
    
    # --- KALIT SO'Z QO'SHISH (BATCH) ---
    if st == "adding_kw":
        words = [w.strip().lower() for w in m.text.split(",") if w.strip()]
        
        if not words:
            await m.answer("❌ Kalit so'z topilmadi!")
            return
        
        # Batch insert
        added = 0
        async with aiosqlite.connect(DB_PATH) as db:
            for w in words:
                try:
                    await db.execute("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (w,))
                    cache.keywords.add(w)  # Cache'ga qo'shish
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
    
    # --- GURUH QO'SHISH (PARALLEL) ---
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
                
                # Cache'ga qo'shish
                cache.groups.add(gid)
                success_count += 1
                
                await asyncio.sleep(0.5)  # Flood kutish
                
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

# --- KO'RISH ---
@dp.callback_query(F.data == "view_kw")
async def view_keywords(c: types.CallbackQuery):
    data = await db_execute("SELECT keyword FROM keywords LIMIT 100", fetch=True)
    
    txt = "📋 <b>Kalit so'zlar ro'yxati:</b>\n\n"
    
    if data:
        txt += "\n".join([f"• {kw[0]}" for kw in data])
        if len(data) == 100:
            txt += f"\n\n<i>... va yana {len(cache.keywords) - 100} ta</i>"
    else:
        txt += "❌ Ro'yxat bo'sh"
    
    await c.message.edit_text(txt, reply_markup=sub_kb('kw'), parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data == "view_gr")
async def view_groups(c: types.CallbackQuery):
    data = await db_execute("SELECT group_name, group_id FROM search_groups LIMIT 50", fetch=True)
    
    txt = "📋 <b>Izlovchi guruhlar:</b>\n\n"
    
    if data:
        for name, gid in data:
            txt += f"• {name[:40]}\n"
        if len(data) == 50:
            txt += f"\n<i>... va yana {len(cache.groups) - 50} ta</i>"
    else:
        txt += "❌ Ro'yxat bo'sh"
    
    await c.message.edit_text(txt, reply_markup=sub_kb('gr'), parse_mode="HTML")
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

# --- BACKGROUND TASK: CACHE YANGILASH ---
async def cache_updater():
    """Har 5 daqiqada cache'ni yangilash"""
    while True:
        try:
            await asyncio.sleep(300)  # 5 daqiqa
            await cache.load_from_db()
            logger.info("Cache updated")
        except Exception as e:
            logger.error(f"Cache update error: {e}")

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await client.start()
    
    # Background task ishga tushirish
    asyncio.create_task(cache_updater())
    
    logger.info("✅ Bot va Userbot maksimal tezlikda ishga tushdi!")
    
    await asyncio.gather(
        dp.start_polling(bot),
        client.run_until_disconnected()
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n❌ Bot to'xtatildi")
