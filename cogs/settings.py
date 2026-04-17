import discord
from discord.ext import commands
from discord import app_commands
import database as db
from utils.checks import is_owner_or_admin
from utils.embeds import success, error, info
from config import COLORS


def settings_embed(settings):
    embed = discord.Embed(title="⚙️ ArchAngel Bot — Настройки", color=COLORS["primary"])
    embed.add_field(name="🔨 Лимит банов", value=f"`{settings['ban_limit']}`", inline=True)
    embed.add_field(name="👢 Лимит киков", value=f"`{settings['kick_limit']}`", inline=True)
    embed.add_field(name="🔇 Лимит мьютов", value=f"`{settings['mute_limit']}`", inline=True)
    embed.add_field(name="📁 Удал. каналов", value=f"`{settings['channel_delete_limit']}`", inline=True)
    embed.add_field(name="🏷️ Удал. ролей", value=f"`{settings['role_delete_limit']}`", inline=True)
    embed.add_field(name="👤 Снятие ролей", value=f"`{settings['role_remove_limit']}`", inline=True)
    embed.add_field(name="⏱️ Интервал (сек)", value=f"`{settings['interval']}`", inline=True)
    embed.add_field(name="⚡ Наказание", value=f"`{settings['punishment']}`", inline=True)
    log_ch = f"<#{settings['log_channel']}>" if settings.get('log_channel') else "`не задан`"
    embed.add_field(name="📋 Лог-канал", value=log_ch, inline=True)
    embed.add_field(name="🔌 Статус защиты", value="`включён`" if settings['enabled'] else "`выключен`", inline=True)
    restore_ch = settings.get('restore_channels', 1)
    restore_rl = settings.get('restore_roles', 1)
    embed.add_field(name="🔄 Восст. каналов", value="`вкл`" if restore_ch else "`выкл`", inline=True)
    embed.add_field(name="🏷️ Восст. ролей", value="`вкл`" if restore_rl else "`выкл`", inline=True)
    return embed


class SettingsSelect(discord.ui.Select):
    def __init__(self, guild_id, settings):
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label="🔨 Лимит банов", value="ban_limit", description=f"Текущее: {settings['ban_limit']}"),
            discord.SelectOption(label="👢 Лимит киков", value="kick_limit", description=f"Текущее: {settings['kick_limit']}"),
            discord.SelectOption(label="🔇 Лимит мьютов", value="mute_limit", description=f"Текущее: {settings['mute_limit']}"),
            discord.SelectOption(label="📁 Удал. каналов", value="channel_delete_limit", description=f"Текущее: {settings['channel_delete_limit']}"),
            discord.SelectOption(label="🏷️ Удал. ролей", value="role_delete_limit", description=f"Текущее: {settings['role_delete_limit']}"),
            discord.SelectOption(label="👤 Снятие ролей", value="role_remove_limit", description=f"Текущее: {settings['role_remove_limit']}"),
            discord.SelectOption(label="⏱️ Интервал (сек)", value="interval", description=f"Текущее: {settings['interval']}"),
        ]
        super().__init__(placeholder="Выберите параметр...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ValueModal(self.guild_id, self.values[0]))


class ValueModal(discord.ui.Modal, title="Изменить значение"):
    value = discord.ui.TextInput(label="Новое значение", placeholder="Введите число...", required=True)

    def __init__(self, guild_id, key):
        super().__init__()
        self.guild_id = guild_id
        self.key = key

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.value.value)
            if val < 1:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("Введите корректное число (минимум 1).", ephemeral=True)
        db.update_setting(self.guild_id, self.key, val)
        await interaction.response.edit_message(embed=settings_embed(db.get_settings(self.guild_id)))


