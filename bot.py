import asyncio
import sqlite3
import logging
import html
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, UserAlreadyParticipant, PeerIdInvalid, ChannelPrivate
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

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

userbot = Client(
    "my_userbot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    session_string=SESSION_STRING.strip(), 
    in_memory=True
)

# Global cache guruhlar uchun
CACHED_GROUPS = set()

# --- DATABASE FUNKSIYALARI ---
async def db_query(query, params=(), fetch=False):
    """Database bilan ishlash uchun xavfsiz funksiya"""
    def _execute():
        try:
            with sqlite3.connect('bot_data.db', timeout=30) as conn:
                conn.execute('PRAGMA journal_mode=WAL')
                cursor = conn.cursor()
                cursor.execute(query, params)
                if fetch:
                    return cursor.fetchall()
                conn.commit()
                return None
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
            return [] if fetch else None
    
    return await asyncio.to_thread(_execute)

# --- USERBOT: GURUHGA QO'SHILISH ---
async def join_chat_logic(link):
    """Guruhga qo'shilish mantiqiy funksiyasi"""
    try:
        # Linkni tozalash
        clean = link.replace("https://t.me/", "").replace("t.me/", "").replace("@", "").strip()
        
        chat = None
        
        # Invite link yoki username tekshirish
        if "joinchat/" in clean or "+" in clean:
            invite_hash = clean.replace("joinchat/", "").replace("+", "")
            try:
                chat = await userbot.join_chat(invite_hash)
                logging.info(f"✅ Guruhga qo'shildi (invite): {chat.title}")
            except UserAlreadyParticipant:
                logging.info("Allaqachon guruh a'zosi (invite link)")
                return None
        else:
            try:
                chat = await userbot.join_chat(clean)
                logging.info(f"✅ Guruhga qo'shildi (username): {chat.title}")
            except UserAlreadyParticipant:
                logging.info("Allaqachon guruh a'zosi, ma'lumot olinmoqda...")
                chat = await userbot.get_chat(clean)
        
        # Cache ga qo'shish
        if chat:
            CACHED_GROUPS.add(chat.id)
            await asyncio.sleep(1)
        
        return chat
        
    except FloodWait as e:
        logging.warning(f"⏳ FloodWait: {e.value} soniya kutilmoqda...")
        await asyncio.sleep(e.value)
        return await join_chat_logic(link)
    
    except ChannelPrivate:
        logging.error("❌ Guruh privat yoki ban qilingan")
        return None
    
    except PeerIdInvalid:
        logging.error("❌ Peer ID noto'g'ri")
        return None
    
    except Exception as e:
        logging.error(f"❌ Qo'shilishda xatolik: {type(e).__name__}: {e}")
        return None

