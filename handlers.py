import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.types import BusinessConnection, CallbackQuery, Message

import core
import db
import notify
import views
from config import ALLOWED_OWNERS, TZ

log = logging.getLogger(__name__)
router = Router()


def allowed(user_id: int) -> bool:
    return not ALLOWED_OWNERS or user_id in ALLOWED_OWNERS


# ---------- Telegram Business: ulanish ----------

@router.business_connection()
async def on_connection(bc: BusinessConnection, bot: Bot) -> None:
    db.save_connection(bc.id, bc.user.id, bc.user_chat_id, bc.is_enabled)
    if not allowed(bc.user.id):
        log.warning("Ruxsatsiz ulanish: %s", bc.user.id)
        return
    db.ensure_owner(bc.user.id, bc.user_chat_id)
    if bc.is_enabled:
        text = (
            "✅ <b>Bot akkauntingizga ulandi!</b>\n\n"
            "Tanlangan mijozlar yozsa — shu yerga kartochka keladi.\n"
            "Bajarilmaganlarini eslatib turaman."
        )
    else:
        text = "⛔️ Bot akkauntingizdan uzildi. Mijoz xabarlari endi kelmaydi."
    try:
        await bot.send_message(bc.user_chat_id, text, reply_markup=views.menu_kb())
    except Exception as e:  # ega botga hali /start bosmagan bo'lishi mumkin
        log.warning("Egaga yozib bo'lmadi: %s", e)


async def owner_of(bot: Bot, conn_id: str) -> int | None:
    conn = db.get_connection(conn_id)
    if conn is None:  # bot qayta ishga tushgan, ulanish bazada yo'q
        bc = await bot.get_business_connection(conn_id)
        db.save_connection(bc.id, bc.user.id, bc.user_chat_id, bc.is_enabled)
        db.ensure_owner(bc.user.id, bc.user_chat_id)
        conn = db.get_connection(conn_id)
    if not conn["enabled"] or not allowed(conn["owner_id"]):
        return None
    if db.get_owner(conn["owner_id"]) is None:
        db.ensure_owner(conn["owner_id"], conn["owner_chat_id"])
    return conn["owner_id"]


# ---------- Telegram Business: mijoz xabarlari ----------

@router.business_message()
async def on_business_message(msg: Message, bot: Bot) -> None:
    if msg.chat.type != "private":
        return
    owner_id = await owner_of(bot, msg.business_connection_id)
    if owner_id is None:
        return
    if (msg.from_user and msg.from_user.id == owner_id) or msg.sender_business_bot:
        await core.owner_replied(bot, owner_id, msg.chat.id)
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    audio, duration = None, 0
    media = msg.voice or msg.video_note or msg.audio
    if media:
        mime = getattr(media, "mime_type", None) or ("video/mp4" if msg.video_note else "audio/ogg")
        duration = media.duration or 0

        async def audio():
            return (await bot.download(media)).getvalue(), mime

    await core.client_message(
        bot, owner_id, msg.chat.id, msg.chat.full_name or "Nomsiz", msg.chat.username,
        views.describe(msg), audio, duration,
    )


# ---------- Kartochka tugmalari ----------

@router.callback_query(F.data.startswith("st:"))
async def on_status(cb: CallbackQuery, bot: Bot) -> None:
    _, rid, status = cb.data.split(":")
    req = db.get_request(int(rid))
    if req is None or req["owner_id"] != cb.from_user.id or status not in views.ICON:
        await cb.answer("Topilmadi", show_alert=True)
        return
    db.set_status(req["id"], status)
    if req["card_msg_id"] != cb.message.message_id:
        db.set_card(req["id"], cb.message.message_id)
    await notify.send_card(bot, req["id"], resend=False)
    await cb.answer({"new": "↩️ Qaytarildi", "progress": "⏳ Jarayonda", "done": "✅ Bajarildi"}[status])


@router.callback_query(F.data.startswith("show:"))
async def on_show(cb: CallbackQuery, bot: Bot) -> None:
    req = db.get_request(int(cb.data.split(":")[1]))
    if req is None or req["owner_id"] != cb.from_user.id:
        await cb.answer("Topilmadi", show_alert=True)
        return
    await notify.send_card(bot, req["id"], resend=True)
    await cb.answer()


@router.callback_query(F.data.startswith("set:"))
async def on_setting(cb: CallbackQuery) -> None:
    _, field, value = cb.data.split(":")
    owner = db.get_owner(cb.from_user.id)
    if owner is None or field not in {"remind_new", "remind_progress", "quiet"}:
        await cb.answer()
        return
    db.set_owner_field(owner["owner_id"], field, int(value))
    owner = db.get_owner(owner["owner_id"])
    try:
        await cb.message.edit_text(views.settings_text(owner), reply_markup=views.settings_kb(owner))
    except Exception:
        pass
    await cb.answer("Saqlandi")


# ---------- "Mijozmi?" tugmalari ----------

@router.callback_query(F.data.startswith("who:"))
async def on_who(cb: CallbackQuery, bot: Bot) -> None:
    _, uid, answer = cb.data.split(":")
    owner_id, user_id = cb.from_user.id, int(uid)
    person = db.get_person(owner_id, user_id)
    if person is None:
        await cb.answer("Topilmadi", show_alert=True)
        return
    if answer == "yes":
        try:
            await cb.message.delete()
        except Exception:
            pass
        await core.approve(bot, owner_id, user_id)
        await cb.answer("✅ Mijozlarga qo'shildi")
    else:
        core.reject(owner_id, user_id)
        text, kb = views.person_rejected(person)
        await cb.message.edit_text(text, reply_markup=kb)
        await cb.answer("Endi uning xabarlari kelmaydi")


# ---------- Bot bilan shaxsiy chat: menyu (/start — login_flow.py da) ----------

@router.message(F.text == views.BTN_OPEN)
async def on_open(msg: Message, bot: Bot) -> None:
    if db.get_owner(msg.from_user.id):
        await notify.send_open_list(bot, msg.from_user.id, reminder=False)


@router.message(F.text == views.BTN_LIST)
async def on_list(msg: Message) -> None:
    if not db.get_owner(msg.from_user.id):
        return
    day_start = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    reqs = db.list_for_day(msg.from_user.id, int(day_start.timestamp()))
    await msg.answer(views.day_list(reqs))


@router.message(F.text == views.BTN_SETTINGS)
async def on_settings(msg: Message) -> None:
    owner = db.get_owner(msg.from_user.id)
    if owner:
        await msg.answer(views.settings_text(owner), reply_markup=views.settings_kb(owner))
