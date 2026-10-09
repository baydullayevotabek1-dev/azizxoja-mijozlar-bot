"""Premium'siz rejim: egasining akkauntiga (Telethon sessiyasi orqali) ulanib, shaxsiy chatlarni kuzatadi.
Mijoz kim: Telegramdagi «Mijozlar» papkasidagilar + bot "✅ Mijoz" deb belgilaganlar."""
import asyncio
import glob
import logging
import os
from dataclasses import dataclass

from aiogram import Bot
from telethon import TelegramClient, events, functions, types, utils
from telethon.errors import AuthKeyDuplicatedError, AuthKeyUnregisteredError, UnauthorizedError
from telethon.sessions import StringSession

import core
import db
import views
from config import API_HASH, API_ID, FOLDER_NAME, SESSIONS_DIR

log = logging.getLogger(__name__)

FOLDER_UPDATES = (types.UpdateDialogFilter, types.UpdateDialogFilters, types.UpdateDialogFilterOrder)


class Folder:
    """Telegram papkasi: kim unga kiradi — shuni aniqlaydi, kerak bo'lsa odam qo'shadi."""

    def __init__(self, client: TelegramClient):
        self.client = client
        self.filter: types.DialogFilter | None = None
        self.include: set[int] = set()
        self.exclude: set[int] = set()

    async def _all(self) -> list:
        res = await self.client(functions.messages.GetDialogFiltersRequest())
        return list(getattr(res, "filters", res))

    async def refresh(self) -> None:
        for f in await self._all():
            if not isinstance(f, types.DialogFilter):
                continue
            title = getattr(f.title, "text", f.title)
            if title.strip().lower() == FOLDER_NAME.lower():
                self.filter = f
                self.include = {utils.get_peer_id(p) for p in f.include_peers + f.pinned_peers}
                self.exclude = {utils.get_peer_id(p) for p in f.exclude_peers}
                return
        self.filter = None
        self.include, self.exclude = set(), set()

    def has(self, user: types.User) -> bool:
        f = self.filter
        if f is None or user.id in self.exclude:
            return False
        if user.id in self.include:
            return True
        # Papkaga "Barcha kontaktlar" / "Kontakt bo'lmaganlar" turi qo'shilgan bo'lsa
        return bool(f.contacts) if user.contact else bool(f.non_contacts)

    async def add(self, user_id: int) -> None:
        """Odamni papkaga qo'shadi; papka bo'lmasa — yaratadi."""
        await self.refresh()
        if user_id in self.include:
            return
        peer = await self.client.get_input_entity(user_id)
        f = self.filter
        if f is None:
            ids = [x.id for x in await self._all() if hasattr(x, "id")]
            f = types.DialogFilter(
                id=max(ids + [1]) + 1,
                title=types.TextWithEntities(text=FOLDER_NAME, entities=[]),
                pinned_peers=[], include_peers=[peer], exclude_peers=[],
            )
        else:
            f.include_peers.append(peer)
            f.exclude_peers = [p for p in f.exclude_peers if utils.get_peer_id(p) != user_id]
        await self.client(functions.messages.UpdateDialogFilterRequest(id=f.id, filter=f))
        await self.refresh()


@dataclass
class Account:
    client: TelegramClient
    folder: Folder


accounts: dict[int, Account] = {}  # owner_id -> ulangan akkaunt


def username_of(user: types.User) -> str | None:
    if user.username:
        return user.username
    for u in user.usernames or []:
        if u.active:
            return u.username
    return None


async def start_one(bot: Bot, session: str) -> int | None:
    """Sessiyani (StringSession matni) ishga tushiradi. Muvaffaqiyatli bo'lsa egasining ID'sini qaytaradi."""
    # connection_retries=None — internet uzilsa ham to'xtovsiz qayta ulanadi
    client = TelegramClient(StringSession(session), API_ID, API_HASH, connection_retries=None, retry_delay=5)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        return None

    me = await client.get_me()
    owner_id = me.id
    if owner_id in accounts:  # shu akkaunt allaqachon ishlayapti
        await client.disconnect()
        return owner_id
    db.ensure_owner(owner_id, owner_id)  # bot bilan shaxsiy chat ID = foydalanuvchi ID

    folder = Folder(client)
    await folder.refresh()
    accounts[owner_id] = Account(client, folder)

    @client.on(events.NewMessage(func=lambda e: e.is_private))
    async def on_message(event) -> None:
        if event.out:
            await core.owner_replied(bot, owner_id, event.chat_id)
            return
        sender = await event.get_sender()
        if not isinstance(sender, types.User) or sender.bot or sender.is_self:
            return

        m = event.message
        name = utils.get_display_name(sender) or "Nomsiz"
        text = views.describe_tl(m)
        person = db.get_person(owner_id, sender.id)
        decision = person["decision"] if person else None

        if decision == "ignore":
            return
        if decision == "client" or folder.has(sender):
            audio, duration = None, 0
            if m.voice or m.video_note or m.audio:
                duration = int(m.file.duration or 0)
                mime = m.file.mime_type or "audio/ogg"

                async def audio():
                    return await m.download_media(file=bytes), mime

            await core.client_message(
                bot, owner_id, sender.id, name, username_of(sender), text, audio, duration
            )
            return
        await core.unknown_person(bot, owner_id, sender.id, name, username_of(sender), text)

    @client.on(events.Raw(FOLDER_UPDATES))
    async def on_folder_change(_) -> None:
        await folder.refresh()  # papkaga mijoz qo'shilsa/olib tashlansa darhol hisobga olinadi

    async def refresh_loop() -> None:
        while client.is_connected():
            await asyncio.sleep(300)
            try:
                await folder.refresh()
            except Exception:
                log.exception("Papkani yangilab bo'lmadi")

    asyncio.create_task(refresh_loop())
    asyncio.create_task(_watch(bot, owner_id, client))
    log.info("%s (%s) ulandi, papkada %s ta chat", me.first_name, owner_id, len(folder.include))
    return owner_id


