"""
database.py — All database interactions in one place.
Uses mysql-connector-python with connection pooling.
"""

import os
import json
import logging
from dotenv import load_dotenv

# ── MUST load .env before pool is created ─────
load_dotenv()

import mysql.connector
from mysql.connector import pooling

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Connection Pool
# ─────────────────────────────────────────────

_pool = pooling.MySQLConnectionPool(
    pool_name = "career_pool",
    pool_size = 5,
    host      = os.environ.get("DB_HOST",     "localhost"),
    port      = int(os.environ.get("DB_PORT", "3306")),
    user      = os.environ.get("DB_USER",     "root"),
    password  = os.environ.get("DB_PASSWORD", "pathan@7970"),
    database  = os.environ.get("DB_NAME",     "career_db"),
)


def _get_conn():
    return _pool.get_connection()


# ─────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        username      VARCHAR(80)  NOT NULL,
        email         VARCHAR(120) NOT NULL UNIQUE,
        password_hash VARCHAR(256) NOT NULL,
        created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analyses (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        user_id    INT          NOT NULL,
        filename   VARCHAR(255),
        career     VARCHAR(120),
        skills     TEXT,
        roadmap    TEXT,
        courses    TEXT,
        raw_output TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """
]


def init_db():
    """Create tables if they don't exist."""
    conn   = _get_conn()
    cursor = conn.cursor()
    try:
        for stmt in SCHEMA_STATEMENTS:
            cursor.execute(stmt)
        conn.commit()
        logger.info("Database initialised successfully.")
    except Exception as e:
        conn.rollback()
        logger.error("Database init failed: %s", e)
        raise
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# User helpers
# ─────────────────────────────────────────────

def email_exists(email: str) -> bool:
    """Return True if email is already registered."""
    conn   = _get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()


def create_user(username: str, email: str, password_hash: str) -> int:
    """Insert a new user and return their id."""
    conn   = _get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def get_user_by_email(email: str) -> dict | None:
    """Return user row as dict, or None if not found."""
    conn   = _get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# Analysis helpers
# ─────────────────────────────────────────────

def save_analysis(user_id: int, filename: str, career: str,
                  skills: list, roadmap: str, courses: list,
                  raw_output: str = "") -> int:
    """Insert an analysis record and return its id."""
    conn   = _get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO analyses
               (user_id, filename, career, skills, roadmap, courses, raw_output)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                user_id,
                filename,
                career,
                json.dumps(skills),
                roadmap,
                json.dumps(courses),
                raw_output,
            )
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def get_user_history(user_id: int, limit: int = 20) -> list:
    """Return a list of analysis dicts for the given user."""
    conn   = _get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT id, filename, career, skills, roadmap, courses, created_at
               FROM analyses
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT %s""",
            (user_id, limit)
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    for row in rows:
        row["skills"]  = json.loads(row["skills"])  if row["skills"]  else []
        row["courses"] = json.loads(row["courses"]) if row["courses"] else []
        row["created_at"] = (
            row["created_at"].strftime("%d %b %Y, %I:%M %p")
            if row["created_at"] else ""
        )
    return rows


def get_analysis_by_id(analysis_id: int, user_id: int) -> dict | None:
    """Fetch a single analysis (only if it belongs to the user)."""
    conn   = _get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM analyses WHERE id = %s AND user_id = %s",
            (analysis_id, user_id)
        )
        row = cursor.fetchone()
        if row:
            row["skills"]  = json.loads(row["skills"])  if row["skills"]  else []
            row["courses"] = json.loads(row["courses"]) if row["courses"] else []
        return row
    finally:
        cursor.close()
        conn.close()