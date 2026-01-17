import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db

# Ma'lumotlar
BOT_TOKEN = "8045123024:AAGdfjgOJAUosbf4SfUpmDQkh2qeGOirblc"
ADMIN_ID = 8228479175

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_keyword = State()
    waiting_for_search_group = State()
    waiting_for_private_group = State()

def get_admin_keyboard():
    keyboard = [
        [KeyboardButton(text="1. Kalit soz qoshish"), KeyboardButton(text="2. kalit so'zlarni korish")],
        [KeyboardButton(text="3. kalit so'zlarni ochirish"), KeyboardButton(text="4. izlovchi guruh qoshish")],
        [KeyboardButton(text="5. izlovchi guruhlarni korish"), KeyboardButton(text="6. izlovchi guruhni ochirish")],
        [KeyboardButton(text="7. shaxsiy guruh qoshish"), KeyboardButton(text="8. shaxsiy guruhni ko'rish")],
        [KeyboardButton(text="9. shaxsiy guruxni ochirish")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(f"Salom Admin! Xush kelibsiz.\nQuyidagi menyudan foydalaning:", reply_markup=get_admin_keyboard())
    else:
        await message.answer("Salom! Ushbu botdan faqat adminlar foydalana oladi.")

# 1. Kalit soz qoshish
@dp.message(F.text == "1. Kalit soz qoshish")
async def add_keyword_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Yangi kalit soz kiriting:")
    await state.set_state(Form.waiting_for_keyword)

@dp.message(Form.waiting_for_keyword)
async def process_keyword(message: types.Message, state: FSMContext):
    if db.add_keyword(message.text):
        await message.answer(f"Kalit so'z '{message.text}' muvaffaqiyatli qo'shildi.")
    else:
        await message.answer("Ushbu kalit so'z allaqachon mavjud.")
    await state.clear()

# 2. Kalit so'zlarni ko'rish
@dp.message(F.text == "2. kalit so'zlarni korish")
async def view_keywords(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    keywords = db.get_keywords()
    if not keywords:
        await message.answer("Hozircha kalit so'zlar yo'q.")
        return
    text = "Kalit so'zlar ro'yxati:\n"
    for k in keywords:
        text += f"- {k[1]}\n"
    await message.answer(text)

# 3. Kalit so'zlarni o'chirish
@dp.message(F.text == "3. kalit so'zlarni ochirish")
async def delete_keyword_list(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    keywords = db.get_keywords()
    if not keywords:
        await message.answer("O'chirish uchun kalit so'zlar yo'q.")
        return
    
    builder = []
    for k in keywords:
        builder.append([InlineKeyboardButton(text=k[1], callback_data=f"del_key_{k[0]}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=builder)
    await message.answer("O'chirmoqchi bo'lgan kalit so'zingizni tanlang:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("del_key_"))
async def process_delete_keyword(callback: types.CallbackQuery):
    key_id = int(callback.data.split("_")[2])
    db.delete_keyword(key_id)
    await callback.answer("Kalit so'z o'chirildi.")
    await callback.message.edit_text("Kalit so'z muvaffaqiyatli o'chirildi.")

# 4. Izlovchi guruh qo'shish
@dp.message(F.text == "4. izlovchi guruh qoshish")
async def add_search_group_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Izlovchi guruh ID yoki havolasini yuboring:")
    await state.set_state(Form.waiting_for_search_group)

@dp.message(Form.waiting_for_search_group)
async def process_search_group(message: types.Message, state: FSMContext):
    # Bu yerda guruhni tekshirish va nomini olish userbot orqali bo'lishi kerak, 
    # lekin hozircha oddiygina saqlaymiz. Userbot ishga tushganda guruhga qo'shiladi.
    group_input = message.text
    if db.add_search_group(group_input, f"Guruh: {group_input}"):
        await message.answer(f"Izlovchi guruh '{group_input}' qo'shildi.")
    else:
        await message.answer("Ushbu guruh allaqachon mavjud.")
    await state.clear()

# 5. Izlovchi guruhlarni ko'rish
@dp.message(F.text == "5. izlovchi guruhlarni korish")
async def view_search_groups(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    groups = db.get_search_groups()
    if not groups:
        await message.answer("Izlovchi guruhlar yo'q.")
        return
    text = "Izlovchi guruhlar:\n"
    for g in groups:
        text += f"- {g[2]} (ID: {g[1]})\n"
    await message.answer(text)

# 6. Izlovchi guruhni o'chirish
@dp.message(F.text == "6. izlovchi guruhni ochirish")
async def delete_search_group_list(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    groups = db.get_search_groups()
    if not groups:
        await message.answer("O'chirish uchun guruhlar yo'q.")
        return
    
    builder = []
    for g in groups:
        builder.append([InlineKeyboardButton(text=g[2], callback_data=f"del_sg_{g[1]}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=builder)
    await message.answer("O'chirmoqchi bo'lgan izlovchi guruhni tanlang:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("del_sg_"))
async def process_delete_sg(callback: types.CallbackQuery):
    group_id = callback.data.replace("del_sg_", "")
    db.delete_search_group(group_id)
    await callback.answer("Guruh o'chirildi.")
    await callback.message.edit_text("Izlovchi guruh muvaffaqiyatli o'chirildi.")

# 7. Shaxsiy guruh qo'shish
@dp.message(F.text == "7. shaxsiy guruh qoshish")
async def add_private_group_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Shaxsiy guruh ID yoki havolasini yuboring:")
    await state.set_state(Form.waiting_for_private_group)

@dp.message(Form.waiting_for_private_group)
async def process_private_group(message: types.Message, state: FSMContext):
    group_input = message.text
    if db.add_private_group(group_input, f"Shaxsiy: {group_input}"):
        await message.answer(f"Shaxsiy guruh '{group_input}' qo'shildi.")
    else:
        await message.answer("Ushbu shaxsiy guruh allaqachon mavjud.")
    await state.clear()

# 8. Shaxsiy guruhni ko'rish
@dp.message(F.text == "8. shaxsiy guruhni ko'rish")
async def view_private_groups(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    groups = db.get_private_groups()
    if not groups:
        await message.answer("Shaxsiy guruhlar yo'q.")
        return
    text = "Shaxsiy guruhlar:\n"
    for g in groups:
        text += f"- {g[2]} (ID: {g[1]})\n"
    await message.answer(text)

# 9. Shaxsiy guruhni o'chirish
@dp.message(F.text == "9. shaxsiy guruxni ochirish")
async def delete_private_group_list(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    groups = db.get_private_groups()
    if not groups:
        await message.answer("O'chirish uchun shaxsiy guruhlar yo'q.")
        return
    
    builder = []
    for g in groups:
        builder.append([InlineKeyboardButton(text=g[2], callback_data=f"del_pg_{g[1]}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=builder)
    await message.answer("O'chirmoqchi bo'lgan shaxsiy guruhni tanlang:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("del_pg_"))
async def process_delete_pg(callback: types.CallbackQuery):
    group_id = callback.data.replace("del_pg_", "")
    db.delete_private_group(group_id)
    await callback.answer("Shaxsiy guruh o'chirildi.")
    await callback.message.edit_text("Shaxsiy guruh muvaffaqiyatli o'chirildi.")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
