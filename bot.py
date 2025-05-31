import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from datetime import datetime, timedelta

API_TOKEN = "7641718670:AAHSV9B00v4vx3FGaiC01BvdfPyHyPm0YX0"  # Твой токен
ADMIN_ID = 1303484682  # Твой админ ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect("subscriptions.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER PRIMARY KEY,
    end_date TEXT
)
""")
conn.commit()

def is_subscribed(user_id):
    cursor.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return False
    end_date = datetime.fromisoformat(result[0])
    return datetime.now() < end_date

async def clean_expired():
    while True:
        now = datetime.now().isoformat()
        cursor.execute("DELETE FROM subscriptions WHERE end_date < ?", (now,))
        conn.commit()
        await asyncio.sleep(3600)

@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        print(f"[INFO] Админ {message.from_user.id} вошёл в админ-панель")
        kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        kb.add(KeyboardButton("📊 Статистика"), KeyboardButton("📢 Рассылка"))
        await message.answer("Добро пожаловать в админ-панель!", reply_markup=kb)
    else:
        print(f"[INFO] Пользователь {message.from_user.id} запустил бота")
        if is_subscribed(message.from_user.id):
            await message.answer("Добро пожаловать! У вас активна подписка ✅")
        else:
            await message.answer("Привет! Подписка не активна. Свяжитесь с @intonusmd для оплаты.")

@dp.message_handler(commands=["confirm"])
async def confirm_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, uid, days = message.text.strip().split()
        user_id = int(uid)
        days = int(days)
        end_date = datetime.now() + timedelta(days=days)
        cursor.execute("REPLACE INTO subscriptions (user_id, end_date) VALUES (?, ?)", (user_id, end_date.isoformat()))
        conn.commit()
        await message.answer(f"Подписка пользователю {user_id} выдана на {days} дней.")
        await bot.send_message(user_id, "Ваша подписка активирована. Добро пожаловать!")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "📢 Рассылка")
async def prompt_broadcast(message: types.Message):
    await message.answer("Отправь сообщение для рассылки (оно будет разослано всем с активной подпиской).")

@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "📊 Статистика")
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM subscriptions")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE end_date > ?", (datetime.now().isoformat(),))
    active = cursor.fetchone()[0]
    await message.answer(f"Всего пользователей: {total}\nАктивных подписок: {active}")

@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and not message.text.startswith("/"))
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
    await message.answer(f"Сообщение отправлено {count} пользователям.")

@dp.message_handler(commands=["keyboard"])
async def keyboard_test(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    kb.add(KeyboardButton("📊 Статистика"), KeyboardButton("📢 Рассылка"))
    await message.answer("Тест клавиатуры:", reply_markup=kb)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(clean_expired())
    executor.start_polling(dp, skip_updates=True)
