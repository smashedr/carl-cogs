import datetime
import discord
import logging
from typing import Optional, Dict, Any

from discord.ext import tasks
from redbot.core import commands, Config
from redbot.core.utils import can_user_send_messages_in

from .gh import GitHub

log = logging.getLogger('red.github')


class Github(commands.Cog):
    """Carl's Github Cog"""

    github_url = 'https://github.com'

    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }

    user_default = {
        'token': None,
        'notifications': {},
        'sent': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_user(**self.user_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.main_loop.start()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.main_loop.cancel()

    @tasks.loop(minutes=10.0)
    async def main_loop(self):
        await self.bot.wait_until_ready()
        log.info('%s: Start Loop: main_loop', self.__cog_name__)
        dt = datetime.datetime.now() - datetime.timedelta(minutes=10)
        all_users: dict = await self.config.all_users()
        for user_id, data in all_users.items():
            log.debug('user_id: %s', user_id)
            log.debug('data: %s', data)
            await self.process_notifications(user_id, dt, data)
        log.info('%s: Finish Loop: main_loop', self.__cog_name__)

    async def process_notifications(self, user_id, dt, data):
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

    @commands.group(name='github', aliases=['ghub'])
    async def _github(self, ctx):
        """Manage Github Options"""

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
