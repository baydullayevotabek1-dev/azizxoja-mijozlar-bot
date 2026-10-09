"""Akkauntga bir marta kirish. Ishga tushiring:  python login.py
Telefon raqam, Telegramdan kelgan kod va (bo'lsa) 2 bosqichli parol so'raladi.
Natijada sessions/<nom>.session fayli yaratiladi — uni hech kimga bermang!"""
import asyncio
import os

from telethon import TelegramClient

from config import API_HASH, API_ID, SESSIONS_DIR


async def main() -> None:
    if not API_ID or not API_HASH:
        raise SystemExit(".env faylida API_ID va API_HASH yo'q (my.telegram.org dan oling)")
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    name = input("Sessiya nomi (masalan: otabek yoki aziz): ").strip() or "main"
    client = TelegramClient(os.path.join(SESSIONS_DIR, name), API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"\n✅ Kirildi: {me.first_name} (ID {me.id})")
    print("Endi botga /start yozing va  python main.py  ni ishga tushiring.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
