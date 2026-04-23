import os
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

print("Checking imports...")
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    print("✓ python-telegram-bot imports OK")
except ImportError as e:
    print(f"✗ python-telegram-bot imports FAILED: {e}")

try:
    from google import genai
    from google.genai import types
    print("✓ google-genai imports OK")
except ImportError as e:
    print(f"✗ google-genai imports FAILED: {e}")

print("Checking Gemini client initialization...")
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("✓ Gemini client initialization OK")
    except Exception as e:
        print(f"✗ Gemini client initialization FAILED: {e}")
else:
    print("! GEMINI_API_KEY missing in .env")

print("Checking Telegram token...")
if not TOKEN:
    print("! TELEGRAM_BOT_TOKEN missing in .env")
else:
    print("✓ Telegram token found")
