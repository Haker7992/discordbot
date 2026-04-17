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


def _parse_duration(text: str):
    """'999d' -> (999, expires_at). Минимум 1d, максимум 999d."""
    match = re.fullmatch(r'(\d+)d', text.strip().lower())
    if not match:
        return None, None
    days = int(match.group(1))
    if days < 1:
        return None, None  # 0d не разрешён
    if days > 999:
        days = 999
    return days, int(time.time()) + days * 86400


def _expires_str(expires_at: int) -> str:
    if not expires_at:
        return "навсегда"
    return f"<t:{expires_at}:D> (<t:{expires_at}:R>)"


class Rape(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Авторебан при разбане ──
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        entry = db.get_rape(guild.id, user.id)
        if not entry:
            return
        expires_at = entry.get("expires_at", 0)
        if expires_at and time.time() > expires_at:
            db.remove_rape(guild.id, user.id)
            return
        import asyncio
        await asyncio.sleep(1)
        try:
            await guild.ban(user, reason=f"Rape List (авторебан): {entry.get('reason', '—')}")
            db.log_action(guild.id, user.id, "rape_reban", "авторебан")
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
            print(f"[RAPE REBAN] {e}")

    # ── Авто-бан при входе ──
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
            print(f"[RAPE BAN] {e}")

    # ══════════════════════════════════════════
    # .rape <id> <дней>d [причина]
    # Отвечает в тот же канал, не удаляет сообщение
    # ══════════════════════════════════════════

    @commands.group(name="rape", invoke_without_command=True)
    @_owner_only()
    async def rape(self, ctx, user: discord.User = None, duration: str = None, *, reason: str = "Не указана"):
        if user is None or duration is None:
            return await ctx.send(embed=info(
                "🔒 Rape List",
                "`.rape <id/@> <дней>d [причина]`\n"
                "`.unrape <id/@>` — убрать + разбанить\n"
                "`.rape list` — список\n\n"
                "Максимум: `999d`"
            ))

        user_id = user.id
        days, expires_at = _parse_duration(duration)
        if days is None:
            return await ctx.send(embed=error(
                "Ошибка формата",
                "Укажи дни: `1d` — `999d`"
            ))

        db.add_rape(ctx.guild.id, user_id, reason, 0, ctx.author.id, expires_at)

        try:
            await ctx.guild.ban(discord.Object(id=user_id), reason=f"Rape List: {reason}", delete_message_days=0)
            db.log_action(ctx.guild.id, user_id, "rape_ban", reason)
            await ctx.send(embed=success(
                "🔒 Rape List",
                f"**Участник:** {user.mention} (`{user_id}`)\n"
                f"**Причина:** {reason}\n"
                f"**До:** {_expires_str(expires_at)}\n"
                f"Забанен. При разбане — авторебан."
            ))
        except discord.NotFound:
            await ctx.send(embed=success(
                "🔒 Rape List",
                f"**ID:** `{user_id}`\n"
                f"**Причина:** {reason}\n"
                f"**До:** {_expires_str(expires_at)}\n"
                f"Не найден — добавлен в список."
            ))
        except Exception as e:
            await ctx.send(embed=error("Ошибка", str(e)))

    @rape.command(name="list")
    @_owner_only()
    async def rape_list(self, ctx):
        entries = db.get_all_rape(ctx.guild.id)
        if not entries:
            return await ctx.send(embed=info("Rape List", "Список пуст."))

        lines = []
        for e in entries:
            expires_at = e.get("expires_at", 0)
            if expires_at and time.time() > expires_at:
                db.remove_rape(ctx.guild.id, e["user_id"])
                continue
            lines.append(f"`{e['user_id']}` — {e['reason'] or '—'} | до {_expires_str(expires_at)}")

        if not lines:
            return await ctx.send(embed=info("Rape List", "Список пуст."))

        for i in range(0, len(lines), 15):
            await ctx.send(embed=discord.Embed(
                title=f"🔒 Rape List ({len(lines)} записей)",
                description="\n".join(lines[i:i+15]),
                color=0xE74C3C
            ))

    @rape.command(name="remove")
    @_owner_only()
    async def rape_remove(self, ctx, user: discord.User):
        entry = db.get_rape(ctx.guild.id, user.id)
        if not entry:
            return await ctx.send(embed=error("Rape List", f"{user.mention} не в списке."))
        db.remove_rape(ctx.guild.id, user.id)
        await ctx.send(embed=success("Rape List", f"{user.mention} удалён из списка. Авторебан отключён."))

    # .unrape <@юз или id> — убрать из списка И разбанить
    @commands.command(name="unrape")
    @_owner_only()
    async def unrape(self, ctx, user: discord.User):
        user_id = user.id
        entry = db.get_rape(ctx.guild.id, user_id)
        if not entry:
            return await ctx.send(embed=error("Rape List", f"{user.mention} не в списке."))

        db.remove_rape(ctx.guild.id, user_id)

        try:
            await ctx.guild.unban(discord.Object(id=user_id), reason="Rape List: снят owner'ом")
            await ctx.send(embed=success(
                "Rape List",
                f"{user.mention} удалён из списка и **разбанен**.\n"
                f"Авторебан отключён."
            ))
        except discord.NotFound:
            await ctx.send(embed=success(
                "Rape List",
                f"{user.mention} удалён из списка.\n"
                f"Не был забанен (или уже разбанен)."
            ))
        except Exception as e:
            await ctx.send(embed=error("Ошибка при разбане", str(e)))


async def setup(bot):
    await bot.add_cog(Rape(bot))
