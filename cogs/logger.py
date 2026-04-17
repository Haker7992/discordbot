import discord
from discord.ext import commands
import asyncio
import time
import database as db
import sqlite3
import os
from utils.checks import is_whitelisted

# Кэш каналов: guild_id -> {channel_id: channel_data}
channel_cache: dict = {}
# Кэш ролей: guild_id -> {role_id: role_data}
role_cache: dict = {}

DB_PATH = os.path.join(os.path.dirname(__file__), '../guard.db')


def _save_dm_history(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO dm_history (user_id, last_dm) VALUES (?,?)",
                     (str(user_id), int(time.time())))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _get_dm_history():
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT user_id FROM dm_history").fetchall()
        conn.close()
        return [int(r[0]) for r in rows]
    except Exception:
        return []


async def get_log_channel(guild, key):
    settings = db.get_settings(guild.id)
    ch_id = settings.get(key)
    if not ch_id:
        return None
    return guild.get_channel(int(ch_id))


async def get_audit(guild, action, limit=3):
    await asyncio.sleep(0.5)
    try:
        async for entry in guild.audit_logs(limit=limit, action=action):
            if time.time() - entry.created_at.timestamp() < 5:
                return entry
    except Exception:
        pass
    return None


def _user_line(user):
    """Компактная строка пользователя."""
    return f"{user.mention} — **{user.display_name if hasattr(user, 'display_name') else user.name}** (`{user.id}`)"


