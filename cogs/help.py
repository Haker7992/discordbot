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


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_cmd(self, ctx):
        await ctx.send(embed=build_help_embed())

    @app_commands.command(name="help", description="Показать список команд")
    async def slash_help(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_help_embed())


async def setup(bot):
    await bot.add_cog(Help(bot))
