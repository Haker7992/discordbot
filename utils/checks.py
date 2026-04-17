import database as db
import config

def is_owner(user_id):
    return user_id in config.OWNER_IDS or user_id in db.get_extra_owners()

def is_owner_id(user_id):
    return user_id in config.OWNER_IDS or user_id in db.get_extra_owners()


def is_whitelisted(guild_id, user_id, permission=None, member=None):
    """
    Проверяет, разрешено ли действие пользователю.

    Порядок проверок:
    1. Owner бота — всегда разрешено.
    2. Роль участника есть в whitelist_roles данного сервера с нужным правом.
    3. Пользователь лично в whitelist данного сервера с нужным правом.

    Whitelist полностью per-guild — права на одном сервере не переносятся на другой.
    """
    if is_owner(user_id):
        return True

    if member is not None:
        guild = getattr(member, 'guild', None)
        member_role_ids = {str(r.id) for r in member.roles if r.id != (guild.id if guild else 0)}

        # Проверка whitelist_roles с учётом конкретного права (только для данного сервера)
        wl_roles = db.get_whitelist_roles(guild_id)
        for wl_role in wl_roles:
            if wl_role["role_id"] in member_role_ids:
                role_perms = wl_role.get("permissions", [])
                if permission is None:
                    return True
                if "all" in role_perms or permission in role_perms:
                    return True

    # Личный whitelist (только для данного сервера)
    entry = db.get_whitelist(guild_id, user_id)
    if not entry:
        return False
    if permission is None:
        return True
    return permission in entry["permissions"] or "all" in entry["permissions"]


def is_owner_or_admin(ctx):
    if is_owner(ctx.author.id):
        return True
    if not ctx.guild:
        return False
    return ctx.author.guild_permissions.administrator
