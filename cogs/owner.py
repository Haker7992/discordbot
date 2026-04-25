import discord
from discord.ext import commands
from discord import app_commands
import database as db
from utils.embeds import success, error, info
from utils.checks import is_owner_id
import config


def is_owner():
    async def predicate(ctx):
        return is_owner_id(ctx.author.id)
    return commands.check(predicate)


def build_owner_help():
    embed = discord.Embed(
        color=0xFFD700,
        description=(
            "```\n"
            "  ╔═══════════════════════════════╗\n"
            "  ║       👑  O W N E R          ║\n"
            "  ║    Только для создателей      ║\n"
            "  ╚═══════════════════════════════╝\n"
            "```"
        )
    )

    embed.add_field(
        name="🔨  Модерация",
        value=(
            "```yaml\n"
            "!ban  !unban  !kick\n"
            "!mute  !unmute  !permaban\n"
            "!inv  !giverole  !takerole\n"
            "!giveroleall  !botadd\n"
            "```"
        ),
        inline=True
    )

    embed.add_field(
        name="👑  Owner'ы",
        value=(
            "```yaml\n"
            "!addowner @user\n"
            "!removeowner @user\n"
            "!owners\n"
            "```"
        ),
        inline=True
    )

    embed.add_field(
        name="🔒  Rape List  [ префикс: . ]",
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
        name="📨  Рассылка",
        value=(
            "```yaml\n"
            "!dm  !dmold  !dmnew  !dmu\n"
            "/owner dm/dmold/dmnew/dmu\n"
            "```"
        ),
        inline=True
    )

    embed.add_field(
        name="📩  Управление сервером",
        value=(
            "```yaml\n"
            "!servers  !select\n"
            "!sban  !sunban  !skick\n"
            "!smute  !sunmute\n"
            "!ssay  !sgiverole  !smembers\n"
            "```"
        ),
        inline=True
    )

    embed.add_field(
        name="💬  ЛС",
        value=(
            "```yaml\n"
            "!dms  !replied\n"
            "!dmls <id>  !dmsscan\n"
            "```"
        ),
        inline=True
    )

    embed.add_field(
        name="⚙️  Прочее",
        value=(
            "```yaml\n"
            "!clearwl  !backup  !restore\n"
            "!blacklist  !botnick\n"
            "!ohelp  /owner help\n"
            "```"
        ),
        inline=True
    )

    embed.set_footer(text="ArchAngel Bot  ·  DavaidKa")
    embed.timestamp = discord.utils.utcnow()
    return embed


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Prefix команды — удаляем сообщение, отвечаем ephemeral через slash ──

    @commands.command(name="ohelp")
    @is_owner()
    async def ohelp_cmd(self, ctx):
        await ctx.send(embed=build_owner_help())

    @commands.command(name="ban")
    @is_owner()
    async def owner_ban(self, ctx, user: discord.User, *, reason="Бан от создателя"):
        await ctx.guild.ban(user, reason=reason)
        await ctx.message.delete()

    @commands.command(name="unban")
    @is_owner()
    async def owner_unban(self, ctx, user_id: int):
        await ctx.guild.unban(discord.Object(id=user_id))
        await ctx.message.delete()

    @commands.command(name="kick")
    @is_owner()
    async def owner_kick(self, ctx, member: discord.Member, *, reason="Кик от создателя"):
        await member.kick(reason=reason)
        await ctx.message.delete()

    @commands.command(name="mute")
    @is_owner()
    async def owner_mute(self, ctx, member: discord.Member, minutes: int = 10):
        import datetime
        await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=minutes))
        await ctx.message.delete()

    @commands.command(name="unmute")
    @is_owner()
    async def owner_unmute(self, ctx, member: discord.Member):
        await member.timeout(None)
        await ctx.message.delete()

    @commands.command(name="giverole")
    @is_owner()
    async def owner_giverole(self, ctx, member: discord.Member, role: discord.Role):
        await member.add_roles(role, reason="Owner: выдача роли")
        await ctx.message.delete()

    @commands.command(name="takerole")
    @is_owner()
    async def owner_takerole(self, ctx, member: discord.Member, role: discord.Role):
        await member.remove_roles(role, reason="Owner: снятие роли")
        await ctx.message.delete()

    @commands.command(name="dmls")
    @is_owner()
    async def dmls_cmd(self, ctx, user_id: int):
        """Показывает ЛС с пользователем и отправляет в ЛС owner'у."""
        try:
            u = await self.bot.fetch_user(user_id)
            dm = await u.create_dm()
            msgs = []
            async for m in dm.history(limit=30, oldest_first=False):
                who = "🤖 Бот" if m.author.bot else f"👤 {m.author.name}"
                msgs.append(f"**{who}:** {m.content or '*embed*'}")
            if not msgs:
                return await ctx.author.send("Сообщений нет.")
            embed = discord.Embed(
                title=f"📩 ЛС с {u.name} ({u.id})",
                description="\n".join(reversed(msgs))[:4000],
                color=0x5865F2
            )
            await ctx.author.send(embed=embed)
            if ctx.guild:
                await ctx.message.delete()
        except Exception as e:
            await ctx.author.send(f"❌ Ошибка: {e}")

    @commands.command(name="clearwl")
    @is_owner()
    async def clear_whitelist(self, ctx):
        for e in db.get_all_whitelist(ctx.guild.id):
            db.remove_whitelist(ctx.guild.id, e["user_id"])
        await ctx.message.delete()

    @commands.command(name="dms")
    @is_owner()
    async def dms_cmd(self, ctx):
        import sqlite3, os
        DB_PATH = os.path.join(os.path.dirname(__file__), '../guard.db')
        try:
            conn = sqlite3.connect(DB_PATH)
            # Объединяем обе таблицы
            rows = conn.execute("""
                SELECT user_id FROM dm_history
                UNION
                SELECT user_id FROM dm_replied
            """).fetchall()
            conn.close()
            user_ids = [int(r[0]) for r in rows]
        except Exception:
            user_ids = []
        if not user_ids:
            return await ctx.send("История ЛС пуста.")
        lines = []
        for uid in user_ids:
            try:
                u = await self.bot.fetch_user(uid)
                lines.append(f"`{uid}` — **{u.name}**")
            except Exception:
                lines.append(f"`{uid}` — неизвестен")
        for i in range(0, len(lines), 20):
            await ctx.send(embed=discord.Embed(
                title=f"📩 История ЛС ({i+1}-{min(i+20, len(lines))} из {len(lines)})",
                description="\n".join(lines[i:i+20]), color=0x5865F2))

    @commands.command(name="replied")
    @is_owner()
    async def replied_cmd(self, ctx):
        import sqlite3, os, time
        from datetime import datetime
        DB_PATH = os.path.join(os.path.dirname(__file__), '../guard.db')
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute("SELECT user_id, last_reply FROM dm_replied ORDER BY last_reply DESC").fetchall()
            conn.close()
        except Exception:
            rows = []
        if not rows:
            return await ctx.send("Никто ещё не отвечал боту.")
        lines = []
        for uid, ts in rows:
            try:
                u = await self.bot.fetch_user(int(uid))
                dt = datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
                lines.append(f"`{uid}` — **{u.name}** | {dt}")
            except Exception:
                lines.append(f"`{uid}` — неизвестен")
        for i in range(0, len(lines), 20):
            await ctx.send(embed=discord.Embed(
                title=f"📬 Ответили боту ({i+1}-{min(i+20, len(lines))} из {len(lines)})",
                description="\n".join(lines[i:i+20]), color=0x5865F2))

    @commands.command(name="permaban")
    @is_owner()
    async def permaban(self, ctx, user_id: int, *, reason="Перманентный бан"):
        await ctx.guild.ban(discord.Object(id=user_id), reason=reason)
        db.log_action(ctx.guild.id, user_id, "bot_ban", f"permaban: {reason}")
        await ctx.message.delete()

    @commands.command(name="dm")
    @is_owner()
    async def dm_all(self, ctx, *, text: str):
        """Отправляет сообщение всем участникам всех серверов в ЛС."""
        if ctx.guild:
            try:
                await ctx.message.delete()
            except Exception:
                pass
        from cogs.logger import _save_dm_history
        text = text.replace(" / ", "\n").replace("/", "\n")
        sent, failed = 0, 0
        msg = await ctx.send(embed=discord.Embed(description="⏳ Отправляю...", color=0x5865F2))
        embed = discord.Embed(description=text, color=0x5865F2)
        embed.set_footer(text="ArchAngel Bot | DavaidKa")
        seen = set()
        guilds = [ctx.guild] if ctx.guild else self.bot.guilds
        for guild in guilds:
            for member in guild.members:
                if member.bot or member.id in seen:
                    continue
                seen.add(member.id)
                try:
                    await member.send(embed=embed)
                    _save_dm_history(member.id)
                    sent += 1
                except Exception:
                    failed += 1
        await msg.edit(embed=discord.Embed(
            title="✅ Готово",
            description=f"Отправлено: `{sent}` | Не доставлено: `{failed}`",
            color=0x57F287
        ))

    @commands.command(name="botadd")
    @is_owner()
    async def botadd(self, ctx, bot_user: discord.Member):
        """Добавляет бота в whitelist с полными правами."""
        if not bot_user.bot:
            return await ctx.send(embed=error("Ошибка", "Это не бот."), delete_after=5)
        db.add_whitelist(ctx.guild.id, bot_user.id, ["all"])
        await ctx.send(embed=success("Бот добавлен", f"{bot_user.mention} добавлен в whitelist с полными правами."))

    @commands.command(name="giveroleall")
    @is_owner()
    async def giverole_all(self, ctx, role: discord.Role):
        """Выдаёт роль всем участникам сервера."""
        await ctx.message.delete()
        msg = await ctx.send(embed=discord.Embed(description=f"⏳ Выдаю {role.mention} всем...", color=0x5865F2))
        done, failed = 0, 0
        for member in ctx.guild.members:
            if member.bot or role in member.roles:
                continue
            try:
                await member.add_roles(role, reason="Owner: массовая выдача роли")
                done += 1
            except Exception:
                failed += 1
        await msg.edit(embed=discord.Embed(
            title="✅ Готово",
            description=f"Выдано: `{done}` | Ошибок: `{failed}`",
            color=0x57F287
        ))

    @commands.command(name="dmu")
    @is_owner()
    async def dm_user(self, ctx, user: discord.User, *, text: str):
        """Отправляет сообщение конкретному пользователю."""
        await ctx.message.delete()
        from cogs.logger import _save_dm_history
        try:
            await user.send(text)
            _save_dm_history(user.id)
            await ctx.send(embed=discord.Embed(description=f"✅ Отправлено <@{user.id}>", color=0x57F287), delete_after=5)
        except discord.Forbidden:
            await ctx.send("❌ ЛС закрыты.", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", delete_after=5)

    @commands.command(name="dmold")
    @is_owner()
    async def dm_old(self, ctx, *, text: str):
        """Отправляет сообщение всем кому бот писал раньше."""
        if ctx.guild:
            try:
                await ctx.message.delete()
            except Exception:
                pass
        from cogs.logger import _get_dm_history, _save_dm_history
        user_ids = _get_dm_history()
        if not user_ids:
            return await ctx.send("Нет истории DM.", delete_after=5)
        msg = await ctx.send(embed=discord.Embed(description="⏳ Отправляю...", color=0x5865F2))
        sent, failed = 0, 0
        for uid in user_ids:
            if uid in config.OWNER_IDS:
                continue
            try:
                user = await self.bot.fetch_user(uid)
                await user.send(text)
                sent += 1
            except Exception:
                failed += 1
        await msg.edit(embed=discord.Embed(
            title="✅ Готово",
            description=f"Отправлено: `{sent}` | Не доставлено: `{failed}`",
            color=0x57F287
        ))

    @commands.command(name="inv")
    @is_owner()
    async def inv_cmd(self, ctx, user_id: int):
        await ctx.message.delete()
        try:
            channel = ctx.guild.text_channels[0]
            invite = await channel.create_invite(max_uses=1, unique=True, reason="Owner: отправка инвайта")
            user = await self.bot.fetch_user(user_id)
            await user.send(f"Вас приглашают на сервер **{ctx.guild.name}**:\n{invite.url}")
        except discord.Forbidden:
            await ctx.send("❌ ЛС закрыты.", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {e}", delete_after=5)

    # ── Slash команды — все ephemeral ──
    owner_group = app_commands.Group(name="owner", description="Команды создателя бота")

    @owner_group.command(name="dmnew", description="Написать всем кому ещё не писал")
    @app_commands.describe(text="Текст сообщения")
    async def slash_dmnew(self, interaction: discord.Interaction, text: str):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.response.send_message(embed=discord.Embed(description="⏳ Отправляю...", color=0x5865F2), ephemeral=True)
        from cogs.logger import _get_dm_history, _save_dm_history
        already_sent = set(_get_dm_history())
        text = text.replace(" / ", "\n").replace("/", "\n")
        embed = discord.Embed(description=text, color=0x5865F2)
        embed.set_footer(text="ArchAngel Bot  •  DavaidKa")
        sent, skipped, failed = 0, 0, 0
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue
                if member.id in already_sent:
                    skipped += 1
                    continue
                try:
                    await member.send(embed=embed)
                    _save_dm_history(member.id)
                    sent += 1
                except Exception:
                    failed += 1
        await interaction.edit_original_response(embed=discord.Embed(
            title="✅ Готово",
            description=f"Отправлено: `{sent}` | Пропущено: `{skipped}` | Не доставлено: `{failed}`",
            color=0x2ECC71
        ))

    @owner_group.command(name="dmsscan", description="Добавить всех участников в историю ЛС")
    async def slash_dmsscan(self, interaction: discord.Interaction):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        from cogs.dm_control import _save_replied_bulk
        import asyncio
        user_ids = set()
        for guild in self.bot.guilds:
            for member in guild.members:
                if not member.bot:
                    user_ids.add(member.id)
        # Запускаем в executor чтобы не блокировать
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _save_replied_bulk, user_ids)
        await interaction.followup.send(embed=discord.Embed(
            title="✅ Готово", description=f"Добавлено: `{len(user_ids)}` участников.", color=0x57F287), ephemeral=True)    @owner_group.command(name="dmls", description="Просмотр ЛС с пользователем")
    @app_commands.describe(user_id="ID пользователя")
    async def slash_dmls(self, interaction: discord.Interaction, user_id: str):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            u = await self.bot.fetch_user(int(user_id))
            dm = await u.create_dm()
            msgs = []
            async for m in dm.history(limit=30, oldest_first=False):
                who = "🤖 Бот" if m.author.bot else f"👤 {m.author.name}"
                msgs.append(f"**{who}:** {m.content or '*embed*'}")
            if not msgs:
                return await interaction.followup.send("Сообщений нет.", ephemeral=True)
            embed = discord.Embed(
                title=f"📩 ЛС с {u.name} ({u.id})",
                description="\n".join(reversed(msgs))[:4000],
                color=0x5865F2
            )
            await interaction.user.send(embed=embed)
            await interaction.followup.send("✅ Отправлено в ЛС.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(embed=error("Ошибка", str(e)), ephemeral=True)

    @owner_group.command(name="dms", description="История ЛС бота")
    async def slash_dms(self, interaction: discord.Interaction):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        from cogs.logger import _get_dm_history
        user_ids = _get_dm_history()
        if not user_ids:
            return await interaction.followup.send("История ЛС пуста.", ephemeral=True)
        lines = []
        for uid in user_ids[:20]:
            try:
                u = await self.bot.fetch_user(uid)
                lines.append(f"`{uid}` — **{u.name}**")
            except Exception:
                lines.append(f"`{uid}` — неизвестен")
        await interaction.followup.send(embed=discord.Embed(
            title="📩 История ЛС", description="\n".join(lines), color=0x5865F2), ephemeral=True)

    @owner_group.command(name="replied", description="Кто отвечал боту")
    async def slash_replied(self, interaction: discord.Interaction):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        import sqlite3, os
        from datetime import datetime
        DB_PATH = os.path.join(os.path.dirname(__file__), '../guard.db')
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute("SELECT user_id, last_reply FROM dm_replied ORDER BY last_reply DESC LIMIT 20").fetchall()
            conn.close()
        except Exception:
            rows = []
        if not rows:
            return await interaction.followup.send("Никто не отвечал.", ephemeral=True)
        lines = []
        for uid, ts in rows:
            try:
                u = await self.bot.fetch_user(int(uid))
                dt = datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
                lines.append(f"`{uid}` — **{u.name}** | {dt}")
            except Exception:
                lines.append(f"`{uid}` — неизвестен")
        await interaction.followup.send(embed=discord.Embed(
            title="📬 Ответили боту", description="\n".join(lines), color=0x5865F2), ephemeral=True)

    @owner_group.command(name="help", description="Панель owner команд")
    async def slash_ohelp(self, interaction: discord.Interaction):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.response.send_message(embed=build_owner_help(), ephemeral=True)

    @owner_group.command(name="ban", description="Забанить пользователя")
    @app_commands.describe(user="Пользователь", reason="Причина")
    async def slash_ban(self, interaction: discord.Interaction, user: discord.User, reason: str = "Бан от создателя"):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.guild.ban(user, reason=reason)
        await interaction.response.send_message(embed=success("Бан", f"<@{user.id}> забанен."), ephemeral=True)

    @owner_group.command(name="unban", description="Разбанить пользователя")
    @app_commands.describe(user_id="ID пользователя")
    async def slash_unban(self, interaction: discord.Interaction, user_id: str):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.guild.unban(discord.Object(id=int(user_id)))
        await interaction.response.send_message(embed=success("Разбан", f"`{user_id}` разбанен."), ephemeral=True)

    @owner_group.command(name="kick", description="Кикнуть участника")
    @app_commands.describe(member="Участник", reason="Причина")
    async def slash_kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Кик от создателя"):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await member.kick(reason=reason)
        await interaction.response.send_message(embed=success("Кик", f"<@{member.id}> кикнут."), ephemeral=True)

    @owner_group.command(name="mute", description="Замьютить участника")
    @app_commands.describe(member="Участник", minutes="Минуты")
    async def slash_mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int = 10):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        import datetime
        await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=minutes))
        await interaction.response.send_message(embed=success("Мьют", f"<@{member.id}> замьючен на {minutes} мин."), ephemeral=True)

    @owner_group.command(name="unmute", description="Размьютить участника")
    @app_commands.describe(member="Участник")
    async def slash_unmute(self, interaction: discord.Interaction, member: discord.Member):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await member.timeout(None)
        await interaction.response.send_message(embed=success("Размьют", f"<@{member.id}> размьючен."), ephemeral=True)

    @owner_group.command(name="giverole", description="Выдать роль участнику")
    @app_commands.describe(member="Участник", role="Роль")
    async def slash_giverole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await member.add_roles(role, reason="Owner: выдача роли")
        await interaction.response.send_message(embed=success("Роль выдана", f"<@{member.id}> получил {role.mention}"), ephemeral=True)

    @owner_group.command(name="takerole", description="Снять роль с участника")
    @app_commands.describe(member="Участник", role="Роль")
    async def slash_takerole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await member.remove_roles(role, reason="Owner: снятие роли")
        await interaction.response.send_message(embed=success("Роль снята", f"<@{member.id}> лишён {role.mention}"), ephemeral=True)

    @owner_group.command(name="permaban", description="Перманентный бан с авторебаном")
    @app_commands.describe(user="Пользователь", reason="Причина")
    async def slash_permaban(self, interaction: discord.Interaction, user: discord.User, reason: str = "Перманентный бан"):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.guild.ban(user, reason=reason)
        db.log_action(interaction.guild.id, user.id, "bot_ban", f"permaban: {reason}")
        await interaction.response.send_message(embed=success("Перманентный бан", f"<@{user.id}> забанен навсегда."), ephemeral=True)

    @owner_group.command(name="botadd", description="Добавить бота в whitelist")
    @app_commands.describe(bot_user="Бот")
    async def slash_botadd(self, interaction: discord.Interaction, bot_user: discord.Member):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        if not bot_user.bot:
            return await interaction.response.send_message(embed=error("Ошибка", "Это не бот."), ephemeral=True)
        db.add_whitelist(interaction.guild.id, bot_user.id, ["all"])
        await interaction.response.send_message(embed=success("Бот добавлен", f"{bot_user.mention} добавлен в whitelist."), ephemeral=True)

    @owner_group.command(name="dmu", description="Отправить сообщение конкретному пользователю")
    @app_commands.describe(user="Пользователь", user_id="Или ID", text="Текст")
    async def slash_dm_user(self, interaction: discord.Interaction, text: str, user: discord.User = None, user_id: str = None):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        if not user and not user_id:
            return await interaction.response.send_message("Укажите пользователя или ID.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        from cogs.logger import _save_dm_history
        try:
            target = user or await self.bot.fetch_user(int(user_id))
            await target.send(text)
            _save_dm_history(target.id)
            await interaction.followup.send(embed=success("Отправлено", f"<@{target.id}> получил сообщение."), ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ ЛС закрыты.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)

    @owner_group.command(name="dmold", description="Сообщение всем кому бот писал раньше")
    @app_commands.describe(text="Текст сообщения")
    async def slash_dm_old(self, interaction: discord.Interaction, text: str):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.response.send_message(embed=discord.Embed(description="⏳ Отправляю...", color=0x5865F2), ephemeral=True)
        from cogs.logger import _get_dm_history
        user_ids = _get_dm_history()
        sent, failed = 0, 0
        for uid in user_ids:
            try:
                user = await self.bot.fetch_user(uid)
                await user.send(text)
                sent += 1
            except Exception:
                failed += 1
        await interaction.edit_original_response(embed=discord.Embed(
            title="✅ Готово",
            description=f"Отправлено: `{sent}` | Не доставлено: `{failed}`",
            color=0x57F287
        ))

    @owner_group.command(name="dm", description="Отправить сообщение всем участникам")
    @app_commands.describe(text="Текст сообщения")
    async def slash_dm_all(self, interaction: discord.Interaction, text: str):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        await interaction.response.send_message(embed=discord.Embed(description="⏳ Отправляю...", color=0x5865F2), ephemeral=True)
        sent, failed = 0, 0
        for member in interaction.guild.members:
            if member.bot:
                continue
            try:
                await member.send(text)
                sent += 1
            except Exception:
                failed += 1
        await interaction.edit_original_response(embed=discord.Embed(
            title="✅ Готово",
            description=f"Отправлено: `{sent}` | Не доставлено: `{failed}`",
            color=0x57F287
        ))

    @owner_group.command(name="inv", description="Отправить инвайт пользователю")
    @app_commands.describe(user="Упомяните пользователя", user_id="Или введите ID")
    async def slash_inv(self, interaction: discord.Interaction, user: discord.User = None, user_id: str = None):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для создателя."), ephemeral=True)
        if not user and not user_id:
            return await interaction.response.send_message("Укажите пользователя или ID.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            target = user or await self.bot.fetch_user(int(user_id))
            channel = interaction.guild.text_channels[0]
            invite = await channel.create_invite(max_uses=1, unique=True, reason="Owner: отправка инвайта")
            await target.send(f"Вас приглашают на сервер **{interaction.guild.name}**:\n{invite.url}")
            await interaction.followup.send(embed=success("Инвайт отправлен", f"<@{target.id}> получил инвайт."), ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ ЛС закрыты.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)

    # --- Переименование ботов на сервере ---
    @commands.command(name="botnick")
    @is_owner()
    async def botnick_cmd(self, ctx, bot_member: discord.Member, *, nick: str):
        """!botnick @бот <ник> — переименовать бота на сервере"""
        if not bot_member.bot:
            return await ctx.send(embed=error("Ошибка", "Это не бот."))
        try:
            await bot_member.edit(nick=nick, reason=f"Owner: переименование бота")
            await ctx.send(embed=success("Готово", f"Ник бота <@{bot_member.id}> изменён на `{nick}`"))
        except discord.Forbidden:
            await ctx.send(embed=error("Ошибка", "Нет прав для изменения ника этого бота."))
        except Exception as e:
            await ctx.send(embed=error("Ошибка", str(e)))

    # ── Управление owner'ами ──
    @commands.command(name="addowner")
    @is_owner()
    async def addowner_cmd(self, ctx, user: discord.User):
        """!addowner @user — добавить пользователя в список owner'ов"""
        if is_owner_id(user.id) and user.id not in config.OWNER_IDS:
            return await ctx.send(embed=error("Ошибка", f"<@{user.id}> уже является owner'ом."))
        if user.id in config.OWNER_IDS:
            return await ctx.send(embed=error("Ошибка", f"<@{user.id}> — главный owner, нельзя добавить повторно."))
        db.add_extra_owner(user.id, ctx.author.id)
        await ctx.send(embed=success("Owner добавлен", f"<@{user.id}> теперь owner бота."))

    @commands.command(name="removeowner")
    @is_owner()
    async def removeowner_cmd(self, ctx, user: discord.User):
        """!removeowner @user — убрать пользователя из owner'ов"""
        if user.id in config.OWNER_IDS:
            return await ctx.send(embed=error("Ошибка", f"<@{user.id}> — главный owner из `.env`, нельзя убрать командой."))
        db.remove_extra_owner(user.id)
        await ctx.send(embed=success("Owner удалён", f"<@{user.id}> больше не owner."))

    @commands.command(name="owners")
    @is_owner()
    async def owners_cmd(self, ctx):
        """!owners — список всех owner'ов"""
        main_owners = [f"<@{uid}> — `главный (.env)`" for uid in config.OWNER_IDS]
        extra = db.get_extra_owners()
        extra_owners = [f"<@{uid}> — `добавлен командой`" for uid in extra if uid not in config.OWNER_IDS]
        all_lines = main_owners + extra_owners
        if not all_lines:
            return await ctx.send(embed=error("Owners", "Список пуст."))
        await ctx.send(embed=discord.Embed(
            title="👑 Список Owner'ов",
            description="\n".join(all_lines),
            color=0xFFD700
        ))

    # ── Slash команды для owner'ов ──
    @owner_group.command(name="addowner", description="Добавить owner'а")
    @app_commands.describe(user="Пользователь")
    async def slash_addowner(self, interaction: discord.Interaction, user: discord.User):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для owner'ов."), ephemeral=True)
        if user.id in config.OWNER_IDS:
            return await interaction.response.send_message(embed=error("Ошибка", "Главный owner из `.env`."), ephemeral=True)
        db.add_extra_owner(user.id, interaction.user.id)
        await interaction.response.send_message(embed=success("Owner добавлен", f"<@{user.id}> теперь owner."), ephemeral=True)

    @owner_group.command(name="removeowner", description="Убрать owner'а")
    @app_commands.describe(user="Пользователь")
    async def slash_removeowner(self, interaction: discord.Interaction, user: discord.User):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для owner'ов."), ephemeral=True)
        if user.id in config.OWNER_IDS:
            return await interaction.response.send_message(embed=error("Ошибка", "Главный owner из `.env`, нельзя убрать командой."), ephemeral=True)
        db.remove_extra_owner(user.id)
        await interaction.response.send_message(embed=success("Owner удалён", f"<@{user.id}> больше не owner."), ephemeral=True)

    @owner_group.command(name="owners", description="Список всех owner'ов")
    async def slash_owners(self, interaction: discord.Interaction):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только для owner'ов."), ephemeral=True)
        main_owners = [f"<@{uid}> — `главный (.env)`" for uid in config.OWNER_IDS]
        extra = db.get_extra_owners()
        extra_owners = [f"<@{uid}> — `добавлен командой`" for uid in extra if uid not in config.OWNER_IDS]
        all_lines = main_owners + extra_owners
        await interaction.response.send_message(embed=discord.Embed(
            title="👑 Список Owner'ов",
            description="\n".join(all_lines) or "Пусто",
            color=0xFFD700
        ), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Owner(bot))
