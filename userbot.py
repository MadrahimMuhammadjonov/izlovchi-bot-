import logging
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, PeerChat, PeerUser
from database import Database
import requests

# Konfiguratsiya
API_ID = 36799342
API_HASH = "fcdf748b56fb519c6900d02e25ae2d62"
PHONE_NUMBER = "+998931317231"
SESSION_STRING = "1ApWapzMBu7wMtDnHS2BHSlKKIcR0O326szif2GpPek9MHzgLxHaafUzSGh864f--z_ImIsN8GkhzJY-T_TLRSyc2MdUBAX89sRsqUWumntyGQ1u0d0h3c0t0k_VSaqq3Mjjt401spd3TcLUgz8qb23Eh7PtVSvs1viHduuKXyExsUAkstyewIDamcQf2mlGQuoQiL5WBc63h5q6Roj-kff-xxr1TJB-3kag0XdKVKzS50xFWyXKBoixQ_XynUB1yk4qkaUbKv9ciCyZGy6yTRm3IgGk8Rb2BECId-p6fRR-jPsVemBhDZIOY2gwNNTrwty8I988h0lACcrT5Hyh9uX56KRlr8tc="

BOT_TOKEN = "8045123024:AAGdfjgOJAUosbf4SfUpmDQkh2qeGOirblc"

# Logging sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database
db = Database()

# Telegram client
client = TelegramClient('userbot_session', API_ID, API_HASH)

async def send_to_personal_group(message_text, group_name, user_id, user_name, user_username, message_link):
    """Shaxsiy guruhga xabar yuborish"""
    personal_group = db.get_personal_group()
    
    if not personal_group:
        logger.warning("Shaxsiy guruh o'rnatilmagan!")
        return
    
    group_id = int(personal_group[0])
    
    # Xabar matni
    text = f"🔍 <b>Kalit so'z topildi!</b>\n\n"
    text += f"👥 <b>Guruh:</b> {group_name}\n"
    text += f"👤 <b>Foydalanuvchi:</b> {user_name}"
    
    if user_username:
        text += f" (@{user_username})\n"
    else:
        text += "\n"
    
    text += f"\n📝 <b>Xabar:</b>\n{message_text}\n"
    
    if message_link:
        text += f"\n🔗 <a href='{message_link}'>Xabarga o'tish</a>"
    
    # Inline tugma - foydalanuvchi profiliga o'tish
    keyboard = {
        'inline_keyboard': [[
            {'text': '👤 Profilga o\'tish', 'url': f'tg://user?id={user_id}'}
        ]]
    }
    
    # Bot orqali xabar yuborish
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': group_id,
        'text': text,
        'parse_mode': 'HTML',
        'reply_markup': keyboard,
        'disable_web_page_preview': True
    }
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            logger.info(f"Xabar yuborildi: {user_name} ({group_name})")
        else:
            logger.error(f"Xabar yuborilmadi: {response.text}")
    except Exception as e:
        logger.error(f"Xatolik: {e}")

def check_keywords(text):
    """Xabarda kalit so'zlar borligini tekshirish"""
    if not text:
        return []
    
    keywords = db.get_keywords()
    found_keywords = []
    
    text_lower = text.lower()
    
    for kid, keyword in keywords:
        if keyword.lower() in text_lower:
            found_keywords.append(keyword)
    
    return found_keywords

@client.on(events.NewMessage())
async def handle_new_message(event):
    """Yangi xabarlarni qayta ishlash"""
    try:
        # Guruhlarni tekshirish
        search_groups = db.get_search_groups()
        
        if not search_groups:
            return
        
        # Xabar guruhdan kelyaptimi?
        chat = await event.get_chat()
        chat_id = str(event.chat_id)
        
        # Izlovchi guruhlar ro'yxatida bormi?
        is_monitored = False
        group_name = ""
        
        for gid, group_id, gname in search_groups:
            if group_id == chat_id or group_id == str(chat.id):
                is_monitored = True
                group_name = gname
                break
        
        if not is_monitored:
            return
        
        # Xabar matnini olish
        message_text = event.message.message
        
        if not message_text:
            return
        
        # Kalit so'zlarni tekshirish
        found_keywords = check_keywords(message_text)
        
        if not found_keywords:
            return
        
        # Foydalanuvchi ma'lumotlarini olish
        sender = await event.get_sender()
        user_id = sender.id
        user_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        if not user_name:
            user_name = "Noma'lum"
        user_username = sender.username
        
        # Xabar havolasi
        message_link = None
        try:
            if hasattr(chat, 'username') and chat.username:
                message_link = f"https://t.me/{chat.username}/{event.message.id}"
            elif hasattr(event.message, 'id'):
                # Private guruh uchun
                message_link = f"https://t.me/c/{str(chat.id)[4:]}/{event.message.id}"
        except:
            pass
        
        # Shaxsiy guruhga yuborish
        logger.info(f"Kalit so'z topildi: {found_keywords} - {user_name} ({group_name})")
        await send_to_personal_group(
            message_text,
            group_name,
            user_id,
            user_name,
            user_username,
            message_link
        )
        
    except Exception as e:
        logger.error(f"Xatolik yuz berdi: {e}")

async def main():
    """Userbotni ishga tushirish"""
    logger.info("Userbot ishga tushirilmoqda...")
    
    # Sessionni import qilish (agar SESSION_STRING berilgan bo'lsa)
    if SESSION_STRING:
        from telethon.sessions import StringSession
        global client
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    
    await client.start(phone=PHONE_NUMBER)
    logger.info("Userbot muvaffaqiyatli ishga tushdi!")
    
    # Izlovchi guruhlarni olish va ularga obuna bo'lish
    search_groups = db.get_search_groups()
    logger.info(f"Izlovchi guruhlar soni: {len(search_groups)}")
    
    for gid, group_id, group_name in search_groups:
        logger.info(f"Kuzatilayotgan guruh: {group_name} ({group_id})")
    
    # Userbotni ishlatish
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Userbot to'xtatildi")
