"""Egaga xabar yuborish: kartochka va bajarilmaganlar ro'yxati."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

import db
import views

log = logging.getLogger(__name__)


async def _send(bot: Bot, chat_id: int, req, text: str):
    try:
        return await bot.send_message(chat_id, text, reply_markup=views.card_kb(req))
    except TelegramBadRequest as e:
        # Mijozning maxfiylik sozlamasi tg://user?id= havolasini taqiqlashi mumkin
        log.warning("Chat havolasisiz yuboramiz: %s", e)
        return await bot.send_message(chat_id, text, reply_markup=views.card_kb(req, with_link=False))


async def send_card(bot: Bot, req_id: int, resend: bool) -> None:
    """resend=True — eski kartochkani o'chirib, pastga yangisini yuboradi (bildirishnoma keladi).
    resend=False — mavjud kartochkani joyida yangilaydi."""
    req = db.get_request(req_id)
    owner = db.get_owner(req["owner_id"])
    text = views.card_text(req)

    if not resend and req["card_msg_id"]:
        try:
            await bot.edit_message_text(
                text, chat_id=owner["chat_id"], message_id=req["card_msg_id"],
                reply_markup=views.card_kb(req),
            )
            return
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                return
            try:
                await bot.edit_message_text(
                    text, chat_id=owner["chat_id"], message_id=req["card_msg_id"],
                    reply_markup=views.card_kb(req, with_link=False),
                )
                return
            except TelegramBadRequest:
                pass  # kartochka o'chirilgan — yangisini yuboramiz

    if req["card_msg_id"]:
        try:
            await bot.delete_message(owner["chat_id"], req["card_msg_id"])
        except TelegramBadRequest:
            pass
    msg = await _send(bot, owner["chat_id"], req, text)
    db.set_card(req_id, msg.message_id)


async def send_prompt(bot: Bot, person, pending) -> None:
    """"Mijozmi?" so'rovi. Odam yana yozsa — o'sha xabar yangilanadi (qayta bildirishnoma yo'q)."""
    text, kb = views.person_prompt(person, pending)
    chat_id = db.get_owner(person["owner_id"])["chat_id"]
    if person["prompt_msg_id"]:
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=person["prompt_msg_id"], reply_markup=kb)
            return
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                return
    msg = await bot.send_message(chat_id, text, reply_markup=kb)
    db.set_prompt(person["owner_id"], person["user_id"], msg.message_id)


async def send_open_list(bot: Bot, owner_id: int, reminder: bool) -> None:
    """Bitta jamlangan ro'yxat. Oldingisi o'chiriladi — chat toza turadi."""
    owner = db.get_owner(owner_id)
    reqs = db.list_open(owner_id)
    text, kb = views.open_list(reqs, reminder)
    if owner["summary_msg_id"]:
        try:
            await bot.delete_message(owner["chat_id"], owner["summary_msg_id"])
        except TelegramBadRequest:
            pass
    msg = await bot.send_message(owner["chat_id"], text, reply_markup=kb)
    db.set_owner_field(owner_id, "summary_msg_id", msg.message_id)
    db.mark_reminded([r["id"] for r in reqs])
