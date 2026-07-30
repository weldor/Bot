import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import os
import sys
import threading

from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# === HTTP-сервер для проверки портов Render ===
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return


def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


threading.Thread(target=start_health_check_server, daemon=True).start()
# ===============================================

print("==> Бот запускается...", flush=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not GROQ_API_KEY or not TELEGRAM_BOT_TOKEN:
    print("ОШИБКА: Проверь переменные GROQ_API_KEY и TELEGRAM_BOT_TOKEN в Render!", flush=True)
    sys.exit(1)

client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

SYSTEM_INSTRUCTION = (
    "Ты саркастичный и юморной друг для общения. "
    "Посмеёшься над мемами и картинками, если они смешные. "
    "Поможешь советами, если нужно, порекомендуешь что-то или объяснишь. "
    "Говори покороче и проще, как обычный человек."
)

chat_histories: dict = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Задавай вопросы или присылай фото — отвечу без занудства.\n\n"
        "/start — старт\n/clear — очистить контекст\n/help — помощь"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Пиши текстом или отправляй картинки. История диалога сохраняется.\n\n"
        "/clear — сбросить память бота"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in chat_histories:
        del chat_histories[user_id]
    await update.message.reply_text("✅ Память очищена!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_text = update.message.text or update.message.caption or ""

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        content_payload = []
        is_vision = False

        if update.message.photo:
            is_vision = True
            photo = update.message.photo[-1]
            photo_file = await photo.get_file()
            image_bytes = await photo_file.download_as_bytearray()
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            content_payload.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
            })

        if user_text:
            content_payload.append({"type": "text", "text": user_text})
        elif not content_payload:
            return

        model_name = "llama-3.2-11b-vision-preview" if is_vision else "llama-3.3-70b-versatile"
        history = chat_histories.get(user_id, [])

        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
        messages.extend(history)
        messages.append({"role": "user", "content": content_payload})

        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )

        reply_text = response.choices[0].message.content

        history.append({"role": "user", "content": content_payload})
        history.append({"role": "assistant", "content": reply_text})
        chat_histories[user_id] = history

        await update.message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Ошибка Groq API: {e}")
        await update.message.reply_text("⚠️ Ошибка при запросе к ИИ.")


def main() -> None:
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("clear", clear_command))
        app.add_handler(
            MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message)
        )

        logger.info("Бот запущен, ожидаю сообщения...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Критическая ошибка запуска: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
