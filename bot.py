import os
import asyncio
from aiohttp import web

# Загружаем переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "8296822215:AAE7HUE8FKo9TPv52LY7bg35Q1I8WT4Fk34")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "6090041587")
REVIEW_CHAT_ID = os.getenv("REVIEW_CHAT_ID", "-1002779423327")
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID", "-1002715413786")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

HEALTH_PORT = int(os.getenv("PORT", 8080))

async def health_handler(request):
    return web.Response(text="OK", status=200)

async def start_health_server():
    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=HEALTH_PORT)
    await site.start()
    print(f"Health server running on port {HEALTH_PORT}")

async def bot_logic():
    while True:
        print("Бот работает... (тут твоя логика)")
        await asyncio.sleep(30)

async def main():
    await start_health_server()
    await bot_logic()

if __name__ == "__main__":
    asyncio.run(main())
