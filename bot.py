import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from datetime import datetime, timedelta

API_TOKEN = "7641718670:AAHSV9B00v4vx3FGaiC01BvdfPyHyPm0YX0"
ADMIN_ID = 1303484682

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

# Добавляем пользователя в базу если его там нет
def add_user(user: types.User):
    user_id = user.id
    username = f"@{user.username}" if user.username else None
    cursor.execute("SELECT user_id FROM subscriptions WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO subscriptions (user_id, username, end_date) VALUES (?, ?, ?)",
            (user_id, username, "1970-01-01T00:00:00")
        )
        conn.commit()

# Проверка подписки
def is_subscribed(user_id):
    cursor.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return False
    end_date = datetime.fromisoformat(result[0])
    return datetime.now() < end_date

# Проверка сколько дней осталось
def days_left(user_id):
    cursor.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return 0
    end_date = datetime.fromisoformat(result[0])
    remaining = (end_date - datetime.now()).days
    return remaining if remaining > 0 else 0

# Автоудаление просроченных подписок (раз в час)
async def clean_expired():
    while True:
        now = datetime.now().isoformat()
        cursor.execute("DELETE FROM subscriptions WHERE end_date < ?", (now,))
        conn.commit()
        await asyncio.sleep(3600)

# Клавиатура для админа
def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        KeyboardButton("📊 Статистика"),
        KeyboardButton("📢 Рассылка"),
        KeyboardButton("➕ Выдать подписку")
    )
    return kb

# Клавиатура для пользователя
def user_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🔍 Проверить подписку"))
    return kb

# Приветственное сообщение
WELCOME_MSG = (
    "👋 Приветствую!\n\n"
    "Добро пожаловать в бот подписок.\n\n"
    "👉 Для получения подписки свяжитесь с @intonusmd.\n"
    "👉 Если у вас уже есть подписка, нажмите кнопку ниже, чтобы проверить её статус."
)

@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    add_user(message.from_user)
    if message.from_user.id == ADMIN_ID:
        await message.answer("Добро пожаловать, админ!", reply_markup=admin_kb())
    else:
        await message.answer(WELCOME_MSG, reply_markup=user_kb())

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID)
async def admin_handler(message: types.Message):
    add_user(message.from_user)
    text = message.text.strip()

    if text == "📊 Статистика":
        cursor.execute("SELECT COUNT(*) FROM subscriptions")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE end_date > ?", (datetime.now().isoformat(),))
        active = cursor.fetchone()[0]
        await message.answer(f"📈 Статистика:\n\nВсего пользователей: {total}\nАктивных подписок: {active}", reply_markup=admin_kb())

    elif text == "📢 Рассылка":
        await message.answer("Отправьте сообщение для рассылки всем активным подписчикам.", reply_markup=admin_kb())
        dp.register_message_handler(broadcast_handler, lambda m: m.from_user.id == ADMIN_ID, state=None)

    elif text == "➕ Выдать подписку":
        await message.answer("Введите username пользователя и количество дней подписки через пробел.\nПример:\n@username 30", reply_markup=admin_kb())

    elif text.startswith("@"):
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer("Ошибка! Формат: @username количество_дней", reply_markup=admin_kb())
            return
        username, days_str = parts
        days = int(days_str)
        cursor.execute("SELECT user_id FROM subscriptions WHERE username = ?", (username,))
        res = cursor.fetchone()
        if not res:
            await message.answer(f"Пользователь {username} не найден.", reply_markup=admin_kb())
            return
        user_id_to_sub = res[0]
        end_date = datetime.now() + timedelta(days=days)
        cursor.execute("REPLACE INTO subscriptions (user_id, username, end_date) VALUES (?, ?, ?)",
                       (user_id_to_sub, username, end_date.isoformat()))
        conn.commit()
        await message.answer(f"Подписка выдана пользователю {username} на {days} дней.", reply_markup=admin_kb())
        try:
            await bot.send_message(user_id_to_sub, f"Ваша подписка активирована на {days} дней. Добро пожаловать!")
        except:
            pass

async def broadcast_handler(message: types.Message):
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
    await message.answer(f"Сообщение отправлено {count} пользователям.", reply_markup=admin_kb())
    dp.message_handlers.unregister(broadcast_handler)  # отменяем регистрацию после рассылки

@dp.message_handler(lambda m: m.from_user.id != ADMIN_ID)
async def user_handler(message: types.Message):
    add_user(message.from_user)
    if message.text == "🔍 Проверить подписку":
        if is_subscribed(message.from_user.id):
            days_remaining = days_left(message.from_user.id)
            await message.answer(f"✅ Ваша подписка активна.\nОсталось дней: {days_remaining}", reply_markup=user_kb())
        else:
            await message.answer("🔒 У вас нет активной подписки. Свяжитесь с @intonusmd для оплаты.", reply_markup=user_kb())
    else:
        await message.answer(WELCOME_MSG, reply_markup=user_kb())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(clean_expired())
    executor.start_polling(dp, skip_updates=True)
