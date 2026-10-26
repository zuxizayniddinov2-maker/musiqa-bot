import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import database

logger = logging.getLogger("AdminPanel")
admin_router = Router()

# --- FSM HOLATLARI ---

class AdminStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    waiting_for_new_admin = State()
    waiting_for_broadcast = State()
    waiting_for_welcome_text = State()

# --- TUGMALARNI YASASH ---

def get_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:cancel")]
    ])

def get_admin_main_kb() -> InlineKeyboardMarkup:
    """Admin boshqaruv panelining bosh menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats"),
            InlineKeyboardButton(text="⚙️ Funksiyalar (ON/OFF)", callback_data="admin:features")
        ],
        [
            InlineKeyboardButton(text="📢 Majburiy Obuna", callback_data="admin:channels"),
            InlineKeyboardButton(text="🔗 Menyu Tugmalari", callback_data="admin:buttons")
        ],
        [
            InlineKeyboardButton(text="✉️ Xabarnoma (Broadcast)", callback_data="admin:broadcast"),
            InlineKeyboardButton(text="👥 Adminlar", callback_data="admin:admins")
        ],
        [
            InlineKeyboardButton(text="📝 Start Matni", callback_data="admin:welcome"),
            InlineKeyboardButton(text="🧹 Keshni Tozalash", callback_data="admin:clear_cache")
        ],
        [
            InlineKeyboardButton(text="❌ Panelni Yopish", callback_data="close_msg")
        ]
    ])

def get_features_kb() -> InlineKeyboardMarkup:
    """Qo'shimcha funksiyalarni yoqish/o'chirish tugmalari."""
    settings = database.get_all_settings()

    def get_status_btn(name: str, key: str, is_danger: bool = False):
        val = settings.get(key, "1" if not is_danger else "0")
        if is_danger:
            icon = "🔴 YOQIQ" if val == "1" else "⚪ O'chiq"
        else:
            icon = "✅ YOQIQ" if val == "1" else "❌ O'chiq"
        return [InlineKeyboardButton(text=f"{name}: {icon}", callback_data=f"admin:toggle:{key}")]

    rows = [
        get_status_btn("🎵 Musiqa Qidiruvi", "feature_search"),
        get_status_btn("🎧 3D Ovoz Effekti", "feature_3d"),
        get_status_btn("🏟️ Konsert Zali", "feature_concert"),
        get_status_btn("📥 Ijtimoiy Video", "feature_social_video"),
        get_status_btn("⭕ Dumaloq Video", "feature_round_video"),
        get_status_btn("🔍 Shazam Qidiruv", "feature_shazam"),
        get_status_btn("📢 Majburiy Obuna", "feature_mandatory_sub"),
        get_status_btn("🛠️ Texnik Ta'mirlash", "maintenance_mode", is_danger=True),
        [InlineKeyboardButton(text="⬅️ Bosh Menyu", callback_data="admin:main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_channels_kb() -> InlineKeyboardMarkup:
    """Majburiy kanallar ro'yxati va boshqaruvi."""
    channels = database.get_channels()
    rows = []
    for ch in channels:
        rows.append([
            InlineKeyboardButton(text=f"📢 {ch['title']}", url=ch['invite_link']),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin:del_channel:{ch['id']}")
        ])
    rows.append([InlineKeyboardButton(text="➕ Yangi Kanal Qo'shish", callback_data="admin:add_channel")])
    rows.append([InlineKeyboardButton(text="⬅️ Bosh Menyu", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_buttons_kb() -> InlineKeyboardMarkup:
    """Maxsus menyu tugmalari ro'yxati."""
    buttons = database.get_extra_buttons()
    rows = []
    for b in buttons:
        rows.append([
            InlineKeyboardButton(text=f"🔗 {b['button_text']}", url=b['button_url']),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin:del_button:{b['id']}")
        ])
    rows.append([InlineKeyboardButton(text="➕ Yangi Tugma Qo'shish", callback_data="admin:add_button")])
    rows.append([InlineKeyboardButton(text="⬅️ Bosh Menyu", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_admins_kb() -> InlineKeyboardMarkup:
    """Adminlar ro'yxati."""
    admins = database.get_admins()
    rows = []
    for aid in admins:
        is_root = aid in config.ADMIN_IDS
        label = f"👑 {aid} (Asosiy)" if is_root else f"👤 {aid}"
        btn_del = [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin:del_admin:{aid}")] if not is_root else []
        rows.append([InlineKeyboardButton(text=label, callback_data="admin:none")] + btn_del)

    rows.append([InlineKeyboardButton(text="➕ Yangi Admin Qo'shish", callback_data="admin:add_admin")])
    rows.append([InlineKeyboardButton(text="⬅️ Bosh Menyu", callback_data="admin:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# --- ADMIN BUYRUG'I (/admin) ---

@admin_router.message(Command("admin", "panel"))
@admin_router.message(F.text.func(lambda t: bool(t and t.strip().lower() in ["/admin", "admin", "panel", "/panel", "admin panel"])))
async def cmd_admin_panel(message: Message, state: FSMContext):
    """Admin panel bosh menyusi."""
    await state.clear()
    user_id = message.from_user.id
    admins = database.get_admins()

    # Agar botda hali bitta ham admin yo'q bo'lsa, birinchi yozgan shaxs Bosh Admin bo'ladi!
    if not admins:
        database.add_admin(user_id)
        config.ADMIN_IDS.add(user_id)
        await message.answer(f"👑 <b>Siz muvaffaqiyatli Bosh Admin (Root) etib belgilandingiz!</b> (ID: <code>{user_id}</code>)")

    if not database.is_admin(user_id):
        await message.answer(
            f"⛔ <b>Siz admin emassiz!</b>\n\n"
            f"Sizning Telegram ID: <code>{user_id}</code>\n"
            f"<i>Admin panel faqat ruxsat berilgan adminlar uchun ochiq.</i>"
        )
        return

    text = (
        "👑 <b>EchoMusiqa Bot — Boshqaruv Paneli</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:\n"
        "• <b>Statistika:</b> Foydalanuvchilar va kesh hisoboti\n"
        "• <b>Funksiyalar:</b> Bot qo'shimchalarini yoqish/o'chirish\n"
        "• <b>Majburiy Obuna:</b> Sponsor kanallarini boshqarish\n"
        "• <b>Menyu Tugmalari:</b> Qo'shimcha havolalar/tugmalar qo'shish\n"
        "• <b>Xabarnoma:</b> Foydalanuvchilarga reklama yoki xabar tarqatish\n"
        "• <b>Adminlar:</b> Yangi admin tayinlash yoki olib tashlash"
    )
    await message.answer(text, reply_markup=get_admin_main_kb())

# --- ASOSIY MENYU VA STATISTIKA ---

@admin_router.callback_query(F.data == "admin:main")
async def cb_admin_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    text = (
        "👑 <b>EchoMusiqa Bot — Boshqaruv Paneli</b>\n\n"
        "Kerakli bo'limni tanlang:"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_main_kb())

@admin_router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    stats = database.get_stats()
    text = (
        "📊 <b>EchoMusiqa Bot — Jonli Statistika</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {stats['total_users']} ta\n"
        f"⚡ <b>Bugun faol bo'lganlar:</b> {stats['active_today']} ta\n\n"
        f"🎵 <b>Keshdagi musiqalar (File ID):</b> {stats['cached_audios']} ta\n"
        f"🎬 <b>Keshdagi videolar:</b> {stats['cached_videos']} ta\n"
        f"⭕ <b>Keshdagi dumaloq videolar:</b> {stats['cached_rounds']} ta\n"
        f"🔍 <b>Saqlangan qidiruvlar:</b> {stats['cached_searches']} ta\n\n"
        f"📢 <b>Ulangan majburiy kanallar:</b> {stats['channels_count']} ta\n"
        f"👑 <b>Adminlar soni:</b> {len(database.get_admins())} ta"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin:stats")],
        [InlineKeyboardButton(text="⬅️ Bosh Menyu", callback_data="admin:main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

# --- QO'SHIMCHALAR / FUNKSIYALAR TOGGLE (ON / OFF) ---

@admin_router.callback_query(F.data == "admin:features")
async def cb_admin_features(callback: CallbackQuery):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    text = (
        "⚙️ <b>Qo'shimchalar va Funksiyalar Sozlamalari</b>\n\n"
        "Kerakli funksiyani bosib, uni <b>yoqishingiz</b> yoki <b>o'chirishingiz</b> mumkin:\n\n"
        "• <i>O'chirilgan funksiyalar foydalanuvchilarga ishlamaydi.</i>\n"
        "• <i>Texnik ta'mirlash yoqilsa, bot faqat adminlar uchun ishlaydi.</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_features_kb())

@admin_router.callback_query(F.data.startswith("admin:toggle:"))
async def cb_admin_toggle(callback: CallbackQuery):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    key = callback.data.split(":", 2)[2]
    current = database.get_setting(key, "1")
    new_val = "0" if current == "1" else "1"
    database.set_setting(key, new_val)
    status_str = "yoqildi ✅" if new_val == "1" else "o'chirildi ❌"
    await callback.answer(f"Sozlama yangilandi: {status_str}")
    try:
        await callback.message.edit_reply_markup(reply_markup=get_features_kb())
    except Exception:
        pass

# --- KANALLAR (MAJBURIY OBUNA) ---

@admin_router.callback_query(F.data == "admin:channels")
async def cb_admin_channels(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    channels = database.get_channels()
    status_sub = "✅ Yoqilgan" if database.is_feature_enabled("feature_mandatory_sub") else "❌ O'chirilgan (Sozlamalardan yoqishingiz mumkin)"
    text = (
        "📢 <b>Majburiy Obuna Kanallari Boshqaruvi</b>\n\n"
        f"Holat: <b>{status_sub}</b>\n\n"
        f"Mavjud kanallar soni: <b>{len(channels)} ta</b>\n"
        "Yangi kanal qo'shish uchun quyidagi tugmani bosing:"
    )
    await callback.message.edit_text(text, reply_markup=get_channels_kb())

@admin_router.callback_query(F.data == "admin:add_channel")
async def cb_admin_add_channel(callback: CallbackQuery, state: FSMContext):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_channel)
    text = (
        "➕ <b>Yangi kanal qo'shish:</b>\n\n"
        "Quyidagi formatda xabar yuboring:\n"
        "<code>Kanal_ID_yoki_Username | Kanal Nomi | Taklif Havolasi</code>\n\n"
        "📌 <b>Misol:</b>\n"
        "<code>@mychannel | Musiqa Kanali | https://t.me/mychannel</code>\n"
        "yoki\n"
        "<code>-1001234567890 | Premyeralar | https://t.me/+AbCdEfGh</code>\n\n"
        "<i>Eslatma: Bot ushbu kanalda administrator bo'lishi shart!</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_cancel_kb())

@admin_router.message(AdminStates.waiting_for_channel)
async def process_add_channel(message: Message, state: FSMContext):
    if not database.is_admin(message.from_user.id):
        return
    raw = message.text.strip()
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) != 3:
        await message.answer(
            "⚠️ Noto'g'ri format! 3 ta qismni <code>|</code> belgisi bilan ajratib yuboring:\n"
            "<code>@username | Nomi | Havola</code>",
            reply_markup=get_cancel_kb()
        )
        return

    channel_id, title, invite_link = parts
    ok = database.add_channel(channel_id, title, invite_link)
    await state.clear()
    if ok:
        await message.answer(f"✅ <b>«{title}» kanali muvaffaqiyatli qo'shildi!</b>", reply_markup=get_channels_kb())
    else:
        await message.answer("⚠️ Ushbu kanal allaqachon mavjud yoki xatolik yuz berdi.", reply_markup=get_channels_kb())

@admin_router.callback_query(F.data.startswith("admin:del_channel:"))
async def cb_admin_del_channel(callback: CallbackQuery):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    chid = callback.data.split(":", 2)[2]
    database.delete_channel(chid)
    await callback.answer("Kanal o'chirildi! 🗑")
    try:
        await callback.message.edit_reply_markup(reply_markup=get_channels_kb())
    except Exception:
        pass

# --- MENYU TUGMALARI (REKLAMA / FOYDALI HAVOLALAR) ---

@admin_router.callback_query(F.data == "admin:buttons")
async def cb_admin_buttons(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    buttons = database.get_extra_buttons()
    text = (
        "🔗 <b>Qo'shimcha Menyu Tugmalari Boshqaruvi</b>\n\n"
        f"Mavjud tugmalar soni: <b>{len(buttons)} ta</b>\n"
        "Ushbu tugmalar botning /start xabarida inline tugma sifatida aks etadi."
    )
    await callback.message.edit_text(text, reply_markup=get_buttons_kb())

@admin_router.callback_query(F.data == "admin:add_button")
async def cb_admin_add_button(callback: CallbackQuery, state: FSMContext):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_button_text)
    text = (
        "➕ <b>Yangi tugma matnini yuboring:</b>\n"
        "(Masalan: <code>📱 Bizning Instagram</code> yoki <code>💬 Guruhimiz</code>)"
    )
    await callback.message.edit_text(text, reply_markup=get_cancel_kb())

@admin_router.message(AdminStates.waiting_for_button_text)
async def process_btn_text(message: Message, state: FSMContext):
    if not database.is_admin(message.from_user.id):
        return
    btn_text = message.text.strip()
    await state.update_data(btn_text=btn_text)
    await state.set_state(AdminStates.waiting_for_button_url)
    await message.answer(
        f"🔗 <b>«{btn_text}» tugmasi bosilganda ochiladigan URL havolani yuboring:</b>\n"
        "(Masalan: <code>https://instagram.com/profil</code> yoki <code>https://t.me/guruh</code>)",
        reply_markup=get_cancel_kb()
    )

@admin_router.message(AdminStates.waiting_for_button_url)
async def process_btn_url(message: Message, state: FSMContext):
    if not database.is_admin(message.from_user.id):
        return
    url = message.text.strip()
    if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("tg://"):
        await message.answer("⚠️ Havola http:// yoki https:// bilan boshlanishi kerak!", reply_markup=get_cancel_kb())
        return

    data = await state.get_data()
    btn_text = data.get("btn_text", "Havola")
    ok = database.add_extra_button(btn_text, url)
    await state.clear()
    if ok:
        await message.answer(f"✅ <b>«{btn_text}» tugmasi qo'shildi!</b>", reply_markup=get_buttons_kb())
    else:
        await message.answer("⚠️ Tugmani saqlashda xatolik yuz berdi.", reply_markup=get_buttons_kb())

@admin_router.callback_query(F.data.startswith("admin:del_button:"))
async def cb_admin_del_button(callback: CallbackQuery):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    bid = int(callback.data.split(":", 2)[2])
    database.delete_extra_button(bid)
    await callback.answer("Tugma o'chirildi! 🗑")
    try:
        await callback.message.edit_reply_markup(reply_markup=get_buttons_kb())
    except Exception:
        pass

# --- XABARNOMA YUBORISH (BROADCAST) ---

@admin_router.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_broadcast)
    users_cnt = len(database.get_all_user_ids())
    text = (
        "✉️ <b>Barcha foydalanuvchilarga xabarnoma yuborish</b>\n\n"
        f"Qabul qiluvchilar soni: <b>{users_cnt} ta</b>\n\n"
        "Xabaringizni (matn, rasm, video yoki istalgan kanal postini forward qilib) yuboring:\n"
        "<i>Xabar darhol barcha foydalanuvchilarga jo'natiladi.</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_cancel_kb())

@admin_router.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not database.is_admin(message.from_user.id):
        return
    await state.clear()
    users = database.get_all_user_ids()
    if not users:
        await message.answer("⚠️ Bazada foydalanuvchilar mavjud emas.")
        return

    status_msg = await message.answer(f"🚀 Xabarnoma yuborilmoqda... (0 / {len(users)})")
    sent = 0
    failed = 0

    for i, uid in enumerate(users, 1):
        try:
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            sent += 1
        except Exception:
            failed += 1

        # Har 50 ta yuborilganda statusni yangilash va Telegram cheklovini saqlash
        if i % 50 == 0:
            try:
                await status_msg.edit_text(f"🚀 Xabarnoma yuborilmoqda... ({i} / {len(users)})")
            except Exception:
                pass
            await asyncio.sleep(0.5)
        else:
            await asyncio.sleep(0.04)

    await status_msg.edit_text(
        f"✅ <b>Xabarnoma muvaffaqiyatli yakunlandi!</b>\n\n"
        f"• Muvaffaqiyatli yetkazildi: <b>{sent} ta</b>\n"
        f"• Yetkazib bo'lmadi (bloklangan): <b>{failed} ta</b>",
        reply_markup=get_admin_main_kb()
    )

# --- ADMINLAR BOSHQARUVI ---

@admin_router.callback_query(F.data == "admin:admins")
async def cb_admin_admins(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    admins = database.get_admins()
    text = (
        "👥 <b>Administratorlar Ro'yxati</b>\n\n"
        f"Jami adminlar soni: <b>{len(admins)} ta</b>\n"
        "Yangi admin tayinlash uchun quyidagi tugmani bosing:"
    )
    await callback.message.edit_text(text, reply_markup=get_admins_kb())

@admin_router.callback_query(F.data == "admin:add_admin")
async def cb_admin_add_admin(callback: CallbackQuery, state: FSMContext):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_new_admin)
    await callback.message.edit_text(
        "➕ <b>Yangi adminning Telegram User ID raqamini yuboring:</b>\n"
        "(Foydalanuvchi o'z ID sini @userinfobot orqali bilib olishi mumkin)",
        reply_markup=get_cancel_kb()
    )

@admin_router.message(AdminStates.waiting_for_new_admin)
async def process_add_admin(message: Message, state: FSMContext):
    if not database.is_admin(message.from_user.id):
        return
    txt = message.text.strip()
    if not txt.isdigit():
        await message.answer("⚠️ Faqat raqamdan iborat User ID yuboring!", reply_markup=get_cancel_kb())
        return
    new_id = int(txt)
    database.add_admin(new_id)
    await state.clear()
    await message.answer(f"👑 <b>Foydalanuvchi ({new_id}) admin etib tayinlandi!</b>", reply_markup=get_admins_kb())

@admin_router.callback_query(F.data.startswith("admin:del_admin:"))
async def cb_admin_del_admin(callback: CallbackQuery):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    target_id = int(callback.data.split(":", 2)[2])
    if target_id in config.ADMIN_IDS:
        await callback.answer("⚠️ Bosh adminni o'chirib bo'lmaydi!", show_alert=True)
        return
    database.remove_admin(target_id)
    await callback.answer("Admin olib tashlandi! 🗑")
    try:
        await callback.message.edit_reply_markup(reply_markup=get_admins_kb())
    except Exception:
        pass

# --- START MATNI VA KESHNI TOZALASH ---

@admin_router.callback_query(F.data == "admin:welcome")
async def cb_admin_welcome(callback: CallbackQuery, state: FSMContext):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_welcome_text)
    current = database.get_setting("custom_welcome_text", "")
    cur_text = f"\n\n<b>Hozirgi maxsus matn:</b>\n{current}" if current else "\n\n<i>Hozir standart matn ishlatilmoqda.</i>"
    text = (
        f"📝 <b>/start xush kelibsiz matnini sozlash</b>{cur_text}\n\n"
        "Yangi matn yuboring yoki standart matnga qaytarish uchun <code>standart</code> deb yozing:"
    )
    await callback.message.edit_text(text, reply_markup=get_cancel_kb())

@admin_router.message(AdminStates.waiting_for_welcome_text)
async def process_welcome_text(message: Message, state: FSMContext):
    if not database.is_admin(message.from_user.id):
        return
    txt = message.text.strip()
    if txt.lower() in ("standart", "default", "0", "-"):
        database.set_setting("custom_welcome_text", "")
        await state.clear()
        await message.answer("✅ Xush kelibsiz matni standart holatga qaytarildi!", reply_markup=get_admin_main_kb())
    else:
        database.set_setting("custom_welcome_text", txt)
        await state.clear()
        await message.answer("✅ <b>Yangi /start matni muvaffaqiyatli saqlandi!</b>", reply_markup=get_admin_main_kb())

@admin_router.callback_query(F.data == "admin:clear_cache")
async def cb_admin_clear_cache(callback: CallbackQuery):
    if not database.is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    res = database.clear_all_cache()
    # downloads papkasini tozalash
    deleted_files = 0
    for p in config.DOWNLOADS_DIR.iterdir():
        if p.is_file():
            try:
                p.unlink()
                deleted_files += 1
            except Exception:
                pass
    await callback.answer("Kesh tozalandi! 🧹", show_alert=True)
    await callback.message.edit_text(
        f"🧹 <b>Kesh to'liq tozalandi!</b>\n\n"
        f"• Qidiruv keshi: {res['search']} ta o'chirildi\n"
        f"• Media keshi: {res['media']} ta o'chirildi\n"
        f"• Diskdagi fayllar: {deleted_files} ta o'chirildi",
        reply_markup=get_admin_main_kb()
    )

@admin_router.callback_query(F.data == "admin:cancel")
async def cb_admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Amal bekor qilindi.")
    await cb_admin_main(callback, state)
