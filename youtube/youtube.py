import asyncio
import discord
import httpx
import json
import logging
import redis.asyncio as redis
from bs4 import BeautifulSoup
from typing import Optional, Union, Dict, Any, List

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils import chat_formatting as cf

from .converters import CarlChannelConverter

log = logging.getLogger('red.youtube')


class YouTube(commands.Cog):
    """Carl's YouTube Cog"""

    global_default = {
        'channels': [],
    }

    guild_default = {
        'channels': {},
        'channel': 0,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(**self.global_default)
        self.config.register_guild(**self.guild_default)
        self.loop: Optional[asyncio.Task] = None
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.callback_url: Optional[str] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)

        # yt_data = await self.bot.get_shared_api_tokens('youtube')
        # if not yt_data['url']:
        #     log.info('YouTube Callback URL Not Set! Use: [p]youtube url')
        # else:
        #     self.callback_url = yt_data['url']
        self.callback_url = 'https://intranet.cssnr.com/youtube/'

        r_data = await self.bot.get_shared_api_tokens('redis')
        self.redis = redis.Redis(
            host=r_data['host'] if 'host' in r_data else 'redis',
            port=int(r_data['port']) if 'port' in r_data else 6379,
            db=int(r_data['db']) if 'db' in r_data else 0,
            password=r_data['pass'] if 'pass' in r_data else None,
        )
        await self.redis.ping()
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        self.loop = asyncio.create_task(self.main_loop())
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.loop.cancel()

    async def main_loop(self):
        await self.bot.wait_until_ready()
        log.info('%s: Start Main Loop', self.__cog_name__)
        channel = 'red.youtube'
        log.info('Listening PubSub Channel: %s', channel)
        await self.pubsub.subscribe(channel)
        while self is self.bot.get_cog('Captcha'):
            message = await self.pubsub.get_message(timeout=None)
            log.debug('message: %s', message)
            if message:
                await self.process_message(message)
            await asyncio.sleep(0.01)

    async def process_message(self, message: dict) -> None:
        try:
            data = json.loads(message['data'].decode('utf-8'))
            log.debug('data: %s', data)

            channel = data['channel']
            log.debug('channel: %s', channel)

            requests = data['requests']
            log.debug('requests: %s', requests)

            # guild: discord.Guild = self.bot.get_guild(int(data['guild']))
            # log.debug('guild: %s', guild)
            #
            # user_id = data['user']
            # log.debug('user_id: %s', user_id)
            # member: discord.Member = await guild.fetch_member(int(user_id))

            resp = {'success': True, 'message': 'null'}
            log.debug('resp: %s', resp)
            pr = await self.redis.publish(channel, json.dumps(resp, default=str))
            log.debug('pr: %s', pr)

        except Exception as error:
            log.error('Exception processing message.')
            log.exception(error)

    @commands.group(name='youtube', aliases=['yt'])
    @commands.guild_only()
    @commands.admin()
    async def _yt(self, ctx: commands.Context):
        """Options for manging YouTube."""

    @_yt.command(name='add', aliases=['a'])
    @commands.max_concurrency(1, commands.BucketType.default)
    @commands.guild_only()
    @commands.admin()
    async def _yt_add(self, ctx: commands.Context, channel: str):
        """Add a YouTube channel for notifications."""
        log.debug('channel: %s', channel)

        chan_id = await self.get_channel_data(channel)
        guild_channels: dict = await self.config.guild(ctx.guild).channels()
        if chan_id in guild_channels:
            await ctx.send(f'⛔ Channel already added: {channel}: {chan_id}')
            return
        r = await self.sub_to_channel(chan_id)
        if not r.is_success:
            await ctx.send(f'⛔ Error subscribing to channel: {channel}: {chan_id}\n'
                           f'```{r.content.decode("utf-8").strip()}```')
            return

        all_channels: list = await self.config.channels()
        if chan_id not in all_channels:
            all_channels.append(chan_id)
            await self.config.channels.set(all_channels)
        guild_channels.update({chan_id: channel})
        await self.config.guild(ctx.guild).channels.set(guild_channels)
        await ctx.send(f'✅ Added Channel {channel}: {chan_id}')

    @_yt.command(name='channel', aliases=['c'], description='Set Channel for Auto Posting YouTube Videos')
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    @commands.admin()
    async def _yt_channel(self, ctx: commands.Context, channel: Optional[CarlChannelConverter] = None):
        """Set Channel for Auto Posting YouTube Videos"""
        channel: discord.TextChannel
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

    # @_yt.command(name='enable', aliases=['e', 'on'])
    # async def _yt_enable(self, ctx: commands.Context):
    #     """Enables YouTube."""
    #     role_id = await self.config.guild(ctx.guild).verified()
    #     enabled = await self.config.guild(ctx.guild).enabled()
    #     if not role_id:
    #         await ctx.send('⛔ YouTube role not set. Please set first.')
    #     elif enabled:
    #         await ctx.send('✅ YouTube module already enabled.')
    #     else:
    #         await self.config.guild(ctx.guild).enabled.set(True)
    #         await ctx.send('✅ YouTube module enabled.')
    #
    # @_yt.command(name='disable', aliases=['d', 'off'])
    # async def _yt_disable(self, ctx: commands.Context):
    #     """Disable YouTube."""
    #     enabled = await self.config.guild(ctx.guild).enabled()
    #     if not enabled:
    #         await ctx.send('✅ YouTube module already disabled.')
    #     else:
    #         await self.config.guild(ctx.guild).enabled.set(False)
    #         await ctx.send('✅ YouTube module disabled.')

    @_yt.command(name='status', aliases=['s', 'settings'])
    async def _yt_status(self, ctx: commands.Context):
        """Get YouTube status."""
        config: Dict[str, Any] = await self.config.guild(ctx.guild).all()
        enabled = 'Enabled' if config['channel'] else 'Disabled'
        channel: Optional[discord.TextChannel] = None
        if config['channel']:
            channel = ctx.guild.get_channel(config['channel'])
        names: List[str] = []
        if config['channels']:
            names = [v for k,v in config['channels'].items()]
        out = (
            f'Youtube Settings:\n'
            '```ini\n'
            f'[Status]: {enabled}\n'
            f'[Channel]: {channel}\n'
            f'[Channels]: {cf.humanize_list(names)}'
            '```'
        )
        await ctx.send(out)

    async def sub_to_channel(self, channel_id: str) -> httpx.Response:
        if not self.callback_url:
            raise ValueError('self.callback_url Not Defined')
        url = 'https://pubsubhubbub.appspot.com/subscribe'
        data = {
            'hub.callback': self.callback_url,
            'hub.topic': f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}',
            'hub.verify': 'async',
            'hub.mode': 'subscribe',
            'hub.verify_token': '',
            'hub.secret': '',
            'hub.lease_numbers': '',
        }
        http_options = {'follow_redirects': True, 'timeout': 30}
        async with httpx.AsyncClient(**http_options) as client:
            r = await client.post(url, data=data)
        log.debug('r.status_code: %s', r.status_code)
        log.debug('r.content: %s', r.content)
        if not r.is_success:
            r.raise_for_status()
        return r

    @staticmethod
    async def get_channel_data(name: str) -> Optional[str]:
        try:
            log.debug('name: %s', name)
            url = f'https://www.youtube.com/c/{name}'
            log.debug('url: %s', url)
            http_options = {'follow_redirects': True, 'timeout': 30}
            async with httpx.AsyncClient(**http_options) as client:
                r = await client.get(url)
            if not r.is_success:
                r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            meta_tag = soup.find('meta', itemprop='identifier')
            channel_id = meta_tag['content']
            log.debug('channel_id: %s', channel_id)
            # meta_tag = soup.find('meta', itemprop='name')
            # channel_name = meta_tag['content'].strip('- ')
            # log.debug('channel_name: %s', channel_name)
            # channel_name = channel_name.strip('- ')
            # log.debug('channel_name: %s', channel_name)
            # if channel_name.lower() != name.lower():
            #     log.warning('Error parsing Channel Name')
            #     channel_name = name
            # resp = channel_id, channel_name
            log.debug('channel_id: %s', channel_id)
            return channel_id
        except Exception as error:
            log.debug(error)
            return None
