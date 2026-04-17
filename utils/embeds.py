import discord

# Цветовая схема — тёмно-золотая тема ArchAngels
COLORS = {
    "primary":  0xFFD700,  # золотой — основной
    "success":  0x2ECC71,  # зелёный
    "danger":   0xE74C3C,  # красный
    "warning":  0xF39C12,  # оранжевый
    "gold":     0xFFD700,
    "purple":   0x9B59B6,
    "blue":     0x3498DB,
}

ICONS = {
    "success": "✅",
    "error":   "❌",
    "warning": "⚠️",
    "info":    "📋",
    "alert":   "🚨",
    "shield":  "🛡️",
    "crown":   "👑",
    "ban":     "🔨",
    "lock":    "🔐",
}


def _base(color, title, description, icon=""):
    embed = discord.Embed(
        title=f"{icon} {title}" if icon else title,
        description=description,
        color=color
    )
    return embed


def success(title, description):
    return _base(COLORS["success"], title, description, ICONS["success"])


def error(title, description):
    return _base(COLORS["danger"], title, description, ICONS["error"])


def warning(title, description):
    return _base(COLORS["warning"], title, description, ICONS["warning"])


def info(title, description):
    return _base(COLORS["blue"], title, description, ICONS["info"])


def alert(title, description, fields=None):
    embed = _base(COLORS["danger"], title, description, ICONS["alert"])
    if fields:
        for f in fields:
            embed.add_field(name=f["name"], value=f["value"], inline=f.get("inline", True))
    embed.timestamp = discord.utils.utcnow()
    return embed


def shield(title, description):
    return _base(COLORS["purple"], title, description, ICONS["shield"])