# --- USERBOT: XABARLARNI KUZATISH ---
@userbot.on_message(filters.group & ~filters.service)
async def message_watcher(client, message):
    """Guruh xabarlarini kuzatish va kalit so'zlarni qidirish"""
    
    # Xabar matnini tekshirish
    if not message.text:
        return
    
    try:
        # 1. Cache dan guruhlarni tekshirish (database ga murojaat qilmasdan)
        if message.chat.id not in CACHED_GROUPS:
            return
        
        # 2. Kalit so'zlarni olish
        res_keywords = await db_query("SELECT keyword FROM keywords", fetch=True)
        if not res_keywords:
            return
        
        keywords = [k[0].lower() for k in res_keywords]
        message_text_lower = message.text.lower()
        
        # 3. Kalit so'zlar topilganmi tekshirish
        found_keywords = [kw for kw in keywords if kw in message_text_lower]
        
        if not found_keywords:
            return
        
        # 4. Xabar ma'lumotlarini to'plash (peer resolution kerak emas!)
        user_name = "Foydalanuvchi"
        user_id = 0
        
        if message.from_user:
            user_name = message.from_user.first_name or "Foydalanuvchi"
            if message.from_user.last_name:
                user_name += f" {message.from_user.last_name}"
            user_id = message.from_user.id
        
        group_title = message.chat.title or "Guruh"
        
        # HTML maxsus belgilarni tozalash
        user_name_safe = html.escape(user_name)
        group_title_safe = html.escape(group_title)
        message_text_safe = html.escape(message.text[:800])
        
        # 5. Hisobot tayyorlash
        report = (
            f"🎯 <b>Yangi xabar topildi!</b>\n\n"
            f"🔑 <b>Kalit so'z:</b> {', '.join(found_keywords)}\n"
            f"👤 <b>Kimdan:</b> {user_name_safe}\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"📍 <b>Guruh:</b> {group_title_safe}\n\n"
            f"📝 <b>Xabar:</b>\n<i>{message_text_safe}</i>"
        )
        
        # 6. Tugmalar yaratish
        keyboard_buttons = []
        
        if user_id > 0:
            keyboard_buttons.append([
                InlineKeyboardButton(text="👤 Profilga o'tish", url=f"tg://user?id={user_id}")
            ])
        
        # Agar guruh username bo'lsa
        if hasattr(message.chat, 'username') and message.chat.username:
            keyboard_buttons.append([
                InlineKeyboardButton(text="📱 Guruhga o'tish", url=f"https://t.me/{message.chat.username}")
            ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons) if keyboard_buttons else None
        
        # 7. Shaxsiy guruhga yuborish
        try:
            await bot.send_message(
                chat_id=PERSONAL_GROUP_ID, 
                text=report, 
                reply_markup=kb, 
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            logging.info(f"✅ Xabar yuborildi: {group_title} | Kalit: {', '.join(found_keywords)}")
        
        except Exception as send_error:
            logging.error(f"❌ Yuborishda xato: {send_error}")
    
    except Exception as e:
        # Xatolarni logga yozish lekin bot ishini to'xtatmaslik
        logging.debug(f"Watcher ichki xato: {type(e).__name__}")

# --- ADMIN PANEL KLAVIATURALARI ---
def main_kb():
    """Asosiy menyu tugmalari"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔑 Kalit so'zlar", callback_data='menu_kw'),
        InlineKeyboardButton(text="📡 Guruhlar", callback_data='menu_gr')
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Holat", callback_data='sys_status')
    )
    return builder.as_markup()

def sub_menu_kb(mode):
    """Ichki menyu tugmalari (kw yoki gr)"""
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

def cancel_kb():
    """Bekor qilish tugmasi"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="home")
    ]])

# --- BOT KOMANDALAR ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Start komandasi - faqat adminlar uchun"""
    if message.from_user.id not in ADMIN_LIST:
        await message.answer("❌ Sizda ruxsat yo'q.")
        return
    
    await message.answer(
        "🤖 <b>Admin Panel</b>\n\n"
        "Xush kelibsiz! Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=main_kb(),
        parse_mode="HTML"
    )

