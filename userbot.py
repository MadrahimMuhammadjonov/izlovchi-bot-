import asyncio
from pyrogram import Client, filters, types
from pyrogram.errors import FloodWait
from database import db

# Ma'lumotlar
API_ID = 36799342
API_HASH = "fcdf748b56fb519c6900d02e25ae2d62"
SESSION_STRING = "1ApWapzMBu7wMtDnHS2BHSlKKIcR0O326szif2GpPek9MHzgLxHaafUzSGh864f--z_ImIsN8GkhzJY-T_TLRSyc2MdUBAX89sRsqUWumntyGQ1u0d0h3c0t0k_VSaqq3Mjjt401spd3TcLUgz8qb23Eh7PtVSvs1viHduuKXyExsUAkstyewIDamcQf2mlGQuoQiL5WBc63h5q6Roj-kff-xxr1TJB-3kag0XdKVKzS50xFWyXKBoixQ_XynUB1yk4qkaUbKv9ciCyZGy6yTRm3IgGk8Rb2BECId-p6fRR-jPsVemBhDZIOY2gwNNTrwty8I988h0lACcrT5Hyh9uX56KRlr8tc="

app = Client("my_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

@app.on_message(filters.group & ~filters.me)
async def check_messages(client, message):
    # Kalit so'zlarni bazadan olish
    keywords = [k[1].lower() for k in db.get_keywords()]
    if not keywords:
        return

    # Izlovchi guruhlarni tekshirish
    search_groups = [g[1] for g in db.get_search_groups()]
    
    # Agar guruh ID si bazada bo'lsa yoki guruh username bazada bo'lsa
    current_chat_id = str(message.chat.id)
    current_chat_username = message.chat.username
    
    is_search_group = False
    for sg in search_groups:
        if sg == current_chat_id or (current_chat_username and sg.endswith(current_chat_username)):
            is_search_group = True
            break
    
    if not is_search_group:
        return

    # Xabarda kalit so'z borligini tekshirish
    msg_text = message.text or message.caption
    if not msg_text:
        return
    
    msg_text_lower = msg_text.lower()
    found_keyword = None
    for kw in keywords:
        if kw in msg_text_lower:
            found_keyword = kw
            break
    
    if found_keyword:
        # Shaxsiy guruhlarni olish
        private_groups = db.get_private_groups()
        if not private_groups:
            return

        # Ma'lumotlarni tayyorlash
        sender = message.from_user
        sender_name = sender.first_name or "Noma'lum"
        group_name = message.chat.title
        
        report_text = (
            f"🔍 **Kalit so'z topildi:** #{found_keyword}\n\n"
            f"👥 **Guruh:** {group_name}\n"
            f"👤 **Kim tomonidan:** {sender_name}\n"
            f"📝 **Xabar:** {msg_text}\n"
        )
        
        # Tugma yaratish
        keyboard = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("👤 Profilga o'tish", user_id=sender.id)]
        ])

        # Har bir shaxsiy guruhga yuborish
        for pg in private_groups:
            try:
                await client.send_message(
                    chat_id=pg[1],
                    text=report_text,
                    reply_markup=keyboard
                )
            except Exception as e:
                print(f"Xabar yuborishda xatolik ({pg[1]}): {e}")

async def main():
    print("Userbot ishga tushmoqda...")
    await app.start()
    
    # Izlovchi guruhlarga qo'shilishga harakat qilish
    search_groups = db.get_search_groups()
    for sg in search_groups:
        try:
            await app.join_chat(sg[1])
            print(f"Guruhga qo'shildi: {sg[1]}")
        except Exception:
            pass

    print("Userbot muvaffaqiyatli ishga tushdi!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
