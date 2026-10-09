import os
from datetime import timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Botdan foydalana oladigan Telegram ID'lar (vergul bilan). Bo'sh bo'lsa — hamma ulay oladi.
ALLOWED_OWNERS = {
    int(x) for x in os.getenv("ALLOWED_OWNERS", "").replace(" ", "").split(",") if x
}

DB_PATH = os.getenv("DB_PATH", "bot.db")

# Postgres (Supabase) — Render'da shart, chunki u yerda fayllar saqlanmaydi. Bo'sh bo'lsa — SQLite.
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Render: veb-sahifa porti (uyg'otish uchun) va Telegram'ga ulanishdan oldin kutish (soniya) —
# yangilanishda eski nusxa to'xtashini kutamiz, aks holda bitta sessiya ikki joyda ishlab qoladi.
PORT = int(os.getenv("PORT") or 0)
STARTUP_DELAY = int(os.getenv("STARTUP_DELAY") or 0)

# Papka rejimi (Premium'siz): my.telegram.org -> API development tools
API_ID = int(os.getenv("API_ID") or 0)
API_HASH = os.getenv("API_HASH", "")
FOLDER_NAME = os.getenv("FOLDER_NAME", "Mijozlar")
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "sessions")

# Gemini AI (ixtiyoriy): aistudio.google.com -> Get API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Birinchisi band/xato bo'lsa keyingisi sinaladi
GEMINI_MODELS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_MODELS", "gemini-3.5-flash,gemini-3.1-flash-lite,gemini-3.8-flash"
    ).split(",")
    if m.strip()
]

# O'zbekiston: UTC+5, yozgi vaqt yo'q
TZ = timezone(timedelta(hours=int(os.getenv("TZ_OFFSET", "5"))))

# Standart sozlamalar (har bir ega keyin botning o'zida o'zgartira oladi)
DEFAULT_REMIND_NEW = int(os.getenv("REMIND_NEW_MIN", "30"))
DEFAULT_REMIND_PROGRESS = int(os.getenv("REMIND_PROGRESS_MIN", "120"))
QUIET_FROM = int(os.getenv("QUIET_FROM_HOUR", "22"))
QUIET_TO = int(os.getenv("QUIET_TO_HOUR", "8"))
