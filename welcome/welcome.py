import discord
import logging
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import Optional
from typing import cast

logger = logging.getLogger('red.welcome')

DEFAULT_SETTINGS = {
    'message': 'Everyone welcome {user.mention} to {guild}!',
    'enabled': False,
    'channel': None,
    'delete_after': None,
}


class Welcome(commands.Cog):
    """Carl's Welcome Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**DEFAULT_SETTINGS)

    async def initialize(self) -> None:
        logger.info('Initializing Welcome Cog')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        config = await self.config.guild(member.guild).all()
        if not config['enabled'] or not config['channel']:
            return
        channel = cast(discord.TextChannel, member.guild.get_channel(config['channel']))
        if not channel:
            logger.warning('Channel set but not found! Was it deleted?')
            return
        message = config['message'].format(user=member, guild=member.guild)
        await channel.send(message, delete_after=config['delete_after'])

    @commands.group(name='welcome')
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def welcome(self, ctx):
        """Options for sending welcome messages."""

    @welcome.command(name='channel', aliases=['c'])
    async def welcome_channel(self, ctx, channel: discord.TextChannel):
        """Sets the channel to send the welcome message."""
        await self.config.guild(ctx.guild).channel.set(channel.id)
        await ctx.send(f'Now sending welcome messages to: {channel.mention}')

    @welcome.command(name='message', aliases=['m'])
    async def welcome_message(self, ctx, *, message: str):
        """
        Adds a welcome message format for the guild to be chosen at random
        Variables that can be used are:
            {user.mention} {user.name} {user.id} {user} {guild}
        Example format:
            Everyone welcome {user.mention} to {guild}!
        """
        logger.debug('welcome_message: %s', message)
        if message:
            await self.config.guild(ctx.guild).message.set(message)
            await ctx.send('Welcome message updated.')

    @welcome.command(name='deleteafter', aliases=['da', 'delete'])
    async def welcome_deleteafter(self, ctx, delete_after: Optional[int] = None):
        """
        Set the time after which a welcome message is deleted in seconds.
        Leave empty or enter 0 to disable.
        """
        if delete_after:
            msg = f'Now deleting welcome messages after {delete_after} seconds.'
            await ctx.send(msg)
        else:
            await ctx.send("No longer deleting welcome messages.")
        await self.config.guild(ctx.guild).delete_after.set(delete_after)

    @welcome.command(name='enable', aliases=['e', 'on'])
    async def welcome_enable(self, ctx):
        """Enables welcome messages."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Server welcome messages are already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Server welcome have been enabled.')

    @welcome.command(name='disable', aliases=['d', 'off'])
    async def welcome_disable(self, ctx):
        """Disable welcome messages."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Server welcome messages are already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Server welcome messages have been disabled.')

    @welcome.command(name='status', aliases=['s', 'settings'])
    async def welcome_status(self, ctx):
        """Get welcome message status."""
        config = await self.config.guild(ctx.guild).all()
        channel_id = cast(discord.TextChannel, config['channel'])
        channel = discord.utils.get(ctx.guild.channels, id=channel_id)
        logger.debug(channel)
        enabled = str(bool(config['enabled']))
        out = f"Welcome Message Status:\n```Enabled: {enabled}\n"
        out += f"Delete After: {config['delete_after']}\n"
        if channel:
            out += f"Channel: #{channel.name} - {channel.id}\n"
        else:
            out += f"Channel: **NOT SET**\n"
        out += f"Message: {config['message']}```"
        await ctx.send(out)

    @welcome.command(name='test')
    async def welcome_test(self, ctx):
        """Test the Welcome Message."""
        config = await self.config.guild(ctx.guild).all()
        if not bool(config['enabled']):
            await ctx.send('Error: Module is disabled, enable first.')
        elif not config['channel']:
            await ctx.send('Error: Channel is not set, set one first.')
        elif not config['message']:
            await ctx.send('Error: Message is not set, set one first.')
        else:
            await self.on_member_join(ctx.author)
