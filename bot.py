
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from datetime import datetime, timedelta

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Храним подписки в памяти (можно заменить на БД)
subscriptions = {}

# Проверка подписки
def is_subscribed(user_id):
    if user_id not in subscriptions:
        return False
    return datetime.now() < subscriptions[user_id]

# Команда /start
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    if is_subscribed(message.from_user.id):
        await message.answer("Добро пожаловать! У вас активна подписка ✅")
    else:
        await message.answer("Привет! Подписка не активна. Свяжитесь с @intonusmd для оплаты.")

# Команда /send (только для админа)
@dp.message_handler(commands=["send"])
async def send_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.replace("/send", "").strip()
    if not text:
        await message.answer("Напиши текст после /send")
        return
    count = 0
    for user_id in subscriptions:
        if is_subscribed(user_id):
            try:
                await bot.send_message(user_id, text)
                count += 1
            except:
                pass
    await message.answer(f"Отправлено {count} пользователям.")

# Команда /confirm user_id days
@dp.message_handler(commands=["confirm"])
async def confirm_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        days = int(parts[2])
        subscriptions[user_id] = datetime.now() + timedelta(days=days)
        await message.answer(f"Пользователь {user_id} активирован на {days} дней.")
        await bot.send_message(user_id, "Ваша подписка активирована. Добро пожаловать!")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
