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
        os.system(f"/data/{os.environ['BOT_NAME']}/cogs/"
                  f'Downloader/lib/playwright/driver/playwright.sh install')
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message):
        """Listens for Messages"""
        guild: discord.Guild = message.guild
        if message.author.bot or not message.content or not guild:
            return
        match = re.search(r'(https?://\S+:\S+@\S+)', message.content)
        if not match:
            return

        reply = await message.reply(cf.box(match.group(1)))
        recent: List[Dict[str, int]] = await self.config.recent()
        recent.insert(0, {str(message.id): reply.id})
        await self.config.recent.set(recent[:50])

    @commands.Cog.listener(name='on_message_delete')
    async def on_message_delete(self, message: discord.Message):
        """Listens for Message Deletions"""
        guild: discord.Guild = message.guild
        if message.author.bot or not message.content or not guild:
            return
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
                         auth: Optional[str]):
        """
        Check the status of a site at the given <url> with optional <auth>.
        Example:
            [p]checksite google.com
            [p]checksite https://secret-site.com/ username:password
        """
        mdn_url = 'https://developer.mozilla.org/en-US/docs/Web/HTTP/Status'
        headers = {'user-agent': self.chrome_agent}
        http_options = {
            'follow_redirects': True,
            'verify': False,
            'timeout': 10,
        }
        await ctx.message.delete()
        msg = await ctx.send('⌛ Checking Status...')
        await ctx.typing()

        if auth:
            if ':' not in auth:
                await ctx.send('Invalid <auth> format. Must be: `user:pass`')
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
            await ctx.send(f'Invalid URL: ```{r.url}```')
            return
        except httpx.ConnectTimeout:
            await msg.delete()
            await ctx.send('Connection timeout after 10 seconds...')
            return
        except httpx.HTTPError as error:
            await msg.delete()
            await ctx.send(f'HTTP Error: `{error}`')
            return
        except Exception as error:
            log.info(error)
            await msg.delete()
            await ctx.send(f'Exception: `{error}`')
            return

        if r.status_code > 399:
            await msg.delete()
            await ctx.send(f'Response: ⛔ **{r.status_code} - {r.reason_phrase}**\n'
                           f'URL: <{r.url}>\nReason: <{mdn_url}/{r.status_code}>')
            return

        content = f'Response: ✅ **{r.status_code}**\nURL: <{r.url}>'
        await msg.edit(content=content)

        ss = await ctx.send('⌛ Generating Screenshots...')
        try:
            files = []
            async with async_playwright() as p:
                for browser_type in [p.chromium, p.firefox]:
                    async with ctx.typing():
                        # browser_type = p.chromium
                        await ss.edit(content=f'⌛ Generating Screenshot: '
                                              f'{browser_type.name.title()}')
                        await ctx.typing()
                        try:
                            browser = await browser_type.launch()
                            if browser_type.name == 'chromium':
                                browser = await browser.new_context(
                                    user_agent=self.chrome_agent
                                )
                            page = await browser.new_page()
                            await page.goto(url=str(r.url), timeout=60000)
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
            await ctx.send(content=content, files=files)
            await msg.delete()
            await ss.delete()
        except Exception as error:
            log.exception(error)
            await msg.delete()
            await ctx.send(str(error))
