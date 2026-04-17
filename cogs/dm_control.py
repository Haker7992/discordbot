import discord
from discord.ext import commands
from discord import app_commands
from utils.checks import is_owner_id
from utils.embeds import success, error, info
from config import COLORS
import sqlite3, os, time, datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '../guard.db')
selected_guild: dict = {}


def _save_replied(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS dm_replied (user_id TEXT PRIMARY KEY, last_reply INTEGER NOT NULL)")
        conn.execute("INSERT OR REPLACE INTO dm_replied (user_id, last_reply) VALUES (?,?)", (str(user_id), int(time.time())))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _save_replied_bulk(user_ids):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS dm_replied (user_id TEXT PRIMARY KEY, last_reply INTEGER NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS dm_history (user_id TEXT PRIMARY KEY, last_dm INTEGER NOT NULL)")
        ts = int(time.time())
        conn.executemany("INSERT OR REPLACE INTO dm_replied (user_id, last_reply) VALUES (?,?)", [(str(uid), ts) for uid in user_ids])
        conn.executemany("INSERT OR REPLACE INTO dm_history (user_id, last_dm) VALUES (?,?)", [(str(uid), ts) for uid in user_ids])
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DMSSCAN] Error: {e}")


def build_server_info(guild):
    embed = discord.Embed(title=f"📊 {guild.name}", color=COLORS["primary"])
    bots = sum(1 for m in guild.members if m.bot)
    embed.add_field(name="👥 Участники", value=f"`{guild.member_count}` (люди: `{guild.member_count-bots}`, боты: `{bots}`)", inline=False)
    embed.add_field(name="💬 Текст", value=f"`{len(guild.text_channels)}`", inline=True)
    embed.add_field(name="🔊 Войс", value=f"`{len(guild.voice_channels)}`", inline=True)
    embed.add_field(name="📁 Категорий", value=f"`{len(guild.categories)}`", inline=True)
    embed.add_field(name="🧵 Веток", value=f"`{len(guild.threads)}`", inline=True)
    embed.add_field(name="🏷️ Ролей", value=f"`{len(guild.roles)-1}`", inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


def owner_only():
    async def predicate(ctx):
        return is_owner_id(ctx.author.id)
    return commands.check(predicate)


class DmControl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Пересылаем ЛС owner'у
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild or message.author.bot:
            return
        if not is_owner_id(message.author.id):
            _save_replied(message.author.id)
            import config
            for owner_id in config.OWNER_IDS:
                try:
                    owner = await self.bot.fetch_user(owner_id)
                    embed = discord.Embed(title="📩 Новое ЛС боту", description=message.content or "*пусто*", color=0xFFD700)
                    embed.set_author(name=f"{message.author} ({message.author.id})", icon_url=message.author.display_avatar.url)
                    embed.timestamp = discord.utils.utcnow()
                    if message.attachments:
                        embed.add_field(name="📎 Вложения", value="\n".join(a.url for a in message.attachments))
                    await owner.send(embed=embed)
                except Exception:
                    pass

    def _get_guild(self, user_id):
        gid = selected_guild.get(user_id)
        if gid:
            return self.bot.get_guild(gid)
        if len(self.bot.guilds) == 1:
            return self.bot.guilds[0]
        return None

    def _no_guild_embed(self):
        guilds = self.bot.guilds
        desc = "\n".join(f"`{i+1}.` **{g.name}** — `{g.id}`" for i, g in enumerate(guilds))
        return error("Выбери сервер", f"Используй `!select <номер>`\n{desc}")

    # ── Prefix команды ──

    @commands.command(name="dmsscan")
    @owner_only()
    async def dmsscan_cmd(self, ctx):
        msg = await ctx.send(embed=info("Сканирование", "⏳ Сканирую..."))
        user_ids = {m.id for g in self.bot.guilds for m in g.members if not m.bot}
        _save_replied_bulk(user_ids)
        await msg.edit(embed=success("Готово", f"Добавлено: `{len(user_ids)}` участников."))

    @commands.command(name="servers")
    @owner_only()
    async def servers_cmd(self, ctx):
        desc = "\n".join(f"`{i+1}.` **{g.name}** — `{g.id}`" for i, g in enumerate(self.bot.guilds))
        await ctx.send(embed=info("Серверы бота", desc or "Нет серверов"))

    @commands.command(name="select")
    @owner_only()
    async def select_cmd(self, ctx, arg: str):
        guild = self.bot.get_guild(int(arg)) if arg.isdigit() else None
        if not guild and arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(self.bot.guilds):
                guild = self.bot.guilds[idx]
        if not guild:
            return await ctx.send(embed=error("Ошибка", f"Сервер `{arg}` не найден."))
        selected_guild[ctx.author.id] = guild.id
        await ctx.send(embed=success("Выбран", f"**{guild.name}**"))

    @commands.command(name="sban")
    @owner_only()
    async def sban_cmd(self, ctx, user_id: int, *, reason="Бан"):
        g = self._get_guild(ctx.author.id)
        if not g: return await ctx.send(embed=self._no_guild_embed())
        await g.ban(discord.Object(id=user_id), reason=reason)
        await ctx.send(embed=success("Бан", f"`{user_id}` забанен на **{g.name}**"))

    @commands.command(name="sunban")
    @owner_only()
    async def sunban_cmd(self, ctx, user_id: int):
        g = self._get_guild(ctx.author.id)
        if not g: return await ctx.send(embed=self._no_guild_embed())
        await g.unban(discord.Object(id=user_id))
        await ctx.send(embed=success("Разбан", f"`{user_id}` разбанен"))

    @commands.command(name="skick")
    @owner_only()
    async def skick_cmd(self, ctx, user_id: int, *, reason="Кик"):
        g = self._get_guild(ctx.author.id)
        if not g: return await ctx.send(embed=self._no_guild_embed())
        m = g.get_member(user_id) or await g.fetch_member(user_id)
        await m.kick(reason=reason)
        await ctx.send(embed=success("Кик", f"`{user_id}` кикнут"))

    @commands.command(name="smute")
    @owner_only()
    async def smute_cmd(self, ctx, user_id: int, minutes: int = 10):
        g = self._get_guild(ctx.author.id)
        if not g: return await ctx.send(embed=self._no_guild_embed())
        m = g.get_member(user_id) or await g.fetch_member(user_id)
        await m.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=minutes))
        await ctx.send(embed=success("Мьют", f"`{user_id}` замьючен на {minutes} мин."))

    @commands.command(name="sunmute")
    @owner_only()
    async def sunmute_cmd(self, ctx, user_id: int):
        g = self._get_guild(ctx.author.id)
        if not g: return await ctx.send(embed=self._no_guild_embed())
        m = g.get_member(user_id) or await g.fetch_member(user_id)
        await m.timeout(None)
        await ctx.send(embed=success("Размьют", f"`{user_id}` размьючен"))

    @commands.command(name="ssay")
    @owner_only()
    async def ssay_cmd(self, ctx, channel_id: int, *, text: str):
        g = self._get_guild(ctx.author.id)
        if not g: return await ctx.send(embed=self._no_guild_embed())
        ch = g.get_channel(channel_id)
        if not ch: return await ctx.send(embed=error("Ошибка", "Канал не найден."))
        await ch.send(text)
        await ctx.send(embed=success("Отправлено", f"В <#{channel_id}>"))

    @commands.command(name="sgiverole")
    @owner_only()
    async def sgiverole_cmd(self, ctx, user_id: int, role_id: int):
        g = self._get_guild(ctx.author.id)
        if not g: return await ctx.send(embed=self._no_guild_embed())
        m = g.get_member(user_id) or await g.fetch_member(user_id)
        r = g.get_role(role_id)
        await m.add_roles(r)
        await ctx.send(embed=success("Роль выдана", f"`{r.name}` → `{user_id}`"))

    @commands.command(name="stakerole")
    @owner_only()
    async def stakerole_cmd(self, ctx, user_id: int, role_id: int):
        g = self._get_guild(ctx.author.id)
        if not g: return await ctx.send(embed=self._no_guild_embed())
        m = g.get_member(user_id) or await g.fetch_member(user_id)
        r = g.get_role(role_id)
        await m.remove_roles(r)
        await ctx.send(embed=success("Роль снята", f"`{r.name}` снята"))

    @commands.command(name="smembers")
    @owner_only()
    async def smembers_cmd(self, ctx):
        g = self._get_guild(ctx.author.id)
        if not g: return await ctx.send(embed=self._no_guild_embed())
        members = [m for m in g.members if not m.bot]
        for i in range(0, len(members), 20):
            chunk = members[i:i+20]
            await ctx.send(embed=discord.Embed(
                title=f"👥 {g.name} ({i+1}-{min(i+20,len(members))} из {len(members)})",
                description="\n".join(f"`{m.id}` — **{m.display_name}**" for m in chunk),
                color=0xFFD700))

    @commands.command(name="dmnew")
    @owner_only()
    async def dmnew_cmd(self, ctx, *, text: str):
        from cogs.logger import _get_dm_history, _save_dm_history
        already = set(_get_dm_history())
        text = text.replace(" / ", "\n").replace("/", "\n")
        emb = discord.Embed(description=text, color=0xFFD700)
        emb.set_footer(text="ArchAngel Bot  •  DavaidKa")
        msg = await ctx.send(embed=info("Рассылка", "⏳ Отправляю..."))
        sent, skipped, failed = 0, 0, 0
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot: continue
                if member.id in already: skipped += 1; continue
                try:
                    await member.send(embed=emb)
                    _save_dm_history(member.id)
                    sent += 1
                except Exception:
                    failed += 1
        await msg.edit(embed=discord.Embed(
            title="✅ Готово",
            description=f"Отправлено: `{sent}` | Пропущено: `{skipped}` | Не доставлено: `{failed}`",
            color=0x2ECC71))

    @commands.command(name="serverinfo")
    async def serverinfo_cmd(self, ctx):
        g = ctx.guild or self._get_guild(ctx.author.id)
        if not g: return await ctx.send(embed=self._no_guild_embed())
        await ctx.send(embed=build_server_info(g))

    # ── Slash группа для управления сервером ──
    srv_group = app_commands.Group(name="srv", description="Управление сервером (owner)")

    @srv_group.command(name="info", description="Информация о сервере")
    async def slash_sinfo(self, interaction: discord.Interaction):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только owner."), ephemeral=True)
        g = interaction.guild or self._get_guild(interaction.user.id)
        if not g: return await interaction.response.send_message(embed=self._no_guild_embed(), ephemeral=True)
        await interaction.response.send_message(embed=build_server_info(g))

    @srv_group.command(name="members", description="Список участников сервера")
    async def slash_smembers(self, interaction: discord.Interaction):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только owner."), ephemeral=True)
        g = interaction.guild or self._get_guild(interaction.user.id)
        if not g: return await interaction.response.send_message(embed=self._no_guild_embed(), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        members = [m for m in g.members if not m.bot]
        lines = [f"`{m.id}` — **{m.display_name}**" for m in members[:20]]
        await interaction.followup.send(embed=discord.Embed(
            title=f"👥 {g.name} (первые {len(lines)} из {len(members)})",
            description="\n".join(lines), color=0xFFD700), ephemeral=True)

    @srv_group.command(name="ban", description="Забанить на сервере")
    @app_commands.describe(user_id="ID пользователя", reason="Причина")
    async def slash_sban(self, interaction: discord.Interaction, user_id: str, reason: str = "Бан"):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только owner."), ephemeral=True)
        g = interaction.guild or self._get_guild(interaction.user.id)
        if not g: return await interaction.response.send_message(embed=self._no_guild_embed(), ephemeral=True)
        await g.ban(discord.Object(id=int(user_id)), reason=reason)
        await interaction.response.send_message(embed=success("Бан", f"`{user_id}` забанен"), ephemeral=True)

    @srv_group.command(name="kick", description="Кикнуть с сервера")
    @app_commands.describe(user_id="ID пользователя")
    async def slash_skick(self, interaction: discord.Interaction, user_id: str):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только owner."), ephemeral=True)
        g = interaction.guild or self._get_guild(interaction.user.id)
        if not g: return await interaction.response.send_message(embed=self._no_guild_embed(), ephemeral=True)
        m = g.get_member(int(user_id)) or await g.fetch_member(int(user_id))
        await m.kick()
        await interaction.response.send_message(embed=success("Кик", f"`{user_id}` кикнут"), ephemeral=True)

    @srv_group.command(name="say", description="Написать в канал сервера")
    @app_commands.describe(channel_id="ID канала", text="Текст")
    async def slash_ssay(self, interaction: discord.Interaction, channel_id: str, text: str):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только owner."), ephemeral=True)
        g = interaction.guild or self._get_guild(interaction.user.id)
        if not g: return await interaction.response.send_message(embed=self._no_guild_embed(), ephemeral=True)
        ch = g.get_channel(int(channel_id))
        if not ch: return await interaction.response.send_message(embed=error("Ошибка", "Канал не найден."), ephemeral=True)
        await ch.send(text)
        await interaction.response.send_message(embed=success("Отправлено", f"В <#{channel_id}>"), ephemeral=True)

    @app_commands.command(name="serverinfo", description="Информация о сервере")
    async def slash_serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        if not g: return await interaction.response.send_message("Используй на сервере.", ephemeral=True)
        await interaction.response.send_message(embed=build_server_info(g))


async def setup(bot):
    await bot.add_cog(DmControl(bot))
