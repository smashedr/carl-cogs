import asyncio
import discord
import httpx
import json
import logging
import re
import redis.asyncio as redis
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from typing import Optional, Union, Dict, Any

from redbot.core import commands, app_commands, Config
from redbot.core.bot import Red
from redbot.core.utils import AsyncIter

from .converters import CarlChannelConverter

log = logging.getLogger('red.dayinhistory')


class DayInHistory(commands.Cog):
    """Carl's This Day In History Cog"""

    base_url = 'https://www.history.com'
    history_url = f'{base_url}/this-day-in-history'
    embed_color = 0xF1C40F  # Color for embed
    send_hour_utc = 20  # Auto post at this hour
    sleep_sec = 60*10  # Must be less than 1 hour
    cache_days = 7  # Must be less than 1 hour

    global_default = {
        'last': None,
    }
    guild_default = {
        'channel': 0,
    }

    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(**self.global_default)
        self.config.register_guild(**self.guild_default)
        self.loop: Optional[asyncio.Task] = None
        self.client: Optional[redis.Redis] = None

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
        self.loop = asyncio.create_task(self.history_loop())
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    async def history_loop(self):
        log.info('%s: Start Main Loop', self.__cog_name__)
        while self is self.bot.get_cog('DayInHistory'):
            log.info(f'Sleeping for {self.sleep_sec} seconds...')
            await asyncio.sleep(self.sleep_sec)
            now = datetime.now()
            current_time = now.time()
            if current_time.hour != self.send_hour_utc:
                log.debug('%s != %s', current_time.hour, self.send_hour_utc)
                continue
            last = await self.config.last()
            if last:
                last = datetime.fromisoformat(last)
                if last.day == now.day:
                    log.debug('%s == %s', last.day, now.day)
                    continue

            log.debug('START')
            await self.config.last.set(now.isoformat())
            log.debug('config.last.set(now.isoformat())')
            all_guilds: dict = await self.config.all_guilds()
            log.debug('all_guilds: %s', all_guilds)
            for guild_id, data in await AsyncIter(all_guilds.items()):
                log.debug('guild_id: %s', guild_id)
                if not data['channel']:
                    continue
                guild: discord.Guild = self.bot.get_guild(guild_id)
                channel: discord.TextChannel = guild.get_channel(data['channel'])
                data: Dict[str, Any] = await self.get_history(now)
                em = discord.Embed.from_dict(data)
                await channel.send(embed=em)
                log.debug('sleep 5')
                await asyncio.sleep(5)
            log.debug('DONE')

    @commands.hybrid_group(name='history', aliases=['dayinhistory', 'thisdayinhistory'],
                           description='Today In History in Discord Commands')
    async def history(self, ctx: commands.Context):
        """Today In History in Discord Commands"""

    @history.command(name='post', aliases=['p'],
                     description="Post Today's history, or a specific day, in Current Channel")
    @app_commands.describe(date='Date of History to Get, Example: 9-11')
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.channel)
    async def history_post(self, ctx: commands.Context, *, date: Optional[str]):
        """Post Today's history, or a specific day, in Current Channel"""
        # TODO: Make this a function
        dt = datetime.now()
        if date:
            log.debug('date: %s', date)
            split = re.split('/|-| ', date)
            log.debug('split: %s', split)
            str_date = f"{split[0]}-{split[1]}"
            log.debug('str_date: %s', str_date)
            try:
                dt = datetime.strptime(str_date, '%m-%d')
            except:
                msg = '\U000026D4 Error processing `date`. Example: **9-11**'
                await ctx.send(msg, ephemeral=True, delete_after=10)  # ⛔
                return
        view = HistoryView(self, ctx.author)
        await view.send_initial_message(ctx, dt)

    @history.command(name='show', aliases=['s'],
                     description="Show Today's history, or a specific day, to You Only")
    @app_commands.describe(date='Date of History to Get, Example: 9-11')
    async def history_show(self, ctx: commands.Context, *, date: Optional[str]):
        """Show Today's history, or a specific day, to You Only"""
        # TODO: Make this a function
        dt = datetime.now()
        if date:
            log.debug('date: %s', date)
            split = re.split('/|-| ', date)
            log.debug('split: %s', split)
            str_date = f"{split[0]}-{split[1]}"
            log.debug('str_date: %s', str_date)
            try:
                dt = datetime.strptime(str_date, '%m-%d')
            except:
                msg = '\U000026D4 Error processing `date`. Example: **9-11**'
                await ctx.send(msg, ephemeral=True, delete_after=10)  # ⛔
                return
        view = HistoryView(self, ctx.author)
        await view.send_initial_message(ctx, dt, ephemeral=True)

    @history.command(name='channel', aliases=['c'],
                     description='Admin Only: Set Channel for Auto Posting History Daily')
    @app_commands.describe(channel='Channel to Post History Too')
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    @commands.admin()
    async def history_channel(self, ctx: commands.Context, channel: Optional[CarlChannelConverter] = None):
        """Admin Only: Set Channel for Auto Posting History Daily"""
        channel: discord.TextChannel
        log.debug('vt_channel')
        if not channel:
            await self.config.guild(ctx.guild).channel.set(0)
            await ctx.send(f'\U00002705 Disabled. Specify a channel to Enable.', ephemeral=True)  # ✅
            return

        log.debug('channel: %s', channel)
        log.debug('channel.type: %s', channel.type)
        if not str(channel.type) == 'text':
            await ctx.send('\U000026D4 Channel must be a Text Channel.', ephemeral=True)  # ⛔
            return

        await self.config.guild(ctx.guild).channel.set(channel.id)
        msg = f'\U00002705 Will post daily history in channel: {channel.name}'  # ✅
        await ctx.send(msg, ephemeral=True)

    async def get_history(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        log.info('get_history')
        now = datetime.now()
        if not date:
            date = now
        data = json.loads(await self.client.get(f'history:{date.strftime("%m%d")}') or '{}')
        if data:
            log.debug('--- cache call ---')
            return data
        log.debug('--- remote call ---')
        http_options = {'follow_redirects': True, 'timeout': 30}
        day_url = f"{self.history_url}/day/{date.strftime('%B-%-d').lower()}"
        log.debug('day_url: %s', day_url)
        async with httpx.AsyncClient(**http_options) as client:
            r = await client.get(day_url)
        if not r.is_success:
            r.raise_for_status()
        html = r.content.decode('utf-8')
        if not html:
            raise Exception('r.content is None')
        soup = BeautifulSoup(html, 'html.parser')
        a_tag = soup.find('a', {'class': 'tdih-featured__title'})
        log.debug('a_tag: %s', a_tag)
        path = a_tag['href']
        log.debug('path: %s', path)
        feat_url = f"{self.base_url}{path}"
        log.debug('feat_url: %s', feat_url)
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
        today_url = f"{self.history_url}/day/{now.strftime('%B-%-d').lower()}"
        description = (f"**Headline: {title}**\n"
                       f"{description}  [read more...]({feat_url})\n"
                       f"**[View Today's History]({today_url})**")
        data = {
            'title': f'This Day in History - {date.strftime("%B %-d")}',
            'url': day_url,
            'description': description,
            'color': self.embed_color,
            'image': {
                'url': image_url,
            },
            'footer': {
                'text': 'This Day in Discord',
                'icon_url': 'https://www.history.com/assets/images/history/favicon.ico',
            },
            'timestamp': date.isoformat(),
        }
        await self.client.setex(
            f'history:{date.strftime("%m%d")}',
            timedelta(days=self.cache_days),
            json.dumps(data),
        )
        return data


class HistoryView(discord.ui.View):
    """Embeds View"""
    def __init__(self, cog,
                 author: Union[int, discord.Member, discord.User],
                 timeout: int = 60*60*2):
        self.cog: DayInHistory = cog
        self.user_id: int = author.id if hasattr(author, 'id') else int(author)
        self.message: Optional[discord.Message] = None
        self.date: Optional[datetime] = None
        self.ephemeral: bool = False
        self.owner_only_sec: int = 120
        self.created_at = datetime.now()
        super().__init__(timeout=timeout)

    async def send_initial_message(self, ctx, date, ephemeral: bool = False, **kwargs) -> discord.Message:
        self.date = date
        self.ephemeral = ephemeral
        data = await self.cog.get_history(self.date)
        embed = discord.Embed.from_dict(data)
        self.message = await ctx.send(view=self, embed=embed, ephemeral=self.ephemeral, **kwargs)
        return self.message

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            return True
        td = datetime.now() - self.created_at
        if td.seconds >= self.owner_only_sec:
            return True
        remaining = self.owner_only_sec - td.seconds
        msg = (f"\U000026D4 The creator has control for {remaining} more seconds...\n"
               f"You can create your own response with the `/history` command.")  # ⛔
        await interaction.response.send_message(msg, ephemeral=True, delete_after=10)
        return False

    async def on_timeout(self):
        for child in self.children:
            child.style = discord.ButtonStyle.gray
            child.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label='Prev', style=discord.ButtonStyle.green)
    async def prev_button(self, interaction, button):
        self.date = self.date - timedelta(days=1)
        data = await self.cog.get_history(self.date)
        embed = discord.Embed.from_dict(data)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label='Next', style=discord.ButtonStyle.green)
    async def next_button(self, interaction, button):
        self.date = self.date + timedelta(days=1)
        data = await self.cog.get_history(self.date)
        embed = discord.Embed.from_dict(data)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label='Delete', style=discord.ButtonStyle.red)
    async def delete_button(self, interaction, button):
        if not interaction.user.id == self.user_id:
            msg = ("\U000026D4 Looks like you didn't create this response.\n"
                   f"You can create your own response with the `/history` command.")  # ⛔
            await interaction.response.send_message(msg, ephemeral=True, delete_after=10)
            return
        await interaction.message.delete()
        await interaction.response.send_message('\U00002705 Your wish is my command!',
                                                ephemeral=True, delete_after=10)  # ✅
