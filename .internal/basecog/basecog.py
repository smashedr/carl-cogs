import discord
import logging
from typing import Optional, Union, List

from redbot.core import app_commands, commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.basecog')


class Basecog(commands.Cog):
    """Carl's Basecog Cog"""

    guild_default = {
        'enabled': False,
        'channels': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

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

    @commands.group(name='basecog', aliases=['bscog'])
    @commands.guild_only()
    @commands.admin()
    async def _basecog(self, ctx: commands.Context):
        """Options for managing Basecog."""

    @_basecog.command(name='channel', aliases=['c', 'chan', 'chann', 'channels'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _basecog_channel(self, ctx: commands.Context):
        """Set Channels for Basecog"""
        view = ChannelView(self, ctx.author)
        msg = 'Select channels for **Basecog**:'
        await view.send_initial_message(ctx, msg, True)

    @_basecog.command(name='toggle', aliases=['enable', 'disable', 'on', 'off'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _basecog_toggle(self, ctx: commands.Context):
        """Enable/Disable Basecog"""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await self.config.guild(ctx.guild).enabled.set(False)
            return await ctx.send(f'✅ {self.__cog_name__} Disabled.')
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f'✅ {self.__cog_name__} Enabled.')


class ChannelView(discord.ui.View):
    def __init__(self, cog, author: Union[discord.Member, discord.User, int],
                 timeout: int = 60 * 3, delete_after: int = 60):
        self.cog = cog
        self.user_id: int = author.id if hasattr(author, 'id') else int(author)
        self.delete_after: int = delete_after
        self.ephemeral: bool = False
        self.message: Optional[discord.Message] = None
        super().__init__(timeout=timeout)

    async def send_initial_message(self, ctx, message: Optional[str] = None,
                                   ephemeral: bool = False, **kwargs) -> discord.Message:
        self.ephemeral = ephemeral
        self.message = await ctx.send(content=message, view=self, ephemeral=self.ephemeral, **kwargs)
        return self.message

    async def on_timeout(self):
        await self.message.delete()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            return True
        msg = f"⛔ Looks like you did not create this response."
        await interaction.response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
        return False

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text],
                       min_values=0, max_values=25)
    async def select_channels(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        response = interaction.response
        channels: List[app_commands.AppCommandChannel] = []
        for value in select.values:
            channels.append(value)
        if not channels:
            await self.cog.config.guild(interaction.guild).channels.set([])
            msg = f'✅ No Channel Selected. All Channels Cleared.'
            return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
        ids = [x.id for x in channels]
        await self.cog.config.guild(interaction.guild).channels.set(ids)
        names = [x.name for x in channels]
        msg = f'✅ Basecog Set to Channels: {cf.humanize_list(names)}'
        return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
