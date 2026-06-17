import os
import sqlite3
import bcrypt
import json
from datetime import datetime

# Allow overriding DB path via env var (useful when attaching Render persistent disk)
DB_NAME = os.environ.get("DATABASE_PATH", "tasks.db")

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Tasks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            estimated_mins INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Pomodoro sessions
    c.execute('''
        CREATE TABLE IF NOT EXISTS pomodoro_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            duration_mins INTEGER NOT NULL,
            completed_at TEXT NOT NULL,
            session_type TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Study log (Daily aggregation)
    c.execute('''
        CREATE TABLE IF NOT EXISTS study_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            subject TEXT NOT NULL,
            hours_studied REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Reminders
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            due_date TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Settings
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (user_id, key),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize DB
init_db()

# --- Auth Helpers ---
def create_user(name, email, password):
    salt = bcrypt.gensalt()
    pwd_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)", (name, email, pwd_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(email, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, password_hash FROM users WHERE email=?", (email,))
    user = c.fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return {"id": user["id"], "name": user["name"]}
    return None

# --- Settings Helpers ---
def get_setting(user_id, key, default=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE user_id=? AND key=?", (user_id, key))
    row = c.fetchone()
    conn.close()
    return json.loads(row["value"]) if row else default

def set_setting(user_id, key, value):
    val_str = json.dumps(value)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (user_id, key, value) VALUES (?, ?, ?)", (user_id, key, val_str))
    conn.commit()
    conn.close()
