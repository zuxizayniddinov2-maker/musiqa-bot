import os
import re
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)
from aiogram.enums import ChatAction, ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

import config
import database
import searcher
import downloader
import effects
import shazam_helper
from admin import admin_router

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("MusicBot")

bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
dp.include_router(admin_router)

# Tezkor xotira keshlari (0.05s javob tezligi uchun)
active_media_files = {}
recognized_music_cache = {}
precomputed_rounds = {}
precomputed_audios = {}
in_flight_downloads = {}

def get_clean_filename(text: str, default: str = "music") -> str:
    """Fayl nomi uchun xavfsiz matn hosil qilish."""
    cleaned = re.sub(r'[^\w\s-]', '', text).strip()
    return cleaned if cleaned else default

# --- FONDA OLDINDAN TAYYORLASH (PRE-COMPUTE) ---

async def precompute_video_assets(url_id: str, video_path: str):
    """Video yuborilgach, orqa fonda musiqani, dumaloq videoni va audioni 0.1s da berishga tayyorlab qo'yish."""
    try:
        # 1. Shazam orqali musiqani fonda darhol aniqlab keshga qo'yish
        rec = await shazam_helper.recognize_song(video_path)
        if rec.get("success"):
            recognized_music_cache[url_id] = rec
            asyncio.create_task(searcher.search_music_top10(rec["query"]))
    except Exception as e:
        logger.error(f"Fonda Shazam xatosi: {e}")

    try:
        # 2. Dumaloq videoni fonda tayyorlab qo'yish
        r_path = await effects.convert_to_video_note(video_path)
        if r_path:
            precomputed_rounds[url_id] = r_path
    except Exception as e:
        logger.error(f"Fonda dumaloq video xatosi: {e}")

    try:
        # 3. Audioni fonda ajratib qo'yish
        a_path = await effects.extract_audio_from_video(video_path)
        if a_path:
            precomputed_audios[url_id] = a_path
    except Exception as e:
        logger.error(f"Fonda audio xatosi: {e}")

async def precompute_music_effects(video_id: str, audio_path: str, title: str = "", performer: str = ""):
    """Musiqa yuklanishi bilan 3D va Konsert ovozlarini fonda darhol tayyorlash."""
    try:
        await effects.apply_3d_effect(audio_path, title=title, performer=performer)
    except Exception as e:
        logger.error(f"Fonda 3D xatosi: {e}")

    try:
        await effects.apply_concert_effect(audio_path, title=title, performer=performer)
    except Exception as e:
        logger.error(f"Fonda konsert xatosi: {e}")


# --- TUGMALARNI SHAKLLANTIRISH ---

def get_search_keyboard(results: list) -> InlineKeyboardMarkup:
    """Top 10 musiqani tanlash uchun kreativ raqamli tugmalar."""
    row1 = []
    row2 = []
    for i, item in enumerate(results[:10], 1):
        vid_id = item['id']
        btn = InlineKeyboardButton(text=f"▶️ {i}", callback_data=f"m:{vid_id}")
        if i <= 5:
            row1.append(btn)
        else:
            row2.append(btn)
    
    rows = []
    if row1:
        rows.append(row1)
    if row2:
        rows.append(row2)
    rows.append([
        InlineKeyboardButton(text="❌ Yopish", callback_data="close_msg")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_audio_keyboard(video_id: str) -> InlineKeyboardMarkup:
    """Musiqa tagidagi 3D va Konsert ovoz tugmalari."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎧 3D Ovoz", callback_data=f"3d:{video_id}"),
            InlineKeyboardButton(text="🏟️ Konsert", callback_data=f"c:{video_id}")
        ]
    ])

def get_video_keyboard(url_id: str) -> InlineKeyboardMarkup:
    """Video tagidagi maxsus imkoniyat tugmalari."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 Musiqa", callback_data=f"vm:{url_id}"),
            InlineKeyboardButton(text="⭕ Dumaloq video", callback_data=f"vr:{url_id}")
        ],
        [
            InlineKeyboardButton(text="🔊 Video audio", callback_data=f"va:{url_id}")
        ]
    ])

def get_direct_video_keyboard(file_id: str) -> InlineKeyboardMarkup:
    """Foydalanuvchi tashlagan video uchun tugmalar."""
    short_id = file_id[-20:]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 Musiqasini aniqlash", callback_data=f"dvm:{short_id}"),
            InlineKeyboardButton(text="🔊 Video audio", callback_data=f"dva:{short_id}")
        ]
    ])


# --- RENDER HEALTH SERVER VA MIDLVARALAR ---

async def handle_health_check(request):
    """Render.com uchun HTTP Health Check javobi."""
    stats = database.get_stats()
    return web.json_response({
        "status": "ok",
        "service": "EchoMusiqa Bot",
        "timestamp": time.time(),
        "total_users": stats.get("total_users", 0),
        "active_today": stats.get("active_today", 0)
    })

