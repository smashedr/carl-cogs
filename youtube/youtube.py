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
        yt_data = await self.bot.get_shared_api_tokens('youtube')
        if not yt_data['callback']:
            log.warning('YouTube Callback URL Not Set! Use: [p]set api')
        else:
            self.callback_url = yt_data['callback']
        log.info('%s: Callback URL: %s', self.__cog_name__, self.callback_url)
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
        await ctx.defer()
        # await self.config.channel(ctx.channel).clear()
        # await ctx.send('clear', ephemeral=True, delete_after=10)
        # return
        log.debug('names: %s', names)
        names_split = names.split()
        names_split = [x.lstrip('@') for x in names_split]
        log.debug('names_split: %s', names_split)
        # clean_names = []
        # for name in names_split:
        #     if name.endswith('/'):
        #         name = name.rstrip('/')
        #     if '/' in name:
        #         name = name.split('/')[-1]
        #     if name.startswith('@'):
        #         name = name.lstrip('@')
        #     clean_names.append(name)
        # log.debug('clean_names: %s', clean_names)
        try:
            chan_data = [await self.get_channel_data(x) for x in names_split]
            if not chan_data or not chan_data[0]:
                await ctx.send(f'⛔ No channels found for one or more passed channels: `{names}`',
                               ephemeral=True, delete_after=15)
                return
        except Exception as error:
            log.debug(error)
            await ctx.send(f'⛔ Error processing one or more passed channels: `{names}`',
                           ephemeral=True, delete_after=15)
            return

        chan_conf: dict = await self.config.channel(ctx.channel).channels()
        log.debug('chan_conf: %s', chan_conf)
        log.debug('chan_data: %s', chan_data)
        for chan in chan_data:
            log.debug('chan: %s', chan)
            cid = list(chan.keys())[0]
            # name = chan[cid]
            if cid not in chan_conf:
                # await self.sub_to_channel(cid)
                chan_conf.update(chan)
                await self.config.channel(ctx.channel).channels.set(chan_conf)
                await asyncio.sleep(0.2)
        all_channels: list = await self.config.channels()
        for chan in chan_data:
            cid = list(chan.keys())[0]
            r = await self.sub_to_channel(cid)
            if cid not in all_channels:
                # r = await self.sub_to_channel(cid)
                # if not r.is_success:
                #     continue  # TODO: Process Error
                all_channels.append(cid)
            await asyncio.sleep(0.2)
        await self.config.channels.set(all_channels)
        await ctx.send(f'✅ Added YouTube Channels: **{cf.humanize_list(names_split)}** '
                       f'to Discord Channel: `{ctx.channel.name}`', ephemeral=True, delete_after=60)

    @_yt.command(name='status', aliases=['s', 'settings'],
                 description='Show all configured YouTube Channels')
    @commands.max_concurrency(1, commands.BucketType.default)
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _yt_status(self, ctx: commands.Context):
        """Get YouTube status."""
        all_channels: dict = await self.config.all_channels()
        guild_channel_ids = [channel.id for channel in ctx.guild.text_channels]
        # chans = []
        # for chan_id, yt_channels in await AsyncIter(all_channels.items(), delay=10, steps=5):
        #     log.debug('chan_id: %s', chan_id)
        #     log.debug('yt_channels: %s', yt_channels['channels'])
        #     if chan_id in guild_channel_ids:
        #         chan: discord.TextChannel = ctx.guild.get_channel(chan_id)
        #         clist = list(yt_channels["channels"].values())
        #         chans.append(f'[{chan.name}]: {cf.humanize_list(clist)}')
        # if not chans:
        #     await ctx.send('⛔ No configurations found.', ephemeral=True, delete_after=15)
        #     return
        #
        # chans_str = '\n'.join(chans)
        # await ctx.send(f'YouTube Configurations:\n```ini\n{chans_str}```', ephemeral=True, delete_after=900)
        chans = []
        for chan_id, yt_channels in await AsyncIter(all_channels.items(), delay=10, steps=5):
            log.debug('chan_id: %s', chan_id)
            log.debug('yt_channels: %s', yt_channels['channels'])
            if chan_id in guild_channel_ids:
                chan: discord.TextChannel = ctx.guild.get_channel(chan_id)
                chans.append(f'{chan.mention}:')
                clist = list(yt_channels["channels"].values())
                for cid, name in yt_channels['channels'].items():
                    chans.append(f'**{name}**: `{cid}`')
                    chans.append(f'- <https://www.youtube.com/@{name}>')
        if not chans:
            await ctx.send('⛔ No configurations found.', ephemeral=True, delete_after=15)
            return
        chans_str = '\n'.join(chans)
        await ctx.send(f'YouTube Configurations:\n{chans_str}', ephemeral=True, delete_after=900)

    async def sub_to_channel(self, channel_id: str, mode: str = 'subscribe') -> httpx.Response:
        log.debug('sub_to_channel: %s', channel_id)
        if not self.callback_url:
            raise ValueError('self.callback_url Not Defined')
        data = {
            'hub.callback': self.callback_url,
            'hub.topic': f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}',
            'hub.verify': 'async',
            'hub.mode': mode,
            'hub.verify_token': '',
            'hub.secret': '',
            'hub.lease_numbers': '',
        }
        url = 'https://pubsubhubbub.appspot.com/subscribe'
        http_options = {'follow_redirects': True, 'timeout': 30}
        async with httpx.AsyncClient(**http_options) as client:
            r = await client.post(url, data=data)
        log.debug('r.status_code: %s', r.status_code)
        return r

    @staticmethod
    async def get_channel_data(name: str) -> Optional[dict]:
        try:
            log.debug('name: %s', name)
            url = f'https://www.youtube.com/@{name}'
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
            return {channel_id: name}
        except Exception as error:
            log.debug(error)
            return None
