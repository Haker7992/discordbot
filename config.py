import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN", "")
PREFIX = os.getenv("PREFIX", "!")

# Поддержка нескольких owner через запятую в .env
# Пример: OWNER_IDS=123456789,987654321
_raw = os.getenv("OWNER_IDS", os.getenv("OWNER_ID", "0"))
OWNER_IDS = [int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()]
OWNER_ID = OWNER_IDS[0] if OWNER_IDS else 0  # главный owner (первый в списке)

DEFAULTS = {
    "ban_limit": 3,
    "kick_limit": 3,
    "mute_limit": 5,
    "channel_delete_limit": 2,
    "role_delete_limit": 2,
    "role_remove_limit": 5,
    "interval": 10,
    "punishment": "ban",
}

COLORS = {
    "primary":  0xFFD700,
    "success":  0x2ECC71,
    "danger":   0xE74C3C,
    "warning":  0xF39C12,
}
