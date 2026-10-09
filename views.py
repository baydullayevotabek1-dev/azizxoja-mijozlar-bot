"""Kartochkalar, ro'yxatlar va tugmalar matni."""
from datetime import datetime
from html import escape

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

import db
from config import QUIET_FROM, QUIET_TO, TZ

ICON = {"new": "🆕", "progress": "⏳", "done": "✅"}
STATUS_NAME = {"new": "Yangi", "progress": "Jarayonda", "done": "Bajarildi"}

BTN_OPEN = "🔴 Bajarilmaganlar"
BTN_LIST = "📋 Ro'yxat"
BTN_SETTINGS = "⚙️ Sozlamalar"


def hhmm(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%H:%M")


def ago(ts: int) -> str:
    mins = max(0, (db.now() - ts) // 60)
    if mins < 1:
        return "hozirgina"
    if mins < 60:
        return f"{mins} daq"
    hours, mins = divmod(mins, 60)
    if hours < 24:
        return f"{hours} soat {mins} daq" if mins else f"{hours} soat"
    return f"{hours // 24} kun"


def short(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def describe(m: Message) -> str:
    """Mijoz xabarini bir qatorga aylantiradi (media bo'lsa belgisi bilan)."""
    media = None
    if m.photo:
        media = "📷 Rasm"
    elif m.video:
        media = "🎬 Video"
    elif m.video_note:
        media = "⏺ Video xabar"
    elif m.voice:
        media = f"🎤 Ovozli xabar ({m.voice.duration // 60}:{m.voice.duration % 60:02d})"
    elif m.audio:
        media = "🎵 Audio"
    elif m.animation:
        media = "🎞 GIF"
    elif m.document:
        media = f"📎 Fayl: {m.document.file_name or ''}".strip()
    elif m.sticker:
        media = f"{m.sticker.emoji or ''} Stiker".strip()
    elif m.location:
        media = "📍 Lokatsiya"
    elif m.contact:
        media = f"👤 Kontakt: {m.contact.first_name} {m.contact.phone_number}"
    text = m.text or m.caption or ""
    if media and text:
        return f"{media} — {text}"
    return media or text or "(xabar)"


def describe_tl(m) -> str:
    """Telethon xabari uchun describe() ning o'xshashi (papka rejimi)."""
    media = None
    if m.photo:
        media = "📷 Rasm"
    elif m.video_note:
        media = "⏺ Video xabar"
    elif m.voice:
        dur = int(m.file.duration or 0)
        media = f"🎤 Ovozli xabar ({dur // 60}:{dur % 60:02d})"
    elif m.gif:
        media = "🎞 GIF"
    elif m.video:
        media = "🎬 Video"
    elif m.audio:
        media = "🎵 Audio"
    elif m.sticker:
        media = f"{m.file.emoji or ''} Stiker".strip()
    elif m.geo:
        media = "📍 Lokatsiya"
    elif m.contact:
        media = f"👤 Kontakt: {m.contact.first_name} {m.contact.phone_number}"
    elif m.document:
        media = f"📎 Fayl: {m.file.name or ''}".strip()
    text = m.message or ""
    if media and text:
        return f"{media} — {text}"
    return media or text or "(xabar)"


def icon(req) -> str:
    """Status belgisi; shoshilinch va hali bajarilmagan bo'lsa — 🔥 qo'shiladi."""
    base = ICON[req["status"]]
    return f"🔥{base}" if req["urgent"] and req["status"] != "done" else base


def gist(req, n: int) -> str:
    """Ro'yxatlar uchun: AI xulosasi bo'lsa o'sha, bo'lmasa oxirgi xabar."""
    return short(req["summary"] or db.last_text(req["id"]), n)


def chat_url(req) -> str:
    if req["username"]:
        return f"https://t.me/{req['username']}"
    return f"tg://user?id={req['client_id']}"


# --- Murojaat kartochkasi ---

def card_text(req) -> str:
    msgs = db.last_messages(req["id"], 5)
    total = db.count_messages(req["id"])
    name = f'<a href="tg://user?id={req["client_id"]}">{escape(req["client_name"])}</a>'
    user = f" · @{escape(req['username'])}" if req["username"] else ""

    lines = [f"{icon(req)} <b>{name}</b>{user}"]
    if req["summary"]:
        lines.append(f"🧠 <i>{escape(req['summary'])}</i>")
    lines.append("")
    if total > len(msgs):
        lines.append(f"<i>…yana {total - len(msgs)} ta oldingi xabar</i>")
    for m in msgs:
        lines.append(f"<code>{hhmm(m['created_at'])}</code>  {escape(short(m['text'], 600))}")
    lines.append("")
    if req["status"] == "done":
        lines.append(f"✅ <b>Bajarildi</b> · {hhmm(req['done_at'])}")
    else:
        lines.append(
            f"{ICON[req['status']]} <b>{STATUS_NAME[req['status']]}</b> · "
            f"yozganiga {ago(req['created_at'])}"
        )
    return "\n".join(lines)


def card_kb(req, with_link: bool = True) -> InlineKeyboardMarkup:
    rid, st = req["id"], req["status"]
    if st == "new":
        row = [
            InlineKeyboardButton(text="⏳ Jarayonda", callback_data=f"st:{rid}:progress"),
            InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"st:{rid}:done"),
        ]
    elif st == "progress":
        row = [InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"st:{rid}:done")]
    else:
        row = [InlineKeyboardButton(text="↩️ Qaytarish", callback_data=f"st:{rid}:new")]
    rows = [row]
    if with_link:
        rows.append([InlineKeyboardButton(text="💬 Chatni ochish", url=chat_url(req))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- "Mijozmi?" so'rovi ---

def person_prompt(person, pending) -> tuple[str, InlineKeyboardMarkup]:
    name = f'<a href="tg://user?id={person["user_id"]}">{escape(person["name"])}</a>'
    user = f" · @{escape(person['username'])}" if person["username"] else ""
    lines = [f"👤 <b>Yangi odam yozdi:</b> {name}{user}", ""]
    for p in pending[-3:]:
        lines.append(f"<code>{hhmm(p['created_at'])}</code>  {escape(short(p['text'], 200))}")
    lines += ["", "<b>Bu mijozmi?</b>"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Mijoz", callback_data=f"who:{person['user_id']}:yes"),
        InlineKeyboardButton(text="❌ Mijoz emas", callback_data=f"who:{person['user_id']}:no"),
    ]])
    return "\n".join(lines), kb


def person_rejected(person) -> tuple[str, InlineKeyboardMarkup]:
    text = f"🚫 {escape(person['name'])} — mijoz emas. Uning xabarlari endi kelmaydi."
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Baribir mijoz", callback_data=f"who:{person['user_id']}:yes"),
    ]])
    return text, kb


