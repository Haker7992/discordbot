import discord
from discord.ext import commands
import database as db
from utils.checks import is_owner_id
from utils.embeds import success, error, info
import time
import re


def _owner_only():
    async def predicate(ctx):
        return is_owner_id(ctx.author.id)
    return commands.check(predicate)


def _get_guild(bot, user_id):
    try:
        from cogs.dm_control import selected_guild
        gid = selected_guild.get(user_id)
        if gid:
            return bot.get_guild(gid)
    except Exception:
        pass
    if len(bot.guilds) == 1:
        return bot.guilds[0]
    return None


def _no_guild_embed(bot):
    guilds = bot.guilds
    desc = "\n".join(f"`{i+1}.` **{g.name}** — `{g.id}`" for i, g in enumerate(guilds))
    return error("Выбери сервер", f"Используй `!select <номер>`\n{desc}")


def _dm_only():
    async def predicate(ctx):
        if ctx.guild:
            try:
                await ctx.message.delete()
            except Exception:
                pass
            return False
        return True
    return commands.check(predicate)


def _parse_duration(text: str):
    """
    Парсит строку вида '999d', '30d', '0d' (0 = навсегда).
    Возвращает (days: int, expires_at: int).
    expires_at = 0 означает навсегда.
    """
    match = re.fullmatch(r'(\d+)d', text.strip().lower())
    if not match:
        return None, None
    days = int(match.group(1))
    if days == 0:
        return 0, 0  # навсегда
    expires_at = int(time.time()) + days * 86400
    return days, expires_at


def _expires_str(expires_at: int) -> str:
    if not expires_at:
        return "навсегда"
    return f"<t:{expires_at}:D> (<t:{expires_at}:R>)"


