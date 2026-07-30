import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from google import genai
from google.genai import types
from google.genai.errors import ClientError
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


# === HTTP-сервер для Render ===
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
# ==============================

print("==> Бот запускается...", flush=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    print("ОШИБКА: Проверь GEMINI_API_KEY и TELEGRAM_BOT_TOKEN в Render!", flush=True)
    sys.exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# Порядок вызова моделей при превышении лимита (429)
GEMINI_MODELS = [
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
]

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
        "Пиши текстом или присылай фото — отвечу в своём стиле!\n\n"
        "/start — старт\n/clear — очистить контекст\n/help — помощь"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Бот работает на Gemini API (текст + фото).\n\n"
        "/clear — очистить историю диалога"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in chat_histories:
        del chat_histories[user_id]
    await update.message.reply_text("✅ История очищена!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_text = update.message.text or update.message.caption or ""

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    history = chat_histories.get(user_id, [])

    try:
        user_parts = []

        if update.message.photo:
            photo = update.message.photo[-1]
            photo_file = await photo.get_file()
            image_bytes = await photo_file.download_as_bytearray()
            user_parts.append(
                types.Part.from_bytes(data=bytes(image_bytes), mime_type="image/jpeg")
            )

        if user_text:
            user_parts.append(types.Part.from_text(text=user_text))

        if not user_parts:
            return

        user_content = types.Content(role="user", parts=user_parts)
        contents = list(history) + [user_content]

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
        )

        reply_text = None

        for model_name in GEMINI_MODELS:
            try:
                logger.info(f"Запрос к модели {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                reply_text = response.text
                if reply_text:
                    break
            except ClientError as e:
                if e.code == 429:
                    logger.warning(f"Лимит 429 на {model_name}, пробуем следующую...")
                    continue
                raise e
            except Exception as e:
                logger.warning(f"Ошибка на {model_name}: {e}")
                continue

        if not reply_text:
            await update.message.reply_text("⚠️ Превышен лимит запросов Gemini API. Попробуй через минуту.")
            return

        model_content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=reply_text)],
        )

        history.append(user_content)
        history.append(model_content)
        chat_histories[user_id] = history

        await update.message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Ошибка Gemini API: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Ошибка при запросе к ИИ.")


def main() -> None:
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("clear", clear_command))
        app.add_handler(
            MessageHandler(
                (filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message
            )
        )

        logger.info("Бот запущен, ожидаю сообщения...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Критическая ошибка запуска: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
