import discord
import logging
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import box, humanize_list, pagify
from typing import cast

logger = logging.getLogger('red.mycog')

DEFAULT_WELCOME = "Welcome {user.name} to {guild.name}!"


class MyCog(commands.Cog):
    """My custom cog"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1337, force_registration=True
        )
        self.config.register_guild(
            message=DEFAULT_WELCOME,
            enabled=False,
            channel=None,
        )

    async def initialize(self) -> None:
        logger.debug('WINNING - Initializing MyCog Cog')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        logger.debug('member: %s', member)
        guild = member.guild
        logger.debug('guild: %s', guild)
        _enabled = await self.config.guild(guild).enabled()
        logger.debug('_enabled: %s', _enabled)
        if not _enabled:
            logger.debug('Welcome messages are DISABLED, not processing.')
            return
        _channel = await self.config.guild(guild).channel()
        logger.debug('_channel: %s', _channel)
        if not _channel:
            logger.warning('NO WELCOME CHANNEL SET!')
            return
        channel = cast(discord.TextChannel, guild.get_channel(_channel))
        logger.debug('channel.name: %s', channel.name)
        _msg = await self.config.guild(guild).message()
        await channel.send(_msg)

    @commands.command(name='mycom', aliases=['m'])
    async def mycom(self, ctx):
        """This does stuff!"""
        logger.debug(dir(ctx))
        logger.debug('ctx: %s', ctx)
        logger.debug('ctx.author: %s', ctx.author)
        logger.debug('ctx.guild: %s', ctx.guild)
        # print(self.bot.guilds)
        # print(self.bot.guilds[0])
        # print(dir(self.bot.guilds[0]))
        # print(self.bot.guilds[0].roles)
        # guild = self.bot.get_guild(188145201879973889)
        # print(dir(guild.channels[0]))
        # print(guild.channels[0])
        await ctx.send('I can do stuff! yes')

    @commands.group(name='welcome')
    @commands.guild_only()
    @commands.admin()
    async def welcome(self, ctx):
        """Options for sending welcome messages."""

    @welcome.command(name='test')
    async def welcome_test(self, ctx):
        """This does stuff!"""
        logger.debug('ctx: %s', ctx)
        logger.debug('ctx.author: %s', ctx.author)
        logger.debug('ctx.guild: %s', ctx.guild)
        await self.on_member_join(ctx.author)
        # _message = await self.config.guild(ctx.message.guild).message()
        # await ctx.send(_message)

    # @welcome.command(name='toggle')
    # async def welcome_toggle(self, ctx):
    #     """Toggle welcome messages on or off."""
    #     _enabled = not await self.config.guild(ctx.message.guild).enabled()
    #     logger.debug(_enabled)
    #     await self.config.TOGGLE.set(_enabled)
    #     text = 'enabled' if _enabled else 'disabled'
    #     await ctx.send(f'Server join messages have been {text}.')

    @welcome.command(name='enable')
    async def welcome_enable(self, ctx):
        """Enables welcome messages"""
        _enabled = await self.config.guild(ctx.message.guild).enabled()
        if _enabled:
            await ctx.send('Server welcome messages are already enabled.')
        else:
            await self.config.guild(ctx.message.guild).enabled.set(True)
            await ctx.send('Server welcome have been enabled.')

    @welcome.command(name='disable')
    async def welcome_disable(self, ctx):
        """Disable welcome messages"""
        _enabled = await self.config.guild(ctx.message.guild).enabled()
        if not _enabled:
            await ctx.send('Server welcome messages are already disabled.')
        else:
            await self.config.guild(ctx.message.guild).enabled.set(False)
            await ctx.send('Server welcome messages have been disabled.')

    @welcome.command(name='status')
    async def welcome_status(self, ctx):
        """Get welcome message status"""
        _enabled = await self.config.guild(ctx.message.guild).enabled()
        if _enabled:
            await ctx.send('Server welcome messages are enabled.')
        else:
            await ctx.send('Server welcome messages are disabled.')

    @welcome.command(name='channel')
    async def welcome_channel(self, ctx, channel: discord.TextChannel) -> None:
        """Sets the channel to send the welcome message"""
        # _channel = await self.config.guild(ctx.message.guild).channel()
        await self.config.guild(ctx.message.guild).channel.set(channel.id)
        msg = f'I will now send welcome messages to {channel.mention}'
        await ctx.send(msg)

    @welcome.command(name='message')
    async def welcome_message(self, ctx, *, message: str = None) -> None:
        """
        Adds a welcome message format for the guild to be chosen at random
        Variables that can be used are:
            {user.name} {user.discriminator} {user.id}
            {guild.name}
        Example format:
            Everyone welcome {user} to {guild}.
        """
        logger.debug('welcome_message: %s', message)
        if message:
            await self.config.guild(ctx.message.guild).message.set(message)
            await ctx.send('Welcome message has been set.')
        else:
            _message = await self.config.guild(ctx.message.guild).message()
            await ctx.send('Include a new message to change it.\n'
                           f'Current Welcome Message: ```{_message}```')
