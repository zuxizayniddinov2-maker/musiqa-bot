import sqlite3
import json
import time
from typing import Optional, List, Dict, Any
from config import DATABASE_PATH, ADMIN_IDS

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
        
        # Media kesh jadvali (Telegram file_id larni saqlash orqali 0.05 soniyada qayta yuborish)
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

        # Sozlamalar jadvali (Funksiyalarni yoqish/o'chirish va moslashtirish)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Majburiy a'zolik kanallari jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                invite_link TEXT NOT NULL,
                created_at REAL
            )
        """)

        # Qo'shimcha menyu/reklama tugmalari jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extra_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                button_text TEXT NOT NULL,
                button_url TEXT NOT NULL,
                created_at REAL
            )
        """)

        # Qo'shimcha adminlar jadvali
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_at REAL
            )
        """)

        # Dastlabki birlamchi sozlamalarni o'rnatish
        default_settings = {
            "feature_search": "1",          # Musiqa qidiruvi
            "feature_3d": "1",              # 3D Ovoz effekti
            "feature_concert": "1",         # Konsert zali effekti
            "feature_social_video": "1",    # Instagram, TikTok, YouTube yuklash
            "feature_round_video": "1",     # Dumaloq video yaratish
            "feature_shazam": "1",          # Shazam orqali musiqani aniqlash
            "feature_mandatory_sub": "0",   # Majburiy obuna tekshiruvi (0=o'chiq, 1=yoqiq)
            "maintenance_mode": "0",        # Texnik ta'mirlash rejimi (0=o'chiq, 1=yoqiq)
            "custom_welcome_text": ""       # Maxsus start matni (bo'sh bo'lsa standart ishlaydi)
        }

        for k, v in default_settings.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        conn.commit()

# --- FOYDALANUVCHILAR ---

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

def get_all_user_ids() -> List[int]:
    """Barcha foydalanuvchilar ID larini olish (Xabarnoma uchun)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        return [row["user_id"] for row in cursor.fetchall()]

# --- MEDIA VA QIDIRUV KESHI ---

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

def clear_all_cache() -> Dict[str, int]:
    """Barcha keshlarni tozalash."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM search_cache")
        s_count = cursor.rowcount
        cursor.execute("DELETE FROM media_cache")
        m_count = cursor.rowcount
        conn.commit()
        return {"search": s_count, "media": m_count}

# --- SOZLAMALAR VA QO'SHIMCHALAR (FEATURE TOGGLES) ---

def get_setting(key: str, default: str = "") -> str:
    """Sozlama qiymatini olish."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

def set_setting(key: str, value: str):
    """Sozlama qiymatini yangilash."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))
        conn.commit()

def get_all_settings() -> Dict[str, str]:
    """Barcha sozlamalarni olish."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in cursor.fetchall()}

def is_feature_enabled(key: str) -> bool:
    """Qo'shimcha funksiya yoqilganmi yoki o'chirilganmi?"""
    return get_setting(key, "1") == "1"

# --- KANALLAR (MAJBURIY OBUNA) ---

def get_channels() -> List[Dict[str, Any]]:
    """Majburiy kanallar ro'yxatini olish."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, channel_id, title, invite_link FROM channels ORDER BY id ASC")
        return [dict(r) for r in cursor.fetchall()]

def add_channel(channel_id: str, title: str, invite_link: str) -> bool:
    """Kanal qo'shish."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO channels (channel_id, title, invite_link, created_at)
                VALUES (?, ?, ?, ?)
            """, (str(channel_id).strip(), title.strip(), invite_link.strip(), time.time()))
            conn.commit()
            return True
    except Exception:
        return False

def delete_channel(channel_id: str) -> bool:
    """Kanalni olib tashlash."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channels WHERE channel_id = ? OR id = ?", (str(channel_id), str(channel_id)))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted

# --- QO'SHIMCHA TUGMALAR (REKLAMA / FOYDALI LINKLAR) ---

def get_extra_buttons() -> List[Dict[str, Any]]:
    """Qo'shimcha menyu tugmalarini olish."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, button_text, button_url FROM extra_buttons ORDER BY id ASC")
        return [dict(r) for r in cursor.fetchall()]

def add_extra_button(text: str, url: str) -> bool:
    """Yangi menyu tugmasi qo'shish."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO extra_buttons (button_text, button_url, created_at)
                VALUES (?, ?, ?)
            """, (text.strip(), url.strip(), time.time()))
            conn.commit()
            return True
    except Exception:
        return False

def delete_extra_button(button_id: int) -> bool:
    """Tugmani olib tashlash."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM extra_buttons WHERE id = ?", (button_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted

# --- ADMINLAR BOSHQARUVI ---

def is_admin(user_id: int) -> bool:
    """Foydalanuvchi adminmi?"""
    if user_id in ADMIN_IDS:
        return True
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None

def add_admin(user_id: int) -> bool:
    """Yangi admin qo'shish."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO admins (user_id, added_at) VALUES (?, ?)", (user_id, time.time()))
            conn.commit()
            return True
    except Exception:
        return False

def remove_admin(user_id: int) -> bool:
    """Adminni olib tashlash."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted

def get_admins() -> List[int]:
    """Barcha adminlar ro'yxatini olish."""
    admin_set = set(ADMIN_IDS)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins")
        for row in cursor.fetchall():
            admin_set.add(row["user_id"])
    return sorted(list(admin_set))

# --- STATISTIKA ---

def get_stats() -> Dict[str, Any]:
    """Loyiha statistikasi."""
    now = time.time()
    today_start = now - 86400
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM users")
        total_users = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM users WHERE last_active >= ?", (today_start,))
        active_today = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM media_cache WHERE media_type = 'audio'")
        cached_audios = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM media_cache WHERE media_type = 'video'")
        cached_videos = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM media_cache WHERE media_type = 'video_note'")
        cached_rounds = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM search_cache")
        cached_searches = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM channels")
        channels_count = cursor.fetchone()["cnt"]

        return {
            "total_users": total_users,
            "active_today": active_today,
            "cached_audios": cached_audios,
            "cached_videos": cached_videos,
            "cached_rounds": cached_rounds,
            "cached_searches": cached_searches,
            "channels_count": channels_count
        }

# Baza jadvalini yaratib qo'yamiz
init_db()
