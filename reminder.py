"""Har daqiqada tekshiradi va vaqti kelgan egalarga bitta jamlangan eslatma yuboradi."""
import asyncio
import logging
from datetime import datetime

from aiogram import Bot

import db
import notify
from config import QUIET_FROM, QUIET_TO, TZ

log = logging.getLogger(__name__)


def is_quiet_now() -> bool:
    hour = datetime.now(TZ).hour
    if QUIET_FROM > QUIET_TO:  # masalan 22 -> 8 (yarim tundan o'tadi)
        return hour >= QUIET_FROM or hour < QUIET_TO
    return QUIET_FROM <= hour < QUIET_TO


def is_due(req, owner, now: int) -> bool:
    interval = owner["remind_new"] if req["status"] == "new" else owner["remind_progress"]
    if req["urgent"]:
        interval //= 2  # 🔥 shoshilinchlar ikki barobar tez-tez eslatiladi
    return bool(interval) and now - req["last_reminded_at"] >= interval * 60


async def tick(bot: Bot) -> None:
    now = db.now()
    quiet = is_quiet_now()
    for owner in db.all_owners():
        if owner["quiet"] and quiet:
            continue
        reqs = db.list_open(owner["owner_id"])
        if any(is_due(r, owner, now) for r in reqs):
            await notify.send_open_list(bot, owner["owner_id"], reminder=True)


async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            await tick(bot)
        except Exception:
            log.exception("Eslatmada xato")
        await asyncio.sleep(60)
