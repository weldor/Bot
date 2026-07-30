from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import os
import sys
import threading

from google import genai
from google.genai import types
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

# Клиент Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

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
        "🤖 Бот работает на Gemini 2.0 Flash (текст + фото).\n\n"
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

        # Обработка изображения
        if update.message.photo:
            photo = update.message.photo[-1]
            photo_file = await photo.get_file()
            image_bytes = await photo_file.download_as_bytearray()
            user_parts.append(
                types.Part.from_bytes(data=bytes(image_bytes), mime_type="image/jpeg")
            )

        # Обработка текста
        if user_text:
            user_parts.append(types.Part.from_text(text=user_text))

        if not user_parts:
            return

        # Создаем объект сообщения пользователя
        user_content = types.Content(role="user", parts=user_parts)

        # Собираем контекст для отправки
        contents = list(history) + [user_content]

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=config,
        )

        reply_text = response.text or "Ничего не могу сказать по этому поводу."

        # Создаем объект сообщения модели для сохранения в историю
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
