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

# Подключение к базе данных
conn = sqlite3.connect("subscriptions.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER PRIMARY KEY,
    end_date TEXT
)
""")
conn.commit()

# Состояние админов (для пошаговой выдачи подписки)
admin_states = {}  # user_id -> {"step": ..., "data": {...}}

# Проверка подписки
def is_subscribed(user_id):
    cursor.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return False
    end_date = datetime.fromisoformat(result[0])
    return datetime.now() < end_date

# Очистка просроченных подписок
async def clean_expired():
    while True:
        now = datetime.now().isoformat()
        cursor.execute("DELETE FROM subscriptions WHERE end_date < ?", (now,))
        conn.commit()
        await asyncio.sleep(3600)

# Команда /start
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("📊 Статистика"), KeyboardButton("📢 Рассылка"))
        kb.add(KeyboardButton("➕ Выдать подписку"))
        await message.answer("Добро пожаловать в админ-панель!", reply_markup=kb)
    else:
        if is_subscribed(message.from_user.id):
            await message.answer("Добро пожаловать! У вас активна подписка ✅")
        else:
            await message.answer("Привет! Подписка не активна. Свяжитесь с @intonusmd для оплаты.")

# Обработка кнопки "Выдать подписку"
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "➕ Выдать подписку")
async def issue_subscription_start(message: types.Message):
    admin_states[message.from_user.id] = {"step": "await_user_id", "data": {}}
    await message.answer("Введите ID пользователя, которому хотите выдать подписку:")

# Обработка шагов выдачи подписки
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.from_user.id in admin_states)
async def process_admin_steps(message: types.Message):
    state = admin_states.get(message.from_user.id)

    if state["step"] == "await_user_id":
        try:
            user_id = int(message.text.strip())
            state["data"]["user_id"] = user_id
            state["step"] = "await_days"
            await message.answer("Введите количество дней подписки:")
        except:
            await message.answer("ID должен быть числом. Попробуйте снова.")

    elif state["step"] == "await_days":
        try:
            days = int(message.text.strip())
            user_id = state["data"]["user_id"]
            end_date = datetime.now() + timedelta(days=days)
            cursor.execute("REPLACE INTO subscriptions (user_id, end_date) VALUES (?, ?)", (user_id, end_date.isoformat()))
            conn.commit()
            del admin_states[message.from_user.id]
            await message.answer(f"Подписка пользователю {user_id} выдана на {days} дней.")
            await bot.send_message(user_id, "Ваша подписка активирована. Добро пожаловать!")
        except:
            await message.answer("Количество дней должно быть числом. Попробуйте снова.")

# Обработка кнопки "Статистика"
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "📊 Статистика")
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM subscriptions")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE end_date > ?", (datetime.now().isoformat(),))
    active = cursor.fetchone()[0]
    await message.answer(f"Всего пользователей: {total}\nАктивных подписок: {active}")

# Обработка кнопки "Рассылка"
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and message.text == "📢 Рассылка")
async def prompt_broadcast(message: types.Message):
    await message.answer("Отправь сообщение для рассылки (оно будет разослано всем с активной подпиской).")

# Обработка текста для рассылки
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID and not message.text.startswith("/") and message.from_user.id not in admin_states)
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

# Запуск
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(clean_expired())
    executor.start_polling(dp, skip_updates=True)
