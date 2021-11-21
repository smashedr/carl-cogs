import asyncio
import discord
import logging
from io import BytesIO
from pyppeteer import launch

from redbot.core import commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate


logger = logging.getLogger('red.carlcog')


class Carlcog(commands.Cog):
    """Carl's Carlcog Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.chrome = '/data/local-chromium/588429/chrome-linux/chrome'

    async def initialize(self) -> None:
        logger.info('Initializing Carlcog Cog')

    def cog_unload(self):
        logger.info('Unload Carlcog Cog')

    @commands.command(name='prefix')
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def cc_setprefix(self, ctx, *, prefix: str = None):
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

    # @commands.command(name='serverinfo', aliases=['guildinfo'])
    # @commands.guild_only()
    # async def cc_serverinfo(self, ctx, guild=None):
    #     """Shows server information."""
    #     if guild is None:
    #         guild = ctx.guild
    #     else:
    #         try:
    #             guild = self.bot.get_guild(int(guild))
    #         except ValueError:
    #             return await ctx.send("Not a valid guild id.")
    #     online = str(len([m.status for m in guild.members if str(m.status) == "online" or str(m.status) == "idle"]))
    #     total_users = str(len(guild.members))
    #     text_channels = [x for x in guild.channels if isinstance(x, discord.TextChannel)]
    #     voice_channels = [x for x in guild.channels if isinstance(x, discord.VoiceChannel)]
    #
    #     load = "```\nLoading guild info...```"
    #     waiting = await ctx.send(load)
    #
    #     data = "```ini\n"
    #     data += "[Name]:     {}\n".format(guild.name)
    #     data += "[ID]:       {}\n".format(guild.id)
    #     data += "[Region]:   {}\n".format(guild.region)
    #     data += "[Owner]:    {}\n".format(guild.owner)
    #     data += "[Users]:    {}/{}\n".format(online, total_users)
    #     data += "[Text]:     {} channels\n".format(len(text_channels))
    #     data += "[Voice]:    {} channels\n".format(len(voice_channels))
    #     data += "[Emojis]:   {}\n".format(len(guild.emojis))
    #     data += "[Roles]:    {} \n```".format(len(guild.roles))
    #     await asyncio.sleep(1)
    #     await waiting.edit(content=data)
