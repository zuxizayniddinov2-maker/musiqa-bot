import os
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from shazamio import Shazam

from config import DOWNLOADS_DIR

_shazam = None

def get_shazam_client() -> Shazam:
    global _shazam
    if _shazam is None:
        _shazam = Shazam()
    return _shazam

async def _extract_fast_audio_snippet(input_path: str) -> Optional[str]:
    """Videodan 8 soniyalik kichik yengil audio parcha ajratish (0.1 soniya)."""
    p = Path(input_path)
    snippet_path = str(DOWNLOADS_DIR / f"snip_{p.stem[:20]}.m4a")
    
    cmd = [
        "ffmpeg", "-y",
        "-ss", "0",
        "-t", "8",
        "-i", str(p),
        "-vn",
        "-c:a", "aac",
        "-b:a", "64k",
        "-threads", "0",
        snippet_path
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
        if Path(snippet_path).exists() and Path(snippet_path).stat().st_size > 500:
            return snippet_path
    except Exception:
        pass
    return None

async def recognize_song(file_path: str) -> Dict[str, Any]:
    """
    Fayldagi (video yoki audio) musiqani Shazam orqali tezkor (0.3-0.5s) aniqlash.
    Katta videolarni to'g'ridan-to'g'ri dekodlash o'rniga 8s yengil audio orqali taniydi.
    """
    p = Path(file_path)
    if not p.exists():
        return {"success": False, "error": "Fayl topilmadi"}

    # Agar fayl video bo'lsa yoki 1MB dan katta bo'lsa, tezkor 8 soniyalik snippet olamiz
    target_path = str(p)
    snippet = None
    if p.suffix.lower() in ['.mp4', '.mkv', '.webm', '.mov', '.avi'] or p.stat().st_size > 1024 * 1024:
        snippet = await _extract_fast_audio_snippet(str(p))
        if snippet:
            target_path = snippet

    try:
        shazam = get_shazam_client()
        out = await shazam.recognize(target_path)
        track = out.get("track")
        if track:
            title = track.get("title", "")
            artist = track.get("subtitle", "")
            query = f"{artist} - {title}".strip(" -")
            return {
                "success": True,
                "title": title,
                "artist": artist,
                "query": query,
                "share_url": track.get("url", "")
            }
        else:
            return {"success": False, "error": "Musiqa topilmadi"}
    except Exception as e:
        print(f"[SHAZAM XATOLIK]: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if snippet and Path(snippet).exists():
            try:
                os.remove(snippet)
            except Exception:
                pass
