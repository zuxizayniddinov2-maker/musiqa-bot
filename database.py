import sqlite3
import json
import time
from typing import Optional, List, Dict, Any
from config import DATABASE_PATH

def get_connection():
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Ma'lumotlar bazasini initsializatsiya qilish."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Foydalanuvchilar jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at REAL,
                last_active REAL
            )
        """)
        
        # Media kesh jadvali (Telegram file_id larni saqlash orqali 0.1 soniyada qayta yuborish)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT NOT NULL,
                media_type TEXT NOT NULL,
                file_id TEXT NOT NULL,
                title TEXT,
                performer TEXT,
                duration INTEGER,
                created_at REAL,
                UNIQUE(cache_key, media_type)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_key ON media_cache(cache_key, media_type)")

        # Qidiruv natijalari keshi (bir xil qidiruvni 0.001 soniyada chiqarish)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT UNIQUE NOT NULL,
                results_json TEXT NOT NULL,
                created_at REAL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_query ON search_cache(query)")

        conn.commit()

def register_user(user_id: int, username: Optional[str], first_name: Optional[str]):
    """Foydalanuvchini bazaga qo'shish yoki oxirgi faolligini yangilash."""
    now = time.time()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, joined_at, last_active)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_active = excluded.last_active
        """, (user_id, username, first_name, now, now))
        conn.commit()

def get_media_cache(cache_key: str, media_type: str) -> Optional[Dict[str, Any]]:
    """Media keshdan file_id ni olish."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_id, title, performer, duration FROM media_cache WHERE cache_key = ? AND media_type = ?",
            (cache_key, media_type)
        )
        row = cursor.fetchone()
        if row:
            return {
                "file_id": row["file_id"],
                "title": row["title"],
                "performer": row["performer"],
                "duration": row["duration"]
            }
        return None

def set_media_cache(cache_key: str, media_type: str, file_id: str, title: str = "", performer: str = "", duration: int = 0):
    """Media file_id ni keshga yozish."""
    now = time.time()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO media_cache (cache_key, media_type, file_id, title, performer, duration, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key, media_type) DO UPDATE SET
                file_id = excluded.file_id,
                title = excluded.title,
                performer = excluded.performer,
                duration = excluded.duration,
                created_at = excluded.created_at
        """, (cache_key, media_type, file_id, title, performer, duration, now))
        conn.commit()

def get_search_cache(query: str) -> Optional[List[Dict[str, Any]]]:
    """Qidiruv natijalarini keshdan olish (agar 24 soatdan oshmagan bo'lsa)."""
    norm_query = query.strip().lower()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT results_json, created_at FROM search_cache WHERE query = ?", (norm_query,))
        row = cursor.fetchone()
        if row:
            # 24 soatlik kesh
            if time.time() - row["created_at"] < 86400:
                try:
                    return json.loads(row["results_json"])
                except Exception:
                    pass
        return None

def set_search_cache(query: str, results: List[Dict[str, Any]]):
    """Qidiruv natijalarini keshga saqlash."""
    norm_query = query.strip().lower()
    now = time.time()
    results_json = json.dumps(results, ensure_ascii=False)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO search_cache (query, results_json, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(query) DO UPDATE SET
                results_json = excluded.results_json,
                created_at = excluded.created_at
        """, (norm_query, results_json, now))
        conn.commit()

# Baza jadvalini yaratib qo'yamiz
init_db()