class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Кэш при старте ──
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            channel_cache[guild.id] = {}
            for ch in guild.channels:
                channel_cache[guild.id][ch.id] = self._serialize(ch)
            role_cache[guild.id] = {}
            for role in guild.roles:
                if not role.is_default() and not role.managed:
                    role_cache[guild.id][role.id] = self._serialize_role(role)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if role.guild.id not in role_cache:
            role_cache[role.guild.id] = {}
        if not role.managed:
            role_cache[role.guild.id][role.id] = self._serialize_role(role)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if after.guild.id not in role_cache:
            role_cache[after.guild.id] = {}
        if not after.managed:
            role_cache[after.guild.id][after.id] = self._serialize_role(after)

    def _serialize_role(self, role):
        return {
            "name": role.name, "color": role.color.value,
            "hoist": role.hoist, "mentionable": role.mentionable,
            "permissions": role.permissions.value, "position": role.position
        }

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if channel.guild.id not in channel_cache:
            channel_cache[channel.guild.id] = {}
        channel_cache[channel.guild.id][channel.id] = self._serialize(channel)

    def _serialize(self, channel):
        data = {
            "name": channel.name, "type": channel.type,
            "position": channel.position,
            "category_id": channel.category_id if hasattr(channel, "category_id") else None,
            "overwrites": {
                str(t.id): {
                    "type": "role" if isinstance(t, discord.Role) else "member",
                    "allow": ow.pair()[0].value, "deny": ow.pair()[1].value,
                }
                for t, ow in channel.overwrites.items()
            }
        }
        if isinstance(channel, discord.TextChannel):
            data["topic"] = channel.topic
            data["nsfw"] = channel.nsfw
            data["slowmode"] = channel.slowmode_delay
        return data

    # ════════════════════════════════════════
    # 🔨 БАН / КИК / ЛИВ / ВХОД → ban_log
    # ════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        ch = await get_log_channel(guild, "log_channel")
        if not ch:
            return
        entry = await get_audit(guild, discord.AuditLogAction.ban)
        executor = entry.user if entry else None
        reason = (entry.reason if entry and entry.reason else "—")
        embed = discord.Embed(color=0xED4245, timestamp=discord.utils.utcnow())
        embed.set_author(name="🔨 БАН", icon_url=user.display_avatar.url)
        embed.description = (
            f"**Участник:** {_user_line(user)}\n"
            f"**Кто забанил:** {executor.mention if executor else '`Неизвестно`'}\n"
            f"**Причина:** {reason}"
        )
        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        ch = await get_log_channel(guild, "log_channel")
        if not ch:
            return
        entry = await get_audit(guild, discord.AuditLogAction.unban)
        executor = entry.user if entry else None
        embed = discord.Embed(color=0x57F287, timestamp=discord.utils.utcnow())
        embed.set_author(name="✅ РАЗБАН", icon_url=user.display_avatar.url)
        embed.description = (
            f"**Участник:** {_user_line(user)}\n"
            f"**Кто разбанил:** {executor.mention if executor else '`Неизвестно`'}"
        )
        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        ch = await get_log_channel(guild, "log_channel")
        if not ch:
            return
        entry = await get_audit(guild, discord.AuditLogAction.kick)
        if entry and entry.target and entry.target.id == member.id:
            embed = discord.Embed(color=0xFEE75C, timestamp=discord.utils.utcnow())
            embed.set_author(name="👢 КИК", icon_url=member.display_avatar.url)
            embed.description = (
                f"**Участник:** {_user_line(member)}\n"
                f"**Кто кикнул:** {entry.user.mention}\n"
                f"**Причина:** {entry.reason or '—'}"
            )
            await ch.send(embed=embed)
        else:
            join_ch = await get_log_channel(guild, "join_log_channel")
            if join_ch:
                embed = discord.Embed(color=0x99AAB5, timestamp=discord.utils.utcnow())
                embed.set_author(name="📤 ЛИВ", icon_url=member.display_avatar.url)
                embed.description = (
                    f"**Участник:** {_user_line(member)}\n"
                    f"**На сервере с:** {discord.utils.format_dt(member.joined_at, 'D') if member.joined_at else '—'}\n"
                    f"**Участников осталось:** `{guild.member_count}`"
                )
                await join_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild

        # Авто-роль
        role = discord.utils.find(
            lambda r: "member" in r.name.lower() or "ᴍᴇᴍʙᴇʀ" in r.name.lower(),
            guild.roles
        )
        if role:
            try:
                await member.add_roles(role, reason="Авто-роль при входе")
            except Exception:
                pass

        # Приветствие в ЛС
        try:
            embed = discord.Embed(
                title="# Привет дорогой друг!",
                description="**Рады видеть тебя в Архангелах!**\n\n**Бот создавал ебейший гениус DavaidKa**",
                color=0x5865F2
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            await member.send(embed=embed)
            _save_dm_history(member.id)
        except discord.Forbidden:
            pass

        # Лог входа
        ch = await get_log_channel(guild, "join_log_channel")
        if not ch:
            ch = await get_log_channel(guild, "log_channel")  # fallback
        if not ch:
            return
        embed = discord.Embed(color=0x2ECC71, timestamp=discord.utils.utcnow())
        embed.set_author(name="📥 ВХОД", icon_url=member.display_avatar.url)
        embed.description = (
            f"**Участник:** {_user_line(member)}\n"
            f"**Аккаунт создан:** {discord.utils.format_dt(member.created_at, 'D')}\n"
            f"**Участников на сервере:** `{guild.member_count}`"
        )
        await ch.send(embed=embed)

    # ════════════════════════════════════════
    # 🏷️ РОЛИ → role_log
    # ════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild = after.guild
        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]

        # Роли
        if added or removed:
            ch = await get_log_channel(guild, "role_log_channel")
            if ch:
                entry = await get_audit(guild, discord.AuditLogAction.member_role_update)
                executor = entry.user if entry else None
                who = executor.mention if executor else "`Неизвестно`"
                if added:
                    embed = discord.Embed(color=0x57F287, timestamp=discord.utils.utcnow())
                    embed.set_author(name="🏷️ РОЛЬ ВЫДАНА", icon_url=after.display_avatar.url)
                    embed.description = (
                        f"**Участник:** {_user_line(after)}\n"
                        f"**Роль:** {' '.join(r.mention for r in added)}\n"
                        f"**Кто выдал:** {who}"
                    )
                    await ch.send(embed=embed)
                if removed:
                    embed = discord.Embed(color=0xED4245, timestamp=discord.utils.utcnow())
                    embed.set_author(name="🏷️ РОЛЬ СНЯТА", icon_url=after.display_avatar.url)
                    embed.description = (
                        f"**Участник:** {_user_line(after)}\n"
                        f"**Роль:** {' '.join(r.mention for r in removed)}\n"
                        f"**Кто снял:** {who}"
                    )
                    await ch.send(embed=embed)

        # Мьют
        if before.timed_out_until != after.timed_out_until:
            ch = await get_log_channel(guild, "mute_log_channel")
            if ch:
                entry = await get_audit(guild, discord.AuditLogAction.member_update)
                executor = entry.user if entry else None
                who = executor.mention if executor else "`Неизвестно`"
                if after.timed_out_until:
                    embed = discord.Embed(color=0xFEE75C, timestamp=discord.utils.utcnow())
                    embed.set_author(name="🔇 МЬЮ", icon_url=after.display_avatar.url)
                    embed.description = (
                        f"**Участник:** {_user_line(after)}\n"
                        f"**Кто замьютил:** {who}\n"
                        f"**До:** {discord.utils.format_dt(after.timed_out_until, 'R')}"
                    )
                else:
                    embed = discord.Embed(color=0x57F287, timestamp=discord.utils.utcnow())
                    embed.set_author(name="🔊 РАЗМЬЮТ", icon_url=after.display_avatar.url)
                    embed.description = (
                        f"**Участник:** {_user_line(after)}\n"
                        f"**Кто размьютил:** {who}"
                    )
                await ch.send(embed=embed)

        # Смена ника
        if before.nick != after.nick:
            ch = await get_log_channel(guild, "mute_log_channel")
            if ch:
                entry = await get_audit(guild, discord.AuditLogAction.member_update)
                executor = entry.user if entry else None
                embed = discord.Embed(color=0x5865F2, timestamp=discord.utils.utcnow())
                embed.set_author(name="✏️ СМЕНА НИКА", icon_url=after.display_avatar.url)
                embed.description = (
                    f"**Участник:** {_user_line(after)}\n"
                    f"**Было:** `{before.nick or '—'}`\n"
                    f"**Стало:** `{after.nick or '—'}`\n"
                    f"**Кто изменил:** {executor.mention if executor else '`Неизвестно`'}"
                )
                await ch.send(embed=embed)

    # ── Войс: мьют/дифен микрофона → mute_log ──
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        ch = await get_log_channel(guild, "mute_log_channel")
        if not ch:
            return

        # Мьют микрофона
        if before.self_mute != after.self_mute or before.mute != after.mute:
            server_muted = after.mute and not before.mute
            server_unmuted = before.mute and not after.mute
            if server_muted:
                embed = discord.Embed(color=0xFEE75C, timestamp=discord.utils.utcnow())
                embed.set_author(name="🎙️ МЬЮ МИКРОФОНА (сервер)", icon_url=member.display_avatar.url)
                embed.description = f"**Участник:** {_user_line(member)}"
                await ch.send(embed=embed)
            elif server_unmuted:
                embed = discord.Embed(color=0x57F287, timestamp=discord.utils.utcnow())
                embed.set_author(name="🎙️ РАЗМЬЮТ МИКРОФОНА (сервер)", icon_url=member.display_avatar.url)
                embed.description = f"**Участник:** {_user_line(member)}"
                await ch.send(embed=embed)

        # Дифен (заглушение)
        server_deafened = after.deaf and not before.deaf
        server_undeafened = before.deaf and not after.deaf
        if server_deafened:
            embed = discord.Embed(color=0xFEE75C, timestamp=discord.utils.utcnow())
            embed.set_author(name="🔕 ДИФЕН (сервер)", icon_url=member.display_avatar.url)
            embed.description = f"**Участник:** {_user_line(member)}"
            await ch.send(embed=embed)
        elif server_undeafened:
            embed = discord.Embed(color=0x57F287, timestamp=discord.utils.utcnow())
            embed.set_author(name="🔔 СНЯТ ДИФЕН (сервер)", icon_url=member.display_avatar.url)
            embed.description = f"**Участник:** {_user_line(member)}"
            await ch.send(embed=embed)

    # ════════════════════════════════════════
    # 📁 КАНАЛЫ → channel_log
    # ════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild

        # Если идёт unsetup — не восстанавливаем
        if hasattr(self.bot, 'unsetup_guilds') and guild.id in self.bot.unsetup_guilds:
            return

        settings = db.get_settings(guild.id)
        log_keys = ["log_channel", "role_log_channel", "channel_log_channel",
                    "mute_log_channel", "whitelist_log_channel", "join_log_channel", "settings_channel"]
        log_ids = {str(settings.get(k)) for k in log_keys if settings.get(k)}
        if str(channel.id) in log_ids:
            return

        # Ждём audit log и проверяем кто удалил
        await asyncio.sleep(0.5)
        executor = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if time.time() - entry.created_at.timestamp() < 5:
                    executor = entry.user
                    break
        except Exception:
            pass

        # Если удалил сам бот — не восстанавливаем и не логируем
        if executor and executor.id == self.bot.user.id:
            return

        if executor:
            exec_member = guild.get_member(executor.id)
            if is_whitelisted(guild.id, executor.id, "channels", member=exec_member):
                ch = await get_log_channel(guild, "channel_log_channel")
                if ch:
                    embed = discord.Embed(color=0x5865F2, timestamp=discord.utils.utcnow())
                    embed.set_author(name="📁 КАНАЛ УДАЛЁН (разрешено)")
                    embed.description = (
                        f"**Канал:** `{channel.name}`\n"
                        f"**Кто удалил:** {executor.mention}\n"
                        f"**Статус:** ✅ Whitelist"
                    )
                    await ch.send(embed=embed)
                return

        data = channel_cache.get(guild.id, {}).get(channel.id)
        restored = False
        if data and db.get_settings(guild.id).get("restore_channels", 1):
            try:
                await self._restore_channel(guild, channel.id, data)
                restored = True
            except Exception as e:
                print(f"[RESTORE] {e}")

        ch = await get_log_channel(guild, "channel_log_channel")
        if not ch:
            return
        embed = discord.Embed(
            color=0x57F287 if restored else 0xED4245,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name="📁 КАНАЛ УДАЛЁН" + (" → ВОССТАНОВЛЕН" if restored else ""))
        embed.description = (
            f"**Канал:** `{channel.name}`\n"
            f"**Кто удалил:** {executor.mention if executor else '`Неизвестно`'}\n"
            f"**Статус:** {'✅ Восстановлен' if restored else '❌ Не восстановлен'}"
        )
        await ch.send(embed=embed)

    async def _restore_channel(self, guild, old_id, data):
        overwrites = {}
        for target_id, ow in data["overwrites"].items():
            perms = discord.PermissionOverwrite.from_pair(
                discord.Permissions(ow["allow"]), discord.Permissions(ow["deny"])
            )
            target = guild.get_role(int(target_id)) if ow["type"] == "role" else guild.get_member(int(target_id))
            if target:
                overwrites[target] = perms

        category = guild.get_channel(data["category_id"]) if data.get("category_id") else None
        ch_type = data["type"]
        new_ch = None
        try:
            if ch_type == discord.ChannelType.text:
                new_ch = await guild.create_text_channel(
                    name=data["name"], overwrites=overwrites, category=category,
                    topic=data.get("topic"), nsfw=data.get("nsfw", False),
                    slowmode_delay=data.get("slowmode", 0), reason="Auto-restore"
                )
            elif ch_type == discord.ChannelType.voice:
                new_ch = await guild.create_voice_channel(
                    name=data["name"], overwrites=overwrites, category=category, reason="Auto-restore"
                )
            elif ch_type == discord.ChannelType.category:
                new_ch = await guild.create_category(
                    name=data["name"], overwrites=overwrites, reason="Auto-restore"
                )
            elif ch_type == discord.ChannelType.forum:
                new_ch = await guild.create_forum(
                    name=data["name"], overwrites=overwrites, category=category, reason="Auto-restore"
                )
            else:
                return
            await asyncio.sleep(0.3)
            await new_ch.edit(position=data["position"])
            channel_cache[guild.id][new_ch.id] = data
            print(f"[RESTORE] Восстановлен: {data['name']}")
        except Exception as e:
            print(f"[RESTORE] Ошибка: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        ch = await get_log_channel(channel.guild, "channel_log_channel")
        if not ch:
            return
        entry = await get_audit(channel.guild, discord.AuditLogAction.channel_create)
        executor = entry.user if entry else None
        embed = discord.Embed(color=0x57F287, timestamp=discord.utils.utcnow())
        embed.set_author(name="📁 КАНАЛ СОЗДАН")
        embed.description = (
            f"**Канал:** {channel.mention}\n"
            f"**Тип:** `{str(channel.type).split('.')[-1]}`\n"
            f"**Кто создал:** {executor.mention if executor else '`Неизвестно`'}"
        )
        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        guild = role.guild
        await asyncio.sleep(0.4)
        executor = None
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.role_delete):
                if time.time() - entry.created_at.timestamp() < 5:
                    executor = entry.user
                    break
        except Exception:
            pass

        # Если удалил сам бот — не восстанавливаем
        if executor and executor.id == self.bot.user.id:
            return

        if executor:
            exec_member = guild.get_member(executor.id)
            if is_whitelisted(guild.id, executor.id, "roles", member=exec_member):
                ch = await get_log_channel(guild, "channel_log_channel")
                if ch:
                    embed = discord.Embed(color=0x5865F2, timestamp=discord.utils.utcnow())
                    embed.set_author(name="🏷️ РОЛЬ УДАЛЕНА (разрешено)")
                    embed.description = (
                        f"**Роль:** `{role.name}`\n"
                        f"**Кто удалил:** {executor.mention}\n"
                        f"**Статус:** ✅ Whitelist"
                    )
                    await ch.send(embed=embed)
                return

        data = role_cache.get(guild.id, {}).get(role.id)
        restored = False
        if data and db.get_settings(guild.id).get("restore_roles", 1):
            try:
                new_role = await guild.create_role(
                    name=data["name"], color=discord.Color(data["color"]),
                    hoist=data["hoist"], mentionable=data["mentionable"],
                    permissions=discord.Permissions(data["permissions"]),
                    reason="Auto-restore"
                )
                await asyncio.sleep(0.3)
                await new_role.edit(position=data["position"])
                role_cache[guild.id][new_role.id] = data
                restored = True
                print(f"[RESTORE] Восстановлена роль {data['name']}")
            except Exception as e:
                print(f"[RESTORE ROLE] {e}")

        ch = await get_log_channel(guild, "channel_log_channel")
        if not ch:
            return
        embed = discord.Embed(
            color=0x57F287 if restored else 0xED4245,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name="🏷️ РОЛЬ УДАЛЕНА" + (" → ВОССТАНОВЛЕНА" if restored else ""))
        embed.description = (
            f"**Роль:** `{role.name}`\n"
            f"**Кто удалил:** {executor.mention if executor else '`Неизвестно`'}\n"
            f"**Статус:** {'✅ Восстановлена' if restored else '❌ Не восстановлена'}"
        )
        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        ch = await get_log_channel(role.guild, "channel_log_channel")
        if not ch:
            return
        entry = await get_audit(role.guild, discord.AuditLogAction.role_create)
        executor = entry.user if entry else None
        embed = discord.Embed(color=0x57F287, timestamp=discord.utils.utcnow())
        embed.set_author(name="🏷️ РОЛЬ СОЗДАНА")
        embed.description = (
            f"**Роль:** {role.mention} (`{role.name}`)\n"
            f"**Кто создал:** {executor.mention if executor else '`Неизвестно`'}"
        )
        await ch.send(embed=embed)

    # ── Удаление веток → восстановление ──
    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        guild = thread.guild
        settings = db.get_settings(guild.id)
        log_keys = ["log_channel", "role_log_channel", "channel_log_channel", "mute_log_channel", "whitelist_log_channel", "settings_channel"]
        log_ids = {str(settings.get(k)) for k in log_keys if settings.get(k)}
        if str(thread.id) in log_ids:
            return
        try:
            parent = thread.parent
            if not parent:
                return
            await parent.create_thread(name=thread.name, type=thread.type, reason="Auto-restore")
            print(f"[RESTORE] Восстановлена ветка {thread.name}")
        except Exception as e:
            print(f"[RESTORE THREAD] {e}")

    # ════════════════════════════════════════
    # ✏️ СООБЩЕНИЯ → ban_log (общий лог)
    # ════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not after.guild or after.author.bot:
            return
        if before.content == after.content:
            return
        ch = await get_log_channel(after.guild, "log_channel")
        if not ch:
            return
        embed = discord.Embed(color=0x3498DB, timestamp=discord.utils.utcnow())
        embed.set_author(name="✏️ СООБЩЕНИЕ ИЗМЕНЕНО", icon_url=after.author.display_avatar.url)
        embed.description = (
            f"**Автор:** {_user_line(after.author)}\n"
            f"**Канал:** {after.channel.mention}\n"
            f"**Было:** {before.content[:300] or '*пусто*'}\n"
            f"**Стало:** {after.content[:300] or '*пусто*'}\n"
            f"[Перейти к сообщению]({after.jump_url})"
        )
        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot:
            return
        ch = await get_log_channel(message.guild, "log_channel")
        if not ch:
            return
        embed = discord.Embed(color=0xE74C3C, timestamp=discord.utils.utcnow())
        embed.set_author(name="🗑️ СООБЩЕНИЕ УДАЛЕНО", icon_url=message.author.display_avatar.url)
        embed.description = (
            f"**Автор:** {_user_line(message.author)}\n"
            f"**Канал:** {message.channel.mention}\n"
            f"**Содержимое:** {message.content[:400] or '*пусто*'}"
        )
        await ch.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Logger(bot))
