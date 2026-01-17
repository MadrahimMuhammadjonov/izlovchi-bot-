#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from database import Database

# Konfiguratsiya
BOT_TOKEN = "8045123024:AAGdfjgOJAUosbf4SfUpmDQkh2qeGOirblc"
ADMIN_ID = 8228479175

# Logging sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database
db = Database()

# Holatlar
WAITING_KEYWORD = "waiting_keyword"
WAITING_SEARCH_GROUP = "waiting_search_group"
WAITING_PERSONAL_GROUP = "waiting_personal_group"

def get_main_menu():
    """Asosiy menyu klaviaturasini yaratish"""
    keyboard = [
        [InlineKeyboardButton("➕ Kalit so'z qo'shish", callback_data='add_keyword')],
        [InlineKeyboardButton("📋 Kalit so'zlarni ko'rish", callback_data='view_keywords')],
        [InlineKeyboardButton("🗑 Kalit so'zlarni o'chirish", callback_data='delete_keyword')],
        [InlineKeyboardButton("➕ Izlovchi guruh qo'shish", callback_data='add_search_group')],
        [InlineKeyboardButton("📋 Izlovchi guruhlarni ko'rish", callback_data='view_search_groups')],
        [InlineKeyboardButton("🗑 Izlovchi guruhni o'chirish", callback_data='delete_search_group')],
        [InlineKeyboardButton("➕ Shaxsiy guruh qo'shish", callback_data='add_personal_group')],
        [InlineKeyboardButton("📋 Shaxsiy guruhni ko'rish", callback_data='view_personal_group')],
        [InlineKeyboardButton("🗑 Shaxsiy guruhni o'chirish", callback_data='delete_personal_group')],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text(
            "👋 Assalomu alaykum!\n\n"
            "⚠️ Ushbu botdan faqat adminlar foydalana oladi."
        )
        return
    
    await update.message.reply_text(
        "👋 Assalomu alaykum, Admin!\n\n"
        "Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=get_main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tugmalar bosilganda ishlaydigan handler"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        return
    
    data = query.data
    
    if data == 'add_keyword':
        context.user_data['state'] = WAITING_KEYWORD
        await query.edit_message_text(
            "📝 Yangi kalit so'z kiriting:\n\n"
            "Bekor qilish uchun /cancel yuboring"
        )
    
    elif data == 'view_keywords':
        keywords = db.get_keywords()
        if keywords:
            text = "📋 Kalit so'zlar ro'yxati:\n\n"
            for idx, (kid, keyword) in enumerate(keywords, 1):
                text += f"{idx}. {keyword}\n"
        else:
            text = "❌ Hozircha kalit so'zlar yo'q"
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'delete_keyword':
        keywords = db.get_keywords()
        if keywords:
            keyboard = []
            for kid, keyword in keywords:
                keyboard.append([InlineKeyboardButton(f"🗑 {keyword}", callback_data=f'del_kw_{kid}')])
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')])
            await query.edit_message_text(
                "O'chirish uchun kalit so'zni tanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(
                "❌ Hozircha kalit so'zlar yo'q",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]])
            )
    
    elif data.startswith('del_kw_'):
        keyword_id = int(data.split('_')[2])
        db.delete_keyword(keyword_id)
        await query.edit_message_text(
            "✅ Kalit so'z o'chirildi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]])
        )
    
    elif data == 'add_search_group':
        context.user_data['state'] = WAITING_SEARCH_GROUP
        await query.edit_message_text(
            "📝 Izlovchi guruh ID yoki havolasini yuboring:\n\n"
            "Bekor qilish uchun /cancel yuboring"
        )
    
    elif data == 'view_search_groups':
        groups = db.get_search_groups()
        if groups:
            text = "📋 Izlovchi guruhlar ro'yxati:\n\n"
            for idx, (gid, group_id, group_name) in enumerate(groups, 1):
                text += f"{idx}. {group_name}\n"
        else:
            text = "❌ Hozircha izlovchi guruhlar yo'q"
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'delete_search_group':
        groups = db.get_search_groups()
        if groups:
            keyboard = []
            for gid, group_id, group_name in groups:
                keyboard.append([InlineKeyboardButton(f"🗑 {group_name}", callback_data=f'del_sg_{gid}')])
            keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')])
            await query.edit_message_text(
                "O'chirish uchun guruhni tanlang:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(
                "❌ Hozircha izlovchi guruhlar yo'q",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]])
            )
    
    elif data.startswith('del_sg_'):
        group_id = int(data.split('_')[2])
        db.delete_search_group(group_id)
        await query.edit_message_text(
            "✅ Izlovchi guruh o'chirildi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]])
        )
    
    elif data == 'add_personal_group':
        context.user_data['state'] = WAITING_PERSONAL_GROUP
        await query.edit_message_text(
            "📝 Shaxsiy guruh ID yoki havolasini yuboring:\n\n"
            "Bekor qilish uchun /cancel yuboring"
        )
    
    elif data == 'view_personal_group':
        group = db.get_personal_group()
        if group:
            text = f"📋 Shaxsiy guruh:\n\n{group[1]}"
        else:
            text = "❌ Shaxsiy guruh o'rnatilmagan"
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'delete_personal_group':
        db.delete_personal_group()
        await query.edit_message_text(
            "✅ Shaxsiy guruh o'chirildi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]])
        )
    
    elif data == 'back_to_menu':
        await query.edit_message_text(
            "👋 Assalomu alaykum, Admin!\n\n"
            "Quyidagi menyudan kerakli bo'limni tanlang:",
            reply_markup=get_main_menu()
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarlarni qayta ishlash"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        return
    
    state = context.user_data.get('state')
    text = update.message.text
    
    if state == WAITING_KEYWORD:
        if db.add_keyword(text):
            await update.message.reply_text(
                f"✅ Kalit so'z qo'shildi: {text}",
                reply_markup=get_main_menu()
            )
        else:
            await update.message.reply_text(
                "❌ Bu kalit so'z allaqachon mavjud!",
                reply_markup=get_main_menu()
            )
        context.user_data['state'] = None
    
    elif state == WAITING_SEARCH_GROUP:
        try:
            if text.startswith('https://t.me/') or text.startswith('@'):
                group_identifier = text
            else:
                group_identifier = int(text)
            
            try:
                chat = await context.bot.get_chat(group_identifier)
                group_id = chat.id
                group_name = chat.title or chat.username or str(group_id)
                
                if db.add_search_group(group_id, group_name):
                    await update.message.reply_text(
                        f"✅ Izlovchi guruh qo'shildi: {group_name}",
                        reply_markup=get_main_menu()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Bu guruh allaqachon mavjud!",
                        reply_markup=get_main_menu()
                    )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Guruhni topib bo'lmadi. Botni guruhga qo'shganingizga ishonch hosil qiling.\nXatolik: {str(e)}",
                    reply_markup=get_main_menu()
                )
        except ValueError:
            await update.message.reply_text(
                "❌ Noto'g'ri format! Guruh ID yoki havolasini yuboring.",
                reply_markup=get_main_menu()
            )
        context.user_data['state'] = None
    
    elif state == WAITING_PERSONAL_GROUP:
        try:
            if text.startswith('https://t.me/') or text.startswith('@'):
                group_identifier = text
            else:
                group_identifier = int(text)
            
            try:
                chat = await context.bot.get_chat(group_identifier)
                group_id = chat.id
                group_name = chat.title or chat.username or str(group_id)
                
                if db.add_personal_group(group_id, group_name):
                    await update.message.reply_text(
                        f"✅ Shaxsiy guruh o'rnatildi: {group_name}",
                        reply_markup=get_main_menu()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Xatolik yuz berdi!",
                        reply_markup=get_main_menu()
                    )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Guruhni topib bo'lmadi. Botni guruhga qo'shganingizga ishonch hosil qiling.\nXatolik: {str(e)}",
                    reply_markup=get_main_menu()
                )
        except ValueError:
            await update.message.reply_text(
                "❌ Noto'g'ri format! Guruh ID yoki havolasini yuboring.",
                reply_markup=get_main_menu()
            )
        context.user_data['state'] = None

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bekor qilish"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    context.user_data['state'] = None
    await update.message.reply_text(
        "❌ Bekor qilindi",
        reply_markup=get_main_menu()
    )

def main():
    """Botni ishga tushirish"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logger.info("Bot ishga tushirilmoqda...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
