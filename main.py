# main.py
import os
import asyncio
import feedparser
from datetime import datetime
from deep_translator import GoogleTranslator
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import openai

# ===== Получаем токены из переменных окружения (Replit Secrets) =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    print("❗ ПЕРЕД ПРОДОЛЖЕНИЕМ: установите TELEGRAM_TOKEN и OPENAI_API_KEY в переменных окружения.")
    raise SystemExit(1)

openai.api_key = OPENAI_API_KEY

# ===== Настройки =====
CHECK_INTERVAL_SECONDS = 60  # опрос RSS каждые 60 секунд
URL = "https://www.coindesk.com/arc/outboundfeeds/rss/"
KEYWORDS = [
    "bitcoin", "crypto", "ethereum", "blockchain",
    "white house", "biden", "trump", "sec", "fed",
    "interest rates", "inflation", "regulation", "us government"
]

translator = GoogleTranslator(source='en', target='ru')
latest_title = None

def log_news(title, summary, analysis):
    with open("news_log.txt", "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"{datetime.now().isoformat()}\n")
        f.write(f"Заголовок: {title}\n")
        f.write(f"Описание: {summary}\n")
        f.write(f"Анализ:\n{analysis}\n")

def get_latest_news():
    global latest_title
    feed = feedparser.parse(URL)
    for entry in feed.entries:
        text = f"{entry.title} {getattr(entry, 'summary', '')}".lower()
        if any(k.lower() in text for k in KEYWORDS):
            if latest_title != entry.title:
                latest_title = entry.title
                return entry
    return None

def analyze_with_gpt(title_ru: str, summary_ru: str) -> str:
    prompt = f"""
Новость (на русском): {title_ru}
Краткое описание: {summary_ru}

Проанализируй, как эта новость может повлиять на рынок криптовалют.
1) Дай одно слово: Позитивное / Негативное / Нейтральное.
2) Если в новости упоминается конкретная криптовалюта из топ-20 — укажи её название и дай рекомендацию: LONG или SHORT.
3) Коротко (1-2 предложения) поясни причину.

Ответ дай в формате:
Влияние: <Позитивное/Негативное/Нейтральное>
Монета: <название или 'нет'>
Рекомендация: <LONG/SHORT/нет>
Пояснение: <текст>
"""
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.0
        )
        return resp['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"❌ Ошибка анализа GPT: {e}"

async def check_and_send_news(app):
    print("🚀 Мониторинг новостей запущен.")
    while getattr(app, "auto_check", True):
        news = get_latest_news()
        if news:
            title_en = news.title
            summary_en = getattr(news, "summary", "")
            title_ru = translator.translate(title_en)
            summary_ru = translator.translate(summary_en)
            analysis = analyze_with_gpt(title_ru, summary_ru)
            log_news(title_ru, summary_ru, analysis)
            msg = (
                f"📰 *Новая новость:*\n\n"
                f"*{title_ru}*\n\n"
                f"{summary_ru}\n\n"
                f"🔗 {news.link}\n\n"
                f"🤖 *Анализ ИИ:*\n{analysis}"
            )
            print(f"Отправляю новость: {title_en}")
            for chat_id in app.chat_ids:
                try:
                    await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                except Exception as ex:
                    print("Ошибка отправки сообщения:", ex)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
    print("Авто-проверка остановлена.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    app = context.application
    if not hasattr(app, "chat_ids"):
        app.chat_ids = set()
    app.chat_ids.add(chat_id)
    app.auto_check = True
    # Запустим задачу (если ещё не запущена)
    if not hasattr(app, "news_task") or app.news_task.done():
        app.news_task = asyncio.create_task(check_and_send_news(app))
    await update.message.reply_text("🚀 Бот активирован. Я пришлю свежие важные новости с анализом.")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    app = context.application
    app.auto_check = False
    await update.message.reply_text("🛑 Авто-проверка приостановлена. Введите /start для возобновления.")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news = get_latest_news()
    if not news:
        await update.message.reply_text("📭 Нет новых новостей прямо сейчас.")
        return
    title_ru = translator.translate(news.title)
    summary_ru = translator.translate(getattr(news, "summary", ""))
    analysis = analyze_with_gpt(title_ru, summary_ru)
    log_news(title_ru, summary_ru, analysis)
    msg = (
        f"📰 *Новая новость:*\n\n"
        f"*{title_ru}*\n\n"
        f"{summary_ru}\n\n"
        f"🔗 {news.link}\n\n"
        f"🤖 *Анализ ИИ:*\n{analysis}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("news", news_command))
    app.chat_ids = set()
    app.auto_check = True
    print("✅ Бот запущен. Ожидаю команды в Telegram...")
    app.run_polling()

if __name__ == "__main__":
    main()
