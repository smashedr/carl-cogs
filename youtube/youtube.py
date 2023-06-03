import asyncio
import discord
import httpx
import json
import logging
import redis.asyncio as redis
from bs4 import BeautifulSoup
from typing import Optional, Union, Dict, List, Any

from redbot.core import app_commands, commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.youtube')


class YouTube(commands.Cog):
    """Carl's YouTube Cog"""

    global_default = {
        'channels': [],
    }
    channel_default = {
        'channels': {},
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(**self.global_default)
        self.config.register_channel(**self.channel_default)
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
        if self.loop and not self.loop.cancelled():
            self.loop.cancel()
        if self.pubsub:
            await self.pubsub.close()

    async def main_loop(self):
        await self.bot.wait_until_ready()
        log.info('%s: Start Main Loop', self.__cog_name__)
        channel = 'red.youtube'
        log.info('Listening PubSub Channel: %s', channel)
        await self.pubsub.subscribe(channel)
        while self is self.bot.get_cog('YouTube'):
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

            if 'new' in data['requests']:
                asyncio.create_task(self.process_new(data))
            resp = {'success': True, 'message': '202'}
            pr = await self.redis.publish(channel, json.dumps(resp, default=str))
            log.debug('pr: %s', pr)

        except Exception as error:
            log.error('Exception Processing Message')
            log.exception(error)

    async def process_new(self, raw_data):
        log.debug('Start: process_new: %s', raw_data)
        yt_channel_id = raw_data['feed']['entry']['yt:channelId']
        log.debug('yt_channel_id: %s', yt_channel_id)
        url = raw_data['feed']['entry']['link']['@href']
        log.debug('url: %s', url)
        name = raw_data['feed']['entry']['author']['name']
        log.debug('name: %s', name)
        msg = f'New Video from: **{name}**\n{url}'
        log.debug('msg: %s', msg)

        all_channels = await self.config.all_channels()
        for chan_id, yt_channels in await AsyncIter(all_channels.items(), delay=10, steps=5):
            log.debug('chan_id: %s', chan_id)
            log.debug('yt_channels: %s', yt_channels)
            if yt_channel_id in yt_channels['channels']:
                channel: discord.TextChannel = self.bot.get_channel(chan_id)
                await channel.send(msg)
        log.debug('Finish: process_new')

    @commands.hybrid_group(name='youtube', aliases=['yt'],
                           description='Options for manging YouTube')
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _yt(self, ctx: commands.Context):
        """Options for manging YouTube"""

    @_yt.command(name='add', aliases=['a'],
                 description='Add one or more YouTube channels to auto post in current channel')
    @app_commands.describe(names='Name or Names of YouTube Channel(s) to add, space seperated')
    @commands.max_concurrency(1, commands.BucketType.default)
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _yt_add(self, ctx: commands.Context, *, names):
        """Add one or more YouTube channels to auto post in current channel"""
        log.debug('names: %s', names)
        names_split = names.split(' ')
        # await self.config.channel(discord_channel).clear()
        chan_data = [await self.get_channel_data(x) for x in names_split]
        if not chan_data:
            await ctx.send(f'⛔ Error processing passed channels: `{names}`', ephemeral=True, delete_after=10)
            return

        chan_conf: dict = await self.config.channel(ctx.channel).channels()
        for chan in chan_data:
            cid = list(chan.keys())[0]
            name = chan[cid]
            if cid not in chan_conf:
                chan_conf.update(chan)
                await self.config.channel(ctx.channel).channels.set(chan_conf)
        all_channels: list = await self.config.channels()
        for chan in chan_data:
            cid = list(chan.keys())[0]
            if cid not in all_channels:
                r = await self.sub_to_channel(cid)
                if not r.is_success:
                    continue  # TODO: Process Error
                all_channels.append(cid)
        await self.config.channels.set(all_channels)
        await ctx.send(f'✅ Added YouTube Channels: **{cf.humanize_list(names_split)}** '
                       f'to Discord Channel: `{ctx.channel.name}`', ephemeral=True, delete_after=30)

    @_yt.command(name='status', aliases=['s', 'settings'],
                 description='Show all configured YouTube Channels')
    @commands.max_concurrency(1, commands.BucketType.default)
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _yt_status(self, ctx: commands.Context):
        """Get YouTube status."""
        all_channels = await self.config.all_channels()
        guild_channel_ids = [channel.id for channel in ctx.guild.text_channels]
        chans = []
        for chan_id, yt_channels in await AsyncIter(all_channels.items(), delay=10, steps=5):
            log.debug('chan_id: %s', chan_id)
            log.debug('yt_channels: %s', yt_channels['channels'])
            if chan_id in guild_channel_ids:
                chan = ctx.guild.get_channel(chan_id)
                clist = list(yt_channels["channels"].values())
                chans.append(f'[{chan.name}]: {cf.humanize_list(clist)}')
        if not chans:
            await ctx.send('⛔ No configurations found.', ephemeral=True, delete_after=10)
            return

        chans_str = '\n'.join(chans)
        await ctx.send(f'YouTube Configurations:\n```ini\n{chans_str}```', ephemeral=True, delete_after=120)

    # @_yt.command(name='channel', aliases=['c'], description='Set Channel for Auto Posting YouTube Videos')
    # @commands.max_concurrency(1, commands.BucketType.guild)
    # @commands.guild_only()
    # @commands.admin()
    # async def _yt_channel(self, ctx: commands.Context, channel: Optional[CarlChannelConverter] = None):
    #     """Set Channel for Auto Posting YouTube Videos"""
    #     channel: discord.TextChannel
    #     if not channel:
    #         await self.config.guild(ctx.guild).channel.set(0)
    #         await ctx.send(f'\U00002705 Disabled. Specify a channel to Enable.', ephemeral=True)  # ✅
    #         return
    #
    #     log.debug('channel: %s', channel)
    #     log.debug('channel.type: %s', channel.type)
    #     if not str(channel.type) == 'text':
    #         await ctx.send('\U000026D4 Channel must be a Text Channel.', ephemeral=True)  # ⛔
    #         return
    #
    #     await self.config.guild(ctx.guild).channel.set(channel.id)
    #     msg = f'\U00002705 Will post daily history in channel: {channel.name}'  # ✅
    #     await ctx.send(msg, ephemeral=True)
    #
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

    async def sub_to_channel(self, channel_id: str) -> httpx.Response:
        log.debug('sub_to_channel: %s', channel_id)
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
    async def get_channel_data(name: str) -> Optional[dict]:
        try:
            log.debug('name: %s', name)
            url = f'https://www.youtube.com/c/{name}'
            log.debug('url: %s', url)
            http_options = {'follow_redirects': True, 'timeout': 30}
            async with httpx.AsyncClient(**http_options) as client:
                r = await client.get(url)
            if not r.is_success:
                url = f'https://www.youtube.com/user/{name}'
                log.debug('url: %s', url)
                async with httpx.AsyncClient(**http_options) as client:
                    r = await client.get(url)
                if not r.is_success:
                    r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            meta_tag = soup.find('meta', itemprop='identifier')
            channel_id = meta_tag['content']
            log.debug('channel_id: %s', channel_id)
            return {channel_id: name}
        except Exception as error:
            log.debug(error)
            return None
