import discord
from discord.ext import commands
import time
import asyncio
import re
import database as db
from utils.checks import is_whitelisted
from utils.embeds import alert
import config

URL_REGEX = re.compile(r"(https?://|discord\.gg/|discord\.com/invite/)\S+", re.IGNORECASE)

# Кэш действий: (guild_id, user_id, action) -> [timestamps]
_cache: dict = {}

def track_action(guild_id, user_id, action, limit, interval=30):
    """Возвращает True если лимит превышен за interval секунд."""
    key = (guild_id, user_id, action)
    now = time.time()
    times = _cache.get(key, [])
    times = [t for t in times if now - t < interval]
    times.append(now)
    _cache[key] = times
    db.log_action(guild_id, user_id, action)
    return len(times) >= limit


async def instant_ban(guild, user_id, reason):
    """Моментальный бан без проверки настроек."""
    try:
        await guild.ban(discord.Object(id=user_id), reason=reason, delete_message_days=0)
        db.log_action(guild.id, user_id, "bot_ban", reason)
        print(f"[BAN] {user_id} | {reason}")
        await send_log(guild, user_id, reason)
    except Exception as e:
        print(f"[BAN ERROR] {e}")


async def send_log(guild, user_id, reason):
    settings = db.get_settings(guild.id)
    ch_id = settings.get("log_channel")
    if not ch_id:
        return
    ch = guild.get_channel(int(ch_id))
    if not ch:
        return
    embed = alert(
        "Нарушитель забанен",
        f"<@{user_id}> автоматически забанен.",
        [{"name": "Причина", "value": reason}]
    )
    try:
        await ch.send(embed=embed)
    except Exception:
        pass


