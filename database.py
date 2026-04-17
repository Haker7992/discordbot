import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "guard.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS whitelist (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                permissions TEXT NOT NULL DEFAULT '[]',
                added_at INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS protected_users (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role_ids TEXT NOT NULL DEFAULT '[]',
                added_at INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                ban_limit INTEGER DEFAULT 3,
                kick_limit INTEGER DEFAULT 3,
                mute_limit INTEGER DEFAULT 5,
                channel_delete_limit INTEGER DEFAULT 2,
                role_delete_limit INTEGER DEFAULT 2,
                role_remove_limit INTEGER DEFAULT 5,
                interval INTEGER DEFAULT 10,
                punishment TEXT DEFAULT 'ban',
                log_channel TEXT DEFAULT NULL,
                role_log_channel TEXT DEFAULT NULL,
                channel_log_channel TEXT DEFAULT NULL,
                mute_log_channel TEXT DEFAULT NULL,
                whitelist_log_channel TEXT DEFAULT NULL,
                settings_channel TEXT DEFAULT NULL,
                enabled INTEGER DEFAULT 1,
                restore_channels INTEGER DEFAULT 1,
                restore_roles INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS whitelist_roles (
                guild_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                permissions TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (guild_id, role_id)
            );
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rape_list (
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                reason TEXT DEFAULT '',
                ban_days INTEGER DEFAULT 0,
                added_at INTEGER NOT NULL,
                added_by TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS extra_owners (
                user_id TEXT PRIMARY KEY,
                added_by TEXT NOT NULL,
                added_at INTEGER NOT NULL
            );
        """)
    print("[DB] Initialized")
    # Миграции — добавляем новые колонки если их нет
    with get_conn() as conn:
        try:
            conn.execute("ALTER TABLE guild_settings ADD COLUMN restore_channels INTEGER DEFAULT 1")
            print("[DB] Migration: added restore_channels")
        except Exception:
            pass  # колонка уже существует
        try:
            conn.execute("ALTER TABLE guild_settings ADD COLUMN restore_roles INTEGER DEFAULT 1")
            print("[DB] Migration: added restore_roles")
        except Exception:
            pass  # колонка уже существует

# --- Whitelist ---
def add_whitelist(guild_id, user_id, permissions=None):
    if permissions is None:
        permissions = []
    import time
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO whitelist (guild_id, user_id, permissions, added_at) VALUES (?,?,?,?)",
            (str(guild_id), str(user_id), json.dumps(permissions), int(time.time()))
        )

def remove_whitelist(guild_id, user_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM whitelist WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id)))

def get_whitelist(guild_id, user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM whitelist WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id))).fetchone()
    if not row:
        return None
    return {"user_id": row["user_id"], "permissions": json.loads(row["permissions"])}

def get_all_whitelist(guild_id):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM whitelist WHERE guild_id=?", (str(guild_id),)).fetchall()
    return [{"user_id": r["user_id"], "permissions": json.loads(r["permissions"])} for r in rows]

def update_whitelist_perms(guild_id, user_id, permissions):
    with get_conn() as conn:
        conn.execute("UPDATE whitelist SET permissions=? WHERE guild_id=? AND user_id=?",
                     (json.dumps(permissions), str(guild_id), str(user_id)))

# --- Whitelist Roles ---
def add_whitelist_role(guild_id, role_id, permissions=None):
    if permissions is None:
        permissions = []
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO whitelist_roles (guild_id, role_id, permissions) VALUES (?,?,?)",
                     (str(guild_id), str(role_id), json.dumps(permissions)))

def remove_whitelist_role(guild_id, role_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM whitelist_roles WHERE guild_id=? AND role_id=?",
                     (str(guild_id), str(role_id)))

def get_whitelist_roles(guild_id):
    with get_conn() as conn:
        rows = conn.execute("SELECT role_id, permissions FROM whitelist_roles WHERE guild_id=?", (str(guild_id),)).fetchall()
    return [{"role_id": r["role_id"], "permissions": json.loads(r["permissions"])} for r in rows]

def update_whitelist_role_perms(guild_id, role_id, permissions):
    with get_conn() as conn:
        conn.execute("UPDATE whitelist_roles SET permissions=? WHERE guild_id=? AND role_id=?",
                     (json.dumps(permissions), str(guild_id), str(role_id)))

# --- Protected Users ---
def add_protected(guild_id, user_id, role_ids=None):
    if role_ids is None:
        role_ids = []
    import time
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO protected_users (guild_id, user_id, role_ids, added_at) VALUES (?,?,?,?)",
            (str(guild_id), str(user_id), json.dumps(role_ids), int(time.time()))
        )

def remove_protected(guild_id, user_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM protected_users WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id)))

def get_protected(guild_id, user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM protected_users WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id))).fetchone()
    if not row:
        return None
    return {"user_id": row["user_id"], "role_ids": json.loads(row["role_ids"])}

def get_all_protected(guild_id):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM protected_users WHERE guild_id=?", (str(guild_id),)).fetchall()
    return [{"user_id": r["user_id"], "role_ids": json.loads(r["role_ids"])} for r in rows]

def update_protected_roles(guild_id, user_id, role_ids):
    with get_conn() as conn:
        conn.execute("UPDATE protected_users SET role_ids=? WHERE guild_id=? AND user_id=?",
                     (json.dumps(role_ids), str(guild_id), str(user_id)))

# --- Guild Settings ---
def get_settings(guild_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM guild_settings WHERE guild_id=?", (str(guild_id),)).fetchone()
        if not row:
            conn.execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (str(guild_id),))
            row = conn.execute("SELECT * FROM guild_settings WHERE guild_id=?", (str(guild_id),)).fetchone()
    return dict(row)

def update_setting(guild_id, key, value):
    get_settings(guild_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE guild_settings SET {key}=? WHERE guild_id=?", (value, str(guild_id)))

# --- Action Log ---
def log_action(guild_id, user_id, action, details=""):
    import time
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO action_log (guild_id, user_id, action, details, timestamp) VALUES (?,?,?,?,?)",
            (str(guild_id), str(user_id), action, details, int(time.time()))
        )

def get_recent_actions(guild_id, user_id, action, since):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM action_log WHERE guild_id=? AND user_id=? AND action=? AND timestamp>?",
            (str(guild_id), str(user_id), action, int(since))
        ).fetchall()
    return rows

# --- Rape List ---
def add_rape(guild_id, user_id, reason, ban_days, added_by):
    import time
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO rape_list (guild_id, user_id, reason, ban_days, added_at, added_by) VALUES (?,?,?,?,?,?)",
            (str(guild_id), str(user_id), reason, int(ban_days), int(time.time()), str(added_by))
        )

def remove_rape(guild_id, user_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM rape_list WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id)))

def get_rape(guild_id, user_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM rape_list WHERE guild_id=? AND user_id=?",
            (str(guild_id), str(user_id))
        ).fetchone()
    return dict(row) if row else None

def get_all_rape(guild_id):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM rape_list WHERE guild_id=?", (str(guild_id),)).fetchall()
    return [dict(r) for r in rows]

# --- Extra Owners ---
def add_extra_owner(user_id, added_by):
    import time
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO extra_owners (user_id, added_by, added_at) VALUES (?,?,?)",
            (str(user_id), str(added_by), int(time.time()))
        )

def remove_extra_owner(user_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM extra_owners WHERE user_id=?", (str(user_id),))

def get_extra_owners():
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM extra_owners").fetchall()
    return [int(r["user_id"]) for r in rows]
