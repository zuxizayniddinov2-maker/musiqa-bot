import os
import asyncio
import subprocess
from pathlib import Path
from typing import Optional
from config import DOWNLOADS_DIR

async def run_ffmpeg_command(cmd: list) -> bool:
    """FFmpeg buyrug'ini asinxron rejimda chaqirish."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            print(f"[FFMPEG XATOLIK]: {stderr.decode(errors='ignore')}")
            return False
        return True
    except Exception as e:
        print(f"[FFMPEG EXCEPTION]: {e}")
        return False

def get_media_duration(filepath: str) -> int:
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

async def apply_3d_effect(input_path: str, output_path: Optional[str] = None, title: str = "", performer: str = "") -> Optional[str]:
    """
    Musiqani 3D / 8D binaural ovoz effektiga o'tkazish.
    Haqiqiy MP3 formatda chiqadi va Telegram uni musiqa pleyerida ochadi.
    """
    p_in = Path(input_path)
    if not p_in.exists():
        return None
        
    if not output_path:
        output_path = str(p_in.parent / f"{p_in.stem}_3d.mp3")

    if Path(output_path).exists() and Path(output_path).stat().st_size > 5000:
        return output_path

    cmd = [
        "ffmpeg", "-y",
        "-vn",
        "-i", str(p_in),
        "-af", "apulsator=hz=0.125:amount=0.95",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-id3v2_version", "3",
        "-write_id3v1", "1",
        "-metadata", f"title={title} (3D Ovoz)" if title else "title=3D Ovoz",
        "-metadata", f"artist={performer}" if performer else "artist=3D Audio",
        "-threads", "0",
        str(output_path)
    ]
    
    success = await run_ffmpeg_command(cmd)
    return output_path if success and Path(output_path).exists() else None

async def apply_concert_effect(input_path: str, output_path: Optional[str] = None, title: str = "", performer: str = "") -> Optional[str]:
    """
    Musiqani ulkan stadion yoki konsert zalidagi jonli ijro atmosferasiga o'tkazish.
    Haqiqiy MP3 formatda chiqadi va Telegram uni musiqa pleyerida ochadi.
    """
    p_in = Path(input_path)
    if not p_in.exists():
        return None
        
    if not output_path:
        output_path = str(p_in.parent / f"{p_in.stem}_concert.mp3")

    if Path(output_path).exists() and Path(output_path).stat().st_size > 5000:
        return output_path

    cmd = [
        "ffmpeg", "-y",
        "-vn",
        "-i", str(p_in),
        "-af", "aecho=0.8:0.9:50|100:0.4|0.3,volume=1.15",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-id3v2_version", "3",
        "-write_id3v1", "1",
        "-metadata", f"title={title} (Konsert Versiya)" if title else "title=Konsert Versiya",
        "-metadata", f"artist={performer}" if performer else "artist=Live Concert",
        "-threads", "0",
        str(output_path)
    ]
    
    success = await run_ffmpeg_command(cmd)
    return output_path if success and Path(output_path).exists() else None

async def convert_to_video_note(input_path_or_url: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Har qanday video yoki URL ni 0.5 soniyada Telegram Dumaloq Video (Video Note) formatiga o'tkazish.
    360x360 o'lcham, crf=28, ultrafast preset orqali minimal hajmda va maksimal tezlikda ishlaydi.
    """
    if not output_path:
        stem = Path(input_path_or_url).stem if not input_path_or_url.startswith("http") else "round"
        output_path = str(DOWNLOADS_DIR / f"{stem}_round.mp4")

    if Path(output_path).exists() and Path(output_path).stat().st_size > 1000:
        return output_path

    cmd = [
        "ffmpeg", "-y",
        "-analyzeduration", "1M",
        "-probesize", "1M",
        "-i", str(input_path_or_url),
        "-t", "60",
        "-vf", "crop=min(iw\\,ih):min(iw\\,ih),scale=360:360",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-crf", "30",
        "-c:a", "aac",
        "-b:a", "64k",
        "-ar", "44100",
        "-threads", "0",
        str(output_path)
    ]
    
    success = await run_ffmpeg_command(cmd)
    return output_path if success and Path(output_path).exists() else None

async def extract_audio_from_video(input_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Videodan audioni alohida MP3 qilib ajratib olish (Telegram audio pleyeri uchun).
    """
    p_in = Path(input_path)
    if not p_in.exists():
        return None
        
    if not output_path:
        output_path = str(p_in.parent / f"{p_in.stem}_extracted.mp3")

    if Path(output_path).exists() and Path(output_path).stat().st_size > 1000:
        return output_path

    cmd = [
        "ffmpeg", "-y",
        "-vn",
        "-i", str(p_in),
        "-c:a", "libmp3lame",
        "-q:a", "3",
        "-threads", "0",
        str(output_path)
    ]
    
    success = await run_ffmpeg_command(cmd)
    return output_path if success and Path(output_path).exists() else None
