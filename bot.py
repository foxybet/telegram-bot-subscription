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

# Инициализация базы данных
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

# Добавление пользователя в базу
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

# Сколько дней осталось
def get_remaining_days(user_id):
    cursor.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return 0
    end_date = datetime.fromisoformat(result[0])
    remaining = (end_date - datetime.now()).days
    return max(remaining, 0)

# Удаление просроченных подписок
async def clean_expired():
    while True:
        try:
            conn_local = sqlite3.connect("subscriptions.db")
            cursor_local = conn_local.cursor()
            now = datetime.now().isoformat()
            cursor_local.execute("DELETE FROM subscriptions WHERE end_date < ?", (now,))
            conn_local.commit()
            conn_local.close()
        except Exception as e:
            logging.error(f"Ошибка при удалении просроченных подписок: {e}")
        await asyncio.sleep(3600)

# Обработка сообщений
@dp.message_handler()
async def handle_all_messages(message: types.Message):
    user = message.from_user
    user_id = user.id
    add_user(user)

    if user_id == ADMIN_ID:
        # Меню админа
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(
            KeyboardButton("📊 Статистика"),
            KeyboardButton("📢 Рассылка"),
            KeyboardButton("➕ Выдать подписку")
        )

        if message.text == "📊 Статистика":
            cursor.execute("SELECT COUNT(*) FROM subscriptions")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE end_date > ?", (datetime.now().isoformat(),))
            active = cursor.fetchone()[0]
            await message.answer(f"Всего пользователей: {total}\nАктивных подписок: {active}", reply_markup=kb)

        elif message.text == "📢 Рассылка":
            await message.answer("Отправь текст, который будет отправлен всем с активной подпиской.", reply_markup=kb)

        elif message.text == "➕ Выдать подписку":
            await message.answer("Введите в формате:\n@username 30", reply_markup=kb)

        elif message.text.startswith("@"):
            try:
                parts = message.text.strip().split()
                if len(parts) != 2:
                    await message.answer("Формат: @username 30", reply_markup=kb)
                    return
                username = parts[0]
                days = int(parts[1])
                cursor.execute("SELECT user_id FROM subscriptions WHERE username = ?", (username,))
                result = cursor.fetchone()
                if not result:
                    await message.answer(f"Пользователь {username} не найден.", reply_markup=kb)
                    return
                uid = result[0]
                end_date = datetime.now() + timedelta(days=days)
                cursor.execute("REPLACE INTO subscriptions (user_id, username, end_date) VALUES (?, ?, ?)",
                               (uid, username, end_date.isoformat()))
                conn.commit()
                await message.answer(f"✅ Подписка выдана пользователю {username} на {days} дней.", reply_markup=kb)
                try:
                    await bot.send_message(uid, f"Ваша подписка активирована на {days} дней!")
                except:
                    pass
            except Exception as e:
                await message.answer(f"Ошибка: {e}", reply_markup=kb)

        else:
            # Рассылка
            cursor.execute("SELECT user_id, end_date FROM subscriptions")
            all_users = cursor.fetchall()
            count = 0
            for uid, end in all_users:
                if datetime.now() < datetime.fromisoformat(end):
                    try:
                        await bot.send_message(uid, message.text)
                        count += 1
                    except:
                        pass
            await message.answer(f"Сообщение отправлено {count} пользователям.", reply_markup=kb)

    else:
        # Меню пользователя
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("⏳ Подписка"))

        if message.text == "/start":
            if is_subscribed(user_id):
                await message.answer("✅ У вас активна подписка.", reply_markup=kb)
            else:
                await message.answer("🔒 У вас нет активной подписки. Свяжитесь с @вашникнейм.", reply_markup=kb)

        elif message.text == "⏳ Подписка":
            if is_subscribed(user_id):
                days = get_remaining_days(user_id)
                await message.answer(f"📅 Осталось {days} дней подписки.", reply_markup=kb)
            else:
                await message.answer("🔒 Подписка не активна. Свяжитесь с @вашникнейм.", reply_markup=kb)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(clean_expired())
    executor.start_polling(dp, skip_updates=True)
