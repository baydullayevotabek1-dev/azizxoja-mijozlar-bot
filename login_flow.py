"""Akkauntni botning o'zida ulash: /start -> raqamni ulashish -> kod (tugmalar bilan) -> 2FA parol.
Terminal kerak emas — foydalanuvchi faqat botga /start bosadi."""
import asyncio
import logging
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InputMediaPhoto,
    Message,
    ReplyKeyboardRemove,
)
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeEmptyError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberInvalidError,
    SendCodeUnavailableError,
    SessionPasswordNeededError,
)
from telethon.tl.types import auth as tl_auth

import db
import userbot
import views
from config import ALLOWED_OWNERS, API_HASH, API_ID

log = logging.getLogger(__name__)
router = Router()

LOGIN_TTL = 15 * 60  # tugallanmagan ulanish 15 daqiqadan keyin bekor bo'ladi


@dataclass
class Login:
    client: TelegramClient
    phone: str
    code_hash: str
    where: str = ""  # kod qayerga yuborilgani
    stage: str = "code"  # code | qr | password
    code: str = ""
    started: float = field(default_factory=time.time)


_logins: dict[int, Login] = {}


def can_connect(user_id: int) -> bool:
    return not ALLOWED_OWNERS or user_id in ALLOWED_OWNERS


def is_connected(user_id: int) -> bool:
    return user_id in userbot.accounts


async def _drop(user_id: int) -> None:
    """Tugallanmagan ulanishni bekor qiladi (sessiya hali bazaga yozilmagan)."""
    st = _logins.pop(user_id, None)
    if st:
        try:
            await st.client.disconnect()
        except Exception:
            pass


def code_destination(sent) -> str:
    """Telegram kodni qayerga yuborganini odam tushunadigan tilda aytadi."""
    t = sent.type
    if isinstance(t, tl_auth.SentCodeTypeApp):
        return "Telegram ilovasidagi rasmiy <b>«Telegram»</b> chatiga (ko'k belgili)"
    if isinstance(t, (tl_auth.SentCodeTypeSms, tl_auth.SentCodeTypeFirebaseSms,
                      tl_auth.SentCodeTypeSmsWord, tl_auth.SentCodeTypeSmsPhrase)):
        return "telefoningizga <b>SMS</b> orqali"
    if isinstance(t, (tl_auth.SentCodeTypeCall, tl_auth.SentCodeTypeFlashCall,
                      tl_auth.SentCodeTypeMissedCall)):
        return "<b>qo'ng'iroq</b> orqali (kod — qo'ng'iroq qilgan raqamning oxirgi raqamlari)"
    if isinstance(t, tl_auth.SentCodeTypeEmailCode):
        return f"<b>emailingizga</b> ({t.email_pattern})"
    if isinstance(t, tl_auth.SentCodeTypeFragmentSms):
        return "<b>Fragment</b> ilovasiga"
    if isinstance(t, tl_auth.SentCodeTypeSetUpEmailRequired):
        return ""  # Telegram avval email bog'lashni talab qilyapti
    return "Telegramga"


def _active(user_id: int) -> Login | None:
    st = _logins.get(user_id)
    if st and time.time() - st.started > LOGIN_TTL:
        return None
    return st


WELCOME = (
    "👋 <b>Assalomu alaykum!</b>\n\n"
    "Men mijozlaringiz yozganini sizga yetkazaman va bajarilmagan ishlarni eslatib turaman.\n\n"
    "Buning uchun Telegram akkauntingizga ulanishim kerak. "
    "Men faqat xabarlarni <b>o'qiyman</b>, hech kimga o'zim yozmayman.\n\n"
    "Pastdagi <b>«📱 Akkauntni ulash»</b> tugmasini bosing."
)

CONNECTED = (
    "✅ <b>Ulandi!</b>\n\n"
    "• Mijozlaringiz yozsa — shu yerga kartochka keladi: <b>⏳ Jarayonda</b> yoki <b>✅ Bajarildi</b> bosasiz.\n"
    "• Yangi odam yozsa — <b>«Mijozmi?»</b> deb so'rayman. «✅ Mijoz» bossangiz, "
    "uni Telegramdagi <b>«Mijozlar»</b> papkasiga o'zim qo'shaman.\n"
    "• Bajarilmaganlarni har 30 daqiqada eslatib turaman.\n\n"
    "Pastdagi tugmalar orqali ro'yxatni ko'rasiz."
)


