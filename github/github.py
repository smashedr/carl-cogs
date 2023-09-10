import asyncio
import datetime
import discord
import json
import httpx
import logging
import redis.asyncio as redis
from typing import Optional, Dict, Any

from discord.ext import tasks
from redbot.core import commands, Config
from redbot.core.utils import can_user_send_messages_in

from .gh import GitHub

log = logging.getLogger('red.github')


class Github(commands.Cog):
    """Carl's Github Cog"""

    channel = 'red.github'
    github_url = 'https://github.com'
    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }
    chrome_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/113.0.0.0 Safari/537.36')
    http_headers = {'user-agent': chrome_agent}
    user_default = {
        'token': None,
        'notifications': {},
        'sent': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_user(**self.user_default)
        self.loop: Optional[asyncio.Task] = None
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.poll_loop.start()
        redis_data: dict = await self.bot.get_shared_api_tokens('redis')
        self.redis = redis.Redis(
            host=redis_data.get('host', 'redis'),
            port=int(redis_data.get('port', 6379)),
            db=int(redis_data.get('db', 0)),
            password=redis_data.get('pass', None),
        )
        await self.redis.ping()
        self.pubsub = self.redis.pubsub(ignore_subscribe_messages=True)
        # self.loop = asyncio.create_task(self.pubsub_loop())
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.poll_loop.cancel()
        if self.loop and not self.loop.cancelled():
            self.loop.cancel()
        if self.pubsub:
            await self.pubsub.close()

    # async def pubsub_loop(self):
    #     await self.bot.wait_until_ready()
    #     log.info('%s: Start: pubsub_loop', self.__cog_name__)
    #     log.info('Listening on PubSub Channel: %s', self.channel)
    #     await self.pubsub.subscribe(self.channel)
    #     while self is self.bot.get_cog('Github'):
    #         log.debug('waiting for message...')
    #         if message := await self.pubsub.get_message(timeout=None):
    #             await self.process_message(message)
    #         await asyncio.sleep(0.01)
    #
    # async def process_message(self, message):
    #     log.debug('----- process_message -----')
    #     log.debug(message)
    #     try:
    #         data = json.loads(message['data'].decode('utf-8'))
    #         log.debug(data)
    #         # check user settings for configurations here
    #         repos = {
    #             'smashedr/test3': (188150516088438785, 'https://intranet.cssnr.com/'),
    #             'django-files/django-files': (228302746011435008, 'https://f-dev.cssnr.com/'),
    #         }
    #         log.debug('repository.full_name: %s', data['repository']['full_name'])
    #         if data['repository']['full_name'] in list(repos.keys()):
    #             await self.process_site_check(data, repos[data['repository']['full_name']])
    #     except Exception as error:
    #         log.warning(error)
    #
    # async def process_site_check(self, data, user_data):
    #     log.debug('channel: %s', user_data[0])
    #     log.debug('url: %s', user_data[1])
    #     channel = self.bot.get_channel(user_data[0])
    #     url = user_data[1]
    #     is_down = await self.wait_for_result(url, False, 120)
    #     if not is_down:
    #         await channel.send('⛔ Site never went down after 120 seconds.')
    #         return log.debug('site never down after 120 seconds')
    #     await channel.send('⚠️ Site found Down - Waiting for Return...')
    #     log.debug('site down - waiting for it to come up')
    #     is_up = await self.wait_for_result(url, True, 300)
    #     if not is_up:
    #         await channel.send('⛔ Site never came back after 300 seconds.')
    #         return log.debug('site never up after 300 seconds')
    #     await channel.send('✅ Site Back UP - We are going to need your firstborn now.')
    #
    # async def wait_for_result(self, url, success: bool, timeout: int):
    #     log.debug('wait_for_result: start')
    #     task = asyncio.create_task(self.check_response(url, success))
    #     try:
    #         log.debug('wait_for_result: try')
    #         return await asyncio.wait_for(task, timeout=timeout)
    #     except asyncio.TimeoutError:
    #         log.debug('wait_for_result: TimeoutError')
    #         task.cancel()
    #         return False
    #
    # async def check_response(self, url, success: bool):
    #     log.debug('check_response: start')
    #     http_options = {'follow_redirects': True, 'timeout': 2}
    #     http_options.update({'headers': self.http_headers})
    #     async with httpx.AsyncClient(**http_options) as client:
    #         while True:
    #             log.debug('check_response: loop')
    #             try:
    #                 r = await client.get(url)
    #                 if r.is_success and success:
    #                     return True
    #                 if not r.is_success and not success:
    #                     return True
    #             except Exception as error:
    #                 log.debug(error)
    #                 pass
    #             await asyncio.sleep(2)

    @tasks.loop(minutes=15.0)
    async def poll_loop(self):
        await self.bot.wait_until_ready()
        log.info('%s: Start Loop: poll_loop', self.__cog_name__)
        dt = datetime.datetime.now() - datetime.timedelta(minutes=15)
        all_users: dict = await self.config.all_users()
        for user_id, data in all_users.items():
            log.debug('user_id: %s', user_id)
            log.debug('data: %s', data)
            await self.process_notifications(user_id, dt, data)
        log.info('%s: Finish Loop: poll_loop', self.__cog_name__)

    async def process_notifications(self, user_id, dt, data):
        log.debug('----- process_notifications -----')
        if not data['notifications']:
            log.debug('no notifications for user_id: %s', user_id)
            return
        ts = dt.isoformat(timespec='seconds') + 'Z'
        log.debug('ts: %s', ts)
        # last: list = await self.config.last()
        gh = GitHub(data['token'])
        notifications = await gh.get_notifications(since=ts)
        log.debug('-'*40)
        log.debug(notifications)
        log.debug('-'*40)
        for notify in notifications:
            log.debug('id: %s', notify['id'])
            # if notify['id'] in last:
            #     continue
            log.debug('repository:full_name: %s', notify['repository']['full_name'])
            if notify['repository']['full_name'] not in data['notifications']:
                continue
            channel_id = data['notifications'][notify['repository']['full_name']]
            await self.send_alert(user_id, channel_id, notify)
            # last.insert(0, notify['id'])
            # await self.config.user(user_id).last.set(last[:50])

    async def send_alert(self, user_id, channel_id, notify):
        log.debug('----- send_alert -----')
        user: discord.User = self.bot.get_user(user_id)
        channel: discord.TextChannel = self.bot.get_channel(channel_id)
        if not can_user_send_messages_in(user, channel):
            log.warning('User %s can not send messages in %s', user.name, channel.name)
            return False
        embed = discord.Embed(
            title=notify['repository']['full_name'],
            url=notify['repository']['html_url'],
            timestamp=datetime.datetime.fromisoformat(notify['updated_at'].rstrip('Z')),
        )
        embed.set_author(
            name=notify['subject']['type'],
            url=notify['subject']['url'],
        )
        # embed.description = (
        #     f"**{notify['subject']['type']}**\n\n"
        #     f"{notify['subject']['title']}"
        # )
        embed.description = notify['subject']['title']
        embed.set_footer(text=notify['repository']['owner']['login'])
        if notify['repository']['owner']['avatar_url']:
            # embed.set_footer(icon_url=notify['repository']['owner']['avatar_url'])
            embed.set_thumbnail(url=notify['repository']['owner']['avatar_url'])
        await channel.send(embed=embed)

    @commands.group(name='github', aliases=['gh'])
    async def _github(self, ctx):
        """Manage Github Options"""

    @_github.command(name='action', aliases=['act'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _github_action(self, ctx: commands.Context, repo: str):
        """Run GitHub Action for owner/repo
        <repo>: `owner/repo` The full name of the repository.
        Example: `django/django`
        """
        log.debug('repo: %s', repo)
        user_conf: Dict[str, Any] = await self.config.user(ctx.author).all()
        if not user_conf['token']:
            view = ModalView(self)
            msg = (f'⛔ No GitHub Access Token found for {ctx.author.mention}\n'
                   f'Click the button to set Access Token.')
            return await ctx.send(msg, view=view, ephemeral=True,
                                  allowed_mentions=discord.AllowedMentions.none())

        if '/' not in repo:
            return await ctx.send('Must be full repository. Ex: `django/django`')

        url = f'https://api.github.com/repos/{repo}/dispatches'
        log.debug('url: %s', url)
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {user_conf['token']}",
        }
        log.debug('headers: %s', headers)
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url, headers=headers, json={"event_type": "webhook"})
        log.debug('r.status_code: %s', r.status_code)
        log.debug('r.content: %s', r.content)
        r.raise_for_status()
        return await ctx.send(f'Build Started: <https://github.com/{repo}/actions>')

    @_github.command(name='add', aliases=['new', 'notification'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _github_add(self, ctx: commands.Context, name: str, channel: Optional[discord.TextChannel]):
        """Add GitHub Notification
        name: The full name of the repository. Ex: `django/django`
        channel: Optional channel to send notifications to
        """
        channel = channel or ctx.channel
        if not can_user_send_messages_in(ctx.author, channel):
            content = f'⛔ You are unable to send messages in channel: {channel.mention}'
            return await ctx.send(content, ephemeral=True, delete_after=120,
                                  allowed_mentions=discord.AllowedMentions.none())
        user_conf: Dict[str, Any] = await self.config.user(ctx.author).all()
        if not user_conf['token']:
            view = ModalView(self)
            msg = (f'⛔ No GitHub Access Token found for {ctx.author.mention}\n'
                   f'Click the button to set Access Token.')
            return await ctx.send(msg, view=view, ephemeral=True,
                                  allowed_mentions=discord.AllowedMentions.none())
        notifications: Dict[str, int] = user_conf['notifications']
        if name in notifications:
            # need to check channels to make sure no duplicates
            # notify = notifications[name]
            content = (f'⛔ There is already an alert setup up for {name}. '
                       f'The ability to send alerts for one repo to multiple '
                       f'channels is a WIP and not yet finished.')
            return await ctx.send(content, ephemeral=True, delete_after=120,
                                  allowed_mentions=discord.AllowedMentions.none())
        notifications[name] = channel.id
        await self.config.user(ctx.author).notifications.set(notifications)
        content = (
            f'✅ Added GitHub notifications for **{name}** to channel {channel.mention}\n'
            f'**IMPORTANT** Make sure you subscribe to notifications for: <{self.github_url}/{name}>'
        )
        await ctx.send(content, ephemeral=True)

    @_github.command(name='list', aliases=['all', 'show', 'view'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _github_list(self, ctx: commands.Context):
        """List GitHub Notifications"""
        notifications: Dict[str, int] = await self.config.user(ctx.author).notifications()
        if not notifications:
            content = f'⛔ No notifications found. Add them with: `{ctx.prefix}github add`'
            return await ctx.send(content, ephemeral=True, delete_after=120,
                                  allowed_mentions=discord.AllowedMentions.none())
        notify_list = []
        for repo, channel_id in notifications.items():
            channel = ctx.guild.get_channel(channel_id)
            notify_list.append(f'{repo} -> {channel.mention}')
        notify = '\n'.join(notify_list)
        content = f'ℹ️ Configured Notifications:\n{notify}'
        await ctx.send(content, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @_github.command(name='token', aliases=['auth', 'access', 'authorization'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _github_token(self, ctx: commands.Context):
        """Set GitHub Access Token"""
        view = ModalView(self)
        content = 'Press the Button to set your Access Token.'
        return await ctx.send(content, view=view, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


class ModalView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label='Set GitHub Access Token', style=discord.ButtonStyle.blurple, emoji='🔐')
    async def set_grafana(self, interaction, button):
        log.debug(interaction)
        log.debug(button)
        modal = DataModal(view=self)
        await interaction.response.send_modal(modal)


class DataModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View):
        super().__init__(title='Set GitHub Access Token')
        self.view = view
        self.access_token = discord.ui.TextInput(
            label='GitHub Access Token',
            placeholder='ghp_xxx',
            style=discord.TextStyle.short,
            max_length=40,
            min_length=40,
        )
        self.add_item(self.access_token)

    async def on_submit(self, interaction: discord.Interaction):
        # discord.interactions.InteractionResponse
        log.debug('ReplyModal - on_submit')
        user: discord.Member = interaction.user
        log.debug('self.access_token.value: %s', self.access_token.value)
        await self.view.cog.config.user(user).token.set(self.access_token.value)
        msg = '✅ GitHub Access Token Updated Successfully...'
        await interaction.response.send_message(msg, ephemeral=True)
