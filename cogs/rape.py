import discord
from discord.ext import commands
from discord import app_commands
import database as db
from utils.checks import is_owner_id
from utils.embeds import success, error, info
import time


def _owner_only():
    async def predicate(ctx):
        return is_owner_id(ctx.author.id)
    return commands.check(predicate)


class Rape(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Авто-бан при входе если в rape list ──
    @commands.Cog.listener()
    async def on_member_join(self, member):
        entry = db.get_rape(member.guild.id, member.id)
        if not entry:
            return
        reason = entry.get("reason") or "Rape list"
        ban_days = int(entry.get("ban_days", 0))
        try:
            await member.guild.ban(
                member,
                reason=f"Rape List: {reason}",
                delete_message_days=min(ban_days, 7)
            )
            db.log_action(member.guild.id, member.id, "rape_ban", reason)
            print(f"[RAPE] Забанен {member.id} при входе | {reason}")

            # Лог в ban_log канал
            settings = db.get_settings(member.guild.id)
            ch_id = settings.get("log_channel")
            if ch_id:
                ch = member.guild.get_channel(int(ch_id))
                if ch:
                    embed = discord.Embed(title="🔒 Rape List — Авто-бан", color=0xE74C3C)
                    embed.add_field(name="Участник", value=f"{member.mention} (`{member.id}`)", inline=True)
                    embed.add_field(name="Причина", value=reason, inline=True)
                    embed.add_field(name="Удалить сообщений", value=f"`{ban_days}` дн.", inline=True)
                    embed.timestamp = discord.utils.utcnow()
                    await ch.send(embed=embed)
        except Exception as e:
            print(f"[RAPE BAN ERROR] {e}")

    # ── Prefix команды ──
    @commands.group(name="rape", invoke_without_command=True)
    @_owner_only()
    async def rape(self, ctx):
        await ctx.send(embed=info(
            "Rape List",
            "`!rape add <id> <дней> <причина>` — добавить\n"
            "`!rape remove <id>` — убрать\n"
            "`!rape list` — список\n"
            "`!rape ban <id> <дней> <причина>` — добавить и сразу забанить"
        ))

    @rape.command(name="add")
    @_owner_only()
    async def rape_add(self, ctx, user_id: int, ban_days: int = 0, *, reason: str = "Не указана"):
        db.add_rape(ctx.guild.id, user_id, reason, ban_days, ctx.author.id)
        # Если пользователь сейчас на сервере — баним сразу
        member = ctx.guild.get_member(user_id)
        if member:
            try:
                await ctx.guild.ban(member, reason=f"Rape List: {reason}", delete_message_days=min(ban_days, 7))
                db.log_action(ctx.guild.id, user_id, "rape_ban", reason)
                await ctx.send(embed=success(
                    "Rape List",
                    f"`{user_id}` добавлен в список и **немедленно забанен**.\n"
                    f"Причина: `{reason}` | Удалить сообщений: `{ban_days}` дн."
                ))
                return
            except Exception as e:
                print(f"[RAPE ADD BAN] {e}")
        await ctx.send(embed=success(
            "Rape List",
            f"`{user_id}` добавлен. При следующем входе будет забанен.\n"
            f"Причина: `{reason}` | Удалить сообщений: `{ban_days}` дн."
        ))

    @rape.command(name="ban")
    @_owner_only()
    async def rape_ban(self, ctx, user_id: int, ban_days: int = 0, *, reason: str = "Не указана"):
        """Добавляет в rape list и сразу банит."""
        db.add_rape(ctx.guild.id, user_id, reason, ban_days, ctx.author.id)
        try:
            await ctx.guild.ban(
                discord.Object(id=user_id),
                reason=f"Rape List: {reason}",
                delete_message_days=min(ban_days, 7)
            )
            db.log_action(ctx.guild.id, user_id, "rape_ban", reason)
            await ctx.send(embed=success(
                "Rape List — Бан",
                f"`{user_id}` добавлен в список и забанен.\n"
                f"Причина: `{reason}` | Удалить сообщений: `{ban_days}` дн."
            ))
        except discord.NotFound:
            await ctx.send(embed=success(
                "Rape List",
                f"`{user_id}` добавлен в список (пользователь не найден на сервере).\n"
                f"Причина: `{reason}`"
            ))
        except Exception as e:
            await ctx.send(embed=error("Ошибка", str(e)))

    @rape.command(name="remove")
    @_owner_only()
    async def rape_remove(self, ctx, user_id: int):
        entry = db.get_rape(ctx.guild.id, user_id)
        if not entry:
            return await ctx.send(embed=error("Rape List", f"`{user_id}` не в списке."))
        db.remove_rape(ctx.guild.id, user_id)
        await ctx.send(embed=success("Rape List", f"`{user_id}` удалён из списка."))

    @rape.command(name="list")
    @_owner_only()
    async def rape_list(self, ctx):
        entries = db.get_all_rape(ctx.guild.id)
        if not entries:
            return await ctx.send(embed=info("Rape List", "Список пуст."))
        lines = []
        for e in entries:
            added = f"<t:{e['added_at']}:d>"
            lines.append(f"`{e['user_id']}` — {e['reason'] or '—'} | `{e['ban_days']}` дн. | {added}")
        # Разбиваем на страницы по 15
        for i in range(0, len(lines), 15):
            chunk = lines[i:i + 15]
            await ctx.send(embed=discord.Embed(
                title=f"🔒 Rape List ({i+1}–{min(i+15, len(lines))} из {len(lines)})",
                description="\n".join(chunk),
                color=0xE74C3C
            ))

    # ── Slash команды ──
    rape_group = app_commands.Group(name="rape", description="Rape list (только owner)")

    @rape_group.command(name="add", description="Добавить в rape list")
    @app_commands.describe(user_id="ID пользователя", ban_days="Удалить сообщений (дней, 0-7)", reason="Причина")
    async def slash_rape_add(self, interaction: discord.Interaction, user_id: str, ban_days: int = 0, reason: str = "Не указана"):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только owner."), ephemeral=True)
        uid = int(user_id)
        db.add_rape(interaction.guild.id, uid, reason, ban_days, interaction.user.id)
        member = interaction.guild.get_member(uid)
        if member:
            try:
                await interaction.guild.ban(member, reason=f"Rape List: {reason}", delete_message_days=min(ban_days, 7))
                db.log_action(interaction.guild.id, uid, "rape_ban", reason)
                return await interaction.response.send_message(embed=success(
                    "Rape List", f"`{uid}` добавлен и **немедленно забанен**.\nПричина: `{reason}`"
                ), ephemeral=True)
            except Exception:
                pass
        await interaction.response.send_message(embed=success(
            "Rape List", f"`{uid}` добавлен. При входе будет забанен.\nПричина: `{reason}` | `{ban_days}` дн."
        ), ephemeral=True)

    @rape_group.command(name="ban", description="Добавить в rape list и сразу забанить")
    @app_commands.describe(user_id="ID пользователя", ban_days="Удалить сообщений (дней, 0-7)", reason="Причина")
    async def slash_rape_ban(self, interaction: discord.Interaction, user_id: str, ban_days: int = 0, reason: str = "Не указана"):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только owner."), ephemeral=True)
        uid = int(user_id)
        db.add_rape(interaction.guild.id, uid, reason, ban_days, interaction.user.id)
        try:
            await interaction.guild.ban(discord.Object(id=uid), reason=f"Rape List: {reason}", delete_message_days=min(ban_days, 7))
            db.log_action(interaction.guild.id, uid, "rape_ban", reason)
            await interaction.response.send_message(embed=success(
                "Rape List — Бан", f"`{uid}` добавлен и забанен.\nПричина: `{reason}` | `{ban_days}` дн."
            ), ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message(embed=success(
                "Rape List", f"`{uid}` добавлен (не найден на сервере).\nПричина: `{reason}`"
            ), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=error("Ошибка", str(e)), ephemeral=True)

    @rape_group.command(name="remove", description="Убрать из rape list")
    @app_commands.describe(user_id="ID пользователя")
    async def slash_rape_remove(self, interaction: discord.Interaction, user_id: str):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только owner."), ephemeral=True)
        uid = int(user_id)
        entry = db.get_rape(interaction.guild.id, uid)
        if not entry:
            return await interaction.response.send_message(embed=error("Rape List", f"`{uid}` не в списке."), ephemeral=True)
        db.remove_rape(interaction.guild.id, uid)
        await interaction.response.send_message(embed=success("Rape List", f"`{uid}` удалён из списка."), ephemeral=True)

    @rape_group.command(name="list", description="Показать rape list")
    async def slash_rape_list(self, interaction: discord.Interaction):
        if not is_owner_id(interaction.user.id):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только owner."), ephemeral=True)
        entries = db.get_all_rape(interaction.guild.id)
        if not entries:
            return await interaction.response.send_message(embed=info("Rape List", "Список пуст."), ephemeral=True)
        lines = [
            f"`{e['user_id']}` — {e['reason'] or '—'} | `{e['ban_days']}` дн."
            for e in entries[:20]
        ]
        await interaction.response.send_message(embed=discord.Embed(
            title=f"🔒 Rape List ({len(entries)} записей)",
            description="\n".join(lines),
            color=0xE74C3C
        ), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Rape(bot))
