import discord
import httpx
import io
import logging
from PIL import Image
from PIL import ExifTags
from typing import Dict, List, Optional, Union

from discord.ext import tasks
from redbot.core import app_commands, commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.exif')


class Exif(commands.Cog):
    """Carl's Exif Cog"""

    http_options = {
        'follow_redirects': True,
        'timeout': 10,
    }

    guild_default = {
        'enabled': False,
        'channels': [],
    }

    global_default = {
        'recent': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.config.register_global(**self.global_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data: Dict[str, str] = await self.bot.get_shared_api_tokens('exif')
        self.main_loop.start()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.main_loop.cancel()

    @tasks.loop(minutes=60.0)
    async def main_loop(self):
        await self.bot.wait_until_ready()
        log.info('%s: Run Loop: main_loop', self.__cog_name__)

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message):
        """Listens for Messages"""
        guild: discord.Guild = message.guild
        if message.author.bot or not guild:
            return log.debug('bot or no guild')
        if not message.embeds and not message.attachments:
            return log.debug('no EMBEDS')
        config: Dict = await self.config.guild(guild).all()
        if not config['enabled']:
            return log.debug('GUILD DISABLED: %s', guild.id)
        if message.channel.id in config['channels']:
            return log.debug('CHANNEL DISABLED: %s - %s', guild.id, message.channel.id)
        await self.process_message(message)

    async def process_message(self, message: discord.Message):
        log.debug('process_image')
        for embed in message.embeds:
            await self.process_url(message, embed=embed)
        for attachment in message.attachments:
            await self.process_url(message, attachment=attachment)

    async def process_url(self, message, embed: Optional[discord.Embed] = None,
                          attachment: Optional[discord.Attachment] = None):
        url = None
        if embed:
            url = embed.url
        elif attachment:
            url = attachment.url
        if not url:
            return log.debug('NO URL')
        log.debug('URL: %s', url)
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url)
            r.raise_for_status()
        file = io.BytesIO(r.content)
        image = Image.open(file)
        exif_data = image.getexif()
        gps_ifd = exif_data.get_ifd(ExifTags.IFD.GPSInfo)
        url = self.geohack_url_from_exif(gps_ifd)
        if not url:
            return log.info('NO GPS URL from geohack_url_from_exif')
        await message.reply(url)

    @commands.group(name='exif')
    @commands.guild_only()
    @commands.admin()
    async def _exif(self, ctx: commands.Context):
        """Options for managing Exif."""

    @_exif.command(name='toggle', aliases=['enable', 'disable', 'on', 'off'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _exif_toggle(self, ctx: commands.Context):
        """Enable/Disable Exif"""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await self.config.guild(ctx.guild).enabled.set(False)
            return await ctx.send(f'\U00002705 {self.__cog_name__} Disabled.')
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f'\U00002705 {self.__cog_name__} Enabled.')

    @_exif.command(name='channel', aliases=['c', 'chan', 'chann'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _exif_channel(self, ctx: commands.Context,
                               channel: Optional[discord.TextChannel],
                               silent: Optional[bool]):
        """Set Channel(s) for Exif"""
        channel: discord.TextChannel
        if not channel:
            await self.config.guild(ctx.guild).channel.set(0)
            return await ctx.send('\U0001F7E2 Disabled. Specify a channel to Enable.', ephemeral=True)

        log.debug('channel: %s', channel)
        log.debug('channel.type: %s', channel.type)
        if not str(channel.type) == 'text':
            return await ctx.send('\U0001F534 Channel must be a Text Channel.', ephemeral=True)

        guild_data = {'channel': channel.id, 'silent': silent}
        await self.config.guild(ctx.guild).set(guild_data)
        msg = f'\U0001F7E2 Will post ASN updates to channel: {channel.name}'
        if silent:
            msg += '\nMessages will post Silently as to not send notifications.'
        await ctx.send(msg, ephemeral=True)

    @_exif.command(name='channels')
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _exif_channels(self, ctx: commands.Context):
        """Set Channels for Exif"""
        view = ChannelView(self, ctx.author)
        msg = 'Select channels for **Exif**:'
        await view.send_initial_message(ctx, msg, True)

    @staticmethod
    def geohack_url_from_exif(gps_ifd: dict, name: Optional[str] = None) -> str:
        try:
            name = name.replace(' ', '_') if name else 'Unknown'
            dn, mn, sn = gps_ifd[2]
            dw, mw, sw = gps_ifd[4]
            params = f"{dn}_{mn}_{sn}_N_{dw}_{mw}_{sw}_W_scale:500000"
            return f"https://geohack.toolforge.org/geohack.php?pagename={name}&params={params}"
        except Exception as error:
            log.debug(error)


class ChannelView(discord.ui.View):
    def __init__(self, cog, author: Union[discord.Member, discord.User, int],
                 timeout: int = 60 * 3, delete_after: int = 60):
        self.cog = cog
        self.user_id: int = author.id if hasattr(author, 'id') else int(author)
        self.delete_after: int = delete_after
        self.ephemeral: bool = False
        self.message: Optional[discord.Message] = None
        super().__init__(timeout=timeout)

    async def on_timeout(self):
        await self.message.delete()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            return True
        msg = '\U0001F534 Looks like you did not create this response.'
        await interaction.response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
        return False

    async def send_initial_message(self, ctx, message: Optional[str] = None,
                                   ephemeral: bool = False, **kwargs) -> discord.Message:
        self.ephemeral = ephemeral
        self.message = await ctx.send(content=message, view=self, ephemeral=self.ephemeral, **kwargs)
        return self.message

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text],
                       min_values=0, max_values=25)
    async def select_channels(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        response = interaction.response
        channels: List[app_commands.AppCommandChannel] = []
        for value in select.values:
            channels.append(value)
        if not channels:
            await self.cog.config.guild(interaction.guild).channels.set([])
            msg = f'\U00002705 Exif Channels Cleared.'
            return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
        ids = [x.id for x in channels]
        await self.cog.config.guild(interaction.guild).channels.set(ids)
        names = [x.name for x in channels]
        msg = f'\U00002705 Exif Channels Set to: {cf.humanize_list(names)}'
        return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