class Rape(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Авторебан при разбане если в rape list и срок не истёк ──
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        entry = db.get_rape(guild.id, user.id)
        if not entry:
            return

        # Проверяем не истёк ли срок
        expires_at = entry.get("expires_at", 0)
        if expires_at and time.time() > expires_at:
            # Срок истёк — убираем из списка
            db.remove_rape(guild.id, user.id)
            print(f"[RAPE] Срок истёк для {user.id}, удалён из списка")
            return

        import asyncio
        await asyncio.sleep(1)
        try:
            await guild.ban(user, reason=f"Rape List (авторебан): {entry.get('reason', '—')}")
            db.log_action(guild.id, user.id, "rape_reban", "авторебан после разбана")
            print(f"[RAPE] Авторебан {user.id} на {guild.name}")

            settings = db.get_settings(guild.id)
            ch_id = settings.get("log_channel")
            if ch_id:
                ch = guild.get_channel(int(ch_id))
                if ch:
                    embed = discord.Embed(title="🔒 Rape List — Авторебан", color=0xE74C3C)
                    embed.add_field(name="Участник", value=f"{user.mention} (`{user.id}`)", inline=True)
                    embed.add_field(name="Причина", value=entry.get("reason") or "—", inline=True)
                    embed.add_field(name="До", value=_expires_str(expires_at), inline=True)
                    embed.timestamp = discord.utils.utcnow()
                    await ch.send(embed=embed)
        except Exception as e:
            print(f"[RAPE REBAN ERROR] {e}")

    # ── Авто-бан при входе если в rape list ──
    @commands.Cog.listener()
    async def on_member_join(self, member):
        entry = db.get_rape(member.guild.id, member.id)
        if not entry:
            return

        expires_at = entry.get("expires_at", 0)
        if expires_at and time.time() > expires_at:
            db.remove_rape(member.guild.id, member.id)
            return

        reason = entry.get("reason") or "Rape list"
        try:
            await member.guild.ban(member, reason=f"Rape List: {reason}", delete_message_days=0)
            db.log_action(member.guild.id, member.id, "rape_ban", reason)
            print(f"[RAPE] Забанен {member.id} при входе | {reason}")

            settings = db.get_settings(member.guild.id)
            ch_id = settings.get("log_channel")
            if ch_id:
                ch = member.guild.get_channel(int(ch_id))
                if ch:
                    embed = discord.Embed(title="🔒 Rape List — Авто-бан при входе", color=0xE74C3C)
                    embed.add_field(name="Участник", value=f"{member.mention} (`{member.id}`)", inline=True)
                    embed.add_field(name="Причина", value=reason, inline=True)
                    embed.add_field(name="До", value=_expires_str(expires_at), inline=True)
                    embed.timestamp = discord.utils.utcnow()
                    await ch.send(embed=embed)
        except Exception as e:
            print(f"[RAPE BAN ERROR] {e}")

    # ══════════════════════════════════════════
    # .rape <id> <дней>d <причина>
    # Только через ЛС бота
    # ══════════════════════════════════════════

    @commands.group(name="rape", invoke_without_command=True)
    @_owner_only()
    @_dm_only()
    async def rape(self, ctx, user_id: int = None, duration: str = None, *, reason: str = "Не указана"):
        if user_id is None or duration is None:
            return await ctx.send(embed=info(
                "🔒 Rape List",
                "**Использование:**\n"
                "`.rape <id> <дней>d [причина]`\n\n"
                "**Примеры:**\n"
                "`.rape 123456789 999d спам` — бан на 999 дней\n"
                "`.rape 123456789 0d` — бан навсегда\n\n"
                "`.unrape <id>` — убрать из списка\n"
                "`.rape list` — список\n\n"
                "При разбане — бот банит обратно автоматически."
            ))

        days, expires_at = _parse_duration(duration)
        if days is None:
            return await ctx.send(embed=error(
                "Ошибка формата",
                "Укажи дни в формате `<число>d`\n"
                "Например: `999d`, `30d`, `0d` (навсегда)"
            ))

        g = _get_guild(self.bot, ctx.author.id)
        if not g:
            return await ctx.send(embed=_no_guild_embed(self.bot))

        db.add_rape(g.id, user_id, reason, 0, ctx.author.id, expires_at)

        try:
            await g.ban(discord.Object(id=user_id), reason=f"Rape List: {reason}", delete_message_days=0)
            db.log_action(g.id, user_id, "rape_ban", reason)
            await ctx.send(embed=success(
                "🔒 Rape List",
                f"**ID:** `{user_id}`\n"
                f"**Сервер:** {g.name}\n"
                f"**Причина:** {reason}\n"
                f"**До:** {_expires_str(expires_at)}\n\n"
                f"Забанен. При разбане — авторебан."
            ))
        except discord.NotFound:
            await ctx.send(embed=success(
                "🔒 Rape List",
                f"**ID:** `{user_id}`\n"
                f"**Сервер:** {g.name}\n"
                f"**Причина:** {reason}\n"
                f"**До:** {_expires_str(expires_at)}\n\n"
                f"Не найден на сервере — добавлен в список.\n"
                f"При входе или разбане — забанит автоматически."
            ))
        except Exception as e:
            await ctx.send(embed=error("Ошибка", str(e)))

    @rape.command(name="list")
    @_owner_only()
    @_dm_only()
    async def rape_list(self, ctx):
        g = _get_guild(self.bot, ctx.author.id)
        if not g:
            return await ctx.send(embed=_no_guild_embed(self.bot))

        entries = db.get_all_rape(g.id)
        if not entries:
            return await ctx.send(embed=info("Rape List", f"Список пуст на **{g.name}**."))

        lines = []
        for e in entries:
            expires_at = e.get("expires_at", 0)
            # Проверяем не истёк ли срок
            if expires_at and time.time() > expires_at:
                db.remove_rape(g.id, e["user_id"])
                continue
            until = _expires_str(expires_at)
            lines.append(f"`{e['user_id']}` — {e['reason'] or '—'} | до {until}")

        if not lines:
            return await ctx.send(embed=info("Rape List", f"Список пуст на **{g.name}**."))

        for i in range(0, len(lines), 15):
            chunk = lines[i:i + 15]
            await ctx.send(embed=discord.Embed(
                title=f"🔒 Rape List — {g.name} ({len(lines)} записей)",
                description="\n".join(chunk),
                color=0xE74C3C
            ))

    @rape.command(name="remove")
    @_owner_only()
    @_dm_only()
    async def rape_remove(self, ctx, user_id: int):
        g = _get_guild(self.bot, ctx.author.id)
        if not g:
            return await ctx.send(embed=_no_guild_embed(self.bot))
        entry = db.get_rape(g.id, user_id)
        if not entry:
            return await ctx.send(embed=error("Rape List", f"`{user_id}` не в списке на **{g.name}**."))
        db.remove_rape(g.id, user_id)
        await ctx.send(embed=success(
            "Rape List",
            f"`{user_id}` удалён из списка на **{g.name}**.\n"
            f"Авторебан отключён."
        ))

    # .unrape <id> — алиас
    @commands.command(name="unrape")
    @_owner_only()
    @_dm_only()
    async def unrape(self, ctx, user_id: int):
        g = _get_guild(self.bot, ctx.author.id)
        if not g:
            return await ctx.send(embed=_no_guild_embed(self.bot))
        entry = db.get_rape(g.id, user_id)
        if not entry:
            return await ctx.send(embed=error("Rape List", f"`{user_id}` не в списке на **{g.name}**."))
        db.remove_rape(g.id, user_id)
        await ctx.send(embed=success(
            "Rape List",
            f"`{user_id}` удалён из списка на **{g.name}**.\n"
            f"Авторебан отключён."
        ))


async def setup(bot):
    await bot.add_cog(Rape(bot))