async def _session_alive(client: TelegramClient) -> bool | None:
    """True — sessiya ishlaydi, False — Telegram uni o'chirgan, None — tarmoq yo'q (aniq emas)."""
    try:
        if not client.is_connected():
            await client.connect()
        return await client.is_user_authorized()
    except (AuthKeyUnregisteredError, AuthKeyDuplicatedError, UnauthorizedError):
        return False
    except Exception:
        return None


async def _watch(bot: Bot, owner_id: int, client: TelegramClient) -> None:
    """Ulanish tugasa — sabab tarmoqmi yoki sessiya o'chirilganmi, aniqlaydi.
    Faqat Telegram sessiyani haqiqatan o'chirgan bo'lsa egasiga xabar beradi."""
    while True:
        try:
            await client.run_until_disconnected()
        except Exception as e:
            log.warning("%s: Telegram ulanishi tugadi: %s", owner_id, e)
        acc = accounts.get(owner_id)
        if acc is None or acc.client is not client:
            return  # ataylab uzilgan (logout)
        delay = 5
        while (alive := await _session_alive(client)) is None:
            log.warning("%s: tarmoq yo'q, %s soniyadan keyin qayta urinamiz", owner_id, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 120)
        if alive:
            log.info("%s: qayta ulandi", owner_id)
            continue
        break
    accounts.pop(owner_id, None)
    db.delete_session(owner_id)
    log.error("%s: sessiya yaroqsiz bo'lib qoldi", owner_id)
    try:
        await bot.send_message(
            owner_id,
            "⚠️ <b>Bot akkauntingizdan uzilib qoldi</b> — mijoz xabarlari endi kelmaydi.\n"
            "Qayta ulash uchun /start bosing.",
        )
    except Exception:
        pass


def _migrate_session_files() -> None:
    """Eski usul (login.py) bilan yaratilgan .session fayllarni bazaga ko'chiradi."""
    from telethon.sessions import SQLiteSession

    for path in sorted(glob.glob(os.path.join(SESSIONS_DIR, "*.session"))):
        try:
            file_session = SQLiteSession(path[: -len(".session")])
            if not file_session.auth_key:
                file_session.close()
                continue
            text = StringSession.save(file_session)
            file_session.close()
        except Exception as e:
            log.warning("%s ni o'qib bo'lmadi: %s", path, e)
            continue
        db.save_session(_session_owner_hint(path), text)
        try:
            os.replace(path, path + ".migrated")
        except OSError as e:  # fayl boshqa dasturda ochiq — keyingi safar qayta urinamiz
            log.warning("%s ni qayta nomlab bo'lmadi: %s", path, e)
        log.info("%s bazaga ko'chirildi", path)


def _session_owner_hint(path: str) -> int:
    """Fayl nomi ID bo'lsa — o'sha; bo'lmasa vaqtinchalik manfiy kalit (ishga tushganda to'g'rilanadi)."""
    name = os.path.basename(path)[: -len(".session")]
    return int(name) if name.isdigit() else -abs(hash(name)) % (10**12)


async def start_userbots(bot: Bot) -> None:
    if not API_ID or not API_HASH:
        log.info("API_ID/API_HASH yo'q — akkaunt ulash o'chiq")
        return
    if os.path.isdir(SESSIONS_DIR):
        _migrate_session_files()
    for row in db.all_sessions():
        try:
            owner_id = await start_one(bot, row["session"])
        except Exception:
            log.exception("%s sessiyasini ishga tushirib bo'lmadi", row["owner_id"])
            continue
        if owner_id is None:
            log.error("%s: sessiya yaroqsiz — o'chirildi, egasi qayta ulanishi kerak", row["owner_id"])
            db.delete_session(row["owner_id"])
        elif owner_id != row["owner_id"]:  # vaqtinchalik kalitni haqiqiy ID bilan almashtiramiz
            db.delete_session(row["owner_id"])
            db.save_session(owner_id, row["session"])
    if not accounts:
        log.info("Hali hech qanday akkaunt ulanmagan — botga /start bosing")


async def add_to_folder(owner_id: int, user_id: int) -> None:
    acc = accounts.get(owner_id)
    if acc is None:
        return
    try:
        await acc.folder.add(user_id)
    except Exception as e:  # masalan, papka to'lgan (100 ta chat) — baza baribir eslab qoladi
        log.warning("Papkaga qo'shib bo'lmadi (%s): %s", user_id, e)


async def logout(owner_id: int) -> None:
    """Akkauntdan butunlay chiqadi va sessiyani bazadan o'chiradi."""
    acc = accounts.pop(owner_id, None)
    db.delete_session(owner_id)
    if acc:
        try:
            await acc.client.log_out()
        except Exception:
            log.exception("log_out xatosi")
