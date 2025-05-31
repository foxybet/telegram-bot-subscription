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

# Автоудаление просроченных подписок (раз в час)
async def clean_expired():
    while True:
        now = datetime.now().isoformat()
        cursor.execute("DELETE FROM subscriptions WHERE end_date < ?", (now,))
        conn.commit()
        await asyncio.sleep(3600)

# Команда /start
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else None

    # Добавляем пользователя в БД, если нет
    cursor.execute("SELECT user_id FROM subscriptions WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO subscriptions (user_id, username, end_date) VALUES (?, ?, ?)",
            (user_id, username, "1970-01-01T00:00:00")
        )
        conn.commit()

    if user_id == ADMIN_ID:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(
            KeyboardButton("📊 Статистика"),
            KeyboardButton("📢 Рассылка"),
            KeyboardButton("➕ Выдать подписку")
        )
        await message.answer("Добро пожаловать в админ-панель!", reply_markup=kb)
    else:
        if is_subscribed(user_id):
            await message.answer("Добро пожаловать! У вас активна подписка ✅")
        else:
            await message.answer("Привет! Подписка не активна. Свяжитесь с @intonusmd для оплаты.")

# Обработка кнопки "Статистика" для админа
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "📊 Статистика")
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM subscriptions")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE end_date > ?", (datetime.now().isoformat(),))
    active = cursor.fetchone()[0]
    await message.answer(f"Всего пользователей: {total}\nАктивных подписок: {active}")

# Обработка кнопки "Рассылка" для админа
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "📢 Рассылка")
async def prompt_broadcast(message: types.Message):
    await message.answer("Отправь сообщение для рассылки (оно будет разослано всем с активной подпиской).")

# Обработка кнопки "Выдать подписку" для админа
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "➕ Выдать подписку")
async def prompt_subscription(message: types.Message):
    await message.answer("Введите username пользователя (начинается с @) и количество дней подписки через пробел.\nПример:\n@username 30")

# Выдача подписки по username и количеству дней
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID)
async def give_subscription(message: types.Message):
    if message.text.startswith("@"):
        try:
            parts = message.text.strip().split()
            if len(parts) != 2:
                await message.answer("Ошибка! Введите в формате: @username количество_дней")
                return
            username = parts[0]
            days = int(parts[1])

            # Найдём user_id по username
            cursor.execute("SELECT user_id FROM subscriptions WHERE username = ?", (username,))
            res = cursor.fetchone()
            if not res:
                await message.answer(f"Пользователь {username} не найден.")
                return

            user_id = res[0]
            end_date = datetime.now() + timedelta(days=days)
            cursor.execute("REPLACE INTO subscriptions (user_id, username, end_date) VALUES (?, ?, ?)",
                           (user_id, username, end_date.isoformat()))
            conn.commit()
            await message.answer(f"Подписка выдана пользователю {username} на {days} дней.")
            try:
                await bot.send_message(user_id, f"Ваша подписка активирована на {days} дней. Добро пожаловать!")
            except:
                pass
        except Exception as e:
            await message.answer(f"Ошибка: {e}")

# Получаем текст для рассылки и отправляем всем активным
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID)
async def handle_broadcast_text(message: types.Message):
    # Если это не команды и не кнопки подписки — это рассылка
    if not message.text.startswith("@") and message.text not in ["📢 Рассылка", "📊 Статистика", "➕ Выдать подписку"]:
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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(clean_expired())
    executor.start_polling(dp, skip_updates=True)
