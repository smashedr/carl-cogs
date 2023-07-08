import discord
import httpx
import ipaddress
import logging
import os
import pathlib
import re
import shutil
import socket
import sys
import whois
from io import BytesIO, StringIO
from playwright.async_api import async_playwright
from typing import Any, Dict, List, Optional

from redbot.core import commands
from redbot.core.utils import chat_formatting as cf

from .functions import verbose_ping

log = logging.getLogger('red.webtools')


class Webtools(commands.Cog):
    """Carl's Webtools"""

    videos_path = '/data/videos'
    playwright_path = '/data/playwright'
    bot_data = f"/data/{os.environ['BOT_NAME']}"
    video_size = {'width': 1280, 'height': 720}
    ip_urls = {
        'IPLocation': 'https://iplocation.io/ip/{ip}',
        'WhatIS MyIPAddress': 'https://whatismyipaddress.com/ip/{ip}',
        'WHOIS IPLocation': 'https://iplocation.io/ip-whois-lookup/{ip}',
        'WHOIS DNSChecker': 'https://dnschecker.org/ip-whois-lookup.php?query={ip}',
        'WHOIS ARIN': 'https://search.arin.net/rdap/?query={ip}',
    }
    http_options = {
        'follow_redirects': False,
        'timeout': 6,
    }
    chrome_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/113.0.0.0 Safari/537.36')

    def __init__(self, bot):
        self.bot = bot
        self.cog_dir = pathlib.Path(__file__).parent.resolve()

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('Recursively Removing Videos Path: %s', self.videos_path)
        shutil.rmtree(self.videos_path)
        if not os.path.exists(self.videos_path):
            log.info('Creating Videos Path: %s', self.videos_path)
            os.mkdir(self.videos_path)
        if not os.path.exists(self.playwright_path):
            log.info('Creating Playwright Path: %s', self.playwright_path)
            os.mkdir(self.playwright_path)
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

    @commands.command(name='whois', aliases=['who'])
    async def whois_command(self, ctx: commands.Context, hostname: str):
        await ctx.typing()
        hostname = hostname.strip('`*')
        log.debug('hostname: %s', hostname)
        w = whois.whois(hostname)
        url = f'https://mxtoolbox.com/SuperTool.aspx?action=whois%3a{hostname}'
        content = f'<{url}>\n{cf.box(w)}'
        await ctx.send(content)

    @commands.command(name='host', aliases=['nslookup'])
    async def host_command(self, ctx: commands.Context, hostname: str):
        await ctx.typing()
        hostname = hostname.strip('`*')
        try:
            if re.match(r'^([0-9]{1,3}\.){3}[0-9]{1,3}$', hostname):
                result, _, _ = socket.gethostbyaddr(hostname)
            else:
                result = socket.gethostbyname(hostname)
            if result:
                await ctx.send(f'**{hostname}:** `{result}`')
            else:
                await ctx.send(f'⛔ No result for: `{hostname}:`')
        except Exception as error:
            log.error(error)
            await ctx.send(f'⛔ Error: `{error}`')

    @commands.command(name='ping')
    async def ping_command(self, ctx: commands.Context, hostname: str):
        await ctx.typing()
        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = StringIO()
            await verbose_ping(hostname, timeout=2)
            sys.stdout = old_stdout
            value = mystdout.getvalue()
            await ctx.send(cf.box(text=value))
        except Exception as error:
            log.error(error)
            await ctx.send(f'⛔ Error: `{error}`')

    @commands.command(name='curl', aliases=['wget'])
    async def curl_command(self, ctx: commands.Context, url: str):
        await ctx.typing()
        if not re.search(r'^[a-zA-Z]+://', url):
            url = 'https://' + url
        try:
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url)
        except Exception as error:
            log.error(error)
            return await ctx.send(f'⛔ Error: `{error}`')
        if 100 <= r.status_code <= 399:
            color = discord.Color.green()
            status = f'✅ {r.status_code}'
            try:
                text = cf.box(r.json()[:2020], lang='json')
            except Exception as error:
                log.debug(error)
                text = cf.box(r.text[:2020], lang='plain')
        else:
            color = discord.Color.red()
            status = f'⛔ {r.status_code}'
            text = cf.box(r.text[:2020], lang='plain')
        embed = discord.Embed(
            title=url,
            url=url,
            color=color,
            description='**Text**\n' + text,
        )
        embed.set_author(name=status)
        embed.add_field(name='Headers', value=cf.box(r.headers))
        await ctx.send(embed=embed)

    @commands.command(name='ipinfo', aliases=['ip', 'ipaddr', 'ipaddress', 'geo'])
    async def ipinfo_command(self, ctx: commands.Context, ip_address: str):
        await ctx.typing()
        try:
            if not re.match(r'^([0-9]{1,3}\.){3}[0-9]{1,3}$', ip_address):
                ip_address, _, _ = socket.gethostbyaddr(ip_address)
            ip = ipaddress.ip_address(ip_address)
            data = await self.get_ip_data(ip.compressed)
            log.debug('data: %s', data)
            description = (
                f"**Country**: {data['country_name']} - {data['country']}/{data['country_code']}\n"
                f"**Region**: {data['region']} - {data['region_code']} / {data['continent_code']}\n"
                f"**City**: {data['city']} / {data['region_code']}\n"
                f"**Lat/Lon**: {data['latitude']} / {data['longitude']}\n"
                f"**Org/ASN**: {data['org']} / {data['asn']}\n"
                f"**Timezone**: {data['timezone']}\n"
            )
            locations = []
            for name, url in self.ip_urls.items():
                if 'WHOIS' in name:
                    continue
                locations.append(f'[{name}]({url.format(ip=ip_address)})')
            description = description.strip() + '\n\n**IP Location Links**\n'
            description += ' | '.join(locations)
            whois = []
            for name, url in self.ip_urls.items():
                if 'WHOIS' not in name:
                    continue
                name = name.replace('WHOIS', '').strip()
                whois.append(f'[{name}]({url.format(ip=ip_address)})')
            description = description.strip() + '\n\n**IP Whois Links**\n'
            description += ' | '.join(whois)
            embed = discord.Embed(
                title=data['ip'],
                description=description,
                color=discord.Color.dark_blue(),
            )
            await ctx.send(embed=embed)

        except Exception as error:
            log.error(error)
            await ctx.send(f'⛔ Error: `{error}`')

    async def get_ip_data(self, ip) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(f'https://ipapi.co/{ip}/json/')
                r.raise_for_status()
            if 'error' in r.json():
                log.debug(r.json())
                return None
            return r.json()
        except Exception as error:
            log.error(error)
            return None

    @commands.command(name='checksite', aliases=['cs', 'check'])
    @commands.cooldown(3, 20, commands.BucketType.user)
    @commands.max_concurrency(1, commands.BucketType.default)
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
            files: List[discord.File] = []
            async with async_playwright() as p:
                for browser_type in [p.chromium, p.firefox]:
                    extra_kwargs = {}
                    await ss.edit(content=f'⌛ Generating {shot_type}: '
                                          f'{browser_type.name.title()}')
                    async with ctx.typing():
                        try:
                            if video:
                                extra_kwargs = {
                                    'record_video_size': self.video_size,
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
            if video:
                for f in files:
                    log.debug('Deleting: %s', f.fp.name)
                    os.remove(f.fp.name)
        except Exception as error:
            log.exception(error)
            await msg.delete()
            await ctx.send(str(error))
