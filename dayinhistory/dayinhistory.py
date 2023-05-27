import asyncio
import discord
import httpx
import json
import logging
import redis.asyncio as redis
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from typing import Optional, Union, Dict, Any

from redbot.core import commands, app_commands, Config
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting as cf

from .converters import CarlChannelConverter

log = logging.getLogger('red.dayinhistory')


class DayInHistory(commands.Cog):
    """Carl's This Day In History Cog"""

    guild_default = {
        'channel': 0,
    }

    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.loop: Optional[asyncio.Task] = None
        self.client: Optional[redis.Redis] = None
        self.base_url = 'https://www.history.com'
        self.history_url = f'{self.base_url}/this-day-in-history'

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('redis')
        self.client = redis.Redis(
            host=data['host'] if 'host' in data else 'redis',
            port=int(data['port']) if 'port' in data else 6379,
            db=int(data['db']) if 'db' in data else 0,
            password=data['pass'] if 'pass' in data else None,
        )
        await self.client.ping()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.hybrid_group(name='dayinhistory', aliases=['history'], description='Today In History in Discord Commands')
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    @commands.admin()
    async def history(self, ctx: commands.Context):
        """Today In History in Discord Commands"""

    @history.command(name='post', description="Post Today's history in Current Channel")
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.channel)
    async def history_post(self, ctx: commands.Context):
        """Post Today's history in Current Channel"""
        data = await self.get_history()
        em = discord.Embed.from_dict(data)
        await ctx.send(embed=em)

    @history.command(name='show', description="Show Today's history to You Only")
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.channel)
    async def history_show(self, ctx: commands.Context):
        """Show Today's history to You Only"""
        data = await self.get_history()
        em = discord.Embed.from_dict(data)
        await ctx.send(embed=em, ephemeral=True)

    @history.command(name='channel', aliases=['c'], description='Set Channel for Auto Posting History Daily')
    @app_commands.describe(channel='Channel to Post History Too')
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    @commands.admin()
    async def history_channel(self, ctx: commands.Context, channel: CarlChannelConverter):
        """Set Channel for Auto Posting History Daily"""
        channel: discord.TextChannel
        log.debug('vt_channel')
        log.debug('channel: %s', channel)
        log.debug('channel.type: %s', channel.type)
        if not str(channel.type) == 'text':
            await ctx.send('\U000026D4 Channel must be a Text Channel.')  # ⛔
            return
        await self.config.guild(ctx.guild).channel.set(channel.id)
        msg = f'\U00002705 Will post daily history in channel: {channel.name}'  # ✅
        await ctx.send(msg, ephemeral=True)

    async def get_history(self) -> Dict[str, Any]:
        log.info('get_history')
        now = datetime.now()
        data = json.loads(await self.client.get(f'history:{now.strftime("%m%d")}') or '{}')
        if data:
            log.debug('--- cache call ---')
            return data

        http_options = {'follow_redirects': True, 'timeout': 30}
        log.info('--- REMOTE CALL ---')
        async with httpx.AsyncClient(**http_options) as client:
            r = await client.get(self.history_url)
        if not r.is_success:
            r.raise_for_status()
        html = r.content.decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        a_tag = soup.find('a', {'class': 'tdih-featured__title'})
        log.debug('a_tag: %s', a_tag)
        path = a_tag['href']
        log.debug('path: %s', path)
        feat_url = f"{self.base_url}{path}"
        log.debug('feat_url: %s', feat_url)
        log.info('--- REMOTE CALL ---')
        async with httpx.AsyncClient(**http_options) as client:
            r = await client.get(feat_url)
        if not r.is_success:
            r.raise_for_status()

        soup = BeautifulSoup(r.content, 'html.parser')

        meta_tag = soup.find('meta', {'name': 'description'})
        description = meta_tag['content']
        log.debug('description: %s', description)

        meta_tag = soup.find('meta', {'property': 'og:title'})
        title = meta_tag.get('content')
        log.debug('title: %s', title)

        meta_tag = soup.find('meta', {'property': 'og:image'})
        image_url = meta_tag.get('content')
        log.debug('image_url: %s', image_url)

        day_url = f"{self.history_url}/day/{now.strftime('%B-%-d').lower()}"
        log.debug('day_url: %s', day_url)

        description = (f"**Headline: {title}**\n"
                       f"{description}  [read more...]({feat_url})\n"
                       f"**[View Today's History]({day_url})**")
        data = {
            'title': f'This Day in History - {now.strftime("%B %-d")}',
            'url': day_url,
            'description': description,
            'color': 0xF1C40F,
            'image': {
                'url': image_url,
            },
            'footer': {
                'text': 'This Day in Discord',
                'icon_url': 'https://www.history.com/assets/images/history/favicon.ico',
            },
            'timestamp': now.isoformat(),
        }
        # TODO: Cache This Shit
        await self.client.setex(
            f'history:{now.strftime("%m%d")}',
            timedelta(hours=24),
            json.dumps(data),
        )
        return data
