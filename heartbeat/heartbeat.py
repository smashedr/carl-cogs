import asyncio
import datetime
import httpx
import logging
import time
from typing import Optional

from redbot.core import commands
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.heartbeat')


class Heartbeat(commands.Cog):
    """Carl's Heartbeat Cog"""

    http_options = {
        'follow_redirects': True,
        'verify': False,
        'timeout': 10,
    }

    def __init__(self, bot):
        self.bot = bot
        self.loop: Optional[asyncio.Task] = None
        self.url: Optional[str] = None
        self.sleep: int = 60

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('heartbeat')
        self.url = data['url']
        log.info('url: %s', self.url)
        self.sleep = int(data.get('sleep', self.sleep))
        log.info('sleep: %s', self.sleep)
        self.loop = asyncio.create_task(self.main_loop())

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        if self.loop and not self.loop.cancelled():
            log.info('Stopping Loop')
            self.loop.cancel()

    async def main_loop(self):
        await self.bot.wait_until_ready()
        log.info('%s: Start Main Loop', self.__cog_name__)
        while self is self.bot.get_cog('Heartbeat'):
            await asyncio.sleep(self.sleep - time.time() % self.sleep)
            if not self.url:
                log.warning('url NOT set for heartbeat. Use the [p]api set command.')
                continue
            bot_delta = datetime.datetime.utcnow() - self.bot.uptime
            msg = 'Uptime: {}'.format(cf.humanize_timedelta(timedelta=bot_delta))
            ping = str(round(self.bot.latency * 1000, 2))
            url = self.url.format(msg=msg, ping=ping)
            try:
                async with httpx.AsyncClient(**self.http_options) as client:
                    r = await client.get(url)
                    r.raise_for_status()
            except Exception as error:
                log.exception(error)
