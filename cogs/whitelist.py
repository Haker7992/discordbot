import discord
from discord.ext import commands
from discord import app_commands
import database as db
from utils.checks import is_owner_or_admin
from utils.embeds import success, error, info, warning

PERMISSIONS = [
    discord.SelectOption(label="🔨 Баны", value="ban", description="Разрешить массовые баны"),
    discord.SelectOption(label="👢 Кики", value="kick", description="Разрешить массовые кики"),
    discord.SelectOption(label="🔇 Мьюты", value="mute", description="Разрешить массовые мьюты"),
    discord.SelectOption(label="📁 Каналы", value="channels", description="Разрешить удаление каналов"),
    discord.SelectOption(label="🏷️ Роли", value="roles", description="Разрешить управление ролями"),
    discord.SelectOption(label="🔗 Ссылки", value="links", description="Разрешить отправку ссылок"),
    discord.SelectOption(label="📢 @everyone/@here", value="mention_everyone", description="Разрешить упоминания всех"),
    discord.SelectOption(label="📨 Инвайты", value="invites", description="Разрешить создание инвайтов"),
    discord.SelectOption(label="⭐ Все права", value="all", description="Полный доступ"),
]


class PermsSelect(discord.ui.Select):
    def __init__(self, guild_id, user_id, mode="add"):
        self.guild_id = guild_id
        self.user_id = user_id
        self.mode = mode
        super().__init__(placeholder="Выберите разрешения...", min_values=0, max_values=len(PERMISSIONS), options=PERMISSIONS)

    async def callback(self, interaction: discord.Interaction):
        if self.mode == "add":
            db.add_whitelist(self.guild_id, self.user_id, self.values)
        else:
            db.update_whitelist_perms(self.guild_id, self.user_id, self.values)
        perms_str = ", ".join(self.values) if self.values else "нет"

        # Лог в whitelist канал
        guild = interaction.guild
        if guild:
            settings = db.get_settings(guild.id)
            wl_ch_id = settings.get("whitelist_log_channel")
            if wl_ch_id and str(wl_ch_id).isdigit():
                wl_ch = guild.get_channel(int(wl_ch_id))
                if wl_ch:
                    action = "добавлен" if self.mode == "add" else "обновлён"
                    embed = discord.Embed(title="✅ Whitelist обновлён", color=0x57F287)
                    embed.add_field(name="Пользователь", value=f"<@{self.user_id}>", inline=True)
                    embed.add_field(name="Действие", value=action, inline=True)
                    embed.add_field(name="Права", value=f"`{perms_str}`", inline=True)
                    embed.add_field(name="Кто изменил", value=interaction.user.mention, inline=True)
                    embed.timestamp = discord.utils.utcnow()
                    await wl_ch.send(embed=embed)

        await interaction.response.edit_message(
            embed=success("Whitelist", f"<@{self.user_id}> — права: `{perms_str}`"),
            view=None
        )


class PermsView(discord.ui.View):
    def __init__(self, guild_id, user_id, mode="add"):
        super().__init__(timeout=30)
        self.add_item(PermsSelect(guild_id, user_id, mode))

    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=warning("Отмена", "Операция отменена."), view=None)


