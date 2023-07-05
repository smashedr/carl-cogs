import discord
import httpx
import os
import logging
import pathlib
import re
from io import BytesIO
from playwright.async_api import async_playwright
from typing import Optional, Dict, List

from redbot.core import commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.miscog')


class Miscog(commands.Cog):
    """Carl's MisCog"""

    videos_path = '/data/videos'
    playwright_path = '/data/playwright'
    bot_data = f"/data/{os.environ['BOT_NAME']}"
    chrome_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/113.0.0.0 Safari/537.36')

    global_default = {
        'recent': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(**self.global_default)
        self.cog_dir = pathlib.Path(__file__).parent.resolve()

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        if not os.path.exists(self.playwright_path):
            log.info('Creating Playwright Path: %s', self.playwright_path)
            os.mkdir(self.playwright_path)
        if not os.path.exists(self.videos_path):
            log.info('Creating Videos Path: %s', self.videos_path)
            os.mkdir(self.videos_path)
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = self.playwright_path
        log.info('PLAYWRIGHT_BROWSERS_PATH: %s', self.playwright_path)
        script = f'{self.bot_data}/cogs/Downloader/lib/playwright/driver/playwright.sh'
        if os.path.isfile(script):
            os.system(f'{script} install')
        else:
            log.error('Playwright Install Script NOT FOUND!')
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message):
        """Listens for Messages"""
        if message.author.bot or not message.content or not message.guild:
            return
        await self.process_basic_auth_message(message)

    @commands.Cog.listener(name='on_message_delete')
    async def on_message_delete(self, message: discord.Message):
        """Listens for Message Deletions"""
        if message.author.bot or not message.content or not message.guild:
            return
        await self.process_basic_auth_delete(message)

    async def process_basic_auth_message(self, message: discord.Message):
        """Basic Auth ON MESSAGE"""
        match = re.search(r'(https?://\S+:\S+@\S+)', message.content)
        if not match:
            return
        reply = await message.reply(cf.box(match.group(1)))
        recent: List[Dict[str, int]] = await self.config.recent()
        recent.insert(0, {str(message.id): reply.id})
        await self.config.recent.set(recent[:50])

    async def process_basic_auth_delete(self, message: discord.Message):
        """Basic Auth ON DELETE"""
        recent: List[Dict[str, int]] = await self.config.recent()
        keys = [list(x.keys())[0] for x in recent]
        if str(message.id) not in keys:
            return
        reply_id: int = [x[str(message.id)] for x in recent if str(message.id) in x][0]
        message: discord.Message = await message.channel.fetch_message(reply_id)
        await message.delete()

    @commands.command(name='checksite', aliases=['cs', 'check'])
    @commands.cooldown(3, 15, commands.BucketType.user)
    async def check_site(self, ctx: commands.Context, url: str,
                         video: Optional[bool], auth: Optional[str]):
        """
        Check status of a <url> with optional <user:pass> or as video <true>.
        Example:
            [p]checksite google.com
            [p]checksite https://video-site.com/ true
            [p]checksite https://secret-site.com/ username:password
        """
        log.debug('video: %s', video)
        mdn_url = 'https://developer.mozilla.org/en-US/docs/Web/HTTP/Status'
        headers = {'user-agent': self.chrome_agent}
        http_options = {
            'follow_redirects': True,
            'verify': False,
            'timeout': 10,
        }
        msg = await ctx.send('⌛ Checking Status...')
        await ctx.typing()

        if auth:
            if ':' not in auth:
                await ctx.send('⛔ Invalid <auth> format. Must be: `user:pass`')
                return

            username, password = auth.split(':')
            basic_auth = {'auth': (username, password)}
        else:
            basic_auth = {}

        url = url.strip('<>')
        if not url.lower().startswith('http'):
            url = f'http://{url}'

        try:
            async with httpx.AsyncClient(**http_options, **basic_auth,
                                         headers=headers) as client:
                log.debug(auth)
                r = await client.head(url)
                if not r.is_success:
                    r = await client.get(url)
        except httpx.InvalidURL:
            await msg.delete()
            await ctx.send(f'❌ Invalid URL: ```{r.url}```')
            return
        except httpx.ConnectTimeout:
            await msg.delete()
            await ctx.send('❌ Connection timeout after 10 seconds...')
            return
        except httpx.HTTPError as error:
            await msg.delete()
            await ctx.send(f'❌ HTTP Error: `{error}`')
            return
        except Exception as error:
            log.info(error)
            await msg.delete()
            await ctx.send(f'❌ Exception: `{error}`')
            return

        if r.status_code > 399:
            content = (f'HTTPX Response: ⛔ **{r.status_code} - {r.reason_phrase}**\n'
                       f'URL: <{r.url}>\nReason: <{mdn_url}/{r.status_code}>')
        else:
            content = f'HTTPX Response: ✅ **{r.status_code}**\nURL: <{r.url}>'
        await msg.edit(content=content)

        shot_type = 'Screenshot' if not video else 'Video'
        ss = await ctx.send(f'⌛ Generating {shot_type}s...')
        try:
            files = []
            async with async_playwright() as p:
                for browser_type in [p.chromium, p.firefox]:
                    extra_kwargs = {}
                    await ss.edit(content=f'⌛ Generating {shot_type}: '
                                          f'{browser_type.name.title()}')
                    async with ctx.typing():
                        try:
                            if video:
                                extra_kwargs = {
                                    'record_video_size': {'width': 1280, 'height': 720},
                                    'record_video_dir': self.videos_path,
                                }
                            browser = await browser_type.launch()
                            if browser_type.name == 'chromium':
                                extra_kwargs['user_agent'] = self.chrome_agent
                            browser = await browser.new_context(
                                **extra_kwargs
                            )
                            page = await browser.new_page()
                            await page.goto(url=str(r.url), timeout=60000)
                            if video:
                                path = await page.video.path()
                                f = discord.File(path, filename=os.path.basename(path))
                                files.append(f)
                            else:
                                result = await page.screenshot()
                                await browser.close()
                                data = BytesIO()
                                data.write(result)
                                data.seek(0)
                                f = discord.File(data, filename=f'{browser_type.name}.png')
                                files.append(f)
                        except Exception as error:
                            log.exception(error)
                            pass

            await ss.edit(content='⌛ Uploading to Discord.')
            await ctx.typing()
            await ctx.send(content=content, files=files)
            await msg.delete()
            await ss.delete()
        except Exception as error:
            log.exception(error)
            await msg.delete()
            await ctx.send(str(error))
