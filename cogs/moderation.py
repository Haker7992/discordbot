import discord
from discord.ext import commands
from discord import app_commands
from utils.checks import is_owner_or_admin
from utils.embeds import success, error, info
import database as db
import sqlite3, os, time

DB_PATH = os.path.join(os.path.dirname(__file__), '../guard.db')


def _init_warns():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS warns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT, user_id TEXT, reason TEXT, timestamp INTEGER
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS autorole (
        guild_id TEXT PRIMARY KEY, role_id TEXT
    )""")
    conn.commit()
    conn.close()


def _add_warn(guild_id, user_id, reason):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO warns (guild_id, user_id, reason, timestamp) VALUES (?,?,?,?)",
                 (str(guild_id), str(user_id), reason, int(time.time())))
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM warns WHERE guild_id=? AND user_id=?",
                         (str(guild_id), str(user_id))).fetchone()[0]
    conn.close()
    return count


def _get_warns(guild_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT reason, timestamp FROM warns WHERE guild_id=? AND user_id=? ORDER BY timestamp DESC",
                        (str(guild_id), str(user_id))).fetchall()
    conn.close()
    return rows


def _clear_warns(guild_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM warns WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id)))
    conn.commit()
    conn.close()


def _set_autorole(guild_id, role_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO autorole (guild_id, role_id) VALUES (?,?)", (str(guild_id), str(role_id)))
    conn.commit()
    conn.close()


def _get_autorole(guild_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT role_id FROM autorole WHERE guild_id=?", (str(guild_id),)).fetchone()
    conn.close()
    return int(row[0]) if row else None


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        _init_warns()

    # Авто-роль при входе
    @commands.Cog.listener()
    async def on_member_join(self, member):
        role_id = _get_autorole(member.guild.id)
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Авто-роль")
                except Exception:
                    pass

    # ── !clear ──
    @commands.command(name="clear")
    @commands.has_permissions(manage_messages=True)
    async def clear_cmd(self, ctx, amount: int = 10):
        if amount < 1 or amount > 100:
            return await ctx.send("Укажите число от 1 до 100.", delete_after=5)
        await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"✅ Удалено `{amount}` сообщений.", delete_after=3)

    @app_commands.command(name="clear", description="Удалить сообщения")
    @app_commands.describe(amount="Количество (1-100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def slash_clear(self, interaction: discord.Interaction, amount: int = 10):
        if amount < 1 or amount > 100:
            return await interaction.response.send_message("Укажите число от 1 до 100.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"✅ Удалено `{amount}` сообщений.", ephemeral=True)

    # ── !warn ──
    @commands.command(name="warn")
    @commands.has_permissions(moderate_members=True)
    async def warn_cmd(self, ctx, member: discord.Member, *, reason: str = "Нарушение правил"):
        count = _add_warn(ctx.guild.id, member.id, reason)
        await ctx.send(embed=success("Предупреждение", f"<@{member.id}> получил предупреждение #{count}\nПричина: {reason}"))
        if count >= 3:
            try:
                await member.ban(reason=f"Авто-бан: {count} предупреждений")
                await ctx.send(embed=discord.Embed(description=f"🔨 <@{member.id}> забанен за {count} предупреждения.", color=0xE74C3C))
            except Exception:
                pass

    @app_commands.command(name="warn", description="Выдать предупреждение")
    @app_commands.describe(member="Участник", reason="Причина")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def slash_warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Нарушение правил"):
        count = _add_warn(interaction.guild.id, member.id, reason)
        await interaction.response.send_message(embed=success("Предупреждение", f"<@{member.id}> — предупреждение #{count}\n{reason}"))
        if count >= 3:
            try:
                await member.ban(reason=f"Авто-бан: {count} предупреждений")
            except Exception:
                pass

    # ── !warns ──
    @commands.command(name="warns")
    async def warns_cmd(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        rows = _get_warns(ctx.guild.id, member.id)
        if not rows:
            return await ctx.send(embed=info("Предупреждения", f"У <@{member.id}> нет предупреждений."))
        desc = "\n".join(f"`{i+1}.` {r[0]}" for i, r in enumerate(rows))
        await ctx.send(embed=info(f"Предупреждения {member.display_name} ({len(rows)})", desc))

    @app_commands.command(name="warns", description="Посмотреть предупреждения")
    @app_commands.describe(member="Участник")
    async def slash_warns(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        rows = _get_warns(interaction.guild.id, member.id)
        if not rows:
            return await interaction.response.send_message(embed=info("Предупреждения", f"У <@{member.id}> нет предупреждений."))
        desc = "\n".join(f"`{i+1}.` {r[0]}" for i, r in enumerate(rows))
        await interaction.response.send_message(embed=info(f"Предупреждения {member.display_name} ({len(rows)})", desc))

    # ── !clearwarns ──
    @commands.command(name="clearwarns")
    @commands.has_permissions(moderate_members=True)
    async def clearwarns_cmd(self, ctx, member: discord.Member):
        _clear_warns(ctx.guild.id, member.id)
        await ctx.send(embed=success("Предупреждения сброшены", f"<@{member.id}> — предупреждения удалены."))

    # ── !slowmode ──
    @commands.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode_cmd(self, ctx, seconds: int = 0):
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send(embed=success("Slowmode", "Замедление отключено."))
        else:
            await ctx.send(embed=success("Slowmode", f"Замедление: `{seconds}` сек."))

    @app_commands.command(name="slowmode", description="Установить замедление канала")
    @app_commands.describe(seconds="Секунды (0 = выкл)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slash_slowmode(self, interaction: discord.Interaction, seconds: int = 0):
        await interaction.channel.edit(slowmode_delay=seconds)
        await interaction.response.send_message(embed=success("Slowmode", f"Замедление: `{seconds}` сек." if seconds else "Отключено."))

    # ── !lock / !unlock ──
    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock_cmd(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(embed=success("Канал закрыт", f"<#{ctx.channel.id}> закрыт."))

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock_cmd(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send(embed=success("Канал открыт", f"<#{ctx.channel.id}> открыт."))

    @app_commands.command(name="lock", description="Закрыть канал")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slash_lock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(embed=success("Канал закрыт", f"<#{interaction.channel.id}> закрыт."))

    @app_commands.command(name="unlock", description="Открыть канал")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slash_unlock(self, interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=None)
        await interaction.response.send_message(embed=success("Канал открыт", f"<#{interaction.channel.id}> открыт."))

    # ── !userinfo ──
    @commands.command(name="userinfo")
    async def userinfo_cmd(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        warns = _get_warns(ctx.guild.id, member.id)
        embed = discord.Embed(title=f"👤 {member.display_name}", color=0xFFD700)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Аккаунт создан", value=discord.utils.format_dt(member.created_at, "D"), inline=True)
        embed.add_field(name="Вошёл на сервер", value=discord.utils.format_dt(member.joined_at, "D"), inline=True)
        embed.add_field(name="Роли", value=" ".join(r.mention for r in member.roles[1:]) or "нет", inline=False)
        embed.add_field(name="⚠️ Предупреждений", value=f"`{len(warns)}`", inline=True)
        await ctx.send(embed=embed)

    @app_commands.command(name="userinfo", description="Информация о пользователе")
    @app_commands.describe(member="Участник")
    async def slash_userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        warns = _get_warns(interaction.guild.id, member.id)
        embed = discord.Embed(title=f"👤 {member.display_name}", color=0xFFD700)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Аккаунт создан", value=discord.utils.format_dt(member.created_at, "D"), inline=True)
        embed.add_field(name="Вошёл на сервер", value=discord.utils.format_dt(member.joined_at, "D"), inline=True)
        embed.add_field(name="Роли", value=" ".join(r.mention for r in member.roles[1:]) or "нет", inline=False)
        embed.add_field(name="⚠️ Предупреждений", value=f"`{len(warns)}`", inline=True)
        await interaction.response.send_message(embed=embed)

    # ── !roleinfo ──
    @commands.command(name="roleinfo")
    async def roleinfo_cmd(self, ctx, role: discord.Role):
        embed = discord.Embed(title=f"🏷️ {role.name}", color=role.color)
        embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="Участников", value=f"`{len(role.members)}`", inline=True)
        embed.add_field(name="Цвет", value=str(role.color), inline=True)
        embed.add_field(name="Позиция", value=f"`{role.position}`", inline=True)
        embed.add_field(name="Упоминаемая", value="Да" if role.mentionable else "Нет", inline=True)
        embed.add_field(name="Отображается отдельно", value="Да" if role.hoist else "Нет", inline=True)
        await ctx.send(embed=embed)

    @app_commands.command(name="roleinfo", description="Информация о роли")
    @app_commands.describe(role="Роль")
    async def slash_roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        embed = discord.Embed(title=f"🏷️ {role.name}", color=role.color)
        embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="Участников", value=f"`{len(role.members)}`", inline=True)
        embed.add_field(name="Цвет", value=str(role.color), inline=True)
        embed.add_field(name="Позиция", value=f"`{role.position}`", inline=True)
        await interaction.response.send_message(embed=embed)

    # ── !autorole ──
    @commands.command(name="autorole")
    @commands.has_permissions(administrator=True)
    async def autorole_cmd(self, ctx, role: discord.Role = None):
        if not role:
            role_id = _get_autorole(ctx.guild.id)
            if role_id:
                r = ctx.guild.get_role(role_id)
                return await ctx.send(embed=info("Авто-роль", f"Текущая: {r.mention if r else role_id}"))
            return await ctx.send(embed=info("Авто-роль", "Не установлена. Используй: `!autorole @role`"))
        _set_autorole(ctx.guild.id, role.id)
        await ctx.send(embed=success("Авто-роль", f"Установлена: {role.mention}"))

    @app_commands.command(name="autorole", description="Установить авто-роль при входе")
    @app_commands.describe(role="Роль")
    @app_commands.checks.has_permissions(administrator=True)
    async def slash_autorole(self, interaction: discord.Interaction, role: discord.Role):
        _set_autorole(interaction.guild.id, role.id)
        await interaction.response.send_message(embed=success("Авто-роль", f"Установлена: {role.mention}"))


async def setup(bot):
    await bot.add_cog(Moderation(bot))
