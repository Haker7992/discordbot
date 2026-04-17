import discord
from discord.ext import commands
from discord import app_commands
import database as db
from utils.checks import is_owner_or_admin
from utils.embeds import success, error, info


class RolesSelect(discord.ui.Select):
    def __init__(self, guild, user_id, current_role_ids):
        self.guild_id = guild.id
        self.user_id = user_id
        roles = [r for r in guild.roles if r.id != guild.id and not r.managed][:25]
        options = [
            discord.SelectOption(label=r.name[:25], value=str(r.id), default=str(r.id) in current_role_ids)
            for r in roles
        ] or [discord.SelectOption(label="Нет ролей", value="none")]
        super().__init__(placeholder="Выберите роли...", min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        role_ids = [v for v in self.values if v != "none"]
        db.update_protected_roles(self.guild_id, self.user_id, role_ids)
        roles_str = " ".join(f"<@&{r}>" for r in role_ids) or "нет"
        await interaction.response.edit_message(embed=success("Защита ролей", f"<@{self.user_id}>: {roles_str}"), view=None)


class RolesView(discord.ui.View):
    def __init__(self, guild, user_id, current_role_ids):
        super().__init__(timeout=30)
        self.add_item(RolesSelect(guild, user_id, current_role_ids))


def admin_check(interaction: discord.Interaction):
    from config import OWNER_IDS
    return interaction.user.guild_permissions.administrator or interaction.user.id in OWNER_IDS


protect_slash = app_commands.Group(name="protect", description="Защита пользователей")


@protect_slash.command(name="add", description="Добавить пользователя под защиту")
@app_commands.describe(user="Участник")
async def slash_protect_add(interaction: discord.Interaction, user: discord.Member):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    db.add_protected(interaction.guild.id, user.id)
    await interaction.response.send_message(embed=success("Защита", f"<@{user.id}> под защитой."), ephemeral=True)


@protect_slash.command(name="remove", description="Убрать пользователя из защиты")
@app_commands.describe(user="Участник")
async def slash_protect_remove(interaction: discord.Interaction, user: discord.Member):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    db.remove_protected(interaction.guild.id, user.id)
    await interaction.response.send_message(embed=success("Защита снята", f"<@{user.id}> больше не под защитой."), ephemeral=True)


@protect_slash.command(name="list", description="Список защищённых пользователей")
async def slash_protect_list(interaction: discord.Interaction):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    entries = db.get_all_protected(interaction.guild.id)
    if not entries:
        return await interaction.response.send_message(embed=info("Защита", "Нет защищённых."), ephemeral=True)
    desc = "\n".join(f"<@{e['user_id']}> — {' '.join(f'<@&{r}>' for r in e['role_ids']) or 'все роли'}" for e in entries)
    await interaction.response.send_message(embed=info("🛡️ Защищённые", desc), ephemeral=True)


@protect_slash.command(name="roles", description="Настроить защищённые роли")
@app_commands.describe(user="Участник")
async def slash_protect_roles(interaction: discord.Interaction, user: discord.Member):
    if not admin_check(interaction):
        return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
    entry = db.get_protected(interaction.guild.id, user.id)
    if not entry:
        return await interaction.response.send_message(embed=error("Ошибка", "Сначала: `/protect add`"), ephemeral=True)
    await interaction.response.send_message(embed=info("Роли", f"Выберите роли для <@{user.id}>:"), view=RolesView(interaction.guild, user.id, entry["role_ids"]), ephemeral=True)


class Protect(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Prefix команды ──
    @commands.group(name="protect", invoke_without_command=True)
    async def protect(self, ctx):
        await ctx.send(embed=info("Защита", "Использование: `!protect add/remove/list/roles`"))

    @protect.command(name="add")
    async def protect_add(self, ctx, user: discord.Member = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if not user:
            return await ctx.send(embed=error("Ошибка", "Укажите пользователя."))
        db.add_protected(ctx.guild.id, user.id)
        await ctx.send(embed=success("Защита", f"<@{user.id}> под защитой. Настройте роли: `!protect roles @user`"))

    @protect.command(name="remove")
    async def protect_remove(self, ctx, user: discord.Member = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if not user:
            return await ctx.send(embed=error("Ошибка", "Укажите пользователя."))
        db.remove_protected(ctx.guild.id, user.id)
        await ctx.send(embed=success("Защита снята", f"<@{user.id}> больше не под защитой."))

    @protect.command(name="list")
    async def protect_list(self, ctx):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        entries = db.get_all_protected(ctx.guild.id)
        if not entries:
            return await ctx.send(embed=info("Защита", "Нет защищённых."))
        desc = "\n".join(f"<@{e['user_id']}> — {' '.join(f'<@&{r}>' for r in e['role_ids']) or 'все роли'}" for e in entries)
        await ctx.send(embed=info("🛡️ Защищённые", desc))

    @protect.command(name="roles")
    async def protect_roles(self, ctx, user: discord.Member = None):
        if not is_owner_or_admin(ctx):
            return await ctx.send(embed=error("Нет доступа", "Только администраторы."))
        if not user:
            return await ctx.send(embed=error("Ошибка", "Укажите пользователя."))
        entry = db.get_protected(ctx.guild.id, user.id)
        if not entry:
            return await ctx.send(embed=error("Ошибка", "Сначала: `!protect add @user`"))
        await ctx.send(embed=info("Роли", f"Выберите роли для <@{user.id}>:"), view=RolesView(ctx.guild, user.id, entry["role_ids"]))

    # ── Slash команды ──
    protect_group = app_commands.Group(name="protect", description="Защита пользователей")

    @protect_group.command(name="add", description="Добавить пользователя под защиту")
    @app_commands.describe(user="Участник")
    async def slash_protect_add(self, interaction: discord.Interaction, user: discord.Member):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.add_protected(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=success("Защита", f"<@{user.id}> под защитой."), ephemeral=True)

    @protect_group.command(name="remove", description="Убрать пользователя из защиты")
    @app_commands.describe(user="Участник")
    async def slash_protect_remove(self, interaction: discord.Interaction, user: discord.Member):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.remove_protected(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=success("Защита снята", f"<@{user.id}> больше не под защитой."), ephemeral=True)

    @protect_group.command(name="list", description="Список защищённых пользователей")
    async def slash_protect_list(self, interaction: discord.Interaction):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        entries = db.get_all_protected(interaction.guild.id)
        if not entries:
            return await interaction.response.send_message(embed=info("Защита", "Нет защищённых."), ephemeral=True)
        desc = "\n".join(f"<@{e['user_id']}> — {' '.join(f'<@&{r}>' for r in e['role_ids']) or 'все роли'}" for e in entries)
        await interaction.response.send_message(embed=info("🛡️ Защищённые", desc), ephemeral=True)

    @protect_group.command(name="roles", description="Настроить защищённые роли")
    @app_commands.describe(user="Участник")
    async def slash_protect_roles(self, interaction: discord.Interaction, user: discord.Member):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        entry = db.get_protected(interaction.guild.id, user.id)
        if not entry:
            return await interaction.response.send_message(embed=error("Ошибка", "Сначала: `/protect add`"), ephemeral=True)
        await interaction.response.send_message(embed=info("Роли", f"Выберите роли для <@{user.id}>:"), view=RolesView(interaction.guild, user.id, entry["role_ids"]), ephemeral=True)


    # ── Slash команды ──
    protect_group = app_commands.Group(name="protect", description="Защита пользователей")

    @protect_group.command(name="add", description="Добавить пользователя под защиту")
    @app_commands.describe(user="Участник")
    async def slash_protect_add(self, interaction: discord.Interaction, user: discord.Member):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.add_protected(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=success("Защита", f"<@{user.id}> под защитой."), ephemeral=True)

    @protect_group.command(name="remove", description="Убрать пользователя из защиты")
    @app_commands.describe(user="Участник")
    async def slash_protect_remove(self, interaction: discord.Interaction, user: discord.Member):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        db.remove_protected(interaction.guild.id, user.id)
        await interaction.response.send_message(embed=success("Защита снята", f"<@{user.id}> больше не под защитой."), ephemeral=True)

    @protect_group.command(name="list", description="Список защищённых пользователей")
    async def slash_protect_list(self, interaction: discord.Interaction):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        entries = db.get_all_protected(interaction.guild.id)
        if not entries:
            return await interaction.response.send_message(embed=info("Защита", "Нет защищённых."), ephemeral=True)
        desc = "\n".join(f"<@{e['user_id']}> — {' '.join(f'<@&{r}>' for r in e['role_ids']) or 'все роли'}" for e in entries)
        await interaction.response.send_message(embed=info("🛡️ Защищённые", desc), ephemeral=True)

    @protect_group.command(name="roles", description="Настроить защищённые роли")
    @app_commands.describe(user="Участник")
    async def slash_protect_roles(self, interaction: discord.Interaction, user: discord.Member):
        if not admin_check(interaction):
            return await interaction.response.send_message(embed=error("Нет доступа", "Только администраторы."), ephemeral=True)
        entry = db.get_protected(interaction.guild.id, user.id)
        if not entry:
            return await interaction.response.send_message(embed=error("Ошибка", "Сначала: `/protect add`"), ephemeral=True)
        await interaction.response.send_message(embed=info("Роли", f"Выберите роли для <@{user.id}>:"), view=RolesView(interaction.guild, user.id, entry["role_ids"]), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Protect(bot))
