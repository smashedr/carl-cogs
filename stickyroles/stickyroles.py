import asyncio
import discord
import logging

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

log = logging.getLogger('red.stickyroles')


class Stickyroles(commands.Cog):
    """Carl's Stickyroles Cog"""

    guild_default = {
        'enabled': False,
        'roles': [],
        'rooms': [],
    }
    member_default = {
        'roles': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.config.register_member(**self.member_default)

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        config = await self.config.guild(after.guild).all()
        if config['enabled'] and not after.bot:
            role_ids = [r.id for r in after.roles]
            role_ids.remove(after.guild.id)
            await self.config.member(after).roles.set(role_ids)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not await self.config.guild(member.guild).enabled():
            return
        role_ids = await self.config.member(member).roles()
        try:
            log.debug(f'Updating roles for {member.name}')
            roles = [member.guild.get_role(r) for r in role_ids]
            await member.add_roles(*roles)
        except discord.Forbidden:
            log.warning('Error adding roles to {member.id} on rejoin.')

    @commands.group(name='stickyroles', aliases=['stickyrole', 'sr'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def stickyroles(self, ctx: commands.Context):
        """Enable or disable remembering users roles and adding them back."""

    @stickyroles.command(name='enable', aliases=['on'])
    async def stickyrolesenable(self, ctx: commands.Context):
        """Enables Stickyroles."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Stickyroles is already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Stickyroles has been enabled.')
            await self.sync_roles(ctx)

    @stickyroles.command(name='disable', aliases=['off'])
    async def stickyroles_disable(self, ctx: commands.Context):
        """Disable Stickyroles."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Stickyroles is already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Stickyroles has been disabled.')

    @stickyroles.command(name='sync', aliases=['synchronize'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def stickyroles_sync(self, ctx: commands.Context):
        """Synchronize Stickyroles."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Stickyroles is disabled. Enable it first.')
            return
        await self.sync_roles(ctx)

    async def sync_roles(self, ctx: commands.Context):
        steps = 2
        members = ctx.guild.members
        seconds = len(members) // steps
        msg = f'Sync all members roles now? ETA {seconds} seconds.'
        message = await ctx.send(msg, delete_after=60)
        pred = ReactionPredicate.yes_or_no(message, ctx.author)
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            await self.bot.wait_for('reaction_add', check=pred, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send('Request timed out.', delete_after=30)
            return

        if not pred.result:
            await message.delete()
            await ctx.send('So be it!', delete_after=10)
            return

        await message.clear_reactions()
        await message.edit(content='Role sync in progress now...')
        async for member in AsyncIter(members, delay=1, steps=steps):
            if not member.bot:
                log.debug(member)
                role_ids = [r.id for r in member.roles]
                role_ids.remove(member.guild.id)
                await self.config.member(member).roles.set(role_ids)
        await ctx.send('✅ All Done.', delete_after=30)
        await message.delete()
