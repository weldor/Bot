import os
import sys
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai
from google.genai import types

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

print("==> Бот запускается...", flush=True)

# Токены читаются из переменных окружения
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not GEMINI_API_KEY:
    print("ОШИБКА: переменная GEMINI_API_KEY не задана", flush=True)
    sys.exit(1)
if not TELEGRAM_BOT_TOKEN:
    print("ОШИБКА: переменная TELEGRAM_BOT_TOKEN не задана", flush=True)
    sys.exit(1)

print("==> Переменные окружения загружены", flush=True)

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("==> Gemini клиент создан", flush=True)
except Exception as e:
    print(f"ОШИБКА: не удалось создать Gemini клиент: {e}", flush=True)
    sys.exit(1)

SYSTEM_INSTRUCTION = (
    "Ты саркастичный и юморной друг для общения. "
    "Посмеёшься над мемами, видосами и картинками если они смешные. "
    "Поможешь советами если нужно, порекомендуешь что-то или объяснишь. "
    "Говори покороче и проще, как обычный человек — без пафоса и длинных лекций."
)

# История чата для каждого пользователя
chat_histories: dict = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start — приветствие."""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот с интеграцией Google Gemini AI. Напиши мне или пришли картинку/мем — "
        "отвечу как нормальный человек, без занудства.\n\n"
        "Команды:\n"
        "/start — приветствие\n"
        "/clear — очистить историю чата\n"
        "/help — помощь"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help — помощь."""
    await update.message.reply_text(
        "🤖 *Как пользоваться:*\n\n"
        "Просто пиши текстом или присылай фото/мемы — отвечу через Google Gemini AI.\n\n"
        "Бот помнит историю разговора в рамках сессии.\n\n"
        "Команды:\n"
        "/start — приветствие\n"
        "/clear — очистить историю чата\n"
        "/help — эта подсказка",
        parse_mode="Markdown"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /clear — сбросить историю чата."""
    user_id = update.effective_user.id
    if user_id in chat_histories:
        del chat_histories[user_id]
    await update.message.reply_text("✅ История очищена. Начнём заново!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка текстовых сообщений и изображений."""
    user_id = update.effective_user.id
    user_text = update.message.text or update.message.caption or ""

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        user_parts = []

        # Если пользователь отправил фото
        if update.message.photo:
            # Берем фото в наибольшем разрешении
            photo = update.message.photo[-1]
            photo_file = await photo.get_file()
            image_bytes = await photo_file.download_as_bytearray()

            # Добавляем изображение в детали запроса
            user_parts.append(
                types.Part.from_bytes(
                    data=bytes(image_bytes),
                    mime_type="image/jpeg"
                )
            )

        # Добавляем текст подписи или обычный текст
        if user_text:
            user_parts.append(types.Part(text=user_text))
        elif not user_parts:
            return  # Пропускаем, если сообщение не содержит ни текста, ни картинок

        history = chat_histories.get(user_id, [])

        # Формируем текущее сообщение
        current_user_content = types.Content(role="user", parts=user_parts)

        # Отправляем в Gemini (используем мультимодальную модель gemini-2.5-flash)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=history + [current_user_content],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            ),
        )

        reply_text = response.text

        # Сохраняем историю
        history.append(current_user_content)
        history.append(types.Content(role="model", parts=[types.Part(text=reply_text)]))
        chat_histories[user_id] = history

        await update.message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Ошибка Gemini API: {e}")
        await update.message.reply_text(
            "⚠️ Что-то пошло не так. Попробуй позже или /clear для сброса."
        )


def main() -> None:
    """Запуск бота."""
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("clear", clear_command))
        
        # Перехватываем как текстовые сообщения, так и фотографии
        app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, handle_message))

        logger.info("Бот запущен, ожидаю сообщения...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Критическая ошибка запуска: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
    "Поможешь советами если нужно, порекомендуешь что-то или объяснишь. "
    "Говори покороче и проще, как обычный человек — без пафоса и длинных лекций."
)

# История чата для каждого пользователя (сбрасывается при перезапуске бота)
chat_histories: dict = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start — приветствие."""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот с интеграцией Google Gemini AI. Напиши мне что угодно — "
        "отвечу как нормальный человек, без занудства.\n\n"
        "Команды:\n"
        "/start — приветствие\n"
        "/clear — очистить историю чата\n"
        "/help — помощь"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /help — помощь."""
    await update.message.reply_text(
        "🤖 *Как пользоваться:*\n\n"
        "Просто пиши — отвечу через Google Gemini AI.\n\n"
        "Бот помнит историю разговора в рамках сессии.\n\n"
        "Команды:\n"
        "/start — приветствие\n"
        "/clear — очистить историю чата\n"
        "/help — эта подсказка",
        parse_mode="Markdown"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /clear — сбросить историю чата."""
    user_id = update.effective_user.id
    if user_id in chat_histories:
        del chat_histories[user_id]
    await update.message.reply_text("✅ История очищена. Начнём заново!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка текстовых сообщений — отправка в Gemini и ответ."""
    user_id = update.effective_user.id
    user_text = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        history = chat_histories.get(user_id, [])

        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=history + [types.Content(
                role="user",
                parts=[types.Part(text=user_text)]
            )],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            ),
        )

        reply_text = response.text

        # Сохраняем историю
        history.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
        history.append(types.Content(role="model", parts=[types.Part(text=reply_text)]))
        chat_histories[user_id] = history

        await update.message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Ошибка Gemini API: {e}")
        await update.message.reply_text(
            "⚠️ Что-то пошло не так. Попробуй позже или /clear для сброса."
        )


def main() -> None:
    """Запуск бота."""
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("clear", clear_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        logger.info("Бот запущен, ожидаю сообщения...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Критическая ошибка запуска: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
