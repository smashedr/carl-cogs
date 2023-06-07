import discord
import logging
import re
import webcolors
from typing import Optional

from discord.ext import tasks
from redbot.core import Config, app_commands, checks, commands
from redbot.core.utils import AsyncIter

log = logging.getLogger('red.colorme')


class ColorMe(commands.Cog):
    """Custom ColorMe Cog."""

    guild_default = {
        'enabled': False,
        'blocked_roles': [],
    }

    color_info_url = 'https://www.color-hex.com/color/'
    prefix = 'c:'

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)
        self.cleanup_roles.start()

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.cleanup_roles.cancel()

    @tasks.loop(minutes=30.0)
    async def cleanup_roles(self):
        log.info('%s: Cleanup Roles Task Run', self.__cog_name__)
        all_guilds: dict = await self.config.all_guilds()
        async for guild_id, data in AsyncIter(all_guilds.items(), delay=2, steps=10):
            if not data['enabled']:
                log.debug('Guild Disabled: %s', guild_id)
                continue
            guild: discord.Guild = self.bot.get_guild(int(guild_id))
            if not guild:
                log.debug('404 - Guild Not Found: %s', guild_id)
                continue
            async for role in AsyncIter(guild.roles, delay=2, steps=20):
                role: discord.Role
                if role.name.startswith(self.prefix):
                    if len(role.members) == 0:
                        log.debug('Guild: %s Removed Color Role: %s', guild.name, role.name)
                        await role.delete(reason='Color Role Cleanup')

    @staticmethod
    def _color_converter(hex_code_or_color_word: str) -> Optional[str]:
        """
        Used for user input on color
        Input:    discord.Color name, CSS3 color name, 0xFFFFFF, #FFFFFF, FFFFFF
        Output:   0xFFFFFF
        """
        # #FFFFFF and FFFFFF to 0xFFFFFF
        hex_match = re.match(r'#?[a-f0-9]{6}', hex_code_or_color_word.lower())
        if hex_match:
            hex_code = f"0x{hex_code_or_color_word.lstrip('#')}"
            return hex_code

        # discord.Color checking
        if hasattr(discord.Color, hex_code_or_color_word):
            hex_code = str(getattr(discord.Color, hex_code_or_color_word)())
            hex_code = hex_code.replace('#', '0x')
            return hex_code

        # CSS3 color name checking
        try:
            hex_code = webcolors.name_to_hex(hex_code_or_color_word, spec='css3')
            hex_code = hex_code.replace('#', '0x')
            return hex_code
        except ValueError:
            pass

    @commands.hybrid_command(name='color')
    @commands.guild_only()
    @commands.cooldown(3, 20, commands.BucketType.user)
    @commands.max_concurrency(1, commands.BucketType.user)
    @app_commands.describe(color='Optional: Hex Value, CSS Name, or Discord Color Name')
    async def color_command(self, ctx: commands.Context, color: Optional[str]):
        """Change the color of your name.
        `newcolor` must be a hex code like `#990000` or `990000`, a [Discord color name](https://discordpy.readthedocs.io/en/latest/api.html#colour),
        or a [CSS3 color name](https://www.w3.org/TR/2018/REC-css-color-3-20180619/#svg-color).
        """
        user = ctx.author
        guild = ctx.guild

        # Check if color command is enabled in guild
        enabled = await self.config.guild(guild).enabled()
        if not enabled:
            msg = '⛔ Color Not Enabled in this Guild. Contact Server Manager to Enable.'
            await ctx.send(msg, ephemeral=True, delete_after=60)
            return

        # Remove color if no color passed
        log.debug('color: %s', color)
        if not color:
            removed = None
            for role in user.roles:
                if role.name.startswith(self.prefix):
                    removed = role
                    log.debug('Removing Role %s from Member %s', role.name, user.name)
                    await user.remove_roles(role, reason='Removing Color Role')
            if removed:
                await ctx.send(f'✅ Color Removed: {removed.name}', ephemeral=True, delete_after=60)
            else:
                await ctx.send(f'⛔ No Color Roles Found.', ephemeral=True, delete_after=60)
            return

        # Validate color passed
        newcolor = self._color_converter(color.replace(' ', '_'))
        log.debug('newcolor: %s', newcolor)
        if not newcolor:
            msg = (
                '⛔ Not a valid color code. Use a hex code like #990000, '
                'a Discord color name or a CSS3 color name.\n'
                '<https://discordpy.readthedocs.io/en/latest/api.html#colour>\n'
                '<https://www.w3.org/TR/2018/REC-css-color-3-20180619/#svg-color>'
            )
            await ctx.send(msg, ephemeral=True, delete_after=60)
            return

        colorhex = newcolor.replace('0x', '')
        role_name = f'{self.prefix}{colorhex}'

        # Check if already has role, blocked_roles, and remove other roles
        blocked_roles = await self.config.guild(guild).blocked_roles()
        for role in user.roles:
            if role.name == role_name:
                log.debug('User already has requested role: %s - %s', role.id, role.name)
                msg = f'⛔ Looks like you already have color role: {role.name}'
                await ctx.send(msg, ephemeral=True, delete_after=60)
                return
            if role.id in blocked_roles:
                msg = '⛔ You have a role that is protected from color changes.'
                await ctx.send(msg, ephemeral=True, delete_after=60)
                return
            if role.name.startswith(self.prefix):
                log.debug('Removing Role %s from Member %s', role.name, user.name)
                await user.remove_roles(role, reason='Removing Color Role')

        # Get or create new color role
        log.debug('role_name: %s', role_name)
        role: discord.Role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            role: discord.Role = await guild.create_role(
                reason='Custom Color Role',
                name=role_name,
                colour=discord.Colour(int(newcolor, 16)),
                permissions=discord.Permissions.none()
            )
            log.debug('Created new role: %s - %s', role.id, role.name)

        # Add color role to user
        await user.add_roles(role)
        log.debug('Added Role: %s to User: %s', role.name, user.name)
        msg = f'✅ Color Updated: **{newcolor}**\n{self.color_info_url}{colorhex}'
        await ctx.send(msg, ephemeral=True, delete_after=60)

    @commands.group(name='colorme', aliases=['col'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def colorme(self, ctx):
        """Manage the Color Command Options"""

    @colorme.command(name='enable', aliases=['e', 'on'])
    async def _colorme_enable(self, ctx: commands.Context):
        """Enables Color"""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send(f'⛔ {self.__cog_name__} is already Enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send(f'✅ {self.__cog_name__} Enabled.')

    @colorme.command(name='disable', aliases=['d', 'off'])
    async def _colorme_disable(self, ctx: commands.Context):
        """Disable Color"""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send(f'⛔ {self.__cog_name__} is already Disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send(f'✅ {self.__cog_name__} Disabled.')

    # @colorme.command(name='set', aliases=['s'])
    # async def _colorme_set(self, ctx: commands.Context, user: discord.Member, color: Optional[str]):
    #     """Set a Color for a User"""
    #     # Copied from Color Command for quick manual setting of a users color
    #     guild = user.guild
    #
    #     # Check if color command is enabled in guild
    #     enabled = await self.config.guild(guild).enabled()
    #     if not enabled:
    #         msg = '⛔ Color Not Enabled in this Guild. Contact Server Manager to Enable.'
    #         await ctx.send(msg, ephemeral=True, delete_after=60)
    #         return
    #
    #     # Remove color if no color passed
    #     log.debug('color: %s', color)
    #     if not color:
    #         removed = None
    #         for role in user.roles:
    #             if role.name.startswith(self.prefix):
    #                 removed = role
    #                 log.debug('Removing Role %s from Member %s', role.name, user.name)
    #                 await user.remove_roles(role, reason='Removing Color Role')
    #         if removed:
    #             await ctx.send(f'✅ Color Removed: {removed.name}', ephemeral=True, delete_after=60)
    #         else:
    #             await ctx.send(f'⛔ No Color Roles Found.', ephemeral=True, delete_after=60)
    #         return
    #
    #     # Validate color passed
    #     newcolor = self._color_converter(color.replace(' ', '_'))
    #     log.debug('newcolor: %s', newcolor)
    #     if not newcolor:
    #         msg = (
    #             '⛔ Not a valid color code. Use a hex code like #990000, '
    #             'a Discord color name or a CSS3 color name.\n'
    #             '<https://discordpy.readthedocs.io/en/latest/api.html#colour>\n'
    #             '<https://www.w3.org/TR/2018/REC-css-color-3-20180619/#svg-color>'
    #         )
    #         await ctx.send(msg, ephemeral=True, delete_after=60)
    #         return
    #
    #     colorhex = newcolor.replace('0x', '')
    #     role_name = f'{self.prefix}{colorhex}'
    #
    #     # Check if already has role, blocked_roles, and remove other roles
    #     blocked_roles = await self.config.guild(guild).blocked_roles()
    #     for role in user.roles:
    #         if role.name == role_name:
    #             log.debug('User already has requested role: %s - %s', role.id, role.name)
    #             msg = f'⛔ Looks like you already have color role: {role.name}'
    #             await ctx.send(msg, ephemeral=True, delete_after=60)
    #             return
    #         if role.id in blocked_roles:
    #             msg = '⛔ You have a role that is protected from color changes.'
    #             await ctx.send(msg, ephemeral=True, delete_after=60)
    #             return
    #         if role.name.startswith(self.prefix):
    #             log.debug('Removing Role %s from Member %s', role.name, user.name)
    #             await user.remove_roles(role, reason='Removing Color Role')
    #
    #     # Get or create new color role
    #     log.debug('role_name: %s', role_name)
    #     role: discord.Role = discord.utils.get(guild.roles, name=role_name)
    #     if not role:
    #         role: discord.Role = await guild.create_role(
    #             reason='Custom Color Role',
    #             name=role_name,
    #             colour=discord.Colour(int(newcolor, 16)),
    #             permissions=discord.Permissions.none()
    #         )
    #         log.debug('Created new role: %s - %s', role.id, role.name)
    #
    #     # Add color role to user
    #     await user.add_roles(role)
    #     log.debug('Added Role: %s to User: %s', role.name, user.name)
    #     msg = f'✅ Color Updated: **{newcolor}**\n{self.color_info_url}{colorhex}'
    #     await ctx.send(msg, ephemeral=True, delete_after=60)

    # @colorme.command(name='block')
    # @checks.admin_or_permissions(manage_guild=True)
    # async def _colorme_block(self, ctx, role: discord.Role):
    #     """Add a role to the list of protected roles.
    #     Members with this role as top role will not be allowed to change color.
    #     Example: [p]colorme protect admin
    #     """
    #     blocked_roles = await self.config.guild(ctx.guild).blocked_roles()
    #     if role.id in blocked_roles:
    #         await ctx.send('⛔ That role is already protected.')
    #         return
    #     blocked_roles.append(role.id)
    #     await self.config.guild(ctx.guild).blocked_roles.set(blocked_roles)
    #     await ctx.send(f'✅ Users with top role {role} are blocked from color changes.')
    #
    # @colorme.command(name='unblock')
    # @checks.admin_or_permissions(manage_guild=True)
    # async def _colorme_unblock(self, ctx, role: discord.Role):
    #     """Remove a role from the list of blocked roles.
    #     Example: [p]colorme unprotect admin
    #     """
    #     blocked_roles = await self.config.guild(ctx.guild).blocked_roles()
    #     if role.id not in blocked_roles:
    #         await ctx.send('⛔ That role is not currently protected.')
    #         return
    #
    #     blocked_roles.remove(role.id)
    #     await self.config.guild(ctx.guild).blocked_roles.set(blocked_roles)
    #     await ctx.send(f'✅ Users with top role {role} are no longer protected from color changes.')
    #
    # @colorme.command(name='list')
    # async def _colorme_list(self, ctx):
    #     """Lists roles that are blocked from color changes."""
    #     guild = ctx.message.guild
    #     blocked_roles: list = await self.config.guild(guild).blocked_roles()
    #     msg_text = 'Protected role(s): '
    #     if len(blocked_roles) == 0:
    #         msg_text += 'None '
    #     for role in blocked_roles:
    #         protected_role: discord.Role = discord.utils.get(guild.roles, id=role)
    #         if protected_role is not None:
    #             msg_text += " '" + protected_role.name + "',"
    #     msg_text = msg_text[:-1] + '.'
    #     await ctx.send(msg_text)
