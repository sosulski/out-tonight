# db.py: everything that talks to the Postgres database lives here.
# Replit gives every app a Postgres database. Its address is in DATABASE_URL.

import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db():
    """Open a connection. Rows come back as dictionaries, like {"id": 1, ...}."""
    if not DATABASE_URL:
        raise RuntimeError("No DATABASE_URL. Open Tools > Database in Replit, then Run again.")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def create_tables():
    """Create the three tables the first time the app runs."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id           INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                display_name      TEXT,
                home_city         TEXT,
                favorite_category TEXT,
                bio               TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_events (
                id       SERIAL PRIMARY KEY,
                user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                event_id TEXT NOT NULL,
                name     TEXT NOT NULL,
                url      TEXT,
                date     TEXT,
                venue    TEXT,
                saved_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (user_id, event_id)
            )
        """)


# ---------- Users ----------

def create_user(username, password_hash):
    """Add a user and an empty profile. Returns the new user's id."""
    with get_db() as conn:
        row = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
            (username, password_hash),
        ).fetchone()
        conn.execute("INSERT INTO profiles (user_id, display_name) VALUES (%s, %s)",
                     (row["id"], username))
        return row["id"]


def get_user_by_username(username):
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE username = %s",
                            (username,)).fetchone()


def get_user_by_id(user_id):
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = %s",
                            (user_id,)).fetchone()


# ---------- Profiles ----------

def get_profile(user_id):
    with get_db() as conn:
        return conn.execute("SELECT * FROM profiles WHERE user_id = %s",
                            (user_id,)).fetchone()


def update_profile(user_id, display_name, home_city, favorite_category, bio):
    with get_db() as conn:
        conn.execute("""
            UPDATE profiles
            SET display_name = %s, home_city = %s, favorite_category = %s, bio = %s
            WHERE user_id = %s
        """, (display_name, home_city, favorite_category, bio, user_id))


# ---------- Saved events ----------

def save_event(user_id, event_id, name, url, date, venue):
    """Save an event. Saving the same event twice does nothing."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO saved_events (user_id, event_id, name, url, date, venue)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, event_id) DO NOTHING
        """, (user_id, event_id, name, url, date, venue))


def unsave_event(user_id, event_id):
    with get_db() as conn:
        conn.execute("DELETE FROM saved_events WHERE user_id = %s AND event_id = %s",
                     (user_id, event_id))


def get_saved_events(user_id):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM saved_events WHERE user_id = %s ORDER BY saved_at DESC",
            (user_id,),
        ).fetchall()


def get_saved_event_ids(user_id):
    """A set of event ids this user has saved, to show a filled star."""
    return {row["event_id"] for row in get_saved_events(user_id)}
