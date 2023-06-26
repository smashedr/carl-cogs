import datetime
import discord
import logging
from typing import Optional

from redbot.core import commands, Config

log = logging.getLogger('red.timer')


class Timer(commands.Cog):
    """Carl's Timer Cog"""

    # guild_default = {
    #     'enabled': True,
    #     'channels': [],
    # }
    # channel_default = {
    #     'timers': [],
    # }
    user_default = {
        'timer': None,
        'channel': 0,
        'message': 0,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        # self.config.register_guild(**self.guild_default)
        # self.config.register_channel(**self.channel_default)
        self.config.register_user(**self.user_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    # @commands.Cog.listener(name='on_message_without_command')
    # async def on_message_without_command(self, message: discord.Message):
    #     """Listens for Messages"""
    #     guild: discord.Guild = message.guild
    #     if message.author.bot or not message.attachments or not guild:
    #         return
    #     enabled: bool = await self.config.guild(guild).enabled()
    #     if not enabled:
    #         return
    #     channels: List[int] = await self.config.guild(guild).channels()
    #     if message.channel.id in channels:
    #         return
    #     # run code here

    @staticmethod
    async def send_embed(ctx: Optional[commands.Context],
                         title: str = 'Start',
                         date: Optional[datetime.datetime] = None,
                         color: Optional[discord.Color] = discord.Color.red()
                         ) -> discord.Message:
        delta = datetime.datetime.now() - date if date else datetime.timedelta(seconds=0)
        human = str(datetime.timedelta(seconds=delta.seconds))
        embed = discord.Embed(
            title=f'Timer - {title}',
            color=color,
            description=f'⌛ {human}'
        )
        embed.set_author(name=f'@{ctx.author.name}')
        return await ctx.send(embed=embed)

    @commands.group(name='timer', aliases=['time'])
    @commands.guild_only()
    @commands.admin()
    async def _timer(self, ctx: commands.Context):
        """Options for managing Timer."""

    @_timer.command(name='start', aliases=['s', 'new', 'run', 'create'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _timer_start(self, ctx: commands.Context):
        """Start a Timer"""
        user_conf = await self.config.user(ctx.author).all()
        if user_conf['timer']:
            # return await ctx.send("⛔ You Have an Active Timer.")
            date = datetime.datetime.fromtimestamp(user_conf['timer'])
            return await self.send_embed(ctx, 'Currently Running', date, discord.Color.yellow())
        message = await self.send_embed(ctx)
        user_conf = {
            'timer': datetime.datetime.now().timestamp(),
            'channel': ctx.channel.id,
            'message': message.id,
        }
        await self.config.user(ctx.author).set(user_conf)

    @_timer.command(name='update', aliases=['show', 'view', 'status', 'display'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _timer_update(self, ctx: commands.Context):
        """Show a Timer"""
        user_conf = await self.config.user(ctx.author).all()
        if not user_conf['timer']:
            return await ctx.send("⛔ No Timer's Found.")
        date = datetime.datetime.fromtimestamp(user_conf['timer'])
        await self.send_embed(ctx, 'Status', date, discord.Color.yellow())

    @_timer.command(name='stop', aliases=['end', 'done', 'finish'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _timer_stop(self, ctx: commands.Context):
        """Stop a Timer"""
        user_conf = await self.config.user(ctx.author).all()
        if not user_conf['timer']:
            return await ctx.send("⛔ No Timer's Found.")
        date = datetime.datetime.fromtimestamp(user_conf['timer'])
        await self.send_embed(ctx, 'Stop', date, discord.Color.green())
        user_conf = {'timer': None, 'channel': 0, 'message': 0}
        await self.config.user(ctx.author).set(user_conf)