@router.message(CommandStart())
async def on_start(msg: Message) -> None:
    uid = msg.from_user.id
    if is_connected(uid):
        await msg.answer(
            "👋 Bot ishlayapti.\n\n"
            "Mijoz yozsa — kartochka keladi: <b>⏳ Jarayonda</b> yoki <b>✅ Bajarildi</b> bosing.",
            reply_markup=views.menu_kb(),
        )
        return
    if not can_connect(uid):
        await msg.answer(f"Bu bot shaxsiy.\n\nSizning Telegram ID: <code>{uid}</code>")
        return
    if not API_ID or not API_HASH:
        await msg.answer("⚠️ Bot hali sozlanmagan (API_ID/API_HASH yo'q).")
        return
    await msg.answer(WELCOME, reply_markup=views.connect_kb())


@router.message(F.contact)
async def on_contact(msg: Message) -> None:
    uid = msg.from_user.id
    if is_connected(uid) or not can_connect(uid) or not API_ID:
        return
    if msg.contact.user_id != uid:
        await msg.answer("Faqat <b>o'z</b> raqamingizni yuboring — pastdagi tugmani bosing.",
                         reply_markup=views.connect_kb())
        return

    await _drop(uid)
    phone = msg.contact.phone_number
    phone = phone if phone.startswith("+") else "+" + phone
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
    except FloodWaitError as e:
        await client.disconnect()
        await msg.answer(f"⏳ Juda ko'p urinish bo'ldi. {e.seconds // 60 + 1} daqiqadan keyin qayta urinib ko'ring.",
                         reply_markup=views.connect_kb())
        return
    except (PhoneNumberInvalidError, PhoneNumberBannedError) as e:
        await client.disconnect()
        await msg.answer(f"❌ Bu raqam bilan kirib bo'lmadi: {type(e).__name__}")
        return

    where = code_destination(sent)
    log.info("Kod yuborildi: %s -> %s", uid, type(sent.type).__name__)
    if not where:
        await client.disconnect()
        await msg.answer(
            "⚠️ Telegram bu akkaunt uchun avval <b>login email</b> bog'lashni talab qilyapti.\n\n"
            "Telegram → Sozlamalar → Maxfiylik va xavfsizlik → <b>Login email</b> ni sozlang, "
            "keyin /start bosing.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    _logins[uid] = Login(client=client, phone=phone, code_hash=sent.phone_code_hash, where=where)
    await msg.answer("Raqam qabul qilindi ✅", reply_markup=ReplyKeyboardRemove())
    await msg.answer(views.keypad_text("", where=where), reply_markup=views.keypad())


async def _finish(bot: Bot, uid: int, chat_id: int) -> None:
    st = _logins[uid]
    me = await st.client.get_me()
    if me.id != uid:  # boshqa birovning akkaunti — darhol chiqamiz
        await st.client.log_out()
        _logins.pop(uid, None)
        await bot.send_message(chat_id, "❌ Bu boshqa akkaunt. Faqat o'z akkauntingizni ulash mumkin.")
        return
    session = st.client.session.save()
    await st.client.disconnect()
    _logins.pop(uid, None)
    db.save_session(uid, session)
    db.ensure_owner(uid, chat_id)
    try:
        await userbot.start_one(bot, session)
    except Exception:
        log.exception("Ulangandan keyin ishga tushmadi")
        await bot.send_message(chat_id, "⚠️ Ulandi, lekin ishga tushirishda xato. Botni qayta ishga tushiring.")
        return
    await bot.send_message(chat_id, CONNECTED, reply_markup=views.menu_kb())
    log.info("Akkaunt ulandi: %s", uid)


@router.callback_query(F.data.startswith("kp:"))
async def on_keypad(cb: CallbackQuery, bot: Bot) -> None:
    uid = cb.from_user.id
    st = _active(uid)
    key = cb.data[3:]
    if key == "cancel":
        await _drop(uid)
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer("✖️ Bekor qilindi. Qayta ulash uchun /start bosing.")
        await cb.answer()
        return
    if key == "qr":
        await cb.answer()
        try:
            await cb.message.delete()
        except Exception:
            pass
        await start_qr(bot, uid, cb.message.chat.id)
        return
    if st is None or st.stage != "code":
        await cb.answer("Ulanish eskirgan — /start bosing", show_alert=True)
        return

    note = ""
    if key.isdigit():
        if len(st.code) < 6:
            st.code += key
    elif key == "del":
        st.code = st.code[:-1]
    elif key == "resend":
        try:
            sent = await st.client.send_code_request(st.phone)
            st.code_hash, st.code = sent.phone_code_hash, ""
            st.where = code_destination(sent) or st.where
            log.info("Kod qayta yuborildi: %s -> %s", uid, type(sent.type).__name__)
            note = "🔄 Yangi kod yuborildi."
        except FloodWaitError as e:
            await cb.answer(f"{e.seconds // 60 + 1} daqiqa kuting", show_alert=True)
            return
        except SendCodeUnavailableError:
            await cb.answer(
                "Telegram boshqa usul bilan kod yubora olmaydi. Avvalgi kod amal qiladi — "
                "«Telegram» chatini tekshiring. Bo'lmasa 10–15 daqiqadan keyin /start bosing.",
                show_alert=True,
            )
            return
        except Exception as e:
            log.warning("Kodni qayta yuborib bo'lmadi: %s", e)
            await cb.answer("Kodni qayta yuborib bo'lmadi. Birozdan keyin /start bosing.", show_alert=True)
            return
    elif key == "ok":
        if len(st.code) < 5:
            await cb.answer("Kod 5 ta raqamdan iborat", show_alert=True)
            return
        try:
            await st.client.sign_in(phone=st.phone, code=st.code, phone_code_hash=st.code_hash)
        except SessionPasswordNeededError:
            st.stage = "password"
            await cb.message.edit_text(
                "🔐 Akkauntingizda <b>ikki bosqichli parol</b> bor.\n\n"
                "Parolni shu yerga xabar qilib yozing — o'qishim bilan xabarni o'chirib tashlayman."
            )
            await cb.answer()
            return
        except (PhoneCodeInvalidError, PhoneCodeEmptyError):
            st.code = ""
            note = "❌ Kod noto'g'ri. Qaytadan kiriting."
        except PhoneCodeExpiredError:
            st.code = ""
            note = "⌛ Kod eskirgan. «🔄 Kodni qayta yuborish» tugmasini bosing."
        else:
            await cb.message.edit_text("⏳ Ulanmoqda...")
            await cb.answer()
            await _finish(bot, uid, cb.message.chat.id)
            return

    try:
        await cb.message.edit_text(views.keypad_text(st.code, note, st.where), reply_markup=views.keypad())
    except Exception:
        pass
    await cb.answer()


# ---------- QR-kod orqali ulash (kod kelmasa) ----------

@router.message(F.text == views.BTN_QR)
async def on_qr_button(msg: Message, bot: Bot) -> None:
    uid = msg.from_user.id
    if is_connected(uid) or not can_connect(uid) or not API_ID:
        return
    await msg.answer("QR-kod tayyorlanmoqda...", reply_markup=ReplyKeyboardRemove())
    await start_qr(bot, uid, msg.chat.id)


async def start_qr(bot: Bot, uid: int, chat_id: int) -> None:
    await _drop(uid)
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    qr = await client.qr_login()
    _logins[uid] = Login(client=client, phone="", code_hash="", stage="qr")
    photo = BufferedInputFile(views.qr_png(qr.url), "qr.png")
    sent = await bot.send_photo(chat_id, photo, caption=views.QR_TEXT, reply_markup=views.qr_kb())
    log.info("QR ulash boshlandi: %s", uid)
    asyncio.create_task(_qr_wait(bot, uid, chat_id, qr, sent.message_id))


async def _qr_wait(bot: Bot, uid: int, chat_id: int, qr, msg_id: int) -> None:
    deadline = time.time() + 5 * 60
    try:
        while time.time() < deadline:
            st = _logins.get(uid)
            if st is None or st.stage != "qr":
                return  # bekor qilingan yoki boshqa usul tanlangan
            left = (qr.expires - datetime.now(timezone.utc)).total_seconds()
            try:
                await qr.wait(timeout=max(left, 5))
            except asyncio.TimeoutError:
                await qr.recreate()  # QR 30 soniyada eskiradi — yangisini ko'rsatamiz
                media = InputMediaPhoto(
                    media=BufferedInputFile(views.qr_png(qr.url), "qr.png"), caption=views.QR_TEXT
                )
                await bot.edit_message_media(media, chat_id=chat_id, message_id=msg_id,
                                             reply_markup=views.qr_kb())
                continue
            except SessionPasswordNeededError:
                st.stage = "password"
                await _delete(bot, chat_id, msg_id)
                await bot.send_message(
                    chat_id,
                    "✅ QR skanerlandi.\n\n🔐 Akkauntingizda <b>ikki bosqichli parol</b> bor.\n"
                    "Parolni shu yerga yozing — o'qishim bilan xabarni o'chirib tashlayman.",
                )
                return
            await _delete(bot, chat_id, msg_id)
            await _finish(bot, uid, chat_id)
            return
        await _drop(uid)
        await _delete(bot, chat_id, msg_id)
        await bot.send_message(chat_id, "⌛ QR muddati tugadi. Qayta urinish uchun /start bosing.")
    except Exception:
        st = _logins.get(uid)
        if st is None or st.stage != "qr":
            return  # foydalanuvchi bekor qildi — ulanish uzilgani uchun xato chiqdi
        log.exception("QR ulashda xato")
        await _drop(uid)
        await bot.send_message(chat_id, "⚠️ QR orqali ulab bo'lmadi. /start bosib qayta urinib ko'ring.")


async def _delete(bot: Bot, chat_id: int, msg_id: int) -> None:
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


def _waiting_password(msg: Message) -> bool:
    st = _active(msg.from_user.id) if msg.from_user else None
    return bool(st and st.stage == "password" and msg.text)


@router.message(_waiting_password)
async def on_password(msg: Message, bot: Bot) -> None:
    uid = msg.from_user.id
    st = _logins[uid]
    password = msg.text
    try:
        await msg.delete()
    except Exception:
        pass
    try:
        await st.client.sign_in(password=password)
    except PasswordHashInvalidError:
        await msg.answer("❌ Parol noto'g'ri. Qaytadan yozing.")
        return
    except FloodWaitError as e:
        await _drop(uid)
        await msg.answer(f"⏳ Juda ko'p urinish. {e.seconds // 60 + 1} daqiqadan keyin /start bosing.")
        return
    await _finish(bot, uid, msg.chat.id)


def _waiting_code_text(msg: Message) -> bool:
    st = _active(msg.from_user.id) if msg.from_user else None
    return bool(st and st.stage == "code" and msg.text)


@router.message(_waiting_code_text)
async def on_code_as_text(msg: Message) -> None:
    await msg.answer(
        "⚠️ Kodni xabar qilib yozmang — Telegram uni bekor qiladi.\n"
        "Yuqoridagi tugmalardan foydalaning. Kod ishlamasa — «🔄 Kodni qayta yuborish»."
    )


# ---------- Akkauntni uzish ----------

@router.callback_query(F.data == "logout:ask")
async def on_logout_ask(cb: CallbackQuery) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔌 Ha, uzish", callback_data="logout:yes"),
        InlineKeyboardButton(text="Yo'q", callback_data="logout:no"),
    ]])
    await cb.message.answer(
        "Akkauntni uzsangiz, bot mijoz xabarlarini ko'rmay qo'yadi. Ishonchingiz komilmi?", reply_markup=kb
    )
    await cb.answer()


@router.callback_query(F.data.in_({"logout:yes", "logout:no"}))
async def on_logout(cb: CallbackQuery) -> None:
    if cb.data == "logout:no":
        await cb.message.delete()
        await cb.answer()
        return
    uid = cb.from_user.id
    await userbot.logout(uid)
    db.delete_owner(uid)
    await cb.message.edit_text("🔌 Akkaunt uzildi. Qayta ulash uchun /start bosing.")
    await cb.answer()
