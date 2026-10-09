# Render'ga qo'yish (bepul)

Render bepul tarifida fayllar saqlanmaydi va 15 daqiqa so'rov bo'lmasa server uxlaydi. Shuning uchun:
baza va ulangan akkauntlar **Supabase**'da (bepul Postgres), uyg'oq turishi uchun **UptimeRobot** sahifani har 5 daqiqada ochib turadi.

1. **Supabase**: supabase.com → New project (region: Frankfurt) → parolni saqlang →
   **Connect** → **Session pooler** ulanish satrini (URI) nusxalang, `[YOUR-PASSWORD]` o'rniga parolni qo'ying.
2. Ulanish satrini `.env` ga `DATABASE_URL=` qilib yozing va mahalliy bazani ko'chiring:
   `python migrate_to_pg.py`
3. **Kompyuterdagi botni to'xtating** (bitta sessiya ikki joyda ishlasa Telegram uni o'chiradi).
4. **Render**: render.com → New → **Blueprint** → GitHub repozitoriyni tanlang → `render.yaml` o'qiladi →
   so'ralgan maxfiy qiymatlarni kiriting: `BOT_TOKEN`, `API_ID`, `API_HASH`, `DATABASE_URL`, `GEMINI_API_KEY`.
5. Deploy tugagach Render bergan manzil (`https://...onrender.com`) ochilsa `ok, ulangan akkauntlar: 1` chiqadi.
6. **UptimeRobot**: uptimerobot.com → ro'yxatdan o'ting → **Add New Monitor** → turi **HTTP(s)** →
   URL: Render manzili → interval **5 daqiqa** → Create. (Bonus: bot to'xtasa UptimeRobot emailga xabar beradi.)

GitHub'ga yangi kod yuklansa (`git push`), Render o'zi qayta deploy qiladi.

---

# Serverga qo'yish (Ubuntu 22.04 / 24.04)

Kerak: istalgan VPS, 1 GB RAM, Ubuntu. Masalan: Hetzner CX22, DigitalOcean, Timeweb Cloud, Aeza (~$4–6/oy).
Provayder bergan: **IP manzil** va **root paroli** (yoki SSH kalit).

> Muhim: fayllarni yuklashdan **oldin** kompyuterdagi botni to'xtating — bitta token va bitta
> sessiya bilan ikki joyda ishlab bo'lmaydi (Telegram sessiyani o'chirib yuborishi mumkin).

## 1. Fayllarni serverga yuklash (kompyuterda, PowerShell)
```
scp -r "BOT_PAPKASI" root@SERVER_IP:/opt/azizbot
```

## 2. Serverda o'rnatish
```
ssh root@SERVER_IP
cd /opt/azizbot
rm -rf bot.log __pycache__                     # keraksiz fayllar
# bot.db va sessions/ QOLADI — ulangan akkaunt qayta ulanishi shart emas
apt update && apt install -y python3 python3-venv
python3 -m venv venv
venv/bin/pip install -r requirements.txt
chmod 600 .env
```

## 3. Doimiy ishlaydigan qilish (server qayta yonsa ham o'zi ishga tushadi)
```
cp deploy/azizbot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now azizbot
```

## Foydali buyruqlar
| Nima | Buyruq |
|---|---|
| Ishlayaptimi? | `systemctl status azizbot` |
| Loglarni ko'rish | `journalctl -u azizbot -f` |
| Qayta ishga tushirish (`.env` o'zgarsa) | `systemctl restart azizbot` |
| To'xtatish | `systemctl stop azizbot` |

## Kodni yangilash
Kompyuterda o'zgartirilgan faylni yuklab, qayta ishga tushirish:
```
scp "BOT_PAPKASI/handlers.py" root@SERVER_IP:/opt/azizbot/
ssh root@SERVER_IP systemctl restart azizbot
```

## Zaxira nusxa
Muhim fayllar: `/opt/azizbot/bot.db` (murojaatlar) va `/opt/azizbot/sessions/` (ulangan akkauntlar).
`sessions/` — akkauntga kirish kaliti, hech kimga bermang.
