import asyncio
import datetime
import discord
import logging
from io import BytesIO
from pyppeteer import launch

from redbot.core import Config, commands

logger = logging.getLogger('red.carlcog')


class Carlcog(commands.Cog):
    """Carl's Carlcog Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.chrome = '/data/local-chromium/588429/chrome-linux/chrome'
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(alert_channel=None)

    async def cog_load(self) -> None:
        logger.info('Initializing Carlcog Cog')

    def cog_unload(self):
        logger.info('Unload Carlcog Cog')

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Notify a channel when the bot leaves a server."""
        logger.debug(guild)
        await self.process_guild_join_leave(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Notify a channel when the bot joins a server."""
        logger.debug(guild)
        await self.process_guild_join_leave(guild, join=True)

    async def process_guild_join_leave(self, guild: discord.Guild, join=False):
        """Notify a channel when the bot joins a server."""
        channel_id = await self.config.alert_channel()
        if not channel_id:
            logger.debug('No channel_id')
            return

        channel = self.bot.get_channel(channel_id)

        if guild.is_icon_animated():
            icon_url = guild.icon_url_as(format='gif')
        else:
            icon_url = guild.icon_url_as(format='png')

        em = discord.Embed(color=guild.me.color)

        if join:  # Joined
            created_at = int(guild.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())
            description = (
                f'{self.bot.user.mention} joined a new server \U0001F4E5 \n\n'
                f"Created on **<t:{created_at}:D>** "
                f"over **<t:{created_at}:R>**"
            )
            em.colour = discord.Colour.green()
        else:  # Parted
            description = f'{self.bot.user.mention} left a server \U0001F4E4 \n'
            em.colour = discord.Colour.red()

        em.set_thumbnail(url=icon_url)
        em.title = guild.name
        em.description = description
        em.add_field(name='Members', value=len(guild.members))
        em.add_field(name='Roles', value=len(guild.roles))
        em.add_field(name='Channels', value=len(guild.channels))
        em.add_field(name='Total Servers', value=len(self.bot.guilds))
        em.add_field(name='Total Users', value=len(self.bot.users))
        em.timestamp = datetime.datetime.now(datetime.timezone.utc)
        await channel.send(embed=em)

    @commands.command(name='setalertchannel', aliases=['sac'])
    @commands.is_owner()
    async def cc_set_alert_channel(self, ctx, channel: discord.TextChannel):
        """Sets the alert channel for various internal alerts."""
        try:
            await channel.send('Testing Write Access.', delete_after=15)
            await self.config.alert_channel.set(channel.id)
            await ctx.send(f'Updated alert channel to: {channel.mention}')
        except Exception as error:
            logger.exception(error)
            await ctx.send(f'Error setting channel to {channel}: {error}')

    @commands.command(name='prefix')
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def cc_set_prefix(self, ctx, *, prefix: str = None):
        """Sets the <prefix(s)> for the server. Leave blank to reset."""
        await ctx.trigger_typing()
        if not prefix:
            await self.bot.set_prefixes([], ctx.guild)
            prefixes = await self.bot.get_valid_prefixes(ctx.guild)
            await ctx.send(f'Custom prefix reset to default: **{prefixes}**')
        else:
            prefixes = prefix.split()
            logger.debug(prefixes)
            await self.bot.set_prefixes(prefixes, ctx.guild)
            await ctx.send(f'Prefixes for guild set to: **{prefixes}**')

    @commands.command(name='checksite', aliases=['cs'])
    @commands.cooldown(2, 15, commands.BucketType.user)
    async def cc_check_site(self, ctx, url: str):
        """Check the status of a site at given <url>"""
        async with ctx.channel.typing():
            try:
                url = url.strip('<>')
                logger.debug(url)
                browser = await launch(
                    executablePath=self.chrome, args=['--no-sandbox'])
                page = await browser.newPage()
                await page.setViewport({'width': 1280, 'height': 960})
                await page.goto(url, timeout=1000 * 12)
                result = await page.screenshot()
                await browser.close()
                data = BytesIO()
                data.write(result)
                data.seek(0)
                file = discord.File(data, filename='screenshot.png')
                await ctx.send(f'Results for: `{url}`', files=[file])
            except Exception as error:
                logger.exception(error)
                await ctx.send(error)
