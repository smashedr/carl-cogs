import asyncio
import discord
import logging

from redbot.core import commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate


logger = logging.getLogger('red.carlcog')


class Carlcog(commands.Cog):
    """Carl's Carlcog Cog"""
    def __init__(self, bot):
        self.bot = bot

    async def initialize(self) -> None:
        logger.info('Initializing Carlcog Cog')

    @commands.group(name='prefix')
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def carl_prefix(self, ctx):
        """Sets the prefix on a per-guild basis. You may provide multiple."""

    @carl_prefix.command(name='set', aliases=['s'])
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def carl_setprefix(self, ctx, *, prefix: str = None):
        """Sets the prefix on a per-guild basis. You may provide multiple."""
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

    @commands.command(name='moveusto', aliases=['mut'])
    @commands.admin_or_permissions(move_members=True)
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def carl_moveusto(self, ctx, *, channel: discord.VoiceChannel):
        """Moves all users from your current channel to `channel`"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send('You are not in a Voice channel.', delete_after=15)
            return

        source = ctx.author.voice.channel
        if channel == source:
            await ctx.send(f'You are already in the destination channel '
                           f'{channel.name}.', delete_after=15)
            return

        await ctx.send(f'Stand by, moving {len(source.members)} members to '
                       f'**{channel.name}**', delete_after=60)
        await ctx.trigger_typing()
        for member in await AsyncIter(source.members, delay=0.2):
            await member.move_to(channel)
        await ctx.send('All done, enjoy =)', delete_after=60)

    @commands.command(name='bitrateall', aliases=['bra'])
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def carl_bitrateall(self, ctx, bitrate: int = 0):
        """Set the bitrate for ALL channels to Guild Max or `bitrate`."""
        await ctx.trigger_typing()
        new_rate = bitrate or ctx.guild.bitrate_limit
        updated = []
        for channel in await AsyncIter(ctx.guild.channels):
            if str(channel.type) == 'voice':
                if channel.bitrate != new_rate:
                    updated.append(channel.name)
                    reason = f'{ctx.author} used bitrateall {new_rate}'
                    await channel.edit(bitrate=new_rate, reason=reason)

        await ctx.send(f'Done. Updated: ```{updated or "Nothing"}```')

    @commands.command(name='roleaddmulti', aliases=['ram'])
    @commands.admin()
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def carl_roleaddmulti(self, ctx, role: discord.Role, *, members: str):
        """Attempts to add a `role` to multiple `users`, space separated..."""
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
        await ctx.send(f'Done! Added `@{role.name}` to:\n{users}')
        await message.delete()