class AntiRaid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_executor(self, guild, action_type, target_id=None):
        # Минимальная задержка — Discord не пишет audit log мгновенно
        await asyncio.sleep(0.3)
        try:
            async for entry in guild.audit_logs(limit=3, action=action_type):
                if time.time() - entry.created_at.timestamp() > 5:
                    continue
                if target_id and hasattr(entry, 'target') and entry.target and entry.target.id != target_id:
                    continue
                return entry.user
        except Exception:
            pass
        return None

    # --- БАН → моментальный бан исполнителя ---
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        executor = await self.get_executor(guild, discord.AuditLogAction.ban)
        if not executor or executor.id == self.bot.user.id:
            return
        member = guild.get_member(executor.id)
        if is_whitelisted(guild.id, executor.id, "ban", member=member):
            return
        await instant_ban(guild, executor.id, "Anti-Raid: Попытка бана участника")

    # --- КИК → моментальный бан исполнителя ---
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        executor = await self.get_executor(guild, discord.AuditLogAction.kick, member.id)
        if not executor or executor.id == self.bot.user.id:
            return
        exec_member = guild.get_member(executor.id)
        if is_whitelisted(guild.id, executor.id, "kick", member=exec_member):
            return
        await instant_ban(guild, executor.id, "Anti-Raid: Попытка кика участника")

    # --- УДАЛЕНИЕ КАНАЛА → моментальный бан ---
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        executor = await self.get_executor(guild, discord.AuditLogAction.channel_delete)
        if not executor or executor.id == self.bot.user.id:
            return
        exec_member = guild.get_member(executor.id)
        if is_whitelisted(guild.id, executor.id, "channels", member=exec_member):
            return
        await instant_ban(guild, executor.id, "Anti-Raid: Удаление канала")

    # --- СОЗДАНИЕ КАНАЛА → бан + удаление если не в whitelist ---
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        guild = channel.guild
        # Сразу удаляем канал
        try:
            await channel.delete(reason="Anti-Raid: создание канала без прав")
        except Exception:
            pass
        executor = await self.get_executor(guild, discord.AuditLogAction.channel_create)
        if not executor or executor.id == self.bot.user.id:
            return
        exec_member = guild.get_member(executor.id)
        # Боты тоже баним — не пропускаем их
        if exec_member and not exec_member.bot:
            if is_whitelisted(guild.id, executor.id, "channels", member=exec_member):
                return
        elif not exec_member:
            # Пользователь уже покинул сервер или не найден — баним по ID
            pass
        await instant_ban(guild, executor.id, "Anti-Raid: Создание канала без прав")

    # --- ПЕРЕИМЕНОВАНИЕ КАНАЛА → возврат старого названия ---
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        guild = after.guild
        if before.name == after.name:
            return
        executor = await self.get_executor(guild, discord.AuditLogAction.channel_update)
        if not executor or executor.id == self.bot.user.id:
            return
        exec_member = guild.get_member(executor.id)
        if is_whitelisted(guild.id, executor.id, "channels", member=exec_member):
            return
        try:
            await after.edit(name=before.name, reason="Anti-Raid: откат переименования канала")
            print(f"[ANTI-RAID] Reverted channel rename by {executor.id}")
        except Exception as e:
            print(f"[ANTI-RAID] Failed to revert channel rename: {e}")

    # --- ПЕРЕИМЕНОВАНИЕ РОЛИ → возврат старого названия ---
    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        guild = after.guild
        if before.name == after.name and before.permissions == after.permissions and before.color == after.color:
            return
        executor = await self.get_executor(guild, discord.AuditLogAction.role_update)
        if not executor or executor.id == self.bot.user.id:
            return
        exec_member = guild.get_member(executor.id)
        if is_whitelisted(guild.id, executor.id, "roles", member=exec_member):
            return
        try:
            await after.edit(
                name=before.name,
                permissions=before.permissions,
                color=before.color,
                reason="Anti-Raid: откат изменения роли"
            )
            print(f"[ANTI-RAID] Reverted role update by {executor.id}")
        except Exception as e:
            print(f"[ANTI-RAID] Failed to revert role update: {e}")

    # --- УДАЛЕНИЕ РОЛИ → моментальный бан ---
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        guild = role.guild
        executor = await self.get_executor(guild, discord.AuditLogAction.role_delete)
        if not executor or executor.id == self.bot.user.id:
            return
        exec_member = guild.get_member(executor.id)
        if is_whitelisted(guild.id, executor.id, "roles", member=exec_member):
            return
        await instant_ban(guild, executor.id, "Anti-Raid: Удаление роли")

    # --- АВТО-РЕБАН при разбане ---
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        recent = db.get_recent_actions(guild.id, user.id, "bot_ban", time.time() - 60)
        if not recent:
            return
        await asyncio.sleep(1)
        try:
            await guild.ban(user, reason="Anti-Raid: Повторный бан после разбана")
            db.log_action(guild.id, user.id, "bot_ban", "Re-ban")
        except Exception as e:
            print(f"[RE-BAN] {e}")

    # --- РОЛИ: выдача / снятие / мьют ---
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild = after.guild

        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]

        executor = None
        if added or removed:
            executor = await self.get_executor(guild, discord.AuditLogAction.member_role_update, after.id)

        # Защита ролей — возврат снятых
        protected = db.get_protected(guild.id, after.id)
        if protected and removed:
            for role in removed:
                if str(role.id) in protected["role_ids"]:
                    try:
                        await after.add_roles(role, reason="Role Protection: автовозврат")
                    except Exception as e:
                        print(f"[PROTECT] {e}")

        if not executor or executor.id == self.bot.user.id:
            return
        exec_member = guild.get_member(executor.id)
        if is_whitelisted(guild.id, executor.id, "roles", member=exec_member):
            return

        # Выдача ролей: если 5+ за 30 сек — бан, иначе откат
        if added:
            if track_action(guild.id, executor.id, "role_add", limit=5, interval=30):
                await instant_ban(guild, executor.id, "Anti-Raid: Массовая выдача ролей (5+ за 30 сек)")
            else:
                # Откатываем выданные роли
                try:
                    await after.remove_roles(*added, reason="Anti-Raid: откат выдачи роли")
                except Exception as e:
                    print(f"[ROLE REVERT] {e}")

        # Снятие ролей: 5+ за 30 сек — бан
        if removed:
            if track_action(guild.id, executor.id, "role_remove", limit=5, interval=30):
                await instant_ban(guild, executor.id, "Anti-Raid: Массовое снятие ролей (5+ за 30 сек)")

        # Мьют (тайм-аут): снятие всех ролей с нарушителя
        if before.timed_out_until != after.timed_out_until and after.timed_out_until:
            try:
                member_exec = guild.get_member(executor.id)
                if member_exec:
                    roles_to_remove = [r for r in member_exec.roles if r != guild.default_role and not r.managed]
                    if roles_to_remove:
                        await member_exec.remove_roles(*roles_to_remove, reason="Anti-Raid: мьют без прав")
                        print(f"[ANTI-RAID] Removed all roles from {executor.id} (mute without perms)")
            except Exception as e:
                print(f"[MUTE ROLES] {e}")

    # --- СПАМ ССЫЛКАМИ → моментальный бан ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        settings = db.get_settings(message.guild.id)

        # --- Защита от @everyone / @here ---
        if not is_whitelisted(message.guild.id, message.author.id, "mention_everyone", member=message.author if isinstance(message.author, discord.Member) else None):
            if "@everyone" in message.content or "@here" in message.content:
                try:
                    await message.delete()
                    print(f"[ANTI-RAID] Deleted @everyone/@here from {message.author.id}")
                except Exception:
                    pass
                return

        # --- Защита от ссылок ---
        if not is_whitelisted(message.guild.id, message.author.id, "links", member=message.author if isinstance(message.author, discord.Member) else None):
            if URL_REGEX.search(message.content):
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    member = message.guild.get_member(message.author.id)
                    if member:
                        import datetime
                        await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=15),
                                             reason="Anti-Raid: Ссылка в чате")
                except Exception:
                    pass



    # --- ВХОД БОТА → кик если добавил не owner/whitelist ---
    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild

    # --- ВХОД БОТА → кик если добавил не owner/whitelist ---
    # --- ВХОД УЧАСТНИКА → бан если роль выше порога ---
    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild

        # Проверяем только ботов
        if member.bot and member.id != self.bot.user.id:
            await asyncio.sleep(0.5)
            # Ищем кто добавил бота через audit log
            executor = await self.get_executor(guild, discord.AuditLogAction.bot_add)
            if executor:
                exec_member = guild.get_member(executor.id)
                # Если добавил owner или вайтлистер с полными правами — разрешаем
                if is_whitelisted(guild.id, executor.id, "all", member=exec_member):
                    return
            # Кикаем бота
            try:
                await guild.kick(member, reason="Anti-Raid: бот добавлен без разрешения")
                db.log_action(guild.id, member.id, "bot_kick", f"Добавил: {executor.id if executor else 'неизвестно'}")
                print(f"[ANTI-RAID] Kicked bot {member.id} ({member.name})")
                await send_log(guild, member.id, f"Anti-Raid: бот {member.name} кикнут (добавил: {executor.mention if executor else 'неизвестно'})")
            except Exception as e:
                print(f"[BOT KICK] {e}")
            return

        # Ждём немного — роль может выдаться чуть позже
        await asyncio.sleep(3)
        fresh = guild.get_member(member.id)
        if not fresh:
            return
        if is_whitelisted(guild.id, fresh.id, "invites"):
            return

        # Ищем роль-порог × ᴍᴇᴍʙᴇʀs
        member_role = discord.utils.find(
            lambda r: "members" in r.name.lower() or "ᴍᴇᴍʙᴇʀs" in r.name,
            guild.roles
        )
        if not member_role:
            return

        # Если у участника есть роль выше порога — бан
        for role in fresh.roles:
            if role.id == guild.id:
                continue
            if role.position > member_role.position:
                await instant_ban(guild, fresh.id, f"Anti-Raid: Получил роль выше × ᴍᴇᴍʙᴇʀs при входе ({role.name})")
                return


async def setup(bot):
    await bot.add_cog(AntiRaid(bot))
