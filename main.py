import discord
from discord.ext import commands
import asyncio
import config
import database

intents = discord.Intents.all()

async def get_prefix(bot, message):
    # На сервере и в ЛС: поддерживаем ! и .
    return ["!", "."]

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)
bot.invite_cache = {}
bot.unsetup_guilds = set()

COGS = ["cogs.antiraid", "cogs.whitelist", "cogs.protect", "cogs.settings", "cogs.help", "cogs.logger", "cogs.owner", "cogs.blacklist", "cogs.backup", "cogs.dm_control", "cogs.moderation", "cogs.antispam", "cogs.rape"]


LOG_CHANNELS = [
    ("🔨・баны-кики", "ban_log"),
    ("📥・входы-ливы", "join_log"),
    ("🏷️・роли", "role_log"),
    ("📁・каналы", "channel_log"),
    ("🔇・муты-ники", "mute_log"),
    ("⚙️・чат", "settings_channel"),
]

async def setup_log_channels(guild):
    """Создаёт категорию Logs и все каналы логов."""
    try:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        category = await guild.create_category(name="📊 Logs", overwrites=overwrites, position=999)
        channel_ids = {}
        for ch_name, key in LOG_CHANNELS:
            ch = await guild.create_text_channel(name=ch_name, category=category, overwrites=overwrites)
            channel_ids[key] = str(ch.id)

        database.update_setting(guild.id, "log_channel",           channel_ids["ban_log"])
        database.update_setting(guild.id, "role_log_channel",      channel_ids["role_log"])
        database.update_setting(guild.id, "channel_log_channel",   channel_ids["channel_log"])
        database.update_setting(guild.id, "mute_log_channel",      channel_ids["mute_log"])
        database.update_setting(guild.id, "whitelist_log_channel", channel_ids["ban_log"])
        database.update_setting(guild.id, "join_log_channel",      channel_ids["join_log"])
        database.update_setting(guild.id, "settings_channel",      channel_ids["settings_channel"])
        print(f"[SETUP] Лог-каналы созданы: {guild.name}")

        settings_ch = guild.get_channel(int(channel_ids["settings_channel"]))
        if settings_ch:
            embed = discord.Embed(
                title="🔐 ArchAngel Bot подключён",
                description=(
                    "```\n"
                    "!help          — список команд\n"
                    "!settings      — настройки защиты\n"
                    "!whitelist     — белый список\n"
                    "!protect       — защита ролей\n"
                    "!rape          — rape list\n"
                    "```"
                ),
                color=0x5865F2
            )
            await settings_ch.send(embed=embed)
        return channel_ids
    except Exception as e:
        print(f"[SETUP] Ошибка: {e}")
        return {}


async def delete_log_channels(guild):
    """Удаляет все лог-каналы и категорию."""
    # Помечаем что идёт unsetup — logger не будет восстанавливать каналы
    bot.unsetup_guilds.add(guild.id)

    settings = database.get_settings(guild.id)
    keys = ["log_channel", "role_log_channel", "channel_log_channel", "mute_log_channel", "whitelist_log_channel", "settings_channel"]
    # Сначала сбрасываем настройки
    for key in keys:
        try:
            database.update_setting(guild.id, key, "")
        except Exception:
            pass

    deleted_categories = set()
    for key in keys:
        ch_id = settings.get(key)
        if not ch_id:
            continue
        ch = guild.get_channel(int(ch_id))
        if ch:
            if ch.category:
                deleted_categories.add(ch.category)
            try:
                await ch.delete(reason="Unsetup")
            except Exception:
                pass

    await asyncio.sleep(0.5)
    for cat in deleted_categories:
        fresh_cat = guild.get_channel(cat.id)
        if fresh_cat and not fresh_cat.channels:
            try:
                await fresh_cat.delete(reason="Unsetup: категория пуста")
            except Exception:
                pass

    # Снимаем флаг после небольшой задержки чтобы все события успели обработаться
    await asyncio.sleep(2)
    bot.unsetup_guilds.discard(guild.id)


# ── Setup UI ──
class SetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="✅ Создать каналы", style=discord.ButtonStyle.success)
    async def do_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Только администраторы.", ephemeral=True)
        await interaction.response.edit_message(
            embed=discord.Embed(description="⏳ Создаю каналы...", color=0x5865F2),
            view=None
        )
        ids = await setup_log_channels(interaction.guild)
        lines = "\n".join(f"<#{v}>" for v in ids.values()) if ids else "—"
        await interaction.edit_original_response(embed=discord.Embed(
            title="✅ Готово",
            description=f"Категория `📊 Logs` создана.\n{lines}",
            color=0x57F287
        ))

    @discord.ui.button(label="🗑️ Удалить каналы", style=discord.ButtonStyle.danger)
    async def do_unsetup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Только администраторы.", ephemeral=True)
        await interaction.response.edit_message(
            embed=discord.Embed(description="⏳ Удаляю каналы...", color=0xE74C3C),
            view=None
        )
        await delete_log_channels(interaction.guild)
        await interaction.edit_original_response(embed=discord.Embed(
            title="🗑️ Готово", description="Лог-каналы удалены.", color=0x57F287
        ))

    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(description="Отменено.", color=0x99AAB5),
            view=None
        )