async def start_render_health_server():
    """Render.com Web Service $PORT da HTTP serverni ko'tarish."""
    port = config.PORT
    try:
        app = web.Application()
        app.router.add_get("/", handle_health_check)
        app.router.add_get("/health", handle_health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Render HTTP server 0.0.0.0:{port} portida muvaffaqiyatli ishga tushdi.")
    except Exception as e:
        logger.error(f"Render HTTP serverni ko'tarishda xatolik: {e}")

def is_in_maintenance(user_id: int) -> bool:
    """Agar texnik ta'mirlash yoqilgan bo'lsa va user admin bo'lmasa True qaytadi."""
    if database.get_setting("maintenance_mode", "0") == "1":
        return not database.is_admin(user_id)
    return False

async def check_user_subscriptions(user_id: int) -> tuple[bool, list]:
    """Foydalanuvchi majburiy kanallarga a'zo bo'lganmi?"""
    if not database.is_feature_enabled("feature_mandatory_sub"):
        return True, []
    if database.is_admin(user_id):
        return True, []
    channels = database.get_channels()
    if not channels:
        return True, []
    unsub = []
    for ch in channels:
        try:
            m = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
            if m.status in ("left", "kicked"):
                unsub.append(ch)
        except Exception as e:
            logger.warning(f"Kanal a'zoligi tekshirishda xatolik ({ch['channel_id']}): {e}")
    return (len(unsub) == 0), unsub

def get_subscription_keyboard(unsub_channels: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in unsub_channels:
        rows.append([InlineKeyboardButton(text=f"📢 {ch['title']}", url=ch['invite_link'])])
    rows.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_start_keyboard(user_id: int = 0) -> Optional[InlineKeyboardMarkup]:
    """Start menyusi uchun qo'shimcha tugmalar (Admin tomonidan qo'shilgan)."""
    rows = []
    if user_id and database.is_admin(user_id):
        rows.append([InlineKeyboardButton(text="👑 Boshqaruv Paneli (Admin)", callback_data="admin:main")])
    extra_btns = database.get_extra_buttons()
    for b in extra_btns:
        rows.append([InlineKeyboardButton(text=b["button_text"], url=b["button_url"])])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


# --- START BUYRUG'I (0.02s TEZLIK) ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Start buyrug'i: Keng qamrovli, kreativ va me'yorida smayllar bilan bezatilgan ma'lumot."""
    asyncio.create_task(asyncio.to_thread(
        database.register_user,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    ))

    # Texnik ishlar tekshiruvi
    if is_in_maintenance(message.from_user.id):
        await message.answer("🛠️ <b>Botda texnik ta'mirlash ishlari olib borilmoqda.</b>\n<i>Tez orada qayta ishga tushadi!</i>")
        return

    # Majburiy obuna tekshiruvi
    is_sub, unsub = await check_user_subscriptions(message.from_user.id)
    if not is_sub:
        await message.answer(
            "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi homiy kanallarga a'zo bo'ling:</b>",
            reply_markup=get_subscription_keyboard(unsub)
        )
        return
    
    user_name = message.from_user.first_name or "Aziz do'stim"
    custom_txt = database.get_setting("custom_welcome_text", "")
    if custom_txt:
        text = custom_txt.replace("{name}", user_name)
    else:
        text = (
            f"⚡ <b>EchoMusiqa Bot olamiga xush kelibsiz, {user_name}!</b>\n\n"
            f"Ushbu bot eng ilg'or texnologiyalar asosida qurilgan bo'lib, har qanday multimedia "
            f"amallarini <b>0.5 soniyada</b> chaqmoqdek tezlikda bajarish imkoniyatiga ega.\n\n"
            f"✨ <b>Botning barcha imkoniyatlari:</b>\n\n"
            f"🎵 <b>Top 10 Original Musiqa Qidiruvi:</b>\n"
            f"Qo'shiq nomi, ijrochi yoki taronaning bir parchasini yozing — bot internet bo'ylab "
            f"eng original, yuqori sifatli Top 10 talikni bir zumda taqdim etadi.\n\n"
            f"🎧 <b>3D Ovoz va 🏟️ Konsert Zali Akustikasi:</b>\n"
            f"Har qanday qo'shiqni yangicha jarangda kashf eting:\n"
            f"• <b>3D Ovoz:</b> Quloqchinlarda tinglanganda tovush 360° aylanuvchi fazoviy (8D) effekt kasb etadi.\n"
            f"• <b>Konsert Zali:</b> Taronaga ulkan stadion va jonli konsert arenasidagi aks-sado (reverb) bag'ishlaydi.\n\n"
            f"📥 <b>Instagram, TikTok va YouTube Yuklovchi:</b>\n"
            f"Ijtimoiy tarmoqlardagi Reels, Shorts va video havolalarini tashlang — video maksimal tiniqlikda "
            f"va suv belgilarisiz tezkor yuklab beriladi.\n\n"
            f"⭕ <b>Telegram Dumaloq Video (Video Note):</b>\n"
            f"Ijtimoiy tarmoq videolarini yoki botga o'zingiz yuborgan har qanday videoni 0.5 soniyada "
            f"haqiqiy Telegram dumaloq video xabariga aylantiring.\n\n"
            f"🔍 <b>Shazam — Videodagi Musiqani Topish:</b>\n"
            f"Videoda yangragan ohang yoqdimi? Birgina tugma bilan aqlli Shazam orqali videodagi "
            f"musiqani aniqlang va uning original Top 10 taligini oling.\n\n"
            f"🔊 <b>Videodan Audio Ajratish:</b>\n"
            f"Har qanday videoning musiqa yoki ovoz yo'lakchasini yuqori sifatli audio (MP3) formatda ajratib oling.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Musiqa izlash uchun uning nomini yozing yoki video yuklash uchun havola yuboring!</i>"
        )
    
    await message.answer(text, reply_markup=get_start_keyboard(message.from_user.id))


@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery):
    """Majburiy obunani qayta tekshirish."""
    is_sub, unsub = await check_user_subscriptions(callback.from_user.id)
    if is_sub:
        await callback.answer("✅ Rahmat! Barcha kanallarga muvaffaqiyatli a'zo bo'lgansiz.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await cmd_start(callback.message)
    else:
        await callback.answer("❌ Hali hamma kanallarga a'zo emassiz! Iltimos, barchasiga ulaning.", show_alert=True)


@dp.callback_query(F.data == "close_msg")
async def cb_close_msg(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


# --- QIDIRUV VA HAVOLA ISHLOVCHILARI (0.3s TEZLIK) ---

async def handle_search_query(message: Message, query: str):
    """Musiqa qidiruvi: 0.05s da javob, 0.3s da Top 10 talikni chiqarish."""
    if is_in_maintenance(message.from_user.id):
        await message.answer("🛠️ <b>Botda texnik ta'mirlash ishlari olib borilmoqda.</b>")
        return

    is_sub, unsub = await check_user_subscriptions(message.from_user.id)
    if not is_sub:
        await message.answer("⚠️ <b>Musiqa qidirish uchun avval homiy kanallarga a'zo bo'ling:</b>", reply_markup=get_subscription_keyboard(unsub))
        return

    if not database.is_feature_enabled("feature_search"):
        await message.answer("⚠️ <b>Musiqa qidiruvi xizmati admin tomonidan vaqtincha to'xtatilgan.</b>")
        return

    norm_query = query.lower().strip()
    cached = database.get_search_cache(norm_query)

    status_msg = None
    if cached:
        results = cached
    else:
        status_msg = await message.answer(f"⚡ <b>«{query}» qidirilmoqda...</b>")
        results = await searcher.search_music_top10(query)

    if not results:
        err_text = f"🔍 «<b>{query}</b>» bo'yicha hech qanday musiqa topilmadi."
        if status_msg:
            await status_msg.edit_text(err_text)
        else:
            await message.answer(err_text)
        return
        
    lines = [f"🎵 <b>«{query}» bo'yicha TOP 10 original musiqa:</b>\n"]
    for i, item in enumerate(results[:10], 1):
        dur = f" ⏱ <i>{item['duration']}</i>" if item.get('duration') and item['duration'] != '0:00' else ""
        ch = f"\n    👤 <i>{item['channel']}</i>" if item.get('channel') else ""
        lines.append(f"<b>{i}.</b> 🎶 <b>{item['title']}</b>{dur}{ch}")
        
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⬇️ <b>Yuklab olish uchun quyidagi raqamlardan birini bosing:</b>")
    
    keyboard = get_search_keyboard(results)
    if status_msg:
        await status_msg.edit_text("\n".join(lines), reply_markup=keyboard)
    else:
        await message.answer("\n".join(lines), reply_markup=keyboard)

    # Faqat 1-musiqani fonda ehtiyotkorlik bilan oldindan yuklab qo'yish (tarmoqni band qilmaslik uchun)
    if results:
        top_item = results[0]
        vid = top_item['id']
        dur_sec = searcher.parse_duration_sec(top_item.get('duration', ''))
        if 0 < dur_sec <= 480 and vid not in in_flight_downloads:
            in_flight_downloads[vid] = asyncio.create_task(downloader.download_youtube_audio(vid))


async def handle_video_url(message: Message, url: str):
    """Instagram, TikTok yoki YouTube videosini tezkor yuklash."""
    if is_in_maintenance(message.from_user.id):
        await message.answer("🛠️ <b>Botda texnik ta'mirlash ishlari olib borilmoqda.</b>")
        return

    is_sub, unsub = await check_user_subscriptions(message.from_user.id)
    if not is_sub:
        await message.answer("⚠️ <b>Video yuklash uchun avval homiy kanallarga a'zo bo'ling:</b>", reply_markup=get_subscription_keyboard(unsub))
        return

    if not database.is_feature_enabled("feature_social_video"):
        await message.answer("⚠️ <b>Ijtimoiy tarmoqlardan video yuklash xizmati admin tomonidan vaqtincha to'xtatilgan.</b>")
        return

    clean_url = url.split('?')[0].rstrip('/')
    url_id = re.sub(r'[^a-zA-Z0-9_]', '_', clean_url)[-30:]
    
    # 1. Kesh tekshiruvi (0.05 soniya!)
    cached = database.get_media_cache(f"video:{url_id}", "video")
    if cached and cached.get("file_id"):
        await message.answer_video(
            video=cached["file_id"],
            caption=f"🎬 <b>{cached.get('title') or 'Video'}</b>\n⚡ @echomusiqa_bot",
            reply_markup=get_video_keyboard(url_id)
        )
        candidates = list(config.DOWNLOADS_DIR.glob(f"*{url_id}*.mp4"))
        if candidates:
            asyncio.create_task(precompute_video_assets(url_id, str(candidates[0])))
        return

    status_msg = await message.answer("📥 <b>Video yuklab olinmoqda... (0.5s)</b>")
    await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)

    # 2. Yuklab olish
    info = await downloader.download_social_video(url)

    if not info or not Path(info["filepath"]).exists():
        await status_msg.edit_text("⚠️ Videoni yuklab bo'lmadi. Havolani yoki video ochiqligini tekshiring.")
        return

    filepath = info["filepath"]
    active_media_files[url_id] = filepath
    
    video_file = FSInputFile(filepath)
    sent_msg = await message.answer_video(
        video=video_file,
        caption=f"🎬 <b>{info.get('title') or 'Video'}</b>\n⚡ @echomusiqa_bot",
        duration=info.get("duration", 0),
        width=info.get("width"),
        height=info.get("height"),
        reply_markup=get_video_keyboard(url_id)
    )
    try:
        await status_msg.delete()
    except Exception:
        pass
    
    if sent_msg.video:
        database.set_media_cache(
            cache_key=f"video:{url_id}",
            media_type="video",
            file_id=sent_msg.video.file_id,
            title=info.get('title', 'Video'),
            duration=info.get("duration", 0)
        )

    # 3. Fonda musiqani, dumaloq videoni va audioni oldindan tayyorlash
    asyncio.create_task(precompute_video_assets(url_id, filepath))


@dp.message(F.text)
async def on_text_message(message: Message):
    """Matn kelganda (Havola yoki Musiqa nomi)."""
    text = message.text.strip()
    if text.startswith("/"):
        return

    asyncio.create_task(asyncio.to_thread(
        database.register_user,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    ))

    url_match = config.URL_PATTERN.search(text)
    if url_match:
        await handle_video_url(message, url_match.group(0))
    else:
        await handle_search_query(message, text)


# --- MUSIQA YUKLAB BERISH (0.1s TEZLIK) ---

@dp.callback_query(F.data.startswith("m:"))
async def cb_download_music(callback: CallbackQuery):
    """Foydalanuvchi qidiruvdagi 1..10 raqamli tugmani bosganda."""
    is_sub, unsub = await check_user_subscriptions(callback.from_user.id)
    if not is_sub:
        await callback.message.answer("⚠️ <b>Musiqa yuklash uchun avval homiy kanallarga a'zo bo'ling:</b>", reply_markup=get_subscription_keyboard(unsub))
        return

    video_id = callback.data.split(":", 1)[1]
    await callback.answer("⚡ Musiqa yuborilmoqda...")

    # 1. Kesh tekshirish (0.05 soniyada yuborish)
    cached = database.get_media_cache(f"yt:{video_id}", "audio")
    if cached and cached.get("file_id"):
        caption = f"🎶 <b>{cached['title']}</b>\n👤 <i>{cached['performer']}</i>\n⚡ @echomusiqa_bot"
        await callback.message.answer_audio(
            audio=cached["file_id"],
            title=cached["title"],
            performer=cached["performer"],
            duration=cached["duration"],
            caption=caption,
            reply_markup=get_audio_keyboard(video_id)
        )
        return

    status_msg = await callback.message.answer("⚡ <b>Musiqa tayyorlanmoqda... (0.5s)</b>")
    await bot.send_chat_action(callback.message.chat.id, ChatAction.UPLOAD_VOICE)

    # 2. Yuklab olish (agar fonda yuklanayotgan bo'lsa kutamiz)
    if video_id in in_flight_downloads:
        info = await in_flight_downloads[video_id]
    else:
        task = asyncio.create_task(downloader.download_youtube_audio(video_id))
        in_flight_downloads[video_id] = task
        info = await task

    if not info or not Path(info["filepath"]).exists():
        await status_msg.edit_text("⚠️ Ushbu musiqani yuklab bo'lmadi. Ro'yxatdagi boshqa raqamni tanlang.")
        return

    filepath = info["filepath"]
    active_media_files[video_id] = filepath

    clean_name = get_clean_filename(f"{info['performer']} - {info['title']}")
    ext = Path(filepath).suffix or ".mp3"
    audio_file = FSInputFile(filepath, filename=f"{clean_name}{ext}")
    thumb_file = FSInputFile(info["thumb_path"]) if info.get("thumb_path") and Path(info["thumb_path"]).exists() else None
    caption = f"🎶 <b>{info['title']}</b>\n👤 <i>{info['performer']}</i>\n⚡ @echomusiqa_bot"

    sent = await callback.message.answer_audio(
        audio=audio_file,
        title=info["title"],
        performer=info["performer"],
        duration=info["duration"] if info.get("duration", 0) > 0 else None,
        thumbnail=thumb_file,
        caption=caption,
        reply_markup=get_audio_keyboard(video_id)
    )
    try:
        await status_msg.delete()
    except Exception:
        pass

    if sent.audio:
        database.set_media_cache(
            cache_key=f"yt:{video_id}",
            media_type="audio",
            file_id=sent.audio.file_id,
            title=info["title"],
            performer=info["performer"],
            duration=info["duration"]
        )


# --- 3D OVOZ EFFEKTI (HAQIQIY MP3 QO'SHIQ SHAKLIDA) ---

@dp.callback_query(F.data.startswith("3d:"))
async def cb_effect_3d(callback: CallbackQuery):
    """Musiqani 3D ovoz effektiga o'tkazish (Telegram musiqa pleyeri uchun MP3)."""
    if not database.is_feature_enabled("feature_3d"):
        await callback.answer("⚠️ 3D ovoz effekti admin tomonidan vaqtincha to'xtatilgan.", show_alert=True)
        return

    video_id = callback.data.split(":", 1)[1]
    await callback.answer("🎧 3D ovoz yuborilmoqda...")

    # 1. Asl musiqa ma'lumotlarini olish
    orig_meta = database.get_media_cache(f"yt:{video_id}", "audio")
    title = orig_meta["title"] if orig_meta and orig_meta.get("title") else "Musiqa"
    performer = orig_meta["performer"] if orig_meta and orig_meta.get("performer") else "3D Audio"
    duration = orig_meta["duration"] if orig_meta and orig_meta.get("duration") else 0

    # 2. Kesh tekshirish (0.05s!)
    cached = database.get_media_cache(f"3d:{video_id}", "audio_3d")
    if cached and cached.get("file_id"):
        cached_dur = cached.get("duration") or duration
        await callback.message.answer_audio(
            audio=cached["file_id"],
            title=cached.get("title") or f"{title} (3D Ovoz)",
            performer=cached.get("performer") or performer,
            duration=cached_dur if cached_dur and cached_dur > 0 else None,
            caption=f"🎧 <b>{title} (3D Ovoz)</b>\n👤 <i>{performer}</i>\n⚡ @echomusiqa_bot"
        )
        return

    status_msg = await callback.message.answer("🎧 <b>3D ovoz tayyorlanmoqda... (0.5s)</b>")

    # 3. Manbani topish
    source_path = active_media_files.get(video_id)
    if not source_path or not Path(source_path).exists():
        candidates = list(config.DOWNLOADS_DIR.glob(f"*{video_id}*.mp3")) or \
                     list(config.DOWNLOADS_DIR.glob(f"*{video_id}*.m4a")) or \
                     list(config.DOWNLOADS_DIR.glob(f"*{video_id}*.mp4"))
        if candidates:
            source_path = str(candidates[0])
            active_media_files[video_id] = source_path
        else:
            if video_id in in_flight_downloads:
                info = await in_flight_downloads[video_id]
            else:
                task = asyncio.create_task(downloader.download_youtube_audio(video_id))
                in_flight_downloads[video_id] = task
                info = await task
            if not info:
                await status_msg.edit_text("⚠️ Audio fayl topilmadi.")
                return
            source_path = info["filepath"]
            active_media_files[video_id] = source_path
            title = info["title"]
            performer = info["performer"]
            duration = info["duration"]

    # 4. 3D MP3 yaratish
    out_3d = await effects.apply_3d_effect(source_path, title=title, performer=performer)
    if not out_3d or not Path(out_3d).exists():
        await status_msg.edit_text("⚠️ 3D ovoz yaratishda xatolik yuz berdi.")
        return

    if duration <= 0 and Path(out_3d).exists():
        duration = effects.get_media_duration(out_3d)

    clean_name = get_clean_filename(f"{performer} - {title}")
    audio_file = FSInputFile(out_3d, filename=f"{clean_name} (3D).mp3")
    thumb_path = config.DOWNLOADS_DIR / f"{video_id}.jpg"
    thumb_file = FSInputFile(str(thumb_path)) if thumb_path.exists() else None

    # 5. Telegram musiqa pleyeri uchun qo'shiq qilib yuborish
    sent = await callback.message.answer_audio(
        audio=audio_file,
        title=f"{title} (3D Ovoz)",
        performer=performer,
        duration=duration if duration > 0 else None,
        thumbnail=thumb_file,
        caption=f"🎧 <b>{title} (3D Ovoz)</b>\n👤 <i>{performer}</i>\n⚡ @echomusiqa_bot"
    )
    try:
        await status_msg.delete()
    except Exception:
        pass

    if sent.audio:
        database.set_media_cache(
            cache_key=f"3d:{video_id}",
            media_type="audio_3d",
            file_id=sent.audio.file_id,
            title=f"{title} (3D Ovoz)",
            performer=performer,
            duration=duration
        )


# --- KONSERT EFFEKTI (HAQIQIY MP3 QO'SHIQ SHAKLIDA) ---

@dp.callback_query(F.data.startswith("c:"))
async def cb_effect_concert(callback: CallbackQuery):
    """Musiqani Konsert Zali ovoz effektiga o'tkazish (Telegram musiqa pleyeri uchun MP3)."""
    if not database.is_feature_enabled("feature_concert"):
        await callback.answer("⚠️ Konsert effekti admin tomonidan vaqtincha to'xtatilgan.", show_alert=True)
        return

    video_id = callback.data.split(":", 1)[1]
    await callback.answer("🏟️ Konsert ovozi yuborilmoqda...")

    # 1. Asl musiqa ma'lumotlarini olish
    orig_meta = database.get_media_cache(f"yt:{video_id}", "audio")
    title = orig_meta["title"] if orig_meta and orig_meta.get("title") else "Musiqa"
    performer = orig_meta["performer"] if orig_meta and orig_meta.get("performer") else "Live Concert"
    duration = orig_meta["duration"] if orig_meta and orig_meta.get("duration") else 0

    # 2. Kesh tekshirish (0.05s!)
    cached = database.get_media_cache(f"c:{video_id}", "audio_concert")
    if cached and cached.get("file_id"):
        cached_dur = cached.get("duration") or duration
        await callback.message.answer_audio(
            audio=cached["file_id"],
            title=cached.get("title") or f"{title} (Konsert Versiya)",
            performer=cached.get("performer") or performer,
            duration=cached_dur if cached_dur and cached_dur > 0 else None,
            caption=f"🏟️ <b>{title} (Konsert Versiya)</b>\n👤 <i>{performer}</i>\n⚡ @echomusiqa_bot"
        )
        return

    status_msg = await callback.message.answer("🏟️ <b>Konsert ovozi tayyorlanmoqda... (0.5s)</b>")

    # 3. Manbani topish
    source_path = active_media_files.get(video_id)
    if not source_path or not Path(source_path).exists():
        candidates = list(config.DOWNLOADS_DIR.glob(f"*{video_id}*.mp3")) or \
                     list(config.DOWNLOADS_DIR.glob(f"*{video_id}*.m4a")) or \
                     list(config.DOWNLOADS_DIR.glob(f"*{video_id}*.mp4"))
        if candidates:
            source_path = str(candidates[0])
            active_media_files[video_id] = source_path
        else:
            if video_id in in_flight_downloads:
                info = await in_flight_downloads[video_id]
            else:
                task = asyncio.create_task(downloader.download_youtube_audio(video_id))
                in_flight_downloads[video_id] = task
                info = await task
            if not info:
                await status_msg.edit_text("⚠️ Audio fayl topilmadi.")
                return
            source_path = info["filepath"]
            active_media_files[video_id] = source_path
            title = info["title"]
            performer = info["performer"]
            duration = info["duration"]

    # 4. Konsert MP3 yaratish
    out_concert = await effects.apply_concert_effect(source_path, title=title, performer=performer)
    if not out_concert or not Path(out_concert).exists():
        await status_msg.edit_text("⚠️ Konsert ovozi yaratib bo'lmadi.")
        return

    if duration <= 0 and Path(out_concert).exists():
        duration = effects.get_media_duration(out_concert)

    clean_name = get_clean_filename(f"{performer} - {title}")
    audio_file = FSInputFile(out_concert, filename=f"{clean_name} (Konsert).mp3")
    thumb_path = config.DOWNLOADS_DIR / f"{video_id}.jpg"
    thumb_file = FSInputFile(str(thumb_path)) if thumb_path.exists() else None

    # 5. Telegram musiqa pleyeri uchun qo'shiq qilib yuborish
    sent = await callback.message.answer_audio(
        audio=audio_file,
        title=f"{title} (Konsert Versiya)",
        performer=performer,
        duration=duration if duration > 0 else None,
        thumbnail=thumb_file,
        caption=f"🏟️ <b>{title} (Konsert Versiya)</b>\n👤 <i>{performer}</i>\n⚡ @echomusiqa_bot"
    )
    try:
        await status_msg.delete()
    except Exception:
        pass

    if sent.audio:
        database.set_media_cache(
            cache_key=f"c:{video_id}",
            media_type="audio_concert",
            file_id=sent.audio.file_id,
            title=f"{title} (Konsert Versiya)",
            performer=performer,
            duration=duration
        )


# --- VIDEO AMALLARI: MUSIQA (0.05s), DUMALOQ VIDEO (0.05s), AUDIO (0.05s) ---

@dp.callback_query(F.data.startswith("vm:"))
async def cb_video_music(callback: CallbackQuery):
    """Videodagi musiqani Shazam orqali aniqlash va Top 10 talikni 0.05s da chiqarish."""
    if not database.is_feature_enabled("feature_shazam"):
        await callback.answer("⚠️ Videodan musiqani aniqlash admin tomonidan vaqtincha to'xtatilgan.", show_alert=True)
        return

    url_id = callback.data.split(":", 1)[1]
    await callback.answer("🔍 Videodagi musiqa aniqlandi!")

    # 1. Oldindan aniqlangan keshni tekshirish (0.01 soniya!)
    pre_rec = recognized_music_cache.get(url_id)
    if pre_rec and pre_rec.get("success"):
        await callback.message.answer(
            f"🎯 <b>Videodagi musiqa aniqlandi:</b>\n"
            f"🎵 <b>{pre_rec['title']}</b>\n"
            f"👤 <i>{pre_rec['artist']}</i>\n\n"
            f"⬇️ <i>Quyida uning TOP 10 original varianti:</i>"
        )
        await handle_search_query(callback.message, pre_rec["query"])
        return

    # 2. Agar keshda bo'lmasa, tezkor aniqlash
    video_path = active_media_files.get(url_id)
    if not video_path or not Path(video_path).exists():
        candidates = list(config.DOWNLOADS_DIR.glob(f"*{url_id}*.mp4"))
        if candidates:
            video_path = str(candidates[0])
            active_media_files[url_id] = video_path

    search_query = None
    if video_path and Path(video_path).exists():
        recognition = await shazam_helper.recognize_song(video_path)
        if recognition.get("success"):
            recognized_music_cache[url_id] = recognition
            search_query = recognition["query"]
            await callback.message.answer(
                f"🎯 <b>Videodagi musiqa aniqlandi:</b>\n"
                f"🎵 <b>{recognition['title']}</b>\n"
                f"👤 <i>{recognition['artist']}</i>\n\n"
                f"⬇️ <i>Quyida uning TOP 10 original varianti:</i>"
            )

    if not search_query:
        cached = database.get_media_cache(f"video:{url_id}", "video")
        if cached and cached.get("title"):
            search_query = cached["title"]
        else:
            search_query = "top music"

    await handle_search_query(callback.message, search_query)


@dp.callback_query(F.data.startswith("vr:"))
async def cb_video_round(callback: CallbackQuery):
    """Videoni Telegram dumaloq videosiga aylantirish (0.05-0.3 soniya)."""
    if not database.is_feature_enabled("feature_round_video"):
        await callback.answer("⚠️ Dumaloq video tayyorlash admin tomonidan vaqtincha to'xtatilgan.", show_alert=True)
        return

    url_id = callback.data.split(":", 1)[1]
    await callback.answer("⭕ Dumaloq video yuborilmoqda...")

    # 1. Telegram File ID keshi (0.05 soniya!)
    cached = database.get_media_cache(f"round:{url_id}", "video_note")
    if cached and cached.get("file_id"):
        await callback.message.answer_video_note(video_note=cached["file_id"])
        return

    # 2. Oldindan tayyorlangan fayl keshi (0.05 soniya!)
    pre_round = precomputed_rounds.get(url_id)
    if pre_round and Path(pre_round).exists():
        sent = await callback.message.answer_video_note(video_note=FSInputFile(pre_round))
        if sent.video_note:
            database.set_media_cache(f"round:{url_id}", "video_note", sent.video_note.file_id)
        return

    status_msg = await callback.message.answer("⭕ <b>Dumaloq video tayyorlanmoqda... (0.5s)</b>")
    await bot.send_chat_action(callback.message.chat.id, ChatAction.RECORD_VIDEO_NOTE)

    # 3. Fayldan konvertatsiya qilish
    video_path = active_media_files.get(url_id)
    if not video_path or not Path(video_path).exists():
        candidates = list(config.DOWNLOADS_DIR.glob(f"*{url_id}*.mp4"))
        if candidates:
            video_path = str(candidates[0])
            active_media_files[url_id] = video_path
        else:
            await status_msg.edit_text("⚠️ Video fayl topilmadi.")
            return

    round_path = await effects.convert_to_video_note(video_path)
    if not round_path or not Path(round_path).exists():
        await status_msg.edit_text("⚠️ Dumaloq video yaratib bo'lmadi.")
        return

    sent = await callback.message.answer_video_note(video_note=FSInputFile(round_path))
    try:
        await status_msg.delete()
    except Exception:
        pass

    if sent.video_note:
        database.set_media_cache(
            cache_key=f"round:{url_id}",
            media_type="video_note",
            file_id=sent.video_note.file_id
        )


@dp.callback_query(F.data.startswith("va:"))
async def cb_video_audio(callback: CallbackQuery):
    """Videoning audiosini ajratish (MP3 formatda)."""
    url_id = callback.data.split(":", 1)[1]
    await callback.answer("🔊 Audio yuborilmoqda...")

    # 1. Kesh
    cached = database.get_media_cache(f"audio:{url_id}", "video_audio")
    if cached and cached.get("file_id"):
        await callback.message.answer_audio(
            audio=cached["file_id"],
            title=cached["title"],
            caption=f"🔊 <b>{cached['title']}</b>\n⚡ @echomusiqa_bot",
            reply_markup=get_audio_keyboard(url_id)
        )
        return

    # 2. Oldindan ajratilgan fayl keshi (0.05 soniya!)
    pre_audio = precomputed_audios.get(url_id)
    if pre_audio and Path(pre_audio).exists():
        cached_video = database.get_media_cache(f"video:{url_id}", "video")
        title = cached_video["title"] if cached_video else "Video Audio"
        clean_name = get_clean_filename(title)
        sent = await callback.message.answer_audio(
            audio=FSInputFile(pre_audio, filename=f"{clean_name}.mp3"),
            title=title,
            performer="Echo Musiqa",
            caption=f"🔊 <b>{title}</b>\n⚡ @echomusiqa_bot",
            reply_markup=get_audio_keyboard(url_id)
        )
        if sent.audio:
            database.set_media_cache(f"audio:{url_id}", "video_audio", sent.audio.file_id, title=title)
        return

    status_msg = await callback.message.answer("🔊 <b>Audio ajratilmoqda... (0.5s)</b>")

    # 3. Faylni topish
    video_path = active_media_files.get(url_id)
    if not video_path or not Path(video_path).exists():
        candidates = list(config.DOWNLOADS_DIR.glob(f"*{url_id}*.mp4"))
        if candidates:
            video_path = str(candidates[0])
            active_media_files[url_id] = video_path
        else:
            await status_msg.edit_text("⚠️ Video topilmadi.")
            return

    # 4. Ajratish
    audio_path = await effects.extract_audio_from_video(video_path)
    if not audio_path or not Path(audio_path).exists():
        await status_msg.edit_text("⚠️ Audio ajratib bo'lmadi.")
        return

    cached_video = database.get_media_cache(f"video:{url_id}", "video")
    title = cached_video["title"] if cached_video else "Video Audio"
    clean_name = get_clean_filename(title)

    sent = await callback.message.answer_audio(
        audio=FSInputFile(audio_path, filename=f"{clean_name}.mp3"),
        title=title,
        performer="Echo Musiqa",
        caption=f"🔊 <b>{title}</b>\n⚡ @echomusiqa_bot",
        reply_markup=get_audio_keyboard(url_id)
    )
    try:
        await status_msg.delete()
    except Exception:
        pass

    if sent.audio:
        database.set_media_cache(
            cache_key=f"audio:{url_id}",
            media_type="video_audio",
            file_id=sent.audio.file_id,
            title=title
        )


# --- TO'G'RIDAN-TO'G'RI YUBORILGAN VIDEO (0.5 SONIYADA DUMALOQ QILISH) ---

@dp.message(F.video | F.video_note | (F.document & F.document.mime_type.startswith("video/")))
async def on_direct_video_received(message: Message):
    """
    Foydalanuvchi botga to'g'ridan-to'g'ri video tashlasa:
    Telegram oqimidan to'g'ridan-to'g'ri 0.5s da dumaloq videoga aylantirib yuboradi!
    """
    if is_in_maintenance(message.from_user.id):
        await message.answer("🛠️ <b>Botda texnik ta'mirlash ishlari olib borilmoqda.</b>")
        return

    is_sub, unsub = await check_user_subscriptions(message.from_user.id)
    if not is_sub:
        await message.answer("⚠️ <b>Dumaloq video tayyorlash uchun avval homiy kanallarga a'zo bo'ling:</b>", reply_markup=get_subscription_keyboard(unsub))
        return

    if not database.is_feature_enabled("feature_round_video"):
        await message.answer("⚠️ <b>Dumaloq video tayyorlash xizmati admin tomonidan vaqtincha to'xtatilgan.</b>")
        return

    asyncio.create_task(asyncio.to_thread(
        database.register_user,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    ))

    video_obj = message.video or message.video_note or message.document
    file_id = video_obj.file_id
    file_unique_id = video_obj.file_unique_id

    # 1. Kesh tekshirish (0.05 soniya!)
    cached = database.get_media_cache(f"round_direct:{file_unique_id}", "video_note")
    if cached and cached.get("file_id"):
        await message.answer_video_note(video_note=cached["file_id"])
        await message.answer("⭕ <b>Dumaloq video tayyor!</b>", reply_markup=get_direct_video_keyboard(file_unique_id))
        return

    status_msg = await message.answer("⭕ <b>Dumaloq video tayyorlanmoqda... (0.5s)</b>")
    await bot.send_chat_action(message.chat.id, ChatAction.RECORD_VIDEO_NOTE)

    # 2. Telegramdan to'g'ridan-to'g'ri URL olish (oqimli ishlov)
    file_info = await bot.get_file(file_id)
    telegram_url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file_info.file_path}"
    round_path = str(config.DOWNLOADS_DIR / f"round_{file_unique_id}.mp4")

    # 3. 0.5 soniyada to'g'ridan-to'g'ri oqimdan dumaloq videoga o'tkazish
    out_round = await effects.convert_to_video_note(telegram_url, round_path)
    if not out_round or not Path(out_round).exists():
        raw_path = str(config.DOWNLOADS_DIR / f"raw_{file_unique_id}.mp4")
        await bot.download_file(file_info.file_path, destination=raw_path)
        out_round = await effects.convert_to_video_note(raw_path, round_path)

    if not out_round or not Path(out_round).exists():
        await status_msg.edit_text("⚠️ Dumaloq video yaratishda xatolik yuz berdi.")
        return

    # 4. Yuborish
    sent = await message.answer_video_note(video_note=FSInputFile(out_round))
    try:
        await status_msg.delete()
    except Exception:
        pass

    if sent.video_note:
        database.set_media_cache(
            cache_key=f"round_direct:{file_unique_id}",
            media_type="video_note",
            file_id=sent.video_note.file_id
        )

    await message.answer("⭕ <b>Dumaloq video tayyor!</b>", reply_markup=get_direct_video_keyboard(file_unique_id))
    active_media_files[file_unique_id] = out_round

    # 5. Fonda musiqani aniqlash va audioni tayyorlash
    asyncio.create_task(precompute_video_assets(file_unique_id, out_round))


@dp.callback_query(F.data.startswith("dvm:"))
async def cb_direct_video_music(callback: CallbackQuery):
    """Tashlangan videodan musiqani aniqlash."""
    if not database.is_feature_enabled("feature_shazam"):
        await callback.answer("⚠️ Musiqani aniqlash admin tomonidan vaqtincha to'xtatilgan.", show_alert=True)
        return

    short_id = callback.data.split(":", 1)[1]
    await callback.answer("🔍 Musiqa aniqlanmoqda...")

    # 1. Oldindan aniqlangan kesh (0.01s!)
    pre_rec = recognized_music_cache.get(short_id)
    if pre_rec and pre_rec.get("success"):
        await callback.message.answer(
            f"🎯 <b>Musiqa aniqlandi:</b>\n"
            f"🎵 <b>{pre_rec['title']}</b>\n"
            f"👤 <i>{pre_rec['artist']}</i>"
        )
        await handle_search_query(callback.message, pre_rec["query"])
        return

    status_msg = await callback.message.answer("🔍 <b>Musiqa aniqlanmoqda... (0.5s)</b>")

    video_path = active_media_files.get(short_id)
    if not video_path:
        candidates = list(config.DOWNLOADS_DIR.glob(f"*{short_id}*.mp4"))
        if candidates:
            video_path = str(candidates[0])

    if not video_path or not Path(video_path).exists():
        await status_msg.edit_text("⚠️ Video topilmadi.")
        return

    rec = await shazam_helper.recognize_song(video_path)
    try:
        await status_msg.delete()
    except Exception:
        pass

    if rec.get("success"):
        recognized_music_cache[short_id] = rec
        await callback.message.answer(
            f"🎯 <b>Musiqa aniqlandi:</b>\n"
            f"🎵 <b>{rec['title']}</b>\n"
            f"👤 <i>{rec['artist']}</i>"
        )
        await handle_search_query(callback.message, rec["query"])
    else:
        await callback.message.answer("⚠️ Musiqa aniqlanmadi.")


@dp.callback_query(F.data.startswith("dva:"))
async def cb_direct_video_audio(callback: CallbackQuery):
    """Tashlangan videodan audio ajratish (MP3 formatda)."""
    short_id = callback.data.split(":", 1)[1]
    await callback.answer("🔊 Audio ajratilmoqda...")

    status_msg = await callback.message.answer("🔊 <b>Audio ajratilmoqda... (0.5s)</b>")

    video_path = active_media_files.get(short_id)
    if not video_path:
        candidates = list(config.DOWNLOADS_DIR.glob(f"*{short_id}*.mp4"))
        if candidates:
            video_path = str(candidates[0])

    if not video_path or not Path(video_path).exists():
        await status_msg.edit_text("⚠️ Video topilmadi.")
        return

    audio_path = await effects.extract_audio_from_video(video_path)
    if not audio_path or not Path(audio_path).exists():
        await status_msg.edit_text("⚠️ Audio ajratib bo'lmadi.")
        return

    audio_file = FSInputFile(audio_path, filename="Videodan_audio.mp3")

    await callback.message.answer_audio(
        audio=audio_file,
        title="Ajratilgan Audio",
        performer="Echo Musiqa",
        caption="🔊 <b>Videodan ajratilgan audio</b>\n⚡ @echomusiqa_bot",
        reply_markup=get_audio_keyboard(short_id)
    )
    try:
        await status_msg.delete()
    except Exception:
        pass


# --- TOZALASH ---

async def cleanup_temp_files_loop():
    """Vaqtinchalik fayllarni tozalash."""
    while True:
        try:
            await asyncio.sleep(900)
            now = time.time()
            for item in config.DOWNLOADS_DIR.iterdir():
                if item.is_file():
                    age = now - item.stat().st_mtime
                    if age > config.TEMP_FILE_LIFETIME:
                        try:
                            item.unlink()
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"Tozalash xatosi: {e}")


# --- MAIN ---

async def main():
    logger.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(cleanup_temp_files_loop())
    
    # Render.com Web Service HTTP Health Serverini ko'tarish ($PORT)
    asyncio.create_task(start_render_health_server())

    # Doimiy http sessiyani oldindan qizdirib qo'yish (pre-warm)
    await searcher.get_http_session()
    
    bot_info = await bot.get_me()
    logger.info(f"Bot ulandi: @{bot_info.username}")
    print(f"\n==========================================")
    print(f"  BOT ISHGA TUSHDI: @{bot_info.username}")
    print(f"==========================================\n")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
