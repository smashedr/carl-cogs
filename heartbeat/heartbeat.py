import asyncio
import datetime
import httpx
import logging
import time

from redbot.core import commands
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.heartbeat')


class Heartbeat(commands.Cog):
    """Carl's Heartbeat Cog"""
    sleep = 60
    url = 'https://intranet-proxy.cssnr.com/api/push/0EzRBO5tb3?msg={msg}&ping={ping}'
    http_options = {
        'follow_redirects': True,
        'verify': False,
        'timeout': 30,
    }

    def __init__(self, bot):
        self.bot = bot
        self.loop = None

    def post_init(self):
        log.info('Initializing Heartbeat Cog Start')
        self.loop = asyncio.create_task(self.heartbeat_loop())
        log.info('Initializing Heartbeat Cog Finished')

    def cog_unload(self):
        if self.loop and not self.loop.cancelled():
            log.info('Unload Cog - Stopping Loop')
            self.loop.cancel()

    async def heartbeat_loop(self):
        log.info('Starting Heartbeat Loop in %s seconds...', round(60 - time.time() % 60))
        await asyncio.sleep(60 - time.time() % 60)
        while self is self.bot.get_cog('Heartbeat'):
            bot_delta = datetime.datetime.utcnow() - self.bot.uptime
            msg = 'Uptime: {}'.format(cf.humanize_timedelta(timedelta=bot_delta))
            ping = str(round(self.bot.latency * 1000, 2))
            url = self.url.format(msg=msg, ping=ping)
            try:
                async with httpx.AsyncClient(**self.http_options) as client:
                    r = await client.get(url)
                    log.debug(r.content)
                if not r.is_success:
                    r.raise_for_status()
            except Exception as error:
                log.exception(error)
            await asyncio.sleep(self.sleep - time.time() % 60)
