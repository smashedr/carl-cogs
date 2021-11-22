import asyncio
import datetime
import discord
import logging
from io import BytesIO
from pyppeteer import launch

from redbot.core import Config, commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

logger = logging.getLogger('red.carlcog')


class Carlcog(commands.Cog):
    """Carl's Carlcog Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.chrome = '/data/local-chromium/588429/chrome-linux/chrome'
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(alert_channel=None)

    async def initialize(self) -> None:
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
            await ctx.send(f'Custom prefix reset to default: ```{prefixes}```')
        else:
            prefixes = prefix.split()
            logger.debug(prefixes)
            await self.bot.set_prefixes(prefixes, ctx.guild)
            await ctx.send(f'Prefixes for guild set to: ```{prefixes}```')

    @commands.command(name='checksite', aliases=['cs'])
    @commands.cooldown(2, 15, commands.BucketType.user)
    async def cc_checksite(self, ctx, url: str):
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

    @commands.command(name='moveusto', aliases=['mut'])
    @commands.admin_or_permissions(move_members=True)
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def cc_moveusto(self, ctx, *, channel: discord.VoiceChannel):
        """Moves all users from your current channel to <channel>"""
        await ctx.trigger_typing()
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send('You are not in a Voice channel.', delete_after=15)
            return

        source = ctx.author.voice.channel
        if channel == source:
            await ctx.send(f'You are already in the destination channel '
                           f'{channel.name}.', delete_after=15)
            return

        await ctx.send(f'Stand by, moving **{len(source.members)}** members '
                       f'to **{channel.name}**', delete_after=60)
        async with ctx.channel.typing():
            for member in await AsyncIter(source.members):
                await member.move_to(channel)
        await ctx.send('All done, enjoy =)', delete_after=60)

    @commands.command(name='bitrateall', aliases=['bra'])
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def cc_bitrateall(self, ctx, bitrate: int = 0):
        """Set the bitrate for ALL channels to Guild Max or <bitrate>."""
        await ctx.trigger_typing()
        limit = ctx.guild.bitrate_limit
        if bitrate and not (8000 > bitrate > 360000) or bitrate > limit:
            await ctx.send(f'Invalid bitrate. Specify a number between `8000` '
                           f'and `360000` or leave blank for the guild max of '
                           f'`{limit}`')
            return

        new_rate = bitrate or limit
        updated = []
        async with ctx.channel.typing():
            for channel in await AsyncIter(ctx.guild.voice_channels):
                if channel.bitrate != new_rate:
                    updated.append(channel.name)
                    reason = f'{ctx.author} used bitrateall {new_rate}'
                    await channel.edit(bitrate=new_rate, reason=reason)

        await ctx.send(f'Done. Updated: ```{updated or "Nothing"}```')

    @commands.command(name='roleaddmulti', aliases=['ram'])
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def cc_roleaddmulti(self, ctx, role: discord.Role, *, members: str):
        """Attempts to add a <role> to multiple <users>, space separated..."""
        await ctx.trigger_typing()
        members = members.split()
        logger.debug(members)
        num_members = len(ctx.guild.members)
        message = await ctx.send(f'Will process **{num_members}** guild '
                                 f'members for role `@{role.name}` \n'
                                 f'Minimum ETA **{num_members//5}** sec. '
                                 f'Proceed?')

        pred = ReactionPredicate.yes_or_no(message, ctx.author)
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            await self.bot.wait_for('reaction_add', check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send('Request timed out. Aborting.', delete_after=60)
            await message.delete()
            return

        if not pred.result:
            await ctx.send('Aborting...', delete_after=5)
            await message.delete()
            return

        await ctx.send('Processing now. Please wait...')
        users = []
        async with ctx.channel.typing():
            for member in await AsyncIter(ctx.guild.members, delay=1, steps=5):
                for m in await AsyncIter(members):
                    if (member.name and m.lower() == member.name.lower()) or \
                            (member.nick and m.lower() == member.nick.lower()):
                        if role not in member.roles:
                            await member.add_roles(role, reason=f'{ctx.author} roleaddmulti')
                            users.append(member.name)
        await ctx.send(f'Done! Added @{role.mention} to:\n{users}')
        await message.delete()
