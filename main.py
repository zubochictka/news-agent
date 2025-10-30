import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import aiohttp

# -----------------------------------------------
# Загрузка переменных окружения (.env)
# -----------------------------------------------
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    print("❗ Убедись, что TELEGRAM_TOKEN и OPENAI_API_KEY заданы в .env или в Render → Environment.")
    exit(1)

# -----------------------------------------------
# Логирование
# -----------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -----------------------------------------------
# Фоновая проверка новостей
# -----------------------------------------------
async def fetch_latest_news():
    """
    Заглушка: получаем последние новости (в реальности — через API или парсер).
    Здесь просто возвращаем фиктивную новость.
    """
    url = "https://api.currentsapi.services/v1/latest-news?language=en&apiKey=demo"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if "news" in data and len(data["news"]) > 0:
                    return data["news"][0]["title"]
                return "No news found."
    except Exception as e:
        logger.error(f"Ошибка при получении новостей: {e}")
        return None


async def check_and_send_news(app):
    """Фоновая задача — проверяет новости каждые 5 минут и отправляет пользователям."""
    bot_data = app.bot_data
    logger.info("🔁 Фоновая проверка новостей запущена.")
    last_sent = None

    while bot_data.get("auto_check", True):
        news_title = await fetch_latest_news()
        if news_title and news_title != last_sent:
            last_sent = news_title
            for chat_id in bot_data.get("chat_ids", []):
                try:
                    await app.bot.send_message(chat_id=chat_id, text=f"📰 {news_title}")
                    logger.info(f"Новость отправлена пользователю {chat_id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке новости пользователю {chat_id}: {e}")
        await asyncio.sleep(300)  # 5 минут

    logger.info("🛑 Фоновая проверка новостей остановлена.")


# -----------------------------------------------
# Команды Telegram
# -----------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    app = context.application
    bot_data = app.bot_data
    chat_id = update.effective_chat.id

    bot_data.setdefault("chat_ids", set()).add(chat_id)
    bot_data["auto_check"] = True

    # Запускаем фоновую задачу, если она не активна
    if not bot_data.get("news_task") or bot_data["news_task"].done():
        bot_data["news_task"] = asyncio.create_task(check_and_send_news(app))

    await update.message.reply_text(
        "🚀 Привет! Я новостной ИИ-агент.\n"
        "Я буду присылать важные новости, влияющие на крипторынок.\n"
        "Чтобы остановить рассылку — используй /stop."
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    app = context.application
    bot_data = app.bot_data
    bot_data["auto_check"] = False
    await update.message.reply_text("🛑 Автоматическая проверка новостей остановлена.")


async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последние новости вручную"""
    latest = await fetch_latest_news()
    if latest:
        await update.message.reply_text(f"📰 Последняя новость: {latest}")
    else:
        await update.message.reply_text("⚠️ Не удалось получить новости.")


# -----------------------------------------------
# Основная функция
# -----------------------------------------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("news", news))

    # Глобальные данные
    app.bot_data["chat_ids"] = set()
    app.bot_data["auto_check"] = True
    app.bot_data["news_task"] = None

    # Запускаем фоновую задачу
    loop = asyncio.get_event_loop()
    if not app.bot_data["news_task"]:
        app.bot_data["news_task"] = loop.create_task(check_and_send_news(app))

    logger.info("✅ Бот успешно запущен. Ожидаю команды в Telegram.")
    app.run_polling(stop_signals=None)  # чтобы Render не убивал процесс


if __name__ == "__main__":
    main()