def _setup_embed(guild):
    settings = database.get_settings(guild.id)
    keys   = ["log_channel", "join_log_channel", "role_log_channel", "channel_log_channel", "mute_log_channel", "settings_channel"]
    labels = ["🔨 Баны/кики", "📥 Входы/ливы", "🏷️ Роли", "📁 Каналы", "🔇 Муты/ники", "⚙️ Чат"]
    lines = []
    for key, label in zip(keys, labels):
        ch_id = settings.get(key)
        val = f"<#{ch_id}>" if ch_id else "`не задан`"
        lines.append(f"{label}: {val}")
    embed = discord.Embed(title="⚙️ Setup — Лог-каналы", description="\n".join(lines), color=0x5865F2)
    return embed


@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_cmd(ctx):
    await ctx.send(embed=_setup_embed(ctx.guild), view=SetupView())


@bot.command(name="unsetup")
@commands.has_permissions(administrator=True)
async def unsetup_cmd(ctx):
    await delete_log_channels(ctx.guild)
    await ctx.send(embed=discord.Embed(title="🗑️ Готово", description="Лог-каналы удалены.", color=0x57F287))


@bot.tree.command(name="setup", description="Управление лог-каналами")
async def slash_setup(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Только администраторы.", ephemeral=True)
    await interaction.response.send_message(embed=_setup_embed(interaction.guild), view=SetupView(), ephemeral=True)


@bot.tree.command(name="unsetup", description="Удалить лог-каналы")
async def slash_unsetup(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Только администраторы.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    await delete_log_channels(interaction.guild)
    await interaction.followup.send(
        embed=discord.Embed(title="🗑️ Готово", description="Лог-каналы удалены.", color=0x57F287),
        ephemeral=True
    )


@bot.event
async def on_ready():
    print(f"[BOT] Запущен как {bot.user} | Серверов: {len(bot.guilds)}")
    print(f"[OWNER] OWNER_IDS = {config.OWNER_IDS}")
    try:
        synced = await bot.tree.sync()
        print(f"[SLASH] Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(f"[SLASH] Ошибка синхронизации: {e}")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{config.PREFIX}help | /help | ArchAngel Bot"
    ))


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)


COMMAND_USAGE = {
    "dmls":        "!dmls <user_id> — например: `!dmls 123456789`",
    "dmu":         "!dmu @user <текст> — например: `!dmu @DavaidKa Привет!`",
    "dm":          "!dm <текст> — например: `!dm Привет всем!`",
    "dmnew":       "!dmnew <текст> — например: `!dmnew Привет!`",
    "dmold":       "!dmold <текст> — например: `!dmold Привет!`",
    "ban":         "!ban @user [причина] — например: `!ban @user спам`",
    "unban":       "!unban <id> — например: `!unban 123456789`",
    "kick":        "!kick @user [причина]",
    "mute":        "!mute @user <минуты> — например: `!mute @user 10`",
    "unmute":      "!unmute @user",
    "giverole":    "!giverole @user @role",
    "takerole":    "!takerole @user @role",
    "giveroleall": "!giveroleall @role",
    "botadd":      "!botadd @bot",
    "permaban":    "!permaban <id> — например: `!permaban 123456789`",
    "inv":         "!inv <id> — например: `!inv 123456789`",
    "select":      "!select <id или номер> — например: `!select 1`",
    "blacklist":   "!blacklist add/remove/list @user",
    "whitelist":   "!whitelist add/remove/list/perms @user",
    "protect":     "!protect add/remove/list/roles @user",
    "restore":     "!restore [guild_id]",
    "ssay":        "!ssay <channel_id> <текст>",
    "sban":        "!sban <user_id>",
    "sgiverole":   "!sgiverole <user_id> <role_id>",
    "rape":        "!rape add/remove/list/ban <user_id> [дней] [причина]",
}


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        cmd = ctx.command.name if ctx.command else "команда"
        usage = COMMAND_USAGE.get(cmd, f"!{cmd} <аргументы>")
        embed = discord.Embed(
            title="⚠️ Не хватает аргумента",
            description=f"Вы не указали: **`{error.param.name}`**\n\n**Использование:**\n`{usage}`",
            color=0xF39C12
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.BadArgument):
        cmd = ctx.command.name if ctx.command else "команда"
        usage = COMMAND_USAGE.get(cmd, f"!{cmd} <аргументы>")
        embed = discord.Embed(
            title="❌ Неверный аргумент",
            description=f"**Использование:**\n`{usage}`",
            color=0xE74C3C
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.CheckFailure):
        pass  # молча игнорируем — включает _dm_only() и _owner_only()
    else:
        print(f"[ERROR] {error}")


async def main():
    database.init()
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"[COG] Loaded: {cog}")
            except Exception as e:
                print(f"[COG] Failed {cog}: {e}")
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
