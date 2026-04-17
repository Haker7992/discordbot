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


async def get_audit(guild, action):
    await asyncio.sleep(0.5)
    try:
        async for entry in guild.audit_logs(limit=1, action=action):
            if time.time() - entry.created_at.timestamp() < 5:
                return entry
    except Exception:
        pass
    return None


class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Кэшируем все каналы и роли при старте."""
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
        """Обновляем кэш при создании роли."""
        if role.guild.id not in role_cache:
            role_cache[role.guild.id] = {}
        if not role.managed:
            role_cache[role.guild.id][role.id] = self._serialize_role(role)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        """Обновляем кэш при изменении роли."""
        if after.guild.id not in role_cache:
            role_cache[after.guild.id] = {}
        if not after.managed:
            role_cache[after.guild.id][after.id] = self._serialize_role(after)

    def _serialize_role(self, role):
        return {
            "name": role.name,
            "color": role.color.value,
            "hoist": role.hoist,
            "mentionable": role.mentionable,
            "permissions": role.permissions.value,
            "position": role.position
        }

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Обновляем кэш при создании канала."""
        if channel.guild.id not in channel_cache:
            channel_cache[channel.guild.id] = {}
        channel_cache[channel.guild.id][channel.id] = self._serialize(channel)

    def _serialize(self, channel):
        """Сохраняем нужные данные канала."""
        data = {
            "name": channel.name,
            "type": channel.type,
            "position": channel.position,
            "category_id": channel.category_id if hasattr(channel, "category_id") else None,
            "overwrites": {
                str(target.id): {
                    "type": "role" if isinstance(target, discord.Role) else "member",
                    "allow": overwrite.pair()[0].value,
                    "deny": overwrite.pair()[1].value,
                }
                for target, overwrite in channel.overwrites.items()
            }
        }
        if isinstance(channel, discord.TextChannel):
            data["topic"] = channel.topic
            data["nsfw"] = channel.nsfw
            data["slowmode"] = channel.slowmode_delay
        return data

    # ── Роли: выдача / снятие / мьют / ник ──
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild = after.guild

        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]

        # 📋 Роли → role_log_channel
        if added or removed:
            ch = await get_log_channel(guild, "role_log_channel")
            if ch:
                entry = await get_audit(guild, discord.AuditLogAction.member_role_update)
                executor = entry.user if entry else None
                if added:
                    embed = discord.Embed(title="🏷️ Роль выдана", color=0x57F287)
                    embed.add_field(name="Участник", value=f"{after.mention} (`{after.id}`)", inline=True)
                    embed.add_field(name="Роль", value=" ".join(r.mention for r in added), inline=True)
                    embed.add_field(name="Кто", value=executor.mention if executor else "Неизвестно", inline=True)
                    embed.timestamp = discord.utils.utcnow()
                    await ch.send(embed=embed)
                if removed:
                    embed = discord.Embed(title="🏷️ Роль снята", color=0xED4245)
                    embed.add_field(name="Участник", value=f"{after.mention} (`{after.id}`)", inline=True)
                    embed.add_field(name="Роль", value=" ".join(r.mention for r in removed), inline=True)
                    embed.add_field(name="Кто", value=executor.mention if executor else "Неизвестно", inline=True)
                    embed.timestamp = discord.utils.utcnow()
                    await ch.send(embed=embed)

        # 🔇 Мьют → mute_log_channel
        if before.timed_out_until != after.timed_out_until and after.timed_out_until:
            ch = await get_log_channel(guild, "mute_log_channel")
            if ch:
                entry = await get_audit(guild, discord.AuditLogAction.member_update)
                executor = entry.user if entry else None
                embed = discord.Embed(title="🔇 Участник замьючен", color=0xFEE75C)
                embed.add_field(name="Участник", value=f"{after.mention} (`{after.id}`)", inline=True)
                embed.add_field(name="Кто", value=executor.mention if executor else "Неизвестно", inline=True)
                embed.add_field(name="До", value=discord.utils.format_dt(after.timed_out_until, "R"), inline=True)
                embed.timestamp = discord.utils.utcnow()
                await ch.send(embed=embed)

        # ✏️ Смена ника → mute_log_channel
        if before.nick != after.nick:
            ch = await get_log_channel(guild, "mute_log_channel")
            if ch:
                entry = await get_audit(guild, discord.AuditLogAction.member_update)
                executor = entry.user if entry else None
                embed = discord.Embed(title="✏️ Смена никнейма", color=0x5865F2)
                embed.add_field(name="Участник", value=f"{after.mention} (`{after.id}`)", inline=True)
                embed.add_field(name="Было", value=before.nick or "нет", inline=True)
                embed.add_field(name="Стало", value=after.nick or "нет", inline=True)
                embed.add_field(name="Кто", value=executor.mention if executor else "Неизвестно", inline=True)
                embed.timestamp = discord.utils.utcnow()
                await ch.send(embed=embed)

    # ── Баны → log_channel ──
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        ch = await get_log_channel(guild, "log_channel")
        if not ch:
            return
        entry = await get_audit(guild, discord.AuditLogAction.ban)
        executor = entry.user if entry else None
        embed = discord.Embed(title="🔨 Участник забанен", color=0xED4245)
        embed.add_field(name="Участник", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="Кто", value=executor.mention if executor else "Неизвестно", inline=True)
        embed.add_field(name="Причина", value=(entry.reason if entry and entry.reason else "Не указана"), inline=False)
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)

    # ── Разбаны → log_channel ──
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        ch = await get_log_channel(guild, "log_channel")
        if not ch:
            return
        entry = await get_audit(guild, discord.AuditLogAction.unban)
        executor = entry.user if entry else None
        embed = discord.Embed(title="✅ Участник разбанен", color=0x57F287)
        embed.add_field(name="Участник", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="Кто", value=executor.mention if executor else "Неизвестно", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)

    # ── Выход участника → log_channel ──
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        ch = await get_log_channel(guild, "log_channel")
        if not ch:
            return
        # Проверяем — это кик или просто выход
        entry = await get_audit(guild, discord.AuditLogAction.kick)
        if entry and entry.target and entry.target.id == member.id:
            embed = discord.Embed(title="👢 Участник кикнут", color=0xFEE75C)
            embed.add_field(name="Участник", value=f"{member.mention} (`{member.id}`)", inline=True)
            embed.add_field(name="Кто", value=entry.user.mention, inline=True)
            embed.add_field(name="Причина", value=entry.reason or "Не указана", inline=False)
        else:
            embed = discord.Embed(title="📤 Участник вышел", color=0xE74C3C)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Участник", value=f"**{member.name}** (`{member.id}`)", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild

        # Если идёт unsetup — не восстанавливаем
        if hasattr(self.bot, 'unsetup_guilds') and guild.id in self.bot.unsetup_guilds:
            return

        # Не восстанавливаем лог-каналы бота
        settings = db.get_settings(guild.id)
        log_keys = ["log_channel", "role_log_channel", "channel_log_channel", "mute_log_channel", "whitelist_log_channel", "settings_channel"]
        log_ids = {str(settings.get(k)) for k in log_keys if settings.get(k)}
        if str(channel.id) in log_ids:
            return

        # Проверяем кто удалил — если вайтлистер, не восстанавливаем
        await asyncio.sleep(0.4)
        executor = None
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.channel_delete):
                if time.time() - entry.created_at.timestamp() < 5:
                    executor = entry.user
                    break
        except Exception:
            pass

        if executor:
            exec_member = guild.get_member(executor.id)
            if is_whitelisted(guild.id, executor.id, "channels", member=exec_member):
                # Вайтлистер удалил — только логируем, не восстанавливаем
                ch = await get_log_channel(guild, "channel_log_channel")
                if ch:
                    embed = discord.Embed(title="📁 Канал удалён", color=0x5865F2)
                    embed.add_field(name="Канал", value=f"`{channel.name}`", inline=True)
                    embed.add_field(name="Кто удалил", value=executor.mention, inline=True)
                    embed.add_field(name="Статус", value="✅ Разрешено (whitelist)", inline=True)
                    embed.timestamp = discord.utils.utcnow()
                    await ch.send(embed=embed)
                return

        # Восстанавливаем канал из кэша
        data = channel_cache.get(guild.id, {}).get(channel.id)
        if data:
            # Проверяем настройку восстановления
            if db.get_settings(guild.id).get("restore_channels", 1):
                try:
                    await self._restore_channel(guild, channel.id, data)
                except Exception as e:
                    print(f"[RESTORE] Ошибка восстановления: {e}")

        # Лог
        ch = await get_log_channel(guild, "channel_log_channel")
        if not ch:
            return
        restored = bool(db.get_settings(guild.id).get("restore_channels", 1))
        embed = discord.Embed(
            title="📁 Канал удалён и восстановлен" if restored else "📁 Канал удалён",
            color=0xFEE75C
        )
        embed.add_field(name="Канал", value=f"`{channel.name}`", inline=True)
        embed.add_field(name="Кто удалил", value=executor.mention if executor else "Неизвестно", inline=True)
        embed.add_field(name="Статус", value="✅ Восстановлен" if restored else "❌ Восстановление выключено", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)

    async def _restore_channel(self, guild, old_id, data):
        """Восстанавливает канал по сохранённым данным."""
        overwrites = {}
        for target_id, ow in data["overwrites"].items():
            perms = discord.PermissionOverwrite.from_pair(
                discord.Permissions(ow["allow"]),
                discord.Permissions(ow["deny"])
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
                    slowmode_delay=data.get("slowmode", 0),
                    reason="Auto-restore: канал был удалён"
                )
            elif ch_type == discord.ChannelType.voice:
                new_ch = await guild.create_voice_channel(
                    name=data["name"], overwrites=overwrites, category=category,
                    reason="Auto-restore: канал был удалён"
                )
            elif ch_type == discord.ChannelType.category:
                new_ch = await guild.create_category(
                    name=data["name"], overwrites=overwrites,
                    reason="Auto-restore: категория была удалена"
                )
            elif ch_type == discord.ChannelType.forum:
                new_ch = await guild.create_forum(
                    name=data["name"], overwrites=overwrites, category=category,
                    reason="Auto-restore: форум был удалён"
                )
            else:
                return

            # Восстанавливаем позицию
            await asyncio.sleep(0.3)
            await new_ch.edit(position=data["position"])
            channel_cache[guild.id][new_ch.id] = data
            print(f"[RESTORE] Восстановлен: {data['name']}")
        except Exception as e:
            print(f"[RESTORE] Ошибка: {e}")

    # ── Создание каналов → channel_log_channel ──
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        ch = await get_log_channel(channel.guild, "channel_log_channel")
        if not ch:
            return
        entry = await get_audit(channel.guild, discord.AuditLogAction.channel_create)
        executor = entry.user if entry else None
        embed = discord.Embed(title="📁 Канал создан", color=0x57F287)
        embed.add_field(name="Канал", value=channel.mention, inline=True)
        embed.add_field(name="Кто", value=executor.mention if executor else "Неизвестно", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)

    # ── Удаление ролей → channel_log_channel + восстановление ──
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        guild = role.guild

        # Проверяем кто удалил — если вайтлистер, не восстанавливаем
        await asyncio.sleep(0.4)
        executor = None
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.role_delete):
                if time.time() - entry.created_at.timestamp() < 5:
                    executor = entry.user
                    break
        except Exception:
            pass

        if executor:
            exec_member = guild.get_member(executor.id)
            if is_whitelisted(guild.id, executor.id, "roles", member=exec_member):
                # Вайтлистер удалил — только логируем
                ch = await get_log_channel(guild, "channel_log_channel")
                if ch:
                    embed = discord.Embed(title="🏷️ Роль удалена", color=0x5865F2)
                    embed.add_field(name="Роль", value=f"`{role.name}`", inline=True)
                    embed.add_field(name="Кто", value=executor.mention, inline=True)
                    embed.add_field(name="Статус", value="✅ Разрешено (whitelist)", inline=True)
                    embed.timestamp = discord.utils.utcnow()
                    await ch.send(embed=embed)
                return

        # Восстанавливаем роль из кэша
        data = role_cache.get(guild.id, {}).get(role.id)
        if data:
            # Проверяем настройку восстановления ролей
            if db.get_settings(guild.id).get("restore_roles", 1):
                try:
                    new_role = await guild.create_role(
                        name=data["name"],
                        color=discord.Color(data["color"]),
                        hoist=data["hoist"],
                        mentionable=data["mentionable"],
                        permissions=discord.Permissions(data["permissions"]),
                        reason="Auto-restore: роль была удалена"
                    )
                    await asyncio.sleep(0.3)
                    await new_role.edit(position=data["position"])
                    role_cache[guild.id][new_role.id] = data
                    print(f"[RESTORE] Восстановлена роль {data['name']}")
                except Exception as e:
                    print(f"[RESTORE ROLE] {e}")

        # Лог
        ch = await get_log_channel(guild, "channel_log_channel")
        if not ch:
            return
        restored = bool(db.get_settings(guild.id).get("restore_roles", 1))
        embed = discord.Embed(
            title="🏷️ Роль удалена и восстановлена" if restored else "🏷️ Роль удалена",
            color=0xFEE75C
        )
        embed.add_field(name="Роль", value=f"`{role.name}`", inline=True)
        embed.add_field(name="Кто", value=executor.mention if executor else "Неизвестно", inline=True)
        embed.add_field(name="Статус", value="✅ Восстановлена" if restored else "❌ Восстановление выключено", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)

    # ── Создание ролей → channel_log_channel ──
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        ch = await get_log_channel(role.guild, "channel_log_channel")
        if not ch:
            return
        entry = await get_audit(role.guild, discord.AuditLogAction.role_create)
        executor = entry.user if entry else None
        embed = discord.Embed(title="🏷️ Роль создана", color=0x57F287)
        embed.add_field(name="Роль", value=role.mention, inline=True)
        embed.add_field(name="Кто", value=executor.mention if executor else "Неизвестно", inline=True)
        embed.timestamp = discord.utils.utcnow()
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
            await parent.create_thread(
                name=thread.name,
                type=thread.type,
                reason="Auto-restore: ветка была удалена"
            )
            print(f"[RESTORE] Восстановлена ветка {thread.name}")
        except Exception as e:
            print(f"[RESTORE THREAD] {e}")

    # ── Вход участника: авто-роль + приветствие в ЛС + лог ──
    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild

        # Авто-роль member
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
                description=(
                    "**Рады видеть тебя в Архангелах!**\n\n"
                    "**Бот создавал ебейший гениус DavaidKa**"
                ),
                color=0x5865F2
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            await member.send(embed=embed)
            _save_dm_history(member.id)
        except discord.Forbidden:
            pass

        # Лог входа
        ch = await get_log_channel(guild, "log_channel")
        if ch:
            log_embed = discord.Embed(title="📥 Участник вошёл", color=0x2ECC71)
            log_embed.set_thumbnail(url=member.display_avatar.url)
            log_embed.add_field(name="Участник", value=f"{member.mention} (`{member.id}`)", inline=True)
            log_embed.add_field(name="Аккаунт создан", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
            log_embed.timestamp = discord.utils.utcnow()
            await ch.send(embed=log_embed)

    # ── Редактирование сообщения → log_channel ──
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not after.guild or after.author.bot:
            return
        if before.content == after.content:
            return
        ch = await get_log_channel(after.guild, "log_channel")
        if not ch:
            return
        embed = discord.Embed(title="✏️ Сообщение изменено", color=0x3498DB)
        embed.add_field(name="Автор", value=f"{after.author.mention} (`{after.author.id}`)", inline=True)
        embed.add_field(name="Канал", value=after.channel.mention, inline=True)
        embed.add_field(name="Было", value=before.content[:500] or "*пусто*", inline=False)
        embed.add_field(name="Стало", value=after.content[:500] or "*пусто*", inline=False)
        embed.add_field(name="Ссылка", value=f"[Перейти]({after.jump_url})", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)

    # ── Удаление сообщения → log_channel ──
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot:
            return
        ch = await get_log_channel(message.guild, "log_channel")
        if not ch:
            return
        embed = discord.Embed(title="🗑️ Сообщение удалено", color=0xE74C3C)
        embed.add_field(name="Автор", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
        embed.add_field(name="Канал", value=message.channel.mention, inline=True)
        embed.add_field(name="Содержимое", value=message.content[:500] or "*пусто*", inline=False)
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Logger(bot))