# --- Akkauntni ulash ---

BTN_CONNECT = "📱 Akkauntni ulash"


BTN_QR = "📷 QR-kod orqali ulash"

QR_TEXT = (
    "📷 <b>QR-kod orqali ulash</b> (kod kerak emas)\n\n"
    "1. Telefoningizda Telegram → <b>Sozlamalar → Qurilmalar</b>\n"
    "2. <b>«Kompyuterni ulash»</b> (Link Desktop Device) ni bosing\n"
    "3. Shu QR-kodni skanerlang\n\n"
    "QR boshqa ekranda ko'rinishi kerak (masalan, kompyuterdagi Telegramda). "
    "Har 30 soniyada o'zi yangilanadi."
)


def connect_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CONNECT, request_contact=True)],
            [KeyboardButton(text=BTN_QR)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def qr_png(url: str) -> bytes:
    import io

    import segno

    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=10, border=3)
    return buf.getvalue()


def qr_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✖️ Bekor qilish", callback_data="kp:cancel")],
    ])


def keypad_text(code: str, note: str = "", where: str = "") -> str:
    shown = " ".join(code.ljust(5, "_"))
    head = f"{note}\n\n" if note else ""
    where = where or "Telegram'ning rasmiy <b>«Telegram»</b> chatiga"
    return (
        f"{head}📨 Kod {where} yuborildi.\n"
        "Kodni <b>pastdagi tugmalar bilan</b> kiriting.\n"
        "⚠️ Kodni xabar qilib yozmang — Telegram uni darhol bekor qiladi.\n\n"
        f"Kod:  <code>{shown}</code>"
    )


