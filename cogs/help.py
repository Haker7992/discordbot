import discord
from discord.ext import commands
from discord import app_commands
from config import PREFIX

GOLD = 0xFFD700
DARK = 0x2B2D31
PURPLE = 0x9B59B6


def build_help_embed():
    embed = discord.Embed(
        title="🔐  A R C H A N G E L  B O T",
        description=(
            "```ansi\n"
            "\u001b[1;33m  Система защиты сервера 24/7\u001b[0m\n"
            "```\n"
            f"**Префикс:** `{PREFIX}`  **|**  **Slash:** `/`"
        ),
        color=GOLD
    )

    embed.add_field(
        name="🚨  Авто-защита",
        value=(
            "```\n"
            "Бан/кик        → мгновенный бан исполнителя\n"
            "Удал. канала   → бан + авто-восстановление\n"
            "Удал. роли     → бан + авто-восстановление\n"
            "Изм. канала    → откат изменений\n"
            "5+ снятий ролей за 30с → бан\n"
            "5+ мьютов за 30с → снятие всех ролей\n"
            "Ссылка в чате  → удаление + таймаут 15м\n"
            "@everyone/@here → удаление сообщения\n"
            "```"
        ),
        inline=False
    )

    embed.add_field(
        name="✅  Whitelist",
        value=(
            f"`{PREFIX}whitelist add @user`\n"
            f"`{PREFIX}whitelist remove @user`\n"
            f"`{PREFIX}whitelist list`\n"
            f"`{PREFIX}whitelist perms @user`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "`/whitelist add/remove/list/perms`"
        ),
        inline=True
    )

    embed.add_field(
        name="🛡️  Защита ролей",
        value=(
            f"`{PREFIX}protect add @user`\n"
            f"`{PREFIX}protect remove @user`\n"
            f"`{PREFIX}protect list`\n"
            f"`{PREFIX}protect roles @user`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "`/protect add/remove/list/roles`"
        ),
        inline=True
    )

    embed.add_field(
        name="⚙️  Настройки",
        value=(
            f"`{PREFIX}settings` | `/settings menu`\n"
            f"`{PREFIX}setup` | `/setup`\n"
            f"`{PREFIX}unsetup` | `/unsetup`\n"
            f"`{PREFIX}serverinfo` | `/serverinfo`\n"
            f"`{PREFIX}backup` / `{PREFIX}restore`"
        ),
        inline=False
    )

    embed.add_field(
        name="🛡️  Модерация",
        value=(
            f"`{PREFIX}warn @user [причина]` | `/warn` — предупреждение\n"
            f"`{PREFIX}warns [@user]` | `/warns` — список предупреждений\n"
            f"`{PREFIX}clearwarns @user` — сбросить предупреждения\n"
            f"`{PREFIX}clear [кол-во]` | `/clear` — очистить чат\n"
            f"`{PREFIX}slowmode [сек]` | `/slowmode` — замедление\n"
            f"`{PREFIX}lock` | `/lock` — закрыть канал\n"
            f"`{PREFIX}unlock` | `/unlock` — открыть канал\n"
            f"`{PREFIX}userinfo [@user]` | `/userinfo` — инфо о пользователе\n"
            f"`{PREFIX}roleinfo @role` | `/roleinfo` — инфо о роли\n"
            f"`{PREFIX}autorole @role` | `/autorole` — авто-роль при входе"
        ),
        inline=False
    )
    embed.timestamp = discord.utils.utcnow()
    return embed


def build_info_embed(bot):
    embed = discord.Embed(
        title="🔐 ArchAngel Bot — Информация",
        description=(
            "Система защиты Discord-серверов 24/7.\n"
            "Автоматически защищает сервер от рейдов, спама и несанкционированных действий."
        ),
        color=GOLD
    )
    embed.add_field(
        name="🛡️ Авто-защита",
        value=(
            "• Бан/кик участника → мгновенный бан исполнителя\n"
            "• Удаление канала → бан + авто-восстановление\n"
            "• Удаление роли → бан + авто-восстановление\n"
            "• Переименование канала/роли → откат\n"
            "• Массовая выдача/снятие ролей → бан\n"
            "• Ссылки в чате → удаление + таймаут 15 мин\n"
            "• @everyone/@here → удаление сообщения\n"
            "• Добавление бота без прав → кик бота\n"
            "• Авто-ребан при разбане"
        ),
        inline=False
    )
    embed.add_field(
        name="✅ Whitelist",
        value=(
            "Гранулярные права для пользователей и ролей:\n"
            "`ban` `kick` `mute` `channels` `roles` `links` `mention_everyone` `invites` `all`\n"
            "Whitelist строго per-guild — права на одном сервере не переносятся на другой"
        ),
        inline=False
    )
    embed.add_field(
        name="🛡️ Защита ролей",
        value="Авто-возврат ролей при снятии для защищённых пользователей",
        inline=True
    )
    embed.add_field(
        name="🔒 Rape List",
        value="Список пользователей которые будут забанены при входе на сервер",
        inline=True
    )
    embed.add_field(
        name="📋 Логирование",
        value=(
            "• 🔨 Баны/кики\n"
            "• 📥 Входы/ливы\n"
            "• 🏷️ Выдача/снятие ролей\n"
            "• 📁 Создание/удаление каналов\n"
            "• 🔇 Муты, смена ников, войс\n"
            "• ✏️ Редактирование/удаление сообщений"
        ),
        inline=True
    )
    embed.add_field(
        name="💾 Backup",
        value="Авто-снапшот структуры сервера при добавлении бота. Восстановление командой `!restore`",
        inline=True
    )
    embed.add_field(
        name="🤖 Антиспам",
        value="5+ сообщений за 5 сек → таймаут 5 мин. 3+ упоминания ролей → таймаут 10 мин",
        inline=True
    )
    embed.add_field(
        name="⚙️ Настройки",
        value=(
            "`/settings menu` — лимиты, наказания, вкл/выкл защиту,\n"
            "вкл/выкл восстановление каналов и ролей"
        ),
        inline=False
    )
    guilds = len(bot.guilds) if bot else "—"
    members = sum(g.member_count for g in bot.guilds) if bot else "—"
    embed.set_footer(text=f"Серверов: {guilds} • Участников: {members} • Создатель: DavaidKa")
    embed.timestamp = discord.utils.utcnow()
    return embed


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_cmd(self, ctx):
        await ctx.send(embed=build_help_embed())

    @app_commands.command(name="help", description="Показать список команд")
    async def slash_help(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_help_embed())

    @commands.command(name="info")
    async def info_cmd(self, ctx):
        await ctx.send(embed=build_info_embed(self.bot))

    @app_commands.command(name="info", description="Информация о боте и его возможностях")
    async def slash_info(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_info_embed(self.bot))


async def setup(bot):
    await bot.add_cog(Help(bot))
