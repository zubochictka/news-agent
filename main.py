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
import json

# -----------------------------------------------
# Загрузка переменных окружения (.env)
# -----------------------------------------------
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    print("❗ TELEGRAM_TOKEN не задан")
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
async def fetch_cryptopanic_news():
    """
    Получает новости с CryptoPanic - нашего главного источника!
    """
    if not CRYPTOPANIC_API_KEY:
        logger.warning("❌ CRYPTOPANIC_API_KEY не задан - пропускаем CryptoPanic")
        return None
    
    # URL для получения важных новостей
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&kind=news&filter=important"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print("✅ Данные от CryptoPanic получены!")  # Для отладки
                    
                    # Проверяем, есть ли новости
                    if "results" in data and len(data["results"]) > 0:
                        latest_news = data["results"][0]  # Берем самую свежую новость
                        
                        # Формируем удобную структуру
                        return {
                            "title": latest_news.get("title", "Без заголовка"),
                            "url": latest_news.get("url", ""),
                            "source": "CryptoPanic",
                            "sentiment": latest_news.get("sentiment", "neutral"),  # bullish/bearish/neutral
                            "published_at": latest_news.get("published_at", "")
                        }
                    else:
                        print("ℹ️ Новостей нет в ответе")
                        return None
                else:
                    print(f"❌ Ошибка HTTP: {resp.status}")
                    return None
                    
    except Exception as e:
        logger.error(f"Ошибка при получении новостей с CryptoPanic: {e}")
        return None
async def fetch_latest_news():
    """
    Главная функция - получает новости из ВСЕХ источников
    """
    print("🔍 Ищу свежие новости...")
    
    # Пробуем получить новости с CryptoPanic (наш главный источник)
    crypto_news = await fetch_cryptopanic_news()
    if crypto_news:
        print(f"✅ Найдена крипто-новость: {crypto_news['title'][:50]}...")
        return crypto_news
    
    # Если CryptoPanic не сработал, можно добавить другие источники позже
    print("ℹ️ Новостей с CryptoPanic нет")
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



