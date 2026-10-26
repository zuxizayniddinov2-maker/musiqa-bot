import os
import re
import shutil
import urllib.request
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
import yt_dlp
from PIL import Image

try:
    if not shutil.which("ffmpeg"):
        import static_ffmpeg
        static_ffmpeg.add_paths()
except Exception:
    pass

from config import DOWNLOADS_DIR, MAX_FILE_SIZE_BYTES
from searcher import clean_song_title
import database

def get_audio_duration_ffprobe(filepath: str) -> int:
    """Fayl davomiyligini (soniya) ffprobe orqali aniqlash."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(filepath)
        ]
        res = subprocess.check_output(cmd, text=True, timeout=3).strip()
        return max(1, int(float(res)))
    except Exception:
        return 0

def fetch_direct_youtube_thumb(video_id: str) -> Optional[str]:
    """YouTube videoning rasmini 50ms da yuklab olish va 320x320 ga moslash."""
    thumb_path = DOWNLOADS_DIR / f"{video_id}.jpg"
    if thumb_path.exists() and thumb_path.stat().st_size > 500:
        return str(thumb_path)
        
    url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2) as resp:
            content = resp.read()
            if len(content) > 1000:
                with open(thumb_path, 'wb') as f:
                    f.write(content)
                # Telegram thumbnail qoidasi: o'lchami <= 320px bo'lishi kerak
                try:
                    with Image.open(thumb_path) as im:
                        im.thumbnail((320, 320))
                        im.convert("RGB").save(thumb_path, "JPEG", quality=90)
                except Exception:
                    pass
                return str(thumb_path)
    except Exception:
        pass
    return None

def _sync_download_audio(video_id_or_url: str) -> Optional[Dict[str, Any]]:
    """
    YouTube dan musiqani tezkor yuklash (403 xatosi oldi olingan).
    Android va iOS mijozlari orqali 403 xatosiz va maksimal tezlikda ishlaydi.
    """
    if video_id_or_url.startswith("http"):
        vid_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', video_id_or_url)
        video_id = vid_match.group(1) if vid_match else "audio"
        url = video_id_or_url
    else:
        video_id = video_id_or_url
        url = f"https://www.youtube.com/watch?v={video_id}"

    # Agar fayl avval yuklangan bo'lsa darhol qaytarish
    for ext in ['.mp3', '.m4a', '.opus', '.mp4']:
        existing = DOWNLOADS_DIR / f"{video_id}{ext}"
        if existing.exists() and existing.stat().st_size > 5000:
            thumb = fetch_direct_youtube_thumb(video_id)
            meta = database.get_media_cache(f"yt:{video_id}", "audio")
            title = meta.get("title") if meta else video_id
            performer = meta.get("performer") if meta else "Artist"
            duration = meta.get("duration", 0) if meta else 0
            
            if duration <= 0:
                duration = get_audio_duration_ffprobe(str(existing))
            
            # Agar mp4 bo'lsa, audio oqimini 0.05s da (-c:a copy) ajratish
            final_path = str(existing)
            if existing.suffix == '.mp4':
                m4a_path = existing.with_suffix('.m4a')
                if not m4a_path.exists():
                    subprocess.run([
                        "ffmpeg", "-y", "-i", str(existing),
                        "-vn", "-c:a", "copy",
                        str(m4a_path)
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if m4a_path.exists() and m4a_path.stat().st_size > 1000:
                    final_path = str(m4a_path)
                    
            return {
                "filepath": final_path,
                "title": title,
                "performer": performer,
                "duration": duration,
                "thumb_path": thumb,
                "id": video_id
            }

    # Rasmni fonda tezkor olish
    thumb = fetch_direct_youtube_thumb(video_id)

    # yt-dlp sozlamalari (tv_embedded va android orqali 403 xatosiz va maksimal tezlikda)
    ydl_opts = {
        'format': '140/ba[ext=m4a]/251/ba/18/b',
        'outtmpl': str(DOWNLOADS_DIR / f"{video_id}.%(ext)s"),
        'writethumbnail': False,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 5,
        'retries': 1,
        'max_filesize': 40 * 1024 * 1024,
        'match_filter': yt_dlp.utils.match_filter_func('!is_live & duration <= 900'),
        'concurrent_fragment_downloads': 4,
        'buffersize': 1024 * 1024,
        'extractor_args': {
            'youtube': {
                'player_client': ['tv_embedded', 'android']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None

            raw_title = info.get('title', 'Unknown Title')
            title = clean_song_title(raw_title)
            performer = info.get('artist') or info.get('uploader') or info.get('channel') or "Artist"
            duration = int(info.get('duration') or 0)

            actual_filename = ydl.prepare_filename(info)
            p = Path(actual_filename)
            if not p.exists():
                for ext in ['.m4a', '.mp3', '.opus', '.webm', '.mp4']:
                    cand = p.with_suffix(ext)
                    if cand.exists():
                        p = cand
                        break

            # Agar MP4 bo'lsa, audio oqimini 0.05 soniyada (-c:a copy) ajratamiz (re-encode yo'q!)
            if p.exists() and p.suffix == '.mp4':
                m4a_path = p.with_suffix('.m4a')
                if not m4a_path.exists():
                    subprocess.run([
                        "ffmpeg", "-y", "-i", str(p),
                        "-vn", "-c:a", "copy",
                        str(m4a_path)
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if m4a_path.exists() and m4a_path.stat().st_size > 1000:
                    p = m4a_path
            elif p.exists() and p.suffix in ['.webm', '.opus', '.ogg']:
                # Webm bo'lsa tezkor mp3 ga o'tkazamiz
                mp3_path = p.with_suffix('.mp3')
                if not mp3_path.exists():
                    subprocess.run([
                        "ffmpeg", "-y", "-i", str(p),
                        "-vn", "-c:a", "libmp3lame", "-b:a", "128k", "-threads", "4",
                        str(mp3_path)
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if mp3_path.exists() and mp3_path.stat().st_size > 1000:
                    p = mp3_path

            if duration <= 0 and p.exists():
                duration = get_audio_duration_ffprobe(str(p))

            return {
                "filepath": str(p),
                "title": title,
                "performer": performer,
                "duration": duration,
                "thumb_path": thumb,
                "id": video_id
            }
    except Exception as e:
        print(f"[AUDIO DOWNLOAD XATOLIK]: {e}")
        # Zaxira urinish: umumiy extractor bilan
        try:
            ydl_opts_backup = {
                'format': 'bestaudio/best',
                'outtmpl': str(DOWNLOADS_DIR / f"{video_id}.%(ext)s"),
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 8,
            }
            with yt_dlp.YoutubeDL(ydl_opts_backup) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    p = Path(ydl.prepare_filename(info))
                    if not p.exists():
                        for ext in ['.mp3', '.m4a', '.opus', '.webm', '.mp4']:
                            cand = p.with_suffix(ext)
                            if cand.exists():
                                p = cand
                                break
                    b_title = clean_song_title(info.get('title', 'Music'))
                    b_performer = info.get('uploader', 'Artist')
                    b_dur = int(info.get('duration') or 0)
                    if p.exists() and p.suffix == '.mp4':
                        mp3_path = p.with_suffix('.mp3')
                        if not mp3_path.exists():
                            subprocess.run([
                                "ffmpeg", "-y", "-i", str(p),
                                "-vn", "-c:a", "libmp3lame", "-b:a", "192k",
                                "-id3v2_version", "3", "-write_id3v1", "1",
                                "-metadata", f"title={b_title}",
                                "-metadata", f"artist={b_performer}",
                                str(mp3_path)
                            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if mp3_path.exists() and mp3_path.stat().st_size > 5000:
                            p = mp3_path
                    if b_dur <= 0 and p.exists():
                        b_dur = get_audio_duration_ffprobe(str(p))

                    return {
                        "filepath": str(p),
                        "title": b_title,
                        "performer": b_performer,
                        "duration": b_dur,
                        "thumb_path": thumb,
                        "id": video_id
                    }
        except Exception as e2:
            print(f"[ZAXIRA DOWNLOAD XATOLIK]: {e2}")

        return None

async def download_youtube_audio(video_id_or_url: str) -> Optional[Dict[str, Any]]:
    """Asinxron audio yuklash."""
    return await asyncio.to_thread(_sync_download_audio, video_id_or_url)

def _sync_download_social_video(url: str) -> Optional[Dict[str, Any]]:
    """Instagram, TikTok, YouTube Shorts va boshqa platformalardan video yuklash."""
    clean_url = url.split('?')[0].rstrip('/')
    url_id = re.sub(r'[^a-zA-Z0-9_]', '_', clean_url)[-30:]

    ydl_opts = {
        'format': 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'outtmpl': str(DOWNLOADS_DIR / f"vid_{url_id}.%(ext)s"),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 10,
        'retries': 2,
        'max_filesize': MAX_FILE_SIZE_BYTES,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None

            title = info.get('title') or "Video"
            duration = int(info.get('duration') or 0)
            width = info.get('width')
            height = info.get('height')

            actual_filename = ydl.prepare_filename(info)
            p = Path(actual_filename)
            if not p.exists():
                for ext in ['.mp4', '.mkv', '.webm']:
                    cand = p.with_suffix(ext)
                    if cand.exists():
                        p = cand
                        break

            return {
                "filepath": str(p),
                "title": title,
                "duration": duration,
                "width": width,
                "height": height,
                "thumb_path": None,
                "id": url_id,
                "url": url
            }
    except Exception as e:
        print(f"[VIDEO DOWNLOAD XATOLIK]: {e}")
        return None

async def download_social_video(url: str) -> Optional[Dict[str, Any]]:
    """Asinxron video yuklash."""
    return await asyncio.to_thread(_sync_download_social_video, url)