class SettingsView(discord.ui.View):
    def __init__(self, guild_id, settings):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.add_item(SettingsSelect(guild_id, settings))

    @discord.ui.button(label="🔌 Вкл/Выкл защиту", style=discord.ButtonStyle.secondary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        s = db.get_settings(self.guild_id)
        db.update_setting(self.guild_id, "enabled", 0 if s["enabled"] else 1)
        await interaction.response.edit_message(embed=settings_embed(db.get_settings(self.guild_id)))

    @discord.ui.button(label="🔄 Вкл/Выкл восстановление каналов", style=discord.ButtonStyle.secondary)
    async def toggle_restore(self, interaction: discord.Interaction, button: discord.ui.Button):
        s = db.get_settings(self.guild_id)
        current = s.get("restore_channels", 1)
        db.update_setting(self.guild_id, "restore_channels", 0 if current else 1)
        await interaction.response.edit_message(embed=settings_embed(db.get_settings(self.guild_id)))

    @discord.ui.button(label="🏷️ Вкл/Выкл восстановление ролей", style=discord.ButtonStyle.secondary)
    async def toggle_restore_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        s = db.get_settings(self.guild_id)
        current = s.get("restore_roles", 1)
        db.update_setting(self.guild_id, "restore_roles", 0 if current else 1)
        await interaction.response.edit_message(embed=settings_embed(db.get_settings(self.guild_id)))


def admin_check(interaction: discord.Interaction):
    from config import OWNER_IDS
    return interaction.user.guild_permissions.administrator or interaction.user.id in OWNER_IDS


settings_slash = app_commands.Group(name="settings", description="Настройки бота")


@settings_slash.command(name="menu", description="Открыть меню настроек")
async def slash_settings_menu(interaction: discord.Interaction):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    s = db.get_settings(interaction.guild.id)
    await interaction.response.send_message(embed=settings_embed(s), view=SettingsView(interaction.guild.id, s), ephemeral=True)


@settings_slash.command(name="logchannel", description="Установить канал для логов")
@app_commands.describe(channel="Канал для логов")
async def slash_set_log(interaction: discord.Interaction, channel: discord.TextChannel):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    db.update_setting(interaction.guild.id, "log_channel", str(channel.id))
    await interaction.response.send_message(embed=success("Настройки", f"Лог-канал: <#{channel.id}>"), ephemeral=True)


@settings_slash.command(name="punishment", description="Тип наказания: ban или kick")
@app_commands.describe(ptype="ban или kick")
@app_commands.choices(ptype=[
    app_commands.Choice(name="ban", value="ban"),
    app_commands.Choice(name="kick", value="kick"),
])
async def slash_set_punishment(interaction: discord.Interaction, ptype: str):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    db.update_setting(interaction.guild.id, "punishment", ptype)
    await interaction.response.send_message(embed=success("Настройки", f"Тип наказания: `{ptype}`"), ephemeral=True)


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Prefix команды ──
    @commands.group(name="settings", invoke_without_command=True)
    async def settings(self, ctx):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        s = db.get_settings(ctx.guild.id)
        await ctx.send(embed=settings_embed(s), view=SettingsView(ctx.guild.id, s))

    @settings.command(name="logchannel")
    async def set_log(self, ctx, channel: discord.TextChannel = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if not channel:
            return await ctx.send(embed=error("Ошибка", "Укажите канал."))
        db.update_setting(ctx.guild.id, "log_channel", str(channel.id))
        await ctx.send(embed=success("Настройки", f"Лог-канал: <#{channel.id}>"))

    @settings.command(name="punishment")
    async def set_punishment(self, ctx, ptype: str = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if ptype not in ("ban", "kick"):
            return await ctx.send(embed=error("Ошибка", "Допустимо: `ban` или `kick`"))
        db.update_setting(ctx.guild.id, "punishment", ptype)
        await ctx.send(embed=success("Настройки", f"Тип наказания: `{ptype}`"))

    # ── Slash команды ──
    settings_group = app_commands.Group(name="settings", description="Настройки бота")

    @settings_group.command(name="menu", description="Открыть меню настроек")
    async def slash_settings(self, interaction: discord.Interaction):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        s = db.get_settings(interaction.guild.id)
        await interaction.response.send_message(embed=settings_embed(s), view=SettingsView(interaction.guild.id, s), ephemeral=True)

    @settings_group.command(name="logchannel", description="Установить канал для логов")
    @app_commands.describe(channel="Канал для логов")
    async def slash_set_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.update_setting(interaction.guild.id, "log_channel", str(channel.id))
        await interaction.response.send_message(embed=success("Настройки", f"Лог-канал: <#{channel.id}>"), ephemeral=True)

    @settings_group.command(name="punishment", description="Тип наказания: ban или kick")
    @app_commands.describe(ptype="ban или kick")
    @app_commands.choices(ptype=[
        app_commands.Choice(name="ban", value="ban"),
        app_commands.Choice(name="kick", value="kick"),
    ])
    async def slash_set_punishment(self, interaction: discord.Interaction, ptype: str):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.update_setting(interaction.guild.id, "punishment", ptype)
        await interaction.response.send_message(embed=success("Настройки", f"Тип наказания: `{ptype}`"), ephemeral=True)


    # ── Slash команды ──
    settings_group = app_commands.Group(name="settings", description="Настройки бота")

    @settings_group.command(name="menu", description="Открыть меню настроек")
    async def slash_settings(self, interaction: discord.Interaction):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        s = db.get_settings(interaction.guild.id)
        await interaction.response.send_message(embed=settings_embed(s), view=SettingsView(interaction.guild.id, s), ephemeral=True)

    @settings_group.command(name="logchannel", description="Установить канал для логов")
    @app_commands.describe(channel="Канал для логов")
    async def slash_set_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.update_setting(interaction.guild.id, "log_channel", str(channel.id))
        await interaction.response.send_message(embed=success("Настройки", f"Лог-канал: <#{channel.id}>"), ephemeral=True)

    @settings_group.command(name="punishment", description="Тип наказания: ban или kick")
    @app_commands.describe(ptype="ban или kick")
    @app_commands.choices(ptype=[
        app_commands.Choice(name="ban", value="ban"),
        app_commands.Choice(name="kick", value="kick"),
    ])
    async def slash_set_punishment(self, interaction: discord.Interaction, ptype: str):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.update_setting(interaction.guild.id, "punishment", ptype)
        await interaction.response.send_message(embed=success("Настройки", f"Тип наказания: `{ptype}`"), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Settings(bot))
