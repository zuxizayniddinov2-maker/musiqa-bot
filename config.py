import os
import re
from pathlib import Path
from dotenv import load_dotenv

# .env faylini yuklash
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8933069954:AAHNQLa7o3l6JOtJgC_iW3cYdB2Fl5ylesk")

# Admin foydalanuvchilar ID lari (standart egasi ID lari va qo'shimchalar)
raw_admins = os.getenv("ADMIN_IDS", "6720922604,8120807604")
ADMIN_IDS = {6720922604, 8120807604}
for a in raw_admins.split(","):
    a_clean = a.strip()
    if a_clean.isdigit():
        ADMIN_IDS.add(int(a_clean))

# Render.com va Web server sozlamalari
PORT = int(os.getenv("PORT", "8080"))
IS_RENDER = os.getenv("RENDER", "").lower() in ("true", "1") or "RENDER" in os.environ

# Papkalar
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = BASE_DIR / "bot_database.db"

# Cheklovlar
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
TEMP_FILE_LIFETIME = int(os.getenv("TEMP_FILE_LIFETIME_MINUTES", "30")) * 60

# URL regex andazalari
URL_PATTERN = re.compile(
    r'(https?://(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|'
    r'https?://[a-zA-Z0-9]+\.[^\s]{2,})',
    re.IGNORECASE
)

INSTAGRAM_PATTERN = re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/[\w-]+', re.IGNORECASE)
TIKTOK_PATTERN = re.compile(r'(?:https?://)?(?:(?:www|vm|vt)\.)?tiktok\.com/[\w/@.-]+', re.IGNORECASE)
YOUTUBE_PATTERN = re.compile(r'(?:https?://)?(?:(?:www|m)\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)[\w-]+', re.IGNORECASE)
