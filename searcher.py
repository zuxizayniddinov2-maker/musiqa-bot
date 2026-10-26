import re
import json
import asyncio
from typing import List, Dict, Any
import aiohttp
import yt_dlp

from database import get_search_cache, set_search_cache

_session: aiohttp.ClientSession = None

async def get_http_session() -> aiohttp.ClientSession:
    """Doimiy aiohttp sessiyasi (keep-alive ulanish orqali 0.1-0.3s tezlik)."""
    global _session
    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=4)
        connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
        _session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    return _session

def clean_song_title(raw_title: str) -> str:
    """Qo'shiq nomini ortiqcha teglardan tozalash."""
    cleaned = re.sub(
        r'[\(\[](?:Official\s*(?:Music\s*)?(?:Video|Audio|Visualizer|HD|4K|Clip)?|Klipi|Premyera|Lyrics|Audio|Full\s*Track|Original)[\)\]]',
        '',
        raw_title,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else raw_title

def parse_duration_sec(dur_text: str) -> int:
    """Davomiylik matnini (masalan, 3:45) soniyaga o'tkazish."""
    if not dur_text or dur_text in ('LIVE', 'SHORTS', '0:00'):
        return 0
    try:
        parts = [int(p) for p in dur_text.split(':')]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except Exception:
        return 0
    return 0

async def search_youtube_fast(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Doimiy aiohttp ulanishi orqali o'ta tezkor (0.3-0.5s) YouTube qidiruvi."""
    try:
        session = await get_http_session()
        url = f"https://www.youtube.com/results?search_query={query}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept-Language': 'uz,ru;q=0.9,en;q=0.8'
        }
        
        async with session.get(url, headers=headers) as response:
            html = await response.text()
            
        m = re.search(r'var ytInitialData = ({.*?});</script>', html)
        if not m:
            m = re.search(r'window\["ytInitialData"\] = ({.*?});', html)
            
        if m:
            data = json.loads(m.group(1))
            results = []
            seen_ids = set()

            def extract_videos(node):
                if isinstance(node, dict):
                    if 'videoRenderer' in node:
                        vr = node['videoRenderer']
                        vid = vr.get('videoId')
                        if vid and vid not in seen_ids:
                            # Jonli efir (live stream) va 15 daqiqadan ortiq videolarni chetlab o'tish
                            badges = str(vr.get('badges', []))
                            dur_text = vr.get('lengthText', {}).get('simpleText', '')
                            dur_sec = parse_duration_sec(dur_text)
                            if 'LIVE' in badges or dur_sec <= 0 or dur_sec > 900:
                                pass
                            else:
                                seen_ids.add(vid)
                                raw_title = ''.join(r.get('text', '') for r in vr.get('title', {}).get('runs', []))
                                channel = ''.join(r.get('text', '') for r in vr.get('ownerText', {}).get('runs', []))
                                
                                results.append({
                                    'id': vid,
                                    'title': clean_song_title(raw_title),
                                    'raw_title': raw_title,
                                    'duration': dur_text,
                                    'channel': channel,
                                    'url': f"https://www.youtube.com/watch?v={vid}"
                                })
                    for value in node.values():
                        if len(results) >= limit:
                            break
                        extract_videos(value)
                elif isinstance(node, list):
                    for item in node:
                        if len(results) >= limit:
                            break
                        extract_videos(item)

            extract_videos(data)
            if len(results) >= 5:
                return results[:limit]
    except Exception:
        pass

    # Zaxira usul: yt-dlp flat search
    return await asyncio.to_thread(search_ytdlp_fallback, query, limit)

def search_ytdlp_fallback(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Zaxira qidiruv (yt-dlp orqali)."""
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'no_warnings': True,
        'socket_timeout': 3,
    }
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch{limit * 2}:{query}", download=False)
            entries = res.get('entries', [])
            for entry in entries:
                if not entry or entry.get('is_live'):
                    continue
                dur_seconds = entry.get('duration') or 0
                if dur_seconds <= 0 or dur_seconds > 900:
                    continue
                vid = entry.get('id')
                raw_title = entry.get('title', '')
                m, s = divmod(int(dur_seconds), 60)
                duration = f"{m}:{s:02d}"
                uploader = entry.get('uploader', '') or entry.get('channel', '')
                
                results.append({
                    'id': vid,
                    'title': clean_song_title(raw_title),
                    'raw_title': raw_title,
                    'duration': duration,
                    'channel': uploader,
                    'url': f"https://www.youtube.com/watch?v={vid}"
                })
                if len(results) >= limit:
                    break
    except Exception:
        pass
    return results[:limit]

async def search_music_top10(query: str) -> List[Dict[str, Any]]:
    """
    Top 10 original musiqalarni qidirish (avval SQLite kesh: 0.001s, keyin aiohttp: 0.3s).
    """
    norm_query = query.lower().strip()
    cached = get_search_cache(norm_query)
    if cached:
        return cached

    results = await search_youtube_fast(query, 10)
    if results:
        set_search_cache(norm_query, results)
        
    return results
