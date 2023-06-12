import datetime
import discord
import logging
from typing import Optional, Union, Tuple, Dict, List, Any

from redbot.core import app_commands, commands, Config
from redbot.core.utils import chat_formatting as cf

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

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message):
        """Listens for Messages"""
        guild: discord.Guild = message.guild
        if message.author.bot or not message.attachments or not guild:
            return
        enabled: bool = await self.config.guild(guild).enabled()
        if not enabled:
            return
        channels: List[int] = await self.config.guild(guild).channels()
        if message.channel.id in channels:
            return
        # run code here

    @staticmethod
    async def send_embed(ctx: Optional[commands.Context] = None,
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
        embed.set_author(name=f"@{ctx.author.name}")
        return await ctx.send(embed=embed)

    @commands.group(name='timer', aliases=['time'])
    @commands.guild_only()
    @commands.admin()
    async def _timer(self, ctx: commands.Context):
        """Options for managing Timer."""

    @_timer.command(name='start', aliases=['s', 'new', 'run', 'create'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _basecog_start(self, ctx: commands.Context):
        """Start a Timer"""
        user_conf = await self.config.user(ctx.author).all()
        if user_conf['timer']:
            # return await ctx.send('\U000026D4 You Have an Active Timer.')  # ⛔
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
    async def _basecog_update(self, ctx: commands.Context):
        """Stop a Timer"""
        user_conf = await self.config.user(ctx.author).all()
        if not user_conf['timer']:
            return await ctx.send("\U000026D4 No Timer's Found.")  # ⛔
        date = datetime.datetime.fromtimestamp(user_conf['timer'])
        message = await self.send_embed(ctx, 'Status', date, discord.Color.yellow())

    @_timer.command(name='stop', aliases=['end', 'done', 'finish'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _basecog_stop(self, ctx: commands.Context):
        """Stop a Timer"""
        user_conf = await self.config.user(ctx.author).all()
        if not user_conf['timer']:
            return await ctx.send("\U000026D4 No Timer's Found.")  # ⛔
        date = datetime.datetime.fromtimestamp(user_conf['timer'])
        message = await self.send_embed(ctx, 'Stop', date, discord.Color.green())
        user_conf = {
            'timer': None,
            'channel': 0,
            'message': 0,
        }
        await self.config.user(ctx.author).set(user_conf)

#     @_timer.command(name='channel', aliases=['c', 'chan', 'chann', 'channels'])
#     @commands.max_concurrency(1, commands.BucketType.guild)
#     async def _basecog_channel(self, ctx: commands.Context):
#         """Restrict Channels for Timer Usage"""
#         view = ChannelView(self, ctx.author)
#         msg = 'Select channels for **Basecog**:'
#         await view.send_initial_message(ctx, msg, True)
#
#     @_timer.command(name='toggle', aliases=['enable', 'disable', 'on', 'off'])
#     async def _basecog_enable(self, ctx: commands.Context):
#         """Enable/Disable Timer"""
#         enabled = await self.config.guild(ctx.guild).enabled()
#         if enabled:
#             await self.config.guild(ctx.guild).enabled.set(False)
#             return await ctx.send(f'\U00002705  {self.__cog_name__} Disabled.')  # ✅
#         await self.config.guild(ctx.guild).enabled.set(True)
#         await ctx.send(f'\U00002705  {self.__cog_name__} Enabled.')  # ✅
#
#
# class ChannelView(discord.ui.View):
#     def __init__(self, cog, author: Union[discord.Member, discord.User, int],
#                  timeout: int = 60 * 3, delete_after: int = 60):
#         self.cog = cog
#         self.user_id: int = author.id if hasattr(author, 'id') else int(author)
#         self.delete_after: int = delete_after
#         self.ephemeral: bool = False
#         self.message: Optional[discord.Message] = None
#         super().__init__(timeout=timeout)
#
#     async def send_initial_message(self, ctx, message: Optional[str] = None,
#                                    ephemeral: bool = False, **kwargs) -> discord.Message:
#         self.ephemeral = ephemeral
#         self.message = await ctx.send(content=message, view=self, ephemeral=self.ephemeral, **kwargs)
#         return self.message
#
#     async def on_timeout(self):
#         await self.message.delete()
#         self.stop()
#
#     async def interaction_check(self, interaction: discord.Interaction):
#         if interaction.user.id == self.user_id:
#             return True
#         msg = f"\U000026D4 Looks like you did not create this response."  # ⛔
#         await interaction.response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
#         return False
#
#     @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text],
#                        min_values=0, max_values=25)
#     async def select_channels(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
#         response = interaction.response
#         channels: List[app_commands.AppCommandChannel] = []
#         for value in select.values:
#             channels.append(value)
#         if not channels:
#             await self.cog.config.guild(interaction.guild).channels.set([])
#             msg = f'\U00002705 No Channel Selected. All Channels Cleared.'  # ✅
#             return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
#         ids = [x.id for x in channels]
#         await self.cog.config.guild(interaction.guild).channels.set(ids)
#         names = [x.name for x in channels]
#         msg = f'\U00002705 Basecog Set to Channels: {cf.humanize_list(names)}'  # ✅
#         return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
