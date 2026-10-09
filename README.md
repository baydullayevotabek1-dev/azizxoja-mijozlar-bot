# Mijozlar boti

Mijozlar shaxsiy Telegramga yozsa, bot kartochka yuboradi: **⏳ Jarayonda / ✅ Bajarildi**.
Bajarilmaganlarini har 30 daqiqada eslatib turadi. Telegram Premium kerak emas.

## Foydalanuvchi uchun — 1 daqiqa
1. Botga kiring va **/start** bosing.
2. **«📱 Akkauntni ulash»** tugmasini bosing — raqamingiz yuboriladi.
3. Telegram'ning rasmiy «Telegram» chatiga kelgan kodni **botdagi tugmalar bilan** kiriting
   (kodni xabar qilib yozmang — Telegram uni bekor qiladi).
4. Ikki bosqichli parol bo'lsa — botga yozing, bot uni darhol o'chiradi.

Tayyor. Terminal, papka yaratish — hech narsa kerak emas.

## Qanday ishlaydi
- **Mijoz yozsa** — kartochka keladi. Ketma-ket bir necha xabar **bitta kartochka**ga yig'iladi.
- **Yangi odam yozsa** — bot so'raydi: **«Bu mijozmi?»**
  - **✅ Mijoz** → murojaat ochiladi va odam Telegramdagi **«Mijozlar»** papkasiga o'zi qo'shiladi
    (papka bo'lmasa — bot yaratadi).
  - **❌ Mijoz emas** → uning xabarlari boshqa kelmaydi (xato bosilsa — «↩️ Baribir mijoz»).
  - Har odam uchun bir marta so'raladi.
- «Mijozlar» papkasiga o'zingiz qo'shgan odamlar ham mijoz hisoblanadi.
- Mijozga o'zingiz javob yozsangiz — murojaat avtomatik **⏳ Jarayonda**.
- **✅ Bajarildi**dan keyin yana yozsa — yangi murojaat ("rahmat", "ok" bundan mustasno).
- Pastdagi tugmalar:
  - **🔴 Bajarilmaganlar** — ochiq murojaatlar
  - **📋 Ro'yxat** — bugungi hammasi (✅ / ⏳ / 🆕)
  - **⚙️ Sozlamalar** — eslatma oralig'i, tungi tinchlik, **🔌 akkauntni uzish**

> Oddiy akkauntda Telegram papkasiga ko'pi bilan 100 ta chat sig'adi. Undan keyin ham bot ishlayveradi —
> mijozlar ro'yxati botning o'z bazasida saqlanadi, faqat papkaga qo'shilmaydi.

## Dasturchi uchun: botni ishga tushirish (bir marta)
1. **@BotFather** → `/newbot` → token.
2. **https://my.telegram.org** → API development tools → `api_id`, `api_hash`.
3. `.env.example` → `.env` nusxa olib, `BOT_TOKEN`, `API_ID`, `API_HASH` (va xohlasa `GEMINI_API_KEY`) ni yozing.
4. `ALLOWED_OWNERS` ga botdan foydalanadiganlarning Telegram ID'larini yozing (vergul bilan) —
   aks holda botni topgan har kim o'z akkauntini ulay oladi. ID'ni @userinfobot dan bilish mumkin.
5. ```
   pip install -r requirements.txt
   python main.py
   ```
Bot doimiy ishlashi kerak — VPS serverga qo'yiladi (~$5/oy). `sessions/` papkasi ham serverga ko'chiriladi.

`login.py` — terminal orqali ulashning muqobil yo'li (odatda kerak emas).

## Eslatmalar
- 🆕 Yangi — har 30 daqiqada, ⏳ Jarayonda — har 2 soatda (Sozlamalar'da o'zgartiriladi).
- Eslatma doim **bitta jamlangan xabar** bo'lib keladi, eskisi o'chadi.
- 22:00–08:00 da eslatma kelmaydi (o'chirsa bo'ladi).

## Bitta bot — bir nechta odam
Har kim botga /start bosib o'z akkauntini ulaydi va faqat o'z mijozlarini ko'radi.

## 🧠 Gemini AI (ixtiyoriy)
`.env` ga `GEMINI_API_KEY` yozilsa (kalit: **aistudio.google.com → Get API key**):
- **Ovozli xabar** (5 daqiqagacha) matnga aylanadi va kartochkada ko'rinadi.
- Kartochka tepasida **🧠 bir qatorli xulosa**: mijoz nima istayapti.
- Mijoz shoshilsa ("bugun kerak", "srochno"...) — **🔥** belgisi, ro'yxat tepasida turadi, ikki barobar tez-tez eslatiladi.

Kartochka AI'ni kutmaydi — darhol keladi, xulosa 1–3 soniyada qo'shiladi.
Kalit bo'lmasa yoki Gemini ishlamasa — bot oddiy rejimda ishlayveradi.

"Rahmat", "ok", "👍" kabi xabarlar ochiq murojaat bo'lmasa yangi murojaat ochmaydi (bu AI'siz ishlaydi).

> Maxfiylik: mijoz xabarlari Google'ga yuboriladi. Bepul tarifda Google ma'lumotdan o'z xizmatlarini
> yaxshilashda foydalanishi mumkin; mijoz yozishmalari uchun AI Studio'da billing yoqilgan (pullik) kalit tavsiya etiladi.

## ⚠️ Xavfsizlik
- `sessions/` papkasidagi `.session` fayl — **akkauntga to'liq kirish kaliti**. Hech kimga bermang, chatga tashlamang.
- Bitta sessiyani bir vaqtda ikki joyda (kompyuter va server) ishlatmang — Telegram uni o'chirib yuborishi mumkin.
  Serverga ko'chirganda kompyuterdagini to'xtating.
- Akkauntdan chiqarish: Telegram → Sozlamalar → Qurilmalar → shu sessiyani tugatish.

## Premium bo'lsa (ixtiyoriy)
Telegram Business orqali ulash ham ishlaydi: @BotFather → Bot Settings → Business Mode → Turn on,
keyin Telegram → Sozlamalar → Telegram Business → Chatbotlar. Bu rejimda `ALLOWED_OWNERS` ni to'ldiring.
