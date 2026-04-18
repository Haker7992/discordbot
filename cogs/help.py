import discord
from discord.ext import commands
from discord import app_commands
from config import PREFIX

# ── Цвета ──
C_MAIN   = 0x5865F2   # Discord blurple
C_GOLD   = 0xFFD700
C_GREEN  = 0x57F287
C_RED    = 0xED4245
C_DARK   = 0x2B2D31


def build_help_embed():
    embed = discord.Embed(
        color=C_MAIN,
        description=(
            "```\n"
            "  ╔═══════════════════════════════╗\n"
            "  ║     🔐  A R C H A N G E L    ║\n"
            "  ║      Защита сервера 24/7      ║\n"
            "  ╚═══════════════════════════════╝\n"
            "```"
        )
    )

    embed.add_field(
        name="<:shield:> 🚨  Авто-защита",
        value=(
            "> 🔨 Бан/кик → мгновенный бан исполнителя\n"
            "> 📁 Удал. канала → бан + восстановление\n"
            "> 🏷️ Удал. роли → бан + восстановление\n"
            "> ✏️ Изм. канала/роли → откат\n"
            "> 🔗 Ссылка → удаление + таймаут 15м\n"
            "> 📢 @everyone → удаление\n"
            "> 🤖 Добавл. бота → кик"
        ),
        inline=False
    )

    embed.add_field(
        name="✅  Whitelist",
        value=(
            "```yaml\n"
            f"{PREFIX}whitelist add/remove/list/perms @user\n"
            f"{PREFIX}whitelist role add/remove/list/perms\n"
            "```"
        ),
        inline=True
    )

    embed.add_field(
        name="🛡️  Защита ролей",
        value=(
            "```yaml\n"
            f"{PREFIX}protect add/remove/list/roles @user\n"
            "```"
        ),
        inline=True
    )

    embed.add_field(
        name="🔒  Rape List",
        value=(
            "```yaml\n"
            ".rape <id/@> <дней>d [причина]\n"
            ".unrape <id/@>\n"
            ".rape list\n"
            "```"
        ),
        inline=False
    )

    embed.add_field(
        name="🛡️  Модерация",
        value=(
            "```yaml\n"
            f"{PREFIX}warn  {PREFIX}warns  {PREFIX}clearwarns\n"
            f"{PREFIX}clear  {PREFIX}slowmode\n"
            f"{PREFIX}lock  {PREFIX}unlock\n"
            f"{PREFIX}userinfo  {PREFIX}roleinfo  {PREFIX}autorole\n"
            "```"
        ),
        inline=True
    )

    embed.add_field(
        name="⚙️  Настройки",
        value=(
            "```yaml\n"
            f"{PREFIX}settings  /settings menu\n"
            f"{PREFIX}setup  {PREFIX}unsetup\n"
            f"{PREFIX}backup  {PREFIX}restore\n"
            f"{PREFIX}info  /info\n"
            "```"
        ),
        inline=True
    )

    embed.set_footer(text=f"!ohelp — панель owner  ·  Префикс: {PREFIX}  ·  Slash: /")
    embed.timestamp = discord.utils.utcnow()
    return embed


def build_info_embed(bot):
    guilds  = len(bot.guilds) if bot else "—"
    members = sum(g.member_count for g in bot.guilds) if bot else "—"

    embed = discord.Embed(
        color=C_MAIN,
        description=(
            "```\n"
            "  ╔═══════════════════════════════╗\n"
            "  ║     🔐  A R C H A N G E L    ║\n"
            "  ║      Система защиты 24/7      ║\n"
            "  ╚═══════════════════════════════╝\n"
            "```"
        )
    )

    embed.add_field(
        name="🚨  Авто-защита",
        value=(
            "> Бан/кик → мгновенный бан исполнителя\n"
            "> Удал. канала/роли → бан + восстановление\n"
            "> Изм. канала/роли → откат\n"
            "> 5+ ролей за 30с → бан\n"
            "> Ссылки → удаление + таймаут\n"
            "> @everyone → удаление\n"
            "> Добавл. бота → кик\n"
            "> Авторебан при разбане"
        ),
        inline=False
    )

    embed.add_field(
        name="✅  Whitelist",
        value=(
            "Гранулярные права per-guild:\n"
            "`ban` `kick` `mute` `channels`\n"
            "`roles` `links` `mention_everyone` `all`"
        ),
        inline=True
    )

    embed.add_field(
        name="🔒  Rape List",
        value=(
            "Перманентный бан с авторебаном.\n"
            "Максимум `999d`. При разбане\n"
            "бот банит обратно автоматически."
        ),
        inline=True
    )

    embed.add_field(
        name="📋  Логирование",
        value=(
            "> 🔨 Баны / кики / разбаны\n"
            "> 📥 Входы / ливы\n"
            "> 🏷️ Роли\n"
            "> 📁 Каналы\n"
            "> 🔇 Муты / ники / войс\n"
            "> ✏️ Сообщения"
        ),
        inline=True
    )

    embed.add_field(
        name="💾  Backup",
        value=(
            "Авто-снапшот при добавлении.\n"
            "Восстановление: `!restore`"
        ),
        inline=True
    )

    embed.add_field(
        name="🤖  Антиспам",
        value=(
            "5+ сообщений/5с → таймаут 5м\n"
            "3+ упоминания ролей → таймаут 10м"
        ),
        inline=True
    )

    embed.set_footer(text=f"Серверов: {guilds}  ·  Участников: {members}  ·  DavaidKa")
    embed.timestamp = discord.utils.utcnow()
    return embed


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_cmd(self, ctx):
        await ctx.send(embed=build_help_embed())

    @app_commands.command(name="help", description="Список команд")
    async def slash_help(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_help_embed())

    @commands.command(name="info")
    async def info_cmd(self, ctx):
        await ctx.send(embed=build_info_embed(self.bot))

    @app_commands.command(name="info", description="Информация о боте")
    async def slash_info(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_info_embed(self.bot))


async def setup(bot):
    await bot.add_cog(Help(bot))
