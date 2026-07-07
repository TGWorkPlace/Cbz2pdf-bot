"""
webserver.py — Lightweight HTTP health check server for Koyeb.
Listens on port 8080. Run alongside bot.py.
"""

from aiohttp import web
import asyncio
import logging

logger = logging.getLogger(__name__)

async def health(request):
    return web.Response(text="OK", status=200)

async def root(request):
    return web.json_response({
        "status": "running",
        "service": "CBR/CBZ to PDF Bot",
    })

def create_app():
    app = web.Application()
    app.router.add_get("/", root)
    app.router.add_get("/health", health)
    return app

async def run_webserver():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Webserver running on http://0.0.0.0:8080")
    return runner
