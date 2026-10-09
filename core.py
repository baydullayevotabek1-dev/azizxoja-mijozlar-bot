"""Murojaat logikasi — xabar qayerdan kelishidan qat'i nazar (papka yoki Telegram Business)."""
import asyncio
import logging
import re
from collections import defaultdict
from collections.abc import Awaitable, Callable

from aiogram import Bot

import ai
import db
import notify

log = logging.getLogger(__name__)

# Ovozli xabarni yuklab beruvchi funksiya: () -> (baytlar, mime turi)
AudioLoader = Callable[[], Awaitable[tuple[bytes, str]]]

MAX_VOICE_SECONDS = 300

# Ochiq murojaat yo'q paytda kelgan shunday xabarlar yangi murojaat ochmaydi
NOISE = {
    "rahmat", "raxmat", "rahmat aka", "raxmat aka", "katta rahmat", "rahmat katta",
    "рахмат", "рахмат ака", "спасибо", "спс", "благодарю",
    "ok", "ок", "okay", "окей", "xop", "xo'p", "xop aka", "хоп", "хоп ака", "ҳоп",
    "mayli", "майли", "yaxshi", "яхши", "zo'r", "зўр", "ajoyib", "понял", "ясно", "хорошо",
    "+", "👍", "🙏", "❤️", "❤", "🤝", "👌", "😊", "🔥", "✅",
}

_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def is_noise(text: str) -> bool:
    t = re.sub(r"[.,!?)(\s]+", " ", text.lower()).strip()
    return t in NOISE


async def client_message(
    bot: Bot,
    owner_id: int,
    client_id: int,
    name: str,
    username: str | None,
    text: str,
    audio: AudioLoader | None = None,
    duration: int = 0,
) -> None:
    """Mijoz yozdi: ochiq murojaati bo'lsa unga qo'shamiz, bo'lmasa yangisini ochamiz."""
    req = db.get_open_request(owner_id, client_id)
    if req is None:
        if audio is None and is_noise(text):
            log.info("%s: '%s' — yangi murojaat ochilmadi", name, text)
            return
        req_id = db.create_request(owner_id, client_id, name, username)
    else:
        req_id = req["id"]
        db.touch_request(req_id, name, username)
    msg_id = db.add_message(req_id, text)

    # Kartochka darhol keladi, AI natijasi keyin shu kartochkaga qo'shiladi
    await notify.send_card(bot, req_id, resend=True)
    if ai.enabled:
        asyncio.create_task(_enrich(bot, req_id, msg_id, text, audio, duration))


async def _enrich(
    bot: Bot, req_id: int, msg_id: int, text: str, audio: AudioLoader | None, duration: int
) -> None:
    try:
        async with _locks[req_id]:
            if audio is not None and duration <= MAX_VOICE_SECONDS:
                data, mime = await audio()
                transcript = await ai.transcribe(data, mime)
                if transcript:
                    db.update_message_text(msg_id, f"{text}: «{transcript}»")

            msgs = [m["text"] for m in db.last_messages(req_id, 15)]
            result = await ai.analyze(msgs)
            if result:
                db.set_analysis(req_id, result.summary.strip(), result.urgent)
            await notify.send_card(bot, req_id, resend=False)
    except Exception:
        log.exception("AI bilan boyitishda xato (murojaat %s)", req_id)


async def owner_replied(bot: Bot, owner_id: int, client_id: int) -> None:
    """Egasi mijozga o'zi javob yozdi -> "Yangi" bo'lsa "Jarayonda"ga o'tkazamiz."""
    req = db.get_open_request(owner_id, client_id)
    if req and req["status"] == "new":
        db.set_status(req["id"], "progress")
        await notify.send_card(bot, req["id"], resend=False)


# ---------- Papkada yo'q, yangi yozgan odam: "Mijozmi?" ----------

async def unknown_person(
    bot: Bot, owner_id: int, user_id: int, name: str, username: str | None, text: str
) -> None:
    db.save_person(owner_id, user_id, name, username, "pending")
    db.add_pending(owner_id, user_id, text)
    person = db.get_person(owner_id, user_id)
    await notify.send_prompt(bot, person, db.get_pending(owner_id, user_id))


async def approve(bot: Bot, owner_id: int, user_id: int) -> None:
    """"✅ Mijoz" bosildi: kutib turgan xabarlardan murojaat ochiladi."""
    import userbot  # aylanma importdan qochish uchun

    person = db.get_person(owner_id, user_id)
    pending = db.get_pending(owner_id, user_id)
    db.set_decision(owner_id, user_id, "client")
    db.clear_pending(owner_id, user_id)
    db.set_prompt(owner_id, user_id, None)
    asyncio.create_task(userbot.add_to_folder(owner_id, user_id))

    if not pending:
        return
    req = db.get_open_request(owner_id, user_id)
    req_id = req["id"] if req else db.create_request(owner_id, user_id, person["name"], person["username"])
    msg_id = 0
    for p in pending:
        msg_id = db.add_message(req_id, p["text"], p["created_at"])
    await notify.send_card(bot, req_id, resend=True)
    if ai.enabled:
        asyncio.create_task(_enrich(bot, req_id, msg_id, pending[-1]["text"], None, 0))


def reject(owner_id: int, user_id: int) -> None:
    db.set_decision(owner_id, user_id, "ignore")
