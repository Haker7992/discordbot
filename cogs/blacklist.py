import discord
from discord.ext import commands
from discord import app_commands
import database as db
from utils.embeds import success, error, info
from utils.checks import is_owner_id
import config

# Таблица blacklist в БД
def init_blacklist():
    import sqlite3, os
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), '../guard.db'))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            reason TEXT DEFAULT '',
            added_at INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dm_history (
            user_id TEXT PRIMARY KEY,
            last_dm INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_blacklist(guild_id, user_id, reason=''):
    import sqlite3, os, time
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), '../guard.db'))
    conn.execute("INSERT OR REPLACE INTO blacklist (guild_id, user_id, reason, added_at) VALUES (?,?,?,?)",
                 (str(guild_id), str(user_id), reason, int(time.time())))
    conn.commit()
    conn.close()

def remove_blacklist(guild_id, user_id):
    import sqlite3, os
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), '../guard.db'))
    conn.execute("DELETE FROM blacklist WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id)))
    conn.commit()
    conn.close()

def get_blacklist(guild_id, user_id):
    import sqlite3, os
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), '../guard.db'))
    row = conn.execute("SELECT * FROM blacklist WHERE guild_id=? AND user_id=?",
                       (str(guild_id), str(user_id))).fetchone()
    conn.close()
    return row

def get_all_blacklist(guild_id):
    import sqlite3, os
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), '../guard.db'))
    rows = conn.execute("SELECT * FROM blacklist WHERE guild_id=?", (str(guild_id),)).fetchall()
    conn.close()
    return rows


class Blacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        init_blacklist()

    # ── Слушаем сообщения ──
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if get_blacklist(message.guild.id, message.author.id):
            try:
                await message.delete()
            except Exception:
                pass

    # ── Слушаем вход в войс ──
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not after.channel:
            return
        if get_blacklist(member.guild.id, member.id):
            try:
                await member.edit(mute=True, reason="Blacklist: мьют микрофона")
                await member.move_to(None, reason="Blacklist: кик из войса")
            except Exception:
                pass

    # ── Prefix команды ──
    @commands.group(name="blacklist", invoke_without_command=True)
    async def blacklist_cmd(self, ctx):
        if not is_owner_id(ctx.author.id):
            return
        await ctx.send(embed=info("Blacklist", "Использование: `!blacklist add/remove/list`"))

    @blacklist_cmd.command(name="add")
    async def bl_add(self, ctx, user: discord.User, *, reason: str = ""):
        if not is_owner_id(ctx.author.id):
            return await ctx.message.delete()
        add_blacklist(ctx.guild.id, user.id, reason)
        await ctx.send(embed=success("Blacklist", f"<@{user.id}> добавлен в чёрный список."))

    @blacklist_cmd.command(name="remove")
    async def bl_remove(self, ctx, user: discord.User):
        if not is_owner_id(ctx.author.id):
            return await ctx.message.delete()
        remove_blacklist(ctx.guild.id, user.id)
        await ctx.send(embed=success("Blacklist", f"<@{user.id}> убран из чёрного списка."))

    @blacklist_cmd.command(name="list")
    async def bl_list(self, ctx):
        if not is_owner_id(ctx.author.id):
            return await ctx.message.delete()
        rows = get_all_blacklist(ctx.guild.id)
        if not rows:
            return await ctx.send(embed=info("Blacklist", "Чёрный список пуст."))
        desc = "\n".join(f"<@{r[1]}> — {r[2] or 'нет причины'}" for r in rows)
        await ctx.send(embed=info("🚫 Blacklist", desc))

    # ── Slash команды ──
    bl_group = app_commands.Group(name="blacklist", description="Чёрный список (только owner)")

    @bl_group.command(name="add", description="Добавить в чёрный список")
    @app_commands.describe(user="Пользователь", reason="Причина")
    async def slash_bl_add(self, interaction: discord.Interaction, user: discord.User, reason: str = ""):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        add_blacklist(interaction.guild.id, user.id, reason)
        await interaction.response.send_message(embed=success("Blacklist", f"<@{user.id}> добавлен в чёрный список."), ephemeral=True)

    @bl_group.command(name="remove", description="Убрать из чёрного списка")
    @app_commands.describe(user="Пользователь")
    async def slash_bl_remove(self, interaction: discord.Interaction, user: discord.User):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        remove_blacklist(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=success("Blacklist", f"<@{user.id}> убран из чёрного списка."), ephemeral=True)

    @bl_group.command(name="list", description="Показать чёрный список")
    async def slash_bl_list(self, interaction: discord.Interaction):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        rows = get_all_blacklist(interaction.guild.id)
        if not rows:
            return await interaction.response.send_message(embed=info("Blacklist", "Пуст."), ephemeral=True)
        desc = "\n".join(f"<@{r[1]}> — {r[2] or 'нет причины'}" for r in rows)
        await interaction.response.send_message(embed=info("🚫 Blacklist", desc), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Blacklist(bot))
