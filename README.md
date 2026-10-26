# ⚡ EchoMusiqa Bot (@echomusiqa_bot)

Professional, o'ta tezkor (**0.5 soniyalik javob tezligi**) Telegram Music & Media Bot.

Ushbu bot musiqa qidirish, qo'shiqlarga **3D** va **Konsert zali** effektlarini berish, **Instagram, TikTok, YouTube** videolarini yuklab olish, **Telegram Dumaloq Video (Video Note)** yaratish, to'liq **Admin Panel** va **Render.com** bulutli xostingiga 100% moslashtirilgan.

---

## 🌟 Asosiy Imkoniyatlar

1. **🎵 Top 10 Original Musiqa Qidiruvi:**
   - Qo'shiq nomi yoki ijrochisi yozilishi bilan eng mashhur va original TOP 10 taronalarni taqdim etadi.
   - 1 dan 10 gacha raqamli qulay tugmalar orqali istalgan musiqani bir zumda yuklab olish.
   - Har bir qo'shiq artisti, davomiyligi va albom rasmi bilan birga keladi.

2. **🎧 3D va 🏟️ Konsert Audio Effektlari:**
   - Har qanday musiqa tagida **[ 🎧 3D Ovoz ]** va **[ 🏟️ Konsert ]** tugmalari mavjud.
   - **3D Ovoz:** Quloqchinlarda tinglanganda ovozni 360° aylanuvchi fazoviy (8D) akustikaga o'tkazadi.
   - **Konsert Ovoz:** Taronaga ulkan stadion va jonli ijro reverberatsiyasi hamda aks-sadosini bag'ishlaydi.

3. **📥 Ijtimoiy Tarmoqlardan Video Yuklash:**
   - **Instagram** (Reels, Postlar, Stories)
   - **TikTok** (Suv belgisiz videolar)
   - **YouTube** (Shorts va to'liq videolar)
   - Video tagidagi 3 ta tezkor tugma:
     - `🎵 Musiqa (Top 10)` — Shazam orqali musiqani aniqlab, uning TOP 10 originalini chiqaradi.
     - `⭕ Dumaloq video` — Videoni 0.5 soniyada Telegram dumaloq videosiga aylantiradi.
     - `🔊 Audio (MP3)` — Videodan musiqani alohida audio qilib ajratadi.

4. **⭕ To'g'ridan-to'g'ri Videoni Dumaloq Qilish:**
   - Foydalanuvchi botga istalgan videoni tashlasa, bot uni soniyaning yarmida 1:1 kvadrat Telegram dumaloq videosiga (Video Note) aylantirib qaytaradi.

---

## 👑 Admin Panel Imkoniyatlari (`/admin`)

Botda to'liq boshqaruv imkoniyatiga ega interaktiv Admin Panel mavjud:

1. **📊 Jonli Statistika:**
   - Jami foydalanuvchilar, bugungi faollar, keshdagi audio/video soni va ulangan kanallar.
2. **⚙️ Funksiyalarni boshqarish (Qo'shimchalar ON / OFF):**
   - Istalgan funksiyani bitta tugma bilan yoqish yoki o'chirish:
     - *Musiqa qidiruvi* (ON/OFF)
     - *3D Ovoz effekti* (ON/OFF)
     - *Konsert zali effekti* (ON/OFF)
     - *Ijtimoiy video yuklash* (ON/OFF)
     - *Dumaloq video* (ON/OFF)
     - *Shazam musiqani aniqlash* (ON/OFF)
     - *Majburiy obuna* (ON/OFF)
     - *Texnik ta'mirlash rejimi (Maintenance)* (ON/OFF)
3. **📢 Majburiy Obuna (Homiy Kanallar):**
   - Yangi kanallar qo'shish va olib tashlash.
   - Obuna bo'lmagan foydalanuvchilar kanallarga a'zo bo'lmaguncha botdan foydalana olmaydi.
4. **🔗 Maxsus Menyu Tugmalari:**
   - `/start` xabarida chiqadigan qo'shimcha reklama/foydali havolalar tugmalarini qo'shish va o'chirish.
5. **✉️ Xabarnoma (Broadcast):**
   - Barcha foydalanuvchilarga xabar (matn, rasm, video, forward post) tarqatish va hisoboti.
6. **👥 Adminlar boshqaruvi:**
   - Yangi adminlar qo'shish (User ID orqali) va olib tashlash.
7. **🧹 Keshni tozalash:**
   - SQLite keshi va diskdagi yuklangan vaqtinchalik fayllarni bir bosishda tozalash.
8. **📝 Xush kelibsiz matni:**
   - `/start` xabarini o'zingiz xohlagan matnga o'zgartirish yoki standartga qaytarish.

---

## ☁️ Render.com da Bepul Ishga Tushirish Qo'llanmasi

Ushbu loyiha Render.com serverida 24/7 rejimida to'xtovsiz ishlashga 100% tayyorlangan.

### 1-usul: Docker orqali (Tavsiya etiladi - FFmpeg avtomatik o'rnatiladi):
1. [Render.com](https://render.com) ga kiring va **New +** -> **Web Service** ni tanlang.
2. GitHub repozitoriyangizni ulang: `https://github.com/zuxizayniddinov2-maker/musiqa-bot`.
3. Sozlamalarda:
   - **Runtime:** `Docker` (loyihadagi `Dockerfile` avtomatik ishga tushadi).
   - **Instance Type:** `Free`.
4. **Environment Variables** bo'limida quyidagilarni kiriting:
   - `BOT_TOKEN` = `sizning_bot_tokeningiz`
   - `ADMIN_IDS` = `sizning_telegram_id_raqamingiz` (masalan: `123456789`)
5. **Create Web Service** ni bosing. Bot ishga tushadi va Render uning HTTP portini muvaffaqiyatli tekshirib (Health Check) 24/7 tirik saqlaydi!

### 2-usul: Python Native Environment orqali:
- **Runtime:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python bot.py`
- Loyihada `static-ffmpeg` ulangan bo'lib, Render tizimida ffmpeg bo'lmasa ham avtomatik sozlanadi.

---

## 📁 Loyiha Strukturasi

```
music bot/
├── .env.example        # Namuna sozlamalar
├── .gitignore          # Maxfiy fayllar himoyasi
├── Dockerfile          # Render.com uchun Docker muhiti
├── render.yaml         # Render Blueprint avtomatik sozlamasi
├── config.py           # Sozlamalar va muhit o'zgaruvchilari
├── database.py         # SQLite tezkor kesh va sozlamalar bazasi
├── admin.py            # To'liq interaktiv Admin Panel moduli
├── searcher.py         # Top 10 original musiqa qidiruv moduli
├── downloader.py       # Tezkor audio va video yuklovchi
├── effects.py          # 3D ovoz, Konsert, Dumaloq video moduli
├── shazam_helper.py    # Shazam musiqani aniqlash moduli
├── bot.py              # Asosiy bot va Render HTTP Health serveri
├── push_to_github.bat  # 1 bosishda GitHub-ga yuklash skripti
├── run.bat             # Windows-da konsolda ishga tushirish
├── start.bat           # Windows-da fonda ishga tushirish
├── stop.bat            # Botni to'xtatish
├── restart.bat         # Qayta ishga tushirish
└── requirements.txt    # Kutubxonalar ro'yxati
```