# --- CALLBACK QUERY HANDLERLAR ---
@dp.callback_query(F.data == "home")
async def back_home(callback: types.CallbackQuery):
    """Asosiy menyuga qaytish"""
    await db_query("DELETE FROM user_state WHERE user_id=?", (callback.from_user.id,))
    
    await callback.message.edit_text(
        "🤖 <b>Admin Panel</b>\n\n"
        "Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=main_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.in_({"menu_kw", "menu_gr"}))
async def sub_menu(callback: types.CallbackQuery):
    """Kalit so'zlar yoki Guruhlar menyusi"""
    mode = 'kw' if callback.data == "menu_kw" else 'gr'
    title = "🔑 Kalit so'zlar" if mode == 'kw' else "📡 Guruhlar"
    
    await callback.message.edit_text(
        f"<b>{title} bo'limi</b>\n\n"
        f"Kerakli amalni tanlang:",
        reply_markup=sub_menu_kb(mode),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("add_"))
async def start_add(callback: types.CallbackQuery):
    """Qo'shish jarayonini boshlash"""
    mode = callback.data.split("_")[1]
    state = "adding_kw" if mode == "kw" else "adding_gr"
    
    await db_query(
        "INSERT OR REPLACE INTO user_state (user_id, state) VALUES (?, ?)", 
        (callback.from_user.id, state)
    )
    
    if mode == "kw":
        text = (
            "📝 <b>Kalit so'z qo'shish</b>\n\n"
            "Kalit so'zlarni vergul (,) bilan ajratib yuboring.\n\n"
            "<i>Masalan: olish, sotish, ayirboshlash</i>"
        )
    else:
        text = (
            "📡 <b>Guruh qo'shish</b>\n\n"
            "Guruh linkini yuboring. Userbot avtomatik guruhga qo'shiladi.\n\n"
            "<i>Masalan: https://t.me/example_group</i>"
        )
    
    await callback.message.edit_text(
        text,
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("view_"))
async def view_items(callback: types.CallbackQuery):
    """Ro'yxatni ko'rsatish"""
    mode = callback.data.split("_")[1]
    
    if mode == "kw":
        data = await db_query("SELECT keyword FROM keywords ORDER BY id", fetch=True)
        title = "📋 <b>Kalit so'zlar ro'yxati:</b>\n\n"
    else:
        data = await db_query("SELECT group_name, group_id FROM search_groups ORDER BY id", fetch=True)
        title = "📋 <b>Guruhlar ro'yxati:</b>\n\n"
    
    if not data:
        text = title + "<i>Hozircha bo'sh</i>"
    else:
        items = []
        for i, row in enumerate(data, 1):
            if mode == "kw":
                items.append(f"{i}. {html.escape(row[0])}")
            else:
                items.append(f"{i}. {html.escape(row[0])}\n   ID: <code>{row[1]}</code>")
        
        text = title + "\n".join(items)
    
    await callback.message.edit_text(
        text,
        reply_markup=main_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def delete_menu(callback: types.CallbackQuery):
    """O'chirish menyusi"""
    mode = callback.data.split("_")[1]
    
    if mode == "kw":
        data = await db_query("SELECT id, keyword FROM keywords ORDER BY id", fetch=True)
        title = "🗑 <b>O'chirish uchun kalit so'zni tanlang:</b>"
    else:
        data = await db_query("SELECT id, group_name FROM search_groups ORDER BY id", fetch=True)
        title = "🗑 <b>O'chirish uchun guruhni tanlang:</b>"
    
    if not data:
        await callback.answer("❌ Ro'yxat bo'sh", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    for item_id, name in data:
        builder.row(InlineKeyboardButton(
            text=f"🗑 {name[:40]}",
            callback_data=f"rm_{mode}_{item_id}"
        ))
    
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"menu_{mode}"))
    
    await callback.message.edit_text(
        title,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("rm_"))
async def process_remove(callback: types.CallbackQuery):
    """O'chirish jarayoni"""
    _, mode, item_id = callback.data.split("_")
    
    if mode == "gr":
        # Guruhni cache dan ham o'chirish
        group_data = await db_query(
            "SELECT group_id FROM search_groups WHERE id=?", 
            (item_id,), 
            fetch=True
        )
        if group_data:
            CACHED_GROUPS.discard(group_data[0][0])
    
    table = "keywords" if mode == "kw" else "search_groups"
    await db_query(f"DELETE FROM {table} WHERE id=?", (item_id,))
    
    await callback.answer("✅ O'chirildi", show_alert=False)
    await delete_menu(callback)

@dp.callback_query(F.data == "sys_status")
async def sys_status(callback: types.CallbackQuery):
    """Tizim holati"""
    kw_count = (await db_query("SELECT COUNT(*) FROM keywords", fetch=True))[0][0]
    gr_count = (await db_query("SELECT COUNT(*) FROM search_groups", fetch=True))[0][0]
    
    userbot_status = "✅ Faol" if userbot.is_connected else "❌ O'chiq"
    
    status_text = (
        f"⚙️ <b>Tizim holati</b>\n\n"
        f"🔑 Kalit so'zlar: <b>{kw_count}</b>\n"
        f"📡 Guruhlar: <b>{gr_count}</b>\n"
        f"🤖 Userbot: {userbot_status}\n"
        f"💾 Cache: <b>{len(CACHED_GROUPS)}</b> guruh\n"
        f"📬 Xabar jo'natish: ✅ Faol"
    )
    
    await callback.message.edit_text(
        status_text,
        reply_markup=main_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

# --- MATN XABARLARINI QAYTA ISHLASH ---
@dp.message(F.text)
async def handle_text_messages(message: types.Message):
    """Foydalanuvchi matn xabarlarini qayta ishlash"""
    
    if message.from_user.id not in ADMIN_LIST:
        return
    
    state_result = await db_query(
        "SELECT state FROM user_state WHERE user_id=?", 
        (message.from_user.id,), 
        fetch=True
    )
    
    if not state_result:
        return
    
    state = state_result[0][0]
    
    # --- KALIT SO'Z QO'SHISH ---
    if state == "adding_kw":
        keywords = [kw.strip() for kw in message.text.split(",") if kw.strip()]
        
        if not keywords:
            await message.answer("❌ Kalit so'z topilmadi. Qaytadan urinib ko'ring.")
            return
        
        added_count = 0
        for keyword in keywords:
            try:
                await db_query("INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (keyword,))
                added_count += 1
            except:
                pass
        
        await db_query("DELETE FROM user_state WHERE user_id=?", (message.from_user.id,))
        
        await message.answer(
            f"✅ <b>Qo'shildi!</b>\n\n"
            f"Jami: {len(keywords)} ta kalit so'z",
            reply_markup=main_kb(),
            parse_mode="HTML"
        )
    
    # --- GURUH QO'SHISH ---
    elif state == "adding_gr":
        wait_msg = await message.answer("⏳ Userbot guruhga qo'shilmoqda...")
        
        chat = await join_chat_logic(message.text.strip())
        
        if chat:
            await db_query(
                "INSERT OR IGNORE INTO search_groups (group_id, group_name) VALUES (?, ?)", 
                (chat.id, chat.title)
            )
            
            # Cache ga qo'shish
            CACHED_GROUPS.add(chat.id)
            
            await db_query("DELETE FROM user_state WHERE user_id=?", (message.from_user.id,))
            
            await wait_msg.edit_text(
                f"✅ <b>Guruh qo'shildi!</b>\n\n"
                f"📍 Nomi: {html.escape(chat.title)}\n"
                f"🆔 ID: <code>{chat.id}</code>",
                reply_markup=main_kb(),
                parse_mode="HTML"
            )
        else:
            await wait_msg.edit_text(
                "❌ <b>Xatolik!</b>\n\n"
                "Guruhga qo'shilishda muammo.\n"
                "Link to'g'ri ekanligini tekshiring.",
                reply_markup=main_kb(),
                parse_mode="HTML"
            )
        
        await db_query("DELETE FROM user_state WHERE user_id=?", (message.from_user.id,))

# --- ASOSIY FUNKSIYA ---
async def main():
    """Botni ishga tushirish"""
    
    # Database jadvallarini yaratish
    await db_query('''
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL
        )
    ''')
    
    await db_query('''
        CREATE TABLE IF NOT EXISTS search_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER UNIQUE NOT NULL,
            group_name TEXT
        )
    ''')
    
    await db_query('''
        CREATE TABLE IF NOT EXISTS user_state (
            user_id INTEGER PRIMARY KEY,
            state TEXT NOT NULL
        )
    ''')
    
    logging.info("✅ Database initialized")
    
    try:
        # Userbot ni ishga tushirish
        await userbot.start()
        logging.info("✅ Userbot started successfully")
        
        # Barcha guruhlarni cache ga yuklash
        groups = await db_query("SELECT group_id FROM search_groups", fetch=True)
        
        if groups:
            logging.info(f"📡 Loading {len(groups)} groups into cache...")
            for group_id, in groups:
                CACHED_GROUPS.add(group_id)
            logging.info(f"✅ Cached {len(CACHED_GROUPS)} groups")
        
        # Bot ni ishga tushirish
        await bot.delete_webhook(drop_pending_updates=True)
        
        logging.info("🚀 Sistema muvaffaqiyatli ishga tushdi!")
        logging.info(f"👤 Admins: {ADMIN_LIST}")
        logging.info(f"📬 Personal group: {PERSONAL_GROUP_ID}")
        
        await dp.start_polling(bot)
    
    except Exception as e:
        logging.error(f"❌ CRITICAL: {e}")
        raise
    
    finally:
        logging.info("🛑 Shutting down...")
        if userbot.is_connected:
            await userbot.stop()

# --- ISHGA TUSHIRISH ---
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("⚠️ Bot to'xtatildi")
    except Exception as e:
        logging.critical(f"💥 Fatal: {e}")
