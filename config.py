import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Список ID администраторов
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

SHOP_NAME = os.getenv("SHOP_NAME", "Optimus Gang")
START_BALANCE = max(0, int(os.getenv("START_BALANCE", "50")))
DAILY_BONUS = max(0, int(os.getenv("DAILY_BONUS", "25")))

DB_PATH = BASE_DIR / "optimus_gang.db"
