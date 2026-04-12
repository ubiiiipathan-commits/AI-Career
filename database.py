"""
database.py — MySQL using pymysql + environment variables
"""

import os
import json
import logging
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_connection():
    return pymysql.connect(
        host        = os.environ.get("MYSQL_HOST",     "localhost"),
        port        = int(os.environ.get("MYSQL_PORT", "3306")),
        user        = os.environ.get("MYSQL_USER",     "root"),
        password    = os.environ.get("MYSQL_PASSWORD", ""),
        database    = os.environ.get("MYSQL_DATABASE", "railway"),
        charset     = "utf8mb4",
        cursorclass = pymysql.cursors.DictCursor,
        autocommit  = True,
    )


def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    username      VARCHAR(80)         NOT NULL,
                    email         VARCHAR(120) UNIQUE NOT NULL,
                    password_hash VARCHAR(256)        NOT NULL,
                    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    user_id    INT NOT NULL,
                    filename   VARCHAR(255),
                    career     VARCHAR(120),
                    skills     TEXT,
                    roadmap    TEXT,
                    courses    TEXT,
                    raw_output TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        logger.info("Database initialised successfully.")
    except Exception as e:
        logger.error("Database init failed: %s", e)
        raise
    finally:
        conn.close()


def email_exists(email: str) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def create_user(username: str, email: str, password_hash: str) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (username, email, password_hash)
            )
            return conn.insert_id()
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            return cur.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, created_at FROM users WHERE id = %s",
                (user_id,)
            )
            return cur.fetchone()
    finally:
        conn.close()


def save_analysis(user_id: int, filename: str, career: str,
                  skills: list, roadmap: str, courses: list,
                  raw_output: str = "") -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO analyses
                    (user_id, filename, career, skills, roadmap, courses, raw_output)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, filename, career,
                json.dumps(skills),
                roadmap,
                json.dumps(courses),
                raw_output,
            ))
            return conn.insert_id()
    finally:
        conn.close()


def get_user_history(user_id: int, limit: int = 20) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, filename, career, skills, roadmap, courses, created_at
                FROM analyses
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            rows = cur.fetchall()
    finally:
        conn.close()
    for row in rows:
        row["skills"]     = json.loads(row["skills"])  if row["skills"]  else []
        row["courses"]    = json.loads(row["courses"]) if row["courses"] else []
        row["created_at"] = (
            row["created_at"].strftime("%d %b %Y, %I:%M %p")
            if row["created_at"] else ""
        )
    return rows


def get_analysis_by_id(analysis_id: int, user_id: int) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM analyses WHERE id = %s AND user_id = %s",
                (analysis_id, user_id)
            )
            row = cur.fetchone()
            if row:
                row["skills"]  = json.loads(row["skills"])  if row["skills"]  else []
                row["courses"] = json.loads(row["courses"]) if row["courses"] else []
                row["created_at"] = (
                    row["created_at"].strftime("%d %b %Y, %I:%M %p")
                    if row["created_at"] else ""
                )
            return row
    finally:
        conn.close()


def delete_analysis(analysis_id: int, user_id: int) -> bool:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM analyses WHERE id = %s AND user_id = %s",
                (analysis_id, user_id)
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def get_user_stats(user_id: int) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) as total FROM analyses WHERE user_id = %s",
                (user_id,)
            )
            total = cur.fetchone()["total"]
            cur.execute("""
                SELECT career, COUNT(*) as cnt
                FROM analyses WHERE user_id = %s
                GROUP BY career ORDER BY cnt DESC LIMIT 1
            """, (user_id,))
            top = cur.fetchone()
            return {
                "total_analyses": total,
                "top_career": top["career"] if top else None,
            }
    finally:
        conn.close()
