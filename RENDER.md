# Botni Render'ga ulash (bepul) — qadamma-qadam

**Rollar:**
- **GitHub egasi** — kod shu ochiq repozitoriyda turadi, maxfiy qiymatlar unda.
- **Render egasi** — botni o'z Render akkauntida ishga tushiradi.
- **Bot egasi** — bot akkauntiga ulangan foydalanuvchi.

> ⚠️ Bot bir vaqtda faqat **bitta joyda** ishlashi kerak. Boshqa joyda (masalan, kompyuterda) ishlab turgan
> bo'lsa — avval to'xtating, aks holda Telegram bot egasining ulanishini o'chirib yuboradi.

> 🔒 Repozitoriyda parol, token, kalit yoki shaxsiy ma'lumot **yo'q** — hammasi Render sozlamalarida turadi.

---

## 1-qadam. Repozitoriyni ulash (Render egasi)

render.com → **New + → Web Service** → **Public Git Repository** →
repozitoriy manzilini qo'ying → **Connect**.

## 2-qadam. Web Service sozlamalari (Render egasi)

| Maydon | Qiymat |
|---|---|
| Name | `azizxoja-mijozlar-bot` |
| Region | **Frankfurt (EU Central)** — baza ham shu yerda |
| Branch | `main` |
| Runtime / Language | **Python 3** |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python main.py` |
| Instance Type | **Free** |

**Advanced → Health Check Path:** `/`

## 3-qadam. Environment Variables (Render egasi)

**Environment Variables → Add Environment Variable** — 8 ta:

| Key | Value |
|---|---|
| `PYTHON_VERSION` | `3.13.2` |
| `STARTUP_DELAY` | `45` |
| `ALLOWED_OWNERS` | GitHub egasidan (bot egasining Telegram ID'si) |
| `BOT_TOKEN` | GitHub egasidan |
| `API_ID` | GitHub egasidan |
| `API_HASH` | GitHub egasidan |
| `DATABASE_URL` | GitHub egasidan (Supabase) |
| `GEMINI_API_KEY` | GitHub egasidan |

> Bu qiymatlar maxfiy — **faqat shaxsiy xabarda** uzatiladi, guruhga yoki ochiq joyga emas.

**Create Web Service** → build 2–4 daqiqa.

## 4-qadam. Tekshirish (Render egasi)

1. **Logs** bo'limida shu qatorlar chiqishi kerak:
   - `Baza: Postgres`
   - `Eski nusxa to'xtashini kutyapmiz: 45 soniya`
   - `... ulandi, papkada ... ta chat`
   - `Run polling for bot @...`
2. Tepadagi manzilni oching (`https://...onrender.com`) — `ok, ulangan akkauntlar: 1` chiqishi kerak.
3. Kimdir bot egasiga shaxsiy xabar yozsin — botda "Mijozmi?" yoki kartochka kelishi kerak.

## 5-qadam. UptimeRobot — bot uxlab qolmasligi uchun

Render bepul serveri 15 daqiqa so'rov bo'lmasa uxlaydi. UptimeRobot uni har 5 daqiqada uyg'otib turadi.

1. https://uptimerobot.com → **Register** (bepul).
2. **+ New monitor**:
   - Monitor type: **HTTP(s)**
   - URL: Render manzili (4-qadamdagi)
   - Monitoring interval: **5 minutes**
   - Alert: emailingiz — bot to'xtasa xabar keladi
3. **Create monitor**. Bir necha daqiqadan keyin holat **Up** (yashil) bo'lishi kerak.

---

## Kod yangilanganda

Render egasi **Manual Deploy → Deploy latest commit** bosadi.
Qulayroq: Render egasi **Settings → Deploy Hook** manzilini GitHub egasiga beradi —
uni ochish bilan bot yangilanadi (Render'ga kirmasdan). Deploy Hook ham maxfiy.

## Muammo bo'lsa

| Belgi | Sabab va yechim |
|---|---|
| Logda `DATABASE_URL` / `connection` xatosi | `DATABASE_URL` noto'g'ri nusxalangan — to'liq satrni qayta qo'ying |
| `sessiya yaroqsiz` | Ulanish o'chgan — bot egasi botga **/start** bosib QR orqali qayta ulanadi |
| Bot javob bermaydi, UptimeRobot **Down** | Render → Logs'ni ko'ring; oyiga 750 soatlik bepul limit tugagan bo'lishi mumkin |
| `Conflict: terminated by other getUpdates` | Bot boshqa joyda ham ishlayapti — o'sha nusxani to'xtating |
