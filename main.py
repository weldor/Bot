import os
import sys
import logging
import base64
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI

# Настройка логирования
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# === Фоновый HTTP-сервер для Render ===
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
# ======================================

print("==> Бот запускается...", flush=True)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not OPENAI_API_KEY:
    print("ОШИБКА: OPENAI_API_KEY не задан", flush=True)
    sys.exit(1)
if not TELEGRAM_BOT_TOKEN:
    print("ОШИБКА: TELEGRAM_BOT_TOKEN не задан", flush=True)
    sys.exit(1)

# Подключение к OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_INSTRUCTION = (
    "Ты саркастичный и юморной друг для общения. "
    "Посмеёшься над мемами, видосами и картинками если они смешные. "
    "Поможешь советами если нужно, порекомендуешь что-то или объяснишь. "
    "Говори покороче и проще, как обычный человек — без пафоса и длинных лекций."
)

chat_histories: dict = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот на базе GPT-4. Напиши мне или пришли картинку/мем — отвечу без занудства.\n\n"
        "Команды:\n"
        "/start — приветствие\n"
        "/clear — очистить историю чата\n"
        "/help — помощь"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 *Как пользоваться:*\n\n"
        "Пиши текстом или присылай фото/мемы — я работаю на GPT-4o-mini и всё понимаю.\n\n"
        "Команды:\n"
        "/start — приветствие\n"
        "/clear — очистить историю чата\n"
        "/help — эта подсказка",
        parse_mode="Markdown"
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in chat_histories:
        del chat_histories[user_id]
    await update.message.reply_text("✅ История очищена. Начнём заново!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_text = update.message.text or update.message.caption or ""

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        content_payload = []

        # Если отправлено фото
        if update.message.photo:
            photo = update.message.photo[-1]
            photo_file = await photo.get_file()
            image_bytes = await photo_file.download_as_bytearray()
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            content_payload.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        if user_text:
            content_payload.append({"type": "text", "text": user_text})
        elif not content_payload:
            return

        # Получаем историю
        history = chat_histories.get(user_id, [])

        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
        messages.extend(history)
        messages.append({"role": "user", "content": content_payload})

        # Запрос к OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )

        reply_text = response.choices[0].message.content

        # Сохранение в историю (чтобы бот помнил контекст)
        history.append({"role": "user", "content": content_payload})
        history.append({"role": "assistant", "content": reply_text})
        chat_histories[user_id] = history

        await update.message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Ошибка OpenAI API: {e}")
        await update.message.reply_text("⚠️ Ошибка при обращении к GPT. Попробуй позже.")

def main() -> None:
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("clear", clear_command))
        app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))

        logger.info("Бот запущен, ожидаю сообщения...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Критическая ошибка запуска: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
