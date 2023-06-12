import datetime
import discord
import logging
from io import BytesIO
from PIL import Image
from pyzbar.pyzbar import Decoded, decode, ZBarSymbol
from typing import Optional, Union, Tuple, Dict, List

from redbot.core import app_commands, commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.qrscanner')


class Qrscanner(commands.Cog):
    """Carl's Qrscanner Cog"""

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
        """Find QR code in message attachments"""
        guild = message.guild
        if message.author.bot or not message.attachments or not guild:
            return
        enabled = await self.config.guild(guild).enabled()
        if not enabled:
            return

        for attachment in message.attachments:
            content_type = attachment.content_type
            if not content_type:
                log.warning('Unknown Content Type')
                continue
            if 'image' not in content_type:
                log.debug('Attachment Not Image')
                continue

            try:
                fp: BytesIO = BytesIO(await attachment.read())
                image: Image = Image.open(fp)
                codes: List[Decoded] = decode(image, symbols=[ZBarSymbol.QRCODE])
                log.debug('Found %s codes', len(codes))
            except Exception as error:
                log.error('Error: %s', error, exc_info=True)
                return
            if not codes:
                log.debug('No QR Codes Found')
                return

            log.debug('codes: %s', len(codes))
            for code in codes:
                data: str = code.data.decode()
                contents = 'QR Code Found:\n'
                contents += f'{data[:800]}...' if len(data) > 800 else data
                await message.reply(contents, allowed_mentions=discord.AllowedMentions.none())

    @commands.group(name='qrscanner', aliases=['qr', 'qrs', 'qrscan'])
    @commands.guild_only()
    @commands.admin()
    async def _qrs(self, ctx: commands.Context):
        """Options for managing QR Scanner."""

    @_qrs.command(name='channel', aliases=['c', 'chan', 'chann', 'channels'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _qrs_channel(self, ctx: commands.Context):
        """Set Channels to limit QR Scanner too"""
        view = ChannelView(self, ctx.author)
        msg = 'Select channels enable **QR Scanner** on:'
        await view.send_initial_message(ctx, msg, True)

    @_qrs.command(name='toggle', aliases=['enable', 'disable', 'on', 'off'])
    async def _qrs_enable(self, ctx: commands.Context):
        """Enables QR Scanner"""
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
        msg = f"\U000026D4 Looks like you did not create this response."  # ⛔
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
            msg = f'\U00002705 No Channel Selected. Now QR Scanning All Channels'  # ✅
            return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
        ids = [x.id for x in channels]
        await self.cog.config.guild(interaction.guild).channels.set(ids)
        names = [x.name for x in channels]
        msg = f'\U00002705 QR Scanning now Limited to Channels: {cf.humanize_list(names)}'  # ✅
        return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
