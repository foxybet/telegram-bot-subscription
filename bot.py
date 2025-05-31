import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from datetime import datetime, timedelta

API_TOKEN = "7641718670:AAHSV9B00v4vx3FGaiC01BvdfPyHyPm0YX0"
ADMIN_ID = 1303484682  # Замени на свой Telegram ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# SQLite
conn = sqlite3.connect("subscriptions.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    end_date TEXT
)
""")
conn.commit()

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 Статистика", "📢 Рассылка", "➕ Выдать подписку")
    return kb

def user_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔍 Проверить подписку")
    return kb

def add_user(user: types.User):
    cursor.execute("SELECT user_id FROM subscriptions WHERE user_id = ?", (user.id,))
    if not cursor.fetchone():
        username = f"@{user.username}" if user.username else None
        cursor.execute(
            "INSERT INTO subscriptions (user_id, username, end_date) VALUES (?, ?, ?)",
            (user.id, username, "1970-01-01T00:00:00")
        )
        conn.commit()

async def clean_expired():
    while True:
        now = datetime.now().isoformat()
        cursor.execute("DELETE FROM subscriptions WHERE end_date < ?", (now,))
        conn.commit()
        await asyncio.sleep(3600)

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID)
async def admin_handler(message: types.Message):
    if message.text == "/start":
        await message.answer("👑 Админ-панель:", reply_markup=admin_kb())
    elif message.text == "📊 Статистика":
        cursor.execute("SELECT COUNT(*) FROM subscriptions")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE end_date > ?", (datetime.now().isoformat(),))
        active = cursor.fetchone()[0]
        await message.answer(f"Всего пользователей: {total}\nАктивных подписок: {active}", reply_markup=admin_kb())
    elif message.text == "📢 Рассылка":
        await message.answer("✉️ Отправьте текст для рассылки активным подписчикам.", reply_markup=admin_kb())
    elif message.text == "➕ Выдать подписку":
        await message.answer("Введите в формате: `@username 30` — для выдачи на 30 дней.", reply_markup=admin_kb())
    elif message.text.startswith("@"):
        try:
            username, days = message.text.strip().split()
            days = int(days)
            cursor.execute("SELECT user_id FROM subscriptions WHERE username = ?", (username,))
            row = cursor.fetchone()
            if not row:
                await message.answer(f"Пользователь {username} не найден.", reply_markup=admin_kb())
                return
            user_id = row[0]
            end_date = datetime.now() + timedelta(days=days)
            cursor.execute("UPDATE subscriptions SET end_date = ? WHERE user_id = ?", (end_date.isoformat(), user_id))
            conn.commit()
            await message.answer(f"✅ Подписка выдана {username} на {days} дней.", reply_markup=admin_kb())
            try:
                await bot.send_message(user_id, f"🎉 Ваша подписка активирована на {days} дней!")
            except:
                await message.answer("❗ Не удалось отправить сообщение пользователю.")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_kb())
    else:
        cursor.execute("SELECT user_id, end_date FROM subscriptions")
        rows = cursor.fetchall()
        sent = 0
        for uid, end_date in rows:
            try:
                if datetime.fromisoformat(end_date) > datetime.now():
                    await bot.send_message(uid, message.text)
                    sent += 1
            except:
                continue
        await message.answer(f"📨 Сообщение отправлено {sent} пользователям.", reply_markup=admin_kb())

@dp.message_handler(lambda m: m.from_user.id != ADMIN_ID)
async def user_handler(message: types.Message):
    add_user(message.from_user)
    user_id = message.from_user.id
    if message.text == "/start":
        await message.answer("👋 Привет! Нажмите «🔍 Проверить подписку».", reply_markup=user_kb())
    elif message.text == "🔍 Проверить подписку":
        cursor.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            end_date = datetime.fromisoformat(result[0])
            now = datetime.now()
            if end_date > now:
                delta = end_date - now
                await message.answer(f"✅ Подписка активна.\nОсталось: {delta.days} дней и {delta.seconds // 3600} часов.", reply_markup=user_kb())
            else:
                await message.answer("🔒 Подписка не активна. Свяжитесь с @intonusmd", reply_markup=user_kb())
        else:
            await message.answer("🔒 Подписка не найдена. Свяжитесь с @intonusmd", reply_markup=user_kb())
    else:
        await message.answer("Выберите действие из меню.", reply_markup=user_kb())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(clean_expired())
    try:
        executor.start_polling(dp, skip_updates=True)
    finally:
        conn.close()
