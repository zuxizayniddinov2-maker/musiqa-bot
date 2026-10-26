# ⚡ EchoMusiqa Bot (@echomusiqa_bot)

Professional, o'ta tezkor (**0.5 soniyalik javob tezligi**) Telegram Music & Media Bot.

Ushbu bot musiqa qidirish, qo'shiqlarga **3D** va **Konsert zali** effektlarini berish, **Instagram, TikTok, YouTube** videolarini yuklab olish hamda ularni darhol **Telegram Dumaloq Video (Video Note)** formatiga aylantirish uchun yaratilgan.

---

## 🌟 Asosiy Imkoniyatlar

1. **🎵 Top 10 Original Musiqa Qidiruvi:**
   - Foydalanuvchi musiqa nomi yoki ijrochini yozishi bilanoq eng mashhur va original TOP 10 qo'shiqlarni chiqarib beradi.
   - 1 dan 10 gacha raqamli qulay tugmalar orqali istalgan musiqani bir bosishda yuklab olish.
   - Har bir musiqaning muallifi, davomiyligi va yuqori sifatli rasmi (cover art) aks etadi.

2. **🎧 3D va 🏟️ Konsert Audio Effektlari:**
   - Har qanday yuborilgan yoki topilgan musiqa tagida **[ 🎧 3D Ovoz ]** va **[ 🏟️ Konsert ]** tugmalari mavjud.
   - **3D Ovoz:** Quloqchinlarda tinglanganda ovozni 360° aylanuvchi fazoviy (8D) akustikaga o'tkazadi.
   - **Konsert Ovoz:** Musiqani ulkan stadion yoki konsert zalidagi jonli ijro reverberatsiyasi va aks-sadosiga ega qiladi.

3. **📥 Ijtimoiy Tarmoqlardan Video Yuklash:**
   - **Instagram** (Reels, Postlar, Stories)
   - **TikTok** (Suv belgisiz videolar)
   - **YouTube** (Shorts va to'liq videolar)
   - Video tagida 3 ta qulay tezkor tugma chiqariladi:
     - `🎵 Musiqa (Top 10)` — Videodagi musiqani Shazam orqali aniqlab, uning TOP 10 original versiyalarini chiqaradi.
     - `⭕ Dumaloq video` — Videoni 0.5 soniyada Telegram dumaloq videosiga (Video Note) aylantirib beradi.
     - `🔊 Audio (MP3)` — Videodan musiqani alohida MP3 qilib ajratib beradi.

4. **⭕ To'g'ridan-to'g'ri Videoni 0.5 Soniyada Dumaloq Qilish:**
   - Foydalanuvchi botga istalgan videoni tashlasa, bot uni soniyaning yarmida 1:1 kvadrat Telegram dumaloq videosiga (Video Note) aylantirib qaytaradi.
   - O'sha videodan musiqani aniqlash va audiosini ajratish imkoniyati ham biriktirilgan.

5. **⚡ 0.5 Soniyalik O'ta Tezkor Arxitektura:**
   - **SQLite Kesh:** Bir bor qidirilgan yoki yuklangan har qanday fayl (audio, video, dumaloq video, 3D ovoz) Telegram `file_id` orqali keyingi safar **0.1 soniyada** yuboriladi!
   - **FFmpeg Ultrafast:** Barcha audio va video konvertatsiyalar `-preset ultrafast -tune zerolatency` rejimi va barcha CPU yadrolari yordamida ishlaydi.
   - **To'liq Asinxron:** Aiogram 3 va asinxron fon vazifalari hisobiga bot bir vaqtning o'zida yuzlab foydalanuvchilarga xizmat ko'rsata oladi.

---

## 🚀 Botni Boshqarish (Fayl orqali O'chirish va Yoqish)

Loyiha papkasida qulay boshqaruv uchun tayyor buyruq fayllari (batch) joylashtirilgan:

- **`start.bat`** — Botni fonda (alohida oynada) ishga tushirish.
- **`run.bat`** — Botni konsol oynasida to'liq loglar bilan ishga tushirish (tekshirish uchun).
- **`stop.bat`** — Ishlayotgan botni bir bosishda to'xtatish.
- **`restart.bat`** — Botni o'chirib, darhol qayta ishga tushirish.

---

## 📁 Loyiha Strukturasi

```
music bot/
├── .env                # Bot tokeni va sozlamalar
├── config.py           # Papkalar va parametrlar
├── database.py         # SQLite tezkor kesh bazasi
├── searcher.py         # Top 10 musiqa qidiruv moduli
├── downloader.py       # YouTube, Instagram, TikTok yuklovchi
├── effects.py          # 3D ovoz, Konsert zali, Dumaloq video konverteri
├── shazam_helper.py    # Videodagi musiqani Shazam orqali aniqlovchi
├── bot.py              # Asosiy Telegram bot kodi (Aiogram 3)
├── run.bat             # Konsolda ishga tushirish
├── start.bat           # Fonda ishga tushirish
├── stop.bat            # Botni to'xtatish
├── restart.bat         # Qayta ishga tushirish
├── requirements.txt    # Kutubxonalar ro'yxati
└── README.md           # Ushbu qo'llanma
```

---

## ⚙️ Sozlamalar

Bot tokeni `.env` faylida saqlanadi:
```env
BOT_TOKEN=8933069954:AAHNQLa7o3l6JOtJgC_iW3cYdB2Fl5ylesk
MAX_FILE_SIZE_MB=50
TEMP_FILE_LIFETIME_MINUTES=30
```