# ── Select для прав роли ──
class RolePermsSelect(discord.ui.Select):
    def __init__(self, guild_id, role_id, current_perms):
        self.guild_id = guild_id
        self.role_id = role_id
        options = [
            discord.SelectOption(
                label=opt.label, value=opt.value,
                description=opt.description,
                default=opt.value in current_perms
            )
            for opt in PERMISSIONS
        ]
        super().__init__(placeholder="Выберите разрешения для роли...", min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        db.update_whitelist_role_perms(self.guild_id, self.role_id, list(self.values))
        perms_str = ", ".join(self.values) if self.values else "нет"

        # Лог
        guild = interaction.guild
        if guild:
            settings = db.get_settings(guild.id)
            wl_ch_id = settings.get("whitelist_log_channel")
            if wl_ch_id and str(wl_ch_id).isdigit():
                wl_ch = guild.get_channel(int(wl_ch_id))
                if wl_ch:
                    embed = discord.Embed(title="✅ Whitelist роли обновлён", color=0x57F287)
                    embed.add_field(name="Роль", value=f"<@&{self.role_id}>", inline=True)
                    embed.add_field(name="Права", value=f"`{perms_str}`", inline=True)
                    embed.add_field(name="Кто изменил", value=interaction.user.mention, inline=True)
                    embed.timestamp = discord.utils.utcnow()
                    await wl_ch.send(embed=embed)

        await interaction.response.edit_message(
            embed=success("Whitelist роли", f"<@&{self.role_id}> — права: `{perms_str}`"),
            view=None
        )


class RolePermsView(discord.ui.View):
    def __init__(self, guild_id, role_id, current_perms):
        super().__init__(timeout=30)
        self.add_item(RolePermsSelect(guild_id, role_id, current_perms))

    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=warning("Отмена", "Операция отменена."), view=None)


def admin_check(interaction: discord.Interaction):
    from config import OWNER_IDS
    return interaction.user.guild_permissions.administrator or interaction.user.id in OWNER_IDS


wl_slash = app_commands.Group(name="whitelist", description="Управление белым списком")


@wl_slash.command(name="add", description="Добавить пользователя в whitelist")
@app_commands.describe(user="Пользователь")
async def slash_wl_add(interaction: discord.Interaction, user: discord.User):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    await interaction.response.send_message(embed=info("Whitelist", f"Выберите права для <@{user.id}>:"), view=PermsView(interaction.guild.id, user.id), ephemeral=True)


@wl_slash.command(name="remove", description="Убрать пользователя из whitelist")
@app_commands.describe(user="Пользователь")
async def slash_wl_remove(interaction: discord.Interaction, user: discord.User):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    db.remove_whitelist(interaction.guild.id, user.id)
    await interaction.response.send_message(embed=success("Whitelist", f"<@{user.id}> удалён."), ephemeral=True)


@wl_slash.command(name="list", description="Показать whitelist")
async def slash_wl_list(interaction: discord.Interaction):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    entries = db.get_all_whitelist(interaction.guild.id)
    if not entries:
        return await interaction.response.send_message(embed=info("Whitelist", "Пуст."), ephemeral=True)
    desc = "\n".join(f"<@{e['user_id']}> — `{', '.join(e['permissions']) or 'нет'}`" for e in entries)
    await interaction.response.send_message(embed=info("📋 Whitelist", desc), ephemeral=True)


@wl_slash.command(name="perms", description="Изменить права пользователя")
@app_commands.describe(user="Пользователь")
async def slash_wl_perms(interaction: discord.Interaction, user: discord.User):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    entry = db.get_whitelist(interaction.guild.id, user.id)
    if not entry:
        return await interaction.response.send_message(embed=error("Ошибка", "Не в whitelist."), ephemeral=True)
    await interaction.response.send_message(embed=info("Права", f"Текущие: `{', '.join(entry['permissions']) or 'нет'}`"), view=PermsView(interaction.guild.id, user.id, "edit"), ephemeral=True)


class Whitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Prefix команды ──
    @commands.group(name="whitelist", invoke_without_command=True)
    async def whitelist(self, ctx):
        await ctx.send(embed=info("Whitelist", "Использование: `!whitelist add/remove/list/perms`"))

    @whitelist.command(name="add")
    async def wl_add(self, ctx, user: discord.User = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if not user:
            return await ctx.send(embed=error("Ошибка", "Укажите пользователя."))
        await ctx.send(embed=info("Whitelist", f"Выберите права для <@{user.id}>:"), view=PermsView(ctx.guild.id, user.id))

    @whitelist.command(name="remove")
    async def wl_remove(self, ctx, user: discord.User = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if not user:
            return await ctx.send(embed=error("Ошибка", "Укажите пользователя."))
        db.remove_whitelist(ctx.guild.id, user.id)
        await ctx.send(embed=success("Whitelist", f"<@{user.id}> удалён."))

    @whitelist.command(name="list")
    async def wl_list(self, ctx):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        entries = db.get_all_whitelist(ctx.guild.id)
        if not entries:
            return await ctx.send(embed=info("Whitelist", "Пуст."))
        desc = "\n".join(f"<@{e['user_id']}> — `{', '.join(e['permissions']) or 'нет'}`" for e in entries)
        await ctx.send(embed=info("📋 Whitelist", desc))

    @whitelist.command(name="perms")
    async def wl_perms(self, ctx, user: discord.User = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if not user:
            return await ctx.send(embed=error("Ошибка", "Укажите пользователя."))
        entry = db.get_whitelist(ctx.guild.id, user.id)
        if not entry:
            return await ctx.send(embed=error("Ошибка", "Не в whitelist."))
        await ctx.send(embed=info("Права", f"Текущие: `{', '.join(entry['permissions']) or 'нет'}`"), view=PermsView(ctx.guild.id, user.id, "edit"))

    @whitelist.group(name="role", invoke_without_command=True)
    async def wl_role(self, ctx):
        await ctx.send(embed=info("Whitelist Roles", "Использование: `!whitelist role add <role_id>`, `remove <role_id>`, `list`"))

    @wl_role.command(name="add")
    async def wl_role_add(self, ctx, role: discord.Role = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if not role:
            return await ctx.send(embed=error("Ошибка", "Укажите роль. Пример: `!whitelist role add @Модератор`"))
        db.add_whitelist_role(ctx.guild.id, role.id)
        await ctx.send(embed=success("Whitelist", f"Роль {role.mention} добавлена в whitelist. Все участники с этой ролью защищены."))

    @wl_role.command(name="remove")
    async def wl_role_remove(self, ctx, role: discord.Role = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if not role:
            return await ctx.send(embed=error("Ошибка", "Укажите роль."))
        db.remove_whitelist_role(ctx.guild.id, role.id)
        await ctx.send(embed=success("Whitelist", f"Роль {role.mention} удалена из whitelist."))

    @wl_role.command(name="list")
    async def wl_role_list(self, ctx):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        roles = db.get_whitelist_roles(ctx.guild.id)
        if not roles:
            return await ctx.send(embed=info("Whitelist Roles", "Нет ролей в whitelist."))
        desc = "\n".join(
            f"<@&{r['role_id']}> — `{', '.join(r['permissions']) or 'нет прав'}`"
            for r in roles
        )
        await ctx.send(embed=info("📋 Whitelist Roles", desc))

    @wl_role.command(name="perms")
    async def wl_role_perms(self, ctx, role: discord.Role = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if not role:
            return await ctx.send(embed=error("Ошибка", "Укажите роль. Пример: `!whitelist role perms @Модератор`"))
        roles = db.get_whitelist_roles(ctx.guild.id)
        entry = next((r for r in roles if r["role_id"] == str(role.id)), None)
        if not entry:
            return await ctx.send(embed=error("Ошибка", f"Роль {role.mention} не в whitelist. Сначала: `!whitelist role add @роль`"))
        current = entry.get("permissions", [])
        await ctx.send(
            embed=info("Права роли", f"Текущие права {role.mention}: `{', '.join(current) or 'нет'}`\nВыберите новые:"),
            view=RolePermsView(ctx.guild.id, str(role.id), current)
        )
    wl_group = app_commands.Group(name="whitelist", description="Управление белым списком")

    @wl_group.command(name="add", description="Добавить пользователя в whitelist")
    @app_commands.describe(user="Пользователь")
    async def slash_wl_add(self, interaction: discord.Interaction, user: discord.User):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        await interaction.response.send_message(embed=info("Whitelist", f"Выберите права для <@{user.id}>:"), view=PermsView(interaction.guild.id, user.id), ephemeral=True)

    @wl_group.command(name="remove", description="Убрать пользователя из whitelist")
    @app_commands.describe(user="Пользователь")
    async def slash_wl_remove(self, interaction: discord.Interaction, user: discord.User):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.remove_whitelist(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=success("Whitelist", f"<@{user.id}> удалён."), ephemeral=True)

    @wl_group.command(name="list", description="Показать whitelist")
    async def slash_wl_list(self, interaction: discord.Interaction):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        entries = db.get_all_whitelist(interaction.guild.id)
        if not entries:
            return await interaction.response.send_message(embed=info("Whitelist", "Пуст."), ephemeral=True)
        desc = "\n".join(f"<@{e['user_id']}> — `{', '.join(e['permissions']) or 'нет'}`" for e in entries)
        await interaction.response.send_message(embed=info("📋 Whitelist", desc), ephemeral=True)

    @wl_group.command(name="perms", description="Изменить права пользователя")
    @app_commands.describe(user="Пользователь")
    async def slash_wl_perms(self, interaction: discord.Interaction, user: discord.User):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        entry = db.get_whitelist(interaction.guild.id, user.id)
        if not entry:
            return await interaction.response.send_message(embed=error("Ошибка", "Не в whitelist."), ephemeral=True)
        await interaction.response.send_message(embed=info("Права", f"Текущие: `{', '.join(entry['permissions']) or 'нет'}`"), view=PermsView(interaction.guild.id, user.id, "edit"), ephemeral=True)

    @wl_group.command(name="role_add", description="Добавить роль в whitelist")
    @app_commands.describe(role="Роль")
    async def slash_wl_role_add(self, interaction: discord.Interaction, role: discord.Role):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.add_whitelist_role(interaction.guild.id, role.id)
        await interaction.response.send_message(
            embed=success("Whitelist", f"Роль {role.mention} добавлена. Настройте права: `/whitelist role_perms`"),
            ephemeral=True
        )

    @wl_group.command(name="role_remove", description="Убрать роль из whitelist")
    @app_commands.describe(role="Роль")
    async def slash_wl_role_remove(self, interaction: discord.Interaction, role: discord.Role):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.remove_whitelist_role(interaction.guild.id, role.id)
        await interaction.response.send_message(embed=success("Whitelist", f"Роль {role.mention} удалена из whitelist."), ephemeral=True)

    @wl_group.command(name="role_list", description="Список ролей в whitelist")
    async def slash_wl_role_list(self, interaction: discord.Interaction):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        roles = db.get_whitelist_roles(interaction.guild.id)
        if not roles:
            return await interaction.response.send_message(embed=info("Whitelist Roles", "Нет ролей в whitelist."), ephemeral=True)
        desc = "\n".join(
            f"<@&{r['role_id']}> — `{', '.join(r['permissions']) or 'нет прав'}`"
            for r in roles
        )
        await interaction.response.send_message(embed=info("📋 Whitelist Roles", desc), ephemeral=True)

    @wl_group.command(name="role_perms", description="Настроить права роли в whitelist")
    @app_commands.describe(role="Роль")
    async def slash_wl_role_perms(self, interaction: discord.Interaction, role: discord.Role):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        roles = db.get_whitelist_roles(interaction.guild.id)
        entry = next((r for r in roles if r["role_id"] == str(role.id)), None)
        if not entry:
            return await interaction.response.send_message(
                embed=error("Ошибка", f"Роль {role.mention} не в whitelist. Сначала: `/whitelist role_add`"),
                ephemeral=True
            )
        current = entry.get("permissions", [])
        await interaction.response.send_message(
            embed=info("Права роли", f"Текущие права {role.mention}: `{', '.join(current) or 'нет'}`\nВыберите новые:"),
            view=RolePermsView(interaction.guild.id, str(role.id), current),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Whitelist(bot))