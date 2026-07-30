import os
import sys
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai
from google.genai import types
# Logging
# Logging — выводим в stdout чтобы Render видел логи
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)
print("==> Бот запускается...", flush=True)
# Токены читаются из переменных окружения — никаких значений в коде
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not GEMINI_API_KEY:
    raise ValueError("Переменная окружения GEMINI_API_KEY не задана")
    print("ОШИБКА: переменная GEMINI_API_KEY не задана", flush=True)
    sys.exit(1)
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Переменная окружения TELEGRAM_BOT_TOKEN не задана")
    print("ОШИБКА: переменная TELEGRAM_BOT_TOKEN не задана", flush=True)
    sys.exit(1)
print("==> Переменные окружения загружены", flush=True)
client = genai.Client(api_key=GEMINI_API_KEY)
SYSTEM_INSTRUCTION = (
