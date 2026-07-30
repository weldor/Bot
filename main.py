import os
import sys
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai
from google.genai import types

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

print("==> Бот запускается...", flush=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not GEMINI_API_KEY:
    print("ОШИБКА: переменная GEMINI_API_KEY не задана", flush=True)
    sys.exit(1)
if not TELEGRAM_BOT_TOKEN:
    print("ОШИБКА: переменная TELEGRAM_BOT_TOKEN не задана", flush=True)
    sys.exit(1)

print("==> Переменные окружения загружены", flush=True)

# ... (остальной код такой же)
