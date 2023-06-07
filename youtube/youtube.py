import asyncio
import datetime
import discord
import httpx
import json
import logging
import xmltodict
import redis.asyncio as redis
from bs4 import BeautifulSoup
from typing import Optional, Union, Dict, List, Any

from discord.ext import tasks
from redbot.core import app_commands, commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.youtube')


class YouTube(commands.Cog):
    """Carl's YouTube Cog"""

    http_options = {'follow_redirects': True, 'timeout': 10}

    global_default = {
        'channels': [],
        'videos': {},
    }
    channel_default = {
        'channels': {},
    }

    channel = 'red.youtube'

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
        self.sub_bub_task.start()
        self.poll_new_videos.start()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.sub_bub_task.cancel()
        self.poll_new_videos.cancel()
        if self.loop and not self.loop.cancelled():
            self.loop.cancel()
        if self.pubsub:
            await self.pubsub.close()

    async def main_loop(self):
        await self.bot.wait_until_ready()
        log.info('%s: Start Main Loop', self.__cog_name__)
        log.info('Listening on PubSub Channel: %s', self.channel)
        await self.pubsub.subscribe(self.channel)
        while self is self.bot.get_cog('YouTube'):
            message = await self.pubsub.get_message(timeout=None)
            # log.debug('message: %s', message)
            if message:
                await self.process_message(message)
            await asyncio.sleep(0.01)

    async def process_message(self, message: dict) -> None:
        try:
            data = json.loads(message['data'].decode('utf-8'))
            if 'new' in data['requests']:
                asyncio.create_task(self.process_new(data))
            resp = {'success': True, 'message': '202'}
            pr = await self.redis.publish(data['channel'], json.dumps(resp, default=str))
            log.debug('pr: %s', pr)

        except Exception as error:
            log.error('Exception Processing Message')
            log.exception(error)

    async def process_new(self, raw_data):
        log.debug('Start: process_new')
        if isinstance(raw_data['feed']['entry'], dict):
            entries = [raw_data['feed']['entry']]
        else:
            entries = raw_data['feed']['entry']

        channels = await self.config.channels()
        all_channels = await self.config.all_channels()
        for entry in reversed(entries):
            log.debug('-'*40)
            name = entry['author']['name'] if 'name' in entry['author'] else None
            log.debug('name: %s', name)
            yt_video_id = entry['yt:videoId']
            log.debug('yt_video_id: %s', yt_video_id)
            yt_channel_id = entry['yt:channelId']
            log.debug('yt_channel_id: %s', yt_channel_id)
            if yt_channel_id not in channels:
                log.warning('----- CHANNEL NOT CONFIGURED -----')
                continue
            all_videos = await self.config.videos()
            if yt_video_id in all_videos[yt_channel_id]:
                log.warning('----- VIDEO ALREADY PROCESSED -----')
                continue
            all_videos[yt_channel_id].append(yt_video_id)
            await self.config.videos.set(all_videos)
            url = entry['link']['@href']
            log.debug('url: %s', url)
            # name = entry['author']['name']
            # log.debug('name: %s', name)
            message = f'**{name}** - {url}'
            log.debug('message: %s', message)
            for chan_id, yt_channels in await AsyncIter(all_channels.items(), delay=2, steps=10):
                if yt_channel_id in yt_channels['channels']:
                    channel: discord.TextChannel = self.bot.get_channel(chan_id)
                    if not channel:
                        log.warning('404: Deleting Channel Config: %s: %s', chan_id, yt_channels)
                        await self.config.channel_from_id(int(chan_id)).clear()
                        continue
                    await channel.send(message)
            log.debug('-'*40)
        log.debug('Finish: process_new')

    @tasks.loop(time=datetime.time(hour=18, minute=0, tzinfo=datetime.timezone.utc))
    async def sub_bub_task(self):
        log.info('%s: Sub Bub Task - Start', self.__cog_name__)
        data: list = await self.config.channels()
        log.debug(data)
        for chan in data:
            await self.sub_to_channel(chan)
            await asyncio.sleep(1.0)
        log.info('%s: Sub Bub Task - Finish', self.__cog_name__)

    @tasks.loop(minutes=15.0)
    async def poll_new_videos(self):
        await self.update_channels_list()
        log.debug('-'*40)
        log.info('%s: Poll Videos Task - Start', self.__cog_name__)
        channels: list = await self.config.channels()  # [channel_id]
        for channel_id in channels:
            log.debug('channel_id: %s', channel_id)
            all_videos:  Dict[str, list] = await self.config.videos()  # 'channel_id': [video_id]
            video_feeds: Dict[str, dict] = await self.get_feed_videos(channel_id, True)  # 'video_id': {entry}
            for video_id, entry in reversed(video_feeds.items()):
                # log.debug('video_id: %s', video_id)  # 'video_id'
                # log.debug('entry: %s', entry)  # {entry}
                if video_id not in all_videos[channel_id]:
                    log.debug('FOUND NEW VIDEO: %s - %s', channel_id, video_id)
                    data = {'feed': {'entry': entry}}
                    await self.process_new(data)
            # await asyncio.sleep(1.0)
            # log.debug('yt:videoId: %s', entry['yt:videoId'])
            # for video in all_videos[channel_id]:
            #     if video not in video_feeds[channel_id]:
            #         log.debug('Found New Video: %s', video)
            #         all_videos[channel_id].append(video)
            # log.debug('all_videos: %s', all_videos)
        log.info('%s: Poll Videos Task - Finish', self.__cog_name__)
        log.debug('-'*40)

    # @tasks.loop(minutes=60)
    async def update_channels_list(self):
        log.info('%s: Update Chan - Start', self.__cog_name__)
        new_channels = []
        all_channels: dict = await self.config.all_channels()
        log.debug('all_channels: %s', all_channels)
        for _, chans in all_channels.items():
            for chan, name in chans['channels'].items():
                if chan not in new_channels:
                    new_channels.append(chan)
        before = await self.config.channels()
        log.debug('before: %s', before)
        await self.config.channels.set(new_channels)
        log.debug('new_channels: %s', new_channels)
        log.info('%s: Update Chan - Finish', self.__cog_name__)

    @commands.hybrid_group(name='youtube', aliases=['yt'],
                           description='Options for manging YouTube')
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _yt(self, ctx: commands.Context):
        """Options for manging YouTube"""

    @_yt.command(name='add', aliases=['a'],
                 description='Add one or more YouTube channels to current channel')
    @app_commands.describe(names='Name or Names of YouTube Channel(s) to add')
    @commands.max_concurrency(1, commands.BucketType.default)
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _yt_add(self, ctx: commands.Context, *, names):
        """Add one or more YouTube channels to current channel"""
        await ctx.defer()
        log.debug('names: %s', names)
        names_split = names.replace(',', ' ').split()
        names_split = [x.lstrip('@') for x in names_split]
        log.debug('names_split: %s', names_split)
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
            # r = await self.sub_to_channel(cid)
            if cid not in chan_conf:
                chan_conf: dict = await self.config.channel(ctx.channel).channels()
                chan_conf.update(chan)
                await self.config.channel(ctx.channel).channels.set(chan_conf)
        all_channels: list = await self.config.channels()
        for chan in chan_data:
            cid = list(chan.keys())[0]
            if cid not in all_channels:
                r = await self.sub_to_channel(cid)
                if not r.is_success:
                    continue  # TODO: Process Error
                all_channels: list = await self.config.channels()
                all_channels.append(cid)
                await self.config.channels.set(all_channels)
                await asyncio.sleep(0.1)
        await ctx.send(f'✅ Added YouTube Channels: **{cf.humanize_list(names_split)}** '
                       f'to Discord Channel: `{ctx.channel.name}`', ephemeral=True, delete_after=60)

    @_yt.command(name='remove', aliases=['r'],
                 description='Remove all YouTube Channels from the Current Channel')
    @commands.max_concurrency(1, commands.BucketType.default)
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _yt_remove(self, ctx: commands.Context):
        """Remove all YouTube Channels from the Current Channel"""
        await ctx.defer()
        channels = await self.config.channel(ctx.channel).channels()
        log.debug('channels: %s', channels)
        await self.config.channel(ctx.channel).clear()
        clist = list(channels.values()) if channels else 'None'
        await ctx.send(f'All Channels Removed from This Channel: {clist}',
                       ephemeral=True, delete_after=60)

    @_yt.command(name='status', aliases=['s', 'settings'],
                 description='Show all configured YouTube Channels')
    @commands.max_concurrency(1, commands.BucketType.default)
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _yt_status(self, ctx: commands.Context):
        """Get YouTube status."""
        await ctx.defer()
        all_channels: dict = await self.config.all_channels()
        guild_channel_ids = [channel.id for channel in ctx.guild.text_channels]
        chans = []
        for chan_id, yt_channels in await AsyncIter(all_channels.items(), delay=10, steps=5):
            log.debug('chan_id: %s', chan_id)
            log.debug('yt_channels: %s', yt_channels['channels'])
            if chan_id in guild_channel_ids:
                chan: discord.TextChannel = ctx.guild.get_channel(chan_id)
                chans.append(f'{chan.mention}')
                # clist = list(yt_channels["channels"].values())
                for cid, name in yt_channels['channels'].items():
                    chans.append(f'- {name}: <https://www.youtube.com/channel/{cid}>')
        if not chans:
            await ctx.send('⛔ No configurations found.', ephemeral=True, delete_after=15)
            return
        chans_str = '\n'.join(chans)
        await ctx.send(f'YouTube Configurations:\n{chans_str}', ephemeral=True, delete_after=300)

    # @_yt.command(name='test', aliases=['t'],
    #              description='Super Powerful Test Command. Do NOT Use!')
    # @commands.max_concurrency(1, commands.BucketType.default)
    # @commands.guild_only()
    # @commands.is_owner()
    # async def _yt_test(self, ctx: commands.Context):
    #     """Super Powerful Test Command. Do NOT Use!"""
    #     await ctx.defer()
    #     log.debug('-'*40)
    #     channels = await self.config.channels()
    #     log.debug('channels: %s', channels)
    #     all_videos = await self.config.videos()
    #     log.debug('all_videos: %s', all_videos)
    #     # await self.sub_bub_task()
    #     # await ctx.send('Pub Done, Bub.')
    #     # log.debug('-'*40)
    #     # await self.update_channels_list()
    #     # await ctx.send('Update Done, Bub.')
    #     # log.debug('-'*40)
    #     # await self.poll_new_videos()
    #     # await ctx.send('Poll Done, Bub.')
    #     log.debug(str(datetime.datetime.now()))
    #     await ctx.send(str(datetime.datetime.now()))

    async def sub_to_channel(self, channel_id: str, mode: str = 'subscribe') -> httpx.Response:
        log.debug('sub_to_channel: %s', channel_id)
        if not self.callback_url:
            raise ValueError('self.callback_url Not Defined')
        topic_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
        all_videos = await self.config.videos()
        if channel_id not in all_videos:
            video_list = await self.get_feed_videos(channel_id)
            all_videos[channel_id] = video_list
            await self.config.videos.set(all_videos)
        data = {
            'hub.callback': self.callback_url,
            'hub.topic': topic_url,
            'hub.verify': 'async',
            'hub.mode': mode,
            'hub.verify_token': '',
            'hub.secret': '',
            'hub.lease_numbers': '',
        }
        url = 'https://pubsubhubbub.appspot.com/subscribe'
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url, data=data)
            r.raise_for_status()
        log.debug('r.status_code: %s', r.status_code)
        return r

    async def get_feed_videos(self, channel_id, as_dict=False) -> Union[list, dict]:
        topic_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(topic_url)
            r.raise_for_status()
        log.debug('r.status_code: %s', r.status_code)
        feed = xmltodict.parse(r.text)
        if as_dict:
            video_data = {}
            for entry in feed['feed']['entry']:
                video_data[entry['yt:videoId']] = entry
            return video_data
        else:
            video_list = []
            for entry in feed['feed']['entry']:
                video_list.append(entry['yt:videoId'])
            return video_list

    async def get_channel_data(self, name: str) -> Optional[dict]:
        try:
            log.debug('name: %s', name)
            url = f'https://www.youtube.com/@{name}'
            log.debug('url: %s', url)
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url)
                r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            meta_tag = soup.find('meta', itemprop='identifier')
            channel_id = meta_tag['content']
            log.debug('channel_id: %s', channel_id)
            return {channel_id: name}
        except Exception as error:
            log.debug(error)
            return None