def keypad() -> InlineKeyboardMarkup:
    def k(t, d):
        return InlineKeyboardButton(text=t, callback_data=f"kp:{d}")

    return InlineKeyboardMarkup(inline_keyboard=[
        [k("1", "1"), k("2", "2"), k("3", "3")],
        [k("4", "4"), k("5", "5"), k("6", "6")],
        [k("7", "7"), k("8", "8"), k("9", "9")],
        [k("⌫", "del"), k("0", "0"), k("✅ Tayyor", "ok")],
        [k("🔄 Kodni qayta yuborish", "resend")],
        [k("📷 Kod kelmadi — QR orqali ulash", "qr")],
        [k("✖️ Bekor qilish", "cancel")],
    ])


# --- Bajarilmaganlar ro'yxati (eslatma ham shu) ---

def open_list(reqs, reminder: bool) -> tuple[str, InlineKeyboardMarkup | None]:
    if not reqs:
        return "🎉 Hammasi bajarilgan, ochiq murojaat yo'q.", None
    head = "🔔 <b>Eslatma!</b> " if reminder else ""
    lines = [f"{head}Bajarilmagan: <b>{len(reqs)} ta</b>", ""]
    buttons = []
    for r in reqs:
        lines.append(
            f"{icon(r)} {escape(r['client_name'])} — "
            f"{escape(gist(r, 50))} · <i>{ago(r['created_at'])}</i>"
        )
        if len(buttons) < 30:
            buttons.append([InlineKeyboardButton(
                text=f"{icon(r)} {short(r['client_name'], 25)} · {ago(r['created_at'])}",
                callback_data=f"show:{r['id']}",
            )])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


def day_list(reqs) -> str:
    if not reqs:
        return "📋 Bugun hali murojaat yo'q."
    counts = {s: sum(1 for r in reqs if r["status"] == s) for s in ICON}
    lines = [
        f"📋 <b>Bugungi ro'yxat: {len(reqs)} ta</b>",
        f"✅ {counts['done']}  ·  ⏳ {counts['progress']}  ·  🆕 {counts['new']}",
        "",
    ]
    for r in reqs:
        lines.append(
            f"{icon(r)} <code>{hhmm(r['created_at'])}</code> {escape(r['client_name'])} — "
            f"{escape(gist(r, 50))}"
        )
    text = "\n".join(lines)
    return text if len(text) < 4000 else text[:3990] + "\n…"


# --- Sozlamalar ---

def settings_text(owner) -> str:
    prog = f"har {owner['remind_progress']} daq" if owner["remind_progress"] else "o'chiq"
    quiet = f"{QUIET_FROM}:00–{QUIET_TO:02d}:00 eslatma yo'q" if owner["quiet"] else "o'chiq"
    return (
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"🆕 Yangi murojaatlar eslatmasi: <b>har {owner['remind_new']} daq</b>\n"
        f"⏳ Jarayondagilar eslatmasi: <b>{prog}</b>\n"
        f"🌙 Tungi tinchlik: <b>{quiet}</b>"
    )


def settings_kb(owner) -> InlineKeyboardMarkup:
    def b(text, field, val, cur):
        mark = " ✓" if cur == val else ""
        return InlineKeyboardButton(text=f"{text}{mark}", callback_data=f"set:{field}:{val}")

    return InlineKeyboardMarkup(inline_keyboard=[
        [b(f"🆕 {m} daq", "remind_new", m, owner["remind_new"]) for m in (15, 30, 60)],
        [b("⏳ 1 soat", "remind_progress", 60, owner["remind_progress"]),
         b("⏳ 2 soat", "remind_progress", 120, owner["remind_progress"]),
         b("⏳ O'chiq", "remind_progress", 0, owner["remind_progress"])],
        [b("🌙 Tun: yoqilgan", "quiet", 1, owner["quiet"]),
         b("🌙 Tun: o'chiq", "quiet", 0, owner["quiet"])],
        [InlineKeyboardButton(text="🔌 Akkauntni uzish", callback_data="logout:ask")],
    ])


def menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_OPEN), KeyboardButton(text=BTN_LIST)],
            [KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
