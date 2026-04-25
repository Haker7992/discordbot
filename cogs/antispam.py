import discord
from discord.ext import commands
import time
from collections import defaultdict
from utils.checks import is_whitelisted

# message_cache: guild_id -> user_id -> [timestamps]
_cache = defaultdict(lambda: defaultdict(list))


class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        member = message.guild.get_member(message.author.id)
        if is_whitelisted(message.guild.id, message.author.id, "all", member=member):
            return

        now = time.time()
        uid = message.author.id
        gid = message.guild.id

        times = _cache[gid][uid]
        times = [t for t in times if now - t < 5]
        times.append(now)
        _cache[gid][uid] = times

        # 5+ сообщений за 5 секунд — таймаут 5 минут
        if len(times) >= 5:
            try:
                await message.delete()
                member = message.guild.get_member(uid)
                if member:
                    await member.timeout(
                        discord.utils.utcnow() + __import__('datetime').timedelta(minutes=5),
                        reason="AntiSpam: спам сообщениями"
                    )
                    _cache[gid][uid] = []
                    print(f"[ANTISPAM] Timeout {uid} in {gid}")
            except Exception as e:
                print(f"[ANTISPAM] {e}")

        # Массовое упоминание ролей (3+)
        if len(message.role_mentions) >= 3:
            try:
                await message.delete()
                member = message.guild.get_member(uid)
                if member:
                    await member.timeout(
                        discord.utils.utcnow() + __import__('datetime').timedelta(minutes=10),
                        reason="AntiSpam: массовое упоминание ролей"
                    )
            except Exception as e:
                print(f"[ANTISPAM ROLES] {e}")


async def setup(bot):
    await bot.add_cog(AntiSpam(bot))
