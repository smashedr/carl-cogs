import discord
import logging

from redbot.core import commands, Config

log = logging.getLogger('red.liverole')


class Liverole(commands.Cog):
    """Carl's Liverole Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(enabled=False, role=None)

    async def cog_load(self):
        log.info(f'{self.__cog_name__}: Cog Load')

    async def cog_unload(self):
        log.info(f'{self.__cog_name__}: Cog Unload')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or not (before.self_stream or after.self_stream):
            return

        config = await self.config.guild(member.guild).all()
        if not config['enabled'] or not config['role']:
            return

        role = member.guild.get_role(config['role'])
        if not role:
            return

        # go live
        if after.self_stream and after.channel:
            if role not in member.roles:
                log.info(f'Adding {role.id} to {member.id}')
                await member.add_roles(role, reason='Liverole user live.')
            else:
                log.debug(f'User already has {role.id} role.')

        # end live
        if (not after.self_stream and after.channel) or \
                (after.self_stream and not after.channel):
            if role in member.roles:
                log.info(f'Removing {role.id} from {member.id}')
                await member.remove_roles(role, reason='Liverole user not live,')
            else:
                log.debug(f'User does not have {role.id} role.')

    @commands.group(name='liverole', aliases=['lr'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def liverole(self, ctx):
        """Options for manging Liverole."""

    @liverole.command(name='role', aliases=['r'])
    async def liverole_channel(self, ctx, *, role: discord.Role):
        """Sets the Liverole Role."""
        await self.config.guild(ctx.guild).role.set(role.id)
        await ctx.send(f'Live role set to: `@{role.name}`')

    @liverole.command(name='enable', aliases=['e', 'on'])
    async def liverole_enable(self, ctx):
        """Enables Liverole."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Server liverole messages are already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Server liverole have been enabled.')

    @liverole.command(name='disable', aliases=['d', 'off'])
    async def liverole_disable(self, ctx):
        """Disable Liverole."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Server liverole messages are already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Server liverole messages have been disabled.')

    @liverole.command(name='status', aliases=['s', 'settings'])
    async def liverole_status(self, ctx):
        """Get Liverole status."""
        config = await self.config.guild(ctx.guild).all()
        role = ctx.guild.get_role(config['role'])
        role_name = f'`@{role.name}`' if role else '**NOT SET**'
        out = f'Liverole Settings:\n' \
              f'Status: **{config["enabled"]}**\n' \
              f'Role: {role_name}'
        await ctx.send(out)

