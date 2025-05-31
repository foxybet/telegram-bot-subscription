import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from datetime import datetime, timedelta

API_TOKEN = "7641718670:AAHSV9B00v4vx3FGaiC01BvdfPyHyPm0YX0"  # Твой токен
ADMIN_ID = 1303484682  # Твой Telegram ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Подключаем SQLite для хранения подписок
conn = sqlite3.connect("subscriptions.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    end_date TEXT
)
""")
conn.commit()

# Проверка подписки
def is_subscribed(user_id):
    cursor.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return False
    end_date = datetime.fromisoformat(result[0])
    return datetime.now() < end_date

# Автоудаление просроченных подписок
async def clean_expired():
    while True:
        now = datetime.now().isoformat()
        cursor.execute("DELETE FROM subscriptions WHERE end_date < ?", (now,))
        conn.commit()
        await asyncio.sleep(3600)

# Кнопочная админка
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(
            KeyboardButton("📊 Статистика"),
            KeyboardButton("📢 Рассылка"),
            KeyboardButton("➕ Выдать подписку")
        )
        await message.answer("Добро пожаловать в админ-панель!", reply_markup=kb)
    else:
        if is_subscribed(message.from_user.id):
            await message.answer("Добро пожаловать! У вас активна подписка ✅")
        else:
            await message.answer("Привет! Подписка не активна. Свяжитесь с @intonusmd для оплаты.")

# Статистика
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text == "📊 Статистика")
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM subscriptions")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE end_date > ?", (datetime.now().isoformat(),))
    active = cursor.fetchone()[0]
    await message.answer(f"Всего пользователей: {total}\nАктивных подписок: {active}")

# Рассылка
broadcast_wait = {}

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text == "📢 Рассылка")
async def prompt_broadcast(message: types.Message):
    broadcast_wait[message.from_user.id] = True
    await message.answer("Отправьте сообщение для рассылки.")

# Выдать подписку — запрос username
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text == "➕ Выдать подписку")
async def ask_username(message: types.Message):
    await message.answer("Отправь username пользователя (начиная с @) и количество дней. Пример:\n`@username 30`", parse_mode="Markdown")

# Принимаем рассылку или выдаем подписку
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID)
async def handle_admin_text(message: types.Message):
    text = message.text.strip()

    # Режим рассылки
    if broadcast_wait.get(message.from_user.id):
        cursor.execute("SELECT user_id, end_date FROM subscriptions")
        users = cursor.fetchall()
        count = 0
        for user_id, end_date in users:
            if datetime.now() < datetime.fromisoformat(end_date):
                try:
                    await bot.send_message(user_id, text)
                    count += 1
                except:
                    pass
        await message.answer(f"Сообщение отправлено {count} пользователям.")
        broadcast_wait[message.from_user.id] = False
        return

    # Выдача подписки по username
    if text.startswith("@") and len(text.split()) == 2:
        username, days_str = text.split()
        try:
            days = int(days_str)
            user = await bot.get_chat(username)
            end_date = datetime.now() + timedelta(days=days)
            cursor.execute(
                "REPLACE INTO subscriptions (user_id, username, end_date) VALUES (?, ?, ?)",
                (user.id, username, end_date.isoformat())
            )
            conn.commit()
            await message.answer(f"Подписка пользователю {username} выдана на {days} дней.")
            await bot.send_message(user.id, "Ваша подписка активирована. Добро пожаловать!")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")
    else:
        await message.answer("Пожалуйста, введите username и количество дней. Пример:\n`@username 30`", parse_mode="Markdown")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(clean_expired())
    executor.start_polling(dp, skip_updates=True)
