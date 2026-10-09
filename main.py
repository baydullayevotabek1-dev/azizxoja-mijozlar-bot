import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from aiohttp import web

import db
from config import BOT_TOKEN, PORT, STARTUP_DELAY
from handlers import router
from login_flow import router as login_router
from reminder import reminder_loop
from userbot import accounts, start_userbots

log = logging.getLogger(__name__)


async def start_web() -> None:
    """Render uchun: sahifa so'rov olib turmasa, bepul server 15 daqiqada uxlab qoladi."""
    if not PORT:
        return

    async def health(_request):
        return web.Response(text=f"ok, ulangan akkauntlar: {len(accounts)}")

    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info("Veb-sahifa %s-portda", PORT)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN yo'q")
    db.init()
    await start_web()
    if STARTUP_DELAY:
        log.info("Eski nusxa to'xtashini kutyapmiz: %s soniya", STARTUP_DELAY)
        await asyncio.sleep(STARTUP_DELAY)

    bot = Bot(
        BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML", link_preview_is_disabled=True),
    )
    dp = Dispatcher()
    dp.include_router(login_router)  # /start va akkaunt ulash — birinchi
    dp.include_router(router)

    await bot.set_my_commands([BotCommand(command="start", description="Botni ishga tushirish")])
    await start_userbots(bot)
    asyncio.create_task(reminder_loop(bot))
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
