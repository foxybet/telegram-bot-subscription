import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils import executor
from datetime import datetime, timedelta

API_TOKEN = "7641718670:AAHSV9B00v4vx3FGaiC01BvdfPyHyPm0YX0"
ADMIN_ID = 1303484682

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# SQLite база данных
conn = sqlite3.connect("subscriptions.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER PRIMARY KEY,
    end_date TEXT
)
""")
conn.commit()

# Переменные состояния
admin_state = {}

# Проверка подписки
def is_subscribed(user_id):
    cursor.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return False
    end_date = datetime.fromisoformat(result[0])
    return datetime.now() < end_date

# Удаление просроченных подписок
async def clean_expired():
    while True:
        now = datetime.now().isoformat()
        cursor.execute("DELETE FROM subscriptions WHERE end_date < ?", (now,))
        conn.commit()
        await asyncio.sleep(3600)

# /start
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("📊 Статистика"), KeyboardButton("📢 Рассылка"))
        kb.add(KeyboardButton("✅ Выдать подписку"))
        await message.answer("Добро пожаловать в админ-панель!", reply_markup=kb)
    else:
        if is_subscribed(message.from_user.id):
            await message.answer("Добро пожаловать! У вас активна подписка ✅")
        else:
            await message.answer("Привет! Подписка не активна. Свяжитесь с @intonusmd для оплаты.")

# Выдача подписки по кнопке
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "✅ Выдать подписку")
async def issue_subscription(message: types.Message):
    admin_state[message.from_user.id] = "awaiting_user_id"
    await message.answer("Введите ID пользователя, которому нужно выдать подписку:")

@dp.message_handler(lambda message: admin_state.get(message.from_user.id) == "awaiting_user_id")
async def get_user_id(message: types.Message):
    try:
        user_id = int(message.text.strip())
        admin_state[message.from_user.id] = ("awaiting_days", user_id)
        await message.answer("Введите количество дней подписки:")
    except ValueError:
        await message.answer("Пожалуйста, введите корректный числовой ID пользователя.")

@dp.message_handler(lambda message: isinstance(admin_state.get(message.from_user.id), tuple) and admin_state[message.from_user.id][0] == "awaiting_days")
async def get_subscription_days(message: types.Message):
    try:
        days = int(message.text.strip())
        user_id = admin_state[message.from_user.id][1]
        end_date = datetime.now() + timedelta(days=days)
        cursor.execute("REPLACE INTO subscriptions (user_id, end_date) VALUES (?, ?)", (user_id, end_date.isoformat()))
        conn.commit()
        await message.answer(f"Подписка пользователю {user_id} выдана на {days} дней ✅", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(
            KeyboardButton("📊 Статистика"), KeyboardButton("📢 Рассылка"), KeyboardButton("✅ Выдать подписку")
        ))
        await bot.send_message(user_id, f"Ваша подписка активирована на {days} дней ✅")
        admin_state.pop(message.from_user.id, None)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число дней.")

# Статистика
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "📊 Статистика")
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM subscriptions")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE end_date > ?", (datetime.now().isoformat(),))
    active = cursor.fetchone()[0]
    await message.answer(f"Всего пользователей в БД: {total}\nАктивных подписок: {active}")

# Рассылка
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "📢 Рассылка")
async def prompt_broadcast(message: types.Message):
    admin_state[message.from_user.id] = "awaiting_broadcast"
    await message.answer("Введите текст сообщения для рассылки:")

@dp.message_handler(lambda message: admin_state.get(message.from_user.id) == "awaiting_broadcast")
async def handle_broadcast_text(message: types.Message):
    text = message.text.strip()
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
    await message.answer(f"Сообщение отправлено {count} пользователям ✅")
    admin_state.pop(message.from_user.id, None)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(clean_expired())
    executor.start_polling(dp, skip_updates=True)
