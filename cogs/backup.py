import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import time
from datetime import timedelta
from utils.checks import is_owner_id
from utils.embeds import success, error, info
import database as db

BACKUP_DIR = os.path.join(os.path.dirname(__file__), '../backups')


def is_owner():
    async def predicate(ctx):
        return is_owner_id(ctx.author.id)
    return commands.check(predicate)


class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs(BACKUP_DIR, exist_ok=True)
        # guild_id -> snapshot dict (in-memory, обновляется при join и изменениях)
        self._snapshots: dict = {}

    # ── Авто-снапшот при входе на сервер ──
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        self._snapshots[guild.id] = await self._collect(guild)
        print(f"[Backup] Снапшот сделан для {guild.name} ({guild.id})")

    # ── Обновляем снапшот при создании канала (только если создал бот) ──
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        await asyncio.sleep(1)
        # Проверяем кто создал канал — обновляем снапшот только если это бот
        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.channel_create):
                if entry.target and entry.target.id == channel.id:
                    if entry.user.id != self.bot.user.id:
                        return  # не бот создал — не обновляем снапшот
                    break
        except Exception:
            pass
        self._snapshots[guild.id] = await self._collect(guild)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        guild = after.guild
        self._snapshots[guild.id] = await self._collect(guild)

    # ── Восстановление удалённого канала ──
    # ── Восстановление удалённого канала ──
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild

        # Если идёт unsetup — не восстанавливаем
        if hasattr(self.bot, 'unsetup_guilds') and guild.id in self.bot.unsetup_guilds:
            return

        # Не восстанавливаем лог-каналы бота по ID
        settings = db.get_settings(guild.id)
        log_keys = ["log_channel", "role_log_channel", "channel_log_channel",
                    "mute_log_channel", "whitelist_log_channel", "join_log_channel", "settings_channel"]
        log_ids = {str(settings.get(k)) for k in log_keys if settings.get(k)}
        if str(channel.id) in log_ids:
            return

        snapshot = self._snapshots.get(guild.id)
        if not snapshot:
            return

        # Ждём audit log
        await asyncio.sleep(0.8)
        executor_id = None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if time.time() - entry.created_at.timestamp() > 5:
                    continue
                if entry.target and entry.target.id == channel.id:
                    executor_id = entry.user.id
                    break
        except Exception:
            pass

        # Если бот удалил — не восстанавливаем
        if executor_id == self.bot.user.id:
            return

        # Если вайтлистер удалил — не восстанавливаем
        if executor_id:
            from utils.checks import is_whitelisted
            exec_member = guild.get_member(executor_id)
            if is_whitelisted(guild.id, executor_id, "channels", member=exec_member):
                return

        # Проверяем настройку восстановления каналов
        if not db.get_settings(guild.id).get("restore_channels", 1):
            return

        # Ищем канал в снапшоте по имени и типу
        ch_data = next(
            (c for c in snapshot["channels"]
             if c["name"] == channel.name and c["type"] == str(channel.type).split(".")[-1]),
            None
        )
        if not ch_data:
            return

        # Небольшая задержка чтобы antiraid успел отработать
        await discord.utils.sleep_until(
            discord.utils.utcnow() + discord.timedelta(seconds=2)
        )

        try:
            # Восстанавливаем категорию если нужно
            category = None
            if ch_data.get("category"):
                category = discord.utils.get(guild.categories, name=ch_data["category"])
                if not category:
                    # Ищем в снапшоте данные категории
                    cat_data = next(
                        (c for c in snapshot["categories"] if c["name"] == ch_data["category"]),
                        None
                    )
                    if cat_data:
                        category = await guild.create_category(
                            name=cat_data["name"],
                            overwrites=self._build_overwrites(guild, cat_data["overwrites"])
                        )

            overwrites = self._build_overwrites(guild, ch_data["overwrites"])
            ch_type = ch_data["type"]

            if ch_type == "text":
                new_ch = await guild.create_text_channel(
                    name=ch_data["name"],
                    category=category,
                    topic=ch_data.get("topic"),
                    nsfw=ch_data.get("nsfw", False),
                    slowmode_delay=ch_data.get("slowmode", 0),
                    overwrites=overwrites,
                    reason="Auto-restore: канал был удалён"
                )
            elif ch_type == "voice":
                new_ch = await guild.create_voice_channel(
                    name=ch_data["name"],
                    category=category,
                    overwrites=overwrites,
                    reason="Auto-restore: канал был удалён"
                )
            else:
                return

            # Ставим позицию
            try:
                await new_ch.edit(position=ch_data.get("position", 0))
            except Exception:
                pass

            print(f"[Backup] Восстановлен канал #{ch_data['name']} на {guild.name}")
        except Exception as e:
            print(f"[Backup] Ошибка восстановления канала: {e}")

    def _build_overwrites(self, guild: discord.Guild, ow_list: list) -> dict:
        overwrites = {}
        for ow in ow_list:
            if ow["type"] == "role":
                target = guild.get_role(int(ow.get("id", 0))) or discord.utils.get(guild.roles, name=ow["name"])
            else:
                target = guild.get_member(int(ow.get("id", 0))) or discord.utils.get(guild.members, name=ow["name"])
            if target:
                overwrites[target] = discord.PermissionOverwrite.from_pair(
                    discord.Permissions(ow["allow"]),
                    discord.Permissions(ow["deny"])
                )
        return overwrites

    @commands.command(name="backup")
    @is_owner()
    async def backup_cmd(self, ctx):
        """Сохраняет структуру сервера и сообщения из категории Информация."""
        msg = await ctx.send(embed=info("Backup", "⏳ Сохраняю структуру сервера..."))
        guild = ctx.guild
        data = await self._collect(guild)

        # Сохраняем сообщения из категории Информация
        info_cat = discord.utils.find(
            lambda c: "информац" in c.name.lower(),
            guild.categories
        )
        data["info_messages"] = {}
        if info_cat:
            for ch in info_cat.text_channels:
                messages = []
                async for m in ch.history(limit=200, oldest_first=True):
                    messages.append({
                        "author": str(m.author),
                        "content": m.content,
                        "timestamp": m.created_at.isoformat(),
                        "embeds": [e.to_dict() for e in m.embeds]
                    })
                data["info_messages"][ch.name] = messages

        path = os.path.join(BACKUP_DIR, f"{guild.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        msg_count = sum(len(v) for v in data["info_messages"].values())
        await msg.edit(embed=success("Backup", (
            f"Сохранено: `{len(data['roles'])}` ролей, `{len(data['categories'])}` категорий, `{len(data['channels'])}` каналов.\n"
            f"Сообщений из Информации: `{msg_count}`\n"
            f"Файл: `backups/{guild.id}.json`"
        )))

    @commands.command(name="restore")
    @is_owner()
    async def restore_cmd(self, ctx, guild_id: int = None):
        """Восстанавливает структуру сервера из JSON файла."""
        gid = guild_id or ctx.guild.id
        path = os.path.join(BACKUP_DIR, f"{gid}.json")
        if not os.path.exists(path):
            return await ctx.send(embed=error("Restore", f"Файл `backups/{gid}.json` не найден."))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        msg = await ctx.send(embed=info("Restore", "⏳ Восстанавливаю структуру..."))

        # Удаляем все текущие каналы
        for ch in ctx.guild.channels:
            try:
                await ch.delete(reason="Restore: очистка перед восстановлением")
            except Exception:
                pass

        await self._restore(ctx.guild, data)

        # Восстанавливаем сообщения из Информации
        info_messages = data.get("info_messages", {})
        if info_messages:
            info_cat = discord.utils.find(
                lambda c: "информац" in c.name.lower(),
                ctx.guild.categories
            )
            if info_cat:
                for ch_name, messages in info_messages.items():
                    ch = discord.utils.get(info_cat.text_channels, name=ch_name)
                    if ch and messages:
                        for m in messages:
                            try:
                                content = m["content"]
                                if m.get("embeds"):
                                    embed_obj = discord.Embed.from_dict(m["embeds"][0])
                                    await ch.send(content=content or None, embed=embed_obj)
                                elif content:
                                    await ch.send(content)
                            except Exception:
                                pass

        await msg.edit(embed=success("Restore", "Структура и сообщения восстановлены."))

    async def _collect(self, guild):
        """Собирает снапшот структуры сервера, исключая лог-каналы бота."""
        data = {"name": guild.name, "roles": [], "categories": [], "channels": []}

        # Получаем ID лог-каналов чтобы исключить их из снапшота
        settings = db.get_settings(guild.id)
        log_keys = ["log_channel", "role_log_channel", "channel_log_channel",
                    "mute_log_channel", "whitelist_log_channel", "join_log_channel", "settings_channel"]
        log_ids = {str(settings.get(k)) for k in log_keys if settings.get(k)}

        # Роли
        for role in reversed(guild.roles):
            if role.is_default() or role.managed:
                continue
            data["roles"].append({
                "name": role.name, "color": role.color.value,
                "hoist": role.hoist, "mentionable": role.mentionable,
                "permissions": role.permissions.value, "position": role.position
            })

        # Категории — исключаем категорию Logs
        for cat in guild.categories:
            # Пропускаем категорию если все её каналы — лог-каналы бота
            cat_channel_ids = {str(ch.id) for ch in cat.channels}
            if cat_channel_ids and cat_channel_ids.issubset(log_ids):
                continue
            if "logs" in cat.name.lower() and cat_channel_ids.issubset(log_ids | {""}):
                continue
            overwrites = self._serialize_overwrites(cat, guild)
            data["categories"].append({
                "name": cat.name, "position": cat.position, "overwrites": overwrites
            })

        # Каналы — исключаем лог-каналы
        for ch in guild.channels:
            if isinstance(ch, discord.CategoryChannel):
                continue
            if str(ch.id) in log_ids:
                continue
            overwrites = self._serialize_overwrites(ch, guild)
            entry = {
                "name": ch.name, "type": str(ch.type),
                "position": ch.position,
                "category": ch.category.name if ch.category else None,
                "overwrites": overwrites
            }
            if isinstance(ch, discord.TextChannel):
                entry["topic"] = ch.topic
                entry["nsfw"] = ch.nsfw
                entry["slowmode"] = ch.slowmode_delay
            data["channels"].append(entry)

        return data

    def _serialize_overwrites(self, channel, guild):
        result = []
        for target, ow in channel.overwrites.items():
            if not hasattr(target, 'name'):
                continue
            result.append({
                "type": "role" if isinstance(target, discord.Role) else "member",
                "name": target.name,
                "id": str(target.id),
                "allow": ow.pair()[0].value,
                "deny": ow.pair()[1].value
            })
        return result

    async def _restore(self, guild, data):
        # Создаём роли
        role_map = {}
        for r in data["roles"]:
            try:
                new_role = await guild.create_role(
                    name=r["name"],
                    color=discord.Color(r["color"]),
                    hoist=r["hoist"],
                    mentionable=r["mentionable"],
                    permissions=discord.Permissions(r["permissions"])
                )
                role_map[r["name"]] = new_role
            except Exception as e:
                print(f"[RESTORE] Role {r['name']}: {e}")

        def get_overwrites(ow_list):
            overwrites = {}
            for ow in ow_list:
                # Сначала ищем по ID, потом по имени
                if ow["type"] == "role":
                    target = guild.get_role(int(ow.get("id", 0))) or discord.utils.get(guild.roles, name=ow["name"])
                else:
                    target = guild.get_member(int(ow.get("id", 0))) or discord.utils.get(guild.members, name=ow["name"])
                if target:
                    overwrites[target] = discord.PermissionOverwrite.from_pair(
                        discord.Permissions(ow["allow"]),
                        discord.Permissions(ow["deny"])
                    )
            return overwrites

        # Создаём категории
        cat_map = {}
        for cat in sorted(data["categories"], key=lambda x: x["position"]):
            try:
                new_cat = await guild.create_category(
                    name=cat["name"],
                    overwrites=get_overwrites(cat["overwrites"])
                )
                cat_map[cat["name"]] = new_cat
            except Exception as e:
                print(f"[RESTORE] Category {cat['name']}: {e}")

        # Создаём каналы
        for ch in sorted(data["channels"], key=lambda x: x["position"]):
            try:
                category = cat_map.get(ch["category"]) if ch["category"] else None
                overwrites = get_overwrites(ch["overwrites"])
                if ch["type"] == "text":
                    await guild.create_text_channel(
                        name=ch["name"], category=category,
                        topic=ch.get("topic"), nsfw=ch.get("nsfw", False),
                        slowmode_delay=ch.get("slowmode", 0),
                        overwrites=overwrites
                    )
                elif ch["type"] == "voice":
                    await guild.create_voice_channel(name=ch["name"], category=category, overwrites=overwrites)
            except Exception as e:
                print(f"[RESTORE] Channel {ch['name']}: {e}")


async def setup(bot):
    await bot.add_cog(Backup(bot))
