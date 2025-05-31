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

def get_subscription_remaining_days(user_id):
    cursor.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return 0
    end_date = datetime.fromisoformat(result[0])
    remaining = (end_date - datetime.now()).days
    return remaining if remaining > 0 else 0

def is_subscribed(user_id):
    return get_subscription_remaining_days(user_id) > 0

async def clean_expired():
    while True:
        now = datetime.now().isoformat()
        cursor.execute("DELETE FROM subscriptions WHERE end_date < ?", (now,))
        conn.commit()
        await asyncio.sleep(3600)

@dp.message_handler()
async def handle_all_messages(message: types.Message):
    add_user(message.from_user)

    user_id = message.from_user.id

    kb_admin = ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton("📊 Статистика"),
        KeyboardButton("📢 Рассылка"),
        KeyboardButton("➕ Выдать подписку")
    )

    kb_user = ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton("🔍 Проверить подписку")
    )

    if user_id == ADMIN_ID:
        # Админка
        if message.text == "📊 Статистика":
            cursor.execute("SELECT COUNT(*) FROM subscriptions")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE end_date > ?", (datetime.now().isoformat(),))
            active = cursor.fetchone()[0]
            await message.answer(f"Всего пользователей: {total}\nАктивных подписок: {active}", reply_markup=kb_admin)

        elif message.text == "📢 Рассылка":
            await message.answer("Отправь сообщение для рассылки (оно будет разослано всем с активной подпиской).", reply_markup=kb_admin)

        elif message.text == "➕ Выдать подписку":
            await message.answer("Введите username пользователя (начинается с @) и количество дней подписки через пробел.\nПример:\n@username 30", reply_markup=kb_admin)

        elif message.text and message.text.startswith("@"):
            try:
                parts = message.text.strip().split()
                if len(parts) != 2:
                    await message.answer("Ошибка! Введите в формате: @username количество_дней", reply_markup=kb_admin)
                    return
                username = parts[0]
                days = int(parts[1])

                cursor.execute("SELECT user_id FROM subscriptions WHERE username = ?", (username,))
                res = cursor.fetchone()
                if not res:
                    await message.answer(f"Пользователь {username} не найден.", reply_markup=kb_admin)
                    return

                user_id_to_sub = res[0]
                end_date = datetime.now() + timedelta(days=days)
                cursor.execute("REPLACE INTO subscriptions (user_id, username, end_date) VALUES (?, ?, ?)",
                               (user_id_to_sub, username, end_date.isoformat()))
                conn.commit()
                await message.answer(f"Подписка выдана пользователю {username} на {days} дней.", reply_markup=kb_admin)
                try:
                    await bot.send_message(user_id_to_sub, f"Ваша подписка активирована на {days} дней. Добро пожаловать!")
                except:
                    pass
            except Exception as e:
                await message.answer(f"Ошибка: {e}", reply_markup=kb_admin)

        else:
            # Рассылка
            text = message.text.strip()
            cursor.execute("SELECT user_id, end_date FROM subscriptions")
            users = cursor.fetchall()
            count = 0
            for uid, end_date in users:
                if datetime.now() < datetime.fromisoformat(end_date):
                    try:
                        await bot.send_message(uid, text)
                        count += 1
                    except:
                        pass
            await message.answer(f"Сообщение отправлено {count} пользователям.", reply_markup=kb_admin)

    else:
        # Пользовательская часть
        if message.text == "/start":
            if is_subscribed(user_id):
                await message.answer("👋 Добро пожаловать обратно!\nУ вас активна подписка ✅", reply_markup=kb_user)
            else:
                welcome_message = (
                    "👋 *Добро пожаловать!*\n\n"
                    "Вы попали в бота с эксклюзивными спортивными прогнозами и аналитикой.\n"
                    "Чтобы получить доступ к материалам — необходима активная подписка.\n\n"
                    "💡 *Подписка даёт:*\n"
                    "- Прогнозы от опытного аналитика 🎯\n"
                    "- Экспрессы с коэффициентом 5+\n"
                    "- Личную поддержку по ставкам 💬\n"
                    "- Обновления без спама\n\n"
                    "🔒 У вас пока нет активной подписки.\n"
                    "Для активации — свяжитесь с администратором 👉 @intonusmd"
                )
                await message.answer(welcome_message, parse_mode="Markdown", reply_markup=kb_user)

        elif message.text == "🔍 Проверить подписку":
            days_left = get_subscription_remaining_days(user_id)
            if days_left > 0:
                await message.answer(f"⏳ Ваша подписка активна ещё {days_left} дней.", reply_markup=kb_user)
            else:
                await message.answer("🔒 У вас нет активной подписки.", reply_markup=kb_user)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(clean_expired())
    executor.start_polling(dp, skip_updates=True)
