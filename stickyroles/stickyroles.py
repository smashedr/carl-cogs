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

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(enabled=False, roles=None)
        self.config.register_member(roles=None)

    async def cog_load(self):
        log.info(f'{self.__cog_name__}: Cog Load')

    async def cog_unload(self):
        log.info(f'{self.__cog_name__}: Cog Unload')

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        config = await self.config.guild(after.guild).all()
        if config['enabled'] and not after.bot:
            role_ids = [r.id for r in after.roles]
            role_ids.remove(after.guild.id)
            await self.config.member(after).roles.set(role_ids)

    @commands.Cog.listener()
    async def on_member_join(self, member):
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
    async def stickyroles(self, ctx):
        """Enable or disable remembering users roles and adding them back."""

    @stickyroles.command(name='enable', aliases=['on'])
    async def stickyrolesenable(self, ctx):
        """Enables Stickyroles."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Stickyroles is already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Stickyroles has been enabled.')
            await self.sync_roles(ctx)

    @stickyroles.command(name='disable', aliases=['off'])
    async def stickyroles_disable(self, ctx):
        """Disable Stickyroles."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Stickyroles is already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Stickyroles has been disabled.')

    @stickyroles.command(name='sync', aliases=['synchronize'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def stickyroles_sync(self, ctx):
        """Synchronize Stickyroles."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Stickyroles is disabled. Enable it first.')
            return
        await self.sync_roles(ctx)

    async def sync_roles(self, ctx):
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

    # @stickyroles.command(name='add')
    # async def stickyroles_add(self, ctx, role: discord.Role) -> None:
    #     """Adds a role to Stickyroles list of roles to add on rejoin"""
    #     roles = await self.config.guild(ctx.guild).roles()
    #     if role.id not in roles:
    #         roles.append(role.id)
    #         await self.config.guild(ctx.guild).roles.set(roles)
    #         await ctx.send(f'Added role `@{role.name}` to Stickyroles list.')
    #     else:
    #         await ctx.send(f'Role `@{role.name}` already in Stickyroles list.')
    #
    # @stickyroles.command(name='delete', aliases=['del', 'remove'])
    # async def stickyroles_delete(self, ctx, role: discord.Role):
    #     """Removes a role from Stickyroles list of roles to add on rejoin"""
    #     roles = await self.config.guild(ctx.guild).roles()
    #     if role.id in roles:
    #         roles.remove(role.id)
    #         await self.config.guild(ctx.guild).roles.set(roles)
    #         await ctx.send(f'Removed role `@{role.name}` from Stickyroles list.')
    #     else:
    #         await ctx.send(f'Role `@{role.name}` not in Stickyroles list.')
